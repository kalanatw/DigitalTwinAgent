"""
Updated Document Views with User-Centric Access Controls
"""

import json
import logging
import os
from threading import Thread
from typing import Optional
from uuid import UUID

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .document_utils import DocumentProcessor, EmbeddingGenerator, SemanticSearch
from .models import (
    TwinVersion,
    Document,
    TwinVersionShare,
    DocumentShare,
)
from .permissions import check_document_access, check_twin_version_access
from .usage_tracker import record_document_usage, record_token_usage

logger = logging.getLogger(__name__)


# User-centric validation functions
def validate_twin_version_access(
    user: User, twin_version_id: UUID, require_owner: bool = False
) -> "TwinVersion":
    """
    Validate that user has access to a twin version.

    Args:
        user: Django User object
        twin_version_id: UUID of twin version
        require_owner: If True, user must be owner (for uploads/modifications)

    Returns:
        TwinVersion object if access granted

    Raises:
        Http404: If no access or twin version not found
    """
    try:
        if require_owner:
            # Only owner can modify
            twin_version = TwinVersion.objects.get(id=twin_version_id, user=user)
        else:
            # Owner, public, or explicitly shared
            twin_version = TwinVersion.objects.get(
                Q(id=twin_version_id)
                & (
                    Q(user=user)
                    | Q(is_shared=True)  # Own twin version
                    | Q(  # Public twin version
                        shares__shared_with=user
                    )  # Explicitly shared
                )
            )
        return twin_version
    except TwinVersion.DoesNotExist:
        raise Http404("Twin version not found or access denied")


def validate_document_access(user, document_id, require_owner=False):
    """
    Validate that user has access to a document through twin version ownership.

    Args:
        user: Django User object
        document_id: UUID of document
        require_owner: If True, user must be owner of document or twin version

    Returns:
        Document object if access granted

    Raises:
        Http404 if no access
    """
    try:
        if require_owner:
            # User must own document or own the twin version
            document = Document.objects.get(
                Q(id=document_id)
                & (
                    Q(user=user)
                    | Q(  # User uploaded the document
                        twin_version__user=user
                    )  # User owns the twin version
                )
            )
        else:
            # Access through twin version permissions
            document = Document.objects.get(
                Q(id=document_id)
                & (
                    Q(user=user)
                    | Q(twin_version__user=user)  # User uploaded the document
                    | Q(twin_version__is_shared=True)  # User owns twin version
                    | Q(  # Public twin version
                        twin_version__shares__shared_with=user
                    )  # Shared twin version
                )
            )
        return document
    except Document.DoesNotExist:
        raise Http404("Document not found or access denied")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def twin_version_list_view(request):
    """API endpoint for listing and creating twin versions"""

    # Require authentication
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    if request.method == "GET":
        """List twin versions for the current user"""
        try:
            # Get user's own twin versions
            user_versions = TwinVersion.objects.filter(
                user=request.user, is_active=True
            )

            # Get shared twin versions (explicitly shared with the user)
            shared_with_user = TwinVersion.objects.filter(
                shares__shared_with=request.user, is_active=True
            )

            # Get publicly shared twin versions
            public_versions = TwinVersion.objects.filter(
                is_shared=True, is_active=True
            ).exclude(
                user=request.user
            )  # Exclude user's own

            # Annotate with document counts
            user_versions = user_versions.annotate(document_count=Count("documents"))
            shared_with_user = shared_with_user.annotate(
                document_count=Count("documents")
            )
            public_versions = public_versions.annotate(
                document_count=Count("documents")
            )

            # Serialize
            own_versions = [
                {
                    "id": str(v.id),
                    "name": v.name,
                    "description": v.description,
                    "version": v.version,
                    "document_count": v.document_count,
                    "created_at": v.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_active": v.is_active,
                    "is_shared": v.is_shared,
                    "owner": "you",
                }
                for v in user_versions
            ]

            shared_versions = [
                {
                    "id": str(v.id),
                    "name": v.name,
                    "description": v.description,
                    "version": v.version,
                    "document_count": v.document_count,
                    "created_at": v.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_active": v.is_active,
                    "is_shared": True,
                    "owner": f"{v.user.username}" if v.user else "Unknown",
                }
                for v in list(shared_with_user) + list(public_versions)
            ]

            return JsonResponse(
                {
                    "twin_versions": own_versions + shared_versions,
                    "own_versions": own_versions,
                    "shared_versions": shared_versions,
                }
            )

        except Exception as e:
            logger.error(f"Error listing twin versions: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    elif request.method == "POST":
        """Create a new twin version"""
        try:
            data = json.loads(request.body)

            name = data.get("name", "New Twin Version").strip()
            version = data.get("version", "1.0").strip()

            # Check if this name/version combination already exists
            counter = 1
            original_name = name
            original_version = version

            while TwinVersion.objects.filter(name=name, version=version).exists():
                # Generate a unique name by adding counter
                name = f"{original_name} ({counter})"
                counter += 1

                # If counter gets too high, also modify version
                if counter > 10:
                    version = f"{original_version}.{counter-10}"
                    name = original_name  # Reset name when changing version
                    counter = 1

            # Create new twin version associated with current user
            twin_version = TwinVersion.objects.create(
                name=name,
                description=data.get("description", ""),
                version=version,
                user=request.user,
                is_shared=data.get("is_shared", False),
            )

            # Share with specific users if provided
            shared_with_usernames = data.get("share_with", [])
            if shared_with_usernames:
                from django.contrib.auth.models import User

                for username in shared_with_usernames:
                    try:
                        user = User.objects.get(username=username)
                        TwinVersionShare.objects.create(
                            twin_version=twin_version, shared_with=user
                        )
                    except User.DoesNotExist:
                        logger.warning(
                            f"Cannot share with non-existent user: {username}"
                        )

            return JsonResponse(
                {
                    "id": str(twin_version.id),
                    "name": twin_version.name,
                    "description": twin_version.description,
                    "version": twin_version.version,
                    "created_at": twin_version.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_active": twin_version.is_active,
                    "is_shared": twin_version.is_shared,
                },
                status=201,
            )

        except Exception as e:
            logger.error(f"Error creating twin version: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)


class TwinVersionDetailView(View):
    """API endpoint for retrieving, updating, and deleting a twin version"""

    @method_decorator(login_required)
    @method_decorator(check_twin_version_access)
    def get(self, request, twin_version_id):
        """Get details for a specific twin version"""
        try:
            twin_version = get_object_or_404(TwinVersion, id=twin_version_id)

            # Check if user can manage (only owner can manage)
            can_manage = twin_version.user == request.user

            # Count documents
            document_count = Document.objects.filter(
                twin_version=twin_version, is_enabled=True
            ).count()

            # List shared users
            shared_users = []
            if can_manage:
                shared_users = list(
                    TwinVersionShare.objects.filter(
                        twin_version=twin_version
                    ).values_list("shared_with__username", flat=True)
                )

            return JsonResponse(
                {
                    "id": str(twin_version.id),
                    "name": twin_version.name,
                    "description": twin_version.description,
                    "version": twin_version.version,
                    "created_at": twin_version.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_active": twin_version.is_active,
                    "is_shared": twin_version.is_shared,
                    "document_count": document_count,
                    "can_manage": can_manage,
                    "owner": (
                        twin_version.user.username if twin_version.user else "Unknown"
                    ),
                    "shared_with": shared_users,
                }
            )

        except Http404:
            return JsonResponse({"error": "Twin version not found"}, status=404)
        except Exception as e:
            logger.error(f"Error retrieving twin version: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    @method_decorator(login_required)
    @method_decorator(check_twin_version_access)
    def put(self, request, twin_version_id):
        """Update a twin version - only the owner can update"""
        try:
            twin_version = get_object_or_404(TwinVersion, id=twin_version_id)

            # Only owner can update
            if twin_version.user != request.user:
                return JsonResponse(
                    {"error": "You do not have permission to update this twin version"},
                    status=403,
                )

            data = json.loads(request.body)

            # Update fields
            twin_version.name = data.get("name", twin_version.name)
            twin_version.description = data.get("description", twin_version.description)
            twin_version.version = data.get("version", twin_version.version)
            twin_version.is_active = data.get("is_active", twin_version.is_active)
            twin_version.is_shared = data.get("is_shared", twin_version.is_shared)
            twin_version.save()

            # Handle sharing updates
            if "share_with" in data:
                from django.contrib.auth.models import User

                # Clear existing shares
                TwinVersionShare.objects.filter(twin_version=twin_version).delete()

                # Add new shares
                for username in data["share_with"]:
                    try:
                        user = User.objects.get(username=username)
                        TwinVersionShare.objects.create(
                            twin_version=twin_version, shared_with=user
                        )
                    except User.DoesNotExist:
                        logger.warning(
                            f"Cannot share with non-existent user: {username}"
                        )

            return JsonResponse(
                {
                    "id": str(twin_version.id),
                    "name": twin_version.name,
                    "description": twin_version.description,
                    "version": twin_version.version,
                    "is_active": twin_version.is_active,
                    "is_shared": twin_version.is_shared,
                }
            )

        except Http404:
            return JsonResponse({"error": "Twin version not found"}, status=404)
        except Exception as e:
            logger.error(f"Error updating twin version: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    @method_decorator(login_required)
    def delete(self, request, twin_version_id):
        """Delete a twin version - only owner can delete"""
        try:
            twin_version = get_object_or_404(TwinVersion, id=twin_version_id)

            # Only owner can delete
            if twin_version.user != request.user:
                return JsonResponse(
                    {"error": "You do not have permission to delete this twin version"},
                    status=403,
                )

            # Mark as inactive instead of deleting
            twin_version.is_active = False
            twin_version.save()

            return JsonResponse({"message": "Twin version deleted successfully"})

        except Http404:
            return JsonResponse({"error": "Twin version not found"}, status=404)
        except Exception as e:
            logger.error(f"Error deleting twin version: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def document_list_view(request):
    """API endpoint for listing and uploading documents"""

    # Require authentication
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    if request.method == "GET":
        try:
            twin_version_id = request.GET.get("twin_version_id")

            if twin_version_id:
                # Validate access to specific twin version
                twin_version = validate_twin_version_access(
                    request.user, twin_version_id
                )

                # Get documents for this specific twin version
                documents = Document.objects.filter(
                    twin_version=twin_version, status="completed"
                ).select_related("twin_version", "uploaded_by")
            else:
                # Get all documents from user's accessible twin versions
                accessible_twin_versions = TwinVersion.objects.filter(
                    Q(user=request.user)
                    | Q(is_shared=True)  # Own twin versions
                    | Q(  # Public twin versions
                        shares__shared_with=request.user
                    )  # Explicitly shared
                )

                documents = Document.objects.filter(
                    twin_version__in=accessible_twin_versions, status="completed"
                ).select_related("twin_version", "uploaded_by")

            # Apply filters
            search_query = request.GET.get("search")
            file_type = request.GET.get("file_type")

            if search_query:
                documents = documents.filter(
                    Q(title__icontains=search_query)
                    | Q(description__icontains=search_query)
                )

            if file_type:
                documents = documents.filter(file_type=file_type)

            # Paginate
            page = request.GET.get("page", 1)
            page_size = min(
                int(request.GET.get("page_size", 10)), 100
            )  # Max 100 per page
            paginator = Paginator(documents, page_size)
            page_obj = paginator.get_page(page)

            # Serialize documents
            document_data = []
            for doc in page_obj:
                is_owner = doc.user == request.user
                document_data.append(
                    {
                        "id": str(doc.id),
                        "title": doc.title,
                        "description": doc.description,
                        "file_type": doc.file_type,
                        "file_size": doc.file_size,
                        "uploaded_at": doc.uploaded_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "twin_version_id": str(doc.twin_version.id),
                        "twin_version_name": doc.twin_version.name,
                        "page_count": doc.page_count,
                        "word_count": doc.word_count,
                        "is_enabled": doc.is_enabled,
                        "is_owner": is_owner,
                        "owner": (
                            "you"
                            if is_owner
                            else (doc.user.username if doc.user else "Unknown")
                        ),
                    }
                )

            return JsonResponse(
                {
                    "documents": document_data,
                    "pagination": {
                        "current_page": page_obj.number,
                        "total_pages": paginator.num_pages,
                        "total_items": paginator.count,
                        "has_next": page_obj.has_next(),
                        "has_previous": page_obj.has_previous(),
                    },
                }
            )

        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    elif request.method == "POST":
        # Handle document upload
        try:
            logger.info(f"Document upload request from user: {request.user.username}")

            twin_version_id = request.POST.get("twin_version_id")
            if not twin_version_id:
                return JsonResponse(
                    {"error": "twin_version_id is required"}, status=400
                )

            logger.info(f"Uploading to twin version: {twin_version_id}")

            # Validate user has permission to upload to this twin version (must be owner)
            twin_version = validate_twin_version_access(
                request.user, twin_version_id, require_owner=True
            )

            if "file" not in request.FILES:
                return JsonResponse({"error": "No file provided"}, status=400)

            uploaded_file = request.FILES["file"]
            title = request.POST.get("title", uploaded_file.name)
            description = request.POST.get("description", "")

            logger.info(f"Creating document: {title}")

            # Create document with proper user association
            try:
                document = Document.objects.create(
                    twin_version=twin_version,
                    title=title,
                    description=description,
                    file=uploaded_file,
                    file_size=uploaded_file.size,
                    uploaded_by=request.user,  # Always associate with current user
                    status="pending",
                )
                logger.info(f"Document created successfully: {document.id}")

                # Trigger automatic document processing for twin version integration
                def process_document_async():
                    try:
                        logger.info(
                            f"Starting background processing for document: {document.title}"
                        )

                        # Initialize document processor and embedding generator
                        doc_processor = DocumentProcessor()
                        embedding_generator = EmbeddingGenerator()

                        # Process document (extract text, create chunks)
                        if doc_processor.process_document(document):
                            logger.info(
                                f"Document processing completed for: {document.title}"
                            )

                            # Generate embeddings for the chunks
                            if embedding_generator.generate_embeddings_for_document(
                                document
                            ):
                                logger.info(
                                    f"Embeddings generated successfully for: {document.title}"
                                )
                            else:
                                logger.warning(
                                    f"Embedding generation failed for: {document.title}"
                                )
                        else:
                            logger.warning(
                                f"Document processing failed for: {document.title}"
                            )

                    except Exception as processing_error:
                        logger.error(
                            f"Error in background processing for document {document.title}: {str(processing_error)}"
                        )

                # Start background processing
                processing_thread = Thread(target=process_document_async)
                processing_thread.daemon = True
                processing_thread.start()
                logger.info(
                    f"Background processing started for document: {document.title}"
                )

            except Exception as create_error:
                logger.error(f"Error creating document: {str(create_error)}")
                return JsonResponse(
                    {"error": f"Failed to create document: {str(create_error)}"},
                    status=500,
                )

            try:
                logger.info(
                    f"User {request.user.username} uploaded document '{title}' to twin version '{twin_version.name}'"
                )

                response_data = {
                    "id": str(document.id),
                    "title": document.title,
                    "status": document.status,
                    "twin_version_id": str(twin_version.id),
                    "message": "Document uploaded successfully. Processing and embedding generation started.",
                }

                return JsonResponse(response_data, status=201)
            except Exception as response_error:
                logger.error(f"Error preparing response: {str(response_error)}")
                return JsonResponse(
                    {
                        "error": f"Document created but response error: {str(response_error)}"
                    },
                    status=500,
                )

        except Http404 as e:
            return JsonResponse({"error": str(e)}, status=404)
        except Exception as e:
            logger.error(f"Error uploading document: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)


class DocumentUploadView(View):
    """API endpoint for uploading documents"""

    @method_decorator(login_required)
    def post(self, request):
        """Upload a document to a twin version"""
        try:
            # Get twin version
            twin_version_id = request.POST.get("twin_version_id")
            twin_version = get_object_or_404(TwinVersion, id=twin_version_id)

            # Verify ownership of twin version
            if twin_version.user != request.user:
                return JsonResponse(
                    {
                        "error": "You do not have permission to upload to this twin version"
                    },
                    status=403,
                )

            # Handle file upload
            if "file" not in request.FILES:
                return JsonResponse({"error": "No file provided"}, status=400)

            uploaded_file = request.FILES["file"]

            # Create document record
            document = Document.objects.create(
                twin_version=twin_version,
                user=request.user,
                title=request.POST.get("title", uploaded_file.name),
                description=request.POST.get("description", ""),
                file=uploaded_file,
                file_size=uploaded_file.size,
                file_type=os.path.splitext(uploaded_file.name)[1][1:].lower(),
                status="pending",
                is_shared=request.POST.get("is_shared", "false").lower() == "true",
            )

            # Start document processing in background
            processor = DocumentProcessor(document)
            thread = Thread(target=processor.process)
            thread.daemon = True
            thread.start()

            # Update user profile stats
            profile = request.user.profile
            profile.total_documents_uploaded += 1
            profile.save(update_fields=["total_documents_uploaded"])

            # Record usage
            record_document_usage(
                user=request.user, document=document, operation="upload"
            )

            return JsonResponse(
                {
                    "id": str(document.id),
                    "title": document.title,
                    "status": document.status,
                },
                status=201,
            )

        except Http404:
            return JsonResponse({"error": "Twin version not found"}, status=404)
        except Exception as e:
            logger.error(f"Error uploading document: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)


class DocumentDetailView(View):
    """API endpoint for retrieving, updating, and deleting documents"""

    @method_decorator(login_required)
    @method_decorator(check_document_access)
    def get(self, request, document_id):
        """Get details for a specific document"""
        try:
            document = get_object_or_404(Document, id=document_id)

            # Check if user can manage (only owner can manage)
            can_manage = document.uploaded_by == request.user

            # Record usage for analytics
            if not can_manage:
                record_document_usage(
                    user=request.user, document=document, operation="view_details"
                )

            # Get shared users if owner
            shared_users = []
            if can_manage:
                shared_users = list(
                    DocumentShare.objects.filter(document=document).values_list(
                        "shared_with__username", flat=True
                    )
                )

            return JsonResponse(
                {
                    "id": str(document.id),
                    "title": document.title,
                    "description": document.description,
                    "file_type": document.file_type,
                    "file_size": document.file_size,
                    "status": document.status,
                    "uploaded_at": document.uploaded_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "processed_at": (
                        document.processed_at.strftime("%Y-%m-%d %H:%M:%S")
                        if document.processed_at
                        else None
                    ),
                    "twin_version_id": str(document.twin_version.id),
                    "twin_version_name": document.twin_version.name,
                    "is_shared": document.is_shared,
                    "page_count": document.page_count,
                    "word_count": document.word_count,
                    "can_manage": can_manage,
                    "owner": (
                        document.uploaded_by.username
                        if document.uploaded_by
                        else "Unknown"
                    ),
                    "shared_with": shared_users,
                    "download_url": document.file.url if document.file else None,
                }
            )

        except Http404:
            return JsonResponse({"error": "Document not found"}, status=404)
        except Exception as e:
            logger.error(f"Error retrieving document: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    @method_decorator(login_required)
    @method_decorator(check_document_access)
    def put(self, request, document_id):
        """Update a document - only owner can update"""
        try:
            document = get_object_or_404(Document, id=document_id)

            # Only owner can update
            if document.uploaded_by != request.user:
                return JsonResponse(
                    {"error": "You do not have permission to update this document"},
                    status=403,
                )

            data = json.loads(request.body)

            # Update fields
            document.title = data.get("title", document.title)
            document.description = data.get("description", document.description)
            document.is_shared = data.get("is_shared", document.is_shared)
            document.is_enabled = data.get("is_enabled", document.is_enabled)
            document.save()

            # Handle sharing updates
            if "share_with" in data:
                from django.contrib.auth.models import User

                # Clear existing shares
                DocumentShare.objects.filter(document=document).delete()

                # Add new shares
                for username in data["share_with"]:
                    try:
                        user = User.objects.get(username=username)
                        DocumentShare.objects.create(
                            document=document, shared_with=user
                        )
                    except User.DoesNotExist:
                        logger.warning(
                            f"Cannot share with non-existent user: {username}"
                        )

            return JsonResponse(
                {
                    "id": str(document.id),
                    "title": document.title,
                    "description": document.description,
                    "is_shared": document.is_shared,
                    "is_enabled": document.is_enabled,
                }
            )

        except Http404:
            return JsonResponse({"error": "Document not found"}, status=404)
        except Exception as e:
            logger.error(f"Error updating document: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    @method_decorator(login_required)
    def delete(self, request, document_id):
        """Delete a document - only owner can delete"""
        try:
            document = get_object_or_404(Document, id=document_id)

            # Only owner can delete
            if document.uploaded_by != request.user:
                return JsonResponse(
                    {"error": "You do not have permission to delete this document"},
                    status=403,
                )

            # Mark as disabled instead of deleting
            document.is_enabled = False
            document.save()

            return JsonResponse({"message": "Document deleted successfully"})

        except Http404:
            return JsonResponse({"error": "Document not found"}, status=404)
        except Exception as e:
            logger.error(f"Error deleting document: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)


class DocumentSearchView(View):
    """API endpoint for searching document content"""

    @method_decorator(login_required)
    def post(self, request):
        """Search document content using vector embeddings"""
        try:
            data = json.loads(request.body)
            query = data.get("query")
            twin_version_id = data.get("twin_version_id")

            if not query:
                return JsonResponse({"error": "No search query provided"}, status=400)

            # Initialize semantic search
            searcher = SemanticSearch()

            # Prepare document filter based on user access
            document_filter = Q(document__is_enabled=True)

            # Filter by user's own documents or shared documents
            document_filter &= (
                Q(document__uploaded_by=request.user)
                | Q(document__is_shared=True)  # User's own documents
                | Q(  # Publicly shared documents
                    document__shares__shared_with=request.user
                )
                | Q(  # Explicitly shared documents
                    document__twin_version__is_shared=True
                )
                | Q(  # Documents in shared twin versions
                    document__twin_version__shares__shared_with=request.user
                )  # Documents in specifically shared twin versions
            )

            # Filter by twin version if provided
            if twin_version_id:
                twin_version = get_object_or_404(TwinVersion, id=twin_version_id)

                # Check if user has access to this twin version
                if not (
                    twin_version.user == request.user
                    or twin_version.is_shared
                    or twin_version.shares.filter(shared_with=request.user).exists()
                ):
                    return JsonResponse(
                        {"error": "Access denied to this twin version"}, status=403
                    )

                document_filter &= Q(document__twin_version=twin_version)

            # Perform search
            results = searcher.search(
                query=query,
                document_filter=document_filter,
                limit=data.get("limit", 10),
                threshold=data.get("threshold", 0.5),
            )

            # Process results
            processed_results = []
            for result in results:
                doc = result["document"]
                is_owner = doc.user == request.user

                processed_results.append(
                    {
                        "document_id": str(doc.id),
                        "document_title": doc.title,
                        "twin_version_id": str(doc.twin_version.id),
                        "twin_version_name": doc.twin_version.name,
                        "content": result["content"],
                        "score": result["score"],
                        "page": result.get("page"),
                        "chunk_id": str(result["chunk_id"]),
                        "is_owner": is_owner,
                        "owner": (
                            "you"
                            if is_owner
                            else (doc.user.username if doc.user else "Unknown")
                        ),
                    }
                )

                # Record usage for non-owners
                if not is_owner:
                    record_document_usage(
                        user=request.user,
                        document=doc,
                        operation="search",
                        tokens_used=10,  # Approximate embedding tokens
                    )

            # Record token usage for embedding the query
            record_token_usage(
                user=request.user,
                tokens_used=len(query.split()) + 5,  # Approximate embedding tokens
                resource_type="search",
                operation="embedding",
            )

            return JsonResponse(
                {
                    "results": processed_results,
                    "query": query,
                    "count": len(processed_results),
                }
            )

        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)


class DocumentShareView(View):
    """View for sharing documents with other users"""

    @method_decorator(login_required)
    def post(self, request, document_id):
        """Share a document with a user"""
        try:
            document = get_object_or_404(Document, id=document_id)

            # Check if user owns the document
            if document.uploaded_by != request.user:
                return JsonResponse(
                    {"error": "You can only share documents you own"}, status=403
                )

            # Get data
            data = json.loads(request.body)
            username = data.get("username")
            is_public = data.get("public", False)

            # Set public sharing flag
            if is_public is not None:
                document.is_shared = bool(is_public)
                document.save(update_fields=["is_shared"])

            # Share with specific user if provided
            if username:
                try:
                    user_to_share_with = User.objects.get(username=username)

                    # Don't share with yourself
                    if user_to_share_with == request.user:
                        return JsonResponse(
                            {"error": "Cannot share with yourself"}, status=400
                        )

                    # Create share (or get existing)
                    share, created = DocumentShare.objects.get_or_create(
                        document=document, shared_with=user_to_share_with
                    )

                    return JsonResponse(
                        {
                            "success": True,
                            "message": f"Document shared with {username}",
                            "created": created,
                        }
                    )

                except User.DoesNotExist:
                    return JsonResponse(
                        {"error": f"User {username} not found"}, status=404
                    )

            return JsonResponse(
                {
                    "success": True,
                    "message": "Document sharing updated",
                    "is_public": document.is_shared,
                }
            )

        except Exception as e:
            logger.error(f"Error sharing document: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    @method_decorator(login_required)
    def delete(self, request, document_id):
        """Remove document sharing for a user"""
        try:
            document = get_object_or_404(Document, id=document_id)

            # Check if user owns the document
            if document.uploaded_by != request.user:
                return JsonResponse(
                    {"error": "You can only manage shares for documents you own"},
                    status=403,
                )

            # Get data
            data = json.loads(request.body)
            username = data.get("username")

            if username:
                try:
                    user_to_unshare = User.objects.get(username=username)

                    # Delete share
                    result = DocumentShare.objects.filter(
                        document=document, shared_with=user_to_unshare
                    ).delete()

                    if result[0] > 0:
                        return JsonResponse(
                            {
                                "success": True,
                                "message": f"Document sharing removed for {username}",
                            }
                        )
                    else:
                        return JsonResponse(
                            {
                                "success": False,
                                "message": f"Document was not shared with {username}",
                            },
                            status=400,
                        )

                except User.DoesNotExist:
                    return JsonResponse(
                        {"error": f"User {username} not found"}, status=404
                    )

            # If no username, remove all shares
            document.is_shared = False
            document.save(update_fields=["is_shared"])
            document.shares.all().delete()

            return JsonResponse(
                {"success": True, "message": "All document sharing removed"}
            )

        except Exception as e:
            logger.error(f"Error removing document sharing: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    @method_decorator(login_required)
    def get(self, request, document_id):
        """Get document sharing information"""
        try:
            document = get_object_or_404(Document, id=document_id)

            # Check if user can access the document
            if not (
                document.uploaded_by == request.user
                or document.is_shared
                or document.shares.filter(shared_with=request.user).exists()
            ):
                return JsonResponse({"error": "Access denied"}, status=403)

            # Get share data
            shares = []
            if document.uploaded_by == request.user:
                # If user is owner, get all shares
                for share in document.shares.all():
                    shares.append(
                        {
                            "username": share.shared_with.username,
                            "email": share.shared_with.email,
                            "shared_at": share.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

            return JsonResponse(
                {
                    "id": str(document.id),
                    "title": document.title,
                    "is_owner": document.uploaded_by == request.user,
                    "is_public": document.is_shared,
                    "owner": (
                        document.uploaded_by.username
                        if document.uploaded_by
                        else "Unknown"
                    ),
                    "shares": shares,
                }
            )

        except Exception as e:
            logger.error(f"Error getting document sharing info: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)


class TwinVersionShareView(View):
    """View for sharing twin versions with other users"""

    @method_decorator(login_required)
    def post(self, request, twin_version_id):
        """Share a twin version with a user"""
        try:
            twin_version = get_object_or_404(TwinVersion, id=twin_version_id)

            # Check if user owns the twin version
            if twin_version.user != request.user:
                return JsonResponse(
                    {"error": "You can only share twin versions you own"}, status=403
                )

            # Get data
            data = json.loads(request.body)
            username = data.get("username")
            is_public = data.get("public", False)
            share_documents = data.get("share_documents", False)

            # Set public sharing flag
            if is_public is not None:
                twin_version.is_shared = bool(is_public)
                twin_version.save(update_fields=["is_shared"])

            # Share with specific user if provided
            if username:
                try:
                    user_to_share_with = User.objects.get(username=username)

                    # Don't share with yourself
                    if user_to_share_with == request.user:
                        return JsonResponse(
                            {"error": "Cannot share with yourself"}, status=400
                        )

                    # Create twin version share (or get existing)
                    share, created = TwinVersionShare.objects.get_or_create(
                        twin_version=twin_version, shared_with=user_to_share_with
                    )

                    # Also share all documents if requested
                    if share_documents:
                        for document in twin_version.documents.filter(
                            uploaded_by=request.user
                        ):
                            DocumentShare.objects.get_or_create(
                                document=document, shared_with=user_to_share_with
                            )

                    return JsonResponse(
                        {
                            "success": True,
                            "message": f"Twin version shared with {username}",
                            "created": created,
                        }
                    )

                except User.DoesNotExist:
                    return JsonResponse(
                        {"error": f"User {username} not found"}, status=404
                    )

            return JsonResponse(
                {
                    "success": True,
                    "message": "Twin version sharing updated",
                    "is_public": twin_version.is_shared,
                }
            )

        except Exception as e:
            logger.error(f"Error sharing twin version: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    @method_decorator(login_required)
    def delete(self, request, twin_version_id):
        """Remove twin version sharing for a user"""
        try:
            twin_version = get_object_or_404(TwinVersion, id=twin_version_id)

            # Check if user owns the twin version
            if twin_version.user != request.user:
                return JsonResponse(
                    {"error": "You can only manage shares for twin versions you own"},
                    status=403,
                )

            # Get data
            data = json.loads(request.body)
            username = data.get("username")
            remove_document_shares = data.get("remove_document_shares", False)

            if username:
                try:
                    user_to_unshare = User.objects.get(username=username)

                    # Delete twin version share
                    result = TwinVersionShare.objects.filter(
                        twin_version=twin_version, shared_with=user_to_unshare
                    ).delete()

                    # Also remove document shares if requested
                    if remove_document_shares:
                        for document in twin_version.documents.filter(
                            uploaded_by=request.user
                        ):
                            DocumentShare.objects.filter(
                                document=document, shared_with=user_to_unshare
                            ).delete()

                    if result[0] > 0:
                        return JsonResponse(
                            {
                                "success": True,
                                "message": f"Twin version sharing removed for {username}",
                            }
                        )
                    else:
                        return JsonResponse(
                            {
                                "success": False,
                                "message": f"Twin version was not shared with {username}",
                            },
                            status=400,
                        )

                except User.DoesNotExist:
                    return JsonResponse(
                        {"error": f"User {username} not found"}, status=404
                    )

            # If no username, remove all shares
            twin_version.is_shared = False
            twin_version.save(update_fields=["is_shared"])
            twin_version.shares.all().delete()

            return JsonResponse(
                {"success": True, "message": "All twin version sharing removed"}
            )

        except Exception as e:
            logger.error(f"Error removing twin version sharing: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    @method_decorator(login_required)
    def get(self, request, twin_version_id):
        """Get twin version sharing information"""
        try:
            twin_version = get_object_or_404(TwinVersion, id=twin_version_id)

            # Check if user can access the twin version
            if not (
                twin_version.user == request.user
                or twin_version.is_shared
                or twin_version.shares.filter(shared_with=request.user).exists()
            ):
                return JsonResponse({"error": "Access denied"}, status=403)

            # Get share data
            shares = []
            if twin_version.user == request.user:
                # If user is owner, get all shares
                for share in twin_version.shares.all():
                    shares.append(
                        {
                            "username": share.shared_with.username,
                            "email": share.shared_with.email,
                            "shared_at": share.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

            return JsonResponse(
                {
                    "id": str(twin_version.id),
                    "name": twin_version.name,
                    "is_owner": twin_version.user == request.user,
                    "is_public": twin_version.is_shared,
                    "owner": (
                        twin_version.user.username if twin_version.user else "Unknown"
                    ),
                    "shares": shares,
                }
            )

        except Exception as e:
            logger.error(f"Error getting twin version sharing info: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET", "PUT", "DELETE"])
def twin_version_detail_view(request, version_id):
    """API endpoint for retrieving, updating, and deleting a specific twin version"""

    # Require authentication
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        # Validate user has access to this twin version
        twin_version = validate_twin_version_access(
            request.user,
            version_id,
            require_owner=(request.method in ["PUT", "DELETE"]),
        )

    except Http404 as e:
        return JsonResponse({"error": str(e)}, status=404)
    except Exception as e:
        return JsonResponse({"error": "Invalid twin version ID"}, status=400)

    if request.method == "GET":
        """Get twin version details"""
        try:
            return JsonResponse(
                {
                    "id": str(twin_version.id),
                    "name": twin_version.name,
                    "description": twin_version.description,
                    "version": twin_version.version,
                    "created_at": twin_version.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": twin_version.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_active": twin_version.is_active,
                    "is_shared": twin_version.is_shared,
                    "owner": (
                        twin_version.user.username if twin_version.user else "Unknown"
                    ),
                    "document_count": twin_version.documents.count(),
                }
            )
        except Exception as e:
            logger.error(f"Error retrieving twin version: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    elif request.method == "PUT":
        """Update twin version"""
        try:
            data = json.loads(request.body)

            # Update fields
            if "name" in data:
                twin_version.name = data["name"]
            if "description" in data:
                twin_version.description = data["description"]
            if "version" in data:
                twin_version.version = data["version"]
            if "is_shared" in data:
                twin_version.is_shared = data["is_shared"]

            twin_version.save()

            logger.info(
                f"User {request.user.username} updated twin version '{twin_version.name}'"
            )

            return JsonResponse(
                {
                    "id": str(twin_version.id),
                    "name": twin_version.name,
                    "description": twin_version.description,
                    "version": twin_version.version,
                    "message": "Twin version updated successfully",
                }
            )

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            logger.error(f"Error updating twin version: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

    elif request.method == "DELETE":
        """Delete twin version"""
        try:
            twin_version_name = twin_version.name
            document_count = twin_version.documents.count()

            # Log the deletion attempt
            logger.info(
                f"User {request.user.username} attempting to delete twin version '{twin_version_name}' with {document_count} documents"
            )

            # Delete the twin version (CASCADE will handle related documents)
            twin_version.delete()

            logger.info(
                f"User {request.user.username} successfully deleted twin version '{twin_version_name}'"
            )

            return JsonResponse(
                {
                    "message": f'Twin version "{twin_version_name}" deleted successfully',
                    "deleted_documents": document_count,
                },
                status=204,
            )

        except Exception as e:
            logger.error(f"Error deleting twin version: {str(e)}")
            return JsonResponse({"error": str(e)}, status=500)

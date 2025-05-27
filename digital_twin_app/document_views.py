"""
Document Management Views for Digital Twin Application
"""
import logging
import json
import uuid
from typing import Dict, Any
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.core.paginator import Paginator
from django.db.models import Q, Count
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from fastapi import HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from threading import Thread

from .models import TwinVersion, Document, DocumentChunk, DocumentEmbedding
from .document_utils import DocumentProcessor, EmbeddingGenerator, SemanticSearch
from .views import fastapi_app

logger = logging.getLogger(__name__)

# Pydantic models for FastAPI
class TwinVersionCreate(BaseModel):
    name: str
    description: str = ""
    version: str = "1.0"

class TwinVersionResponse(BaseModel):
    id: str
    name: str
    description: str
    version: str
    is_active: bool
    created_at: str
    document_count: int = 0

class DocumentResponse(BaseModel):
    id: str
    title: str
    description: str
    file_type: str
    file_size: int
    status: str
    is_enabled: bool
    uploaded_at: str
    page_count: int = None
    word_count: int = None

class SearchRequest(BaseModel):
    query: str
    twin_version_id: str
    top_k: int = 5

class SearchResult(BaseModel):
    document_title: str
    content: str
    similarity: float
    page_number: int = None


# Django Views
class DMSView(View):
    """Main Document Management System view."""
    
    def get(self, request):
        """Render the DMS interface."""
        twin_versions = TwinVersion.objects.filter(is_active=True).annotate(
            document_count=Count('documents')
        )
        return render(request, 'dms.html', {'twin_versions': twin_versions})


class DocumentListView(View):
    """View for listing documents with filtering."""
    
    def get(self, request):
        """Get paginated list of documents."""
        twin_version_id = request.GET.get('twin_version_id')
        search_query = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        
        # Build query
        documents = Document.objects.all()
        
        if twin_version_id:
            documents = documents.filter(twin_version_id=twin_version_id)
        
        if search_query:
            documents = documents.filter(
                Q(title__icontains=search_query) | 
                Q(description__icontains=search_query)
            )
        
        if status_filter:
            documents = documents.filter(status=status_filter)
        
        # Paginate
        paginator = Paginator(documents.order_by('-uploaded_at'), per_page)
        page_obj = paginator.get_page(page)
        
        # Serialize data
        document_data = []
        for doc in page_obj:
            document_data.append({
                'id': str(doc.id),
                'title': doc.title,
                'description': doc.description,
                'file_type': doc.file_type,
                'file_size': doc.file_size,
                'status': doc.status,
                'is_enabled': doc.is_enabled,
                'uploaded_at': doc.uploaded_at.isoformat(),
                'page_count': doc.page_count,
                'word_count': doc.word_count,
                'twin_version': {
                    'id': str(doc.twin_version.id),
                    'name': doc.twin_version.name,
                    'version': doc.twin_version.version
                }
            })
        
        return JsonResponse({
            'documents': document_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            }
        })


@method_decorator(csrf_exempt, name='dispatch')
class DocumentUploadView(View):
    """View for handling document uploads."""
    
    def post(self, request):
        """Handle document upload."""
        try:
            twin_version_id = request.POST.get('twin_version_id')
            title = request.POST.get('title')
            description = request.POST.get('description', '')
            uploaded_file = request.FILES.get('file')
            
            if not all([twin_version_id, title, uploaded_file]):
                return JsonResponse({
                    'error': 'Missing required fields: twin_version_id, title, file'
                }, status=400)
            
            # Get twin version
            try:
                twin_version = TwinVersion.objects.get(id=twin_version_id)
            except TwinVersion.DoesNotExist:
                return JsonResponse({'error': 'Invalid twin version'}, status=400)
            
            # Create document processor
            processor = DocumentProcessor()
            file_type = processor.determine_file_type(uploaded_file.name)
            
            # Create document record
            document = Document.objects.create(
                twin_version=twin_version,
                title=title,
                description=description,
                file=uploaded_file,
                file_type=file_type,
                file_size=uploaded_file.size,
                uploaded_by=request.user if request.user.is_authenticated else None
            )
            
            # Process document in background
            def process_document_async():
                processor = DocumentProcessor()
                if processor.process_document(document):
                    # Generate embeddings
                    embedding_generator = EmbeddingGenerator()
                    embedding_generator.generate_embeddings_for_document(document)
            
            thread = Thread(target=process_document_async)
            thread.daemon = True
            thread.start()
            
            return JsonResponse({
                'message': 'Document uploaded successfully',
                'document_id': str(document.id),
                'status': 'processing'
            })
            
        except Exception as e:
            logger.error(f"Error uploading document: {e}")
            return JsonResponse({'error': 'Upload failed'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TwinVersionListView(View):
    """View for twin version management."""
    
    def get(self, request):
        """Get all twin versions."""
        try:
            twin_versions = TwinVersion.objects.filter(is_active=True).annotate(
                document_count=Count('documents')
            )
            
            return JsonResponse({
                'twin_versions': [
                    {
                        'id': str(version.id),
                        'name': version.name,
                        'description': version.description,
                        'version': version.version,
                        'is_active': version.is_active,
                        'created_at': version.created_at.isoformat(),
                        'document_count': version.document_count
                    }
                    for version in twin_versions
                ]
            })
            
        except Exception as e:
            logger.error(f"Error getting twin versions: {e}")
            return JsonResponse({'error': 'Failed to get twin versions'}, status=500)
    
    def post(self, request):
        """Create a new twin version."""
        try:
            data = json.loads(request.body)
            
            twin_version = TwinVersion.objects.create(
                name=data['name'],
                description=data.get('description', ''),
                version=data.get('version', '1.0')
            )
            
            return JsonResponse({
                'id': str(twin_version.id),
                'name': twin_version.name,
                'description': twin_version.description,
                'version': twin_version.version,
                'is_active': twin_version.is_active,
                'created_at': twin_version.created_at.isoformat(),
                'document_count': 0
            }, status=201)
            
        except Exception as e:
            logger.error(f"Error creating twin version: {e}")
            return JsonResponse({'error': 'Failed to create twin version'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class TwinVersionDetailView(View):
    """View for individual twin version management."""
    
    def get(self, request, version_id):
        """Get twin version details."""
        try:
            twin_version = get_object_or_404(TwinVersion, id=version_id)
            document_count = Document.objects.filter(twin_version=twin_version).count()
            
            return JsonResponse({
                'id': str(twin_version.id),
                'name': twin_version.name,
                'description': twin_version.description,
                'version': twin_version.version,
                'is_active': twin_version.is_active,
                'created_at': twin_version.created_at.isoformat(),
                'updated_at': twin_version.updated_at.isoformat(),
                'document_count': document_count
            })
            
        except Exception as e:
            logger.error(f"Error getting twin version details: {e}")
            return JsonResponse({'error': 'Failed to get twin version details'}, status=500)
    
    def patch(self, request, version_id):
        """Update twin version."""
        try:
            twin_version = get_object_or_404(TwinVersion, id=version_id)
            data = json.loads(request.body)
            
            if 'name' in data:
                twin_version.name = data['name']
            if 'description' in data:
                twin_version.description = data['description']
            if 'version' in data:
                twin_version.version = data['version']
            if 'is_active' in data:
                twin_version.is_active = data['is_active']
            
            twin_version.save()
            
            return JsonResponse({'message': 'Twin version updated successfully'})
            
        except Exception as e:
            logger.error(f"Error updating twin version: {e}")
            return JsonResponse({'error': 'Update failed'}, status=500)
    
    def delete(self, request, version_id):
        """Delete twin version."""
        try:
            twin_version = get_object_or_404(TwinVersion, id=version_id)
            
            # Check if there are documents
            document_count = Document.objects.filter(twin_version=twin_version).count()
            if document_count > 0:
                return JsonResponse({
                    'error': f'Cannot delete twin version with {document_count} documents'
                }, status=400)
            
            twin_version.delete()
            
            return JsonResponse({'message': 'Twin version deleted successfully'})
            
        except Exception as e:
            logger.error(f"Error deleting twin version: {e}")
            return JsonResponse({'error': 'Delete failed'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class DocumentSearchView(View):
    """View for semantic document search."""
    
    async def post(self, request):
        """Search documents using semantic similarity."""
        try:
            data = json.loads(request.body)
            query = data['query']
            twin_version_id = data['twin_version_id']
            top_k = data.get('top_k', 5)
            
            semantic_search = SemanticSearch()
            results = await semantic_search.search_documents(
                query=query,
                twin_version_id=twin_version_id,
                top_k=top_k
            )
            
            return JsonResponse({
                'results': [
                    {
                        'document_title': result['document'].title,
                        'content': result['content'][:500] + "..." if len(result['content']) > 500 else result['content'],
                        'similarity': result['similarity'],
                        'page_number': result['chunk'].page_number,
                        'document_id': str(result['document'].id),
                        'chunk_id': str(result['chunk'].id)
                    }
                    for result in results
                ]
            })
            
        except Exception as e:
            logger.error(f"Error in document search: {e}")
            return JsonResponse({'error': 'Search failed'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class DocumentDetailView(View):
    """View for document details and management."""
    
    def get(self, request, document_id):
        """Get document details."""
        try:
            document = get_object_or_404(Document, id=document_id)
            
            # Get chunks count
            chunks_count = DocumentChunk.objects.filter(document=document).count()
            embeddings_count = DocumentEmbedding.objects.filter(
                chunk__document=document
            ).count()
            
            return JsonResponse({
                'id': str(document.id),
                'title': document.title,
                'description': document.description,
                'file_type': document.file_type,
                'file_size': document.file_size,
                'status': document.status,
                'is_enabled': document.is_enabled,
                'uploaded_at': document.uploaded_at.isoformat(),
                'processed_at': document.processed_at.isoformat() if document.processed_at else None,
                'page_count': document.page_count,
                'word_count': document.word_count,
                'chunks_count': chunks_count,
                'embeddings_count': embeddings_count,
                'processing_error': document.processing_error,
                'twin_version': {
                    'id': str(document.twin_version.id),
                    'name': document.twin_version.name,
                    'version': document.twin_version.version
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting document details: {e}")
            return JsonResponse({'error': 'Failed to get document details'}, status=500)
    
    def patch(self, request, document_id):
        """Update document settings."""
        try:
            document = get_object_or_404(Document, id=document_id)
            data = json.loads(request.body)
            
            # Update allowed fields
            if 'title' in data:
                document.title = data['title']
            if 'description' in data:
                document.description = data['description']
            if 'is_enabled' in data:
                document.is_enabled = data['is_enabled']
            
            document.save()
            
            return JsonResponse({'message': 'Document updated successfully'})
            
        except Exception as e:
            logger.error(f"Error updating document: {e}")
            return JsonResponse({'error': 'Update failed'}, status=500)
    
    def delete(self, request, document_id):
        """Delete document and its data."""
        try:
            document = get_object_or_404(Document, id=document_id)
            
            # Delete file
            if document.file:
                document.file.delete()
            
            # Delete document (cascades to chunks and embeddings)
            document.delete()
            
            return JsonResponse({'message': 'Document deleted successfully'})
            
        except Exception as e:
            logger.error(f"Error deleting document: {e}")
            return JsonResponse({'error': 'Delete failed'}, status=500)


# FastAPI Endpoints
@fastapi_app.get("/api/twin-versions", response_model=list[TwinVersionResponse])
async def get_twin_versions():
    """Get all twin versions."""
    try:
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def get_versions():
            versions = TwinVersion.objects.filter(is_active=True).annotate(
                document_count=Count('documents')
            )
            return list(versions)
        
        versions = await get_versions()
        
        return [
            TwinVersionResponse(
                id=str(version.id),
                name=version.name,
                description=version.description,
                version=version.version,
                is_active=version.is_active,
                created_at=version.created_at.isoformat(),
                document_count=version.document_count
            )
            for version in versions
        ]
    except Exception as e:
        logger.error(f"Error getting twin versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.post("/api/twin-versions", response_model=TwinVersionResponse)
async def create_twin_version(version_data: TwinVersionCreate):
    """Create a new twin version."""
    try:
        from asgiref.sync import sync_to_async
        
        @sync_to_async
        def create_version():
            return TwinVersion.objects.create(
                name=version_data.name,
                description=version_data.description,
                version=version_data.version
            )
        
        twin_version = await create_version()
        
        return TwinVersionResponse(
            id=str(twin_version.id),
            name=twin_version.name,
            description=twin_version.description,
            version=twin_version.version,
            is_active=twin_version.is_active,
            created_at=twin_version.created_at.isoformat(),
            document_count=0
        )
    except Exception as e:
        logger.error(f"Error creating twin version: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    twin_version_id: str = Form(...),
    title: str = Form(...),
    description: str = Form("")
):
    """Upload a document via FastAPI."""
    try:
        # Validate twin version
        try:
            twin_version = TwinVersion.objects.get(id=twin_version_id)
        except TwinVersion.DoesNotExist:
            raise HTTPException(status_code=400, detail="Invalid twin version")
        
        # Validate file type
        processor = DocumentProcessor()
        file_type = processor.determine_file_type(file.filename)
        
        if file_type == 'other':
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        # Save file
        from django.core.files.uploadedfile import SimpleUploadedFile
        django_file = SimpleUploadedFile(
            file.filename,
            await file.read(),
            content_type=file.content_type
        )
        
        # Create document
        document = Document.objects.create(
            twin_version=twin_version,
            title=title,
            description=description,
            file=django_file,
            file_type=file_type,
            file_size=django_file.size
        )
        
        # Process document in background
        def process_document_async():
            processor = DocumentProcessor()
            if processor.process_document(document):
                embedding_generator = EmbeddingGenerator()
                embedding_generator.generate_embeddings_for_document(document)
        
        thread = Thread(target=process_document_async)
        thread.daemon = True
        thread.start()
        
        return JSONResponse({
            "message": "Document uploaded successfully",
            "document_id": str(document.id),
            "status": "processing"
        })
        
    except Exception as e:
        logger.error(f"Error uploading document via FastAPI: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.post("/api/documents/search", response_model=list[SearchResult])
async def search_documents(search_request: SearchRequest):
    """Search documents using semantic similarity."""
    try:
        semantic_search = SemanticSearch()
        results = await semantic_search.search_documents(
            query=search_request.query,
            twin_version_id=search_request.twin_version_id,
            top_k=search_request.top_k
        )
        
        return [
            SearchResult(
                document_title=result['document'].title,
                content=result['content'][:500] + "..." if len(result['content']) > 500 else result['content'],
                similarity=result['similarity'],
                page_number=result['chunk'].page_number
            )
            for result in results
        ]
        
    except Exception as e:
        logger.error(f"Error in document search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/api/documents/{document_id}/chunks")
async def get_document_chunks(document_id: str, page: int = 1, per_page: int = 10):
    """Get chunks for a document."""
    try:
        document = Document.objects.get(id=document_id)
        chunks = DocumentChunk.objects.filter(document=document).order_by('chunk_index')
        
        # Paginate
        from django.core.paginator import Paginator
        paginator = Paginator(chunks, per_page)
        page_obj = paginator.get_page(page)
        
        return {
            "chunks": [
                {
                    "id": str(chunk.id),
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number,
                    "word_count": chunk.word_count
                }
                for chunk in page_obj
            ],
            "pagination": {
                "current_page": page_obj.number,
                "total_pages": paginator.num_pages,
                "total_items": paginator.count
            }
        }
        
    except Document.DoesNotExist:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        logger.error(f"Error getting document chunks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

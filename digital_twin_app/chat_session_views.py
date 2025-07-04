"""
Chat Session Views for User-Centric Chat History Management
"""
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum, Max
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View

from .models import ChatSession, ChatMessage, AgentConfiguration, TwinVersion
from .serializers import ChatSessionSerializer, ChatMessageSerializer

logger = logging.getLogger(__name__)


class ChatSessionListView(View):
    """API view for listing and creating user chat sessions"""
    
    @method_decorator(login_required)
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        """Get paginated list of user's chat sessions"""
        try:
            # Get query parameters
            page = int(request.GET.get('page', 1))
            per_page = min(int(request.GET.get('per_page', 20)), 100)  # Max 100 per page
            search = request.GET.get('search', '').strip()
            archived = request.GET.get('archived', 'false').lower() == 'true'
            pinned_only = request.GET.get('pinned_only', 'false').lower() == 'true'
            
            # Base queryset - only user's sessions
            queryset = ChatSession.objects.filter(user=request.user)
            
            # Apply filters
            if not archived:
                queryset = queryset.filter(is_archived=False)
            
            if pinned_only:
                queryset = queryset.filter(is_pinned=True)
            
            if search:
                queryset = queryset.filter(
                    Q(title__icontains=search) |
                    Q(context_summary__icontains=search) |
                    Q(tags__icontains=search)
                )
            
            # Ordering: pinned first, then by last message time
            queryset = queryset.order_by('-is_pinned', '-last_message_at', '-updated_at')
            
            # Paginate
            paginator = Paginator(queryset, per_page)
            page_obj = paginator.get_page(page)
            
            # Serialize sessions
            sessions_data = []
            for session in page_obj:
                session_data = {
                    'id': session.id,  # Use integer ID for now
                    'session_id': session.session_id,
                    'title': session.title or f"Session {session.session_id[:8]}...",
                    'created_at': session.created_at.isoformat(),
                    'updated_at': session.updated_at.isoformat(),
                    'last_message_at': session.last_message_at.isoformat() if session.last_message_at else None,
                    'message_count': session.message_count,
                    'total_tokens_used': session.total_tokens_used,
                    'is_pinned': session.is_pinned,
                    'is_archived': session.is_archived,
                    'tags': session.tags,
                    'twin_version': {
                        'id': str(session.twin_version.id),
                        'name': session.twin_version.name,
                        'version': session.twin_version.version,
                    } if session.twin_version else None,
                    'agent_config': {
                        'id': session.agent_config.id,
                        'name': session.agent_config.name,
                    } if session.agent_config else None,
                }
                sessions_data.append(session_data)
            
            return JsonResponse({
                'success': True,
                'sessions': sessions_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous(),
                }
            })
            
        except Exception as e:
            logger.error(f"Error listing chat sessions for user {request.user.id}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to load chat sessions'
            }, status=500)
    
    def post(self, request):
        """Create a new chat session"""
        try:
            data = json.loads(request.body)
            
            # Generate unique session ID
            session_id = data.get('session_id') or str(uuid.uuid4())
            
            # Get twin version and agent config (user-scoped)
            twin_version = None
            if data.get('twin_version_id'):
                try:
                    twin_version = TwinVersion.objects.filter(
                        Q(user=request.user) | Q(is_shared=True),
                        id=data['twin_version_id']
                    ).first()
                except Exception:
                    pass
            
            agent_config = None
            if data.get('agent_config_id'):
                try:
                    agent_config = AgentConfiguration.objects.filter(
                        Q(user=request.user) | Q(is_shared=True),
                        id=data['agent_config_id']
                    ).first()
                except Exception:
                    pass
            
            # Create session
            session = ChatSession.objects.create(
                session_id=session_id,
                user=request.user,
                title=data.get('title', ''),
                twin_version=twin_version,
                agent_config=agent_config,
                tags=data.get('tags', [])
            )
            
            return JsonResponse({
                'success': True,
                'session': {
                    'id': session.id,  # Use integer ID for now
                    'session_id': session.session_id,
                    'title': session.title,
                    'created_at': session.created_at.isoformat(),
                }
            })
            
        except Exception as e:
            logger.error(f"Error creating chat session for user {request.user.id}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to create chat session'
            }, status=500)


class ChatSessionDetailView(View):
    """API view for individual chat session operations"""
    
    @method_decorator(login_required)
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get_session(self, request, session_id):
        """Get session ensuring user ownership"""
        try:
            return ChatSession.objects.get(
                session_id=session_id,
                user=request.user
            )
        except ChatSession.DoesNotExist:
            return None
    
    def get(self, request, session_id):
        """Get session details and message history"""
        session = self.get_session(request, session_id)
        if not session:
            return JsonResponse({
                'success': False,
                'error': 'Session not found'
            }, status=404)
        
        try:
            # Get messages with pagination
            page = int(request.GET.get('page', 1))
            per_page = min(int(request.GET.get('per_page', 50)), 200)
            
            messages_queryset = session.messages.filter(is_deleted=False).order_by('message_index')
            paginator = Paginator(messages_queryset, per_page)
            page_obj = paginator.get_page(page)
            
            # Serialize messages
            messages_data = []
            for message in page_obj:
                message_data = {
                    'id': message.id,  # Use integer ID for now
                    'role': message.role,
                    'content': message.content,
                    'timestamp': message.timestamp.isoformat(),
                    'message_index': message.message_index,
                    'input_tokens': message.input_tokens,
                    'output_tokens': message.output_tokens,
                    'total_tokens': message.total_tokens,
                    'tools_used': message.tools_used,
                    'model_used': message.model_used,
                    'is_edited': message.is_edited,
                }
                messages_data.append(message_data)
            
            return JsonResponse({
                'success': True,
                'session': {
                    'id': session.id,  # Use integer ID for now
                    'session_id': session.session_id,
                    'title': session.title,
                    'context_summary': session.context_summary,
                    'tags': session.tags,
                    'created_at': session.created_at.isoformat(),
                    'updated_at': session.updated_at.isoformat(),
                    'last_message_at': session.last_message_at.isoformat() if session.last_message_at else None,
                    'message_count': session.message_count,
                    'total_tokens_used': session.total_tokens_used,
                    'is_pinned': session.is_pinned,
                    'is_archived': session.is_archived,
                    'twin_version': {
                        'id': str(session.twin_version.id),
                        'name': session.twin_version.name,
                        'version': session.twin_version.version,
                    } if session.twin_version else None,
                    'agent_config': {
                        'id': session.agent_config.id,
                        'name': session.agent_config.name,
                    } if session.agent_config else None,
                },
                'messages': messages_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count,
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting session {session_id} for user {request.user.id}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to load session details'
            }, status=500)
    
    def patch(self, request, session_id):
        """Update session metadata"""
        session = self.get_session(request, session_id)
        if not session:
            return JsonResponse({
                'success': False,
                'error': 'Session not found'
            }, status=404)
        
        try:
            data = json.loads(request.body)
            
            # Update allowed fields
            if 'title' in data:
                session.title = data['title']
            if 'is_pinned' in data:
                session.is_pinned = bool(data['is_pinned'])
            if 'is_archived' in data:
                session.is_archived = bool(data['is_archived'])
            if 'tags' in data:
                session.tags = data['tags']
            if 'context_summary' in data:
                session.context_summary = data['context_summary']
            
            # Update twin version and agent config (user-scoped)
            if 'twin_version_id' in data:
                if data['twin_version_id']:
                    twin_version = TwinVersion.objects.filter(
                        Q(user=request.user) | Q(is_shared=True),
                        id=data['twin_version_id']
                    ).first()
                    session.twin_version = twin_version
                else:
                    session.twin_version = None
            
            if 'agent_config_id' in data:
                if data['agent_config_id']:
                    agent_config = AgentConfiguration.objects.filter(
                        Q(user=request.user) | Q(is_shared=True),
                        id=data['agent_config_id']
                    ).first()
                    session.agent_config = agent_config
                else:
                    session.agent_config = None
            
            session.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Session updated successfully'
            })
            
        except Exception as e:
            logger.error(f"Error updating session {session_id} for user {request.user.id}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to update session'
            }, status=500)
    
    def delete(self, request, session_id):
        """Delete a chat session"""
        session = self.get_session(request, session_id)
        if not session:
            return JsonResponse({
                'success': False,
                'error': 'Session not found'
            }, status=404)
        
        try:
            session.delete()
            return JsonResponse({
                'success': True,
                'message': 'Session deleted successfully'
            })
            
        except Exception as e:
            logger.error(f"Error deleting session {session_id} for user {request.user.id}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete session'
            }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def add_message_to_session(request, session_id):
    """Add a message to a chat session"""
    try:
        # Get session ensuring user ownership
        session = ChatSession.objects.filter(
            session_id=session_id,
            user=request.user
        ).first()
        
        if not session:
            return JsonResponse({
                'success': False,
                'error': 'Session not found'
            }, status=404)
        
        data = json.loads(request.body)
        
        # Create message
        message = ChatMessage.objects.create(
            session=session,
            role=data.get('role', 'user'),
            content=data.get('content', ''),
            input_tokens=data.get('input_tokens', 0),
            output_tokens=data.get('output_tokens', 0),
            tools_used=data.get('tools_used', []),
            tool_outputs=data.get('tool_outputs', {}),
            model_used=data.get('model_used', ''),
            temperature=data.get('temperature'),
            finish_reason=data.get('finish_reason', '')
        )
        
        # Auto-generate session title if needed
        if not session.title and session.message_count == 1 and message.role == 'user':
            # Generate title from first user message
            title = message.content[:50]
            if len(message.content) > 50:
                title += "..."
            session.title = title
            session.save(update_fields=['title'])
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,  # Use integer ID for now
                'role': message.role,
                'content': message.content,
                'timestamp': message.timestamp.isoformat(),
                'message_index': message.message_index,
                'total_tokens': message.total_tokens,
            }
        })
        
    except Exception as e:
        logger.error(f"Error adding message to session {session_id} for user {request.user.id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to add message'
        }, status=500)


@login_required
@require_http_methods(["POST"])
@csrf_exempt 
def auto_name_session(request, session_id):
    """Auto-generate a name for a chat session using AI"""
    try:
        from .agent import DigitalTwinAgent
        
        # Get session ensuring user ownership
        session = ChatSession.objects.filter(
            session_id=session_id,
            user=request.user
        ).first()
        
        if not session:
            return JsonResponse({
                'success': False,
                'error': 'Session not found'
            }, status=404)
        
        # Get first few messages to generate title
        messages = session.messages.filter(is_deleted=False).order_by('message_index')[:5]
        
        if not messages.exists():
            return JsonResponse({
                'success': False,
                'error': 'No messages in session to generate title from'
            }, status=400)
        
        # Create conversation context for AI
        conversation_text = ""
        for msg in messages:
            conversation_text += f"{msg.role}: {msg.content[:200]}\n"
        
        # Use AI to generate a concise title
        agent = DigitalTwinAgent()
        prompt = f"""Generate a concise, descriptive title (max 50 characters) for this conversation:

{conversation_text}

Title should be:
- Clear and descriptive
- Maximum 50 characters
- No quotes or special formatting
- Captures the main topic/purpose

Title:"""
        
        try:
            response = agent.generate_response(prompt, max_tokens=20)
            generated_title = response.strip().strip('"').strip("'")
            
            # Ensure it's not too long
            if len(generated_title) > 50:
                generated_title = generated_title[:47] + "..."
            
            # Update session title
            session.title = generated_title
            session.save(update_fields=['title'])
            
            return JsonResponse({
                'success': True,
                'title': generated_title
            })
            
        except Exception as ai_error:
            logger.error(f"AI title generation failed: {str(ai_error)}")
            # Fallback: use first user message
            first_user_msg = messages.filter(role='user').first()
            if first_user_msg:
                fallback_title = first_user_msg.content[:47] + "..." if len(first_user_msg.content) > 47 else first_user_msg.content
                session.title = fallback_title
                session.save(update_fields=['title'])
                
                return JsonResponse({
                    'success': True,
                    'title': fallback_title,
                    'note': 'AI naming failed, used fallback method'
                })
        
    except Exception as e:
        logger.error(f"Error auto-naming session {session_id} for user {request.user.id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to generate session name'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def search_chat_sessions(request):
    """Search through user's chat sessions and messages"""
    try:
        query = request.GET.get('q', '').strip()
        if not query:
            return JsonResponse({
                'success': False,
                'error': 'Search query is required'
            }, status=400)
        
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 20)), 50)
        
        # Search in sessions
        session_results = ChatSession.objects.filter(
            user=request.user,
            is_archived=False
        ).filter(
            Q(title__icontains=query) |
            Q(context_summary__icontains=query) |
            Q(tags__icontains=query)
        ).order_by('-last_message_at')
        
        # Search in messages
        message_results = ChatMessage.objects.filter(
            session__user=request.user,
            session__is_archived=False,
            is_deleted=False,
            content__icontains=query
        ).select_related('session').order_by('-timestamp')
        
        # Combine and paginate results
        combined_results = []
        
        # Add session matches
        for session in session_results[:10]:  # Limit session results
            combined_results.append({
                'type': 'session',
                'session_id': session.session_id,
                'title': session.title,
                'timestamp': session.last_message_at or session.updated_at,
                'match_type': 'title/summary',
                'preview': session.context_summary[:100] if session.context_summary else session.title
            })
        
        # Add message matches
        for message in message_results[:20]:  # Limit message results
            combined_results.append({
                'type': 'message',
                'session_id': message.session.session_id,
                'title': message.session.title,
                'timestamp': message.timestamp,
                'match_type': 'message content',
                'preview': message.content[:100],
                'message_index': message.message_index,
                'role': message.role
            })
        
        # Sort by timestamp
        combined_results.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Paginate
        paginator = Paginator(combined_results, per_page)
        page_obj = paginator.get_page(page)
        
        return JsonResponse({
            'success': True,
            'results': list(page_obj),
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_pages': paginator.num_pages,
                'total_count': paginator.count,
            },
            'query': query
        })
        
    except Exception as e:
        logger.error(f"Error searching chat sessions for user {request.user.id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Search failed'
        }, status=500)


@login_required
@require_http_methods(["GET"])
def get_chat_statistics(request):
    """Get user's chat statistics for dashboard/profile"""
    try:
        user = request.user
        
        # Get date range
        days = int(request.GET.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Basic stats
        total_sessions = ChatSession.objects.filter(user=user).count()
        active_sessions = ChatSession.objects.filter(user=user, is_archived=False).count()
        total_messages = ChatMessage.objects.filter(session__user=user, is_deleted=False).count()
        total_tokens = ChatSession.objects.filter(user=user).aggregate(
            total=Sum('total_tokens_used')
        )['total'] or 0
        
        # Recent activity
        recent_sessions = ChatSession.objects.filter(
            user=user,
            created_at__gte=start_date
        ).count()
        
        recent_messages = ChatMessage.objects.filter(
            session__user=user,
            timestamp__gte=start_date,
            is_deleted=False
        ).count()
        
        # Most active sessions
        most_active = ChatSession.objects.filter(
            user=user,
            message_count__gt=0
        ).order_by('-message_count')[:5]
        
        most_active_data = []
        for session in most_active:
            most_active_data.append({
                'session_id': session.session_id,
                'title': session.title,
                'message_count': session.message_count,
                'total_tokens': session.total_tokens_used,
                'last_activity': session.last_message_at.isoformat() if session.last_message_at else None,
            })
        
        return JsonResponse({
            'success': True,
            'statistics': {
                'total_sessions': total_sessions,
                'active_sessions': active_sessions,
                'total_messages': total_messages,
                'total_tokens_used': total_tokens,
                'recent_sessions': recent_sessions,
                'recent_messages': recent_messages,
                'most_active_sessions': most_active_data,
                'period_days': days,
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting chat statistics for user {request.user.id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to load statistics'
        }, status=500)

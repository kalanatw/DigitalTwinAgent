"""
Django Views and FastAPI Integration for Digital Twin Application
"""
import logging
import uuid
import asyncio
import threading
import concurrent.futures
from typing import Dict, Any
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from asgiref.sync import sync_to_async
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json

from .agent import get_agent_instance, get_agent_instance_async
from .models import ChatSession, ChatMessage
from .serializers import ChatRequestSerializer, ChatResponseSerializer

logger = logging.getLogger(__name__)

# Thread pool executor for running async operations in separate threads
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=10, thread_name_prefix="async-agent")

def run_async_in_thread(async_func, *args, **kwargs):
    """
    Run an async function in a separate thread with its own event loop.
    This completely isolates async operations from Django's synchronous context.
    """
    def run_in_new_loop():
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Import Django modules in the thread to avoid context issues
            import os
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_twin.settings')
            import django
            if not django.apps.apps.ready:
                django.setup()
            
            # Clear any existing async context to ensure complete isolation
            import contextvars
            ctx = contextvars.copy_context()
            
            logger.info(f"🔧 Running async function in separate thread: {async_func.__name__}")
            
            # Force sync database settings for this thread
            from django.db import connection
            # Close any existing database connections to force fresh ones
            connection.close()
            
            # Run the async function with completely isolated context
            def run_with_context():
                return loop.run_until_complete(async_func(*args, **kwargs))
            
            result = ctx.run(run_with_context)
            logger.info(f"✅ Successfully completed async function: {async_func.__name__}")
            return result
        except Exception as e:
            logger.error(f"❌ Error in async thread for {async_func.__name__}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            if "async context" in str(e):
                logger.error("🚨 ASYNC CONTEXT ERROR DETECTED - This should not happen in thread!")
                logger.error("Falling back to pure sync mode in this thread...")
                # Instead of raising, try to run the sync version
                raise
            raise
        finally:
            # Clean up the loop and connections
            try:
                from django.db import connection
                connection.close()
            except:
                pass
            loop.close()
    
    # Submit to thread pool and wait for result
    logger.info(f"📤 Submitting to thread pool: {async_func.__name__}")
    future = _thread_pool.submit(run_in_new_loop)
    try:
        result = future.result(timeout=60)  # 60 second timeout
        logger.info(f"📥 Thread pool completed successfully: {async_func.__name__}")
        return result
    except Exception as e:
        logger.error(f"❌ Thread pool execution failed for {async_func.__name__}: {e}")
        raise

# FastAPI app instance
fastapi_app = FastAPI(
    title="Digital Twin API",
    description="API for Digital Twin Chat Agent",
    version="1.0.0"
)

# Add CORS middleware
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for FastAPI
class ChatRequest(BaseModel):
    message: str
    session_id: str = None
    twin_version_id: str = None
    test_agent: dict = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    status: str
    metadata: Dict[str, Any] = None
    error: str = None


# Django Views
@method_decorator(login_required(login_url='/login/'), name='dispatch')
class ChatView(View):
    """Django view for handling chat interface."""
    
    def get(self, request):
        """Render the chat interface."""
        return render(request, 'chat.html')


@method_decorator(csrf_exempt, name='dispatch')
class ApiChatView(View):
    """Django API view for chat functionality."""
    
    def post(self, request):
        """Handle chat message via Django."""
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            session_id = data.get('session_id') or str(uuid.uuid4())
            twin_version_id = data.get('twin_version_id')
            test_agent_config = data.get('test_agent')
            
            if not message:
                return JsonResponse({'error': 'Message is required'}, status=400)
            
            # Define async function to process message
            async def process_message_async():
                # Get agent instance (use test agent if provided)
                if test_agent_config:
                    # Create a test agent instance using the provided configuration
                    from .agent import DigitalAssetsManagerAgent
                    from agents import set_default_openai_key
                    from django.conf import settings
                    
                    # Ensure OpenAI key is set
                    set_default_openai_key(settings.OPENAI_API_KEY)
                    
                    # Create test agent with custom configuration
                    agent = DigitalAssetsManagerAgent(custom_config=test_agent_config)
                    
                    # Add available tools if specified
                    tools_enabled = test_agent_config.get('tools_enabled', [])
                    if tools_enabled:
                        logger.info(f"Test agent configured with tools: {tools_enabled}")
                    
                    logger.info(f"Using test agent: {test_agent_config.get('name', 'Test Agent')}")
                else:
                    # Use regular agent instance with user-specific configuration
                    # For testing: use a fallback user ID if not authenticated
                    user_id = request.user.id if request.user.is_authenticated else 1  # Use user ID 1 for testing
                    agent = await get_agent_instance_async(user_id=user_id)
                
                # Include document context if twin version is specified
                if twin_version_id:
                    logger.info(f"🔍 RAG ENABLED: Processing message with documents from twin_version_id: {twin_version_id}")
                    result = await agent.process_message_with_documents(message, session_id, twin_version_id, user_id)
                else:
                    logger.info("💬 REGULAR CHAT: Processing message without RAG")
                    result = await agent.process_message(message, session_id)
                
                return result
            
            # Run the async function in a separate thread to avoid Django's async context issues
            try:
                result = run_async_in_thread(process_message_async)
            except Exception as e:
                if "async context" in str(e):
                    logger.warning(f"🚨 Async context error detected, falling back to sync agent loading: {e}")
                    # Try with sync agent loading as fallback
                    try:
                        from .agent import get_agent_instance_sync
                        user_id_fallback = request.user.id if request.user.is_authenticated else 1
                        agent = get_agent_instance_sync(user_id=user_id_fallback)
                        # Process message synchronously - check for twin_version_id for RAG
                        import asyncio
                        if twin_version_id:
                            logger.info(f"🔍 Sync fallback with RAG for twin_version_id: {twin_version_id}")
                            result = asyncio.run(agent.process_message_with_documents(message, session_id, twin_version_id, user_id_fallback))
                        else:
                            result = asyncio.run(agent.process_message(message, session_id))
                        logger.info("✅ Successfully processed message with sync fallback")
                    except Exception as sync_e:
                        logger.error(f"❌ Sync fallback also failed: {sync_e}")
                        raise e  # Re-raise original error
                else:
                    raise
            
            # Store in database (temporarily disabled due to async context)
            # TODO: Implement proper async database storage
            try:
                pass  # Database storage temporarily disabled
                
            except Exception as db_error:
                logger.warning(f"Database storage failed: {db_error}")
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error in chat view: {e}")
            return JsonResponse({'error': 'Internal server error'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SessionHistoryView(View):
    """Django view for retrieving conversation history."""
    
    def get(self, request, session_id):
        """Get conversation history for a session."""
        try:
            async def get_history_async():
                # Try to get from database first
                try:
                    chat_session = await sync_to_async(ChatSession.objects.get)(session_id=session_id)
                    messages = await sync_to_async(list)(ChatMessage.objects.filter(session=chat_session).order_by('created_at'))
                    history = []
                    for msg in messages:
                        history.append({
                            'id': msg.id,
                            'role': msg.role,
                            'content': msg.content,
                            'tools_used': msg.tools_used or [],
                            'timestamp': msg.created_at.isoformat()
                        })
                    return {'session_id': session_id, 'messages': history}
                except ChatSession.DoesNotExist:
                    # Try Redis cache
                    user_id = request.user.id if request.user.is_authenticated else None
                    agent = await get_agent_instance_async(user_id=user_id)
                    history = await agent.get_conversation_history(session_id)
                    return {'session_id': session_id, 'messages': history}
            
            # Run async function in separate thread
            result = run_async_in_thread(get_history_async)
            return JsonResponse(result)
                
        except Exception as e:
            logger.error(f"Error retrieving history for session {session_id}: {e}")
            return JsonResponse({'error': 'Failed to retrieve history'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SessionClearView(View):
    """Django view for clearing conversation history."""
    
    def delete(self, request, session_id):
        """Clear conversation history for a session."""
        try:
            async def clear_session_async():
                # Clear from database
                try:
                    chat_session = await sync_to_async(ChatSession.objects.get)(session_id=session_id)
                    await sync_to_async(ChatMessage.objects.filter(session=chat_session).delete)()
                    await sync_to_async(chat_session.delete)()
                except ChatSession.DoesNotExist:
                    pass
                
                # Clear from Redis cache
                user_id = getattr(request, 'user', None)
                user_id = user_id.id if user_id and user_id.is_authenticated else None
                agent = await get_agent_instance_async(user_id=user_id)
                await agent.clear_conversation(session_id)
                
                return {'message': f'Session {session_id} cleared successfully'}
            
            # Run async function in separate thread
            result = run_async_in_thread(clear_session_async)
            return JsonResponse(result)
            
        except Exception as e:
            logger.error(f"Error clearing session {session_id}: {e}")
            return JsonResponse({'error': 'Failed to clear session'}, status=500)


# FastAPI endpoints
@fastapi_app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """FastAPI endpoint for chat functionality."""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        
        if not request.message:
            raise HTTPException(status_code=400, detail="Message is required")
        
        # Get agent instance and process message
        # Note: FastAPI doesn't have user context, so use default agent
        default_user_id = 1  # Use default user for FastAPI calls without authentication
        agent = await get_agent_instance_async(user_id=default_user_id)
        
        # Include document context if twin version is specified
        if request.twin_version_id:
            result = await agent.process_message_with_documents(request.message, session_id, request.twin_version_id, default_user_id)
        else:
            result = await agent.process_message(request.message, session_id)
        
        logger.info(f"FastAPI chat processed for session: {session_id}")
        
        return ChatResponse(**result)
        
    except Exception as e:
        logger.error(f"Error in FastAPI chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "Digital Twin API"}


@fastapi_app.get("/sessions/{session_id}/history")
async def get_conversation_history(session_id: str):
    """Get conversation history for a session."""
    try:
        agent = await get_agent_instance_async(user_id=None)  # FastAPI doesn't have user context
        history = await agent.get_conversation_history(session_id)
        return {"session_id": session_id, "history": history}
    except Exception as e:
        logger.error(f"Error retrieving history for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    try:
        agent = await get_agent_instance_async(user_id=None)  # FastAPI doesn't have user context
        success = await agent.clear_conversation(session_id)
        if success:
            return {"message": f"Session {session_id} cleared successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear session")
    except Exception as e:
        logger.error(f"Error clearing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/tools/sensor-data")
async def get_sensor_data(sensor_type: str = "all", location: str = "main_facility"):
    """Direct endpoint to get sensor data."""
    try:
        # Import the actual function, not the tool wrapper
        from .tools import _get_sensor_data
        result = _get_sensor_data(sensor_type, location)
        return json.loads(result)
    except Exception as e:
        logger.error(f"Error getting sensor data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.get("/tools/system-status")
async def get_system_status(system_component: str = "all"):
    """Direct endpoint to get system status."""
    try:
        from .tools import _get_system_status
        result = _get_system_status(system_component)
        return json.loads(result)
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Django REST Framework views
@api_view(['POST'])
def drf_chat_view(request):
    """Django REST Framework chat view."""
    serializer = ChatRequestSerializer(data=request.data)
    if serializer.is_valid():
        message = serializer.validated_data['message']
        session_id = serializer.validated_data.get('session_id') or str(uuid.uuid4())
        
        try:
            # Define async function to process message
            async def process_message_async():
                user_id = request.user.id if request.user.is_authenticated else None
                agent = await get_agent_instance_async(user_id=user_id)
                return await agent.process_message(message, session_id)
            
            # Run async function in separate thread
            result = run_async_in_thread(process_message_async)
            
            response_serializer = ChatResponseSerializer(data=result)
            if response_serializer.is_valid():
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(response_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error in DRF chat view: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Cleanup function for thread pool
def cleanup_thread_pool():
    """Clean up the thread pool when the application shuts down."""
    global _thread_pool
    if _thread_pool:
        logger.info("Shutting down async agent thread pool...")
        _thread_pool.shutdown(wait=True)
        logger.info("Thread pool shutdown complete.")

# Register cleanup function (Django will call this on shutdown if available)
import atexit
atexit.register(cleanup_thread_pool)

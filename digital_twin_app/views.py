"""
Django Views and FastAPI Integration for Digital Twin Application
"""
import logging
import uuid
import asyncio
from typing import Dict, Any
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json

from .agent import get_agent_instance
from .models import ChatSession, ChatMessage
from .serializers import ChatRequestSerializer, ChatResponseSerializer

logger = logging.getLogger(__name__)

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

class ChatResponse(BaseModel):
    response: str
    session_id: str
    status: str
    metadata: Dict[str, Any] = None
    error: str = None


# Django Views
class ChatView(View):
    """Django view for handling chat interface."""
    
    def get(self, request):
        """Render the chat interface."""
        return render(request, 'chat.html')


@method_decorator(csrf_exempt, name='dispatch')
class ApiChatView(View):
    """Django API view for chat functionality."""
    
    async def post(self, request):
        """Handle chat message via Django."""
        try:
            data = json.loads(request.body)
            message = data.get('message', '')
            session_id = data.get('session_id') or str(uuid.uuid4())
            
            if not message:
                return JsonResponse({'error': 'Message is required'}, status=400)
            
            # Get agent instance and process message
            agent = get_agent_instance()
            result = await agent.process_message(message, session_id)
            
            # Store in database
            try:
                chat_session, created = ChatSession.objects.get_or_create(
                    session_id=session_id,
                    defaults={'is_active': True}
                )
                
                # Save user message
                ChatMessage.objects.create(
                    session=chat_session,
                    role='user',
                    content=message
                )
                
                # Save assistant response
                ChatMessage.objects.create(
                    session=chat_session,
                    role='assistant',
                    content=result['response'],
                    tools_used=result.get('metadata', {}).get('tools_used', [])
                )
                
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
    
    async def get(self, request, session_id):
        """Get conversation history for a session."""
        try:
            # Try to get from database first
            try:
                chat_session = ChatSession.objects.get(session_id=session_id)
                messages = ChatMessage.objects.filter(session=chat_session).order_by('created_at')
                history = []
                for msg in messages:
                    history.append({
                        'id': msg.id,
                        'role': msg.role,
                        'content': msg.content,
                        'tools_used': msg.tools_used or [],
                        'timestamp': msg.created_at.isoformat()
                    })
                return JsonResponse({'session_id': session_id, 'messages': history})
            except ChatSession.DoesNotExist:
                # Try Redis cache
                agent = get_agent_instance()
                history = await agent.get_conversation_history(session_id)
                return JsonResponse({'session_id': session_id, 'messages': history})
                
        except Exception as e:
            logger.error(f"Error retrieving history for session {session_id}: {e}")
            return JsonResponse({'error': 'Failed to retrieve history'}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SessionClearView(View):
    """Django view for clearing conversation history."""
    
    async def delete(self, request, session_id):
        """Clear conversation history for a session."""
        try:
            # Clear from database
            try:
                chat_session = ChatSession.objects.get(session_id=session_id)
                ChatMessage.objects.filter(session=chat_session).delete()
                chat_session.delete()
            except ChatSession.DoesNotExist:
                pass
            
            # Clear from Redis cache
            agent = get_agent_instance()
            await agent.clear_conversation(session_id)
            
            return JsonResponse({'message': f'Session {session_id} cleared successfully'})
            
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
        agent = get_agent_instance()
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
        agent = get_agent_instance()
        history = await agent.get_conversation_history(session_id)
        return {"session_id": session_id, "history": history}
    except Exception as e:
        logger.error(f"Error retrieving history for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@fastapi_app.delete("/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    try:
        agent = get_agent_instance()
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
            # Process message asynchronously
            agent = get_agent_instance()
            
            # Run async function in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(agent.process_message(message, session_id))
            loop.close()
            
            response_serializer = ChatResponseSerializer(data=result)
            if response_serializer.is_valid():
                return Response(response_serializer.data, status=status.HTTP_200_OK)
            else:
                return Response(response_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error in DRF chat view: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

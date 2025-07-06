"""
Gmail Views for OAuth connection and email management.

This module handles Gmail OAuth2 authentication flow and email retrieval
following Gmail API documentation standards.
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import UserGmailConnection
from .services.gmail_api_service import GmailAPIService

logger = logging.getLogger(__name__)


@login_required
def gmail_connect(request):
    """
    Initiate Gmail OAuth flow with correct redirect URI.
    
    Creates OAuth2 authorization URL with proper Gmail API scopes
    and redirects user to Google's authorization server.
    """
    try:
        # Get Google OAuth configuration
        google_config = settings.GOOGLE_OAUTH_CONFIG.get('web', {})
        client_id = google_config.get('client_id')
        
        if not client_id:
            logger.error("Google OAuth client_id not configured")
            messages.error(request, 'Gmail OAuth not properly configured')
            return redirect('/email/')
        
        # Use exact redirect URI from google_oauth_config.json
        redirect_uri = "http://localhost:8000/email/callback/"
        
        # Gmail API scopes for reading and sending emails
        scopes = [
            'https://mail.google.com/',  # Full Gmail access including send
            'email',
            'profile'
        ]
        scope_string = ' '.join(scopes)
        
        # Generate state parameter for CSRF protection
        import secrets
        state = secrets.token_urlsafe(32)
        request.session['gmail_oauth_state'] = state
        
        # Build OAuth authorization URL
        auth_params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': scope_string,
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state
        }
        
        auth_url = (
            f"https://accounts.google.com/o/oauth2/auth?"
            f"{'&'.join(f'{k}={v}' for k, v in auth_params.items())}"
        )
        
        logger.info(f"Redirecting user {request.user.username} to Gmail OAuth")
        return redirect(auth_url)
        
    except Exception as error:
        logger.error(f"Error initiating Gmail OAuth: {error}")
        messages.error(request, 'Error connecting to Gmail. Please try again.')
        return redirect('/email/')


@csrf_exempt
def gmail_callback(request):
    """
    Handle Gmail OAuth callback and exchange code for tokens.
    
    Processes the OAuth callback, validates state parameter,
    exchanges authorization code for access tokens, and stores
    the connection information.
    """
    try:
        # Extract parameters from callback
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        # Check for OAuth errors
        if error:
            logger.error(f"Gmail OAuth error: {error}")
            messages.error(request, f'Gmail connection failed: {error}')
            return redirect('/email/')
        
        # Validate state parameter for CSRF protection
        stored_state = request.session.get('gmail_oauth_state')
        if not state or state != stored_state:
            logger.error("Gmail OAuth state mismatch")
            messages.error(request, 'Invalid OAuth state. Please try again.')
            return redirect('/email/')
        
        if not code:
            logger.error("No authorization code in Gmail OAuth callback")
            messages.error(request, 'No authorization code received')
            return redirect('/email/')
        
        # Exchange authorization code for tokens
        token_data = _exchange_code_for_tokens(code)
        if not token_data:
            messages.error(request, 'Failed to exchange authorization code')
            return redirect('/email/')
        
        # Get user information
        user_info = _get_user_info(token_data['access_token'])
        if not user_info:
            messages.error(request, 'Failed to get user information')
            return redirect('/email/')
        
        # Store Gmail connection
        _store_gmail_connection(request.user, token_data, user_info)
        
        # Clean up session
        request.session.pop('gmail_oauth_state', None)
        
        logger.info(f"Successfully connected Gmail for user {request.user.username}")
        messages.success(request, 'Gmail connected successfully!')
        
        return redirect('/email/')
        
    except Exception as error:
        logger.error(f"Error in Gmail OAuth callback: {error}")
        messages.error(request, 'Error connecting Gmail. Please try again.')
        return redirect('/email/')


def _exchange_code_for_tokens(code: str) -> Optional[Dict]:
    """
    Exchange OAuth authorization code for access and refresh tokens.
    
    Args:
        code: Authorization code from OAuth callback
        
    Returns:
        Dict containing token information or None if failed
    """
    try:
        google_config = settings.GOOGLE_OAUTH_CONFIG.get('web', {})
        
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            'client_id': google_config.get('client_id'),
            'client_secret': google_config.get('client_secret'),
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': "http://localhost:8000/email/callback/"
        }
        
        response = requests.post(token_url, data=token_data, timeout=30)
        response.raise_for_status()
        
        token_json = response.json()
        
        if 'access_token' not in token_json:
            logger.error(f"No access token in response: {token_json}")
            return None
        
        return token_json
        
    except requests.RequestException as error:
        logger.error(f"HTTP error exchanging code for tokens: {error}")
        return None
    except Exception as error:
        logger.error(f"Unexpected error exchanging code for tokens: {error}")
        return None


def _get_user_info(access_token: str) -> Optional[Dict]:
    """
    Get user information from Google OAuth2 API.
    
    Args:
        access_token: OAuth2 access token
        
    Returns:
        Dict containing user information or None if failed
    """
    try:
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = requests.get(user_info_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        user_data = response.json()
        
        if 'email' not in user_data:
            logger.error(f"No email in user info: {user_data}")
            return None
        
        return user_data
        
    except requests.RequestException as error:
        logger.error(f"HTTP error getting user info: {error}")
        return None
    except Exception as error:
        logger.error(f"Unexpected error getting user info: {error}")
        return None


def _store_gmail_connection(user, token_data: Dict, user_info: Dict) -> None:
    """
    Store or update Gmail connection information in database.
    
    Args:
        user: Django User instance
        token_data: Dict containing OAuth token information
        user_info: Dict containing user profile information
    """
    try:
        # Calculate token expiration time
        expires_in = token_data.get('expires_in', 3600)  # Default to 1 hour
        expires_at = timezone.now() + timedelta(seconds=expires_in)
        
        # Extract granted scopes
        scope = token_data.get('scope', '')
        scopes_granted = scope.split(' ') if scope else []
        
        # Store or update Gmail connection
        gmail_connection, created = UserGmailConnection.objects.update_or_create(
            user=user,
            defaults={
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token', ''),
                'token_expires_at': expires_at,
                'scopes_granted': scopes_granted,
                'email_address': user_info['email'],
                'is_active': True
            }
        )
        
        action = "Created" if created else "Updated"
        logger.info(f"{action} Gmail connection for user {user.username}")
        
    except Exception as error:
        logger.error(f"Error storing Gmail connection: {error}")
        raise


@login_required
def email_management(request):
    """
    Email management page displaying Gmail connection status and emails.
    
    Shows Gmail connection status and provides interface for
    connecting/disconnecting Gmail and viewing emails.
    """
    has_connection = False
    connected_email = ''
    
    try:
        gmail_connection = UserGmailConnection.objects.get(
            user=request.user,
            is_active=True
        )
        has_connection = True
        connected_email = gmail_connection.email_address
        
    except UserGmailConnection.DoesNotExist:
        logger.info(f"No Gmail connection found for user {request.user.username}")
    
    context = {
        'has_gmail_connection': has_connection,
        'connected_email': connected_email,
    }
    
    return render(request, 'email_management.html', context)


@login_required
def gmail_disconnect(request):
    """
    Disconnect Gmail account by deactivating the connection.
    
    Marks the Gmail connection as inactive and optionally
    revokes the OAuth tokens with Google.
    """
    try:
        gmail_connection = UserGmailConnection.objects.get(
            user=request.user,
            is_active=True
        )
        
        # Optionally revoke token with Google
        try:
            revoke_url = f"https://oauth2.googleapis.com/revoke?token={gmail_connection.access_token}"
            requests.post(revoke_url, timeout=10)
        except Exception as revoke_error:
            logger.warning(f"Failed to revoke token with Google: {revoke_error}")
        
        # Deactivate connection
        gmail_connection.is_active = False
        gmail_connection.save()
        
        logger.info(f"Disconnected Gmail for user {request.user.username}")
        messages.success(request, 'Gmail disconnected successfully.')
        
    except UserGmailConnection.DoesNotExist:
        messages.info(request, 'Gmail was not connected.')
    except Exception as error:
        logger.error(f"Error disconnecting Gmail: {error}")
        messages.error(request, 'Error disconnecting Gmail.')
    
    return redirect('/email/')


# API Endpoints

@login_required
def gmail_connection_status(request):
    """
    API endpoint to check Gmail connection status.
    
    Returns:
        JsonResponse: Connection status and user information
    """
    try:
        gmail_connection = UserGmailConnection.objects.get(
            user=request.user,
            is_active=True
        )
        
        return JsonResponse({
            'success': True,
            'connected': True,
            'email': gmail_connection.email_address,
            'scopes': gmail_connection.scopes_granted,
            'token_expired': gmail_connection.is_token_expired()
        })
        
    except UserGmailConnection.DoesNotExist:
        return JsonResponse({
            'success': True,
            'connected': False,
            'email': '',
            'scopes': []
        })
    except Exception as error:
        logger.error(f"Error checking Gmail status: {error}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to check Gmail status'
        }, status=500)


@login_required
def gmail_list_emails(request):
    """
    API endpoint to fetch Gmail emails with pagination.
    
    Query Parameters:
        max_results: Maximum number of emails to return (default: 10)
        query: Gmail search query string
        page_token: Token for pagination
        
    Returns:
        JsonResponse: Email list and pagination information
    """
    try:
        # Get Gmail connection
        gmail_connection = UserGmailConnection.objects.get(
            user=request.user,
            is_active=True
        )
        
        # Initialize Gmail service
        gmail_service = GmailAPIService(
            access_token=gmail_connection.access_token,
            refresh_token=gmail_connection.refresh_token
        )
        
        # Get query parameters
        max_results = min(int(request.GET.get('max_results', 10)), 50)
        query = request.GET.get('query', '')
        page_token = request.GET.get('page_token')
        
        # Fetch emails
        emails, next_page_token = gmail_service.list_messages(
            max_results=max_results,
            query=query,
            page_token=page_token
        )
        
        return JsonResponse({
            'success': True,
            'data': {
                'emails': emails,
                'count': len(emails),
                'next_page_token': next_page_token
            }
        })
        
    except UserGmailConnection.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Gmail not connected'
        }, status=401)
    except Exception as error:
        logger.error(f"Error fetching Gmail emails: {error}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to fetch emails'
        }, status=500)


# Email Reply Generation API Endpoints

@login_required
@require_http_methods(["POST"])
def generate_email_reply_api(request):
    """
    Generate email reply using selected agent and twin version.
    
    POST /api/email/generate-reply/
    Body: {
        "email_id": "gmail_message_id",
        "agent_id": "selected_agent_id", 
        "twin_version_id": "selected_twin_version_id",
        "tone": "professional|friendly|formal|casual",
        "additional_context": "optional additional instructions"
    }
    """
    try:
        data = json.loads(request.body)
        email_id = data.get('email_id')
        agent_id = data.get('agent_id')
        twin_version_id = data.get('twin_version_id')
        tone = data.get('tone', 'professional')
        additional_context = data.get('additional_context', '')
        
        if not all([email_id, agent_id, twin_version_id]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required parameters: email_id, agent_id, twin_version_id'
            }, status=400)
        
        # Get user's Gmail connection
        try:
            gmail_connection = UserGmailConnection.objects.get(
                user=request.user,
                is_active=True
            )
        except UserGmailConnection.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Gmail connection not found'
            }, status=400)
        
        # Initialize Gmail service
        gmail_service = GmailAPIService(
            access_token=gmail_connection.access_token,
            refresh_token=gmail_connection.refresh_token
        )
        
        # Get the original email
        original_email = gmail_service.get_message(email_id)
        if not original_email:
            return JsonResponse({
                'success': False,
                'error': 'Email not found'
            }, status=404)
        
        # Generate reply using chat API with email-specific system prompt
        reply_content = generate_email_reply_with_agent(
            email_content=original_email,
            agent_id=agent_id,
            twin_version_id=twin_version_id,
            tone=tone,
            additional_context=additional_context,
            user=request.user
        )
        
        # Prepare reply data
        reply_data = {
            'to': original_email.get('from', ''),
            'subject': f"Re: {original_email.get('subject', '')}" if not original_email.get('subject', '').startswith('Re:') else original_email.get('subject', ''),
            'body': reply_content,
            'cc': [],
            'bcc': [],
            'from': gmail_connection.email_address
        }
        
        return JsonResponse({
            'success': True,
            'reply_data': reply_data,
            'original_email': {
                'subject': original_email.get('subject', ''),
                'from': original_email.get('from', ''),
                'body': original_email.get('body_text', '') or original_email.get('snippet', ''),
                'date': original_email.get('date', '')
            }
        })
        
    except Exception as error:
        logger.error(f"Error generating email reply: {error}")
        return JsonResponse({
            'success': False,
            'error': str(error)
        }, status=500)


@login_required
def get_active_agent_api(request):
    """
    Get the currently active agent for the user.
    
    GET /api/agents/active/
    """
    try:
        from .models import AgentConfiguration
        
        active_agent = AgentConfiguration.objects.filter(
            user=request.user,
            is_active=True
        ).first()
        
        if active_agent:
            twin_version_name = 'Default'
            if hasattr(active_agent, 'twin_version') and active_agent.twin_version:
                twin_version_name = active_agent.twin_version.name
            elif hasattr(active_agent, 'current_twin_version'):
                twin_version_name = getattr(active_agent.current_twin_version, 'name', 'Default')
            
            return JsonResponse({
                'success': True,
                'agent': {
                    'id': active_agent.id,
                    'name': active_agent.name,
                    'twin_version': twin_version_name,
                    'personality': getattr(active_agent, 'personality', ''),
                    'expertise': getattr(active_agent, 'expertise', '')
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'No active agent found'
            })
            
    except Exception as error:
        logger.error(f"Error getting active agent: {error}")
        return JsonResponse({
            'success': False,
            'error': str(error)
        }, status=500)


@login_required
def list_user_agents_api(request):
    """
    List all available agents for the user.
    
    GET /api/agents/list/
    """
    try:
        from .models import AgentConfiguration
        
        agents = AgentConfiguration.objects.filter(user=request.user)
        
        agents_data = [{
            'id': agent.id,
            'name': agent.name,
            'personality': getattr(agent, 'personality', ''),
            'expertise': getattr(agent, 'expertise', ''),
            'is_active': agent.is_active
        } for agent in agents]
        
        return JsonResponse({
            'success': True,
            'agents': agents_data
        })
        
    except Exception as error:
        logger.error(f"Error listing agents: {error}")
        return JsonResponse({
            'success': False,
            'error': str(error)
        }, status=500)


@login_required
def list_twin_versions_api(request):
    """
    List twin versions for an agent.
    
    GET /api/twins/versions/?agent_id=<agent_id>
    """
    try:
        from .models import TwinVersion
        
        agent_id = request.GET.get('agent_id')
        if not agent_id:
            return JsonResponse({
                'success': False,
                'error': 'Agent ID required'
            }, status=400)
        
        # Check if TwinVersion model exists and get versions
        try:
            versions = TwinVersion.objects.filter(
                user=request.user  # Assuming TwinVersion has user field
            )
            
            versions_data = [{
                'id': version.id,
                'name': version.name,
                'version': getattr(version, 'version', '1.0'),
                'description': getattr(version, 'description', '')
            } for version in versions]
            
        except Exception:
            # If TwinVersion model doesn't exist or has different structure, 
            # create default versions
            versions_data = [
                {'id': 'default', 'name': 'Default', 'version': '1.0', 'description': 'Default version'},
                {'id': 'enhanced', 'name': 'Enhanced', 'version': '2.0', 'description': 'Enhanced capabilities'},
                {'id': 'expert', 'name': 'Expert', 'version': '3.0', 'description': 'Expert level responses'}
            ]
        
        return JsonResponse({
            'success': True,
            'versions': versions_data
        })
        
    except Exception as error:
        logger.error(f"Error listing twin versions: {error}")
        return JsonResponse({
            'success': False,
            'error': str(error)
        }, status=500)


def generate_email_reply_with_agent(email_content, agent_id, twin_version_id, tone, additional_context, user):
    """
    Generate email reply using the chat API with email-specific system prompt.
    """
    try:
        from .models import AgentConfiguration
        
        # Get agent
        agent = AgentConfiguration.objects.get(id=agent_id, user=user)
        
        # Create email-specific system prompt
        system_prompt = create_email_system_prompt(agent, email_content, tone, additional_context)
        
        # Create user message for the chat
        user_message = f"""
Please generate an email reply with {tone} tone.
{f"Additional instructions: {additional_context}" if additional_context else ""}

Make sure to:
1. Address all points in the original email
2. Maintain a {tone} tone
3. Be helpful and actionable
4. Use proper email etiquette
"""
        
        # Use existing chat service or create a simple implementation
        reply_content = generate_chat_response(
            user_message=user_message,
            system_prompt=system_prompt,
            agent=agent
        )
        
        return reply_content
        
    except Exception as error:
        logger.error(f"Error in generate_email_reply_with_agent: {error}")
        raise error


def create_email_system_prompt(agent, original_email, tone, additional_context=""):
    """
    Create specialized system prompt for email reply generation.
    """
    return f"""
You are {agent.name}, an AI assistant helping to compose professional email replies.

Your characteristics:
- Personality: {getattr(agent, 'personality', 'Professional and helpful')}
- Expertise: {getattr(agent, 'expertise', 'General assistance')}
- Communication style: {tone}

TASK: Generate a professional email reply

ORIGINAL EMAIL CONTEXT:
From: {original_email.get('from', 'Unknown')}
Subject: {original_email.get('subject', 'No Subject')}
Date: {original_email.get('date', 'Unknown')}
Content: {original_email.get('body_text', '') or original_email.get('snippet', '')}

REPLY GUIDELINES:
1. Maintain {tone} tone throughout
2. Address all points raised in original email
3. Be concise but comprehensive
4. Use proper email etiquette
5. Include appropriate greeting and closing
6. Make response actionable and helpful
7. Stay true to your personality and expertise

{f"ADDITIONAL CONTEXT: {additional_context}" if additional_context else ""}

Generate only the email body content (no headers like To:, From:, Subject:).
Start with an appropriate greeting and end with a professional closing.
"""


def generate_chat_response(user_message, system_prompt, agent):
    """
    Generate chat response using existing chat service or simple implementation.
    """
    try:
        # Try to use existing chat service
        from .views import ApiChatView
        from django.http import HttpRequest
        import json
        
        # Create a mock request for the chat API
        mock_request = HttpRequest()
        mock_request.method = 'POST'
        mock_request.user = agent.user
        
        chat_data = {
            'message': user_message,
            'system_prompt': system_prompt,
            'agent_id': agent.id
        }
        mock_request._body = json.dumps(chat_data).encode('utf-8')
        
        # Use the existing chat view
        chat_view = ApiChatView()
        response = chat_view.post(mock_request)
        
        if response.status_code == 200:
            response_data = json.loads(response.content)
            return response_data.get('response', 'Unable to generate response')
        else:
            # Fallback to simple response
            return generate_simple_email_response(user_message, system_prompt)
            
    except Exception as error:
        logger.error(f"Error using chat service: {error}")
        return generate_simple_email_response(user_message, system_prompt)


def generate_simple_email_response(user_message, system_prompt):
    """
    Simple fallback email response generator.
    """
    return f"""Dear [Recipient],

Thank you for your email. I have received your message and will review the information you provided.

I will get back to you with a detailed response shortly. In the meantime, please feel free to reach out if you have any urgent questions or concerns.

Best regards,
[Your Name]
"""


@login_required
@require_http_methods(["POST"])
def send_email_api(request):
    """
    Send email through Gmail API.
    
    POST /api/gmail/send/
    Body: {
        "to": "recipient@example.com",
        "cc": "cc@example.com",  // optional
        "bcc": "bcc@example.com",  // optional
        "subject": "Email subject",
        "body": "Email body content",
        "from": "sender@example.com"  // optional, will use connected Gmail if not provided
    }
    """
    try:
        data = json.loads(request.body)
        to_email = data.get('to')
        subject = data.get('subject')
        body = data.get('body')
        cc = data.get('cc', '')
        bcc = data.get('bcc', '')
        from_email = data.get('from', '')
        
        if not all([to_email, subject, body]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields: to, subject, body'
            }, status=400)
        
        # Get user's Gmail connection
        try:
            gmail_connection = UserGmailConnection.objects.get(
                user=request.user,
                is_active=True
            )
        except UserGmailConnection.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Gmail connection not found'
            }, status=400)
        
        # Initialize Gmail service
        gmail_service = GmailAPIService(
            access_token=gmail_connection.access_token,
            refresh_token=gmail_connection.refresh_token
        )
        
        # Prepare email data
        email_data = {
            'to': to_email,
            'cc': cc if cc else None,
            'bcc': bcc if bcc else None,
            'subject': subject,
            'body': body,
            'from': from_email or gmail_connection.email_address
        }
        
        # Send email using Gmail service
        result = gmail_service.send_email(email_data)
        
        if result and result.get('id'):
            return JsonResponse({
                'success': True,
                'message': 'Email sent successfully',
                'email_id': result['id']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to send email'
            }, status=500)
        
    except Exception as error:
        logger.error(f"Error sending email: {error}")
        return JsonResponse({
            'success': False,
            'error': str(error)
        }, status=500)


@login_required
def gmail_reauthorize(request):
    """
    Force Gmail re-authorization with updated scopes.
    
    Clears existing OAuth tokens and redirects user to Google's
    OAuth consent screen to re-authorize with expanded permissions.
    This is necessary when we need additional Gmail API scopes.
    """
    try:
        # Clear existing Gmail connection tokens
        try:
            gmail_connection = UserGmailConnection.objects.get(
                user=request.user,
                is_active=True
            )
            
            # Optionally revoke old token with Google
            try:
                revoke_url = f"https://oauth2.googleapis.com/revoke?token={gmail_connection.access_token}"
                requests.post(revoke_url, timeout=10)
                logger.info(f"Revoked old Gmail token for user {request.user.username}")
            except Exception as revoke_error:
                logger.warning(f"Failed to revoke old token: {revoke_error}")
            
            # Delete the old connection to force fresh OAuth
            gmail_connection.delete()
            logger.info(f"Cleared existing Gmail connection for user {request.user.username}")
            
        except UserGmailConnection.DoesNotExist:
            logger.info(f"No existing Gmail connection found for user {request.user.username}")
        
        # Get Google OAuth configuration
        google_config = settings.GOOGLE_OAUTH_CONFIG.get('web', {})
        client_id = google_config.get('client_id')
        
        if not client_id:
            logger.error("Google OAuth client_id not configured")
            messages.error(request, 'Gmail OAuth not properly configured')
            return redirect('/email/')
        
        # Use exact redirect URI from google_oauth_config.json
        redirect_uri = "http://localhost:8000/email/callback/"
        
        # Updated Gmail API scopes - using the full Gmail scope for all permissions
        scopes = [
            'https://mail.google.com/',  # Full Gmail access including send
            'email',
            'profile'
        ]
        scope_string = ' '.join(scopes)
        
        # Generate state parameter for CSRF protection
        import secrets
        state = secrets.token_urlsafe(32)
        request.session['gmail_oauth_state'] = state
        request.session['gmail_reauth'] = True  # Mark as re-authorization
        
        # Build OAuth authorization URL with consent prompt to force re-authorization
        auth_params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': scope_string,
            'access_type': 'offline',
            'prompt': 'consent',  # Force consent screen to show updated permissions
            'state': state
        }
        
        auth_url = (
            f"https://accounts.google.com/o/oauth2/auth?"
            f"{'&'.join(f'{k}={v}' for k, v in auth_params.items())}"
        )
        
        logger.info(f"Redirecting user {request.user.username} to Gmail re-authorization")
        messages.info(request, 'Re-authorizing Gmail with updated permissions...')
        
        return redirect(auth_url)
        
    except Exception as error:
        logger.error(f"Error during Gmail re-authorization: {error}")
        messages.error(request, 'Error starting re-authorization process.')
        return redirect('/email/')


@login_required
def gmail_check_scope_error(request):
    """
    API endpoint to check if Gmail connection has scope issues.
    
    Returns:
        JsonResponse: Information about scope validation and re-auth requirements
    """
    try:
        gmail_connection = UserGmailConnection.objects.get(
            user=request.user,
            is_active=True
        )
        
        # Try to validate scopes by making a test API call
        gmail_service = GmailAPIService(
            access_token=gmail_connection.access_token,
            refresh_token=gmail_connection.refresh_token
        )
        
        # Test if we can access Gmail profile (basic read)
        profile = gmail_service.get_user_profile()
        if not profile:
            return JsonResponse({
                'success': True,
                'has_scope_issue': True,
                'error_type': 'read_access',
                'message': 'Gmail read access is not available. Re-authorization required.'
            })
        
        # For now, we'll assume send scope is the issue if we get this far
        # A more robust check would involve testing the send endpoint
        return JsonResponse({
            'success': True,
            'has_scope_issue': True,
            'error_type': 'send_access',
            'message': 'Gmail send permissions may need updating. Try re-authorization if sending fails.'
        })
        
    except UserGmailConnection.DoesNotExist:
        return JsonResponse({
            'success': True,
            'has_scope_issue': True,
            'error_type': 'no_connection',
            'message': 'Gmail not connected. Please connect your Gmail account.'
        })
    except Exception as error:
        logger.error(f"Error checking Gmail scopes: {error}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to check Gmail permissions'
        }, status=500)

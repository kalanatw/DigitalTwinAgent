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
        
        # Gmail API scopes for reading emails
        scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.labels',
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

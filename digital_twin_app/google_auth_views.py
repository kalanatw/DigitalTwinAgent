"""
Google OAuth Authentication Views for Digital Twin App
"""
import json
import logging
import requests
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .social_auth import process_google_auth_code

logger = logging.getLogger(__name__)


@csrf_exempt
def google_login(request):
    """
    Custom Google OAuth login endpoint at /api/auth/google/login/
    Redirects to Google OAuth authorization URL
    """
    try:
        # Get Google OAuth config
        google_config = settings.GOOGLE_OAUTH_CONFIG.get('web', {})
        client_id = google_config.get('client_id')
        client_secret = google_config.get('client_secret')
        
        if not client_id or not client_secret:
            logger.error("Google OAuth client_id or client_secret not configured")
            return JsonResponse({"error": "Google OAuth not configured"}, status=500)
            
        # Use the exact redirect URI that's configured in Google Cloud Console
        redirect_uri = "http://localhost:8000/accounts/google/login/callback/"
        auth_url = (
            f"{google_config.get('auth_uri', 'https://accounts.google.com/o/oauth2/auth')}"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope=email+profile"
        )
        
        logger.info(f"Redirecting to Google OAuth: {auth_url}")
        return HttpResponseRedirect(auth_url)
    except Exception as e:
        logger.error(f"Error initiating Google OAuth login: {e}")
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
def google_callback(request):
    """
    Custom Google OAuth callback handler
    Processes the OAuth callback and logs in the user
    """
    try:
        # Extract authorization code from request
        code = request.GET.get('code')
        if not code:
            logger.error("No authorization code in Google OAuth callback")
            return HttpResponseRedirect('/login/?error=no_auth_code')
            
        # Process the authorization code using our custom handler
        user = process_google_auth_code(request, code)
        
        # If login successful, redirect to home page
        if user and request.user.is_authenticated:
            logger.info(f"Google OAuth login successful for user {request.user.username}")
            return HttpResponseRedirect('/')
        else:
            logger.warning("Google OAuth login failed - user not authenticated after callback")
            return HttpResponseRedirect('/login/?error=auth_failed')
            
    except Exception as e:
        logger.error(f"Error handling Google OAuth callback: {e}")
        return HttpResponseRedirect(f'/login/?error={str(e)}')


@csrf_exempt
def google_oauth_callback(request):
    """
    Handler for the exact callback URL registered in Google Cloud Console.
    This route handles /accounts/google/login/callback/
    """
    try:
        # Extract authorization code from request
        code = request.GET.get('code')
        if not code:
            logger.error("No authorization code in Google OAuth callback")
            return HttpResponseRedirect('/login/?error=no_auth_code')
            
        # Process the authorization code using our custom handler
        user = process_google_auth_code(request, code)
        
        # If login successful, redirect to home page
        if user and request.user.is_authenticated:
            logger.info(f"Google OAuth login successful for user {request.user.username}")
            return HttpResponseRedirect('/')
        else:
            logger.warning("Google OAuth login failed - user not authenticated after callback")
            return HttpResponseRedirect('/login/?error=auth_failed')
            
    except Exception as e:
        logger.error(f"Error handling Google OAuth callback: {e}")
        return HttpResponseRedirect(f'/login/?error={str(e)}')

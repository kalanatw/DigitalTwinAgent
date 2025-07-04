"""
Social Authentication utilities for Digital Twin app.
This module integrates django-allauth with the existing authentication system.
"""
import logging
import json
import requests
from django.contrib.auth import login, authenticate
from django.utils import timezone
from django.contrib.auth.models import User
from .models import UserProfile

logger = logging.getLogger(__name__)

def process_social_login(request, sociallogin):
    """
    Process social login from django-allauth.
    This function is called when a user logs in via a social provider.
    It ensures the user profile exists and updates necessary information.
    
    Args:
        request: The HTTP request
        sociallogin: The SocialLogin object from django-allauth
    """
    user = sociallogin.user
    
    # Check if this is a new user
    is_new = getattr(user, 'pk', None) is None
    
    if is_new:
        # Set email to primary if not already set
        if not user.email and sociallogin.account.extra_data.get('email'):
            user.email = sociallogin.account.extra_data.get('email')
            
        # Set name fields if available
        if sociallogin.account.provider == 'google':
            if not user.first_name and sociallogin.account.extra_data.get('given_name'):
                user.first_name = sociallogin.account.extra_data.get('given_name')
            if not user.last_name and sociallogin.account.extra_data.get('family_name'):
                user.last_name = sociallogin.account.extra_data.get('family_name')
            
            # Set username if not already set or generate a unique one
            if not user.username:
                # Try email as username or create a unique one
                email_username = user.email.split('@')[0] if user.email else None
                if email_username and not User.objects.filter(username=email_username).exists():
                    user.username = email_username
                else:
                    # Create a unique username based on first name + last initial
                    base_username = f"{user.first_name.lower()}{user.last_name[0].lower() if user.last_name else ''}"
                    username = base_username
                    counter = 1
                    # Keep incrementing counter until we find a unique username
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1
                    user.username = username
        
        # Save user changes
        user.save()
        
        logger.info(f"New social login: {user.username} via {sociallogin.account.provider}")
    
    # Create or update user profile
    profile, created = UserProfile.objects.get_or_create(user=user)
    profile.last_login = timezone.now()
    profile.save()
    
    # Set session expiry (24 hours)
    request.session.set_expiry(86400)
    
    logger.info(f"User {user.username} logged in via {sociallogin.account.provider}")
    
    return True

def process_google_auth_code(request, auth_code):
    """
    Process a Google OAuth authorization code
    """
    from django.conf import settings
    google_config = settings.GOOGLE_OAUTH_CONFIG.get('web', {})
    client_id = google_config.get('client_id')
    client_secret = google_config.get('client_secret')
    token_uri = google_config.get('token_uri', 'https://oauth2.googleapis.com/token')
    
    # Exchange authorization code for tokens - use the exact same redirect URI as used in the initial request
    redirect_uri = "http://localhost:8000/accounts/google/login/callback/"
    
    # Make token exchange request
    response = requests.post(
        token_uri,
        data={
            'code': auth_code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code'
        }
    )
    
    if response.status_code != 200:
        logger.error(f"Token exchange failed: {response.text}")
        return None
        
    tokens = response.json()
    
    # Get user info from Google
    user_info_response = requests.get(
        'https://www.googleapis.com/oauth2/v3/userinfo',
        headers={'Authorization': f"Bearer {tokens.get('access_token')}"}
    )
    
    if user_info_response.status_code != 200:
        logger.error(f"Failed to get user info: {user_info_response.text}")
        return None
        
    user_info = user_info_response.json()
    
    # Get or create user
    try:
        user = User.objects.get(email=user_info.get('email'))
    except User.DoesNotExist:
        # Create new user
        user = User.objects.create_user(
            username=user_info.get('email').split('@')[0],
            email=user_info.get('email'),
            first_name=user_info.get('given_name', ''),
            last_name=user_info.get('family_name', '')
        )
    
    # Create or update user profile
    profile, created = UserProfile.objects.get_or_create(user=user)
    profile.last_login = timezone.now()
    profile.save()
    
    # Log in user
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)
    
    # Set session expiry (24 hours)
    request.session.set_expiry(86400)
    
    logger.info(f"User {user.username} logged in via Google OAuth")
    
    return user

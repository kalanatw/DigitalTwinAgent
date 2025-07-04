"""
Django AllAuth Adapters for Digital Twin App
This integrates django-allauth with our custom authentication flow.
"""
import logging
from django.urls import reverse
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .social_auth import process_social_login
from allauth.core.exceptions import ImmediateHttpResponse
from django.http import HttpResponseRedirect

logger = logging.getLogger(__name__)


class DigitalTwinAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter for Digital Twin App"""
    
    def is_open_for_signup(self, request):
        """
        Whether to allow sign ups. Can be used to restrict signup to specific conditions.
        """
        return True
        
    def get_login_redirect_url(self, request):
        """
        Override to redirect to our own login page
        """
        return "/"
        

class DigitalTwinSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter for Digital Twin App"""
    
    def is_open_for_signup(self, request, sociallogin):
        """
        Whether to allow social sign ups. Can be used to restrict social signup to specific conditions.
        """
        return True
    
    def pre_social_login(self, request, sociallogin):
        """
        Hook that can be used to intervene in the login process after the social account
        is verified but before the user is logged in.
        """
        # Check if we have an existing user with this email
        email = sociallogin.account.extra_data.get('email')
        if email:
            from django.contrib.auth.models import User
            try:
                user = User.objects.get(email=email)
                if not sociallogin.is_existing:
                    # Connect the social account to the existing user
                    sociallogin.connect(request, user)
                    logger.info(f"Connected Google account to existing user: {user.username}")
            except User.DoesNotExist:
                pass
                
        # Continue with normal flow
        return super().pre_social_login(request, sociallogin)
    
    def save_user(self, request, sociallogin, form=None):
        """
        Save the user and create a user profile
        """
        user = super().save_user(request, sociallogin, form)
        process_social_login(request, sociallogin)
        return user
        
    def get_connect_redirect_url(self, request, socialaccount):
        """
        Override to redirect to home page after connecting account
        """
        return "/"

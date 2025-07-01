"""
Authentication Middleware for Digital Twin Application
"""
import logging
from django.shortcuts import redirect
from django.http import JsonResponse
from django.contrib.auth import get_user
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class AuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware to enforce authentication for protected routes
    """
    
    # Routes that don't require authentication
    EXEMPT_PATHS = [
        '/login/',
        '/api/auth/login/',
        '/api/auth/signup/',
        '/api/auth/csrf-token/',
        '/api/auth/user/',
        '/admin/',
        '/static/',
        '/media/',
        '/favicon.ico',
    ]
    
    # API routes that should return JSON error for unauthenticated access
    API_PATHS = [
        '/api/',
    ]
    
    # Routes that require authentication (protected routes)
    PROTECTED_PATHS = [
        '/profile/',
        '/settings/',
        '/api/auth/profile/',
        '/api/auth/update-tokens/',
        '/api/chat/',
        '/api/email/',
        '/api/documents/',
        '/api/csv/',
        '/api/agents/',
    ]
    
    def process_request(self, request):
        """Process incoming request for authentication"""
        
        # Skip authentication check for exempt paths
        if any(request.path.startswith(path) for path in self.EXEMPT_PATHS):
            return None
        
        # Check if this is a protected route
        is_protected = any(request.path.startswith(path) for path in self.PROTECTED_PATHS)
        
        # Only enforce authentication for protected routes
        if not is_protected:
            return None
        
        # Check if user is authenticated
        user = get_user(request)
        if not user.is_authenticated:
            logger.warning(f"Unauthenticated access attempt to {request.path} from {request.META.get('REMOTE_ADDR')}")
            
            # Return JSON response for API calls
            if any(request.path.startswith(path) for path in self.API_PATHS):
                return JsonResponse({
                    'error': 'Authentication required',
                    'message': 'Please log in to access this resource',
                    'redirect': '/login/'
                }, status=401)
            
            # Redirect to login page for web interface
            return redirect('/login/')
        
        return None


class TokenTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to track token usage for authenticated users
    """
    
    def process_response(self, request, response):
        """Track token usage from API responses"""
        
        # Only track for authenticated users and successful API calls
        if (hasattr(request, 'user') and 
            request.user.is_authenticated and 
            request.path.startswith('/api/') and
            response.status_code == 200):
            
            try:
                # Check if response contains token usage information
                if hasattr(response, 'token_usage'):
                    input_tokens = getattr(response, 'input_tokens', 0)
                    output_tokens = getattr(response, 'output_tokens', 0)
                    
                    if input_tokens > 0 or output_tokens > 0:
                        # Update user profile with token usage
                        if hasattr(request.user, 'profile'):
                            request.user.profile.add_token_usage(input_tokens, output_tokens)
                            logger.debug(f"Tracked {input_tokens + output_tokens} tokens for user {request.user.username}")
                        
            except Exception as e:
                logger.error(f"Error tracking token usage for user {request.user.username}: {str(e)}")
        
        return response


class SessionTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to track user sessions and activity
    """
    
    def process_request(self, request):
        """Track user activity and update last login"""
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            try:
                # Update user profile last login time
                if hasattr(request.user, 'profile'):
                    from django.utils import timezone
                    request.user.profile.last_login = timezone.now()
                    request.user.profile.save(update_fields=['last_login'])
                    
            except Exception as e:
                logger.error(f"Error updating session tracking for user {request.user.username}: {str(e)}")
        
        return None

"""
Resource Access Middleware for user-centric resources
"""
import logging
import json
from django.http import JsonResponse
from django.urls import resolve
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


class ResourceAccessMiddleware:
    """
    Middleware to enforce user-centric resource access controls.
    This handles all API endpoints that accept resource IDs to ensure
    the user has proper access to the requested resource.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # URL patterns that need access checking
        self.resource_patterns = {
            # Document patterns
            'document_detail': {'param': 'document_id', 'model': 'Document'},
            'document_search': {'check_body': True, 'param': 'document_ids', 'model': 'Document'},
            
            # Twin version patterns
            'twin_version_detail': {'param': 'twin_version_id', 'model': 'TwinVersion'},
            
            # Agent patterns
            'agent_detail': {'param': 'agent_id', 'model': 'AgentConfiguration'},
            'agent_activate': {'param': 'agent_id', 'model': 'AgentConfiguration'},
            'agent_test': {'param': 'agent_id', 'model': 'AgentConfiguration'},
            'system_agent_activate': {'param': 'agent_id', 'model': 'AgentConfiguration'},
        }
        
    def __call__(self, request):
        # Only check API requests
        if not request.path.startswith('/api/'):
            return self.get_response(request)
        
        # Only check authenticated requests
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        try:
            # Resolve the URL to get the view name
            url_match = resolve(request.path)
            view_name = url_match.url_name
            
            # Check if this view needs resource access checking
            if view_name in self.resource_patterns:
                pattern = self.resource_patterns[view_name]
                
                # Get resource ID from URL kwargs
                resource_id = url_match.kwargs.get(pattern['param'])
                
                # Get resource IDs from request body if specified
                if pattern.get('check_body') and request.method in ('POST', 'PUT', 'PATCH'):
                    try:
                        body_data = json.loads(request.body)
                        if pattern['param'] in body_data:
                            resource_id = body_data[pattern['param']]
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                
                # If we have a resource ID, check access
                if resource_id:
                    has_access = self._check_resource_access(
                        request.user, pattern['model'], resource_id
                    )
                    
                    if not has_access:
                        logger.warning(
                            f"Access denied: User {request.user.username} attempted to access "
                            f"{pattern['model']} {resource_id}"
                        )
                        return JsonResponse(
                            {'error': 'You do not have access to this resource'}, 
                            status=403
                        )
        
        except Exception as e:
            # Log but don't block the request if our middleware fails
            logger.error(f"Error in ResourceAccessMiddleware: {str(e)}")
        
        # Continue processing the request
        return self.get_response(request)
    
    def _check_resource_access(self, user, model_name, resource_id):
        """
        Check if user has access to the specified resource
        
        Args:
            user: The user making the request
            model_name: The name of the resource model
            resource_id: The ID of the resource
            
        Returns:
            bool: True if the user has access, False otherwise
        """
        try:
            # Import models here to avoid circular imports
            from .models import Document, TwinVersion, AgentConfiguration
            
            if model_name == 'Document':
                try:
                    doc = Document.objects.get(id=resource_id)
                    
                    # Owner always has access
                    if doc.user == user:
                        return True
                    
                    # Check if document is shared
                    if doc.is_shared:
                        return True
                    
                    # Check if document is explicitly shared with user
                    if doc.shares.filter(shared_with=user).exists():
                        return True
                    
                    # Check if twin version is shared
                    if doc.twin_version.is_shared:
                        return True
                    
                    # Check if twin version is explicitly shared with user
                    if doc.twin_version.shares.filter(shared_with=user).exists():
                        return True
                    
                    # No access
                    return False
                    
                except Document.DoesNotExist:
                    # If document doesn't exist, let the view handle it
                    return True
                    
            elif model_name == 'TwinVersion':
                try:
                    tv = TwinVersion.objects.get(id=resource_id)
                    
                    # Owner always has access
                    if tv.user == user:
                        return True
                    
                    # Check if twin version is shared
                    if tv.is_shared:
                        return True
                    
                    # Check if twin version is explicitly shared with user
                    if tv.shares.filter(shared_with=user).exists():
                        return True
                    
                    # No access
                    return False
                    
                except TwinVersion.DoesNotExist:
                    # If twin version doesn't exist, let the view handle it
                    return True
                    
            elif model_name == 'AgentConfiguration':
                try:
                    agent = AgentConfiguration.objects.get(id=resource_id)
                    
                    # Owner always has access
                    if agent.user == user:
                        return True
                    
                    # Check if agent is shared
                    if agent.is_shared:
                        return True
                    
                    # Check if agent is explicitly shared with user
                    if agent.shares.filter(shared_with=user).exists():
                        return True
                    
                    # No access
                    return False
                    
                except AgentConfiguration.DoesNotExist:
                    # If agent doesn't exist, let the view handle it
                    return True
            
            # Unknown model type, default to no access
            logger.warning(f"Unknown model type in access check: {model_name}")
            return False
            
        except Exception as e:
            # Log error but default to allowing access
            # (let the view handle more specific permission checks)
            logger.error(f"Error checking resource access: {str(e)}")
            return True

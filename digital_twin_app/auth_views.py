"""
Auth-protected views for Digital Twin
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.urls import reverse_lazy

class AuthRequiredTemplateView(LoginRequiredMixin, TemplateView):
    """
    Template view that requires authentication.
    Redirects to login page if user is not authenticated.
    """
    login_url = '/login/'
    redirect_field_name = 'next'
    
class HomeView(AuthRequiredTemplateView):
    """Home page view that requires authentication"""
    template_name = 'chat.html'

class ProfileView(AuthRequiredTemplateView):
    """Profile page view that requires authentication"""
    template_name = 'profile.html'

class SettingsView(AuthRequiredTemplateView):
    """Settings page view that requires authentication"""
    template_name = 'settings.html'

class DocumentView(AuthRequiredTemplateView):
    """Documents page view that requires authentication"""
    template_name = 'dms.html'
    
class EmailView(AuthRequiredTemplateView):
    """Email management page view that requires authentication"""
    template_name = 'email_management.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Check if user has Gmail connection
        has_connection = False
        connected_email = ''
        
        try:
            from .models import UserGmailConnection
            gmail_connection = UserGmailConnection.objects.get(
                user=self.request.user,
                is_active=True
            )
            has_connection = True
            connected_email = gmail_connection.email_address
        except UserGmailConnection.DoesNotExist:
            pass
        
        # Get active agent information
        active_agent = None
        agent_name = 'No Agent Active'
        twin_version_name = None
        
        try:
            from .models import AgentConfiguration
            active_agent = AgentConfiguration.objects.filter(
                user=self.request.user,
                is_active=True
            ).first()
            
            if active_agent:
                agent_name = active_agent.name
                # Get current twin version if available
                if hasattr(active_agent, 'twin_version') and active_agent.twin_version:
                    twin_version_name = active_agent.twin_version.name
                elif hasattr(active_agent, 'current_twin_version'):
                    twin_version_name = getattr(active_agent.current_twin_version, 'name', 'Default')
                else:
                    twin_version_name = 'Default'
        except Exception as e:
            # Log the error but don't break the page
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Error getting active agent: {e}")
        
        context.update({
            'has_gmail_connection': has_connection,
            'connected_email': connected_email,
            'active_agent': active_agent,
            'agent_id': active_agent.id if active_agent else '',
            'agent_name': agent_name,
            'twin_version_name': twin_version_name,
        })
        
        return context
    
class CSVView(AuthRequiredTemplateView):
    """CSV manager page view that requires authentication"""
    template_name = 'csv_manager.html'

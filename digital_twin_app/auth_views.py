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
        
        context.update({
            'has_gmail_connection': has_connection,
            'connected_email': connected_email,
        })
        
        return context
    
class CSVView(AuthRequiredTemplateView):
    """CSV manager page view that requires authentication"""
    template_name = 'csv_manager.html'

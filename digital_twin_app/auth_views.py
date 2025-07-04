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
    """Email automation page view that requires authentication"""
    template_name = 'email_automation.html'
    
class CSVView(AuthRequiredTemplateView):
    """CSV manager page view that requires authentication"""
    template_name = 'csv_manager.html'

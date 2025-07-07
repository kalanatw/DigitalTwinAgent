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

class ArchitectureView(AuthRequiredTemplateView):
    """Interactive architecture visualization page"""
    template_name = 'architecture.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Architecture components data
        context.update({
            'frontend_components': [
                {
                    'id': 'browser',
                    'name': 'Web Browser',
                    'icon': '🌐',
                    'description': 'User interface layer with modern web standards',
                    'technologies': ['HTML5', 'CSS3', 'JavaScript ES6+'],
                    'details': 'Responsive design supporting desktop and mobile devices'
                },
                {
                    'id': 'alpine',
                    'name': 'AlpineJS State Management',
                    'icon': '⚡',
                    'description': 'Reactive state management for email interface',
                    'technologies': ['AlpineJS', 'Event System', 'Reactive Data'],
                    'code_example': """function emailManagementApp() {
    return {
        activeAgent: { id: '', name: '' },
        selectedEmail: null,
        showEmailModal: false
    }
}"""
                },
                {
                    'id': 'components',
                    'name': 'Email Components',
                    'icon': '📧',
                    'description': 'Modular UI components for email management',
                    'technologies': ['Django Templates', 'Component Architecture'],
                    'files': ['email_modal.html', 'email_list.html', 'agent_selector.html']
                }
            ],
            'backend_components': [
                {
                    'id': 'django-views',
                    'name': 'Django Views & Controllers',
                    'icon': '🛣️',
                    'description': 'Request handling and business logic coordination',
                    'technologies': ['Django Views', 'Class-Based Views', 'Mixins'],
                    'code_example': """class EmailView(AuthRequiredTemplateView):
    template_name = 'email_management.html'
    
    def get_context_data(self, **kwargs):
        # Get Gmail connection status
        # Get active agent configuration
        # Return context for template"""
                },
                {
                    'id': 'agent-management',
                    'name': 'Agent Management System',
                    'icon': '🤖',
                    'description': 'Runtime agent configuration and activation',
                    'technologies': ['Django ORM', 'Database Transactions', 'Caching'],
                    'features': ['Runtime Switching', 'Multi-tenant', 'Configuration Storage']
                },
                {
                    'id': 'gmail-integration',
                    'name': 'Gmail API Integration',
                    'icon': '📬',
                    'description': 'OAuth 2.0 and Gmail API communication',
                    'technologies': ['OAuth 2.0', 'Gmail API', 'Token Management'],
                    'scopes': ['https://mail.google.com/']
                }
            ],
            'data_components': [
                {
                    'id': 'postgresql',
                    'name': 'PostgreSQL Database',
                    'icon': '🗄️',
                    'description': 'Primary data storage with ACID compliance',
                    'technologies': ['PostgreSQL', 'Django ORM', 'Migrations'],
                    'models': ['User', 'AgentConfiguration', 'UserGmailConnection', 'TwinVersion']
                },
                {
                    'id': 'redis',
                    'name': 'Redis Cache',
                    'icon': '⚡',
                    'description': 'High-performance caching and session storage',
                    'technologies': ['Redis', 'Django Cache Framework', 'Session Storage'],
                    'use_cases': ['Agent State', 'Session Data', 'API Rate Limiting']
                }
            ],
            'external_components': [
                {
                    'id': 'gmail-api',
                    'name': 'Gmail API',
                    'icon': '🔵',
                    'description': 'Google Gmail API for email operations',
                    'technologies': ['REST API', 'OAuth 2.0', 'JSON'],
                    'capabilities': ['Read Emails', 'Send Emails', 'Search', 'Labels']
                },
                {
                    'id': 'openai',
                    'name': 'OpenAI API',
                    'icon': '🧠',
                    'description': 'AI processing for intelligent email responses',
                    'technologies': ['GPT Models', 'REST API', 'Streaming'],
                    'models': ['GPT-4', 'GPT-3.5-turbo']
                }
            ],
            'data_flows': [
                {
                    'id': 'agent-activation',
                    'name': 'Agent Activation Flow',
                    'steps': [
                        'User clicks Switch Agent',
                        'AlpineJS sends AJAX request', 
                        'Django processes activation',
                        'Database updates atomically',
                        'Cache invalidation',
                        'UI updates with new agent'
                    ],
                    'components': ['alpine', 'django-views', 'agent-management', 'postgresql']
                },
                {
                    'id': 'email-reply',
                    'name': 'AI Email Reply Generation',
                    'steps': [
                        'User selects email',
                        'Modal opens with email details',
                        'User clicks Generate Reply',
                        'Active agent retrieved',
                        'AI processing with context',
                        'Reply generated and displayed'
                    ],
                    'components': ['components', 'agent-management', 'openai', 'gmail-api']
                }
            ]
        })
        
        return context

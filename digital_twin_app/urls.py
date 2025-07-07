"""
URL Configuration for Digital Twin App
"""
from django.urls import path, include
from django.views.generic import TemplateView
from . import views
from . import document_views
from . import user_centric_document_views
from . import integrated_email_views
from . import agent_settings_views
from . import csv_views
from . import google_auth_views
from . import auth_views
from . import profile_views
from . import chat_session_views
from . import gmail_views

urlpatterns = [
    # API endpoints first (more specific)
    path('api/chat/', views.ApiChatView.as_view(), name='api_chat'),
    path('api/drf-chat/', views.drf_chat_view, name='drf_chat'),
    
    # User-Centric Chat Session Management API endpoints  
    path('api/chat/sessions/', chat_session_views.ChatSessionListView.as_view(), name='chat_session_list'),
    path('api/chat/sessions/<str:session_id>/', chat_session_views.ChatSessionDetailView.as_view(), name='chat_session_detail'),
    path('api/chat/sessions/<str:session_id>/messages/', chat_session_views.add_message_to_session, name='chat_session_add_message'),
    path('api/chat/sessions/<str:session_id>/auto-name/', chat_session_views.auto_name_session, name='chat_session_auto_name'),
    path('api/chat/search/', chat_session_views.search_chat_sessions, name='chat_session_search'),
    path('api/chat/statistics/', chat_session_views.get_chat_statistics, name='chat_statistics'),
    
    # Authentication endpoints
    path('api/auth/login/', agent_settings_views.login_view, name='login'),
    path('api/auth/logout/', agent_settings_views.logout_view, name='logout'),
    path('api/auth/user/', agent_settings_views.user_info, name='user_info'),
    path('api/auth/csrf-token/', agent_settings_views.get_csrf_token, name='csrf_token'),
    path('api/auth/profile/', agent_settings_views.user_profile, name='user_profile'),
    path('api/auth/signup/', agent_settings_views.signup_view, name='signup'),
    path('api/auth/update-tokens/', agent_settings_views.update_token_usage, name='update_token_usage'),
    
    # Google OAuth endpoints
    path('api/auth/google/login/', google_auth_views.google_login, name='google_login'),
    path('api/auth/google/callback/', google_auth_views.google_callback, name='google_callback'),
    path('accounts/google/login/callback/', google_auth_views.google_callback, name='google_oauth_callback'),
    
    # Chat History endpoints
    path('api/chat/history/<str:session_id>/', agent_settings_views.get_chat_history, name='get_chat_history'),
    path('api/chat/message/<str:session_id>/', agent_settings_views.save_chat_message, name='save_chat_message'),
    path('api/chat/clear/<str:session_id>/', agent_settings_views.clear_chat_history, name='clear_chat_history'),
    
    # Email Integration endpoints
    path('api/email/oauth/', integrated_email_views.get_oauth_url, name='email_oauth'),
    path('api/email/oauth/url/', integrated_email_views.get_oauth_url, name='email_oauth_url'),
    path('api/email/oauth/callback/', integrated_email_views.oauth_callback, name='email_oauth_callback'),
    path('api/email/setup/', integrated_email_views.setup_email_integration, name='email_setup'),
    path('api/email/check/', integrated_email_views.check_and_process_emails, name='email_check'),
    path('api/email/status/', integrated_email_views.get_email_status, name='email_status'),
    path('api/email/toggle/', integrated_email_views.toggle_auto_reply, name='email_toggle'),
    path('api/email/add-sender/', integrated_email_views.add_validated_sender, name='email_add_sender'),
    path('api/email/thread/', integrated_email_views.get_email_thread, name='email_thread'),
    path('api/email/messages/', integrated_email_views.get_email_messages, name='email_messages'),
    path('api/email/clear-tokens/', integrated_email_views.clear_gmail_tokens, name='email_clear_tokens'),
    path('api/email/send-response/<int:email_id>/', integrated_email_views.send_email_response, name='email_send_response'),
    path('api/email/update-response/<int:email_id>/', integrated_email_views.update_email_response, name='email_update_response'),
    path('api/email/generate-response/<int:email_id>/', integrated_email_views.generate_email_response, name='email_generate_response'),
    # Gmail-specific endpoints (with string IDs)
    path('api/email/send-response/<str:email_id>/', integrated_email_views.send_email_response, name='gmail_send_response'),
    path('api/email/update-response/<str:email_id>/', integrated_email_views.update_email_response, name='gmail_update_response'),
    path('api/email/generate-response/<str:email_id>/', integrated_email_views.generate_email_response, name='gmail_generate_response'),
    path('api/email/create-test-emails/', integrated_email_views.create_test_emails, name='email_create_test'),
    
    # Gmail OAuth and API endpoints (following Gmail API standards)
    path('email/connect/', gmail_views.gmail_connect, name='gmail_connect'),
    path('email/callback/', gmail_views.gmail_callback, name='gmail_callback'),
    path('email/disconnect/', gmail_views.gmail_disconnect, name='gmail_disconnect'),
    path('email/reauthorize/', gmail_views.gmail_reauthorize, name='gmail_reauthorize'),
    path('api/gmail/status/', gmail_views.gmail_connection_status, name='gmail_status'),
    path('api/gmail/emails/', gmail_views.gmail_list_emails, name='gmail_list_emails'),
    path('api/gmail/send/', gmail_views.send_email_api, name='gmail_send_email'),
    path('api/gmail/check-scope/', gmail_views.gmail_check_scope_error, name='gmail_check_scope'),
    
    # Email reply generation API endpoints
    path('api/email/generate-reply/', gmail_views.generate_email_reply_api, name='generate_email_reply'),
    path('api/agents/active/', gmail_views.get_active_agent_api, name='get_active_agent'),
    path('api/agents/list/', gmail_views.list_user_agents_api, name='list_user_agents'),
    path('api/twins/versions/', gmail_views.list_twin_versions_api, name='list_twin_versions'),
    
    # Twin Version API endpoints (User-Centric)
    path('api/twin-versions/', user_centric_document_views.twin_version_list_view, name='twin_version_list'),
    path('api/twin-versions/<uuid:version_id>/', user_centric_document_views.twin_version_detail_view, name='twin_version_detail'),
    path('api/twin-versions/<uuid:version_id>/share/', user_centric_document_views.TwinVersionShareView.as_view(), name='twin_version_share'),
    
    # Document API endpoints (User-Centric)
    path('api/documents/', user_centric_document_views.document_list_view, name='document_list'),
    path('api/documents/upload/', user_centric_document_views.DocumentUploadView.as_view(), name='document_upload'),
    path('api/documents/<uuid:document_id>/', user_centric_document_views.DocumentDetailView.as_view(), name='document_detail'),
    path('api/documents/search/', user_centric_document_views.DocumentSearchView.as_view(), name='document_search'),
    path('api/documents/<uuid:document_id>/share/', user_centric_document_views.DocumentShareView.as_view(), name='document_share'),
    
    # CSV Document API endpoints
    path('api/csv/upload/', csv_views.upload_csv_file, name='csv_upload'),
    path('api/csv/documents/', csv_views.list_csv_documents, name='csv_document_list'),
    path('api/csv/documents/<uuid:document_id>/', csv_views.get_csv_document, name='csv_document_detail'),
    path('api/csv/documents/<uuid:document_id>/query/', csv_views.query_csv_document, name='csv_document_query'),
    
    # Session management endpoints
    path('api/sessions/<str:session_id>/history/', views.SessionHistoryView.as_view(), name='session_history'),
    path('api/sessions/<str:session_id>/', views.SessionClearView.as_view(), name='session_clear'),
    
    # Agent Settings API endpoints
    path('api/agents/', agent_settings_views.agent_configurations, name='agent_list'),
    path('api/agents/<int:agent_id>/', agent_settings_views.agent_configuration_detail, name='agent_detail'),
    path('api/agents/<int:agent_id>/activate/', agent_settings_views.activate_agent, name='agent_activate'),
    path('api/agents/<str:agent_id>/activate/', agent_settings_views.activate_agent, name='system_agent_activate'),
    path('api/agents/<int:agent_id>/test/', agent_settings_views.test_agent, name='agent_test'),
    path('api/agents/import/', agent_settings_views.import_agents, name='agent_import'),
    path('api/agents/export/', agent_settings_views.export_agents, name='agent_export'),
    path('api/agents/templates/', agent_settings_views.agent_templates, name='agent_template_list'),
    path('api/agents/sessions/', agent_settings_views.agent_sessions, name='agent_session_list'),
    path('api/agents/current/', agent_settings_views.current_agent, name='current_agent'),
    path('api/agents/system/', agent_settings_views.system_agents, name='system_agent_list'),
    path('api/agents/tools/', agent_settings_views.available_tools, name='available_tools'),
    path('api/agents/enhance-prompt/', agent_settings_views.enhance_prompt, name='enhance_prompt'),
    path('api/agents/create-instance/', agent_settings_views.create_agent_instance, name='create_agent_instance'),
    
    # User Profile endpoints
    path('api/profile/', profile_views.profile_view, name='profile_view'),
    path('api/profile/token-usage/', profile_views.api_token_usage, name='api_token_usage'),
    path('api/profile/enhanced-token-stats/', profile_views.api_enhanced_token_stats, name='api_enhanced_token_stats'),
    path('api/profile/resources/', profile_views.api_user_resources, name='api_user_resources'),
    path('api/profile/shared-resources/', profile_views.api_shared_resources, name='api_shared_resources'),
    
    # Main template views
    path('', auth_views.HomeView.as_view(), name='home'),
    path('login/', TemplateView.as_view(template_name='login.html'), name='login_page'),
    path('profile/', profile_views.profile_view, name='profile_page'),
    path('profile/resources/', profile_views.profile_resources_view, name='profile_resources_page'),
    path('about/', auth_views.AuthRequiredTemplateView.as_view(template_name='about.html'), name='about'),
    path('architecture/', auth_views.ArchitectureView.as_view(), name='architecture'),
    path('settings/', auth_views.SettingsView.as_view(), name='settings'),
    path('dms/', auth_views.DocumentView.as_view(), name='dms'),
    path('email/', auth_views.EmailView.as_view(), name='email_automation'),
    path('csv/', auth_views.CSVView.as_view(), name='csv_manager'),
]

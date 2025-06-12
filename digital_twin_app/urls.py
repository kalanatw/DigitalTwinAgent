"""
URL Configuration for Digital Twin App
"""
from django.urls import path, include
from django.views.generic import TemplateView
from . import views
from . import document_views
from . import integrated_email_views

urlpatterns = [
    # API endpoints first (more specific)
    path('api/chat/', views.ApiChatView.as_view(), name='api_chat'),
    path('api/drf-chat/', views.drf_chat_view, name='drf_chat'),
    
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
    
    # Twin Version API endpoints
    path('api/twin-versions/', document_views.TwinVersionListView.as_view(), name='twin_version_list'),
    path('api/twin-versions/<uuid:version_id>/', document_views.TwinVersionDetailView.as_view(), name='twin_version_detail'),
    
    # Document API endpoints
    path('api/documents/', document_views.DocumentListView.as_view(), name='document_list'),
    path('api/documents/upload/', document_views.DocumentUploadView.as_view(), name='document_upload'),
    path('api/documents/<uuid:document_id>/', document_views.DocumentDetailView.as_view(), name='document_detail'),
    path('api/documents/search/', document_views.DocumentSearchView.as_view(), name='document_search'),
    
    # Session management endpoints
    path('api/sessions/<str:session_id>/history/', views.SessionHistoryView.as_view(), name='session_history'),
    path('api/sessions/<str:session_id>/', views.SessionClearView.as_view(), name='session_clear'),
    
    # Main pages (less specific patterns)
    path('', views.ChatView.as_view(), name='chat_home'),
    path('chat/', views.ChatView.as_view(), name='chat_interface'),
    path('email/', integrated_email_views.email_automation_page, name='email_automation'),
    
    # Document Management System
    path('dms/', document_views.DMSView.as_view(), name='dms'),
    
    # Static pages
    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),
]

"""
URL Configuration for Digital Twin App
"""
from django.urls import path, include
from django.views.generic import TemplateView
from . import views
from . import document_views

urlpatterns = [
    # API endpoints first (more specific)
    path('api/chat/', views.ApiChatView.as_view(), name='api_chat'),
    path('api/drf-chat/', views.drf_chat_view, name='drf_chat'),
    
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
    
    # Document Management System
    path('dms/', document_views.DMSView.as_view(), name='dms'),
    
    # Static pages
    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),
]

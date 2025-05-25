"""
URL Configuration for Digital Twin App
"""
from django.urls import path, include
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    # Main chat interface
    path('', views.ChatView.as_view(), name='chat_home'),
    path('chat/', views.ChatView.as_view(), name='chat_interface'),
    
    # API endpoints
    path('api/chat/', views.ApiChatView.as_view(), name='api_chat'),
    path('api/drf-chat/', views.drf_chat_view, name='drf_chat'),
    
    # Session management endpoints
    path('api/sessions/<str:session_id>/history/', views.SessionHistoryView.as_view(), name='session_history'),
    path('api/sessions/<str:session_id>/', views.SessionClearView.as_view(), name='session_clear'),
    
    # Static pages
    path('about/', TemplateView.as_view(template_name='about.html'), name='about'),
]

"""
URL configuration for digital_twin project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from digital_twin_app.google_auth_views import google_oauth_callback

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Custom handler for Google OAuth callback
    path('accounts/google/login/callback/', google_oauth_callback, name='google_oauth_callback'),
    
    # Django AllAuth URLs - our custom handler above takes precedence
    path('accounts/', include('allauth.urls')),  # Django AllAuth URLs
    
    path('', include('digital_twin_app.urls')),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

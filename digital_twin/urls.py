"""
URL configuration for digital_twin project.
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('digital_twin_app.urls')),
    path('', include('digital_twin_app.urls')),
]

"""
ASGI config for digital_twin project.
"""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_twin.settings')

application = get_asgi_application()

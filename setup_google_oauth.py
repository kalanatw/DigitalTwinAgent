#!/usr/bin/env python
"""
Script to configure the Google OAuth app in the database

This script:
1. Sets up the Django Site framework with the correct domain
2. Configures the Google OAuth application with credentials from google_oauth_config.json
3. Associates the Google OAuth app with the site

Usage:
  python setup_google_oauth.py
"""
import os
import sys
import json
import django
from pathlib import Path

# Add the project path to sys.path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_twin.settings')
django.setup()

# Now we can import Django models
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp

# Load Google OAuth config
GOOGLE_CONFIG_PATH = os.path.join(BASE_DIR, 'google_oauth_config.json')
try:
    with open(GOOGLE_CONFIG_PATH, 'r') as f:
        GOOGLE_CONFIG = json.load(f)
        
    # Get client_id and secret from config
    client_id = GOOGLE_CONFIG.get('web', {}).get('client_id', '')
    client_secret = GOOGLE_CONFIG.get('web', {}).get('client_secret', '')
    
    if not client_id or not client_secret:
        print("Error: Missing client_id or client_secret in google_oauth_config.json")
        sys.exit(1)
        
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Error loading Google OAuth config: {e}")
    sys.exit(1)

# Check existing Google SocialApp entries
print("Configuring Google OAuth...")
existing_apps = SocialApp.objects.filter(provider='google')

# Get the site
try:
    site = Site.objects.get(id=1)
except Site.DoesNotExist:
    # Create the site if it doesn't exist
    site = Site.objects.create(id=1, domain='localhost:8000', name='Digital Twin')
    print(f"Created site: {site.domain}")

# Only one Google OAuth app should exist
if existing_apps.count() > 1:
    print(f"Found {existing_apps.count()} Google OAuth apps. Cleaning up...")
    # Keep only the first one and delete the rest
    first_app = existing_apps.first()
    SocialApp.objects.filter(provider='google').exclude(id=first_app.id).delete()
    google_app = first_app
    print("Kept one Google OAuth app and deleted duplicates.")
elif existing_apps.count() == 1:
    google_app = existing_apps.first()
    print("Found existing Google OAuth app. Updating credentials...")
else:
    print("Creating new Google OAuth app...")
    google_app = SocialApp.objects.create(
        provider='google',
        name='Google OAuth',
        client_id='',
        secret=''
    )

# Update credentials
google_app.name = 'Google OAuth'
google_app.client_id = client_id
google_app.secret = client_secret
google_app.save()

# Associate with site
google_app.sites.add(site)
print(f"Created and configured Google OAuth app: {google_app.name}")

# Verify setup
print("\nVerification:")
print(f"Site: {site.domain} (ID: {site.id})")
app = SocialApp.objects.get(provider='google')
sites = ", ".join([s.domain for s in app.sites.all()])
print(f"Google App: {app.name} (Client ID: {app.client_id[:10]}...{app.client_id[-4:]})")
print(f"Associated Sites: {sites}")
print("\nGoogle OAuth setup completed successfully!")

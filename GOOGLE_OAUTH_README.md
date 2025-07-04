# Google OAuth Integration Guide

This guide explains how Google OAuth has been integrated with the Digital Twin application.

## Architecture

The integration follows these principles:

1. **Seamless Authentication** - Users can log in with either username/password or Google OAuth
2. **Single Sign-On Experience** - One login page with both authentication options
3. **Profile Integration** - OAuth logins are integrated with the existing UserProfile system
4. **Security** - Authentication required for all application pages except login and about

## Setup Instructions

1. **Install Requirements**

   ```bash
   pip install -r requirements.txt
   ```

2. **Run Migrations**

   ```bash
   python manage.py migrate
   ```

3. **Configure Google OAuth**

   ```bash
   python setup_google_oauth.py
   ```

   ```bash
   python manage.py migrate
   ```

   This will:
   - Install required packages
   - Run migrations
   - Configure the Site model
   - Setup the Google OAuth SocialApp
   - Start the development server

2. **Test the Integration**

   - Visit `http://localhost:8000/login/`
   - Click "Continue with Google"
   - Complete the Google authentication flow
   - You should be redirected to the home page (`/`)

## URL Structure

- `/login/` - Main login page with both options
- `/api/auth/google/login/` - Initiates Google OAuth flow
- `/accounts/google/login/callback/` - Google OAuth callback endpoint (registered in Google Cloud Console)
- `/api/auth/logout/` - Logout endpoint (works for both standard and OAuth logins)

## Configuration

The Google OAuth client is configured in `google_oauth_config.json`. This file should contain:

```json
{
  "web": {
    "client_id": "YOUR_CLIENT_ID",
    "project_id": "YOUR_PROJECT_ID",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_secret": "YOUR_CLIENT_SECRET",
    "redirect_uris": ["http://localhost:8000/accounts/google/login/callback/"],
    "javascript_origins": ["http://localhost:8000"]
  }
}
```

## Files Modified

1. `digital_twin_app/google_auth_views.py` - Custom Google OAuth views
2. `digital_twin_app/urls.py` - Added Google OAuth endpoints
3. `digital_twin_app/social_auth.py` - Handles OAuth integration with UserProfile
4. `digital_twin_app/adapters.py` - Custom django-allauth adapters
5. `templates/login.html` - Updated Google login button URL
6. `google_oauth_config.json` - Updated callback URL
7. `requirements.txt` - Added required packages

## How It Works

1. **Custom OAuth Flow** - We use django-allauth internally but with our own URL structure and flow
2. **Account Linking** - If a user with the same email exists, the Google account is connected to it
3. **Profile Integration** - OAuth logins update the UserProfile model just like standard logins
4. **Session Management** - Uses the same session management as regular authentication

## Security Considerations

- Client secrets are stored in the `google_oauth_config.json` file (for production, use environment variables)
- HTTPS should be enabled in production
- The redirect URI in Google Cloud Console must match exactly: `http://localhost:8000/accounts/google/login/callback/`

## Troubleshooting

If you encounter issues:

1. Check the application logs: `digital_twin.log`
2. Verify the Site model has the correct domain: 
   ```
   python manage.py shell -c "from django.contrib.sites.models import Site; print(Site.objects.all())"
   ```
3. Verify Google SocialApp is correctly configured: 
   ```
   python manage.py shell -c "from allauth.socialaccount.models import SocialApp; print(SocialApp.objects.all())"
   ```
4. Run `python setup_google_oauth.py` to reset the Google OAuth configuration

## Additional Resources

- [Django AllAuth Documentation](https://django-allauth.readthedocs.io/)
- [Google OAuth Documentation](https://developers.google.com/identity/protocols/oauth2)

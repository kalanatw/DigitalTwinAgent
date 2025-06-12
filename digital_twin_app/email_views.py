"""
Minimal Email Views for automation
"""
import json
import asyncio
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from .models import EmailAccount, EmailMessage
from .email_service import EmailService, encrypt_password

@csrf_exempt
@require_http_methods(["POST"])
def login_user(request):
    """Simple login endpoint"""
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return JsonResponse({"success": True, "message": "Login successful"})
        else:
            return JsonResponse({"success": False, "error": "Invalid credentials"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required
def email_automation_page(request):
    """Email automation frontend page"""
    context = {
        'user': request.user,
        'has_email_account': hasattr(request.user, 'email_account'),
        'email_account': getattr(request.user, 'email_account', None),
        'recent_emails': [],
        'email_providers': EmailService.PROVIDERS
    }
    
    if hasattr(request.user, 'email_account'):
        context['recent_emails'] = EmailMessage.objects.filter(
            account=request.user.email_account
        ).order_by('-received_at')[:10]
    
    return render(request, 'email_automation.html', context)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def setup_email_account(request):
    """Setup user's email account with provider auto-detection"""
    try:
        data = json.loads(request.body)
        
        email_address = data.get('email_address')
        password = data.get('password')
        auto_reply = data.get('auto_reply_enabled', False)
        
        # Auto-detect provider settings
        provider_settings = EmailService.get_provider_settings(email_address)
        
        # Create or update email account
        account, created = EmailAccount.objects.get_or_create(
            user=request.user,
            defaults={
                'email_address': email_address,
                'password': encrypt_password(password),
                'auto_reply_enabled': auto_reply,
                'imap_server': provider_settings['imap_server'],
                'imap_port': provider_settings['imap_port'],
                'smtp_server': provider_settings['smtp_server'],
                'smtp_port': provider_settings['smtp_port']
            }
        )
        
        if not created:
            account.email_address = email_address
            account.password = encrypt_password(password)
            account.auto_reply_enabled = auto_reply
            account.imap_server = provider_settings['imap_server']
            account.imap_port = provider_settings['imap_port']
            account.smtp_server = provider_settings['smtp_server']
            account.smtp_port = provider_settings['smtp_port']
            account.save()
        
        # Test connection
        service = EmailService(account)
        test_result = service.test_connection()
        
        if test_result['success']:
            return JsonResponse({
                "success": True,
                "message": f"✅ Email account configured successfully! Using {provider_settings['display_name']} settings."
            })
        else:
            # Delete account if connection fails
            account.delete()
            return JsonResponse({
                "success": False,
                "error": test_result['message'],
                "error_type": test_result.get('error_type', 'unknown')
            })
            
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def check_emails(request):
    """Manually check for new emails"""
    try:
        if not hasattr(request.user, 'email_account'):
            return JsonResponse({"success": False, "error": "No email account configured"})
        
        service = EmailService(request.user.email_account)
        
        # Use sync method instead of async
        new_emails = service.check_new_emails_sync()
        
        return JsonResponse({
            "success": True, 
            "message": f"Email check completed. Found {new_emails} new emails."
        })
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@csrf_exempt
@require_http_methods(["GET", "POST"])
def get_emails(request):
    """Get user's emails"""
    try:
        if not hasattr(request.user, 'email_account'):
            return JsonResponse({"success": False, "error": "No email account configured"})
        
        emails = EmailMessage.objects.filter(
            account=request.user.email_account
        ).order_by('-received_at')[:20]
        
        email_data = []
        for email_obj in emails:
            email_data.append({
                'id': email_obj.id,
                'sender': email_obj.sender,
                'subject': email_obj.subject,
                'body': email_obj.body[:200] + '...' if len(email_obj.body) > 200 else email_obj.body,
                'received_at': email_obj.received_at.strftime('%Y-%m-%d %H:%M'),
                'has_response': email_obj.has_response,
                'response_sent': email_obj.response_sent
            })
        
        return JsonResponse({"success": True, "emails": email_data})
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def generate_response(request):
    """Generate response for a specific email"""
    try:
        data = json.loads(request.body)
        email_id = data.get('email_id')
        
        email_obj = EmailMessage.objects.get(
            id=email_id,
            account__user=request.user
        )
        
        service = EmailService(email_obj.account)
        
        # Generate response synchronously
        service._generate_response_sync(email_obj)
        
        email_obj.refresh_from_db()
        
        return JsonResponse({
            "success": True,
            "response": email_obj.ai_response,
            "response_sent": email_obj.response_sent
        })
        
    except EmailMessage.DoesNotExist:
        return JsonResponse({"success": False, "error": "Email not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def toggle_automation(request):
    """Toggle email automation on/off"""
    try:
        data = json.loads(request.body)
        
        if not hasattr(request.user, 'email_account'):
            return JsonResponse({"success": False, "error": "No email account configured"})
        
        account = request.user.email_account
        
        # Use the auto_reply value from request if provided, otherwise toggle
        if 'auto_reply' in data:
            account.auto_reply_enabled = data['auto_reply']
        else:
            account.auto_reply_enabled = not account.auto_reply_enabled
            
        account.save()
        
        message = f"Auto-reply {'enabled' if account.auto_reply_enabled else 'disabled'}"
        
        return JsonResponse({
            "success": True,
            "auto_reply_enabled": account.auto_reply_enabled,
            "message": message
        })
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@csrf_exempt
@require_http_methods(["POST"])
def get_provider_settings(request):
    """Get recommended provider settings for an email address"""
    try:
        data = json.loads(request.body)
        email_address = data.get('email_address', '')
        
        if not email_address:
            return JsonResponse({"success": False, "error": "Email address required"})
        
        settings = EmailService.get_provider_settings(email_address)
        
        return JsonResponse({
            "success": True,
            "settings": settings,
            "message": f"Recommended settings for {settings['display_name']}"
        })
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

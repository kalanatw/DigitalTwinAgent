"""
Integrated Email Views for Chatbot Frontend
"""
import json
import logging
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.utils import timezone

from .models import EmailAccount, EmailMessage, ValidatedSender, ChatSession
from .google_email_service import GoogleEmailService, get_google_oauth_url, exchange_oauth_code

logger = logging.getLogger(__name__)

@csrf_exempt
@require_http_methods(["GET", "POST"])
def get_oauth_url(request):
    """Get Google OAuth URL for email authorization"""
    try:
        oauth_url = get_google_oauth_url()
        
        # If it's a GET request, redirect directly to OAuth
        if request.method == "GET":
            return HttpResponseRedirect(oauth_url)
        
        # If it's a POST request, return JSON
        return JsonResponse({
            "success": True,
            "oauth_url": oauth_url,
            "message": "Redirect to this URL to authorize email access"
        })
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@csrf_exempt
def oauth_callback(request):
    """Handle Google OAuth callback"""
    try:
        code = request.GET.get('code')
        error = request.GET.get('error')
        
        if error:
            return HttpResponseRedirect('/chat/?error=oauth_denied')
        
        if not code:
            return HttpResponseRedirect('/chat/?error=no_code')
        
        # Exchange code for tokens
        tokens = exchange_oauth_code(code)
        
        if 'access_token' not in tokens:
            return HttpResponseRedirect('/chat/?error=token_exchange_failed')
        
        # Create or get a default user for Gmail integration if not logged in
        if not request.user.is_authenticated:
            from django.contrib.auth.models import User
            # Create a default Gmail user or use existing one
            default_user, created = User.objects.get_or_create(
                username='gmail_user',
                defaults={
                    'email': 'gmail_user@example.com',
                    'first_name': 'Gmail',
                    'last_name': 'User'
                }
            )
            
            # Log in the default user
            from django.contrib.auth import login
            login(request, default_user)
        
        # Create or update email account with tokens
        email_account, created = EmailAccount.objects.get_or_create(
            user=request.user,
            defaults={
                'email_address': 'gmail_user@gmail.com',  # Will be updated when we fetch emails
                'google_access_token': tokens['access_token'],
                'google_refresh_token': tokens.get('refresh_token', ''),
                'auto_reply_enabled': True
            }
        )
        
        if not created:
            email_account.google_access_token = tokens['access_token']
            if tokens.get('refresh_token'):
                email_account.google_refresh_token = tokens['refresh_token']
            email_account.save()
        
        # Test the Gmail connection and get user's email address
        try:
            service = GoogleEmailService(email_account)
            if service.service:
                # Get user's profile to fetch their actual email address
                profile = service.service.users().getProfile(userId='me').execute()
                email_address = profile.get('emailAddress', 'gmail_user@gmail.com')
                email_account.email_address = email_address
                email_account.save()
                
                # Add the connected email as a validated sender
                ValidatedSender.objects.get_or_create(
                    email_address=email_address,
                    defaults={'name': 'Gmail User', 'is_active': True}
                )
                
                logger.info(f"Gmail connected successfully for {email_address}")
        except Exception as e:
            logger.warning(f"Failed to fetch Gmail profile: {e}")
        
        # Add default validated senders if none exist
        if not ValidatedSender.objects.filter(is_active=True).exists():
            default_senders = [
                {'email': 'kalanathathsara99@gmail.com', 'name': 'Kalana Thathsara'},
                {'email': 'weerakoonwakt.19@itfac.mrt.ac.lk', 'name': 'WAKT Weerakoon'},
            ]
            
            for sender in default_senders:
                ValidatedSender.objects.get_or_create(
                    email_address=sender['email'],
                    defaults={'name': sender['name'], 'is_active': True}
                )
        else:
            # Always ensure weerakoonwakt.19@itfac.mrt.ac.lk is added as validated sender
            ValidatedSender.objects.get_or_create(
                email_address='weerakoonwakt.19@itfac.mrt.ac.lk',
                defaults={'name': 'WAKT Weerakoon', 'is_active': True}
            )
        
        return HttpResponseRedirect('/chat/?gmail_auth=success')
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        return HttpResponseRedirect('/chat/?error=oauth_callback_failed')

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def setup_email_integration(request):
    """Setup email integration with stored OAuth tokens"""
    try:
        tokens = request.session.get('google_tokens')
        if not tokens:
            return JsonResponse({
                "success": False, 
                "error": "No OAuth tokens found. Please authorize first."
            })
        
        data = json.loads(request.body)
        email_address = data.get('email_address', '')
        
        # Create or update email account
        account, created = EmailAccount.objects.get_or_create(
            user=request.user,
            defaults={
                'email_address': email_address,
                'google_access_token': tokens['access_token'],
                'google_refresh_token': tokens.get('refresh_token', ''),
                'auto_reply_enabled': True
            }
        )
        
        if not created:
            account.email_address = email_address
            account.google_access_token = tokens['access_token']
            if tokens.get('refresh_token'):
                account.google_refresh_token = tokens['refresh_token']
            account.save()
        
        # Clear tokens from session
        if 'google_tokens' in request.session:
            del request.session['google_tokens']
        
        # Add default validated sender
        ValidatedSender.objects.get_or_create(
            email_address='kalanathathsara99@gmail.com',
            defaults={'name': 'Kalana Thathsara', 'is_active': True}
        )
        
        return JsonResponse({
            "success": True,
            "message": "Email integration configured successfully!",
            "email": email_address
        })
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def check_and_process_emails(request):
    """Check for new emails and process them"""
    try:
        if not hasattr(request.user, 'email_account'):
            return JsonResponse({
                "success": False, 
                "error": "No email account configured"
            })
        
        service = GoogleEmailService(request.user.email_account)
        processed_count = service.process_new_emails()
        
        return JsonResponse({
            "success": True,
            "processed_count": processed_count,
            "message": f"Processed {processed_count} new emails"
        })
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@csrf_exempt
@require_http_methods(["GET", "POST"])
def get_email_status(request):
    """Get email status for chatbot display"""
    try:
        # Try to get any available email account with valid tokens
        email_account = EmailAccount.objects.filter(
            google_access_token__isnull=False,
            google_refresh_token__isnull=False
        ).exclude(
            google_access_token__exact='',
            google_refresh_token__exact=''
        ).first()
        
        if not email_account:
            return JsonResponse({
                "success": True,
                "email_configured": False,
                "configured": False,
                "messages": []
            })
        
        # Get recent email messages from database (matching Gmail records)
        recent_emails = EmailMessage.objects.filter(
            account=email_account
        ).select_related('chat_session').order_by('-received_at')[:10]
        
        messages = []
        for email in recent_emails:
            messages.append({
                'id': email.id,
                'sender': email.sender,
                'subject': email.subject,
                'body': email.body[:200] + '...' if len(email.body) > 200 else email.body,
                'status': email.status,
                'ai_response': email.ai_response[:200] + '...' if email.ai_response and len(email.ai_response) > 200 else email.ai_response,
                'response_sent': email.response_sent,
                'received_at': email.received_at.isoformat(),
                'processed_at': email.processed_at.isoformat() if email.processed_at else None,
                'chat_session_id': email.chat_session.session_id if email.chat_session else None,
                'is_from_validated_sender': email.is_from_validated_sender
            })
        
        # Get validated senders
        validated_senders = list(
            ValidatedSender.objects.filter(is_active=True)
            .values('email_address', 'name')
        )
        
        return JsonResponse({
            "success": True,
            "email_configured": True,
            "configured": True,
            "email_address": email_account.email_address,
            "auto_reply_enabled": email_account.auto_reply_enabled,
            "messages": messages,
            "validated_senders": validated_senders,
            "stats": {
                "total_received": EmailMessage.objects.filter(account=email_account).count(),
                "responded": EmailMessage.objects.filter(account=email_account, response_sent=True).count(),
                "from_validated": EmailMessage.objects.filter(account=email_account).filter(sender__in=[s['email_address'] for s in validated_senders]).count()
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting email status: {e}")
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def toggle_auto_reply(request):
    """Toggle auto-reply feature"""
    try:
        if not hasattr(request.user, 'email_account'):
            return JsonResponse({
                "success": False, 
                "error": "No email account configured"
            })
        
        account = request.user.email_account
        account.auto_reply_enabled = not account.auto_reply_enabled
        account.save()
        
        return JsonResponse({
            "success": True,
            "auto_reply_enabled": account.auto_reply_enabled,
            "message": f"Auto-reply {'enabled' if account.auto_reply_enabled else 'disabled'}"
        })
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def add_validated_sender(request):
    """Add a new validated sender"""
    try:
        data = json.loads(request.body)
        email_address = data.get('email_address')
        name = data.get('name', '')
        
        if not email_address:
            return JsonResponse({
                "success": False, 
                "error": "Email address is required"
            })
        
        sender, created = ValidatedSender.objects.get_or_create(
            email_address=email_address,
            defaults={'name': name, 'is_active': True}
        )
        
        if not created:
            sender.name = name
            sender.is_active = True
            sender.save()
        
        return JsonResponse({
            "success": True,
            "message": f"Validated sender {'added' if created else 'updated'}: {email_address}"
        })
        
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def get_email_thread(request):
    """Get email thread for chat display"""
    try:
        data = json.loads(request.body)
        email_id = data.get('email_id')
        
        email_obj = EmailMessage.objects.get(
            id=email_id,
            account__user=request.user
        )
        
        # Format as chat messages
        chat_messages = [
            {
                'role': 'user',
                'content': f"📧 **Email from {email_obj.sender}**\n\n**Subject:** {email_obj.subject}\n\n**Message:**\n{email_obj.body}",
                'timestamp': email_obj.received_at.isoformat(),
                'email_metadata': {
                    'sender': email_obj.sender,
                    'subject': email_obj.subject,
                    'status': email_obj.status
                }
            }
        ]
        
        if email_obj.ai_response:
            chat_messages.append({
                'role': 'assistant',
                'content': f"📤 **Auto-Reply Sent**\n\n{email_obj.ai_response}",
                'timestamp': email_obj.processed_at.isoformat() if email_obj.processed_at else email_obj.received_at.isoformat(),
                'email_metadata': {
                    'response_sent': email_obj.response_sent,
                    'status': email_obj.status
                }
            })
        
        return JsonResponse({
            "success": True,
            "email_thread": chat_messages,
            "session_id": email_obj.chat_session.session_id if email_obj.chat_session else None
        })
        
    except EmailMessage.DoesNotExist:
        return JsonResponse({"success": False, "error": "Email not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@require_http_methods(["GET"])
def get_email_messages(request):
    """Get email messages from Gmail API with fallback to database"""
    try:
        # Get validated senders
        validated_senders = ValidatedSender.objects.filter(is_active=True)
        
        if not validated_senders.exists():
            return JsonResponse({
                "success": True,
                "emails": [],
                "validated_senders": [],
                "total_count": 0,
                "has_email_account": False,
                "message": "No validated senders configured"
            })
        
        email_data = []
        gmail_emails_fetched = False
        
        # Check if we have any email account with valid OAuth tokens
        email_account = None
        try:
            # Try to get the first available email account with valid tokens
            email_account = EmailAccount.objects.filter(
                google_access_token__isnull=False,
                google_refresh_token__isnull=False
            ).exclude(
                google_access_token__exact='',
                google_refresh_token__exact=''
            ).first()
        except EmailAccount.DoesNotExist:
            pass
        
        # Try to fetch emails from Gmail API first
        if email_account:
            try:
                gmail_service = GoogleEmailService(email_account)
                if gmail_service.service:
                    gmail_emails = gmail_service.get_recent_emails(max_results=50, include_read=True)
                    
                    if gmail_emails:
                        gmail_emails_fetched = True
                        for gmail_email in gmail_emails:
                            # Try to find existing database record for AI response/status
                            db_record = None
                            try:
                                db_record = EmailMessage.objects.filter(
                                    message_id=gmail_email['message_id']
                                ).first()
                            except:
                                pass
                            
                            email_data.append({
                                "id": db_record.id if db_record else f"gmail_{gmail_email['message_id']}",
                                "message_id": gmail_email['message_id'],
                                "sender": gmail_email['sender'],
                                "subject": gmail_email['subject'],
                                "body": gmail_email['body'],
                                "status": db_record.status if db_record else 'received',
                                "ai_response": db_record.ai_response if db_record else None,
                                "response_sent": db_record.response_sent if db_record else False,
                                "received_at": gmail_email['received_at'].isoformat() if hasattr(gmail_email['received_at'], 'isoformat') else str(gmail_email['received_at']),
                                "processed_at": db_record.processed_at.isoformat() if db_record and db_record.processed_at else None,
                                "is_from_validated_sender": gmail_email['is_from_validated_sender'],
                                "source": "gmail",
                                "expanded": False  # For frontend display
                            })
                        
                        logger.info(f"Fetched {len(gmail_emails)} emails from Gmail API")
                    else:
                        logger.info("No emails found in Gmail API response")
                else:
                    logger.warning("Gmail service not initialized properly")
                    
            except Exception as e:
                logger.warning(f"Failed to fetch emails from Gmail API: {e}")
        
        # Fallback to database emails if Gmail fetch failed or no account
        if not gmail_emails_fetched:
            logger.info("Falling back to database emails")
            messages = EmailMessage.objects.filter(
                sender__in=validated_senders.values_list('email_address', flat=True)
            ).order_by('-received_at')
            
            for msg in messages:
                email_data.append({
                    "id": msg.id,
                    "sender": msg.sender,
                    "subject": msg.subject,
                    "body": msg.body,
                    "status": msg.status,
                    "ai_response": msg.ai_response,
                    "response_sent": msg.response_sent,
                    "received_at": msg.received_at.isoformat(),
                    "processed_at": msg.processed_at.isoformat() if msg.processed_at else None,
                    "is_from_validated_sender": True,
                    "source": "database",
                    "expanded": False  # For frontend display
                })
        
        # Add info about validated senders
        validated_sender_list = list(validated_senders.values('email_address', 'name', 'is_active'))
        
        # Check if current user has email account
        has_email_account = email_account is not None
        
        return JsonResponse({
            "success": True,
            "emails": email_data,
            "validated_senders": validated_sender_list,
            "total_count": len(email_data),
            "has_email_account": has_email_account,
            "gmail_connected": gmail_emails_fetched,
            "source": "gmail" if gmail_emails_fetched else "database",
            "message": f"Displaying {len(email_data)} emails from {'Gmail API' if gmail_emails_fetched else 'database'}"
        })
        
    except Exception as e:
        logger.error(f"Error fetching email messages: {e}")
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def send_email_response(request, email_id):
    """Send the AI response for a specific email"""
    try:
        if not hasattr(request.user, 'email_account'):
            return JsonResponse({"success": False, "error": "Email not configured"})
        
        email_msg = EmailMessage.objects.get(
            id=email_id,
            account=request.user.email_account
        )
        
        if email_msg.response_sent:
            return JsonResponse({"success": False, "error": "Response already sent"})
        
        if not email_msg.ai_response:
            return JsonResponse({"success": False, "error": "No AI response available"})
        
        # Initialize email service
        service = GoogleEmailService(request.user.email_account)
        
        # Send the response
        success = service.send_reply(
            email_msg.sender,
            f"Re: {email_msg.subject}",
            email_msg.ai_response
        )
        
        if success:
            email_msg.response_sent = True
            email_msg.status = 'responded'
            email_msg.processed_at = timezone.now()
            email_msg.save()
            
            return JsonResponse({"success": True})
        else:
            return JsonResponse({"success": False, "error": "Failed to send email"})
        
    except EmailMessage.DoesNotExist:
        return JsonResponse({"success": False, "error": "Email not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_email_response(request, email_id):
    """Update the AI response for a specific email"""
    try:
        if not hasattr(request.user, 'email_account'):
            return JsonResponse({"success": False, "error": "Email not configured"})
        
        import json
        data = json.loads(request.body)
        new_response = data.get('response', '')
        
        if not new_response.strip():
            return JsonResponse({"success": False, "error": "Response cannot be empty"})
        
        email_msg = EmailMessage.objects.get(
            id=email_id,
            account=request.user.email_account
        )
        
        email_msg.ai_response = new_response
        email_msg.save()
        
        return JsonResponse({"success": True})
        
    except EmailMessage.DoesNotExist:
        return JsonResponse({"success": False, "error": "Email not found"})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})

@require_http_methods(["GET"])
def email_automation_page(request):
    """Render the email automation monitoring page"""
    return render(request, 'email_automation.html')

@require_http_methods(["POST"])
def create_test_emails(request):
    """Create test email data for demonstration (development only)"""
    try:
        from django.contrib.auth.models import User
        from django.utils import timezone
        import uuid
        
        # Get or create a test user
        test_user, created = User.objects.get_or_create(
            username='test_email_user',
            defaults={
                'email': 'test@example.com',
                'first_name': 'Test',
                'last_name': 'User'
            }
        )
        
        # Get or create email account for test user
        email_account, created = EmailAccount.objects.get_or_create(
            user=test_user,
            defaults={
                'email_address': 'test@example.com',
                'is_configured': True,
                'auto_reply_enabled': True
            }
        )
        
        # Get validated sender
        validated_sender = ValidatedSender.objects.filter(
            email_address='kalanathathsara99@gmail.com'
        ).first()
        
        if not validated_sender:
            return JsonResponse({
                "success": False, 
                "error": "No validated sender found. Please ensure kalanathathsara99@gmail.com is added as a validated sender."
            })
        
        # Create test emails
        test_emails = [
            {
                'subject': 'Hello from Email Automation',
                'body': 'This is a test email to demonstrate the email automation system. Please respond with information about digital twin capabilities.',
                'status': 'received'
            },
            {
                'subject': 'Question about IoT Integration',
                'body': 'Hi, I would like to know more about how your digital twin system handles IoT sensor data integration. Can you provide some details?',
                'status': 'processing'
            },
            {
                'subject': 'Meeting Request',
                'body': 'I would like to schedule a meeting to discuss the digital twin implementation for our manufacturing facility. When would be a good time?',
                'status': 'responded'
            }
        ]
        
        created_emails = []
        for i, email_data in enumerate(test_emails):
            # Generate AI response for demonstration
            ai_responses = [
                "Thank you for your interest in our email automation system! Our digital twin platform offers comprehensive capabilities including real-time sensor monitoring, predictive analytics, and automated responses. I'd be happy to provide more details about specific features you're interested in.",
                "Great question about IoT integration! Our digital twin system seamlessly connects with various IoT sensors and devices. We support multiple protocols including MQTT, REST APIs, and direct database connections. The system can process real-time data streams and provide intelligent insights based on the collected sensor information.",
                "I'd be delighted to schedule a meeting to discuss digital twin implementation for your manufacturing facility. Our platform specializes in industrial applications and can significantly improve operational efficiency. Please let me know your preferred time slots and I'll coordinate the meeting accordingly."
            ]
            
            email_obj, created = EmailMessage.objects.get_or_create(
                account=email_account,
                message_id=f"test_email_{i+1}_{uuid.uuid4().hex[:8]}",
                defaults={
                    'sender': validated_sender.email_address,
                    'subject': email_data['subject'],
                    'body': email_data['body'],
                    'status': email_data['status'],
                    'ai_response': ai_responses[i],
                    'response_sent': email_data['status'] == 'responded',
                    'received_at': timezone.now() - timezone.timedelta(hours=i+1),
                    'processed_at': timezone.now() - timezone.timedelta(minutes=30*i) if email_data['status'] in ['responded', 'processing'] else None
                }
            )
            
            if created:
                created_emails.append({
                    'id': email_obj.id,
                    'subject': email_obj.subject,
                    'status': email_obj.status
                })
        
        return JsonResponse({
            "success": True,
            "message": f"Created {len(created_emails)} test emails",
            "emails": created_emails
        })
        
    except Exception as e:
        logger.error(f"Error creating test emails: {e}")
        return JsonResponse({"success": False, "error": str(e)})

@require_http_methods(["POST"])
@csrf_exempt
def generate_email_response(request, email_id):
    """Generate AI response for a specific email (database or Gmail)"""
    try:
        # Check if this is a Gmail email ID (starts with "gmail_")
        if str(email_id).startswith("gmail_"):
            # Handle Gmail email
            gmail_message_id = str(email_id).replace("gmail_", "")
            
            # Try to fetch the email details from Gmail API
            try:
                # Get the first available email account with valid tokens
                email_account = EmailAccount.objects.filter(
                    google_access_token__isnull=False,
                    google_refresh_token__isnull=False
                ).exclude(
                    google_access_token__exact='',
                    google_refresh_token__exact=''
                ).first()
                
                if not email_account:
                    return JsonResponse({
                        'success': False,
                        'error': 'No valid Gmail account configured'
                    }, status=400)
                
                # Fetch recent emails to find the specific email
                gmail_service = GoogleEmailService(email_account)
                if gmail_service.service:
                    gmail_emails = gmail_service.get_recent_emails(max_results=50, include_read=True)
                    
                    # Find the specific email
                    target_email = None
                    for email in gmail_emails:
                        if email['message_id'] == gmail_message_id:
                            target_email = email
                            break
                    
                    if not target_email:
                        return JsonResponse({
                            'success': False,
                            'error': 'Gmail email not found'
                        }, status=404)
                    
                    # Generate AI response using the agent
                    import asyncio
                    from .agent import get_agent_instance
                    from .email_formatter import EmailFormatter
                    
                    agent = get_agent_instance()
                    
                    prompt = f"""
You are a Digital Assets Manager. Please respond to this email professionally.

From: {target_email['sender']}
Subject: {target_email['subject']}
Message: {target_email['body']}

Generate a helpful, professional response. Keep it concise and relevant.
Use appropriate email templates if this appears to be a business inquiry.
Do not include markdown formatting in your response - write in plain professional text.
"""
                    
                    # Run async method in sync context
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    response = loop.run_until_complete(
                        agent.process_message(prompt, session_id=f"gmail_{gmail_message_id}")
                    )
                    loop.close()
                    
                    if response and response.get('response'):
                        # Format the response professionally
                        formatted_email = EmailFormatter.format_agent_response_to_email(response['response'])
                        
                        # Try to find or create database record for caching
                        db_record, created = EmailMessage.objects.get_or_create(
                            message_id=gmail_message_id,
                            defaults={
                                'account': email_account,
                                'sender': target_email['sender'],
                                'subject': target_email['subject'],
                                'body': target_email['body'],
                                'status': 'received'
                            }
                        )
                        
                        # Update with AI response (store the formatted version)
                        db_record.ai_response = formatted_email['html_body']
                        db_record.status = 'processing'
                        db_record.save()
                        
                        return JsonResponse({
                            'success': True,
                            'response': formatted_email['html_body'],
                            'subject': formatted_email['subject'],
                            'text_response': formatted_email['text_body'],
                            'email_type': 'gmail'
                        })
                    else:
                        return JsonResponse({
                            'success': False,
                            'error': 'Failed to generate response'
                        }, status=500)
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Gmail service not available'
                    }, status=500)
                    
            except Exception as gmail_error:
                logger.error(f"Error handling Gmail email: {gmail_error}")
                return JsonResponse({
                    'success': False,
                    'error': f'Gmail error: {str(gmail_error)}'
                }, status=500)
        
        else:
            # Handle database email (integer ID)
            try:
                email_id = int(email_id)
                email_obj = EmailMessage.objects.get(id=email_id)
                
                # Generate AI response using the agent
                import asyncio
                from .agent import get_agent_instance
                from .email_formatter import EmailFormatter
                
                agent = get_agent_instance()
                
                prompt = f"""
You are a Digital Assets Manager. Please respond to this email professionally.

From: {email_obj.sender}
Subject: {email_obj.subject}
Message: {email_obj.body}

Generate a helpful, professional response. Keep it concise and relevant.
Use appropriate email templates if this appears to be a business inquiry.
Do not include markdown formatting in your response - write in plain professional text.
"""
                
                # Run async method in sync context
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                response = loop.run_until_complete(
                    agent.process_message(prompt, session_id=f"email_{email_obj.id}")
                )
                loop.close()
                
                if response and response.get('response'):
                    # Format the response professionally
                    formatted_email = EmailFormatter.format_agent_response_to_email(response['response'])
                    
                    email_obj.ai_response = formatted_email['html_body']
                    email_obj.status = 'processing'
                    email_obj.save()
                    
                    return JsonResponse({
                        'success': True,
                        'response': formatted_email['html_body'],
                        'subject': formatted_email['subject'],
                        'text_response': formatted_email['text_body'],
                        'email_type': 'database'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': 'Failed to generate response'
                    }, status=500)
                    
            except (ValueError, EmailMessage.DoesNotExist):
                return JsonResponse({
                    'success': False,
                    'error': 'Email not found'
                }, status=404)
            
    except Exception as e:
        logger.error(f"Error generating response for email {email_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def clear_gmail_tokens(request):
    """Clear invalid Gmail tokens and reset authentication"""
    try:
        # Clear all invalid tokens
        invalid_accounts = EmailAccount.objects.filter(
            google_access_token__isnull=False,
            google_refresh_token__isnull=False
        ).exclude(
            google_access_token__exact='',
            google_refresh_token__exact=''
        )
        
        cleared_count = 0
        for account in invalid_accounts:
            # Clear the tokens
            account.google_access_token = ''
            account.google_refresh_token = ''
            account.save()
            cleared_count += 1
            logger.info(f"Cleared invalid tokens for {account.email_address}")
        
        return JsonResponse({
            "success": True,
            "message": f"Cleared tokens for {cleared_count} account(s). Please re-authenticate.",
            "cleared_count": cleared_count
        })
        
    except Exception as e:
        logger.error(f"Error clearing Gmail tokens: {e}")
        return JsonResponse({"success": False, "error": str(e)})

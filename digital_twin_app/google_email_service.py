"""
Google OAuth Email Service for automated email handling
"""
import json
import base64
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from django.conf import settings
from django.utils import timezone

from .models import EmailAccount, EmailMessage, ValidatedSender, ChatSession
from .agent import get_agent_instance

logger = logging.getLogger(__name__)

class GoogleEmailService:
    """Google OAuth Email Service for automated email processing"""
    
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/gmail.modify'
    ]
    
    def __init__(self, email_account: EmailAccount):
        self.account = email_account
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Gmail API service with OAuth credentials"""
        try:
            # Check if we have the required tokens
            if not self.account.google_access_token or not self.account.google_refresh_token:
                logger.warning(f"Missing OAuth tokens for account {self.account.email_address}")
                self.service = None
                return
            
            # Load Google OAuth config
            with open('google_oauth_config.json', 'r') as f:
                config = json.load(f)
            
            # Create credentials from stored tokens
            creds = Credentials(
                token=self.account.google_access_token,
                refresh_token=self.account.google_refresh_token,
                token_uri=config['web']['token_uri'],
                client_id=config['web']['client_id'],
                client_secret=config['web']['client_secret'],
                scopes=self.SCOPES
            )
            
            # Always try to refresh if we have a refresh token to ensure we have valid credentials
            if creds.refresh_token:
                try:
                    logger.info(f"Refreshing OAuth tokens for {self.account.email_address}")
                    creds.refresh(Request())
                    self._update_tokens(creds)
                    logger.info(f"Successfully refreshed OAuth tokens for {self.account.email_address}")
                except Exception as refresh_error:
                    logger.error(f"Failed to refresh OAuth tokens for {self.account.email_address}: {refresh_error}")
                    # If refresh fails, the tokens might be revoked - we'll still try to use existing token
                    # but it will likely fail, which is handled in the calling methods
            
            self.service = build('gmail', 'v1', credentials=creds)
            logger.info(f"Gmail service initialized successfully for {self.account.email_address}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service for {self.account.email_address}: {e}")
            self.service = None
    
    def _update_tokens(self, creds):
        """Update stored OAuth tokens"""
        from django.utils import timezone
        
        self.account.google_access_token = creds.token
        if creds.refresh_token:
            self.account.google_refresh_token = creds.refresh_token
        if creds.expiry:
            # Ensure timezone-aware datetime
            if creds.expiry.tzinfo is None:
                # If naive datetime, make it timezone-aware
                self.account.token_expires_at = timezone.make_aware(creds.expiry)
            else:
                self.account.token_expires_at = creds.expiry
        self.account.save()
    
    def check_new_emails(self) -> List[Dict]:
        """Check for new emails from validated senders"""
        if not self.service:
            return []
        
        try:
            # Get validated senders
            validated_emails = list(
                ValidatedSender.objects.filter(is_active=True)
                .values_list('email_address', flat=True)
            )
            
            if not validated_emails:
                return []
            
            new_emails = []
            
            # Check emails from each validated sender
            for sender_email in validated_emails:
                query = f'from:{sender_email} is:unread'
                results = self.service.users().messages().list(
                    userId='me', q=query
                ).execute()
                
                messages = results.get('messages', [])
                
                for message in messages:
                    email_data = self._parse_email_message(message['id'])
                    if email_data:
                        new_emails.append(email_data)
                        # Mark as read
                        self.service.users().messages().modify(
                            userId='me',
                            id=message['id'],
                            body={'removeLabelIds': ['UNREAD']}
                        ).execute()
            
            return new_emails
            
        except Exception as e:
            logger.error(f"Error checking emails: {e}")
            return []
    
    def _parse_email_message(self, message_id: str) -> Optional[Dict]:
        """Parse Gmail message and extract relevant data"""
        try:
            message = self.service.users().messages().get(
                userId='me', id=message_id, format='full'
            ).execute()
            
            payload = message['payload']
            headers = payload.get('headers', [])
            
            # Extract headers
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            
            # Extract sender email
            if '<' in sender and '>' in sender:
                sender_email = sender.split('<')[1].split('>')[0]
            else:
                sender_email = sender
            
            # Extract body
            body = self._extract_body(payload)
            
            return {
                'message_id': message_id,
                'sender': sender_email,
                'subject': subject,
                'body': body,
                'received_at': timezone.now()
            }
            
        except Exception as e:
            logger.error(f"Error parsing email message {message_id}: {e}")
            return None
    
    def _extract_body(self, payload) -> str:
        """Extract email body from Gmail API payload"""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body']['data']
                    body = base64.urlsafe_b64decode(data).decode('utf-8')
                    break
        elif payload['mimeType'] == 'text/plain':
            data = payload['body']['data']
            body = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return body
    
    def send_reply(self, to_email: str, subject: str, body: str, 
                   thread_id: str = None) -> bool:
        """Send email reply using Gmail API"""
        try:
            message = MIMEMultipart()
            message['to'] = to_email
            message['from'] = self.account.email_address
            message['subject'] = subject
            
            message.attach(MIMEText(body, 'plain'))
            
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode('utf-8')
            
            send_message = {'raw': raw_message}
            if thread_id:
                send_message['threadId'] = thread_id
            
            result = self.service.users().messages().send(
                userId='me', body=send_message
            ).execute()
            
            logger.info(f"Email sent to {to_email}, Message ID: {result['id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")
            return False
    
    def send_html_reply(self, to_email: str, subject: str, text_body: str, 
                       html_body: str, thread_id: str = None) -> bool:
        """Send HTML email reply using Gmail API"""
        try:
            message = MIMEMultipart('alternative')
            message['to'] = to_email
            message['from'] = self.account.email_address
            message['subject'] = subject
            
            # Add both text and HTML versions
            text_part = MIMEText(text_body, 'plain', 'utf-8')
            html_part = MIMEText(html_body, 'html', 'utf-8')
            
            message.attach(text_part)
            message.attach(html_part)
            
            raw_message = base64.urlsafe_b64encode(
                message.as_bytes()
            ).decode('utf-8')
            
            send_message = {'raw': raw_message}
            if thread_id:
                send_message['threadId'] = thread_id
            
            result = self.service.users().messages().send(
                userId='me', body=send_message
            ).execute()
            
            logger.info(f"HTML email sent to {to_email}, Message ID: {result['id']}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending HTML email to {to_email}: {e}")
            return False
    
    def process_new_emails(self) -> int:
        """Process new emails and generate responses"""
        new_emails = self.check_new_emails()
        processed_count = 0
        
        for email_data in new_emails:
            try:
                # Check if already processed
                if EmailMessage.objects.filter(
                    message_id=email_data['message_id']
                ).exists():
                    continue
                
                # Create email record
                email_obj = EmailMessage.objects.create(
                    account=self.account,
                    message_id=email_data['message_id'],
                    sender=email_data['sender'],
                    subject=email_data['subject'],
                    body=email_data['body'],
                    status='received'
                )
                
                # Generate and send response if auto-reply enabled
                if self.account.auto_reply_enabled and email_obj.is_from_validated_sender:
                    self._generate_and_send_response(email_obj)
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error processing email: {e}")
        
        return processed_count
    
    def _generate_and_send_response(self, email_obj: EmailMessage):
        """Generate AI response and send it"""
        try:
            email_obj.status = 'processing'
            email_obj.save()

            # Create or get chat session for this email thread
            session_id = f"email_{email_obj.sender}_{email_obj.id}"
            chat_session, created = ChatSession.objects.get_or_create(
                session_id=session_id,
                defaults={'user': self.account.user}
            )

            email_obj.chat_session = chat_session
            email_obj.save()

            # Generate AI response using the correct async method
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
                agent.process_message(prompt, session_id=session_id)
            )
            loop.close()

            if response and response.get('response'):
                ai_response = response['response']
                
                # Format the response professionally
                formatted_email = EmailFormatter.format_agent_response_to_email(ai_response)
                
                # Send response using HTML format
                success = self.send_html_reply(
                    email_obj.sender,
                    formatted_email['subject'],
                    formatted_email['text_body'],
                    formatted_email['html_body']
                )

                if success:
                    email_obj.ai_response = ai_response
                    email_obj.response_sent = True
                    email_obj.status = 'responded'
                    email_obj.processed_at = timezone.now()
                    email_obj.save()

                    logger.info(f"Auto-response sent to {email_obj.sender}")
                else:
                    email_obj.status = 'failed'
                    email_obj.save()
                    logger.error(f"Failed to send response to {email_obj.sender}")
            else:
                email_obj.status = 'failed'
                email_obj.save()
                logger.error(f"Failed to generate response for email {email_obj.id}")

        except Exception as e:
            logger.error(f"Error generating response for email {email_obj.id}: {e}")
            email_obj.status = 'failed'
            email_obj.save()
    
    def get_recent_emails(self, max_results: int = 50, include_read: bool = True) -> List[Dict]:
        """Get recent emails from Gmail API for display purposes"""
        if not self.service:
            logger.warning(f"Gmail service not initialized for {self.account.email_address}")
            return []
        
        try:
            # Get validated senders
            validated_emails = list(
                ValidatedSender.objects.filter(is_active=True)
                .values_list('email_address', flat=True)
            )
            
            if not validated_emails:
                logger.info("No validated senders found")
                return []
            
            all_emails = []
            
            # Build query to get emails from validated senders
            sender_queries = [f'from:{email}' for email in validated_emails]
            query = ' OR '.join(sender_queries)
            
            if not include_read:
                query += ' is:unread'
            
            logger.debug(f"Gmail API query: {query}")
            
            # Get recent messages
            results = self.service.users().messages().list(
                userId='me', 
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} emails from validated senders for {self.account.email_address}")
            
            # Parse each message
            for message in messages:
                email_data = self._parse_gmail_message_for_display(message['id'])
                if email_data:
                    # Check if sender is validated
                    email_data['is_from_validated_sender'] = email_data['sender'] in validated_emails
                    all_emails.append(email_data)
            
            # Sort by received date (newest first)
            all_emails.sort(key=lambda x: x['received_at'], reverse=True)
            
            logger.info(f"Successfully parsed {len(all_emails)} emails from Gmail API for {self.account.email_address}")
            return all_emails
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error fetching recent emails for {self.account.email_address}: {error_msg}")
            
            # Check if it's an authentication error
            if 'invalid_grant' in error_msg or 'invalid_token' in error_msg:
                logger.error(f"OAuth tokens appear to be invalid for {self.account.email_address}. User needs to re-authenticate.")
                # Clear invalid tokens automatically
                self.account.google_access_token = ''
                self.account.google_refresh_token = ''
                self.account.save()
                logger.info(f"Cleared invalid tokens for {self.account.email_address}")
            
            return []
    
    def _parse_gmail_message_for_display(self, message_id: str) -> Optional[Dict]:
        """Parse Gmail message for display in email automation interface"""
        try:
            message = self.service.users().messages().get(
                userId='me', id=message_id, format='full'
            ).execute()
            
            payload = message['payload']
            headers = payload.get('headers', [])
            
            # Extract headers
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            date_header = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            # Extract sender email
            if '<' in sender and '>' in sender:
                sender_email = sender.split('<')[1].split('>')[0]
            else:
                sender_email = sender.strip()
            
            # Extract body
            body = self._extract_body(payload)
            
            # Parse date
            received_at = timezone.now()
            if date_header:
                try:
                    from email.utils import parsedate_to_datetime
                    received_at = parsedate_to_datetime(date_header)
                    if received_at.tzinfo is None:
                        received_at = timezone.make_aware(received_at)
                except Exception as e:
                    logger.warning(f"Could not parse date '{date_header}': {e}")
            
            return {
                'message_id': message_id,
                'sender': sender_email,
                'subject': subject,
                'body': body,
                'received_at': received_at
            }
            
        except Exception as e:
            logger.error(f"Error parsing Gmail message {message_id} for display: {e}")
            return None

def get_google_oauth_url() -> str:
    """Generate Google OAuth authorization URL"""
    with open('google_oauth_config.json', 'r') as f:
        config = json.load(f)
    
    params = {
        'client_id': config['web']['client_id'],
        'redirect_uri': 'http://localhost:8000/api/email/oauth/callback/',
        'scope': ' '.join(GoogleEmailService.SCOPES),
        'response_type': 'code',
        'access_type': 'offline',
        'prompt': 'consent'
    }
    
    url = config['web']['auth_uri'] + '?' + '&'.join([
        f"{k}={requests.utils.quote(str(v))}" for k, v in params.items()
    ])
    
    return url


def exchange_oauth_code(code: str) -> Dict:
    """Exchange OAuth code for access tokens"""
    with open('google_oauth_config.json', 'r') as f:
        config = json.load(f)
    
    data = {
        'client_id': config['web']['client_id'],
        'client_secret': config['web']['client_secret'],
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': 'http://localhost:8000/api/email/oauth/callback/'
    }
    
    response = requests.post(config['web']['token_uri'], data=data)
    return response.json()

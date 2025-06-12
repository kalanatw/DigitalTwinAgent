"""
Minimal Email Service for automated email responses
"""
import imaplib
import smtplib
import email
import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr
from datetime import datetime
from typing import List, Dict, Optional
import base64
from django.utils import timezone
from .models import EmailAccount, EmailMessage
from .agent import get_agent_instance

logger = logging.getLogger(__name__)

# Simple encryption for passwords
def encrypt_password(password: str) -> str:
    """Simple password encryption using base64"""
    return base64.b64encode(password.encode()).decode()

def decrypt_password(encrypted_password: str) -> str:
    """Simple password decryption using base64"""
    try:
        return base64.b64decode(encrypted_password.encode()).decode()
    except:
        return encrypted_password  # If not encoded

class EmailService:
    """Minimal email service for automation"""
    
    # Email provider presets
    PROVIDERS = {
        'gmail': {
            'imap_server': 'imap.gmail.com',
            'imap_port': 993,
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'display_name': 'Gmail'
        },
        'outlook': {
            'imap_server': 'outlook.office365.com',
            'imap_port': 993,
            'smtp_server': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'display_name': 'Outlook/Hotmail'
        },
        'yahoo': {
            'imap_server': 'imap.mail.yahoo.com',
            'imap_port': 993,
            'smtp_server': 'smtp.mail.yahoo.com',
            'smtp_port': 587,
            'display_name': 'Yahoo Mail'
        }
    }
    
    def __init__(self, email_account: EmailAccount):
        self.account = email_account
        self.user = email_account.user
    
    @classmethod
    def get_provider_settings(cls, email_address: str) -> Dict[str, any]:
        """Get recommended settings based on email address"""
        domain = email_address.split('@')[-1].lower()
        
        if 'gmail' in domain:
            return cls.PROVIDERS['gmail']
        elif 'outlook' in domain or 'hotmail' in domain or 'live' in domain:
            return cls.PROVIDERS['outlook']
        elif 'yahoo' in domain:
            return cls.PROVIDERS['yahoo']
        else:
            # Default to Gmail settings
            return cls.PROVIDERS['gmail']
    
    def test_connection(self) -> Dict[str, any]:
        """Test email connection with detailed error messages"""
        try:
            password = decrypt_password(self.account.password)
            
            # Test IMAP first
            try:
                mail = imaplib.IMAP4_SSL(self.account.imap_server, self.account.imap_port)
                mail.login(self.account.email_address, password)
                mail.select('INBOX')
                mail.logout()
            except imaplib.IMAP4.error as e:
                error_msg = str(e).lower()
                if 'authenticationfailed' in error_msg or 'invalid credentials' in error_msg:
                    return {
                        "success": False, 
                        "message": "❌ Authentication failed. Are you using an APP PASSWORD instead of your regular password? Please check the EMAIL_SETUP_GUIDE.md for instructions.",
                        "error_type": "authentication"
                    }
                else:
                    return {"success": False, "message": f"❌ IMAP connection failed: {e}", "error_type": "imap"}
            
            # Test SMTP
            try:
                smtp = smtplib.SMTP(self.account.smtp_server, self.account.smtp_port)
                smtp.starttls()
                smtp.login(self.account.email_address, password)
                smtp.quit()
            except smtplib.SMTPAuthenticationError as e:
                return {
                    "success": False, 
                    "message": "❌ SMTP Authentication failed. Please verify your app password.",
                    "error_type": "smtp_auth"
                }
            except Exception as e:
                return {"success": False, "message": f"❌ SMTP connection failed: {e}", "error_type": "smtp"}
            
            return {"success": True, "message": "✅ Connection successful! Both IMAP and SMTP are working."}
        except Exception as e:
            logger.error(f"Email connection failed: {e}")
            return {"success": False, "error": str(e)}
    
    def check_emails(self) -> List[Dict]:
        """Check for new emails"""
        try:
            password = decrypt_password(self.account.password)
            mail = imaplib.IMAP4_SSL(self.account.imap_server, self.account.imap_port)
            mail.login(self.account.email_address, password)
            mail.select('INBOX')
            
            # Get unread emails
            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()
            
            new_emails = []
            for email_id in email_ids[-5:]:  # Last 5 unread emails
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                parsed = self._parse_email(email_message)
                if parsed:
                    new_emails.append(parsed)
            
            mail.logout()
            return new_emails
            
        except Exception as e:
            logger.error(f"Error checking emails: {e}")
            return []
    
    def _parse_email(self, email_message) -> Optional[Dict]:
        """Parse email message"""
        try:
            sender = parseaddr(email_message['From'])[1]
            subject = email_message['Subject'] or "No Subject"
            message_id = email_message['Message-ID']
            
            # Get body
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
            else:
                body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
            
            return {
                'message_id': message_id,
                'sender': sender,
                'subject': subject,
                'body': body,
                'received_at': timezone.now()
            }
            
        except Exception as e:
            logger.error(f"Error parsing email: {e}")
            return None
    
    def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """Send email"""
        try:
            password = decrypt_password(self.account.password)
            
            msg = MIMEMultipart()
            msg['From'] = self.account.email_address
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.account.smtp_server, self.account.smtp_port) as server:
                server.starttls()
                server.login(self.account.email_address, password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
    
    def check_new_emails_sync(self) -> int:
        """Synchronous version of email checking for web interface"""
        try:
            new_emails = self.check_emails()
            new_count = 0
            
            for email_data in new_emails:
                try:
                    # Save to database
                    email_obj, created = EmailMessage.objects.get_or_create(
                        message_id=email_data['message_id'],
                        defaults={
                            'account': self.account,
                            'sender': email_data['sender'],
                            'subject': email_data['subject'],
                            'body': email_data['body'],
                            'received_at': email_data['received_at']
                        }
                    )
                    
                    if created:
                        new_count += 1
                        # Generate response if auto-reply is enabled
                        if self.account.auto_reply_enabled:
                            self._generate_response_sync(email_obj)
                            
                except Exception as e:
                    logger.error(f"Error processing email: {e}")
            
            return new_count
            
        except Exception as e:
            logger.error(f"Error checking emails: {e}")
            return 0
    
    def _generate_response_sync(self, email_obj: EmailMessage):
        """Synchronous version of response generation"""
        try:
            from .agent import get_agent_instance
            
            # Generate AI response
            agent = get_agent_instance()
            prompt = f"""
            Please respond to this email professionally:
            
            From: {email_obj.sender}
            Subject: {email_obj.subject}
            Message: {email_obj.body}
            
            Generate a helpful response as a Digital Assets Manager.
            """
            
            response = agent.handle_message(prompt, session_id=f"email_{email_obj.id}")
            
            if response and hasattr(response, 'content'):
                ai_response = response.content
                
                # Send response
                success = self.send_email(
                    email_obj.sender,
                    f"Re: {email_obj.subject}",
                    ai_response
                )
                
                if success:
                    email_obj.response_sent = True
                    email_obj.ai_response = ai_response
                    email_obj.save()
                    logger.info(f"Auto-response sent to {email_obj.sender}")
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
    
    async def process_new_emails(self):
        """Process new emails and generate auto-responses"""
        if not self.account.auto_reply_enabled:
            return
        
        new_emails = self.check_emails()
        
        for email_data in new_emails:
            try:
                # Save to database
                email_obj, created = EmailMessage.objects.get_or_create(
                    message_id=email_data['message_id'],
                    defaults={
                        'account': self.account,
                        'sender': email_data['sender'],
                        'subject': email_data['subject'],
                        'body': email_data['body'],
                        'received_at': email_data['received_at']
                    }
                )
                
                if created:
                    await self._generate_response(email_obj)
                    
            except Exception as e:
                logger.error(f"Error processing email: {e}")
    
    async def _generate_response(self, email_obj: EmailMessage):
        """Generate AI response for email"""
        try:
            agent = get_agent_instance()
            
            prompt = f"""
            I received this email that needs a professional response:
            
            From: {email_obj.sender}
            Subject: {email_obj.subject}
            Message: {email_obj.body}
            
            Please generate a professional email response. Analyze the content and use appropriate templates if needed.
            """
            
            session_id = f"email_{email_obj.id}"
            response = await agent.process_message(prompt, session_id)
            
            if response['status'] == 'success':
                ai_response = response['response']
                
                # Extract subject and body
                subject = f"Re: {email_obj.subject}"
                body = ai_response
                
                # Look for subject in response
                lines = ai_response.split('\n')
                for i, line in enumerate(lines):
                    if 'subject:' in line.lower() or '**subject:**' in line.lower():
                        subject = line.split(':', 1)[1].strip().replace('*', '')
                        body = '\n'.join(lines[i+1:]).strip()
                        break
                
                # Send response
                if self.send_email(email_obj.sender, subject, body):
                    email_obj.has_response = True
                    email_obj.response_sent = True
                    email_obj.ai_response = ai_response
                    email_obj.save()
                    
                    logger.info(f"Auto-replied to {email_obj.sender}")
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")

# Background task runner
async def run_email_automation():
    """Run email automation for all active accounts"""
    accounts = EmailAccount.objects.filter(auto_reply_enabled=True, is_active=True)
    
    for account in accounts:
        try:
            service = EmailService(account)
            await service.process_new_emails()
        except Exception as e:
            logger.error(f"Error in automation for {account.email_address}: {e}")

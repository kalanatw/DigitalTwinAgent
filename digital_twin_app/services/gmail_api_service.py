"""
Gmail API Service for Digital Twin App

This service handles Gmail API interactions following Google's documentation
standards and best practices.
"""
import base64
import logging
from typing import Dict, List, Optional, Tuple

import requests
from django.conf import settings
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GmailAPIService:
    """
    Gmail API service following Google's documentation standards.
    
    Handles OAuth2 authentication, token management, and Gmail API operations
    with proper error handling and rate limiting consideration.
    """
    
    def __init__(self, access_token: str, refresh_token: str = None):
        """
        Initialize Gmail API service with OAuth2 credentials.
        
        Args:
            access_token: OAuth2 access token for Gmail API
            refresh_token: OAuth2 refresh token for token renewal
            
        Raises:
            ValueError: If access_token is None or empty
        """
        if not access_token:
            raise ValueError("Access token is required")
            
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.service = None
        self._build_service()
    
    def _build_service(self) -> None:
        """
        Build Gmail API service instance with credentials.
        
        Creates OAuth2 credentials and initializes the Gmail API service
        with proper scopes and error handling.
        """
        try:
            # Create credentials object
            credentials = Credentials(
                token=self.access_token,
                refresh_token=self.refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=settings.GOOGLE_OAUTH_CONFIG['web']['client_id'],
                client_secret=settings.GOOGLE_OAUTH_CONFIG['web']['client_secret'],
                scopes=[
                    'https://www.googleapis.com/auth/gmail.readonly',
                    'https://www.googleapis.com/auth/gmail.labels'
                ]
            )
            
            # Refresh token if expired
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self.access_token = credentials.token
                logger.info("Gmail API credentials refreshed successfully")
            
            # Build Gmail service
            self.service = build('gmail', 'v1', credentials=credentials)
            logger.info("Gmail API service initialized successfully")
            
        except Exception as error:
            logger.error(f"Error building Gmail API service: {error}")
            raise
    
    def get_user_profile(self) -> Optional[Dict]:
        """
        Get Gmail user profile information.
        
        Returns:
            Dict containing user profile data or None if error occurs
            Format: {
                'emailAddress': str,
                'messagesTotal': int,
                'threadsTotal': int,
                'historyId': str
            }
        """
        try:
            if not self.service:
                logger.error("Gmail service not initialized")
                return None
                
            profile = self.service.users().getProfile(userId='me').execute()
            logger.info(f"Retrieved profile for user: {profile.get('emailAddress')}")
            return profile
            
        except HttpError as error:
            logger.error(f"HTTP error getting user profile: {error}")
            if error.resp.status == 401:
                logger.warning("Gmail API authentication failed - token may be expired")
            return None
        except Exception as error:
            logger.error(f"Unexpected error getting user profile: {error}")
            return None
    
    def list_messages(
        self, 
        max_results: int = 10, 
        query: str = '',
        page_token: str = None
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        List messages from user's Gmail inbox.
        
        Args:
            max_results: Maximum number of messages to return (1-500)
            query: Gmail search query string (e.g., 'is:unread', 'from:example@gmail.com')
            page_token: Token for pagination
            
        Returns:
            Tuple of (messages_list, next_page_token)
            
        Raises:
            ValueError: If max_results is out of valid range
        """
        if not (1 <= max_results <= 500):
            raise ValueError("max_results must be between 1 and 500")
            
        try:
            if not self.service:
                logger.error("Gmail service not initialized")
                return [], None
            
            # Build request parameters
            request_params = {
                'userId': 'me',
                'maxResults': max_results
            }
            
            if query:
                request_params['q'] = query
            if page_token:
                request_params['pageToken'] = page_token
            
            # Execute API request
            result = self.service.users().messages().list(**request_params).execute()
            
            messages = result.get('messages', [])
            next_page_token = result.get('nextPageToken')
            
            # Get detailed message information
            detailed_messages = []
            for message in messages:
                message_detail = self.get_message(message['id'])
                if message_detail:
                    detailed_messages.append(message_detail)
            
            logger.info(f"Retrieved {len(detailed_messages)} messages from Gmail")
            return detailed_messages, next_page_token
            
        except HttpError as error:
            logger.error(f"HTTP error listing messages: {error}")
            self._handle_api_error(error)
            return [], None
        except Exception as error:
            logger.error(f"Unexpected error listing messages: {error}")
            return [], None
    
    def get_message(self, message_id: str) -> Optional[Dict]:
        """
        Get detailed message information by ID.
        
        Args:
            message_id: Gmail message ID
            
        Returns:
            Dict containing parsed message data or None if error occurs
            Format: {
                'id': str,
                'thread_id': str,
                'subject': str,
                'from': str,
                'to': str,
                'date': str,
                'body_text': str,
                'body_html': str,
                'snippet': str,
                'labels': List[str],
                'is_unread': bool
            }
        """
        try:
            if not self.service:
                logger.error("Gmail service not initialized")
                return None
            
            # Get message with full format to access headers and body
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            return self._parse_message(message)
            
        except HttpError as error:
            logger.error(f"HTTP error getting message {message_id}: {error}")
            self._handle_api_error(error)
            return None
        except Exception as error:
            logger.error(f"Unexpected error getting message {message_id}: {error}")
            return None
    
    def _parse_message(self, message_data: Dict) -> Dict:
        """
        Parse Gmail API message data into readable format.
        
        Args:
            message_data: Raw message data from Gmail API
            
        Returns:
            Dict containing parsed message information
        """
        try:
            # Extract basic message info
            message_id = message_data.get('id', '')
            thread_id = message_data.get('threadId', '')
            snippet = message_data.get('snippet', '')
            labels = message_data.get('labelIds', [])
            
            # Check if message is unread
            is_unread = 'UNREAD' in labels
            
            # Extract headers
            payload = message_data.get('payload', {})
            headers = payload.get('headers', [])
            
            header_dict = {h['name'].lower(): h['value'] for h in headers}
            
            subject = header_dict.get('subject', 'No Subject')
            from_email = header_dict.get('from', 'Unknown Sender')
            to_email = header_dict.get('to', 'Unknown Recipient')
            date = header_dict.get('date', 'Unknown Date')
            
            # Extract message body
            body_text, body_html = self._extract_message_body(payload)
            
            return {
                'id': message_id,
                'thread_id': thread_id,
                'subject': subject,
                'from': from_email,
                'to': to_email,
                'date': date,
                'body_text': body_text,
                'body_html': body_html,
                'snippet': snippet,
                'labels': labels,
                'is_unread': is_unread
            }
            
        except Exception as error:
            logger.error(f"Error parsing message: {error}")
            return {}
    
    def _extract_message_body(self, payload: Dict) -> Tuple[str, str]:
        """
        Extract text and HTML body from message payload.
        
        Args:
            payload: Message payload from Gmail API
            
        Returns:
            Tuple of (text_body, html_body)
        """
        body_text = ""
        body_html = ""
        
        try:
            # Handle multipart messages
            if 'parts' in payload:
                for part in payload['parts']:
                    mime_type = part.get('mimeType', '')
                    
                    if mime_type == 'text/plain':
                        body_text = self._decode_body_data(
                            part.get('body', {}).get('data', '')
                        )
                    elif mime_type == 'text/html':
                        body_html = self._decode_body_data(
                            part.get('body', {}).get('data', '')
                        )
                    elif mime_type.startswith('multipart/'):
                        # Handle nested multipart messages
                        nested_text, nested_html = self._extract_message_body(part)
                        if not body_text and nested_text:
                            body_text = nested_text
                        if not body_html and nested_html:
                            body_html = nested_html
            
            # Handle single part messages
            elif payload.get('mimeType') == 'text/plain':
                body_text = self._decode_body_data(
                    payload.get('body', {}).get('data', '')
                )
            elif payload.get('mimeType') == 'text/html':
                body_html = self._decode_body_data(
                    payload.get('body', {}).get('data', '')
                )
            
            # Fallback to snippet if no body found
            if not body_text and not body_html:
                body_text = "Could not extract message body"
            
        except Exception as error:
            logger.error(f"Error extracting message body: {error}")
            body_text = "Error reading message body"
        
        return body_text, body_html
    
    def _decode_body_data(self, data: str) -> str:
        """
        Decode base64url encoded body data.
        
        Args:
            data: Base64url encoded string
            
        Returns:
            Decoded string content
        """
        try:
            if not data:
                return ""
            
            # Add padding if needed for base64 decoding
            data += '=' * (4 - len(data) % 4)
            
            # Decode base64url
            decoded_bytes = base64.urlsafe_b64decode(data.encode('utf-8'))
            return decoded_bytes.decode('utf-8', errors='replace')
            
        except Exception as error:
            logger.error(f"Error decoding body data: {error}")
            return "Error decoding message content"
    
    def _handle_api_error(self, error: HttpError) -> None:
        """
        Handle Gmail API errors with appropriate logging and responses.
        
        Args:
            error: HttpError from Gmail API
        """
        if error.resp.status == 401:
            logger.warning("Gmail API authentication failed - token expired")
        elif error.resp.status == 403:
            logger.warning("Gmail API access forbidden - quota exceeded or insufficient permissions")
        elif error.resp.status == 404:
            logger.info("Gmail resource not found")
        elif error.resp.status == 429:
            logger.warning("Gmail API rate limit exceeded")
        else:
            logger.error(f"Gmail API error {error.resp.status}: {error}")
    
    def search_messages(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Search messages using Gmail query syntax.
        
        Args:
            query: Gmail search query (e.g., 'from:user@example.com subject:important')
            max_results: Maximum number of results to return
            
        Returns:
            List of matching messages
        """
        try:
            messages, _ = self.list_messages(
                max_results=max_results,
                query=query
            )
            
            logger.info(f"Search query '{query}' returned {len(messages)} results")
            return messages
            
        except Exception as error:
            logger.error(f"Error searching messages: {error}")
            return []

"""
Email Formatting Utilities for Professional Email Responses
"""
import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class EmailFormatter:
    """Professional email formatter for agent responses"""
    
    @staticmethod
    def format_agent_response_to_email(agent_response: str, sender_name: str = "Digital Assets Manager") -> Dict[str, str]:
        """
        Convert agent markdown/text response to professional HTML email format
        
        Args:
            agent_response: Raw response from the agent
            sender_name: Name of the sender
            
        Returns:
            Dictionary with 'subject', 'text_body', and 'html_body'
        """
        try:
            # Clean up the response
            cleaned_response = EmailFormatter._clean_agent_response(agent_response)
            
            # Extract subject if present
            subject = EmailFormatter._extract_subject(cleaned_response)
            
            # Generate text and HTML versions
            text_body = EmailFormatter._convert_to_text(cleaned_response)
            html_body = EmailFormatter._convert_to_html(cleaned_response, sender_name)
            
            return {
                'subject': subject,
                'text_body': text_body,
                'html_body': html_body
            }
            
        except Exception as e:
            logger.error(f"Error formatting email response: {e}")
            # Fallback to simple formatting
            return {
                'subject': 'Digital Assets - Response to Your Inquiry',
                'text_body': agent_response,
                'html_body': EmailFormatter._simple_html_wrapper(agent_response, sender_name)
            }
    
    @staticmethod
    def _clean_agent_response(response: str) -> str:
        """Clean up agent response, removing system messages and formatting"""
        # Remove common AI assistant phrases
        response = re.sub(r'^(Here\'s a professional response|I\'ll help you|Let me provide)', '', response, flags=re.IGNORECASE)
        response = re.sub(r'^---+\s*$', '', response, flags=re.MULTILINE)
        response = re.sub(r'^\*\*Subject:\*\*\s*', 'Subject: ', response, flags=re.MULTILINE | re.IGNORECASE)
        
        # Clean up excessive markdown
        response = re.sub(r'\*\*([^*]+)\*\*', r'\1', response)  # Remove bold markdown
        response = re.sub(r'\*([^*]+)\*', r'\1', response)      # Remove italic markdown
        
        # Clean up extra whitespace
        response = re.sub(r'\n\n\n+', '\n\n', response)
        response = response.strip()
        
        return response
    
    @staticmethod
    def _extract_subject(response: str) -> str:
        """Extract subject line from response"""
        # Look for subject line patterns
        subject_patterns = [
            r'^Subject:\s*(.+)$',
            r'^\*\*Subject:\*\*\s*(.+)$',
            r'^# (.+)$'
        ]
        
        lines = response.split('\n')
        for line in lines[:3]:  # Check first 3 lines
            for pattern in subject_patterns:
                match = re.match(pattern, line.strip(), re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        
        # Default subject
        return 'Digital Assets - Response to Your Inquiry'
    
    @staticmethod
    def _convert_to_text(response: str) -> str:
        """Convert response to plain text format"""
        # Remove subject line if present
        lines = response.split('\n')
        if lines and ('subject:' in lines[0].lower() or lines[0].startswith('#')):
            lines = lines[1:]
        
        text = '\n'.join(lines).strip()
        
        # Clean up markdown artifacts
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        return text
    
    @staticmethod
    def _convert_to_html(response: str, sender_name: str) -> str:
        """Convert response to professional HTML email format"""
        # Remove subject line if present
        lines = response.split('\n')
        if lines and ('subject:' in lines[0].lower() or lines[0].startswith('#')):
            lines = lines[1:]
        
        content = '\n'.join(lines).strip()
        
        # Convert markdown-style formatting to HTML
        content = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', content)
        content = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', content)
        content = re.sub(r'`([^`]+)`', r'<code>\1</code>', content)
        
        # Convert bullet points
        content = re.sub(r'^[-•]\s*(.+)$', r'<li>\1</li>', content, flags=re.MULTILINE)
        content = re.sub(r'(<li>.*?</li>)', r'<ul>\n\1\n</ul>', content, flags=re.DOTALL)
        content = re.sub(r'</ul>\s*<ul>', '', content)  # Merge consecutive lists
        
        # Convert line breaks to paragraphs
        paragraphs = content.split('\n\n')
        html_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if para:
                if '<ul>' in para or '<li>' in para:
                    html_paragraphs.append(para)
                else:
                    # Regular paragraph
                    para = para.replace('\n', '<br>')
                    html_paragraphs.append(f'<p>{para}</p>')
        
        body_content = '\n'.join(html_paragraphs)
        
        # Create professional HTML email
        html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Digital Assets Response</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f8f9fa;
        }}
        .email-container {{
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            border-bottom: 2px solid #0066cc;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        .company-name {{
            color: #0066cc;
            font-size: 18px;
            font-weight: bold;
            margin: 0;
        }}
        .content {{
            margin-bottom: 30px;
        }}
        .content p {{
            margin-bottom: 15px;
        }}
        .content ul {{
            margin: 15px 0;
            padding-left: 20px;
        }}
        .content li {{
            margin-bottom: 8px;
        }}
        .signature {{
            border-top: 1px solid #eee;
            padding-top: 20px;
            margin-top: 30px;
        }}
        .signature-name {{
            font-weight: bold;
            color: #0066cc;
            margin-bottom: 5px;
        }}
        .signature-title {{
            color: #666;
            font-size: 14px;
            margin-bottom: 3px;
        }}
        .contact-info {{
            font-size: 12px;
            color: #888;
            margin-top: 10px;
        }}
        strong {{
            color: #0066cc;
        }}
        code {{
            background-color: #f1f1f1;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <div class="company-name">AAS Digital Assets</div>
        </div>
        
        <div class="content">
            {body_content}
        </div>
        
        <div class="signature">
            <div class="signature-name">{sender_name}</div>
            <div class="signature-title">Digital Assets Manager</div>
            <div class="signature-title">AAS Digital Assets</div>
            <div class="contact-info">
                📞 +61-2-9000-0001 | ✉️ manager@aasdigitalassets.com.au
            </div>
        </div>
    </div>
</body>
</html>
"""
        
        return html_template.strip()
    
    @staticmethod
    def _simple_html_wrapper(content: str, sender_name: str) -> str:
        """Simple HTML wrapper for fallback"""
        content_html = content.replace('\n', '<br>')
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .signature {{ margin-top: 20px; border-top: 1px solid #ccc; padding-top: 10px; }}
    </style>
</head>
<body>
    <div>
        {content_html}
    </div>
    <div class="signature">
        <strong>{sender_name}</strong><br>
        Digital Assets Manager<br>
        AAS Digital Assets<br>
        📞 +61-2-9000-0001 | ✉️ manager@aasdigitalassets.com.au
    </div>
</body>
</html>
"""

"""
Digital Twin Agent Configuration and Management
"""
import logging
import asyncio
import os
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.cache import cache
from agents import Agent, Runner, set_default_openai_key
from .email_tools import email_template_selector, list_email_templates, analyze_email_content

logger = logging.getLogger(__name__)

# Set OpenAI API key from Django settings
if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
    api_key = settings.OPENAI_API_KEY
    logger.info(f"OpenAI API key configured from Django settings: {api_key[:10]}...{api_key[-10:]}")
    set_default_openai_key(api_key)
else:
    logger.warning("No OpenAI API key found in Django settings")


class DigitalAssetsManagerAgent:
    """
    Digital Assets Manager Agent for handling email communications and client inquiries.
    """
    
    def __init__(self):
        """Initialize the Digital Assets Manager Agent with email tools and configuration."""
        self.agent = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the OpenAI agent with appropriate instructions and tools."""
        logger.info("Initializing Digital Assets Manager Agent")
        
        instructions = """
        You are a Digital Assets Manager specialized in professional email communications and client relationship management.
        
        Your role is to:
        1. Intelligently detect when a user's message is an email that requires a professional response
        2. Analyze email content to determine the most appropriate template for response
        3. Select and format appropriate email templates for various business scenarios
        4. Provide general assistance and information about digital assets and financial services
        
        When a user sends what appears to be an email (contains business inquiries, requests for information, 
        mentions of meetings, market updates, portfolio questions, etc.), you should:
        1. Use analyze_email_content to understand the email context
        2. Use email_template_selector to choose and format an appropriate response
        3. Present the formatted email response in markdown format
        
        Available email template types:
        - tariff_impact_analysis: For market analysis and economic impact discussions
        - event_reminder: For event notifications and meeting reminders
        - portfolio_update: For portfolio performance and investment updates
        - market_alert: For urgent market notifications and alerts
        - meeting_request: For scheduling meetings and consultations
        - client_onboarding: For welcoming new clients
        
        For general inquiries that are not emails, provide helpful information about:
        - Digital assets management
        - Investment strategies
        - Market analysis
        - Financial planning
        - Professional services
        
        Always maintain a professional, knowledgeable, and client-focused tone.
        """
        
        try:
            self.agent = Agent(
                name="Digital Assets Manager",
                instructions=instructions,
                tools=[email_template_selector, list_email_templates, analyze_email_content],
                model=getattr(settings, 'AGENT_MODEL', 'gpt-4o-mini')
            )
            logger.info("Digital Assets Manager Agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Digital Assets Manager Agent: {e}")
            raise
    
    async def process_message(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        Process a user message and return the agent's response.
        Intelligently detects emails and uses appropriate templates for responses.
        
        Args:
            message: User's input message
            session_id: Unique session identifier for conversation tracking
            
        Returns:
            Dictionary containing the response and metadata
        """
        logger.info(f"Processing message for session {session_id}: {message[:100]}...")
        
        try:
            # Get conversation history from cache
            conversation_key = f"conversation:{session_id}"
            conversation_history = cache.get(conversation_key, [])
            
            # Add user message to history
            conversation_history.append({"role": "user", "content": message})
            
            # Check if this looks like an email that needs a template response
            enhanced_message = await self._enhance_message_for_email_detection(message)
            
            # Run the agent with conversation context
            result = await Runner.run(
                self.agent,
                input=enhanced_message,
                max_turns=getattr(settings, 'AGENT_MAX_TURNS', 20)
            )
            
            # Extract the final response
            response_content = result.final_output if hasattr(result, 'final_output') else str(result)
            
            # Add agent response to history
            conversation_history.append({"role": "assistant", "content": response_content})
            
            # Cache the updated conversation (expire after 1 hour)
            cache.set(conversation_key, conversation_history, 3600)
            
            logger.info(f"Successfully processed message for session {session_id}")
            
            return {
                "response": response_content,
                "session_id": session_id,
                "status": "success",
                "metadata": {
                    "model": getattr(settings, 'AGENT_MODEL', 'gpt-4o-mini'),
                    "tools_used": self._extract_tools_used(result),
                    "conversation_length": len(conversation_history),
                    "agent_type": "digital_assets_manager"
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing message for session {session_id}: {e}")
            return {
                "response": "I apologize, but I encountered an error while processing your request. Please try again.",
                "session_id": session_id,
                "status": "error",
                "error": str(e)
            }

    async def process_message_with_documents(self, message: str, session_id: str, twin_version_id: str) -> Dict[str, Any]:
        """
        Process a user message with document context from a specific twin version.
        Intelligently detects emails and uses appropriate templates for responses.
        
        Args:
            message: User's input message
            session_id: Unique session identifier for conversation tracking
            twin_version_id: Twin version ID to search for relevant documents
            
        Returns:
            Dictionary containing the response and metadata including document context
        """
        logger.info(f"Processing message with documents for session {session_id}, twin version {twin_version_id}: {message[:100]}...")
        
        try:
            # Get document context
            from .document_utils import SemanticSearch
            semantic_search = SemanticSearch()
            
            # Search for relevant documents
            document_results = await semantic_search.search_documents(
                query=message,
                twin_version_id=twin_version_id,
                top_k=5
            )
            
            # Prepare document context for the agent
            document_context = ""
            document_info = []
            
            if document_results:
                context_parts = []
                for result in document_results:
                    context_part = f"[From: {result['title']}]\n{result['content']}\n"
                    context_parts.append(context_part)
                    document_info.append({
                        'title': result['title'],
                        'similarity': result['similarity']
                    })
                
                document_context = "\n".join(context_parts)
                
                # Enhance the message with document context and email detection
                enhanced_message = await self._enhance_message_for_email_detection(message)
                enhanced_message = f"""
Context from uploaded documents:
{document_context}

{enhanced_message}

Please answer using the provided document context when relevant. If the documents contain relevant information, reference them in your response. If this appears to be an email requiring a template response, use the appropriate email tools to construct a professional reply.
"""
            else:
                enhanced_message = await self._enhance_message_for_email_detection(message)
            
            # Get conversation history from cache
            conversation_key = f"conversation:{session_id}"
            conversation_history = cache.get(conversation_key, [])
            
            # Add user message to history
            conversation_history.append({"role": "user", "content": message})
            
            # Run the agent with enhanced message
            result = await Runner.run(
                self.agent,
                input=enhanced_message,
                max_turns=getattr(settings, 'AGENT_MAX_TURNS', 20)
            )
            
            # Extract the final response
            response_content = result.final_output if hasattr(result, 'final_output') else str(result)
            
            # Add agent response to history
            conversation_history.append({"role": "assistant", "content": response_content})
            
            # Cache the updated conversation (expire after 1 hour)
            cache.set(conversation_key, conversation_history, 3600)
            
            logger.info(f"Successfully processed message with documents for session {session_id}")
            
            return {
                "response": response_content,
                "session_id": session_id,
                "status": "success",
                "metadata": {
                    "model": getattr(settings, 'AGENT_MODEL', 'gpt-4o-mini'),
                    "tools_used": self._extract_tools_used(result),
                    "conversation_length": len(conversation_history),
                    "document_context": document_info,
                    "documents_found": len(document_results),
                    "agent_type": "digital_assets_manager"
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing message with documents for session {session_id}: {e}")
            return {
                "response": "I apologize, but I encountered an error while processing your request. Please try again.",
                "session_id": session_id,
                "status": "error",
                "error": str(e)
            }
            
            # Prepare document context for the agent
            document_context = ""
            document_info = []
            
            if document_results:
                context_parts = []
                for result in document_results:
                    context_part = f"[From: {result['title']}]\n{result['content']}\n"
                    context_parts.append(context_part)
                    document_info.append({
                        'title': result['title'],
                        'similarity': result['similarity']
                    })
                
                document_context = "\n".join(context_parts)
                
                # Enhance the message with document context
                enhanced_message = f"""
Context from uploaded documents:
{document_context}

User question: {message}

Please answer the user's question using the provided document context when relevant. If the documents contain relevant information, reference them in your response. If the documents don't contain relevant information for this question, answer based on your general knowledge about digital twins and industrial systems.
"""
            else:
                enhanced_message = message
            
            # Get conversation history from cache
            conversation_key = f"conversation:{session_id}"
            conversation_history = cache.get(conversation_key, [])
            
            # Add user message to history
            conversation_history.append({"role": "user", "content": message})
            
            # Run the agent with enhanced message
            result = await Runner.run(
                self.agent,
                input=enhanced_message,
                max_turns=getattr(settings, 'AGENT_MAX_TURNS', 20)
            )
            
            # Extract the final response
            response_content = result.final_output if hasattr(result, 'final_output') else str(result)
            
            # Add agent response to history
            conversation_history.append({"role": "assistant", "content": response_content})
            
            # Cache the updated conversation (expire after 1 hour)
            cache.set(conversation_key, conversation_history, 3600)
            
            logger.info(f"Successfully processed message with documents for session {session_id}")
            
            return {
                "response": response_content,
                "session_id": session_id,
                "status": "success",
                "metadata": {
                    "model": getattr(settings, 'AGENT_MODEL', 'gpt-4o-mini'),
                    "tools_used": self._extract_tools_used(result),
                    "conversation_length": len(conversation_history),
                    "document_context": document_info,
                    "documents_found": len(document_results)
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing message with documents for session {session_id}: {e}")
            return {
                "response": "I apologize, but I encountered an error while processing your request. Please try again.",
                "session_id": session_id,
                "status": "error",
                "error": str(e)
            }
    
    async def _enhance_message_for_email_detection(self, message: str) -> str:
        """
        Enhance the message with context to help the agent detect if it's an email requiring a template response.
        
        Args:
            message: Original user message
            
        Returns:
            Enhanced message with email detection guidance
        """
        # Check for email indicators
        email_indicators = [
            "dear", "hi", "hello", "regards", "sincerely", "best regards", "kind regards",
            "meeting", "appointment", "schedule", "portfolio", "market", "investment",
            "tariff", "event", "reminder", "update", "alert", "welcome", "onboard",
            "subject:", "to:", "from:", "cc:", "bcc:", "@", ".com", ".au"
        ]
        
        message_lower = message.lower()
        email_score = sum(1 for indicator in email_indicators if indicator in message_lower)
        
        # If it looks like an email (contains multiple indicators), add guidance
        if email_score >= 2 or len(message) > 100:
            enhanced_message = f"""
IMPORTANT: Analyze this message to determine if it appears to be an email that requires a professional template response.

Email indicators detected: {email_score}/20

If this looks like:
1. A business inquiry or request for information
2. A meeting request or scheduling message  
3. A market update or portfolio question
4. An event notification or reminder
5. Any professional correspondence requiring a formal response

Then:
1. First use 'analyze_email_content' to understand the context
2. Then use 'email_template_selector' to choose and format an appropriate response
3. Present the formatted email response clearly in markdown format

User message: {message}
"""
        else:
            enhanced_message = f"""
This appears to be a general inquiry about digital assets management. Provide helpful information and assistance.

User message: {message}
"""
        
        return enhanced_message
    
    def _extract_tools_used(self, result) -> list:
        """Extract information about tools used during agent execution."""
        tools_used = []
        try:
            # This would depend on the specific structure of the result object
            # from the OpenAI Agents SDK
            if hasattr(result, 'tool_calls'):
                for tool_call in result.tool_calls:
                    tools_used.append(tool_call.function.name)
        except Exception:
            pass
        return tools_used
    
    async def get_conversation_history(self, session_id: str) -> list:
        """
        Retrieve conversation history for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            List of conversation messages
        """
        conversation_key = f"conversation:{session_id}"
        return cache.get(conversation_key, [])
    
    async def clear_conversation(self, session_id: str) -> bool:
        """
        Clear conversation history for a session.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conversation_key = f"conversation:{session_id}"
            cache.delete(conversation_key)
            logger.info(f"Cleared conversation for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing conversation for session {session_id}: {e}")
            return False


# Global agent instance
_agent_instance: Optional[DigitalAssetsManagerAgent] = None


def get_agent_instance() -> DigitalAssetsManagerAgent:
    """Get or create the global agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DigitalAssetsManagerAgent()
    return _agent_instance

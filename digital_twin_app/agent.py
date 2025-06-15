"""
Digital Twin Agent Configuration and Management
"""
import logging
import asyncio
import os
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.cache import cache
from asgiref.sync import sync_to_async
from agents import Agent, Runner, set_default_openai_key
from .email_tools import email_template_selector, list_email_templates, analyze_email_content

logger = logging.getLogger(__name__)

# Configure OpenAI API key from Django settings
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
    
    def __init__(self, custom_config=None):
        """Initialize the Digital Assets Manager Agent with email tools and configuration."""
        self.agent = None
        self.custom_config = custom_config
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the OpenAI agent with appropriate instructions and tools."""
        logger.info("Initializing Digital Assets Manager Agent")
        
        # Import all available tools at the beginning
        from .email_tools import email_template_selector, list_email_templates, analyze_email_content
        from .tools import sensor_data_tool, system_status_tool
        
        # Use custom config if provided, otherwise use defaults
        if self.custom_config:
            instructions = self.custom_config.get('instructions', '')
            model = self.custom_config.get('model', 'gpt-4o-mini')
            agent_name = self.custom_config.get('name', 'Digital Assets Manager')
            tools_enabled = self.custom_config.get('tools_enabled', [])
            
            # Create available tools map
            available_tools_map = {
                'email_template_selector': email_template_selector,
                'list_email_templates': list_email_templates,
                'analyze_email_content': analyze_email_content,
                'sensor_data_tool': sensor_data_tool,
                'system_status_tool': system_status_tool,
            }
            
            # Build tools list for this agent
            agent_tools = []
            for tool_name in tools_enabled:
                if tool_name in available_tools_map:
                    agent_tools.append(available_tools_map[tool_name])
                    logger.info(f"Added tool: {tool_name}")
            
            # If no tools specified, use default based on agent type/name
            if not agent_tools:
                if 'digital twin' in agent_name.lower() or 'twin' in agent_name.lower():
                    # Default tools for digital twin agents
                    agent_tools = [sensor_data_tool, system_status_tool]
                    logger.info("Using default digital twin tools: sensor_data_tool, system_status_tool")
                else:
                    # Default tools for other agents
                    agent_tools = [email_template_selector, list_email_templates, analyze_email_content]
                    logger.info("Using default email tools")
                
        else:
            # Default configuration
            model = getattr(settings, 'AGENT_MODEL', 'gpt-4o-mini')
            agent_name = "Digital Assets Manager"
            agent_tools = [email_template_selector, list_email_templates, analyze_email_content]
            instructions = """
You are a Digital Assets Manager specialized in professional email communications and client relationship management.

Your role is to:
1. Intelligently detect when a user's message is an email that requires a professional response
2. Analyze email content to determine the most appropriate template for response
3. Select and format appropriate email templates for various business scenarios
4. Provide general assistance and information about digital assets and financial services

When a user sends what appears to be an email (contains business inquiries, requests for information,
professional correspondence, or formal communications), you should:
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
                name=agent_name,
                instructions=instructions,
                tools=agent_tools,
                model=model
            )
            
            logger.info(f"Digital Assets Manager Agent initialized successfully: {agent_name}")
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
            # Enhance the message with email detection context
            enhanced_message = await self._enhance_message_for_email_detection(message)
            
            # Get conversation history from cache (using sync_to_async)
            conversation_key = f"conversation:{session_id}"
            conversation_history = await sync_to_async(cache.get)(conversation_key, [])
            
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
            
            # Cache the updated conversation (expire after 1 hour) using sync_to_async
            await sync_to_async(cache.set)(conversation_key, conversation_history, 3600)
            
            logger.info(f"Successfully processed message for session {session_id}")
            
            # Get agent type from custom config if available
            agent_type = "digital_assets_manager"  # default
            agent_name = "Digital Assets Manager"  # default
            
            if self.custom_config:
                agent_type = self.custom_config.get('type', 'custom')
                agent_name = self.custom_config.get('name', 'Custom Agent')
                logger.info(f"Using custom agent metadata: type={agent_type}, name={agent_name}")
            
            return {
                "response": response_content,
                "session_id": session_id,
                "status": "success",
                "metadata": {
                    "model": self.custom_config.get('model', getattr(settings, 'AGENT_MODEL', 'gpt-4o-mini')) if self.custom_config else getattr(settings, 'AGENT_MODEL', 'gpt-4o-mini'),
                    "tools_used": self._extract_tools_used(result),
                    "conversation_length": len(conversation_history),
                    "agent_type": agent_type,
                    "agent_name": agent_name
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
                
                enhanced_message = f"""
Context from uploaded documents:
{document_context}

User message: {message}

Please answer using the provided document context when relevant. If the documents contain relevant information, reference them in your response. If this appears to be an email requiring a template response, use the appropriate email tools to construct a professional reply.
"""
            else:
                enhanced_message = await self._enhance_message_for_email_detection(message)
            
            # Get conversation history from cache
            conversation_key = f"conversation:{session_id}"
            conversation_history = await sync_to_async(cache.get)(conversation_key, [])
            
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
            await sync_to_async(cache.set)(conversation_key, conversation_history, 3600)
            
            logger.info(f"Successfully processed message with documents for session {session_id}")
            
            # Get agent type from custom config if available
            agent_type = "digital_assets_manager"  # default
            agent_name = "Digital Assets Manager"  # default
            
            if self.custom_config:
                agent_type = self.custom_config.get('type', 'custom')
                agent_name = self.custom_config.get('name', 'Custom Agent')
                logger.info(f"Using custom agent metadata: type={agent_type}, name={agent_name}")
            
            return {
                "response": response_content,
                "session_id": session_id,
                "status": "success",
                "metadata": {
                    "model": self.custom_config.get('model', getattr(settings, 'AGENT_MODEL', 'gpt-4o-mini')) if self.custom_config else getattr(settings, 'AGENT_MODEL', 'gpt-4o-mini'),
                    "tools_used": self._extract_tools_used(result),
                    "conversation_length": len(conversation_history),
                    "document_context": document_info,
                    "agent_type": agent_type,
                    "agent_name": agent_name
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
        Enhance message to detect emails and provide guidance for template usage.
        
        Args:
            message: Original user message
            
        Returns:
            Enhanced message with email context
        """
        # Check for email indicators
        email_indicators = [
            "dear", "hi", "hello", "regards", "sincerely", "best regards", "kind regards",
            "meeting", "appointment", "schedule", "portfolio", "market", "investment",
            "tariff", "event", "reminder", "update", "alert", "welcome", "onboard",
            "inquiry", "request", "client", "business", "professional"
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
        return await sync_to_async(cache.get)(conversation_key, [])
    
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
            await sync_to_async(cache.delete)(conversation_key)
            logger.info(f"Cleared conversation for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error clearing conversation for session {session_id}: {e}")
            return False


# Global agent instance
_agent_instance: Optional[DigitalAssetsManagerAgent] = None


def clear_agent_cache():
    """Clear the global agent instance to force fresh loading."""
    global _agent_instance
    _agent_instance = None
    logger.info("🗑️ Cleared global agent instance cache")


def get_agent_instance(user_id=None) -> DigitalAssetsManagerAgent:
    """Get or create the global agent instance (simplified version without cache to avoid async context issues)."""
    global _agent_instance
    
    # For synchronous contexts, always return the default agent to avoid cache issues
    # User-specific agents should be accessed via get_agent_instance_async
    if _agent_instance is None:
        _agent_instance = DigitalAssetsManagerAgent()
    return _agent_instance


# Async version for use in async contexts
async def get_agent_instance_async(user_id=None) -> DigitalAssetsManagerAgent:
    """Async version of get_agent_instance for use in async contexts with database loading."""
    global _agent_instance
    
    logger.info(f"=== AGENT LOADING DEBUG ===")
    logger.info(f"Requested agent for user_id: {user_id}")
    
    # If user_id is provided, try to load agent configuration from database
    if user_id:
        try:
            # Import the model inside the function to avoid import issues
            from .models import AgentConfiguration
            
            logger.info(f"Querying database for agent configurations...")
            
            # Try to get user-specific active configuration first
            try:
                user_config = await sync_to_async(
                    AgentConfiguration.objects.filter(
                        created_by_id=user_id,
                        is_active=True
                    ).first
                )()
                
                if user_config:
                    logger.info(f"Found USER-SPECIFIC agent config: {user_config.name} (ID: {user_config.id})")
                    config = await _convert_db_config_to_dict(user_config)
                    agent = DigitalAssetsManagerAgent(custom_config=config)
                    logger.info(f"✅ Created agent from USER-SPECIFIC database config: {user_config.name}")
                    return agent
                else:
                    logger.info(f"No user-specific agent config found for user {user_id}")
            except Exception as e:
                logger.error(f"Error querying user-specific agent config: {e}")
            
            # Try to get system default configuration
            try:
                system_config = await sync_to_async(
                    AgentConfiguration.objects.filter(
                        is_active=True,
                        is_default=True
                    ).first
                )()
                
                if system_config:
                    logger.info(f"Found SYSTEM DEFAULT agent config: {system_config.name} (ID: {system_config.id})")
                    config = await _convert_db_config_to_dict(system_config)
                    agent = DigitalAssetsManagerAgent(custom_config=config)
                    logger.info(f"✅ Created agent from SYSTEM DEFAULT database config: {system_config.name}")
                    return agent
                else:
                    logger.info(f"No system default agent config found")
            except Exception as e:
                logger.error(f"Error querying system default agent config: {e}")
            
            # Try to get any active configuration
            try:
                any_config = await sync_to_async(
                    AgentConfiguration.objects.filter(
                        is_active=True
                    ).first
                )()
                
                if any_config:
                    logger.info(f"Found ANY ACTIVE agent config: {any_config.name} (ID: {any_config.id})")
                    config = await _convert_db_config_to_dict(any_config)
                    agent = DigitalAssetsManagerAgent(custom_config=config)
                    logger.info(f"✅ Created agent from ANY ACTIVE database config: {any_config.name}")
                    return agent
                else:
                    logger.info(f"No active agent configurations found in database")
            except Exception as e:
                logger.error(f"Error querying any active agent config: {e}")
                
        except Exception as e:
            logger.error(f"Error loading agent configuration from database: {e}")
            logger.error(f"Traceback: ", exc_info=True)
    
    # Fall back to global default agent
    logger.info(f"🔄 Falling back to DEFAULT agent configuration")
    try:
        if _agent_instance is None:
            _agent_instance = DigitalAssetsManagerAgent()
            logger.info(f"✅ Created default Digital Assets Manager agent instance")
        else:
            logger.info(f"✅ Using existing default agent instance")
        
        return _agent_instance
    except Exception as e:
        logger.error(f"Error creating default agent: {e}")
        logger.error(f"Traceback: ", exc_info=True)
        raise


def get_agent_instance_sync(user_id=None) -> DigitalAssetsManagerAgent:
    """Synchronous version of agent loading as a fallback for async context issues."""
    logger.info(f"=== SYNC AGENT LOADING FALLBACK ===")
    logger.info(f"Requested agent for user_id: {user_id} (sync mode)")
    
    # If user_id is provided, try to load agent configuration from database
    if user_id:
        try:
            # Import the model inside the function to avoid import issues
            from .models import AgentConfiguration
            
            logger.info(f"Querying database for agent configurations (sync)...")
            
            # Try to get user-specific active configuration first
            try:
                user_config = AgentConfiguration.objects.filter(
                    created_by_id=user_id,
                    is_active=True
                ).first()
                
                if user_config:
                    logger.info(f"Found USER-SPECIFIC agent config (sync): {user_config.name} (ID: {user_config.id})")
                    config = _convert_db_config_to_dict_sync(user_config)
                    agent = DigitalAssetsManagerAgent(custom_config=config)
                    logger.info(f"✅ Created agent from USER-SPECIFIC database config (sync): {user_config.name}")
                    return agent
                else:
                    logger.info(f"No user-specific agent config found for user {user_id} (sync)")
            except Exception as e:
                logger.error(f"Error querying user-specific agent config (sync): {e}")
            
            # Try to get system default configuration
            try:
                system_config = AgentConfiguration.objects.filter(
                    is_active=True,
                    is_default=True
                ).first()
                
                if system_config:
                    logger.info(f"Found SYSTEM DEFAULT agent config (sync): {system_config.name} (ID: {system_config.id})")
                    config = _convert_db_config_to_dict_sync(system_config)
                    agent = DigitalAssetsManagerAgent(custom_config=config)
                    logger.info(f"✅ Created agent from SYSTEM DEFAULT database config (sync): {system_config.name}")
                    return agent
                else:
                    logger.info(f"No system default agent config found (sync)")
            except Exception as e:
                logger.error(f"Error querying system default agent config (sync): {e}")
            
            # Try to get any active configuration
            try:
                any_config = AgentConfiguration.objects.filter(
                    is_active=True
                ).first()
                
                if any_config:
                    logger.info(f"Found ANY ACTIVE agent config (sync): {any_config.name} (ID: {any_config.id})")
                    config = _convert_db_config_to_dict_sync(any_config)
                    agent = DigitalAssetsManagerAgent(custom_config=config)
                    logger.info(f"✅ Created agent from ANY ACTIVE database config (sync): {any_config.name}")
                    return agent
                else:
                    logger.info(f"No active agent configurations found in database (sync)")
            except Exception as e:
                logger.error(f"Error querying any active agent config (sync): {e}")
                
        except Exception as e:
            logger.error(f"Error loading agent configuration from database (sync): {e}")
            logger.error(f"Traceback: ", exc_info=True)
    
    # Fall back to global default agent
    logger.info(f"🔄 Falling back to DEFAULT agent configuration (sync)")
    try:
        global _agent_instance
        if _agent_instance is None:
            _agent_instance = DigitalAssetsManagerAgent()
            logger.info(f"✅ Created default Digital Assets Manager agent instance (sync)")
        else:
            logger.info(f"✅ Using existing default agent instance (sync)")
        
        return _agent_instance
    except Exception as e:
        logger.error(f"Error creating default agent (sync): {e}")
        logger.error(f"Traceback: ", exc_info=True)
        raise


async def _convert_db_config_to_dict(db_config) -> dict:
    """Convert database AgentConfiguration to dictionary format."""
    logger.info(f"Converting database config to dict: {db_config.name}")
    
    config = {
        'name': db_config.name,
        'type': 'database',
        'instructions': db_config.instructions,
        'model': db_config.model,
        'tools_enabled': db_config.tools_enabled or [],
        'max_turns': db_config.max_turns,
        'timeout': db_config.timeout,
        'temperature': db_config.temperature,
        'top_p': db_config.top_p,
        'frequency_penalty': db_config.frequency_penalty,
        'presence_penalty': db_config.presence_penalty,
        'system_context': db_config.system_context,
        'capabilities': db_config.capabilities or [],
    }
    
    logger.info(f"Database config converted:")
    logger.info(f"  - Name: {config['name']}")
    logger.info(f"  - Model: {config['model']}")
    logger.info(f"  - Tools: {config['tools_enabled']}")
    logger.info(f"  - Instructions length: {len(config['instructions'])} chars")
    
    return config


def _convert_db_config_to_dict_sync(db_config) -> dict:
    """Synchronous version of convert database AgentConfiguration to dictionary format."""
    logger.info(f"Converting database config to dict (sync): {db_config.name}")
    
    config = {
        'name': db_config.name,
        'type': 'database',
        'instructions': db_config.instructions,
        'model': db_config.model,
        'tools_enabled': db_config.tools_enabled or [],
        'max_turns': db_config.max_turns,
        'timeout': db_config.timeout,
        'temperature': db_config.temperature,
        'top_p': db_config.top_p,
        'frequency_penalty': db_config.frequency_penalty,
        'presence_penalty': db_config.presence_penalty,
        'system_context': db_config.system_context,
        'capabilities': db_config.capabilities or [],
    }
    
    logger.info(f"Database config converted (sync):")
    logger.info(f"  - Name: {config['name']}")
    logger.info(f"  - Model: {config['model']}")
    logger.info(f"  - Tools: {config['tools_enabled']}")
    logger.info(f"  - Instructions length: {len(config['instructions'])} chars")
    
    return config

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
from .tools import sensor_data_tool, system_status_tool

logger = logging.getLogger(__name__)

# Set OpenAI API key from Django settings
if hasattr(settings, 'OPENAI_API_KEY') and settings.OPENAI_API_KEY:
    api_key = settings.OPENAI_API_KEY
    logger.info(f"OpenAI API key configured from Django settings: {api_key[:10]}...{api_key[-10:]}")
    set_default_openai_key(api_key)
else:
    logger.warning("No OpenAI API key found in Django settings")


class DigitalTwinAgent:
    """
    Digital Twin Agent for handling conversations about digital twin systems.
    """
    
    def __init__(self):
        """Initialize the Digital Twin Agent with tools and configuration."""
        self.agent = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the OpenAI agent with appropriate instructions and tools."""
        logger.info("Initializing Digital Twin Agent")
        
        instructions = """
        You are a Digital Twin Assistant specialized in industrial IoT systems and digital twin technology.
        
        Your role is to:
        1. Help users understand and interact with digital twin systems
        2. Provide insights about sensor data, system status, and operational metrics
        3. Explain digital twin concepts and industrial automation processes
        4. Assist with monitoring and troubleshooting system components
        
        When users ask about sensor data or system status, use the available tools to retrieve real-time information.
        Always explain the significance of the readings and provide context about what they mean for system operation.
        
        Key capabilities:
        - Retrieve sensor data (temperature, pressure, humidity, vibration, power consumption, flow rate)
        - Check system component status (motors, pumps, controllers, network)
        - Analyze data trends and provide operational insights
        - Explain digital twin architecture and benefits
        
        Be helpful, informative, and focus on practical insights that can improve system operation and maintenance.
        """
        
        try:
            self.agent = Agent(
                name="Digital Twin Assistant",
                instructions=instructions,
                tools=[sensor_data_tool, system_status_tool],
                model=getattr(settings, 'AGENT_MODEL', 'gpt-4o-mini')
            )
            logger.info("Digital Twin Agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Digital Twin Agent: {e}")
            raise
    
    async def process_message(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        Process a user message and return the agent's response.
        
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
            
            # Run the agent with conversation context
            result = await Runner.run(
                self.agent,
                input=message,
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
                    "conversation_length": len(conversation_history)
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
_agent_instance: Optional[DigitalTwinAgent] = None


def get_agent_instance() -> DigitalTwinAgent:
    """Get or create the global agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = DigitalTwinAgent()
    return _agent_instance

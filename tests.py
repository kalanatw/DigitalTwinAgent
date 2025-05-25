"""
Tests for Digital Twin Application
"""
import pytest
import json
from unittest.mock import patch, AsyncMock
from django.test import TestCase, Client
from django.urls import reverse
from digital_twin_app.tools import sensor_data_tool, system_status_tool
from digital_twin_app.agent import DigitalTwinAgent


class ToolsTestCase(TestCase):
    """Test cases for digital twin tools."""
    
    def test_sensor_data_tool_all_sensors(self):
        """Test sensor data tool with all sensors."""
        result = sensor_data_tool("all", "main_facility")
        data = json.loads(result)
        
        self.assertIn("sensors", data)
        self.assertIn("location", data)
        self.assertIn("timestamp", data)
        self.assertEqual(data["location"], "main_facility")
        self.assertIn("temperature", data["sensors"])
        self.assertIn("pressure", data["sensors"])
        self.assertIn("humidity", data["sensors"])
    
    def test_sensor_data_tool_specific_sensor(self):
        """Test sensor data tool with specific sensor."""
        result = sensor_data_tool("temperature", "secondary_unit")
        data = json.loads(result)
        
        self.assertIn("sensors", data)
        self.assertEqual(data["location"], "secondary_unit")
        self.assertIn("temperature", data["sensors"])
        self.assertNotIn("pressure", data["sensors"])
    
    def test_sensor_data_tool_invalid_sensor(self):
        """Test sensor data tool with invalid sensor type."""
        result = sensor_data_tool("invalid_sensor", "main_facility")
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("available_sensors", data)
    
    def test_system_status_tool_all_components(self):
        """Test system status tool with all components."""
        result = system_status_tool("all")
        data = json.loads(result)
        
        self.assertIn("components", data)
        self.assertIn("timestamp", data)
        self.assertIn("motors", data["components"])
        self.assertIn("pumps", data["components"])
        self.assertIn("controllers", data["components"])
    
    def test_system_status_tool_specific_component(self):
        """Test system status tool with specific component."""
        result = system_status_tool("motors")
        data = json.loads(result)
        
        self.assertIn("components", data)
        self.assertIn("motors", data["components"])
        self.assertNotIn("pumps", data["components"])


class ViewsTestCase(TestCase):
    """Test cases for views."""
    
    def setUp(self):
        self.client = Client()
    
    def test_chat_view_get(self):
        """Test chat view GET request."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
    
    def test_about_view(self):
        """Test about view."""
        response = self.client.get('/about/')
        self.assertEqual(response.status_code, 200)
    
    @patch('digital_twin_app.views.get_agent_instance')
    def test_api_chat_view_post(self, mock_agent):
        """Test API chat view POST request."""
        # Mock agent response
        mock_agent_instance = AsyncMock()
        mock_agent_instance.process_message.return_value = {
            'response': 'Test response',
            'session_id': 'test_session',
            'status': 'success',
            'metadata': {'tools_used': []}
        }
        mock_agent.return_value = mock_agent_instance
        
        response = self.client.post(
            '/api/chat/',
            data=json.dumps({
                'message': 'Test message',
                'session_id': 'test_session'
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
    
    def test_api_chat_view_invalid_json(self):
        """Test API chat view with invalid JSON."""
        response = self.client.post(
            '/api/chat/',
            data='invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
    
    def test_api_chat_view_missing_message(self):
        """Test API chat view with missing message."""
        response = self.client.post(
            '/api/chat/',
            data=json.dumps({'session_id': 'test'}),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)


@pytest.mark.asyncio
class AgentTestCase:
    """Test cases for the Digital Twin Agent."""
    
    @patch('digital_twin_app.agent.Agent')
    async def test_agent_initialization(self, mock_agent_class):
        """Test agent initialization."""
        agent = DigitalTwinAgent()
        mock_agent_class.assert_called_once()
        assert agent.agent is not None
    
    @patch('digital_twin_app.agent.Runner')
    @patch('digital_twin_app.agent.cache')
    async def test_process_message(self, mock_cache, mock_runner):
        """Test message processing."""
        # Setup mocks
        mock_cache.get.return_value = []
        mock_runner.run.return_value = AsyncMock(final_output="Test response")
        
        agent = DigitalTwinAgent()
        result = await agent.process_message("Test message", "test_session")
        
        assert result['status'] == 'success'
        assert result['response'] == "Test response"
        assert result['session_id'] == "test_session"


if __name__ == '__main__':
    pytest.main([__file__])

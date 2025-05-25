"""
Django management utility for testing and development tasks.
"""
from django.core.management.base import BaseCommand
from digital_twin_app.tools import sensor_data_tool, system_status_tool
import json


class Command(BaseCommand):
    help = 'Test Digital Twin tools and agent functionality'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-tools',
            action='store_true',
            help='Test sensor data and system status tools',
        )
        parser.add_argument(
            '--test-agent',
            action='store_true',
            help='Test agent functionality',
        )

    def handle(self, *args, **options):
        if options['test_tools']:
            self.test_tools()
        
        if options['test_agent']:
            self.test_agent()

    def test_tools(self):
        """Test the digital twin tools."""
        self.stdout.write(self.style.SUCCESS("Testing Digital Twin Tools..."))
        
        # Test sensor data tool
        self.stdout.write("\n1. Testing Sensor Data Tool:")
        result = sensor_data_tool("all", "main_facility")
        data = json.loads(result)
        self.stdout.write(f"   Location: {data['location']}")
        self.stdout.write(f"   Sensors found: {len(data['sensors'])}")
        
        # Test specific sensor
        result = sensor_data_tool("temperature", "secondary_unit")
        data = json.loads(result)
        temp_value = data['sensors']['temperature']['value']
        self.stdout.write(f"   Temperature at secondary_unit: {temp_value}°C")
        
        # Test system status tool
        self.stdout.write("\n2. Testing System Status Tool:")
        result = system_status_tool("all")
        data = json.loads(result)
        self.stdout.write(f"   Components found: {len(data['components'])}")
        
        # Test specific component
        result = system_status_tool("motors")
        data = json.loads(result)
        motor_count = len(data['components']['motors'])
        self.stdout.write(f"   Motors monitored: {motor_count}")
        
        self.stdout.write(self.style.SUCCESS("\n✅ Tools test completed successfully!"))

    def test_agent(self):
        """Test the agent functionality."""
        self.stdout.write(self.style.SUCCESS("Testing Digital Twin Agent..."))
        
        try:
            from digital_twin_app.agent import get_agent_instance
            import asyncio
            
            agent = get_agent_instance()
            self.stdout.write("✅ Agent instance created successfully")
            
            # Test message processing
            async def test_message():
                result = await agent.process_message(
                    "Show me temperature data", 
                    "test_session"
                )
                return result
            
            # Run async test
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(test_message())
            loop.close()
            
            self.stdout.write(f"✅ Agent response: {result['status']}")
            self.stdout.write(self.style.SUCCESS("\n✅ Agent test completed successfully!"))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Agent test failed: {str(e)}")
            )

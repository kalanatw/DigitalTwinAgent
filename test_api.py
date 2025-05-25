#!/usr/bin/env python
"""
Test script to verify OpenAI API key works
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
project_root = Path(__file__).parent
env_path = project_root / '.env'
load_dotenv(env_path)

# Setup Django
sys.path.insert(0, str(project_root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_twin.settings')
import django
django.setup()

from agents import Agent, set_default_openai_key
from digital_twin_app.tools import sensor_data_tool

def test_api_key():
    # Get API key from environment
    api_key = os.getenv('OPENAI_API_KEY')
    print(f"API Key from env: {api_key[:10]}...{api_key[-10:] if api_key else 'None'}")
    
    # Set the API key
    if api_key:
        set_default_openai_key(api_key)
        print("API key set successfully")
        
        # Test creating an agent
        try:
            agent = Agent(
                name="Test Agent",
                instructions="You are a helpful assistant.",
                tools=[sensor_data_tool],
                model="gpt-4o-mini"
            )
            print("Agent created successfully!")
            return True
        except Exception as e:
            print(f"Error creating agent: {e}")
            return False
    else:
        print("No API key found!")
        return False

if __name__ == "__main__":
    test_api_key()

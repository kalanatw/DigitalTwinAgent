"""
Tests for user-centric resource management in Digital Twin
"""
import json
import uuid
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_twin.settings')
django.setup()

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from digital_twin_app.models import (
    Document, TwinVersion, AgentConfiguration, 
    DocumentShare, TwinVersionShare, AgentShare,
    UserProfile, TokenUsage
)


class UserCentricResourcesTest(TestCase):
    """Test user-centric resource functionality"""
    
    def setUp(self):
        """Set up test users and resources"""
        # Create users
        self.user1 = User.objects.create_user(username='user1', email='user1@example.com', password='password123')
        self.user2 = User.objects.create_user(username='user2', email='user2@example.com', password='password123')
        
        # Create TwinVersion for user1
        self.twin_version1 = TwinVersion.objects.create(
            name="User1's Twin Version",
            description="Test twin version",
            version="1.0",
            user=self.user1,
            is_shared=False
        )
        
        # Create TwinVersion for user2
        self.twin_version2 = TwinVersion.objects.create(
            name="User2's Twin Version",
            description="Test twin version",
            version="1.0",
            user=self.user2,
            is_shared=False
        )
        
        # Create shared TwinVersion for user1
        self.twin_version_shared = TwinVersion.objects.create(
            name="User1's Shared Twin Version",
            description="Test twin version that is shared",
            version="1.0",
            user=self.user1,
            is_shared=True
        )
        
        # Set up the client
        self.client = Client()

    def test_user_can_access_own_resources(self):
        """Test that a user can access their own resources"""
        # Login as user1
        self.client.login(username='user1', password='password123')
        
        # Access user1's twin version
        url = reverse('twin_version_detail', args=[self.twin_version1.id])
        response = self.client.get(url)
        
        # Check if access is granted
        self.assertEqual(response.status_code, 200)
        
        # Parse response
        data = json.loads(response.content)
        self.assertEqual(data['id'], str(self.twin_version1.id))
        self.assertEqual(data['name'], self.twin_version1.name)
    
    def test_user_cannot_access_other_resources(self):
        """Test that a user cannot access resources owned by another user"""
        # Login as user1
        self.client.login(username='user1', password='password123')
        
        # Try to access user2's twin version
        url = reverse('twin_version_detail', args=[self.twin_version2.id])
        response = self.client.get(url)
        
        # Check if access is denied
        self.assertEqual(response.status_code, 403)
    
    def test_user_can_access_shared_resources(self):
        """Test that a user can access publicly shared resources"""
        # Login as user2
        self.client.login(username='user2', password='password123')
        
        # Try to access user1's shared twin version
        url = reverse('twin_version_detail', args=[self.twin_version_shared.id])
        response = self.client.get(url)
        
        # Check if access is granted
        self.assertEqual(response.status_code, 200)
        
        # Parse response
        data = json.loads(response.content)
        self.assertEqual(data['id'], str(self.twin_version_shared.id))
        self.assertEqual(data['name'], self.twin_version_shared.name)
    
    def test_token_usage_tracking(self):
        """Test token usage tracking functionality"""
        # Record token usage for user1
        from .usage_tracker import record_token_usage
        
        record_token_usage(
            user=self.user1,
            tokens_used=100,
            input_tokens=70,
            output_tokens=30,
            resource_type='twin_version',
            resource_id=self.twin_version1.id,
            operation='test'
        )
        
        # Check if token usage was recorded
        token_usage = TokenUsage.objects.filter(user=self.user1).first()
        self.assertIsNotNone(token_usage)
        self.assertEqual(token_usage.tokens_used, 100)
        self.assertEqual(token_usage.input_tokens, 70)
        self.assertEqual(token_usage.output_tokens, 30)
        self.assertEqual(token_usage.resource_type, 'twin_version')
        self.assertEqual(token_usage.resource_id, str(self.twin_version1.id))
        
        # Check if user profile was updated
        profile = UserProfile.objects.get(user=self.user1)
        self.assertEqual(profile.total_tokens_used, 100)
        self.assertEqual(profile.total_input_tokens, 70)
        self.assertEqual(profile.total_output_tokens, 30)
    
    def test_resource_sharing(self):
        """Test resource sharing between users"""
        # Create a document under user1's twin version
        document = Document.objects.create(
            twin_version=self.twin_version1,
            title="Test Document",
            description="Test document description",
            file="test.txt",
            file_type="txt",
            file_size=100,
            uploaded_by=self.user1
        )
        
        # User2 should not be able to access the document
        self.client.login(username='user2', password='password123')
        url = reverse('document_detail', args=[document.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        
        # Share the document with user2
        DocumentShare.objects.create(
            document=document,
            shared_with=self.user2
        )
        
        # Now user2 should be able to access the document
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # Check if the document data is correct
        data = json.loads(response.content)
        self.assertEqual(data['id'], str(document.id))
        self.assertEqual(data['title'], document.title)
        self.assertEqual(data['uploaded_by'], self.user1.username)

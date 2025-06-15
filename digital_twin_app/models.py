"""
Django Models for Digital Twin Application
"""
from django.db import models
from django.contrib.auth.models import User
import uuid
import os


class TwinVersion(models.Model):
    """Model to represent different versions of digital twins."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=50, default="1.0")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['name', 'version']
    
    def __str__(self):
        return f"{self.name} v{self.version}"


class ChatSession(models.Model):
    """Model to track chat sessions."""
    session_id = models.CharField(max_length=100, unique=True)
    twin_version = models.ForeignKey(TwinVersion, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Session {self.session_id} - {self.twin_version}"


class ChatMessage(models.Model):
    """Model to store chat messages."""
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=[('user', 'User'), ('assistant', 'Assistant')])
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    tools_used = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ['timestamp']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."


def get_document_upload_path(instance, filename):
    """Generate upload path for documents based on twin version."""
    twin_version_id = instance.twin_version.id if instance.twin_version else 'default'
    return f'documents/{twin_version_id}/{filename}'


class Document(models.Model):
    """Model to store uploaded documents."""
    DOCUMENT_TYPES = [
        ('pdf', 'PDF'),
        ('docx', 'Word Document'),
        ('txt', 'Text File'),
        ('md', 'Markdown'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending Processing'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    twin_version = models.ForeignKey(TwinVersion, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to=get_document_upload_path)
    file_type = models.CharField(max_length=10, choices=DOCUMENT_TYPES, default='other')
    file_size = models.BigIntegerField(default=0)  # in bytes
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)  # For chat enablement
    processing_error = models.TextField(blank=True)
    
    # Metadata
    page_count = models.IntegerField(null=True, blank=True)
    word_count = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['twin_version', 'status']),
            models.Index(fields=['twin_version', 'is_enabled']),
        ]
    
    def __str__(self):
        return f"{self.title} ({self.twin_version})"
    
    def get_file_extension(self):
        """Get file extension from filename."""
        return os.path.splitext(self.file.name)[1].lower()


class DocumentChunk(models.Model):
    """Model to store document chunks for embedding."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    content = models.TextField()
    chunk_index = models.IntegerField()
    page_number = models.IntegerField(null=True, blank=True)
    word_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']
        indexes = [
            models.Index(fields=['document', 'chunk_index']),
        ]
    
    def __str__(self):
        return f"Chunk {self.chunk_index} of {self.document.title}"


class DocumentEmbedding(models.Model):
    """Model to store document embeddings for semantic search."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    chunk = models.OneToOneField(DocumentChunk, on_delete=models.CASCADE, related_name='embedding')
    embedding = models.JSONField()  # Store as JSON array
    embedding_model = models.CharField(max_length=100, default='text-embedding-3-small')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Embedding for {self.chunk}"


class SensorReading(models.Model):
    """Model to store sensor readings for historical analysis."""
    sensor_type = models.CharField(max_length=50)
    location = models.CharField(max_length=100)
    value = models.FloatField()
    unit = models.CharField(max_length=20)
    status = models.CharField(max_length=20)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['sensor_type', 'location']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.sensor_type} at {self.location}: {self.value} {self.unit}"


class ValidatedSender(models.Model):
    """Model to store validated email senders for auto-reply"""
    email_address = models.EmailField(unique=True)
    name = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} <{self.email_address}>" if self.name else self.email_address


class EmailAccount(models.Model):
    """Model to store email account configuration"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_account')
    email_address = models.EmailField()
    google_access_token = models.TextField(blank=True)
    google_refresh_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    auto_reply_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.email_address}"


class EmailMessage(models.Model):
    """Model to store received and sent email messages"""
    STATUS_CHOICES = [
        ('received', 'Received'),
        ('processing', 'Processing'),
        ('responded', 'Responded'),
        ('failed', 'Failed'),
    ]
    
    account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE, related_name='messages')
    message_id = models.CharField(max_length=255, unique=True)
    sender = models.EmailField()
    subject = models.CharField(max_length=500)
    body = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='received')
    ai_response = models.TextField(blank=True)
    response_sent = models.BooleanField(default=False)
    chat_session = models.ForeignKey(ChatSession, on_delete=models.SET_NULL, null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-received_at']
        indexes = [
            models.Index(fields=['sender', 'status']),
            models.Index(fields=['received_at']),
        ]
    
    def __str__(self):
        return f"Email from {self.sender}: {self.subject}"
    
    @property
    def is_from_validated_sender(self):
        return ValidatedSender.objects.filter(
            email_address=self.sender, 
            is_active=True
        ).exists()


class AgentConfiguration(models.Model):
    """Model to store custom agent configurations and prompts"""
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Core agent settings
    instructions = models.TextField(help_text="Main instructions/prompt for the agent")
    model = models.CharField(max_length=50, default='gpt-4o-mini', 
                           help_text="OpenAI model to use (e.g., gpt-4o-mini, gpt-4-turbo)")
    max_turns = models.IntegerField(default=20, help_text="Maximum conversation turns")
    timeout = models.IntegerField(default=30, help_text="Timeout in seconds")
    
    # Advanced settings
    temperature = models.FloatField(default=0.7, help_text="Model temperature (0.0-2.0)")
    top_p = models.FloatField(default=1.0, help_text="Top-p sampling parameter")
    frequency_penalty = models.FloatField(default=0.0, help_text="Frequency penalty")
    presence_penalty = models.FloatField(default=0.0, help_text="Presence penalty")
    
    # Context and specialization
    system_context = models.TextField(blank=True, 
                                    help_text="Additional system context and background")
    tools_enabled = models.JSONField(default=list, blank=True,
                                   help_text="List of enabled tools for this agent")
    capabilities = models.JSONField(default=list, blank=True,
                                  help_text="List of agent capabilities")
    
    # Metadata
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_agents')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
        
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Ensure only one default agent per user
        if self.is_default:
            AgentConfiguration.objects.filter(
                created_by=self.created_by,
                is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


class AgentTemplate(models.Model):
    """Predefined agent templates for quick setup"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    # Template content
    instructions_template = models.TextField()
    system_context_template = models.TextField(blank=True)
    default_tools = models.JSONField(default=list)
    default_capabilities = models.JSONField(default=list)
    
    # Recommended settings
    recommended_model = models.CharField(max_length=50, default='gpt-4o-mini')
    recommended_temperature = models.FloatField(default=0.7)
    
    # Metadata
    is_system_template = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return self.name


class AgentSession(models.Model):
    """Track active agent sessions and their configurations"""
    session_id = models.CharField(max_length=100, unique=True)
    agent_config = models.ForeignKey(AgentConfiguration, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Session metadata
    messages_count = models.IntegerField(default=0)
    total_tokens_used = models.IntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-last_activity']
        
    def __str__(self):
        return f"Session {self.session_id} - {self.agent_config.name}"

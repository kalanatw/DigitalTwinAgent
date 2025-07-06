"""
Django Models for Digital Twin Application
"""
import os
import uuid
import json
import logging
import mimetypes
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

# Helper functions
def get_document_upload_path(instance, filename):
    """Generate upload path for document files with user folder."""
    # Use user ID in path if available
    user_id = getattr(instance.uploaded_by, 'id', 'shared')
    return os.path.join('documents', f'user_{user_id}', f"{uuid.uuid4()}_{filename}")

class TwinVersion(models.Model):
    """Model to represent different versions of digital twins."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=50, default="1.0")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='twin_versions')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    # New fields for user-centric model
    is_shared = models.BooleanField(default=False, help_text='Whether this twin version is shared with other users')
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'name', 'version']  # Make constraint user-specific
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['is_shared']),
        ]
    
    def __str__(self):
        return f"{self.name} v{self.version}"


class ChatSession(models.Model):
    """Model to track user-centric chat sessions."""
    # Keep existing integer ID for now to avoid migration issues
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(max_length=100, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_sessions')
    title = models.CharField(max_length=255, blank=True, help_text="Auto-generated title for the session")
    twin_version = models.ForeignKey(TwinVersion, on_delete=models.CASCADE, null=True, blank=True)
    agent_config = models.ForeignKey('AgentConfiguration', on_delete=models.CASCADE, null=True, blank=True)
    
    # Session management
    is_active = models.BooleanField(default=True)
    is_pinned = models.BooleanField(default=False, help_text="Pinned sessions appear at top")
    is_archived = models.BooleanField(default=False, help_text="Archived sessions are hidden by default")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    
    # Usage tracking
    message_count = models.IntegerField(default=0)
    total_tokens_used = models.IntegerField(default=0)
    total_input_tokens = models.IntegerField(default=0)
    total_output_tokens = models.IntegerField(default=0)
    
    # Context preservation
    context_summary = models.TextField(blank=True, help_text="AI-generated summary of the conversation")
    tags = models.JSONField(default=list, blank=True, help_text="User-defined tags for organization")
    
    class Meta:
        ordering = ['-last_message_at', '-updated_at']
        indexes = [
            models.Index(fields=['user', 'is_active', '-last_message_at']),
            models.Index(fields=['user', 'is_pinned', '-updated_at']),
            models.Index(fields=['user', 'is_archived']),
            models.Index(fields=['session_id']),
        ]
    
    def __str__(self):
        title = self.title or f"Session {self.session_id[:8]}..."
        return f"{title} - {self.user.username if self.user else 'Unknown'}"
    
    def save(self, *args, **kwargs):
        # Generate title if not provided
        if not self.title and self.message_count > 0:
            first_message = self.messages.filter(role='user').first()
            if first_message:
                # Generate title from first user message (truncated)
                self.title = first_message.content[:50] + "..." if len(first_message.content) > 50 else first_message.content
        super().save(*args, **kwargs)


class ChatMessage(models.Model):
    """Model to store user-centric chat messages."""
    # Keep existing integer ID for now to avoid migration issues
    # id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=[('user', 'User'), ('assistant', 'Assistant'), ('system', 'System')])
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Message metadata
    message_index = models.IntegerField(default=0, help_text="Order of message in the session")
    parent_message = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, 
                                     help_text="For branching conversations")
    
    # Token usage tracking
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    
    # Tool usage
    tools_used = models.JSONField(default=list, blank=True, help_text="List of tools used in this message")
    tool_outputs = models.JSONField(default=dict, blank=True, help_text="Outputs from tools used")
    
    # Message state
    is_deleted = models.BooleanField(default=False)
    is_edited = models.BooleanField(default=False)
    edit_history = models.JSONField(default=list, blank=True, help_text="History of edits")
    
    # AI metadata
    model_used = models.CharField(max_length=50, blank=True, help_text="AI model used for this response")
    temperature = models.FloatField(null=True, blank=True, help_text="Temperature used for this response")
    finish_reason = models.CharField(max_length=50, blank=True, help_text="Why the model stopped")
    
    class Meta:
        ordering = ['session', 'message_index']
        indexes = [
            models.Index(fields=['session', 'message_index']),
            models.Index(fields=['session', 'role', '-timestamp']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."
    
    def save(self, *args, **kwargs):
        # Track if this is a new message
        is_new = self.pk is None
        
        # Auto-increment message index
        if self.message_index is None or self.message_index == 0:
            max_index = ChatMessage.objects.filter(session=self.session).aggregate(
                models.Max('message_index')
            )['message_index__max']
            self.message_index = (max_index or 0) + 1
        
        # Update total tokens
        self.total_tokens = self.input_tokens + self.output_tokens
        
        super().save(*args, **kwargs)
        
        # Update session stats (only for new messages)
        if is_new:
            self.session.message_count = self.session.messages.count()
            self.session.last_message_at = self.timestamp
            self.session.total_tokens_used += self.total_tokens
            self.session.total_input_tokens += self.input_tokens
            self.session.total_output_tokens += self.output_tokens
            self.session.save(update_fields=['message_count', 'last_message_at', 
                                           'total_tokens_used', 'total_input_tokens', 'total_output_tokens'])


class Document(models.Model):
    """Model to store uploaded documents."""
    DOCUMENT_TYPES = [
        ('pdf', 'PDF'),
        ('docx', 'Word Document'),
        ('txt', 'Text File'),
        ('md', 'Markdown'),
        ('csv', 'CSV File'),
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
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, db_column='user_id')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)  # For chat enablement
    is_shared = models.BooleanField(default=False)  # Whether document is shared publicly
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
    embedding_type = models.CharField(max_length=50, default='document')  # Type of embedding (e.g., document, query)
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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_agents')
    is_shared = models.BooleanField(default=False, help_text='Whether this agent is shared with other users')
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
                user=self.user,
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


class CSVDocument(models.Model):
    """Model for storing CSV document metadata"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    twin_version = models.ForeignKey(TwinVersion, on_delete=models.CASCADE, related_name='csv_documents')
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file_path = models.CharField(max_length=512)
    file = models.FileField(upload_to='csv_documents/', null=True, blank=True)
    file_size = models.IntegerField(default=0)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    row_count = models.IntegerField(default=0)
    column_count = models.IntegerField(default=0)
    schema_summary = models.TextField(null=True, blank=True)  # JSON text field
    status = models.CharField(max_length=20, default='processing',
                             choices=[('processing', 'Processing'), 
                                     ('completed', 'Completed'), 
                                     ('failed', 'Failed')])
    processing_error = models.TextField(blank=True)
    is_enabled = models.BooleanField(default=True)
    
    def __str__(self):
        return self.title


class CSVDataset(models.Model):
    """Model for storing actual data and statistics about a CSV file"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(CSVDocument, on_delete=models.CASCADE, related_name='dataset')
    data_sample = models.TextField(null=True, blank=True)  # JSON text field with sample rows
    total_rows = models.IntegerField(default=0)
    statistical_summary = models.TextField(null=True, blank=True)  # JSON text field
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Dataset for {self.document.title}"


class CSVColumn(models.Model):
    """Model for storing column information from CSV files"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(CSVDataset, on_delete=models.CASCADE, related_name='columns')
    name = models.CharField(max_length=255)
    data_type = models.CharField(max_length=50)
    description = models.TextField(null=True, blank=True)
    statistics = models.TextField(null=True, blank=True)  # JSON text field
    is_time_column = models.BooleanField(default=False)
    is_categorical = models.BooleanField(default=False)
    is_numerical = models.BooleanField(default=False)
    is_primary_key = models.BooleanField(default=False)
    sample_values = models.TextField(null=True, blank=True)  # JSON text field
    
    def __str__(self):
        return f"{self.name} ({self.data_type})"


class TimeSeriesData(models.Model):
    """Model for storing time series data sources and metadata"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Source
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='time_series', null=True, blank=True)
    csv_document = models.ForeignKey('CSVDocument', on_delete=models.CASCADE, related_name='time_series', null=True, blank=True)
    data_type = models.CharField(max_length=50, choices=[('manual', 'Manual Entry'), 
                                                        ('sensor', 'Sensor Data'),
                                                        ('csv', 'CSV Data'),
                                                        ('api', 'External API')])
    source_text = models.CharField(max_length=255, blank=True)
    
    # Properties
    unit = models.CharField(max_length=50, blank=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    total_points = models.IntegerField(default=0)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_enabled = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Time Series"
        verbose_name_plural = "Time Series Data"
    
    def __str__(self):
        return self.title


class TimeSeriesPoint(models.Model):
    """Model for storing individual time series data points"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    time_series = models.ForeignKey(TimeSeriesData, on_delete=models.CASCADE, related_name='points')
    timestamp = models.DateTimeField()
    value = models.FloatField()
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['time_series', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.time_series.title} @ {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}: {self.value}"


class UserProfile(models.Model):
    """Extended user profile with usage statistics"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Token usage tracking
    total_tokens_used = models.BigIntegerField(default=0)
    total_input_tokens = models.BigIntegerField(default=0)
    total_output_tokens = models.BigIntegerField(default=0)
    
    # Usage statistics
    total_chat_sessions = models.IntegerField(default=0)
    total_messages_sent = models.IntegerField(default=0)
    total_documents_uploaded = models.IntegerField(default=0)
    total_emails_processed = models.IntegerField(default=0)
    
    # Account settings
    daily_token_limit = models.IntegerField(default=1000000)  # 1M tokens per day
    monthly_token_limit = models.BigIntegerField(default=30000000)  # 30M tokens per month
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    def get_token_usage_percentage(self):
        """Calculate token usage as percentage of monthly limit"""
        if self.monthly_token_limit > 0:
            return min((self.total_tokens_used / self.monthly_token_limit) * 100, 100)
        return 0
    
    def can_use_tokens(self, token_count):
        """Check if user can use specified number of tokens"""
        return (self.total_tokens_used + token_count) <= self.monthly_token_limit
    
    def add_token_usage(self, input_tokens=0, outputTokens=0):
        """Add token usage to user's profile"""
        self.total_input_tokens += input_tokens
        self.total_output_tokens += outputTokens
        self.total_tokens_used += (inputTokens + outputTokens)
        self.save()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a new User is created"""
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile when User is saved"""
    if hasattr(instance, 'profile'):
        instance.profile.save()
    else:
        UserProfile.objects.create(user=instance)


class TokenUsage(models.Model):
    """Model to track token usage across all operations"""
    RESOURCE_TYPES = [
        ('agent', 'Agent'),
        ('document', 'Document'),
        ('twin_version', 'Twin Version'),
        ('chat', 'Chat'),
        ('other', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='token_usage')
    timestamp = models.DateTimeField(auto_now_add=True)
    tokens_used = models.IntegerField()
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPES)
    resource_id = models.CharField(max_length=100, null=True, blank=True)
    operation = models.CharField(max_length=50)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['resource_type', 'resource_id']),
        ]


class DocumentUsage(models.Model):
    """Model to track document usage"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='document_usage')
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='usage_records')
    timestamp = models.DateTimeField(auto_now_add=True)
    operation = models.CharField(max_length=50)  # e.g., "view", "search", "process"
    tokens_used = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['user', 'timestamp'])]


class AgentUsage(models.Model):
    """Model to track agent usage"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_usage')
    agent = models.ForeignKey('AgentConfiguration', on_delete=models.CASCADE, related_name='usage_records')
    timestamp = models.DateTimeField(auto_now_add=True)
    operation = models.CharField(max_length=50)  # e.g., "chat", "test", "configure"
    tokens_used = models.IntegerField(default=0)
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['user', 'timestamp'])]


class DocumentShare(models.Model):
    """Model to track document sharing between users"""
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='shares')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_documents')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['document', 'shared_with']


class TwinVersionShare(models.Model):
    """Model to track twin version sharing between users"""
    twin_version = models.ForeignKey(TwinVersion, on_delete=models.CASCADE, related_name='shares')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_twin_versions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['twin_version', 'shared_with']


class AgentShare(models.Model):
    """Model to track agent configuration sharing between users"""
    agent = models.ForeignKey('AgentConfiguration', on_delete=models.CASCADE, related_name='shares')
    shared_with = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shared_agents')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['agent', 'shared_with']


class UserGmailConnection(models.Model):
    """
    Store user's Gmail OAuth tokens and connection information.
    
    This model securely stores OAuth2 tokens for Gmail API access
    and tracks connection status for each user.
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='gmail_connection'
    )
    access_token = models.TextField(
        help_text="OAuth2 access token for Gmail API"
    )
    refresh_token = models.TextField(
        blank=True,
        null=True,
        help_text="OAuth2 refresh token for token renewal"
    )
    token_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the access token expires"
    )
    scopes_granted = models.JSONField(
        default=list,
        help_text="List of OAuth scopes granted by user"
    )
    email_address = models.EmailField(
        help_text="Gmail email address for this connection"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether the Gmail connection is active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_gmail_connections'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['email_address']),
        ]
    
    def __str__(self) -> str:
        return f"Gmail connection for {self.user.username} ({self.email_address})"
    
    def is_token_expired(self) -> bool:
        """Check if the access token has expired."""
        if not self.token_expires_at:
            return False
        return timezone.now() >= self.token_expires_at
    
    def has_required_scopes(self, required_scopes: list) -> bool:
        """Check if the connection has all required OAuth scopes."""
        if not self.scopes_granted:
            return False
        return all(scope in self.scopes_granted for scope in required_scopes)

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

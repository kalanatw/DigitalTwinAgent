"""
Serializers for API responses
"""
from rest_framework import serializers
from .models import ChatSession, ChatMessage, SensorReading


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'timestamp', 'tools_used']


class ChatSessionSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)
    
    class Meta:
        model = ChatSession
        fields = ['id', 'session_id', 'created_at', 'updated_at', 'is_active', 'messages']


class SensorReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorReading
        fields = ['id', 'sensor_type', 'location', 'value', 'unit', 'status', 'timestamp']


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=5000)
    session_id = serializers.CharField(max_length=100, required=False)


class ChatResponseSerializer(serializers.Serializer):
    response = serializers.CharField()
    session_id = serializers.CharField()
    status = serializers.CharField()
    metadata = serializers.JSONField(required=False)
    error = serializers.CharField(required=False)

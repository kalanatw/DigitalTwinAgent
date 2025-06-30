"""
Serializers for CSV-related models
"""
from rest_framework import serializers
from .models import CSVDocument, CSVDataset, CSVColumn, TimeSeriesData, TimeSeriesPoint


class CSVColumnSerializer(serializers.ModelSerializer):
    """Serializer for CSV column information"""
    class Meta:
        model = CSVColumn
        fields = ['id', 'name', 'data_type', 'description', 'statistics', 
                 'is_time_column', 'is_categorical', 'is_numerical', 'is_primary_key']


class CSVDatasetSerializer(serializers.ModelSerializer):
    """Serializer for CSV dataset information"""
    class Meta:
        model = CSVDataset
        fields = ['id', 'data_sample', 'total_rows', 'statistical_summary', 'created_at']


class CSVDocumentSerializer(serializers.ModelSerializer):
    """Serializer for CSV document information"""
    class Meta:
        model = CSVDocument
        fields = ['id', 'title', 'description', 'file_path', 'file_size', 
                 'uploaded_by', 'uploaded_at', 'processed_at', 'row_count', 
                 'column_count', 'status', 'is_enabled']


class TimeSeriesPointSerializer(serializers.ModelSerializer):
    """Serializer for time series data points"""
    class Meta:
        model = TimeSeriesPoint
        fields = ['id', 'timestamp', 'value', 'notes']


class TimeSeriesDataSerializer(serializers.ModelSerializer):
    """Serializer for time series datasets"""
    points = TimeSeriesPointSerializer(many=True, read_only=True)
    
    class Meta:
        model = TimeSeriesData
        fields = ['id', 'title', 'description', 'data_type', 'unit', 
                 'start_date', 'end_date', 'total_points', 'is_enabled', 
                 'created_at', 'updated_at', 'points']

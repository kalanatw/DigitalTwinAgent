"""
Views for handling CSV file upload, processing and querying
"""
import logging
import json
import pandas as pd
from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import (
    TwinVersion, Document, CSVDocument, CSVDataset, 
    CSVColumn, TimeSeriesData, TimeSeriesPoint
)
from .document_utils import DocumentProcessor, CSVProcessor
from .serializers import CSVDocumentSerializer, CSVDatasetSerializer, CSVColumnSerializer

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_csv_file(request):
    """
    API endpoint for uploading CSV files.
    
    The file is processed intelligently to extract schema and other metadata.
    """
    if 'file' not in request.FILES:
        return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
    
    file_obj = request.FILES['file']
    
    # Validate file extension
    if not file_obj.name.lower().endswith('.csv'):
        return Response({'error': 'File must be a CSV'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get twin version
    twin_version_id = request.data.get('twin_version_id', None)
    twin_version = None
    
    if twin_version_id:
        try:
            twin_version = TwinVersion.objects.get(id=twin_version_id)
        except TwinVersion.DoesNotExist:
            return Response({'error': 'Invalid twin version'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        # Get default twin version if exists
        twin_versions = TwinVersion.objects.filter(is_active=True).order_by('-created_at')
        if twin_versions.exists():
            twin_version = twin_versions.first()
    
    # Save file temporarily
    file_path = default_storage.save(f'temp_csv/{file_obj.name}', ContentFile(file_obj.read()))
    file_path = default_storage.path(file_path)
    
    try:
        # Process the CSV file
        csv_processor = CSVProcessor()
        result = csv_processor.process_csv_file(
            file_path=file_path,
            filename=file_obj.name,
            twin_version_id=twin_version.id if twin_version else None,
            user_id=request.user.id
        )
        
        if result['success']:
            # Retrieve the document for the response
            csv_doc = CSVDocument.objects.get(id=result['document_id'])
            
            # Return successful response with document details
            serializer = CSVDocumentSerializer(csv_doc)
            
            # Add schema overview and time series info
            response_data = serializer.data
            response_data['schema_overview'] = {
                'row_count': result['stats']['rows'],
                'column_count': result['stats']['columns'],
                'column_names': result['stats']['column_names'][:10],  # First 10 columns
                'primary_key': result['schema'].get('primary_key', None)
            }
            
            # Include time series info
            if result['time_series']:
                response_data['time_series'] = [
                    {
                        'name': ts['name'],
                        'description': ts['description'],
                        'time_column': ts['time_column'],
                        'value_column': ts['value_column']
                    }
                    for ts in result['time_series'][:5]  # First 5 time series
                ]
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': result.get('error', 'Failed to process CSV file')}, 
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error processing CSV file: {str(e)}")
        return Response({'error': f'Error processing file: {str(e)}'}, 
                      status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        # Clean up temporary file
        default_storage.delete(file_path)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def list_csv_documents(request):
    """List all CSV documents with basic information"""
    twin_version_id = request.query_params.get('twin_version_id', None)
    
    if twin_version_id:
        documents = CSVDocument.objects.filter(twin_version_id=twin_version_id, is_enabled=True)
    else:
        documents = CSVDocument.objects.filter(is_enabled=True)
    
    serializer = CSVDocumentSerializer(documents, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_csv_document(request, document_id):
    """Get detailed information about a CSV document"""
    try:
        document = CSVDocument.objects.get(id=document_id, is_enabled=True)
    except CSVDocument.DoesNotExist:
        return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = CSVDocumentSerializer(document)
    
    # Get dataset info
    try:
        dataset = document.dataset
        dataset_serializer = CSVDatasetSerializer(dataset)
        dataset_data = dataset_serializer.data
        
        # Get column info
        columns = dataset.columns.all()
        column_serializer = CSVColumnSerializer(columns, many=True)
        dataset_data['columns'] = column_serializer.data
        
        # Get time series data
        time_series = document.time_series.all()
        time_series_data = []
        
        for ts in time_series:
            # Get sample points (first 5 and last 5)
            first_points = ts.points.order_by('timestamp')[:5]
            last_points = ts.points.order_by('-timestamp')[:5]
            
            points_data = []
            for point in list(first_points) + list(last_points):
                points_data.append({
                    'timestamp': point.timestamp.isoformat(),
                    'value': point.value
                })
            
            time_series_data.append({
                'id': str(ts.id),
                'title': ts.title,
                'description': ts.description,
                'unit': ts.unit,
                'total_points': ts.total_points,
                'sample_points': points_data
            })
        
        # Combine all data
        response_data = serializer.data
        response_data['dataset'] = dataset_data
        response_data['time_series'] = time_series_data
        
        return Response(response_data)
    
    except Exception as e:
        logger.error(f"Error getting CSV document details: {str(e)}")
        return Response(serializer.data)  # Return basic document info at minimum


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def query_csv_document(request, document_id):
    """
    Execute a query on a CSV document.
    
    This endpoint accepts natural language queries and returns relevant data.
    """
    try:
        document = CSVDocument.objects.get(id=document_id, is_enabled=True)
    except CSVDocument.DoesNotExist:
        return Response({'error': 'Document not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get query from request
    query = request.data.get('query')
    if not query:
        return Response({'error': 'No query provided'}, status=status.HTTP_400_BAD_REQUEST)
    
    # This would integrate with an agent to process the query
    # For now, we'll return a basic error that this will be implemented
    return Response({
        'message': 'CSV query functionality will be implemented with agent integration',
        'document_id': str(document.id),
        'query': query,
        'status': 'pending'
    })

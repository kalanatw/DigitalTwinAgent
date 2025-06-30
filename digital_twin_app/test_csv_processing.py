"""
Test CSV file processing functionality
"""
import os
import unittest
import tempfile
import pandas as pd
import numpy as np
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from digital_twin_app.models import TwinVersion, CSVDocument, CSVDataset, CSVColumn, TimeSeriesData, TimeSeriesPoint
from digital_twin_app.document_utils import CSVProcessor

class CSVProcessorTests(TestCase):
    """Test CSV file processing functionality"""
    
    def setUp(self):
        """Setup test environment"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create test twin version
        self.twin_version = TwinVersion.objects.create(
            name="Test Twin",
            description="Twin for testing CSV processing",
            created_by=self.user
        )
        
        # Create CSV processor
        self.csv_processor = CSVProcessor()
    
    def create_test_csv(self, data=None):
        """Create a test CSV file"""
        if data is None:
            # Create sample data with time series
            dates = pd.date_range(start='2025-01-01', periods=100, freq='D')
            data = {
                'date': dates,
                'temperature': np.random.normal(25, 5, 100),
                'humidity': np.random.normal(60, 10, 100),
                'pressure': np.random.normal(1010, 5, 100),
                'location_id': np.random.choice([1, 2, 3, 4], 100),
                'status': np.random.choice(['active', 'inactive', 'maintenance'], 100)
            }
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Save to temporary file
        temp_file = tempfile.NamedTemporaryFile(suffix='.csv', delete=False)
        df.to_csv(temp_file.name, index=False)
        temp_file.close()
        
        return temp_file.name
    
    def test_load_csv_intelligently(self):
        """Test intelligent CSV loading"""
        # Create CSV file
        file_path = self.create_test_csv()
        
        # Load the CSV
        df = self.csv_processor._load_csv_intelligently(file_path)
        
        # Verify the dataframe loaded correctly
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 100)  # Check number of rows
        self.assertEqual(len(df.columns), 6)  # Check number of columns
        
        # Clean up
        os.unlink(file_path)
    
    def test_schema_inference(self):
        """Test schema inference"""
        # Create CSV file
        file_path = self.create_test_csv()
        
        # Load the CSV
        df = self.csv_processor._load_csv_intelligently(file_path)
        
        # Infer schema
        schema = self.csv_processor._infer_schema(df)
        
        # Verify schema
        self.assertIn('summary', schema)
        self.assertIn('columns', schema)
        self.assertEqual(schema['summary']['column_count'], 6)
        
        # Check column types
        self.assertEqual(schema['columns']['temperature']['data_type'], 'float')
        self.assertIn('numerical', schema['columns']['temperature']['tags'])
        self.assertIn('temporal', schema['columns']['date']['tags'])
        self.assertIn('categorical', schema['columns']['status']['tags'])
        
        # Clean up
        os.unlink(file_path)
    
    def test_time_series_detection(self):
        """Test time series detection"""
        # Create CSV file
        file_path = self.create_test_csv()
        
        # Load the CSV
        df = self.csv_processor._load_csv_intelligently(file_path)
        
        # Infer schema
        schema = self.csv_processor._infer_schema(df)
        
        # Detect time series
        time_series = self.csv_processor._detect_time_series(df, schema)
        
        # Verify time series detection
        self.assertGreaterEqual(len(time_series), 1)
        
        # Check that temperature is identified as time series
        found_temperature = False
        for ts in time_series:
            if ts['value_column'] == 'temperature':
                found_temperature = True
                self.assertEqual(ts['time_column'], 'date')
                break
        
        self.assertTrue(found_temperature, "Temperature time series not detected")
        
        # Clean up
        os.unlink(file_path)
    
    def test_csv_processing_pipeline(self):
        """Test the full CSV processing pipeline"""
        # Create CSV file
        file_path = self.create_test_csv()
        
        # Process the CSV file
        result = self.csv_processor.process_csv_file(
            file_path=file_path,
            filename="test_data.csv",
            twin_version_id=str(self.twin_version.id),
            user_id=str(self.user.id)
        )
        
        # Verify result
        self.assertTrue(result['success'])
        self.assertIn('document_id', result)
        
        # Check database records
        csv_doc = CSVDocument.objects.get(id=result['document_id'])
        self.assertEqual(csv_doc.status, 'completed')
        self.assertEqual(csv_doc.row_count, 100)
        self.assertEqual(csv_doc.column_count, 6)
        
        # Check dataset and columns
        dataset = csv_doc.dataset
        self.assertIsNotNone(dataset)
        self.assertEqual(dataset.total_rows, 100)
        
        columns = dataset.columns.all()
        self.assertEqual(columns.count(), 6)
        
        # Check for time series data
        time_series = csv_doc.time_series.all()
        self.assertGreater(time_series.count(), 0)
        
        # Clean up
        os.unlink(file_path)


class CSVAPITests(TestCase):
    """Test CSV API endpoints"""
    
    def setUp(self):
        """Setup test environment"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Setup test client
        self.client = Client()
        self.client.login(username='testuser', password='testpassword')
        
        # Create test twin version
        self.twin_version = TwinVersion.objects.create(
            name="Test Twin",
            description="Twin for testing CSV processing",
            created_by=self.user
        )
    
    def test_csv_upload_endpoint(self):
        """Test CSV upload endpoint"""
        # Create test CSV data
        dates = pd.date_range(start='2025-01-01', periods=10, freq='D')
        data = {
            'date': dates,
            'value': np.random.normal(25, 5, 10)
        }
        df = pd.DataFrame(data)
        
        # Create in-memory CSV file
        csv_content = df.to_csv(index=False).encode('utf-8')
        csv_file = SimpleUploadedFile("test_data.csv", csv_content, content_type="text/csv")
        
        # Make API request
        url = reverse('csv_upload')
        response = self.client.post(url, {
            'file': csv_file,
            'twin_version_id': str(self.twin_version.id)
        })
        
        # Check response
        self.assertEqual(response.status_code, 201)
        
        # Verify document was created
        csv_docs = CSVDocument.objects.filter(title='test_data.csv')
        self.assertEqual(csv_docs.count(), 1)
        
    def test_csv_query_endpoint(self):
        """Test CSV query endpoint"""
        # Create a test CSV document
        csv_doc = CSVDocument.objects.create(
            title="test_data.csv",
            twin_version=self.twin_version,
            uploaded_by=self.user,
            row_count=10,
            column_count=2,
            status='completed'
        )
        
        # Make API request
        url = reverse('csv_document_query', kwargs={'document_id': str(csv_doc.id)})
        response = self.client.post(url, {
            'query': 'Show me statistics for this CSV'
        }, content_type='application/json')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertIn('message', response.json())

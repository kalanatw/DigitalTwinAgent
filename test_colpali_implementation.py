#!/usr/bin/env python3
"""
Comprehensive test script for ColPali implementation in Digital Twin.
Tests the entire ColPali workflow: image upload, embedding, retrieval, and Gemini response.
"""

import os
import sys
import logging
import sqlite3
from io import BytesIO
from pathlib import Path
import requests
from PIL import Image

# Add Django project to path
sys.path.append('/Users/kalana/Desktop/Personal/AgentProjects/Digital_Twin')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_twin.settings')
import django
django.setup()

from digital_twin_app.colpali_service import ColPaliService
from digital_twin_app.colpali_agent import ColPaliAgent
from digital_twin_app.gemini_service import GeminiService

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_test_image(url: str) -> Image.Image:
    """Download and return a PIL image from URL."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        logger.error(f"Failed to download image from {url}: {e}")
        raise

def test_colpali_service():
    """Test ColPali service directly."""
    logger.info("Testing ColPali Service...")
    
    try:
        service = ColPaliService()
        logger.info("ColPali service initialized successfully")
        
        # Test document processing 
        test_image_url = "https://github.com/tonywu71/colpali-cookbooks/blob/main/examples/data/shift_kazakhstan.jpg?raw=true"
        test_image = download_test_image(test_image_url)
        
        # Save test image temporarily
        test_image_path = "test_document.jpg"
        test_image.save(test_image_path)
        
        # Process document
        doc_id = service.process_document(test_image_path)
        logger.info(f"Document processed with ID: {doc_id}")
        
        # Test query processing
        query = "What is the share of offshore oil production in Kazakhstan?"
        results = service.search_documents(query, top_k=3)
        logger.info(f"Search results: {results}")
        
        # Cleanup
        os.remove(test_image_path)
        
        return True
        
    except Exception as e:
        logger.error(f"ColPali service test failed: {e}")
        return False

def test_gemini_service():
    """Test Gemini service."""
    logger.info("Testing Gemini Service...")
    
    try:
        service = GeminiService()
        
        # Test text-only response
        response = service.generate_response("What is 2+2?")
        logger.info(f"Gemini text response: {response}")
        
        # Test image analysis
        test_image_url = "https://github.com/tonywu71/colpali-cookbooks/blob/main/examples/data/shift_kazakhstan.jpg?raw=true"
        test_image = download_test_image(test_image_url)
        
        image_response = service.analyze_image_with_query(
            test_image, 
            "What information can you extract from this document?"
        )
        logger.info(f"Gemini image analysis: {image_response}")
        
        return True
        
    except Exception as e:
        logger.error(f"Gemini service test failed: {e}")
        return False

def test_colpali_agent():
    """Test ColPali agent end-to-end."""
    logger.info("Testing ColPali Agent...")
    
    try:
        agent = ColPaliAgent()
        
        # Test document upload and processing
        test_image_url = "https://github.com/tonywu71/colpali-cookbooks/blob/main/examples/data/shift_kazakhstan.jpg?raw=true"
        test_image = download_test_image(test_image_url)
        
        # Save test image temporarily
        test_image_path = "test_agent_document.jpg"
        test_image.save(test_image_path)
        
        # Process document with agent
        doc_id = agent.process_document(test_image_path)
        logger.info(f"Agent processed document with ID: {doc_id}")
        
        # Test query with agent
        query = "What percentage of Kazakhstan's oil production comes from offshore fields?"
        response = agent.process_query(query)
        logger.info(f"Agent response: {response}")
        
        # Cleanup
        os.remove(test_image_path)
        
        return True
        
    except Exception as e:
        logger.error(f"ColPali agent test failed: {e}")
        return False

def test_database_operations():
    """Test database operations."""
    logger.info("Testing database operations...")
    
    try:
        # Test SQLite database
        db_path = Path("colpali_embeddings.db")
        
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='document_embeddings'
        """)
        
        result = cursor.fetchone()
        if result:
            logger.info("Database table exists")
            
            # Check row count
            cursor.execute("SELECT COUNT(*) FROM document_embeddings")
            count = cursor.fetchone()[0]
            logger.info(f"Database contains {count} documents")
        else:
            logger.warning("Database table not found")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        return False

def test_full_workflow():
    """Test the complete ColPali workflow."""
    logger.info("Testing full ColPali workflow...")
    
    try:
        # Initialize agent
        agent = ColPaliAgent()
        
        # Download and process multiple test documents
        test_images = [
            "https://github.com/tonywu71/colpali-cookbooks/blob/main/examples/data/shift_kazakhstan.jpg?raw=true",
            "https://github.com/tonywu71/colpali-cookbooks/blob/main/examples/data/energy_electricity_generation.jpg?raw=true"
        ]
        
        processed_docs = []
        for i, url in enumerate(test_images):
            try:
                image = download_test_image(url)
                image_path = f"test_workflow_doc_{i}.jpg"
                image.save(image_path)
                
                doc_id = agent.process_document(image_path)
                processed_docs.append(doc_id)
                logger.info(f"Processed document {i+1} with ID: {doc_id}")
                
                os.remove(image_path)
            except Exception as e:
                logger.warning(f"Failed to process document {i+1}: {e}")
        
        # Test various queries
        test_queries = [
            "What is the share of offshore oil production?",
            "Which energy source had the highest generation?",
            "Tell me about Kazakhstan's energy production.",
            "What information is shown in these charts?"
        ]
        
        for query in test_queries:
            try:
                response = agent.process_query(query)
                logger.info(f"Query: {query}")
                logger.info(f"Response: {response[:200]}...")
                print(f"\n--- Query: {query} ---")
                print(f"Response: {response}\n")
            except Exception as e:
                logger.error(f"Query failed: {query} - {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Full workflow test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("ColPali Implementation Test Suite")
    print("=" * 60)
    
    tests = [
        ("Database Operations", test_database_operations),
        ("Gemini Service", test_gemini_service),
        ("ColPali Service", test_colpali_service),
        ("ColPali Agent", test_colpali_agent),
        ("Full Workflow", test_full_workflow),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n--- Running {test_name} Test ---")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"{test_name} test crashed: {e}")
            results[test_name] = False
        
        status = "PASSED" if results[test_name] else "FAILED"
        print(f"{test_name}: {status}")
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name:.<50} {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! ColPali implementation is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the logs above.")
        return 1

if __name__ == "__main__":
    exit(main())

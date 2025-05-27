#!/usr/bin/env python3
"""
Comprehensive test script for the Digital Twin Document System
Tests all major functionality end-to-end
"""

import requests
import json
import uuid
import time

BASE_URL = "http://127.0.0.1:8000"

def test_twin_version_management():
    """Test twin version creation and listing"""
    print("🔄 Testing Twin Version Management...")
    
    # Create a new twin version
    twin_data = {
        "name": "Test System v2.0",
        "version": "2.0.0",
        "description": "Advanced test twin version with enhanced features"
    }
    
    response = requests.post(f"{BASE_URL}/api/twin-versions/", json=twin_data)
    assert response.status_code == 201, f"Twin creation failed: {response.text}"
    
    twin_version = response.json()
    print(f"✅ Created twin version: {twin_version['name']} (ID: {twin_version['id']})")
    
    # List all twin versions
    response = requests.get(f"{BASE_URL}/api/twin-versions/")
    assert response.status_code == 200, f"Twin listing failed: {response.text}"
    
    twin_versions = response.json()
    print(f"✅ Listed {len(twin_versions)} twin versions")
    
    return twin_version['id']

def test_document_upload(twin_version_id):
    """Test document upload functionality"""
    print("🔄 Testing Document Upload...")
    
    # Create a test document
    test_content = """
    Digital Twin System Documentation
    
    This document contains comprehensive information about:
    1. Real-time sensor data monitoring and analysis
    2. Predictive maintenance algorithms and their implementation
    3. System performance optimization techniques
    4. Machine learning models for anomaly detection
    5. Integration with IoT devices and edge computing
    6. Data visualization and dashboard creation
    7. API documentation for third-party integrations
    8. Security protocols and access control mechanisms
    
    The system supports multiple data sources including temperature sensors,
    pressure monitoring, vibration analysis, and energy consumption tracking.
    """
    
    with open('/tmp/test_doc.txt', 'w') as f:
        f.write(test_content)
    
    # Upload the document
    with open('/tmp/test_doc.txt', 'rb') as f:
        files = {'file': f}
        data = {
            'twin_version_id': twin_version_id,
            'title': 'Digital Twin System Documentation',
            'description': 'Comprehensive documentation for the digital twin system'
        }
        
        response = requests.post(f"{BASE_URL}/api/documents/upload/", files=files, data=data)
        assert response.status_code == 200, f"Document upload failed: {response.text}"
    
    result = response.json()
    print(f"✅ Uploaded document: {result['document_id']}")
    
    # Wait for processing
    time.sleep(3)
    
    return result['document_id']

def test_semantic_search(twin_version_id):
    """Test semantic search functionality"""
    print("🔄 Testing Semantic Search...")
    
    # Test various search queries
    test_queries = [
        "sensor data monitoring",
        "machine learning anomaly detection",
        "IoT integration",
        "predictive maintenance",
        "system performance"
    ]
    
    for query in test_queries:
        search_data = {
            "query": query,
            "twin_version_id": twin_version_id,
            "top_k": 3
        }
        
        response = requests.post(f"{BASE_URL}/api/documents/search/", json=search_data)
        assert response.status_code == 200, f"Search failed for '{query}': {response.text}"
        
        results = response.json()
        print(f"✅ Search '{query}': Found {len(results.get('results', []))} results")
        
        if results.get('results'):
            best_result = results['results'][0]
            print(f"   Best match: {best_result['similarity']:.3f} similarity")

def test_chat_integration(twin_version_id):
    """Test chat integration with document context"""
    print("🔄 Testing Chat Integration...")
    
    test_messages = [
        "What sensor data can this system monitor?",
        "How does the predictive maintenance work?", 
        "Tell me about the machine learning capabilities",
        "What IoT devices are supported?"
    ]
    
    session_id = f"test-session-{uuid.uuid4()}"
    
    for message in test_messages:
        chat_data = {
            "message": message,
            "session_id": session_id,
            "twin_version_id": twin_version_id
        }
        
        response = requests.post(f"{BASE_URL}/api/chat/", json=chat_data)
        assert response.status_code == 200, f"Chat failed for '{message}': {response.text}"
        
        result = response.json()
        assert result['status'] == 'success', f"Chat error: {result}"
        
        print(f"✅ Chat query: '{message[:30]}...'")
        
        # Check if document context was used
        metadata = result.get('metadata', {})
        if metadata.get('document_context'):
            doc_count = metadata.get('documents_found', 0)
            print(f"   📄 Used {doc_count} document(s) for context")
        
        # Brief pause between requests
        time.sleep(0.5)

def test_document_management(twin_version_id):
    """Test document listing and management"""
    print("🔄 Testing Document Management...")
    
    # List documents for the twin version
    response = requests.get(f"{BASE_URL}/api/documents/?twin_version_id={twin_version_id}")
    assert response.status_code == 200, f"Document listing failed: {response.text}"
    
    data = response.json()
    docs = data.get('documents', [])
    print(f"✅ Listed {len(docs)} documents for twin version")
    
    return docs

def main():
    """Run comprehensive tests"""
    print("🚀 Starting Comprehensive Digital Twin System Tests\n")
    
    try:
        # Test 1: Twin Version Management
        twin_version_id = test_twin_version_management()
        print()
        
        # Test 2: Document Upload
        document_id = test_document_upload(twin_version_id)
        print()
        
        # Test 3: Semantic Search
        test_semantic_search(twin_version_id)
        print()
        
        # Test 4: Chat Integration
        test_chat_integration(twin_version_id)
        print()
        
        # Test 5: Document Management
        docs = test_document_management(twin_version_id)
        print()
        
        print("🎉 All tests completed successfully!")
        print(f"📊 Test Summary:")
        print(f"   - Twin Version ID: {twin_version_id}")
        print(f"   - Document ID: {document_id}")
        print(f"   - Documents found: {len(docs)}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())

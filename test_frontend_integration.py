#!/usr/bin/env python3
"""
Frontend Integration Test Script
Tests all the endpoints that the frontend DMS and Chat interfaces use
"""

import requests
import json
import time
from typing import List, Dict

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(method: str, url: str, data: dict = None, files: dict = None) -> dict:
    """Test an endpoint and return response data."""
    try:
        full_url = f"{BASE_URL}{url}"
        print(f"\n🔍 Testing {method} {url}")
        
        if method == "GET":
            response = requests.get(full_url)
        elif method == "POST":
            if files:
                response = requests.post(full_url, data=data, files=files)
            else:
                response = requests.post(full_url, json=data)
        elif method == "PATCH":
            response = requests.patch(full_url, json=data)
        elif method == "DELETE":
            response = requests.delete(full_url)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code < 400:
            try:
                response_data = response.json()
                print(f"   ✅ Success: {len(str(response_data))} characters")
                return response_data
            except:
                print(f"   ✅ Success: Non-JSON response")
                return {"success": True}
        else:
            print(f"   ❌ Error: {response.status_code} - {response.text[:100]}")
            return {"error": response.status_code, "message": response.text}
            
    except Exception as e:
        print(f"   💥 Exception: {str(e)}")
        return {"error": "exception", "message": str(e)}

def main():
    """Run comprehensive frontend integration tests."""
    
    print("🚀 Frontend Integration Test Suite")
    print("=" * 50)
    
    # Test 1: Twin Versions List (used by both DMS and Chat)
    print("\n📋 1. Testing Twin Versions Endpoint")
    twin_versions = test_endpoint("GET", "/api/twin-versions/")
    
    twin_version_id = None
    if isinstance(twin_versions, dict) and "twin_versions" in twin_versions:
        versions = twin_versions["twin_versions"]
        if versions:
            twin_version_id = versions[0]["id"]
            print(f"   Found {len(versions)} twin versions")
            print(f"   First version ID: {twin_version_id}")
    
    # Test 2: Create New Twin Version (DMS functionality)
    print("\n🆕 2. Testing Create Twin Version")
    new_version_data = {
        "name": "Frontend Test Version",
        "version": "1.0.0",
        "description": "Created by frontend integration test"
    }
    new_version = test_endpoint("POST", "/api/twin-versions/", new_version_data)
    
    if isinstance(new_version, dict) and "id" in new_version:
        test_twin_id = new_version["id"]
        print(f"   Created test twin version: {test_twin_id}")
    else:
        test_twin_id = twin_version_id
    
    # Test 3: Document Upload (DMS functionality)
    print("\n📄 3. Testing Document Upload")
    if test_twin_id:
        # Create a test file
        test_content = "This is a test document for frontend integration testing.\nIt contains multiple lines and should be processed correctly."
        files = {
            'file': ('test_frontend.txt', test_content, 'text/plain')
        }
        upload_data = {
            'twin_version_id': test_twin_id,
            'title': 'Frontend Integration Test Document',
            'description': 'Test document for verifying frontend upload functionality'
        }
        
        upload_result = test_endpoint("POST", "/api/documents/upload/", upload_data, files)
        
        document_id = None
        if isinstance(upload_result, dict) and "id" in upload_result:
            document_id = upload_result["id"]
            print(f"   Uploaded document ID: {document_id}")
    
    # Test 4: Documents List (DMS functionality)
    print("\n📚 4. Testing Documents List")
    if test_twin_id:
        documents = test_endpoint("GET", f"/api/documents/?twin_version_id={test_twin_id}")
        
        if isinstance(documents, dict) and "documents" in documents:
            docs = documents["documents"]
            print(f"   Found {len(docs)} documents for twin version")
            if docs:
                print(f"   First document: {docs[0].get('title', 'N/A')}")
    
    # Test 5: Semantic Search (Both DMS and Chat functionality)
    print("\n🧠 5. Testing Semantic Search")
    if test_twin_id:
        search_data = {
            "query": "test document integration",
            "twin_version_id": test_twin_id,
            "top_k": 5
        }
        search_results = test_endpoint("POST", "/api/documents/search/", search_data)
        
        if isinstance(search_results, list):
            print(f"   Found {len(search_results)} search results")
            for i, result in enumerate(search_results[:2]):
                similarity = result.get("similarity", 0)
                print(f"   Result {i+1}: {similarity:.2%} similarity")
    
    # Test 6: Chat Endpoint (Chat functionality)
    print("\n💬 6. Testing Chat Endpoint")
    chat_data = {
        "message": "Hello, what can you tell me about the test documents?",
        "session_id": f"test_session_{int(time.time())}",
    }
    
    if test_twin_id:
        chat_data["twin_version_id"] = test_twin_id
    
    chat_response = test_endpoint("POST", "/api/chat/", chat_data)
    
    if isinstance(chat_response, dict) and "response" in chat_response:
        response_text = chat_response["response"]
        print(f"   Chat response length: {len(response_text)} characters")
        print(f"   Response preview: {response_text[:100]}...")
    
    # Test 7: Document Status Toggle (DMS functionality)
    print("\n🔄 7. Testing Document Status Toggle")
    if document_id:
        status_data = {"is_enabled": False}
        status_result = test_endpoint("PATCH", f"/api/documents/{document_id}/", status_data)
        
        if isinstance(status_result, dict):
            new_status = status_result.get("is_enabled", "unknown")
            print(f"   Document enabled status: {new_status}")
    
    # Test 8: Document Search with Filters (DMS functionality)
    print("\n🔍 8. Testing Document Search with Filters")
    if test_twin_id:
        search_params = f"twin_version_id={test_twin_id}&search=test&status=completed"
        filtered_docs = test_endpoint("GET", f"/api/documents/?{search_params}")
        
        if isinstance(filtered_docs, dict) and "documents" in filtered_docs:
            filtered_count = len(filtered_docs["documents"])
            print(f"   Filtered documents count: {filtered_count}")
    
    # Test 9: DMS Frontend Page Load
    print("\n🖥️  9. Testing DMS Frontend Page")
    try:
        response = requests.get(f"{BASE_URL}/dms/")
        print(f"   DMS page status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ DMS page loads successfully")
        else:
            print(f"   ❌ DMS page error: {response.status_code}")
    except Exception as e:
        print(f"   💥 DMS page exception: {e}")
    
    # Test 10: Chat Frontend Page Load
    print("\n💬 10. Testing Chat Frontend Page")
    try:
        response = requests.get(f"{BASE_URL}/chat/")
        print(f"   Chat page status: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Chat page loads successfully")
        else:
            print(f"   ❌ Chat page error: {response.status_code}")
    except Exception as e:
        print(f"   💥 Chat page exception: {e}")
    
    # Cleanup: Delete test document
    print("\n🧹 11. Cleanup - Delete Test Document")
    if document_id:
        delete_result = test_endpoint("DELETE", f"/api/documents/{document_id}/")
        if isinstance(delete_result, dict):
            print("   ✅ Test document deleted")
    
    print("\n" + "=" * 50)
    print("🎉 Frontend Integration Test Suite Complete!")
    print("\nIf all tests show ✅, your frontend integration is working correctly.")
    print("Any ❌ or 💥 indicates issues that need to be addressed.")

if __name__ == "__main__":
    main()

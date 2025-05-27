#!/usr/bin/env python3
"""
Test script to validate document search and chat functionality.
"""
import os
import sys
import django
import asyncio
from django.core.wsgi import get_wsgi_application
from asgiref.sync import sync_to_async

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_twin.settings')
django.setup()

from digital_twin_app.document_utils import SemanticSearch
from digital_twin_app.models import TwinVersion, Document


async def test_document_search():
    """Test the semantic search functionality."""
    print("Testing Document Search Functionality...")
    
    # Get a twin version with documents
    try:
        twin_version = await sync_to_async(TwinVersion.objects.filter(is_active=True).first)()
        if not twin_version:
            print("❌ No active twin versions found")
            return False
            
        print(f"✅ Found twin version: {twin_version.name}")
        
        # Check if there are documents
        document_count = await sync_to_async(Document.objects.filter(
            twin_version=twin_version,
            is_enabled=True,
            status='completed'
        ).count)()
        
        if document_count == 0:
            print("❌ No completed documents found")
            return False
            
        print(f"✅ Found {document_count} documents")
        
        # Test semantic search
        semantic_search = SemanticSearch()
        
        # Test query
        query = "digital twin technology applications"
        print(f"\n🔍 Searching for: '{query}'")
        
        results = await semantic_search.search_documents(
            query=query,
            twin_version_id=str(twin_version.id),
            top_k=3
        )
        
        if not results:
            print("❌ No search results found")
            return False
            
        print(f"✅ Found {len(results)} search results:")
        
        for i, result in enumerate(results, 1):
            print(f"\n  {i}. Document: {result['title']}")
            print(f"     Similarity: {result['similarity']:.4f}")
            print(f"     Content preview: {result['content'][:100]}...")
        
        # Test context generation
        print(f"\n📄 Testing context generation...")
        try:
            context = await semantic_search.get_context_for_chat(
                query=query,
                twin_version_id=str(twin_version.id),
                max_context_length=1000
            )
            
            print(f"Debug: Context length = {len(context) if context else 0}")
            print(f"Debug: Context type = {type(context)}")
            
            if not context or len(context.strip()) == 0:
                print("❌ No context generated or context is empty")
                # Let's try to debug why
                print("Debug: Retrying with larger context length...")
                context = await semantic_search.get_context_for_chat(
                    query=query,
                    twin_version_id=str(twin_version.id),
                    max_context_length=5000
                )
                print(f"Debug: Retry context length = {len(context) if context else 0}")
                
                if not context or len(context.strip()) == 0:
                    print("❌ Still no context generated")
                    return False
                else:
                    print(f"✅ Generated context with larger limit ({len(context)} characters)")
            else:
                print(f"✅ Generated context ({len(context)} characters)")
            
            print(f"Context preview: {context[:200]}...")
            
            return True
        except Exception as e:
            print(f"❌ Error generating context: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("🚀 Digital Twin Document Search Test\n")
    
    success = await test_document_search()
    
    if success:
        print("\n🎉 All tests passed! Document search is working correctly.")
    else:
        print("\n💥 Some tests failed. Please check the error messages above.")
    
    return success


if __name__ == "__main__":
    asyncio.run(main())

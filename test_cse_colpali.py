#!/usr/bin/env python3
"""
ColPali CSE Document Test Script

Tests the ColPali implementation using the Colombo Stock Exchange (CSE) merged PDF document.
This script will:
1. Convert the PDF to images
2. Process them with ColPali embeddings
3. Test various financial queries
4. Demonstrate end-to-end retrieval and response generation
"""

import os
import sys
import logging
import tempfile
import shutil
from pathlib import Path

# Add Django project to path
sys.path.append('/Users/kalana/Desktop/Personal/AgentProjects/Digital_Twin')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'digital_twin.settings')
import django
django.setup()

from digital_twin_app.pdf_processor import PDFProcessor
from digital_twin_app.colpali_service import ColPaliService
from digital_twin_app.colpali_agent import ColPaliAgent
from digital_twin_app.gemini_service import GeminiService

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CSEDocumentTester:
    """Test ColPali implementation with CSE financial document."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.temp_dir = None
        self.processor = PDFProcessor(dpi=200)
        self.colpali_service = None
        self.colpali_agent = None
        self.gemini_service = None
        
    async def setup(self):
        """Setup test environment."""
        logger.info("Setting up CSE document test environment...")
        
        # Create temporary directory for images
        self.temp_dir = tempfile.mkdtemp(prefix="cse_test_")
        logger.info(f"Created temporary directory: {self.temp_dir}")
        
        # Initialize services
        self.colpali_service = ColPaliService()
        self.colpali_agent = ColPaliAgent()
        self.gemini_service = GeminiService()
        
        # Initialize ColPali service
        await self.colpali_service.initialize()
        
    async def cleanup(self):
        """Cleanup test environment."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
    
    async def test_pdf_processing(self):
        """Test PDF to image conversion."""
        logger.info("Testing PDF processing...")
        
        if not os.path.exists(self.pdf_path):
            raise FileNotFoundError(f"CSE PDF not found at: {self.pdf_path}")
        
        try:
            # Convert PDF to images
            image_paths = self.processor.save_images_from_pdf(
                self.pdf_path, 
                self.temp_dir
            )
            
            logger.info(f"Successfully converted PDF to {len(image_paths)} images")
            
            # Display info about each page
            for i, path in enumerate(image_paths):
                size = os.path.getsize(path)
                logger.info(f"Page {i+1}: {os.path.basename(path)} ({size:,} bytes)")
            
            return image_paths
            
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            raise
    
    async def test_colpali_embeddings(self, image_paths: list):
        """Test ColPali embedding generation."""
        logger.info("Testing ColPali embedding generation...")
        
        processed_docs = []
        
        for i, image_path in enumerate(image_paths):
            try:
                # Process document with ColPali
                doc_id = await self.colpali_service.process_document(image_path)
                processed_docs.append({
                    'doc_id': doc_id,
                    'page': i + 1,
                    'path': image_path
                })
                logger.info(f"Processed page {i+1} with document ID: {doc_id}")
                
            except Exception as e:
                logger.error(f"Failed to process page {i+1}: {e}")
        
        logger.info(f"Successfully processed {len(processed_docs)} pages")
        return processed_docs
    
    async def test_financial_queries(self):
        """Test various financial queries relevant to CSE data."""
        logger.info("Testing financial queries...")
        
        # CSE-specific financial queries
        test_queries = [
            "What are the sector-wise price movements in the CSE?",
            "Which sectors showed the highest growth?",
            "What is the market capitalization information?",
            "Show me the banking sector performance",
            "What are the top performing stocks?",
            "Which companies are listed in the manufacturing sector?",
            "What is the price-to-earnings ratio data?",
            "Show dividend yield information",
            "What are the trading volumes by sector?",
            "Which sectors have the lowest volatility?",
            "What is the overall market trend shown?",
            "Show me telecommunications sector data",
            "What companies are in the food and beverage sector?",
            "Display the energy sector performance",
            "What are the real estate sector metrics?"
        ]
        
        results = []
        
        for query in test_queries:
            try:
                logger.info(f"Processing query: {query}")
                
                # Test with ColPali agent
                response = await self.colpali_agent.process_query(query)
                
                result = {
                    'query': query,
                    'response': response,
                    'success': True
                }
                results.append(result)
                
                # Display result
                print(f"\n{'='*60}")
                print(f"Query: {query}")
                print(f"{'='*60}")
                print(f"Response: {response}")
                
            except Exception as e:
                logger.error(f"Query failed: {query} - {e}")
                results.append({
                    'query': query,
                    'response': str(e),
                    'success': False
                })
        
        return results
    
    async def test_similarity_search(self):
        """Test similarity search functionality."""
        logger.info("Testing similarity search...")
        
        test_queries = [
            "banking sector performance",
            "market capitalization",
            "dividend yields",
            "price volatility"
        ]
        
        for query in test_queries:
            try:
                # Search for similar documents
                results = await self.colpali_service.search_documents(query, top_k=5)
                
                print(f"\n--- Similarity Search: {query} ---")
                for i, result in enumerate(results):
                    print(f"{i+1}. Document ID: {result['doc_id']}, Score: {result['score']:.4f}")
                
            except Exception as e:
                logger.error(f"Similarity search failed for '{query}': {e}")
    
    async def generate_test_report(self, results: list):
        """Generate a comprehensive test report."""
        logger.info("Generating test report...")
        
        total_queries = len(results)
        successful_queries = sum(1 for r in results if r['success'])
        success_rate = (successful_queries / total_queries) * 100 if total_queries > 0 else 0
        
        report = f"""
{'='*80}
COLPALI CSE DOCUMENT TEST REPORT
{'='*80}

PDF Document: {self.pdf_path}
Test Date: {os.system('date')}

SUMMARY:
--------
Total Queries Tested: {total_queries}
Successful Queries: {successful_queries}
Failed Queries: {total_queries - successful_queries}
Success Rate: {success_rate:.1f}%

QUERY RESULTS:
--------------
"""
        
        for i, result in enumerate(results, 1):
            status = "✓ SUCCESS" if result['success'] else "✗ FAILED"
            report += f"\n{i:2d}. {status} - {result['query']}"
            if not result['success']:
                report += f"\n    Error: {result['response']}"
        
        report += f"\n\n{'='*80}"
        
        # Save report to file
        report_path = os.path.join(self.temp_dir, "cse_test_report.txt")
        with open(report_path, 'w') as f:
            f.write(report)
        
        print(report)
        logger.info(f"Test report saved to: {report_path}")
        
        return report_path

async def main():
    """Main test execution."""
    cse_pdf_path = "/Users/kalana/Downloads/CSE Data/CSE_merged.pdf"
    
    tester = CSEDocumentTester(cse_pdf_path)
    
    try:
        # Setup test environment
        await tester.setup()
        
        # Test PDF processing
        image_paths = await tester.test_pdf_processing()
        
        # Test ColPali embeddings
        processed_docs = await tester.test_colpali_embeddings(image_paths)
        
        # Test similarity search
        await tester.test_similarity_search()
        
        # Test financial queries
        query_results = await tester.test_financial_queries()
        
        # Generate test report
        report_path = await tester.generate_test_report(query_results)
        
        print(f"\n🎉 CSE Document test completed successfully!")
        print(f"Report saved to: {report_path}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"\n❌ Test failed: {e}")
        return 1
        
    finally:
        # Cleanup
        await tester.cleanup()

if __name__ == "__main__":
    import asyncio
    exit(asyncio.run(main()))

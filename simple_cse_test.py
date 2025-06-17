#!/usr/bin/env python3
"""
Simple ColPali CSE Test Script

A standalone test for ColPali functionality with the CSE document,
without Django dependencies for easier testing.
"""

import os
import sys
import logging
import tempfile
import shutil
from pathlib import Path
from typing import List
from PIL import Image

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    try:
        import pymupdf as fitz
        PYMUPDF_AVAILABLE = True
    except ImportError:
        logger.error("PyMuPDF not available. Install with: pip install PyMuPDF")
        PYMUPDF_AVAILABLE = False

try:
    from colpali_engine.models import ColQwen2, ColQwen2Processor
    from colpali_engine.utils.torch_utils import get_torch_device
    import torch
    COLPALI_AVAILABLE = True
except ImportError as e:
    logger.error(f"ColPali not available: {e}")
    COLPALI_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    logger.error("Google Generative AI not available")
    GEMINI_AVAILABLE = False


class SimpleCSETester:
    """Simple CSE document tester for ColPali."""
    
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.temp_dir = None
        self.model = None
        self.processor = None
        
    def setup(self):
        """Setup test environment."""
        logger.info("Setting up CSE test environment...")
        
        # Create temp directory
        self.temp_dir = tempfile.mkdtemp(prefix="cse_test_")
        logger.info(f"Created temp directory: {self.temp_dir}")
        
        # Check availability
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF is required")
        if not COLPALI_AVAILABLE:
            raise ImportError("ColPali engine is required")
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Generative AI is required")
    
    def cleanup(self):
        """Cleanup test environment."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info("Cleaned up temp directory")
    
    def pdf_to_images(self) -> List[str]:
        """Convert PDF to images."""
        logger.info("Converting PDF to images...")
        
        if not os.path.exists(self.pdf_path):
            raise FileNotFoundError(f"PDF not found: {self.pdf_path}")
        
        image_paths = []
        
        try:
            doc = fitz.open(self.pdf_path)
            
            for page_num in range(min(5, doc.page_count)):  # Limit to first 5 pages for testing
                page = doc[page_num]
                
                # Convert to image
                mat = fitz.Matrix(1.5, 1.5)  # 150 DPI
                pix = page.get_pixmap(matrix=mat)
                
                # Save as image
                img_path = os.path.join(self.temp_dir, f"page_{page_num+1:03d}.jpg")
                pix.save(img_path)
                image_paths.append(img_path)
                
                logger.info(f"Saved page {page_num+1} to {img_path}")
            
            doc.close()
            logger.info(f"Converted {len(image_paths)} pages")
            
        except Exception as e:
            logger.error(f"PDF conversion failed: {e}")
            raise
        
        return image_paths
    
    def test_colpali_model(self, image_paths: List[str]):
        """Test ColPali model loading and processing."""
        logger.info("Testing ColPali model...")
        
        try:
            # Load model
            device = get_torch_device("auto")
            model_name = "vidore/colqwen2-v1.0"
            
            logger.info(f"Loading model {model_name} on {device}")
            
            self.model = ColQwen2.from_pretrained(
                model_name,
                torch_dtype=torch.bfloat16,
                device_map=device,
            )
            
            self.processor = ColQwen2Processor.from_pretrained(model_name)
            
            logger.info("Model loaded successfully")
            
            # Test processing first image
            if image_paths:
                test_image = Image.open(image_paths[0])
                logger.info(f"Testing with image: {test_image.size}")
                
                # Process image
                batch_images = self.processor.process_images([test_image]).to(device)
                
                with torch.no_grad():
                    embeddings = self.model.forward(**batch_images)
                    logger.info(f"Generated embeddings shape: {embeddings.shape}")
                
                # Test query
                test_query = "financial data"
                batch_queries = self.processor.process_queries([test_query]).to(device)
                
                with torch.no_grad():
                    query_embeddings = self.model.forward(**batch_queries)
                    logger.info(f"Query embeddings shape: {query_embeddings.shape}")
                
                # Test similarity
                scores = self.processor.score_multi_vector(query_embeddings, embeddings)
                logger.info(f"Similarity score: {scores.item():.4f}")
                
                return True
                
        except Exception as e:
            logger.error(f"ColPali test failed: {e}")
            return False
    
    def test_gemini_analysis(self, image_paths: List[str]):
        """Test Gemini image analysis."""
        logger.info("Testing Gemini analysis...")
        
        try:
            # Setup Gemini (you'll need to set your API key)
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                logger.warning("GEMINI_API_KEY not set, skipping Gemini test")
                return False
            
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-pro-latest')
            
            # Test with first image
            if image_paths:
                image = Image.open(image_paths[0])
                
                response = model.generate_content([
                    "Analyze this financial document and tell me what sector information you can see:",
                    image
                ])
                
                logger.info(f"Gemini response: {response.text[:200]}...")
                return True
                
        except Exception as e:
            logger.error(f"Gemini test failed: {e}")
            return False
    
    def run_tests(self):
        """Run all tests."""
        try:
            self.setup()
            
            # Test PDF conversion
            image_paths = self.pdf_to_images()
            
            # Test ColPali
            colpali_success = self.test_colpali_model(image_paths)
            
            # Test Gemini
            gemini_success = self.test_gemini_analysis(image_paths)
            
            # Results
            print("\n" + "="*60)
            print("TEST RESULTS")
            print("="*60)
            print(f"PDF Conversion: ✓ SUCCESS ({len(image_paths)} pages)")
            print(f"ColPali Model: {'✓ SUCCESS' if colpali_success else '✗ FAILED'}")
            print(f"Gemini Analysis: {'✓ SUCCESS' if gemini_success else '✗ FAILED'}")
            
            if colpali_success and gemini_success:
                print("\n🎉 All tests passed! ColPali implementation is working.")
                return 0
            else:
                print("\n❌ Some tests failed. Check logs above.")
                return 1
                
        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            print(f"\n❌ Test suite failed: {e}")
            return 1
            
        finally:
            self.cleanup()


def main():
    """Main test execution."""
    print("="*60)
    print("ColPali CSE Document Test")
    print("="*60)
    
    cse_pdf_path = "/Users/kalana/Downloads/CSE Data/CSE_merged.pdf"
    
    if not os.path.exists(cse_pdf_path):
        print(f"❌ CSE PDF not found at: {cse_pdf_path}")
        print("Please ensure the file exists and try again.")
        return 1
    
    tester = SimpleCSETester(cse_pdf_path)
    return tester.run_tests()


if __name__ == "__main__":
    exit(main())

"""
PDF Processing Utilities for ColPali Implementation
"""
import os
import logging
from typing import List, Tuple
from PIL import Image

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    try:
        import pymupdf as fitz
        PYMUPDF_AVAILABLE = True
    except ImportError:
        PYMUPDF_AVAILABLE = False

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Utility class for processing PDF files into images for ColPali."""
    
    def __init__(self, dpi: int = 200):
        """
        Initialize PDF processor.
        
        Args:
            dpi: Resolution for PDF to image conversion (default: 200)
        """
        self.dpi = dpi
    
    def pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """
        Convert PDF pages to PIL Images.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            List of PIL Images, one per page
        """
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF is required for PDF processing. Install with: pip install PyMuPDF")
        
        images = []
        
        try:
            # Open PDF with PyMuPDF
            doc = fitz.open(pdf_path)
            
            for page_num in range(doc.page_count):
                page = doc[page_num]
                
                # Convert page to image
                mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)  # Scale factor
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PIL Image
                img_data = pix.tobytes("ppm")
                from io import BytesIO
                img = Image.open(BytesIO(img_data))
                images.append(img)
                
                logger.info(f"Processed page {page_num + 1}/{doc.page_count}")
            
            doc.close()
            logger.info(f"Successfully converted {len(images)} pages from {pdf_path}")
            
        except Exception as e:
            logger.error(f"Failed to process PDF {pdf_path}: {e}")
            raise
        
        return images
    
    def save_images_from_pdf(self, pdf_path: str, output_dir: str) -> List[str]:
        """
        Convert PDF to images and save them to disk.
        
        Args:
            pdf_path: Path to PDF file
            output_dir: Directory to save images
            
        Returns:
            List of saved image file paths
        """
        os.makedirs(output_dir, exist_ok=True)
        
        images = self.pdf_to_images(pdf_path)
        saved_paths = []
        
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        for i, img in enumerate(images):
            output_path = os.path.join(output_dir, f"{pdf_name}_page_{i+1:03d}.jpg")
            img.save(output_path, "JPEG", quality=95)
            saved_paths.append(output_path)
            
        logger.info(f"Saved {len(saved_paths)} images to {output_dir}")
        return saved_paths

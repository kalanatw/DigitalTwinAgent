"""
Gemini API Service for Image-to-Text Generation

This module provides integration with Google Gemini API for generating
text responses based on images and queries.
"""
import logging
import asyncio
from typing import List, Dict, Any, Optional
from PIL import Image
import io
import base64
from django.conf import settings

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Gemini API dependencies not available: {e}")
    GEMINI_AVAILABLE = False


class GeminiService:
    """
    Service class for Google Gemini API integration.
    Handles image-to-text generation and multimodal responses.
    """
    
    def __init__(self):
        self.model = None
        self.api_key = None
        self._initialized = False
        
    async def initialize(self):
        """Initialize Gemini API connection."""
        if self._initialized or not GEMINI_AVAILABLE:
            return
            
        try:
            # Get API key from settings
            self.api_key = getattr(settings, 'GEMINI_API_KEY', None)
            if not self.api_key:
                logger.error("GEMINI_API_KEY not found in settings")
                return
            
            # Configure the API
            genai.configure(api_key=self.api_key)
            
            # Initialize the model
            self.model = genai.GenerativeModel('gemini-1.5-pro')
            
            self._initialized = True
            logger.info("Gemini API service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Gemini service: {e}")
            raise
    
    async def generate_response_from_images(self, 
                                          query: str, 
                                          image_paths: List[str],
                                          context: str = "") -> Dict[str, Any]:
        """
        Generate a text response based on query and images.
        
        Args:
            query: User query/question
            image_paths: List of image file paths
            context: Additional context for the response
            
        Returns:
            Dict containing the generated response and metadata
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._initialized:
            return {
                "success": False,
                "error": "Gemini service not available",
                "response": "Sorry, the image analysis service is currently unavailable."
            }
        
        try:
            logger.info(f"Generating response for query: {query} with {len(image_paths)} images")
            
            # Load and prepare images
            images = []
            for image_path in image_paths:
                try:
                    image = Image.open(image_path)
                    images.append(image)
                except Exception as e:
                    logger.warning(f"Failed to load image {image_path}: {e}")
            
            if not images:
                return {
                    "success": False,
                    "error": "No valid images found",
                    "response": "No images were available for analysis."
                }
            
            # Prepare the prompt
            prompt_parts = []
            
            # Add context if provided
            if context:
                prompt_parts.append(f"Context: {context}\n\n")
            
            # Add the main query
            prompt_parts.append(f"Query: {query}\n\n")
            
            # Add instruction for image analysis
            prompt_parts.append(
                "Please analyze the provided images and answer the query based on the visual content. "
                "If the images contain documents, tables, charts, or text, please extract and interpret "
                "the relevant information to answer the question accurately."
            )
            
            # Combine prompt
            prompt = "".join(prompt_parts)
            
            # Create content list with prompt and images
            content = [prompt] + images
            
            # Generate response
            response = await asyncio.get_event_loop().run_in_executor(
                None, self.model.generate_content, content
            )
            
            return {
                "success": True,
                "response": response.text,
                "metadata": {
                    "model": "gemini-1.5-pro",
                    "images_processed": len(images),
                    "query": query
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to generate response from images: {e}")
            return {
                "success": False,
                "error": str(e),
                "response": f"Sorry, I encountered an error while analyzing the images: {str(e)}"
            }
    
    async def analyze_document_images(self, 
                                    image_paths: List[str],
                                    analysis_type: str = "general") -> Dict[str, Any]:
        """
        Analyze document images for content extraction.
        
        Args:
            image_paths: List of image file paths
            analysis_type: Type of analysis (general, table, chart, text)
            
        Returns:
            Dict containing analysis results
        """
        if not self._initialized:
            await self.initialize()
        
        if not self._initialized:
            return {"success": False, "error": "Gemini service not available"}
        
        try:
            # Define analysis prompts based on type
            analysis_prompts = {
                "general": "Analyze these document images and provide a comprehensive summary of the content.",
                "table": "Extract and structure any tabular data found in these images. Present the data in a clear, organized format.",
                "chart": "Describe any charts, graphs, or visual data representations in these images. Include key insights and data points.",
                "text": "Extract all text content from these images, maintaining the original structure and formatting as much as possible."
            }
            
            prompt = analysis_prompts.get(analysis_type, analysis_prompts["general"])
            
            # Use the general response generation method
            result = await self.generate_response_from_images("", image_paths, prompt)
            
            # Add analysis type to metadata
            if result["success"]:
                result["metadata"]["analysis_type"] = analysis_type
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze document images: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def is_available(self) -> bool:
        """Check if Gemini service is available."""
        return GEMINI_AVAILABLE and self._initialized


# Global service instance
gemini_service = GeminiService()

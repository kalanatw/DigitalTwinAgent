"""
ColPali Agent Implementation

This module provides the ColPali-based agent that uses visual document retrieval
and Gemini API for multimodal responses.
"""
import logging
import asyncio
import os
from typing import Dict, Any, List, Optional
from django.conf import settings
from .colpali_service import colpali_service
from .gemini_service import gemini_service
from .document_utils import get_semantic_search_results

logger = logging.getLogger(__name__)


class ColPaliAgent:
    """
    ColPali-powered agent for visual document retrieval and analysis.
    Uses ColPali for image embeddings, Milvus for storage, and Gemini for responses.
    """
    
    def __init__(self, custom_config=None):
        """Initialize the ColPali Agent."""
        self.custom_config = custom_config or {}
        self.name = self.custom_config.get('name', 'ColPali Visual Agent')
        self.model_name = 'colpali'
        self._initialized = False
        
    async def process_document(self, document_path: str) -> str:
        """
        Process a document with ColPali embeddings.
        
        Args:
            document_path: Path to the document image file
            
        Returns:
            Document ID for the processed document
        """
        await self.initialize()
        
        try:
            doc_id = await colpali_service.process_document(document_path)
            logger.info(f"Processed document: {document_path} -> {doc_id}")
            return doc_id
            
        except Exception as e:
            logger.error(f"Failed to process document {document_path}: {e}")
            raise
    
    async def process_query(self, query: str, top_k: int = 5) -> str:
        """
        Process a query using ColPali retrieval and Gemini generation.
        
        Args:
            query: User query
            top_k: Number of top documents to retrieve
            
        Returns:
            Generated response from Gemini
        """
        await self.initialize()
        
        try:
            # Search for relevant documents using ColPali
            search_results = await colpali_service.search_documents(query, top_k=top_k)
            
            if not search_results:
                return "I couldn't find any relevant documents for your query."
            
            # Get the most relevant image for Gemini analysis
            best_result = search_results[0]
            image_path = best_result.get('image_path')
            
            if not image_path or not os.path.exists(image_path):
                logger.warning(f"Image path not found: {image_path}")
                return "I found relevant documents but couldn't access the image data."
            
            # Analyze with Gemini
            from PIL import Image
            image = Image.open(image_path)
            
            response = await gemini_service.analyze_image_with_query(image, query)
            
            # Add context about the search
            context_info = f"\n\nThis response is based on analysis of {len(search_results)} relevant document(s) from your collection."
            
            return response + context_info
            
        except Exception as e:
            logger.error(f"Failed to process query '{query}': {e}")
            return f"I encountered an error while processing your query: {str(e)}"
    
    async def process_query(self, query: str, twin_version_id: str = None, **kwargs) -> Dict[str, Any]:
        """
        Process a query using ColPali visual retrieval and Gemini response generation.
        
        Args:
            query: User query
            twin_version_id: Optional twin version ID for document context
            **kwargs: Additional parameters
            
        Returns:
            Dict containing the agent response and metadata
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info(f"Processing ColPali query: {query}")
            
            # Check if services are available
            if not colpali_service.is_available():
                return await self._fallback_text_response(query, twin_version_id)
            
            if not gemini_service.is_available():
                return {
                    "success": False,
                    "response": "Visual analysis service is currently unavailable. Please try again later.",
                    "agent_name": self.name,
                    "model": self.model_name
                }
            
            # Search for relevant images using ColPali
            similar_images = await colpali_service.search_similar_images(query, top_k=5)
            
            if not similar_images:
                # Fallback to text-based search if no images found
                return await self._fallback_text_response(query, twin_version_id)
            
            # Extract image paths from results  
            image_base64_list = []
            for img in similar_images:
                if img.get("image_base64"):
                    image_base64_list.append(img["image_base64"])
            
            if not image_base64_list:
                return await self._fallback_text_response(query, twin_version_id)
            
            # Convert base64 images to temporary files for Gemini
            import tempfile
            temp_image_paths = []
            try:
                for i, img_base64 in enumerate(image_base64_list):
                    # Decode base64 to image
                    import base64
                    import io
                    from PIL import Image
                    
                    img_data = base64.b64decode(img_base64)
                    image = Image.open(io.BytesIO(img_data))
                    
                    # Save to temporary file
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                    image.save(temp_file.name, format='PNG')
                    temp_image_paths.append(temp_file.name)
                
                # Generate response using Gemini
                context = self._build_context(similar_images, twin_version_id)
                gemini_response = await gemini_service.generate_response_from_images(
                    query=query,
                    image_paths=temp_image_paths,
                    context=context
                )
                
            finally:
                # Clean up temporary files
                for temp_path in temp_image_paths:
                    try:
                        os.unlink(temp_path)
                    except:
                        pass
            
            if gemini_response["success"]:
                return {
                    "success": True,
                    "response": gemini_response["response"],
                    "agent_name": self.name,
                    "model": self.model_name,
                    "metadata": {
                        "visual_retrieval": True,
                        "images_analyzed": len(temp_image_paths),
                        "similar_images": similar_images,
                        "gemini_metadata": gemini_response.get("metadata", {})
                    }
                }
            else:
                return {
                    "success": False,
                    "response": gemini_response.get("response", "Failed to generate response"),
                    "agent_name": self.name,
                    "model": self.model_name,
                    "error": gemini_response.get("error")
                }
                
        except Exception as e:
            logger.error(f"Error processing ColPali query: {e}")
            return {
                "success": False,
                "response": f"An error occurred while processing your query: {str(e)}",
                "agent_name": self.name,
                "model": self.model_name,
                "error": str(e)
            }
    
    async def _fallback_text_response(self, query: str, twin_version_id: str = None) -> Dict[str, Any]:
        """
        Fallback to text-based search when visual search is not available or returns no results.
        """
        try:
            logger.info("Using text-based fallback for ColPali agent")
            
            # Use existing semantic search as fallback
            if twin_version_id:
                search_results = await get_semantic_search_results(query, twin_version_id)
                
                if search_results:
                    context = "\n".join([
                        f"Document: {result.get('filename', 'Unknown')}\n"
                        f"Content: {result.get('content', '')}\n"
                        for result in search_results[:3]
                    ])
                    
                    response = f"Based on the available documents, here's what I found:\n\n{context}\n\n"
                    response += f"Regarding your question: {query}\n\n"
                    response += "Note: Visual analysis was not available, so this response is based on text content only."
                    
                    return {
                        "success": True,
                        "response": response,
                        "agent_name": self.name,
                        "model": self.model_name,
                        "metadata": {
                            "visual_retrieval": False,
                            "text_search_results": len(search_results),
                            "fallback_used": True
                        }
                    }
            
            # Default response when no context is available
            return {
                "success": True,
                "response": "I'm the ColPali Visual Agent, specialized in analyzing document images. However, no relevant visual content was found for your query, and no document context was provided. Please ensure you have uploaded documents with images or provide a twin version ID.",
                "agent_name": self.name,
                "model": self.model_name,
                "metadata": {
                    "visual_retrieval": False,
                    "fallback_used": True
                }
            }
            
        except Exception as e:
            logger.error(f"Error in fallback text response: {e}")
            return {
                "success": False,
                "response": f"Unable to process your query: {str(e)}",
                "agent_name": self.name,
                "model": self.model_name,
                "error": str(e)
            }
    
    def _build_context(self, similar_images: List[Dict[str, Any]], twin_version_id: str = None) -> str:
        """Build context string from similar images and metadata."""
        context_parts = []
        
        if twin_version_id:
            context_parts.append(f"Document context: Twin version {twin_version_id}")
        
        context_parts.append("Found relevant visual content in the following sources:")
        
        for i, img in enumerate(similar_images, 1):
            doc_id = img.get("document_id", "Unknown")
            page_num = img.get("page_number", "Unknown")
            similarity = img.get("similarity_score", 0.0)
            
            context_parts.append(
                f"{i}. Document: {doc_id}, Page: {page_num} (Similarity: {similarity:.3f})"
            )
        
        return "\n".join(context_parts)
    
    async def index_document_images(self, document_id: str, image_paths: List[str]) -> bool:
        """
        Index document images for future retrieval.
        
        Args:
            document_id: Unique identifier for the document
            image_paths: List of paths to document page images
            
        Returns:
            bool: Success status
        """
        if not self._initialized:
            await self.initialize()
        
        if not colpali_service.is_available():
            logger.warning("ColPali service not available for indexing")
            return False
        
        return await colpali_service.embed_document_images(document_id, image_paths)
    
    async def delete_document_index(self, document_id: str) -> bool:
        """
        Delete document index from ColPali storage.
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            bool: Success status
        """
        if not self._initialized:
            await self.initialize()
        
        if not colpali_service.is_available():
            logger.warning("ColPali service not available for deletion")
            return False
        
        return await colpali_service.delete_document_embeddings(document_id)
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get information about the ColPali agent."""
        return {
            "name": self.name,
            "model": self.model_name,
            "type": "visual_retrieval",
            "capabilities": [
                "Visual document analysis",
                "Image-based search",
                "Multimodal responses",
                "Document understanding",
                "Table and chart analysis"
            ],
            "requirements": [
                "ColPali engine",
                "Milvus vector database",
                "Google Gemini API",
                "Document images"
            ],
            "initialized": self._initialized,
            "services_available": {
                "colpali": colpali_service.is_available(),
                "gemini": gemini_service.is_available()
            }
        }


# Global agent instance
colpali_agent = ColPaliAgent()

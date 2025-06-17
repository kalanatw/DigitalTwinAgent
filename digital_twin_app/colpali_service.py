"""
ColPali Image Embedding and Retrieval Service

This module provides ColPali-based image embedding generation and retrieval
for document images, with SQLite database integration.

Based on insights from the ColPali cookbooks repository:
https://github.com/tonywu71/colpali-cookbooks
"""
import logging
import os
import asyncio
import sqlite3
import pickle
import base64
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from PIL import Image
import torch
import numpy as np
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

try:
    from colpali_engine.models import ColQwen2, ColQwen2Processor
    from colpali_engine.utils.torch_utils import get_torch_device
    COLPALI_AVAILABLE = True
except ImportError as e:
    logger.warning(f"ColPali dependencies not available: {e}")
    COLPALI_AVAILABLE = False


class ColPaliService:
    """
    Service class for ColPali model integration with SQLite database.
    Handles document image embedding and retrieval using ColQwen2.
    
    This implementation follows best practices from the ColPali cookbooks,
    including proper image scaling and multi-vector similarity scoring.
    """
    
    def __init__(self):
        self.model = None
        self.processor = None
        # Use the latest stable ColQwen2 model
        self.model_name = "vidore/colqwen2-v1.0"
        self.db_path = os.path.join(settings.BASE_DIR, 'colpali_embeddings.db')
        self.device = get_torch_device("auto") if COLPALI_AVAILABLE else "cpu"
        self._initialized = False
        
    def _get_device(self):
        """Determine the best available device using ColPali utilities."""
        if COLPALI_AVAILABLE:
            return get_torch_device("auto")
        if torch.cuda.is_available():
            return "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"  # Apple Silicon
        else:
            return "cpu"
    
    async def initialize(self):
        """Initialize ColPali model and SQLite database."""
        if self._initialized or not COLPALI_AVAILABLE:
            return
            
        try:
            logger.info("Initializing ColPali service...")
            
            # Initialize ColPali model
            await self._init_colpali_model()
            
            # Initialize SQLite database
            await self._init_database()
            
            self._initialized = True
            logger.info("ColPali service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ColPali service: {e}")
            raise
    
    async def _init_colpali_model(self):
        """Initialize the ColQwen2 model and processor."""
        logger.info(f"Loading ColPali model: {self.model_name}")
        
        self.model = ColQwen2.from_pretrained(
            self.model_name,
            torch_dtype=torch.bfloat16,
            device_map=self.device,
        )
        
        self.processor = ColQwen2Processor.from_pretrained(self.model_name)
        logger.info(f"ColPali model loaded on device: {self.device}")
    
    def scale_image(self, image: Image.Image, new_height: int = 512) -> Image.Image:
        """
        Scale an image to a new height while maintaining aspect ratio.
        
        Following ColPali cookbook recommendations, scaling to 512px height
        provides a good balance between quality and performance for document tasks.
        
        Args:
            image: PIL Image to scale
            new_height: Target height in pixels (default: 512)
            
        Returns:
            PIL Image scaled to new dimensions
        """
        width, height = image.size
        if height == new_height:
            return image
            
        aspect_ratio = width / height
        new_width = int(new_height * aspect_ratio)
        
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    
    async def _init_database(self):
        """Initialize SQLite database for storing embeddings."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Create embeddings table
            c.execute('''
                CREATE TABLE IF NOT EXISTS embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    document_id TEXT,
                    page_number INTEGER,
                    image_base64 TEXT,
                    image_hash TEXT UNIQUE,
                    embedding BLOB,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index for faster searches
            c.execute('CREATE INDEX IF NOT EXISTS idx_document_id ON embeddings(document_id)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_image_hash ON embeddings(image_hash)')
            
            conn.commit()
            conn.close()
            
            logger.info(f"SQLite database initialized at: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize SQLite database: {e}")
            raise
    
    def _get_db_connection(self):
        """Get SQLite database connection."""
        return sqlite3.connect(self.db_path)
    
    async def embed_document_images(self, document_id: str, image_paths: List[str]) -> bool:
        """
        Generate embeddings for document images and store in SQLite.
        
        Args:
            document_id: Unique identifier for the document
            image_paths: List of paths to document page images
            
        Returns:
            bool: Success status
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info(f"Embedding {len(image_paths)} images for document {document_id}")
            
            # Load and process images
            processed_images = []
            for i, image_path in enumerate(image_paths):
                try:
                    if os.path.exists(image_path):
                        image = Image.open(image_path).convert('RGB')
                        
                        # Convert image to base64
                        import io
                        buffered = io.BytesIO()
                        image.save(buffered, format="PNG")
                        img_base64 = base64.b64encode(buffered.getvalue()).decode()
                        
                        # Generate image hash
                        image_hash = hashlib.sha256(buffered.getvalue()).hexdigest()
                        
                        processed_images.append({
                            'image': image,
                            'base64': img_base64,
                            'hash': image_hash,
                            'page_number': i,
                            'path': image_path
                        })
                    else:
                        logger.warning(f"Image not found: {image_path}")
                except Exception as e:
                    logger.error(f"Failed to load image {image_path}: {e}")
            
            if not processed_images:
                logger.warning(f"No valid images found for document {document_id}")
                return False
            
            # Process images through ColPali
            images = [item['image'] for item in processed_images]
            batch_images = self.processor.process_images(images).to(self.model.device)
            
            with torch.no_grad():
                embeddings = self.model(**batch_images)
            
            # Store embeddings in database
            conn = self._get_db_connection()
            c = conn.cursor()
            
            for i, img_data in enumerate(processed_images):
                try:
                    # Check if image already exists
                    c.execute('SELECT id FROM embeddings WHERE image_hash = ?', (img_data['hash'],))
                    if c.fetchone():
                        logger.info(f"Image already indexed: {img_data['hash']}")
                        continue
                    
                    # Get embedding for this image
                    embedding = embeddings[i].cpu().to(torch.float32).numpy()
                    embedding_bytes = pickle.dumps(embedding)
                    
                    # Insert into database
                    c.execute('''
                        INSERT INTO embeddings 
                        (document_id, page_number, image_base64, image_hash, embedding, metadata) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        document_id,
                        img_data['page_number'],
                        img_data['base64'],
                        img_data['hash'],
                        embedding_bytes,
                        f'{{"model": "{self.model_name}", "device": "{self.device}"}}'
                    ))
                    
                except Exception as e:
                    logger.error(f"Failed to store embedding for image {i}: {e}")
            
            conn.commit()
            conn.close()
            
            logger.info(f"Successfully embedded {len(processed_images)} images for document {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to embed document images: {e}")
            return False
    
    async def search_similar_images(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar images based on text query.
        
        Args:
            query: Text query to search for
            top_k: Number of top results to return
            
        Returns:
            List of similar image results with metadata
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            logger.info(f"Searching for images similar to query: {query}")
            
            # Process query through ColPali
            with torch.no_grad():
                batch_query = self.processor.process_queries([query]).to(self.model.device)
                query_embedding = self.model(**batch_query)
            
            query_embedding_cpu = query_embedding.cpu().to(torch.float32).numpy()[0]
            
            # Retrieve all embeddings from database
            conn = self._get_db_connection()
            c = conn.cursor()
            c.execute('''
                SELECT document_id, page_number, image_base64, image_hash, embedding, metadata 
                FROM embeddings
            ''')
            rows = c.fetchall()
            conn.close()
            
            if not rows:
                logger.warning("No images found in the index")
                return []
            
            # Set fixed sequence length (matching the reference implementation)
            fixed_seq_len = 620
            
            # Process stored embeddings and compute similarities
            similarities = []
            for row in rows:
                document_id, page_number, image_base64, image_hash, embedding_bytes, metadata = row
                
                try:
                    # Load embedding
                    embedding = pickle.loads(embedding_bytes)
                    seq_len, embedding_dim = embedding.shape
                    
                    # Adjust to fixed sequence length
                    if seq_len < fixed_seq_len:
                        padding = np.zeros((fixed_seq_len - seq_len, embedding_dim), dtype=embedding.dtype)
                        embedding_fixed = np.concatenate([embedding, padding], axis=0)
                    elif seq_len > fixed_seq_len:
                        embedding_fixed = embedding[:fixed_seq_len, :]
                    else:
                        embedding_fixed = embedding
                    
                    # Adjust query embedding
                    seq_len_q, embedding_dim_q = query_embedding_cpu.shape
                    if seq_len_q < fixed_seq_len:
                        padding_q = np.zeros((fixed_seq_len - seq_len_q, embedding_dim_q), dtype=query_embedding_cpu.dtype)
                        query_embedding_fixed = np.concatenate([query_embedding_cpu, padding_q], axis=0)
                    elif seq_len_q > fixed_seq_len:
                        query_embedding_fixed = query_embedding_cpu[:fixed_seq_len, :]
                    else:
                        query_embedding_fixed = query_embedding_cpu
                    
                    # Convert to tensors and compute similarity
                    query_tensor = torch.from_numpy(query_embedding_fixed).to(self.model.device).unsqueeze(0)
                    image_tensor = torch.from_numpy(embedding_fixed).to(self.model.device).unsqueeze(0)
                    
                    with torch.no_grad():
                        score = self.processor.score_multi_vector(query_tensor, image_tensor)
                    
                    similarity_score = float(score.cpu().numpy())
                    
                    similarities.append({
                        "document_id": document_id,
                        "page_number": page_number,
                        "image_base64": image_base64,
                        "image_hash": image_hash,
                        "similarity_score": similarity_score,
                        "metadata": metadata
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing embedding for {image_hash}: {e}")
            
            # Sort by similarity score
            similarities.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            # Return top_k results
            top_results = similarities[:top_k]
            
            logger.info(f"Found {len(top_results)} similar images")
            return top_results
            
        except Exception as e:
            logger.error(f"Failed to search similar images: {e}")
            return []
    
    async def delete_document_embeddings(self, document_id: str) -> bool:
        """
        Delete all embeddings for a specific document.
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            bool: Success status
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            conn = self._get_db_connection()
            c = conn.cursor()
            
            c.execute('DELETE FROM embeddings WHERE document_id = ?', (document_id,))
            deleted_count = c.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"Deleted {deleted_count} embeddings for document: {document_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete document embeddings: {e}")
            return False
    
    def clear_cache(self):
        """Clear GPU memory cache for different platforms."""
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception as e:
            logger.warning(f"Could not clear cache: {str(e)}")
    
    def is_available(self) -> bool:
        """Check if ColPali service is available."""
        return COLPALI_AVAILABLE and self._initialized
    
    def scale_image(self, image: Image.Image, new_height: int = 512) -> Image.Image:
        """
        Scale an image to a new height while maintaining aspect ratio.
        
        Following ColPali cookbook recommendations, scaling to 512px height
        provides a good balance between quality and performance for document tasks.
        
        Args:
            image: PIL Image to scale
            new_height: Target height in pixels (default: 512)
            
        Returns:
            PIL Image scaled to new dimensions
        """
        width, height = image.size
        if height == new_height:
            return image
            
        aspect_ratio = width / height
        new_width = int(new_height * aspect_ratio)
        
        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


# Global service instance
colpali_service = ColPaliService()

"""
Document processing utilities for Digital Twin Application
"""
import os
import logging
import PyPDF2
import docx
import openai
import numpy as np
from typing import List, Dict, Any, Optional
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone
from asgiref.sync import sync_to_async
from sklearn.metrics.pairwise import cosine_similarity

from .models import Document, DocumentChunk, DocumentEmbedding

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Class to handle document processing and text extraction."""
    
    def __init__(self):
        self.chunk_size = 1000  # characters per chunk
        self.chunk_overlap = 200  # overlap between chunks
    
    def extract_text_from_pdf(self, file_path: str) -> tuple[str, int]:
        """Extract text from PDF file."""
        try:
            text = ""
            page_count = 0
            
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                page_count = len(pdf_reader.pages)
                
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            
            return text, page_count
        
        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            raise
    
    def extract_text_from_docx(self, file_path: str) -> tuple[str, int]:
        """Extract text from DOCX file."""
        try:
            doc = docx.Document(file_path)
            text = ""
            
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            
            # Estimate page count (assuming ~500 words per page)
            word_count = len(text.split())
            page_count = max(1, word_count // 500)
            
            return text, page_count
        
        except Exception as e:
            logger.error(f"Error extracting text from DOCX {file_path}: {e}")
            raise
    
    def extract_text_from_txt(self, file_path: str) -> tuple[str, int]:
        """Extract text from plain text file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
            
            # Estimate page count
            word_count = len(text.split())
            page_count = max(1, word_count // 500)
            
            return text, page_count
        
        except Exception as e:
            logger.error(f"Error extracting text from TXT {file_path}: {e}")
            raise
    
    def determine_file_type(self, filename: str) -> str:
        """Determine file type from filename."""
        extension = os.path.splitext(filename)[1].lower()
        
        if extension == '.pdf':
            return 'pdf'
        elif extension in ['.docx', '.doc']:
            return 'docx'
        elif extension in ['.txt', '.md']:
            return 'txt'
        else:
            return 'other'
    
    def extract_text(self, file_path: str, file_type: str) -> tuple[str, int]:
        """Extract text from file based on type."""
        if file_type == 'pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_type == 'docx':
            return self.extract_text_from_docx(file_path)
        elif file_type == 'txt':
            return self.extract_text_from_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def chunk_text(self, text: str) -> List[str]:
        """Split text into chunks for embedding."""
        if len(text) <= self.chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings near the chunk boundary
                for i in range(end, max(start + self.chunk_size - 100, start), -1):
                    if text[i] in '.!?':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - self.chunk_overlap
            
            # Prevent infinite loop
            if start >= end:
                start = end
        
        return chunks
    
    def process_document(self, document: Document) -> bool:
        """Process a document: extract text, create chunks."""
        try:
            logger.info(f"Processing document: {document.title}")
            
            # Update status
            document.status = 'processing'
            document.save()
            
            # Extract text
            file_path = document.file.path
            text, page_count = self.extract_text(file_path, document.file_type)
            
            # Update document metadata
            document.page_count = page_count
            document.word_count = len(text.split())
            document.save()
            
            # Create chunks
            chunks = self.chunk_text(text)
            
            # Save chunks to database
            for i, chunk_text in enumerate(chunks):
                DocumentChunk.objects.create(
                    document=document,
                    content=chunk_text,
                    chunk_index=i,
                    word_count=len(chunk_text.split())
                )
            
            logger.info(f"Created {len(chunks)} chunks for document {document.title}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing document {document.title}: {e}")
            document.status = 'failed'
            document.processing_error = str(e)
            document.save()
            return False


class EmbeddingGenerator:
    """Class to handle embedding generation using OpenAI."""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-small"
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI."""
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def generate_embeddings_for_document(self, document: Document) -> bool:
        """Generate embeddings for all chunks of a document."""
        try:
            logger.info(f"Generating embeddings for document: {document.title}")
            
            chunks = DocumentChunk.objects.filter(document=document)
            
            for chunk in chunks:
                # Check if embedding already exists
                if hasattr(chunk, 'embedding'):
                    continue
                
                # Generate embedding
                embedding = self.generate_embedding(chunk.content)
                
                # Save embedding
                DocumentEmbedding.objects.create(
                    chunk=chunk,
                    embedding=embedding,
                    embedding_model=self.model
                )
            
            # Update document status
            document.status = 'completed'
            document.processed_at = timezone.now()
            document.save()
            
            logger.info(f"Generated embeddings for {chunks.count()} chunks")
            return True
            
        except Exception as e:
            logger.error(f"Error generating embeddings for document {document.title}: {e}")
            document.status = 'failed'
            document.processing_error = str(e)
            document.save()
            return False


class SemanticSearch:
    """Class to handle semantic search using embeddings."""
    
    def __init__(self):
        self.embedding_generator = EmbeddingGenerator()
    
    async def search_documents(self, query: str, twin_version_id: str, 
                        top_k: int = 5) -> List[Dict[str, Any]]:
        """Search documents using semantic similarity."""
        try:
            # Generate query embedding
            query_embedding = self.embedding_generator.generate_embedding(query)
            
            # Get all embeddings for the twin version using async database access
            embeddings = await sync_to_async(list)(
                DocumentEmbedding.objects.filter(
                    chunk__document__twin_version_id=twin_version_id,
                    chunk__document__is_enabled=True,
                    chunk__document__status='completed'
                ).select_related('chunk', 'chunk__document')
            )
            
            if not embeddings:
                return []
            
            # Calculate similarities
            similarities = []
            for emb in embeddings:
                doc_embedding = np.array(emb.embedding)
                query_emb = np.array(query_embedding)
                
                # Calculate cosine similarity
                similarity = cosine_similarity([query_emb], [doc_embedding])[0][0]
                
                similarities.append({
                    'chunk': emb.chunk,
                    'document': emb.chunk.document,
                    'similarity': similarity,
                    'content': emb.chunk.content,
                    'title': emb.chunk.document.title
                })
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    async def get_context_for_chat(self, query: str, twin_version_id: str, 
                                 max_context_length: int = 4000) -> str:
        """Get relevant document context for chat."""
        search_results = await self.search_documents(query, twin_version_id, top_k=10)
        
        if not search_results:
            return ""
        
        context_parts = []
        total_length = 0
        
        for result in search_results:
            content = result['content']
            document_title = result['document'].title
            
            # Add document reference
            formatted_content = f"[From: {document_title}]\n{content}\n\n"
            
            # If this is the first result and it's larger than max_context_length,
            # include it anyway (truncated)
            if len(context_parts) == 0 and len(formatted_content) > max_context_length:
                truncated_content = formatted_content[:max_context_length-3] + "..."
                context_parts.append(truncated_content)
                break
            elif total_length + len(formatted_content) <= max_context_length:
                context_parts.append(formatted_content)
                total_length += len(formatted_content)
            else:
                break
        
        return "".join(context_parts)

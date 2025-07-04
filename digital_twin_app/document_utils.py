"""
Document processing utilities for Digital Twin Application.

This module provides classes and functions for processing various document types
including PDF, DOCX, TXT, and CSV files, generating embeddings, and performing
semantic search with user-centric access control.
"""

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import docx
import numpy as np
import openai
import pandas as pd
import PyPDF2
from asgiref.sync import sync_to_async
from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from sklearn.metrics.pairwise import cosine_similarity

from .models import (
    CSVColumn,
    CSVDataset,
    CSVDocument,
    Document,
    DocumentChunk,
    DocumentEmbedding,
)

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Handles document processing and text extraction for various file types.

    Supports PDF, DOCX, TXT, and CSV files with intelligent text extraction
    and chunking for embedding generation.
    """

    def __init__(self) -> None:
        """Initialize the document processor with default settings."""
        self.chunk_size: int = 1000  # characters per chunk
        self.chunk_overlap: int = 200  # overlap between chunks
        self.csv_processor = CSVProcessor()

    def extract_text_from_pdf(self, file_path: str) -> Tuple[str, int]:
        """
        Extract text from PDF file.

        Args:
            file_path: Path to the PDF file

        Returns:
            Tuple of (extracted_text, page_count)

        Raises:
            Exception: If PDF reading fails
        """
        try:
            text = ""
            page_count = 0

            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                page_count = len(pdf_reader.pages)

                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"

            return text, page_count

        except Exception as e:
            logger.error(f"Error extracting text from PDF {file_path}: {e}")
            raise

    def extract_text_from_docx(self, file_path: str) -> Tuple[str, int]:
        """
        Extract text from DOCX file.

        Args:
            file_path: Path to the DOCX file

        Returns:
            Tuple of (extracted_text, estimated_page_count)

        Raises:
            Exception: If DOCX reading fails
        """
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

    def extract_text_from_txt(self, file_path: str) -> Tuple[str, int]:
        """
        Extract text from plain text file.

        Args:
            file_path: Path to the text file

        Returns:
            Tuple of (extracted_text, estimated_page_count)

        Raises:
            Exception: If text file reading fails
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                text = file.read()

            # Estimate page count
            word_count = len(text.split())
            page_count = max(1, word_count // 500)

            return text, page_count

        except Exception as e:
            logger.error(f"Error extracting text from TXT {file_path}: {e}")
            raise

    def extract_text_from_csv(self, file_path: str) -> Tuple[str, int]:
        """
        Extract text from CSV file and convert it to readable text format.

        Args:
            file_path: Path to the CSV file

        Returns:
            Tuple of (extracted_text, estimated_page_count)

        Raises:
            ValueError: If CSV file cannot be loaded
            Exception: If CSV processing fails
        """
        try:
            # Use the CSV processor to load the file
            df = self.csv_processor._load_csv_intelligently(file_path)
            if df is None:
                raise ValueError("Failed to load CSV file")

            # Convert to string representation
            text = f"CSV File with {len(df)} rows and {len(df.columns)} " f"columns\n\n"

            # Add column names
            text += "Columns: " + ", ".join(df.columns.tolist()) + "\n\n"

            # Add sample data (first 10 rows)
            text += "Sample Data:\n"
            sample_rows = min(10, len(df))
            for i in range(sample_rows):
                row_text = " | ".join(
                    [f"{col}: {df.iloc[i][col]}" for col in df.columns]
                )
                text += f"Row {i+1}: {row_text}\n"

            # Add basic statistics for numerical columns
            num_cols = df.select_dtypes(include=["number"]).columns
            if len(num_cols) > 0:
                text += "\nNumerical Column Statistics:\n"
                for col in num_cols:
                    stats = df[col].describe()
                    text += f"{col}:\n"
                    text += f"  Mean: {stats['mean']:.2f}\n"
                    text += f"  Min: {stats['min']:.2f}\n"
                    text += f"  Max: {stats['max']:.2f}\n"
                    text += f"  StdDev: {stats['std']:.2f}\n"

            # Estimate page count based on text length
            word_count = len(text.split())
            page_count = max(1, word_count // 500)

            return text, page_count

        except Exception as e:
            logger.error(f"Error extracting text from CSV {file_path}: {e}")
            raise

    def determine_file_type(self, filename: str) -> str:
        """
        Determine file type from filename extension.

        Args:
            filename: Name of the file

        Returns:
            File type string ('pdf', 'docx', 'txt', 'csv', or 'other')
        """
        extension = os.path.splitext(filename)[1].lower()

        if extension == ".pdf":
            return "pdf"
        elif extension in [".docx", ".doc"]:
            return "docx"
        elif extension in [".txt", ".md"]:
            return "txt"
        elif extension == ".csv":
            return "csv"
        else:
            return "other"

    def extract_text(self, file_path: str, file_type: str) -> tuple[str, int]:
        """Extract text from file based on type."""
        if file_type == "pdf":
            return self.extract_text_from_pdf(file_path)
        elif file_type == "docx":
            return self.extract_text_from_docx(file_path)
        elif file_type == "txt":
            return self.extract_text_from_txt(file_path)
        elif file_type == "csv":
            return self.extract_text_from_csv(file_path)
        elif file_type == "md":
            # Treat markdown files as text files
            return self.extract_text_from_txt(file_path)
        elif file_type == "other":
            # Try to detect file type from extension or treat as text
            if file_path.lower().endswith(".txt"):
                return self.extract_text_from_txt(file_path)
            elif file_path.lower().endswith(".md"):
                return self.extract_text_from_txt(file_path)
            else:
                # Attempt to read as text file anyway
                try:
                    return self.extract_text_from_txt(file_path)
                except Exception as e:
                    logger.warning(f"Could not process file {file_path} as text: {e}")
                    raise ValueError(
                        f"Unsupported file type: {file_type} for file {file_path}"
                    )
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
                    if text[i] in ".!?":
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
            document.status = "processing"
            document.save()

            # Handle CSV files with special processing
            if document.file_type == "csv":
                return self.process_csv_file(document)

            # Extract text for other file types
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
                    word_count=len(chunk_text.split()),
                )

            logger.info(f"Created {len(chunks)} chunks for document {document.title}")
            return True

        except Exception as e:
            logger.error(f"Error processing document {document.title}: {e}")
            document.status = "failed"
            document.processing_error = str(e)
            document.save()
            return False

    def process_csv_file(self, document):
        """Process a CSV file, extract schema, and store in database"""
        try:
            logger.info(f"Processing CSV file: {document.title}")

            # Get the file path
            file_path = document.file.path

            # Process the CSV file using CSVProcessor
            result = self.csv_processor.process_csv_file(
                file_path=file_path,
                filename=document.title,
                twin_version_id=(
                    str(document.twin_version.id) if document.twin_version else None
                ),
                user_id=str(document.uploaded_by.id) if document.uploaded_by else None,
            )

            if not result.get("success", False):
                document.status = "failed"
                document.processing_error = result.get(
                    "error", "Unknown error processing CSV file"
                )
                document.save()
                logger.error(
                    f"Error processing CSV file {document.title}: "
                    f"{document.processing_error}"
                )
                return False

            # Extract text for embedding
            text, page_count = self.extract_text_from_csv(file_path)

            # Update document metadata
            document.page_count = page_count
            document.word_count = len(text.split())
            document.status = "completed"
            document.processed_at = timezone.now()
            document.save()

            # Create chunks for embedding
            chunks = self.chunk_text(text)

            # Store chunks
            stored_chunks = []
            for i, chunk_text in enumerate(chunks):
                chunk = DocumentChunk.objects.create(
                    document=document, chunk_index=i, content=chunk_text
                )
                stored_chunks.append(chunk)

            logger.info(
                f"Created {len(stored_chunks)} chunks for document {document.title}"
            )

            return True

        except Exception as e:
            logger.error(f"Error processing CSV file {document.title}: {e}")
            document.status = "failed"
            document.processing_error = str(e)
            document.save()
            return False


class EmbeddingGenerator:
    """
    Handles embedding generation using OpenAI's text embedding models.

    Provides methods for generating embeddings for individual text chunks
    and processing entire documents.
    """

    def __init__(self) -> None:
        """Initialize the embedding generator with OpenAI client."""
        self.client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "text-embedding-3-small"

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using OpenAI.

        Args:
            text: Text to generate embedding for

        Returns:
            List of float values representing the embedding

        Raises:
            Exception: If embedding generation fails
        """
        try:
            response = self.client.embeddings.create(model=self.model, input=text)
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
                if hasattr(chunk, "embedding"):
                    continue

                # Generate embedding
                embedding = self.generate_embedding(chunk.content)

                # Save embedding
                DocumentEmbedding.objects.create(
                    chunk=chunk,
                    embedding=embedding,
                    embedding_model=self.model,
                    embedding_type="document",
                )

            # Update document status
            document.status = "completed"
            document.processed_at = timezone.now()
            document.save()

            logger.info(f"Generated embeddings for {chunks.count()} chunks")
            return True

        except Exception as e:
            logger.error(
                f"Error generating embeddings for document {document.title}: {e}"
            )
            document.status = "failed"
            document.processing_error = str(e)
            document.save()
            return False


class SemanticSearch:
    """
    Handles semantic search using embeddings with user-centric access control.

    Provides methods for searching documents and retrieving context for chat
    with proper security and permission handling.
    """

    def __init__(self) -> None:
        """Initialize the semantic search with an embedding generator."""
        self.embedding_generator = EmbeddingGenerator()

    async def search_documents(
        self,
        query: str,
        twin_version_id: Optional[str] = None,
        user_id: Optional[int] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search documents using semantic similarity with user-centric access control.

        Args:
            query: Search query text
            twin_version_id: Optional twin version ID to limit search scope
            user_id: User ID for access control (required for user-centric filtering)
            top_k: Number of top results to return

        Returns:
            List of dictionaries containing search results with similarity scores
        """
        try:
            # Generate query embedding
            query_embedding = self.embedding_generator.generate_embedding(query)

            # Build base query with user access control
            base_query = DocumentEmbedding.objects.filter(
                chunk__document__is_enabled=True, chunk__document__status="completed"
            )

            # Add user-based filtering - user can access:
            # 1. Their own documents
            # 2. Documents in shared twin versions
            # 3. Documents in twin versions shared with them
            if user_id:
                user_filter = Q(
                    chunk__document__uploaded_by=user_id
                )  # Own documents

                # Add shared twin versions
                user_filter |= Q(
                    chunk__document__twin_version__is_shared=True
                )  # Public twin versions
                user_filter |= Q(
                    chunk__document__twin_version__shares__shared_with_id=user_id
                )  # Explicitly shared

                base_query = base_query.filter(user_filter)

            # Add twin version filtering if specified
            if twin_version_id:
                base_query = base_query.filter(
                    chunk__document__twin_version_id=twin_version_id
                )

            # Get embeddings with proper relations
            embeddings = await sync_to_async(list)(
                base_query.select_related(
                    "chunk",
                    "chunk__document",
                    "chunk__document__twin_version",
                    "chunk__document__uploaded_by",
                )
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

                similarities.append(
                    {
                        "chunk": emb.chunk,
                        "document": emb.chunk.document,
                        "twin_version": emb.chunk.document.twin_version,
                        "similarity": similarity,
                        "content": emb.chunk.content,
                        "title": emb.chunk.document.title,
                        "uploaded_by": (
                            emb.chunk.document.uploaded_by.username
                            if emb.chunk.document.uploaded_by
                            else "Unknown"
                        ),
                    }
                )

            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x["similarity"], reverse=True)

            return similarities[:top_k]

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []

    async def get_context_for_chat(
        self,
        query: str,
        twin_version_id: str = None,
        user_id: int = None,
        max_context_length: int = 4000,
    ) -> str:
        """
        Get relevant document context for chat with user-centric access control.

        Args:
            query: Search query text
            twin_version_id: Optional twin version ID to limit search scope
            user_id: User ID for access control
            max_context_length: Maximum length of context to return
        """
        search_results = await self.search_documents(
            query, twin_version_id=twin_version_id, user_id=user_id, top_k=10
        )

        if not search_results:
            return ""

        context_parts = []
        total_length = 0

        for result in search_results:
            content = result["content"]
            document_title = result["document"].title
            twin_version_name = (
                result["twin_version"].name if result["twin_version"] else "Unknown"
            )

            # Add document and twin version reference
            formatted_content = f"[From: {document_title} (Twin Version: {twin_version_name})]\n{content}\n\n"

            # If this is the first result and it's larger than max_context_length,
            # include it anyway (truncated)
            if len(context_parts) == 0 and len(formatted_content) > max_context_length:
                truncated_content = formatted_content[: max_context_length - 3] + "..."
                context_parts.append(truncated_content)
                break
            elif total_length + len(formatted_content) <= max_context_length:
                context_parts.append(formatted_content)
                total_length += len(formatted_content)
            else:
                break

        return "".join(context_parts)


class CSVProcessor:
    """
    Handles CSV file processing and intelligent analysis.

    Provides comprehensive CSV processing including schema inference,
    time series detection, and database storage with statistics.
    """

    def __init__(self) -> None:
        """Initialize the CSV processor with default settings."""
        self.sample_size: int = 1000  # Maximum rows to sample for schema inference
        self.common_date_patterns: List[str] = [
            r"\d{4}-\d{1,2}-\d{1,2}",  # YYYY-MM-DD
            r"\d{1,2}/\d{1,2}/\d{4}",  # MM/DD/YYYY or DD/MM/YYYY
            r"\d{1,2}-\d{1,2}-\d{4}",  # MM-DD-YYYY or DD-MM-YYYY
            r"\d{1,2}\.\d{1,2}\.\d{4}",  # DD.MM.YYYY or MM.DD.YYYY
            r"\d{1,2}/\d{1,2}/\d{2}",  # MM/DD/YY or DD/MM/YY
        ]

    def process_csv_file(
        self,
        file_path: str,
        filename: str,
        twin_version_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Process a CSV file and extract all relevant information.

        Args:
            file_path: Path to the CSV file
            filename: Original filename
            twin_version_id: Optional ID of twin version
            user_id: ID of the user who uploaded the file

        Returns:
            Dictionary with processing results including success status,
            statistics, schema, and time series information
        """
        logger.info(f"Processing CSV file: {filename}")

        # Load the CSV file intelligently
        df = self._load_csv_intelligently(file_path)
        if df is None:
            return {"success": False, "error": "Failed to load CSV file"}

        # Get basic file stats
        stats = self._get_basic_stats(df)

        # Infer schema
        schema = self._infer_schema(df)

        # Detect time series
        time_series = self._detect_time_series(df, schema)

        # Create database records
        csv_doc = self._save_to_database(
            df, filename, schema, time_series, twin_version_id, user_id, file_path
        )

        return {
            "success": True,
            "document_id": str(csv_doc.id),
            "stats": stats,
            "schema": schema,
            "time_series": time_series,
        }

    def _load_csv_intelligently(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Intelligently load a CSV file, handling various formats and encodings.
        """
        # Try to detect delimiter, encoding, etc.
        try:
            # First try with pandas' auto-detection
            df = pd.read_csv(file_path)
            return df
        except Exception as e:
            logger.warning(f"Initial CSV load failed: {str(e)}")
            # If that fails, try with different settings
            encodings = ["utf-8", "latin1", "iso-8859-1", "cp1252"]
            separators = [",", ";", "\t", "|"]

            for encoding in encodings:
                for sep in separators:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding, sep=sep)
                        # If we get here, it worked
                        logger.info(
                            f"Successfully loaded CSV with encoding {encoding} and separator {sep}"
                        )
                        return df
                    except Exception:
                        continue

            # If all options fail
            logger.error(f"Failed to load CSV file {file_path}")
            return None

    def _get_basic_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Get basic statistics about the CSV file"""
        return {
            "rows": len(df),
            "columns": len(df.columns),
            "memory_usage": int(df.memory_usage(deep=True).sum()),
            "column_names": df.columns.tolist(),
        }

    def _infer_schema(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Infer schema from dataframe.

        Args:
            df: Pandas dataframe

        Returns:
            Dictionary with schema information
        """
        schema = {
            "summary": {"row_count": len(df), "column_count": len(df.columns)},
            "columns": {},
        }

        # Analyze each column
        for column in df.columns:
            col_info = self._analyze_column(df, column)
            schema["columns"][column] = col_info

        # Try to identify primary keys
        schema["primary_key"] = self._identify_primary_key(df, schema["columns"])
        if schema["primary_key"]:
            # Add primary_key tag to the identified column
            schema["columns"][schema["primary_key"]]["tags"].append("primary_key")

        # Analyze inter-column relationships
        schema["relationships"] = self._analyze_relationships(df, schema["columns"])

        return schema

    def _analyze_column(self, df: pd.DataFrame, column: str) -> Dict[str, Any]:
        """
        Analyze a single column to determine its properties.

        Args:
            df: Pandas dataframe
            column: Column name

        Returns:
            Dictionary with column information
        """
        col_data = df[column]
        unique_count = col_data.nunique()
        null_count = col_data.isna().sum()

        # Initialize column info
        col_info = {
            "name": column,
            "description": self._generate_column_description(column, col_data),
            "tags": [],
            "statistics": {
                "unique_count": int(unique_count),
                "null_count": int(null_count),
                "null_percentage": float((null_count / len(df)) * 100),
                "unique_percentage": float((unique_count / len(df)) * 100),
            },
        }

        # Detect data type
        data_type, type_tags = self._detect_data_type(col_data, column)
        col_info["data_type"] = data_type
        col_info["tags"].extend(type_tags)

        # Add statistics based on data type
        if data_type in ["integer", "float", "numeric"]:
            numeric_data = pd.to_numeric(col_data, errors="coerce")
            col_info["statistics"].update(
                {
                    "min": (
                        float(numeric_data.min())
                        if not pd.isna(numeric_data.min())
                        else None
                    ),
                    "max": (
                        float(numeric_data.max())
                        if not pd.isna(numeric_data.max())
                        else None
                    ),
                    "mean": (
                        float(numeric_data.mean())
                        if not pd.isna(numeric_data.mean())
                        else None
                    ),
                    "median": (
                        float(numeric_data.median())
                        if not pd.isna(numeric_data.median())
                        else None
                    ),
                    "std": (
                        float(numeric_data.std())
                        if not pd.isna(numeric_data.std())
                        else None
                    ),
                }
            )
            col_info["tags"].append("numerical")

        elif data_type == "datetime":
            try:
                datetime_data = pd.to_datetime(col_data, errors="coerce")
                col_info["statistics"].update(
                    {
                        "min": (
                            datetime_data.min().isoformat()
                            if not pd.isna(datetime_data.min())
                            else None
                        ),
                        "max": (
                            datetime_data.max().isoformat()
                            if not pd.isna(datetime_data.max())
                            else None
                        ),
                        "range_days": (
                            (datetime_data.max() - datetime_data.min()).days
                            if not pd.isna(datetime_data.min())
                            and not pd.isna(datetime_data.max())
                            else None
                        ),
                    }
                )
                col_info["tags"].append("temporal")
            except Exception:
                pass

        elif data_type in ["string", "category"]:
            if unique_count / len(df) < 0.5:  # If less than 50% unique values
                col_info["statistics"]["frequent_values"] = {
                    str(k): int(v)
                    for k, v in col_data.value_counts().head(10).to_dict().items()
                }
                col_info["tags"].append("categorical")

            if unique_count == len(df) and unique_count > 1:  # If all values are unique
                col_info["tags"].append("unique")

        return col_info

    def _detect_data_type(
        self, series: pd.Series, column_name: str
    ) -> Tuple[str, List[str]]:
        """
        Detect the data type of a column.

        Returns:
            Tuple of (data_type, tags)
        """
        # Handle completely empty columns
        if series.isna().all():
            return "unknown", []

        # First check if it's datetime
        if self._is_datetime(series, column_name):
            return "datetime", ["temporal"]

        # Check if it's numeric
        non_null = series.dropna()
        if len(non_null) == 0:
            return "unknown", []

        try:
            numeric_series = pd.to_numeric(non_null)
            # Check if all values are integers
            if np.all(numeric_series.astype(int) == numeric_series):
                # Is it likely a categorical variable?
                if (
                    numeric_series.nunique() < 15
                    and numeric_series.nunique() / len(numeric_series) < 0.05
                ):
                    return "integer", ["categorical"]
                # Or is it more like an ID?
                elif column_name.lower().endswith("id") or column_name.lower() == "id":
                    return "integer", ["identifier"]
                else:
                    return "integer", []
            else:
                # Check if it's a percentage
                if "percent" in column_name.lower() or "%" in str(non_null.iloc[0]):
                    return "float", ["percentage"]
                # Check if it's money
                elif any(
                    curr in column_name.lower()
                    for curr in ["price", "cost", "amount", "salary"]
                ):
                    return "float", ["monetary"]
                else:
                    return "float", []
        except (ValueError, TypeError):
            pass

        # Check if it's boolean
        if self._is_boolean(non_null):
            return "boolean", ["categorical"]

        # Check if it's categorical
        if non_null.nunique() < 15 and non_null.nunique() / len(non_null) < 0.1:
            return "category", ["categorical"]

        # Default to string
        return "string", []

    def _is_datetime(self, series: pd.Series, column_name: str) -> bool:
        """Check if a series contains datetime values"""
        # Check if column name suggests datetime
        date_patterns = [
            "date",
            "time",
            "dt",
            "day",
            "month",
            "year",
            "created",
            "updated",
        ]
        name_suggests_date = any(
            pattern in column_name.lower() for pattern in date_patterns
        )

        # Try to convert to datetime directly
        try:
            pd.to_datetime(series, errors="raise")
            return True
        except (ValueError, TypeError, pd.errors.OutOfBoundsDatetime):
            # If that fails, check for common date patterns
            if name_suggests_date:
                # Sample non-null values
                sample = series.dropna().astype(str).head(10).tolist()

                # Check if any values match date patterns
                for pattern in self.common_date_patterns:
                    matches = sum(1 for val in sample if re.fullmatch(pattern, val))
                    if matches / len(sample) > 0.5:  # More than 50% match
                        return True

            return False

    def _is_boolean(self, series: pd.Series) -> bool:
        """Check if a series contains boolean-like values"""
        # Convert to lowercase string
        str_series = series.astype(str).str.lower()

        # Check for common boolean values
        true_values = ["true", "yes", "y", "1", "t"]
        false_values = ["false", "no", "n", "0", "f"]

        # Count matches
        all_values = set(str_series.unique())

        # If only 2 unique values and they match boolean patterns
        if len(all_values) <= 2:
            true_matches = sum(1 for val in all_values if val in true_values)
            false_matches = sum(1 for val in all_values if val in false_values)

            return true_matches + false_matches == len(all_values)

        return False

    def _analyze_relationships(
        self, df: pd.DataFrame, columns_info: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze relationships between columns"""
        relationships = []

        # Look for columns that might be foreign keys
        for col_name, col_info in columns_info.items():
            # If column name ends with _id and is integer type
            if (
                col_name.lower().endswith("_id")
                and col_info["data_type"] == "integer"
                and "unique" not in col_info["tags"]
            ):

                # Look for potential primary key references
                for ref_col, ref_info in columns_info.items():
                    if (
                        "unique" in ref_info["tags"]
                        and ref_info["data_type"] == "integer"
                        and col_name != ref_col
                    ):

                        # Check if values in col_name are subset of ref_col
                        try:
                            overlap = set(df[col_name].dropna()) <= set(
                                df[ref_col].dropna()
                            )

                            if overlap:
                                relationships.append(
                                    {
                                        "type": "foreign_key",
                                        "from_column": col_name,
                                        "to_column": ref_col,
                                        "confidence": (
                                            "high"
                                            if "primary_key" in ref_info["tags"]
                                            else "medium"
                                        ),
                                    }
                                )
                        except (ValueError, TypeError, KeyError):
                            pass

        # Look for correlated columns
        numerical_cols = [
            col
            for col, info in columns_info.items()
            if info["data_type"] in ["integer", "float", "numeric"]
        ]

        if len(numerical_cols) >= 2:
            try:
                # Compute correlation matrix
                corr_matrix = df[numerical_cols].corr()

                # Find highly correlated pairs
                for i in range(len(numerical_cols)):
                    for j in range(i + 1, len(numerical_cols)):
                        col1 = numerical_cols[i]
                        col2 = numerical_cols[j]
                        corr = corr_matrix.loc[col1, col2]

                        if abs(corr) > 0.8:  # High correlation
                            relationships.append(
                                {
                                    "type": "correlation",
                                    "columns": [col1, col2],
                                    "correlation": float(corr),
                                    "description": f"Strong {'positive' if corr > 0 else 'negative'} correlation",
                                }
                            )
            except Exception as e:
                logger.warning(f"Error calculating correlations: {str(e)}")

        return relationships

    def _identify_primary_key(
        self, df: pd.DataFrame, columns_info: Dict[str, Any]
    ) -> Optional[str]:
        """Try to identify primary key column"""
        candidates = []

        for col_name, col_info in columns_info.items():
            # Check for exact name match
            if col_name.lower() == "id":
                candidates.append((col_name, 4))  # Highest priority

            # Check for name containing id
            elif "id" in col_name.lower():
                candidates.append((col_name, 3))

            # Check for unique columns
            elif "unique" in col_info["tags"]:
                candidates.append((col_name, 2))

            # Check for integer columns with high cardinality
            elif (
                col_info["data_type"] == "integer"
                and col_info["statistics"]["unique_percentage"] > 90
            ):
                candidates.append((col_name, 1))

        # Sort by priority
        candidates.sort(key=lambda x: x[1], reverse=True)

        return candidates[0][0] if candidates else None

    def _generate_column_description(self, column: str, data: pd.Series) -> str:
        """Generate a human-readable description for the column"""
        description = f"Column '{column}'"

        # Check for patterns in the name
        common_patterns = {
            "id": "identifier",
            "date": "date/time",
            "name": "name/title",
            "email": "email address",
            "phone": "phone number",
            "address": "address",
            "price": "price/cost",
            "qty": "quantity",
            "amount": "amount",
            "percent": "percentage",
            "status": "status",
        }

        for pattern, meaning in common_patterns.items():
            if pattern in column.lower():
                description = f"{meaning.capitalize()} column '{column}'"
                break

        # Add info about uniqueness
        unique_count = data.nunique()
        if unique_count == 1:
            description += " with constant value"
        elif unique_count == len(data) and unique_count > 1:
            description += " with unique values"
        elif unique_count < 10:
            description += f" with {unique_count} distinct values"

        return description

    def _detect_time_series(
        self, df: pd.DataFrame, schema: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect time series data in the dataframe.

        Args:
            df: Pandas dataframe
            schema: Schema information from the schema inference

        Returns:
            List of time series configurations
        """
        time_series_list = []

        # First, find all temporal columns
        temporal_columns = []
        date_column_patterns = [
            "date",
            "time",
            "timestamp",
            "datetime",
            "day",
            "month",
            "year",
        ]

        for col_name, col_info in schema["columns"].items():
            if "temporal" in col_info["tags"]:
                temporal_columns.append(col_name)
            elif any(pattern in col_name.lower() for pattern in date_column_patterns):
                # Try to convert to datetime
                try:
                    pd.to_datetime(df[col_name])
                    temporal_columns.append(col_name)
                except (ValueError, TypeError, pd.errors.OutOfBoundsDatetime):
                    pass

        # If no temporal columns found, try to find numeric columns that could be years
        if not temporal_columns:
            for col_name, col_info in schema["columns"].items():
                if col_info["data_type"] == "integer":
                    sample_values = df[col_name].dropna().head(10).tolist()
                    # Check if values could be years
                    if all(1900 <= x <= 2100 for x in sample_values if not pd.isna(x)):
                        temporal_columns.append(col_name)

        # If still no temporal columns, we can't identify time series
        if not temporal_columns:
            logger.info("No temporal columns found in the dataset")
            return []

        # For each temporal column, look for potential value columns
        for time_col in temporal_columns:
            # Look for numeric columns that could be series data
            numeric_columns = []
            for col_name, col_info in schema["columns"].items():
                if (
                    col_info["data_type"] in ["integer", "float", "numeric"]
                    and col_name != time_col
                    and "identifier" not in col_info["tags"]
                ):
                    numeric_columns.append(col_name)

            # Skip if no numeric columns found
            if not numeric_columns:
                continue

            try:
                # Convert temporal column to datetime
                time_data = pd.to_datetime(df[time_col], errors="coerce")

                # Check if values are sequential (more than 50% of intervals are same)
                sorted_times = time_data.sort_values().dropna()
                if len(sorted_times) <= 1:
                    continue

                intervals = sorted_times.diff().dropna()
                most_common_interval = intervals.value_counts().idxmax()
                interval_consistency = intervals.value_counts().max() / len(intervals)

                # If we have somewhat consistent intervals, this is likely a time series
                is_time_series = interval_consistency > 0.3

                if is_time_series:
                    # For each numeric column, create a time series configuration
                    for value_col in numeric_columns:
                        # Check if there's actual data (not just NaNs)
                        if df[value_col].isna().sum() < len(df):
                            # Try to determine what kind of metric this is
                            description, unit = self._determine_metric_info(value_col)

                            time_series_list.append(
                                {
                                    "name": f"{value_col} over time",
                                    "description": description,
                                    "time_column": time_col,
                                    "value_column": value_col,
                                    "unit": unit,
                                    "interval": str(most_common_interval),
                                    "count": int(len(df[value_col].dropna())),
                                    "sorted": bool(sorted_times.is_monotonic),
                                }
                            )
            except Exception as e:
                logger.warning(
                    f"Error processing time series for column {time_col}: {str(e)}"
                )
                continue

        return time_series_list

    def _determine_metric_info(self, column_name: str) -> Tuple[str, str]:
        """
        Try to determine what kind of metric this column contains.

        Returns:
            Tuple of (description, unit)
        """
        name = column_name.lower()

        # Check for common units in the name
        unit_patterns = {
            "%": "percentage",
            "percent": "percentage",
            "price": "currency",
            "cost": "currency",
            "dollar": "USD",
            "euro": "EUR",
            "pound": "GBP",
            "kg": "kilograms",
            "gram": "grams",
            "meter": "meters",
            "mile": "miles",
            "celsius": "°C",
            "fahrenheit": "°F",
            "degree": "degrees",
            "watt": "watts",
            "amp": "amperes",
            "volt": "volts",
            "hour": "hours",
            "minute": "minutes",
            "second": "seconds",
            "count": "count",
            "quantity": "count",
        }

        unit = ""
        for pattern, unit_name in unit_patterns.items():
            if pattern in name:
                unit = unit_name
                break

        # Generate description
        description = f"Time series data of {column_name}"

        # Add more context based on the name
        context_patterns = {
            "revenue": "Revenue or income figures over time",
            "sale": "Sales figures over time",
            "profit": "Profit measurements over time",
            "temperature": "Temperature measurements over time",
            "speed": "Speed or velocity measurements over time",
            "energy": "Energy consumption or production over time",
            "population": "Population counts over time",
            "growth": "Growth metrics over time",
            "rate": "Rate measurements over time",
            "index": "Index values over time",
            "level": "Level measurements over time",
            "usage": "Usage metrics over time",
        }

        for pattern, desc in context_patterns.items():
            if pattern in name:
                description = desc
                break

        return description, unit

    def _save_to_database(
        self,
        df: pd.DataFrame,
        filename: str,
        schema: Dict[str, Any],
        time_series: List[Dict[str, Any]],
        twin_version_id: str = None,
        user_id: str = None,
        file_path: str = None,
    ) -> CSVDocument:
        """Save the processed CSV data to the database"""

        from django.db import transaction
        from django.contrib.auth.models import User
        from .models import TwinVersion, TimeSeriesData, TimeSeriesPoint

        with transaction.atomic():
            # Get default user if not provided
            if user_id:
                user = User.objects.get(id=user_id)
            else:
                user, _ = User.objects.get_or_create(username="default_user")

            # Get twin version if provided
            twin_version = None
            if twin_version_id:
                twin_version = TwinVersion.objects.get(id=twin_version_id)

            # Create CSV document
            csv_doc = CSVDocument.objects.create(
                title=filename,
                file_path=file_path or filename,
                twin_version=twin_version,
                uploaded_by=user,
                file_size=os.path.getsize(file_path) if file_path else 0,
                row_count=len(df),
                column_count=len(df.columns),
                schema_summary=json.dumps(schema["summary"]),
                status="completed",
                processed_at=timezone.now(),
            )

            # Create dataset record
            dataset = CSVDataset.objects.create(
                document=csv_doc, data_sample=df.head(5).to_json(), total_rows=len(df)
            )

            # Try to generate statistical summary
            try:
                stats_summary = self._generate_stats_summary(df)
                dataset.statistical_summary = json.dumps(stats_summary)
                dataset.save()
            except Exception as e:
                logger.warning(f"Error generating statistical summary: {str(e)}")

            # Create column records
            for col_name, col_info in schema["columns"].items():
                CSVColumn.objects.create(
                    dataset=dataset,
                    name=col_name,
                    data_type=col_info["data_type"],
                    description=col_info.get("description", ""),
                    statistics=json.dumps(col_info["statistics"]),
                    is_time_column="temporal" in col_info.get("tags", []),
                    is_categorical="categorical" in col_info.get("tags", []),
                    is_numerical="numerical" in col_info.get("tags", []),
                    is_primary_key="primary_key" in col_info.get("tags", []),
                    sample_values=json.dumps(df[col_name].head(10).tolist()),
                )

            # Create time series records
            for ts in time_series:
                time_series_obj = TimeSeriesData.objects.create(
                    title=ts["name"],
                    description=ts["description"],
                    document=csv_doc,  # Link to the document
                    data_type="csv",
                    unit=ts.get("unit", ""),
                    source_text=f"CSV column: {ts['value_column']}",
                )

                # Create time series points
                time_data = df[ts["time_column"]]
                value_data = df[ts["value_column"]]

                # Convert time data to datetime if necessary
                try:
                    time_data = pd.to_datetime(time_data)
                except (ValueError, TypeError, pd.errors.OutOfBoundsDatetime):
                    # If conversion fails, skip this time series
                    continue

                # Create points (limiting to 10,000 points max)
                points_to_create = []
                max_points = min(len(time_data), 10000)

                # Sample points if there are too many
                if len(time_data) > max_points:
                    step = len(time_data) // max_points
                    indices = list(range(0, len(time_data), step))[:max_points]
                else:
                    indices = range(len(time_data))

                for i in indices:
                    try:
                        time_value = time_data.iloc[i]
                        value = float(value_data.iloc[i])

                        if pd.notna(time_value) and pd.notna(value):
                            # Ensure we have timezone info
                            if timezone.is_naive(time_value):
                                time_value = timezone.make_aware(time_value)

                            points_to_create.append(
                                TimeSeriesPoint(
                                    time_series=time_series_obj,
                                    timestamp=time_value,
                                    value=value,
                                )
                            )
                    except (ValueError, TypeError):
                        continue

                # Bulk create all points (in batches to avoid memory issues)
                batch_size = 1000
                for i in range(0, len(points_to_create), batch_size):
                    batch = points_to_create[i : i + batch_size]
                    TimeSeriesPoint.objects.bulk_create(batch)

            return csv_doc

    def _generate_stats_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Generate statistical summary for the dataset"""
        summary = {}

        try:
            # Get numerical column stats
            numerical_cols = df.select_dtypes(include=["number"])
            if not numerical_cols.empty:
                summary["numerical"] = {
                    "mean": {
                        col: float(val)
                        for col, val in numerical_cols.mean().to_dict().items()
                    },
                    "median": {
                        col: float(val)
                        for col, val in numerical_cols.median().to_dict().items()
                    },
                    "std": {
                        col: float(val)
                        for col, val in numerical_cols.std().to_dict().items()
                    },
                    "min": {
                        col: float(val)
                        for col, val in numerical_cols.min().to_dict().items()
                    },
                    "max": {
                        col: float(val)
                        for col, val in numerical_cols.max().to_dict().items()
                    },
                }

            # Get categorical column stats
            categorical_cols = df.select_dtypes(include=["object", "category"])
            if not categorical_cols.empty:
                summary["categorical"] = {}
                for col in categorical_cols.columns:
                    value_counts = {
                        str(k): int(v)
                        for k, v in df[col].value_counts().head(10).to_dict().items()
                    }
                    unique_count = df[col].nunique()
                    null_count = df[col].isna().sum()

                    summary["categorical"][col] = {
                        "top_values": value_counts,
                        "unique_count": int(unique_count),
                        "null_count": int(null_count),
                        "null_percentage": float((null_count / len(df)) * 100),
                    }

            # Get temporal stats if any
            try:
                date_cols = df.select_dtypes(include=["datetime"])
                if not date_cols.empty:
                    summary["temporal"] = {}
                    for col in date_cols.columns:
                        summary["temporal"][col] = {
                            "min": (
                                df[col].min().isoformat()
                                if not pd.isna(df[col].min())
                                else None
                            ),
                            "max": (
                                df[col].max().isoformat()
                                if not pd.isna(df[col].max())
                                else None
                            ),
                            "range_days": (
                                int((df[col].max() - df[col].min()).days)
                                if not pd.isna(df[col].min())
                                and not pd.isna(df[col].max())
                                else None
                            ),
                        }
            except (ValueError, TypeError, AttributeError):
                # Skip temporal stats if datetime conversion issues
                pass

            # Get null stats
            null_counts = df.isna().sum().to_dict()
            summary["null_stats"] = {
                "column_nulls": {col: int(count) for col, count in null_counts.items()},
                "total_nulls": int(sum(null_counts.values())),
                "null_percentage": float(
                    (sum(null_counts.values()) / (len(df) * len(df.columns))) * 100
                ),
            }

        except Exception as e:
            logger.error(f"Error generating stats summary: {str(e)}")
            summary["error"] = str(e)

        return summary

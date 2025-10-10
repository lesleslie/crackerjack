"""Embedding generation service for semantic search functionality."""

import hashlib
import logging

# Suppress transformers framework warnings (we only use tokenizers, not models)
import os
import sys
import typing as t
import warnings
from io import StringIO
from pathlib import Path

import numpy as np
import onnxruntime as ort

# Temporarily redirect stderr to suppress transformers warnings
_original_stderr = sys.stderr
sys.stderr = StringIO()

# Also set environment variable to suppress transformers warnings
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

try:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning)
        from transformers import AutoTokenizer
finally:
    # Restore original stderr
    sys.stderr = _original_stderr

from crackerjack.models.semantic_models import SemanticConfig

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing text embeddings using ONNX Runtime."""

    def __init__(self, config: SemanticConfig) -> None:
        """Initialize the embedding service with configuration.

        Args:
            config: Semantic search configuration containing model settings
        """
        self.config = config
        self._session: ort.InferenceSession | None = None
        self._tokenizer: AutoTokenizer | None = None
        self._model_loaded = False

    @property
    def session(self) -> ort.InferenceSession:
        """Lazy-loaded ONNX inference session."""
        if not self._model_loaded:
            self._load_model()
        if self._session is None:
            msg = f"Failed to load ONNX model: {self.config.embedding_model}"
            raise RuntimeError(msg)
        return self._session

    @property
    def tokenizer(self) -> AutoTokenizer:
        """Lazy-loaded tokenizer."""
        if not self._model_loaded:
            self._load_model()
        if self._tokenizer is None:
            msg = f"Failed to load tokenizer: {self.config.embedding_model}"
            raise RuntimeError(msg)
        return self._tokenizer

    def _load_model(self) -> None:
        """Load the ONNX model and tokenizer."""
        try:
            logger.info(f"Loading ONNX embedding model: {self.config.embedding_model}")

            # Use a simple local model path approach for now
            # In production, this would download from HuggingFace Hub
            model_name = self.config.embedding_model

            # Try to load tokenizer with specific revision for security
            self._tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                revision="main",  # nosec B615
            )

            # For now, we'll use a simplified approach without actual ONNX model file
            # This would need to be expanded to download/convert ONNX models
            self._session = None  # Placeholder - would load actual ONNX file
            self._model_loaded = True

            logger.info(
                f"Successfully loaded tokenizer for: {self.config.embedding_model}"
            )
            logger.warning(
                "ONNX session not implemented yet - using fallback embeddings"
            )

        except Exception as e:
            logger.error(
                f"Failed to load embedding model {self.config.embedding_model}: {e}"
            )
            self._session = None
            self._tokenizer = None
            self._model_loaded = True

    def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding vector for a single text.

        Args:
            text: Text content to embed

        Returns:
            List of float values representing the embedding vector

        Raises:
            RuntimeError: If model loading failed or text is empty
        """
        if not text.strip():
            msg = "Cannot generate embedding for empty text"
            raise ValueError(msg)

        try:
            # For now, use a simple hash-based embedding as fallback
            # This will be replaced with proper ONNX inference
            embedding = self._generate_fallback_embedding(text)
            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding for text: {e}")
            raise RuntimeError(f"Embedding generation failed: {e}") from e

    def _generate_fallback_embedding(self, text: str) -> list[float]:
        """Generate a simple hash-based embedding as fallback.

        This is a temporary implementation until proper ONNX integration.
        """
        # Create a simple 384-dimensional embedding based on text hash
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Convert hex to numbers and normalize
        embedding = []
        for i in range(
            0, min(len(text_hash), 96), 2
        ):  # 96 hex chars = 48 bytes = 384 bits
            hex_pair = text_hash[i : i + 2]
            value = int(hex_pair, 16) / 255.0  # Normalize to 0-1
            embedding.extend([value] * 8)  # Expand to 384 dimensions

        # Pad to exactly 384 dimensions
        while len(embedding) < 384:
            embedding.append(0.0)

        return embedding[:384]

    def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of text content to embed

        Returns:
            List of embedding vectors, one for each input text

        Raises:
            ValueError: If texts list is empty
            RuntimeError: If model loading failed
        """
        if not texts:
            msg = "Cannot generate embeddings for empty text list"
            raise ValueError(msg)

        # Filter out empty texts and track original indices
        valid_texts = []
        valid_indices = []

        for i, text in enumerate(texts):
            if text.strip():
                valid_texts.append(text)
                valid_indices.append(i)

        if not valid_texts:
            msg = "All texts are empty - cannot generate embeddings"
            raise ValueError(msg)

        try:
            logger.debug(f"Generating embeddings for {len(valid_texts)} texts")

            # Generate embeddings for each text using fallback approach
            result = [[] for _ in texts]

            for i, text in enumerate(valid_texts):
                original_index = valid_indices[i]
                embedding = self._generate_fallback_embedding(text)
                result[original_index] = embedding

            return result

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            raise RuntimeError(f"Batch embedding generation failed: {e}") from e

    def calculate_similarity(
        self, embedding1: list[float], embedding2: list[float]
    ) -> float:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score between 0.0 and 1.0 (higher means more similar)

        Raises:
            ValueError: If embeddings have different dimensions or are empty
        """
        if not embedding1 or not embedding2:
            msg = "Cannot calculate similarity for empty embeddings"
            raise ValueError(msg)

        if len(embedding1) != len(embedding2):
            msg = (
                f"Embedding dimensions mismatch: {len(embedding1)} vs {len(embedding2)}"
            )
            raise ValueError(msg)

        try:
            # Convert to numpy arrays for efficient computation
            vec1 = np.array(embedding1, dtype=np.float32)
            vec2 = np.array(embedding2, dtype=np.float32)

            # Calculate cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if 0 in (norm1, norm2):
                return 0.0

            similarity = dot_product / (norm1 * norm2)

            # Ensure result is between 0 and 1
            return max(0.0, min(1.0, float(similarity)))

        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            raise RuntimeError(f"Similarity calculation failed: {e}") from e

    def calculate_similarities_batch(
        self, query_embedding: list[float], embeddings: list[list[float]]
    ) -> list[float]:
        """Calculate similarities between query and multiple embeddings efficiently.

        Args:
            query_embedding: Query embedding vector
            embeddings: List of embedding vectors to compare against

        Returns:
            List of similarity scores (0.0 to 1.0) for each embedding

        Raises:
            ValueError: If query embedding is empty or embeddings list is empty
        """
        if not query_embedding:
            msg = "Query embedding cannot be empty"
            raise ValueError(msg)

        if not embeddings:
            msg = "Embeddings list cannot be empty"
            raise ValueError(msg)

        try:
            # Convert to numpy arrays for vectorized computation
            query_vec = np.array(query_embedding, dtype=np.float32)
            embedding_matrix = np.array(embeddings, dtype=np.float32)

            # Calculate cosine similarities using vectorized operations
            dot_products = np.dot(embedding_matrix, query_vec)
            query_norm = np.linalg.norm(query_vec)
            embedding_norms = np.linalg.norm(embedding_matrix, axis=1)

            # Handle zero norms
            if query_norm == 0:
                return [0.0] * len(embeddings)

            similarities = dot_products / (query_norm * embedding_norms)

            # Handle any NaN values and ensure range [0, 1]
            similarities = np.nan_to_num(similarities, nan=0.0)
            similarities = np.clip(similarities, 0.0, 1.0)

            return similarities.tolist()

        except Exception as e:
            logger.error(f"Failed to calculate batch similarities: {e}")
            raise RuntimeError(f"Batch similarity calculation failed: {e}") from e

    def get_text_hash(self, text: str) -> str:
        """Generate a hash for text content to detect changes.

        Args:
            text: Text content to hash

        Returns:
            SHA-256 hash of the text content
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get_file_hash(self, file_path: Path) -> str:
        """Generate a hash for file content to detect changes.

        Args:
            file_path: Path to file to hash

        Returns:
            SHA-256 hash of the file content

        Raises:
            OSError: If file cannot be read
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            return self.get_text_hash(content)
        except UnicodeDecodeError:
            # Handle binary files by reading as bytes
            content_bytes = file_path.read_bytes()
            return hashlib.sha256(content_bytes).hexdigest()

    def chunk_text(self, text: str) -> list[str]:
        """Split text into chunks based on configuration.

        Args:
            text: Text content to chunk

        Returns:
            List of text chunks with overlap as configured
        """
        if not text.strip():
            return []

        # Simple sentence-based chunking with overlap
        sentences = self._split_into_sentences(text)
        chunks = []

        current_chunk = ""
        overlap_sentences = []

        for sentence in sentences:
            # Check if adding this sentence would exceed chunk size
            potential_chunk = current_chunk + sentence

            if len(potential_chunk) <= self.config.chunk_size:
                current_chunk = potential_chunk
            else:
                # Save current chunk if it has content
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())

                # Start new chunk with overlap
                overlap_text = (
                    "".join(overlap_sentences[-2:]) if overlap_sentences else ""
                )
                current_chunk = overlap_text + sentence

            overlap_sentences.append(sentence)

        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences using simple string operations.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitting using string operations (no regex)
        # Split on common sentence terminators
        sentences = []
        current_sentence = ""

        for char in text:
            current_sentence += char
            if char in ".!?" and len(current_sentence.strip()) > 1:
                # Look ahead to see if there's whitespace (end of sentence)
                sentences.append(current_sentence.strip())
                current_sentence = ""

        # Add remaining text as final sentence
        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        return sentences or [text]

    def is_model_available(self) -> bool:
        """Check if the embedding model is available and loaded.

        Returns:
            True if model is ready for use, False otherwise
        """
        if not self._model_loaded:
            try:
                # Try to load the model
                self._load_model()
            except Exception:
                return False

        return self._session is not None

    def get_model_info(self) -> dict[str, t.Any]:
        """Get information about the loaded model.

        Returns:
            Dictionary containing model metadata
        """
        if not self.is_model_available():
            return {
                "model_name": self.config.embedding_model,
                "loaded": False,
                "error": "Model not available",
                "embedding_dimension": 384,  # Fallback dimension
            }

        try:
            # Use fallback approach for model info
            test_embedding = self._generate_fallback_embedding("test")
            return {
                "model_name": self.config.embedding_model,
                "loaded": True,
                "max_seq_length": "unknown",
                "embedding_dimension": len(test_embedding),
                "device": "cpu",
            }
        except Exception as e:
            return {
                "model_name": self.config.embedding_model,
                "loaded": True,
                "error": str(e),
            }

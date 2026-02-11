"""Issue embedder using sentence-transformers for semantic similarity.

This module provides neural embeddings for Issue objects using the
all-MiniLM-L6-v2 model, converting issues to 384-dimensional vectors
for fast cosine similarity matching.

Falls back gracefully to TF-IDF when torch is unavailable (e.g., Python 3.13
on Intel Macs where torch wheels are not available).
"""

import logging
import warnings

import numpy as np

from crackerjack.agents.base import Issue

logger = logging.getLogger(__name__)

# Try to import sentence-transformers
# Note: This may fail on Python 3.13 + Intel Mac due to lack of torch wheels
_SENTENCE_TRANSFORMERS_AVAILABLE = False
_model_class = None

try:
    from sentence_transformers import SentenceTransformer

    _SENTENCE_TRANSFORMERS_AVAILABLE = True
    _model_class = SentenceTransformer
    logger.info("✅ sentence-transformers is available (neural embeddings enabled)")
except ImportError as e:
    logger.warning(
        f"⚠️ sentence-transformers not available: {e}. "
        "Will use TF-IDF fallback for embeddings."
    )
    _SENTENCE_TRANSFORMERS_AVAILABLE = False
except Exception as e:
    logger.warning(
        f"⚠️ sentence-transformers initialization failed: {e}. "
        "Will use TF-IDF fallback for embeddings."
    )
    _SENTENCE_TRANSFORMERS_AVAILABLE = False


class IssueEmbedder:
    """Neural issue embedder using sentence-transformers.

    Features:
    - Converts Issue objects to 384-dimensional embeddings
    - Uses all-MiniLM-L6-v2 model (80MB download on first use)
    - Caches model globally for performance (~100ms per embedding)
    - Handles missing fields gracefully (file_path can be None)

    Raises:
        ImportError: If sentence-transformers is not available during init
    """

    # Expected embedding dimension for all-MiniLM-L6-v2
    EXPECTED_EMBEDDING_DIM = 384

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize the embedder with a sentence-transformers model.

        Args:
            model_name: HuggingFace model name (default: all-MiniLM-L6-v2)

        Raises:
            ImportError: If sentence-transformers is not available
            RuntimeError: If model loading fails
        """
        if not _SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is not available. "
                "Use FallbackIssueEmbedder from fallback_embedder.py instead, "
                "or install torch/sentence-transformers for your platform."
            )

        try:
            # Suppress torch warnings
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning)
                self.model = _model_class(model_name)

            # Validate embedding dimension
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            if self.embedding_dim != self.EXPECTED_EMBEDDING_DIM:
                logger.warning(
                    f"Model {model_name} has embedding_dim={self.embedding_dim}, "
                    f"expected {self.EXPECTED_EMBEDDING_DIM}"
                )

            logger.info(
                f"✅ IssueEmbedder initialized with {model_name} "
                f"(embedding_dim={self.embedding_dim})"
            )
        except Exception as e:
            logger.error(f"❌ Failed to load sentence transformer model: {e}")
            raise RuntimeError(f"Model loading failed: {e}") from e

    def embed_issue(self, issue: Issue) -> np.ndarray:
        """Convert a single Issue to a 384-dimensional embedding vector.

        Args:
            issue: The Issue object to embed

        Returns:
            np.ndarray: 384-dimensional embedding vector (float32)

        Raises:
            Exception: Returns zero vector on failure (logged)
        """
        try:
            feature_text = self._build_feature_text(issue)
            embedding = self.model.encode(
                feature_text,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            # Ensure float32 for storage efficiency
            embedding = embedding.astype(np.float32)

            logger.debug(
                f"Created embedding for issue {issue.id[:8]}... "
                f"(shape={embedding.shape})"
            )

            return embedding

        except Exception as e:
            logger.error(f"Failed to embed issue {issue.id}: {e}")

            # Return zero vector on failure (same dimension as expected)
            return np.zeros(self.EXPECTED_EMBEDDING_DIM, dtype=np.float32)

    def embed_batch(self, issues: list[Issue]) -> np.ndarray:
        """Convert multiple Issues to embedding vectors (batch processing).

        Args:
            issues: List of Issue objects to embed

        Returns:
            np.ndarray: Array of shape (len(issues), 384) with embeddings

        Note:
            Returns zero array on failure (logged)
        """
        if not issues:
            return np.array([]).reshape(0, self.EXPECTED_EMBEDDING_DIM)

        try:
            feature_texts = [self._build_feature_text(issue) for issue in issues]
            embeddings = self.model.encode(
                feature_texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=32,
            )

            # Ensure float32 for storage efficiency
            embeddings = embeddings.astype(np.float32)

            logger.debug(
                f"Created batch embeddings for {len(issues)} issues "
                f"(shape={embeddings.shape})"
            )
            return embeddings

        except Exception as e:
            logger.error(f"Failed to embed batch of {len(issues)} issues: {e}")

            # Return zero array on failure
            return np.zeros((len(issues), self.EXPECTED_EMBEDDING_DIM), dtype=np.float32)

    def _build_feature_text(self, issue: Issue) -> str:
        """Build text representation for embedding.

        Combines issue features into a single string for semantic encoding.
        Format follows pattern: "Type: TYPE | Message: MSG | Stage: STAGE | File: PATH"

        Args:
            issue: Issue object to convert to text

        Returns:
            str: Text representation of issue features
        """
        parts = [
            f"Type: {issue.type.value}",
            f"Message: {issue.message}",
            f"Stage: {issue.stage}",
        ]

        if issue.file_path:
            parts.append(f"File: {issue.file_path}")

        if issue.line_number:
            parts.append(f"Line: {issue.line_number}")

        return " | ".join(parts)

    @staticmethod
    def compute_similarity(
        query_embedding: np.ndarray,
        stored_embedding: np.ndarray,
    ) -> float:
        """Compute cosine similarity between two embedding vectors.

        Args:
            query_embedding: Query issue embedding (384-dim)
            stored_embedding: Stored issue embedding (384-dim)

        Returns:
            float: Cosine similarity score (0.0 to 1.0)

        Note:
            Returns 0.0 on failure (logged)
        """
        try:
            # Cosine similarity = dot product of normalized vectors
            norm_query = np.linalg.norm(query_embedding)
            norm_stored = np.linalg.norm(stored_embedding)

            if norm_query == 0 or norm_stored == 0:
                return 0.0

            similarity = np.dot(query_embedding, stored_embedding) / (norm_query * norm_stored)
            return float(similarity)

        except Exception as e:
            logger.warning(f"Failed to compute similarity: {e}")
            return 0.0


# Global singleton for model caching
_embedder_instance: IssueEmbedder | None = None


def get_issue_embedder(model_name: str = "all-MiniLM-L6-v2") -> IssueEmbedder:
    """Get or create global IssueEmbedder instance (singleton pattern).

    Caches the model globally to avoid reloading (~80MB download on first use,
    ~100ms per embedding after loading).

    Args:
        model_name: HuggingFace model name (default: all-MiniLM-L6-v2)

    Returns:
        IssueEmbedder: Singleton embedder instance

    Raises:
        ImportError: If sentence-transformers is not available
    """
    global _embedder_instance

    if _embedder_instance is None:
        _embedder_instance = IssueEmbedder(model_name)
        logger.info("Created new IssueEmbedder singleton instance")

    return _embedder_instance


def is_neural_embeddings_available() -> bool:
    """Check if neural embeddings are available on this platform.

    Returns:
        bool: True if sentence-transformers can be imported, False otherwise

    Note:
        Returns False on Python 3.13 + Intel Mac (no torch wheels available).
        Use FallbackIssueEmbedder in this case.
    """
    return _SENTENCE_TRANSFORMERS_AVAILABLE


__all__ = [
    "IssueEmbedder",
    "get_issue_embedder",
    "is_neural_embeddings_available",
]

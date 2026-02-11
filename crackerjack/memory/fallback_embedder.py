"""Fallback issue embedder using scikit-learn for platform compatibility.

This module provides TF-IDF vectorization and cosine similarity
as a fallback when sentence-transformers is not available.
"""

import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from crackerjack.agents.base import Issue

logger = logging.getLogger(__name__)


class FallbackIssueEmbedder:
    """Fallback issue embedder using TF-IDF when ML libraries unavailable.

    Uses scikit-learn for:
    - TF-IDF vectorization of issue text
    - Cosine similarity for finding similar issues
    - Platform-universal (no torch requirement)
    """

    def __init__(self) -> None:
        """Initialize the fallback embedder."""
        try:
            # Create TF-IDF vectorizer
            # Features: issue type, message, file path, stage
            self.vectorizer = TfidfVectorizer(
                max_features=100,  # Limit vocabulary size
                ngram_range=(1, 3),  # Use unigrams, bigrams, trigrams
                stop_words='english',  # Common stopwords
                lowercase=True,  # Normalize to lowercase
            )

            logger.info(
                "✅ FallbackIssueEmbedder initialized (TF-IDF, scikit-learn based)"
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize fallback embedder: {e}")
            raise

    def embed_issue(self, issue: Issue) -> np.ndarray:
        """Convert issue to TF-IDF vector.

        Args:
            issue: The issue to embed

        Returns:
            np.ndarray: TF-IDF vector (sparse matrix representation)
        """
        try:
            # Build feature text (same as neural embedder)
            feature_text = self._build_feature_text(issue)

            # Transform to TF-IDF vector
            tfidf_matrix = self.vectorizer.fit_transform([feature_text])

            logger.debug(
                f"Created TF-IDF embedding for issue {issue.id[:8]}... "
                f"(shape={tfidf_matrix.shape}, features={tfidf_matrix.shape[1]})"
            )

            return tfidf_matrix

        except Exception as e:
            logger.error(f"Failed to embed issue {issue.id}: {e}")
            # Return zero vector on failure
            return np.zeros((1, 100), dtype=np.float32)

    def compute_similarity(
        self,
        query_vector: np.ndarray,
        stored_vector: np.ndarray,
    ) -> float:
        """Compute cosine similarity between TF-IDF vectors.

        Args:
            query_vector: TF-IDF vector of query issue
            stored_vector: TF-IDF vector of stored issue

        Returns:
            float: Cosine similarity score (0-1)
        """
        try:
            # scikit-learn cosine_similarity handles sparse matrices
            similarity = cosine_similarity(query_vector, stored_vector)

            # Return scalar from 1x1 matrix
            if hasattr(similarity, 'flatten'):
                return float(similarity.flatten()[0])
            else:
                return float(similarity)

        except Exception as e:
            logger.warning(f"Failed to compute similarity: {e}")
            return 0.0

    def _build_feature_text(self, issue: Issue) -> str:
        """Build text representation for TF-IDF vectorization.

        Format: "type message file stage" (same as neural embedder)
        """
        parts = [
            f"{issue.type.value}",
            issue.message,
            issue.stage,
        ]

        if issue.file_path:
            parts.append(issue.file_path)

        return " ".join(parts)


# Global singleton
_embedder_instance: FallbackIssueEmbedder | None = None


def get_fallback_embedder() -> FallbackIssueEmbedder:
    """Get or create global fallback embedder instance.

    Returns:
        FallbackIssueEmbedder: Singleton instance
    """
    global _embedder_instance

    if _embedder_instance is None:
        _embedder_instance = FallbackIssueEmbedder()
        logger.info("Created new FallbackIssueEmbedder instance")

    return _embedder_instance

"""Convert issues to vector embeddings for semantic similarity matching.

This module uses sentence-transformers to create 384-dimensional embeddings
that capture the semantic meaning of issues for neural pattern matching.
"""

import logging
import typing as t

import numpy as np
from sentence_transformers import SentenceTransformer

from crackerjack.agents.base import Issue

logger = logging.getLogger(__name__)


class IssueEmbedder:
    """Convert issues to embeddings for pattern matching.

    Uses the all-MiniLM-L6-v2 model which provides:
    - 384-dimensional embeddings
    - Fast encoding (~50ms per issue)
    - Good semantic quality for code-related text
    - Small model size (80MB)
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        """Initialize the sentence transformer model.

        Args:
            model_name: HuggingFace model name (default: all-MiniLM-L6-v2)
        """
        try:
            self.model = SentenceTransformer(model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(
                f"✅ IssueEmbedder initialized with {model_name} "
                f"(embedding_dim={self.embedding_dim})"
            )
        except Exception as e:
            logger.error(f"❌ Failed to load sentence transformer model: {e}")
            raise

    def embed_issue(self, issue: Issue) -> np.ndarray:
        """Convert issue to 384-dim embedding vector.

        The embedding captures semantic features from:
        - Issue type (e.g., type_error, complexity)
        - Error message (semantic meaning)
        - File path (code location context)
        - Stage (workflow phase context)

        Args:
            issue: The issue to embed

        Returns:
            np.ndarray: 384-dimensional float vector
        """
        try:
            feature_text = self._build_feature_text(issue)
            embedding = self.model.encode(
                feature_text,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            logger.debug(
                f"Created embedding for issue {issue.id[:8]}... "
                f"(shape={embedding.shape})"
            )

            return embedding

        except Exception as e:
            logger.error(f"Failed to embed issue {issue.id}: {e}")
            # Return zero embedding on failure (will have low similarity)
            return np.zeros(self.embedding_dim, dtype=np.float32)

    def _build_feature_text(self, issue: Issue) -> str:
        """Build text representation for embedding.

        Combines structured issue data into a single text string
        that the sentence transformer can encode semantically.

        Format: "Type: {type} | Message: {message} | Stage: {stage} | File: {file}"
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

    def embed_batch(self, issues: list[Issue]) -> np.ndarray:
        """Encode multiple issues at once for efficiency.

        Args:
            issues: List of issues to embed

        Returns:
            np.ndarray: Shape (len(issues), 384) embedding matrix
        """
        if not issues:
            return np.array([]).reshape(0, self.embedding_dim)

        try:
            feature_texts = [self._build_feature_text(issue) for issue in issues]
            embeddings = self.model.encode(
                feature_texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=32,
            )

            logger.debug(f"Created batch embeddings for {len(issues)} issues")
            return embeddings

        except Exception as e:
            logger.error(f"Failed to embed batch of {len(issues)} issues: {e}")
            # Return zero embeddings
            return np.zeros((len(issues), self.embedding_dim), dtype=np.float32)


# Global singleton for reuse
_embedder_instance: IssueEmbedder | None = None


def get_issue_embedder(model_name: str = "all-MiniLM-L6-v2") -> IssueEmbedder:
    """Get or create global IssueEmbedder instance.

    Args:
        model_name: Model name to use

    Returns:
        IssueEmbedder: Singleton instance
    """
    global _embedder_instance

    if _embedder_instance is None:
        _embedder_instance = IssueEmbedder(model_name)

    return _embedder_instance

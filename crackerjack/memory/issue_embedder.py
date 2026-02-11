import logging
import warnings
from typing import Protocol

import numpy as np

from crackerjack.agents.base import Issue

logger = logging.getLogger(__name__)


class IssueEmbedderProtocol(Protocol):
    def embed_issue(self, issue: Issue) -> np.ndarray: ...

    def compute_similarity(self, query: np.ndarray, stored: np.ndarray) -> float: ...


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
    EXPECTED_EMBEDDING_DIM = 384

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        if not _SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is not available. "
                "Use FallbackIssueEmbedder from fallback_embedder.py instead, "
                "or install torch/sentence-transformers for your platform."
            )

        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning)
                self.model = _model_class(model_name)

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
        try:
            feature_text = self._build_feature_text(issue)
            embedding = self.model.encode(
                feature_text,
                convert_to_numpy=True,
                show_progress_bar=False,
            )

            embedding = embedding.astype(np.float32)

            logger.debug(
                f"Created embedding for issue {issue.id[:8]}... "
                f"(shape={embedding.shape})"
            )

            return embedding

        except Exception as e:
            logger.error(f"Failed to embed issue {issue.id}: {e}")

            return np.zeros(self.EXPECTED_EMBEDDING_DIM, dtype=np.float32)

    def embed_batch(self, issues: list[Issue]) -> np.ndarray:
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

            embeddings = embeddings.astype(np.float32)

            logger.debug(
                f"Created batch embeddings for {len(issues)} issues "
                f"(shape={embeddings.shape})"
            )
            return embeddings

        except Exception as e:
            logger.error(f"Failed to embed batch of {len(issues)} issues: {e}")

            return np.zeros(
                (len(issues), self.EXPECTED_EMBEDDING_DIM), dtype=np.float32
            )

    def _build_feature_text(self, issue: Issue) -> str:
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
        try:
            norm_query = np.linalg.norm(query_embedding)
            norm_stored = np.linalg.norm(stored_embedding)

            if norm_query == 0 or norm_stored == 0:
                return 0.0

            similarity = np.dot(query_embedding, stored_embedding) / (
                norm_query * norm_stored
            )
            return float(similarity)

        except Exception as e:
            logger.warning(f"Failed to compute similarity: {e}")
            return 0.0


_embedder_instance: IssueEmbedder | None = None


def get_issue_embedder(
    model_name: str = "all-MiniLM-L6-v2",
) -> IssueEmbedderProtocol:
    global _embedder_instance

    if _embedder_instance is None:
        if _SENTENCE_TRANSFORMERS_AVAILABLE:
            _embedder_instance = IssueEmbedder(model_name)
            logger.info("✅ Created IssueEmbedder with sentence-transformers")
        else:
            from crackerjack.memory.fallback_embedder import (
                FallbackIssueEmbedder,
            )

            _embedder_instance = FallbackIssueEmbedder()
            logger.info("✅ Created FallbackIssueEmbedder (TF-IDF based)")

    return _embedder_instance


def is_neural_embeddings_available() -> bool:
    return _SENTENCE_TRANSFORMERS_AVAILABLE


__all__ = [
    "IssueEmbedderProtocol",
    "IssueEmbedder",
    "get_issue_embedder",
    "is_neural_embeddings_available",
]

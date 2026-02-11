import logging

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from crackerjack.agents.base import Issue

logger = logging.getLogger(__name__)


class FallbackIssueEmbedder:
    def __init__(self) -> None:
        try:
            self.vectorizer = TfidfVectorizer(
                max_features=100,
                ngram_range=(1, 3),
                stop_words="english",
                lowercase=True,
            )

            logger.info(
                "✅ FallbackIssueEmbedder initialized (TF-IDF, scikit-learn based)"
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize fallback embedder: {e}")
            raise

    def embed_issue(self, issue: Issue) -> np.ndarray:
        try:
            feature_text = self._build_feature_text(issue)

            tfidf_matrix = self.vectorizer.fit_transform([feature_text])

            logger.debug(
                f"Created TF-IDF embedding for issue {issue.id[:8]}... "
                f"(shape={tfidf_matrix.shape}, features={tfidf_matrix.shape[1]})"
            )

            return tfidf_matrix

        except Exception as e:
            logger.error(f"Failed to embed issue {issue.id}: {e}")

            return np.zeros((1, 100), dtype=np.float32)

    def compute_similarity(
        self,
        query_vector: np.ndarray,
        stored_vector: np.ndarray,
    ) -> float:
        try:
            similarity = cosine_similarity(query_vector, stored_vector)

            if hasattr(similarity, "flatten"):
                return float(similarity.flatten()[0])
            else:
                return float(similarity)

        except Exception as e:
            logger.warning(f"Failed to compute similarity: {e}")
            return 0.0

    def _build_feature_text(self, issue: Issue) -> str:
        parts = [
            f"{issue.type.value}",
            issue.message,
            issue.stage,
        ]

        if issue.file_path:
            parts.append(issue.file_path)

        return " ".join(parts)


_embedder_instance: FallbackIssueEmbedder | None = None


def get_fallback_embedder() -> FallbackIssueEmbedder:
    global _embedder_instance

    if _embedder_instance is None:
        _embedder_instance = FallbackIssueEmbedder()
        logger.info("Created new FallbackIssueEmbedder instance")

    return _embedder_instance

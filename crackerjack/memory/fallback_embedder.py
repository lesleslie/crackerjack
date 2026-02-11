import logging
from typing import Union

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from crackerjack.agents.base import Issue
from crackerjack.models.git_analytics import (
    GitBranchEvent,
    GitCommitData,
    WorkflowEvent,
)

logger = logging.getLogger(__name__)

# Type alias for all embeddable data types
EmbeddableData = Union[Issue, GitCommitData, GitBranchEvent, WorkflowEvent]


class FallbackIssueEmbedder:
    EXPECTED_EMBEDDING_DIM = 100

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

    def embed_git_commit(self, commit: GitCommitData) -> np.ndarray:
        """Embed a git commit using TF-IDF fallback.

        Args:
            commit: GitCommitData instance to embed

        Returns:
            numpy array with TF-IDF features
        """
        try:
            feature_text = commit.to_searchable_text()

            tfidf_matrix = self.vectorizer.fit_transform([feature_text])

            logger.debug(
                f"Created TF-IDF embedding for commit {commit.commit_hash[:8]}... "
                f"(shape={tfidf_matrix.shape}, features={tfidf_matrix.shape[1]})"
            )

            return tfidf_matrix

        except Exception as e:
            logger.error(f"Failed to embed commit {commit.commit_hash}: {e}")

            return np.zeros((1, 100), dtype=np.float32)

    def embed_git_branch_event(self, event: GitBranchEvent) -> np.ndarray:
        """Embed a git branch event using TF-IDF fallback.

        Args:
            event: GitBranchEvent instance to embed

        Returns:
            numpy array with TF-IDF features
        """
        try:
            feature_text = event.to_searchable_text()

            tfidf_matrix = self.vectorizer.fit_transform([feature_text])

            logger.debug(
                f"Created TF-IDF embedding for branch event {event.branch_name} "
                f"(shape={tfidf_matrix.shape}, features={tfidf_matrix.shape[1]})"
            )

            return tfidf_matrix

        except Exception as e:
            logger.error(f"Failed to embed branch event {event.branch_name}: {e}")

            return np.zeros((1, 100), dtype=np.float32)

    def embed_workflow_event(self, event: WorkflowEvent) -> np.ndarray:
        """Embed a workflow event using TF-IDF fallback.

        Args:
            event: WorkflowEvent instance to embed

        Returns:
            numpy array with TF-IDF features
        """
        try:
            feature_text = event.to_searchable_text()

            tfidf_matrix = self.vectorizer.fit_transform([feature_text])

            logger.debug(
                f"Created TF-IDF embedding for workflow event {event.workflow_name} "
                f"(shape={tfidf_matrix.shape}, features={tfidf_matrix.shape[1]})"
            )

            return tfidf_matrix

        except Exception as e:
            logger.error(f"Failed to embed workflow event {event.workflow_name}: {e}")

            return np.zeros((1, 100), dtype=np.float32)

    def embed_batch(self, items: list[EmbeddableData]) -> np.ndarray:
        """Embed a batch of mixed data types using TF-IDF fallback.

        Args:
            items: List of Issue, GitCommitData, GitBranchEvent, or WorkflowEvent

        Returns:
            list of numpy arrays with TF-IDF features (one per item)
        """
        embeddings = []
        for item in items:
            if isinstance(item, Issue):
                embeddings.append(self.embed_issue(item))
            elif isinstance(item, GitCommitData):
                embeddings.append(self.embed_git_commit(item))
            elif isinstance(item, GitBranchEvent):
                embeddings.append(self.embed_git_branch_event(item))
            elif isinstance(item, WorkflowEvent):
                embeddings.append(self.embed_workflow_event(item))
            else:
                logger.warning(f"Unknown item type: {type(item)}")
                embeddings.append(np.zeros((1, 100), dtype=np.float32))

        return embeddings

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

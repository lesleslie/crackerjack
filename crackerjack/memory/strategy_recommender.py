from __future__ import annotations

import operator

import logging
from dataclasses import dataclass

import numpy as np

from crackerjack.agents.base import Issue
from crackerjack.memory.fix_strategy_storage import FixAttempt, FixStrategyStorage
from crackerjack.memory.issue_embedder import (
    IssueEmbedderProtocol,
    get_issue_embedder,
)

logger = logging.getLogger(__name__)


@dataclass
class StrategyRecommendation:
    agent_strategy: str
    confidence: float
    similarity_score: float
    success_rate: float
    sample_count: int
    alternatives: list[tuple[str, float]]
    reasoning: str


class StrategyRecommender:
    MIN_SIMILARITY_THRESHOLD = 0.3

    MIN_SAMPLE_SIZE = 2

    def __init__(
        self,
        storage: FixStrategyStorage,
        embedder: IssueEmbedderProtocol | None = None,
    ) -> None:
        self.storage = storage

        if embedder is None:
            try:
                embedder = get_issue_embedder()
            except ImportError:
                logger.warning(
                    "Neural embeddings not available, "
                    "recommendations will use TF-IDF fallback"
                )

        self.embedder = embedder
        logger.info("StrategyRecommender initialized")

    def recommend_strategy(
        self,
        issue: Issue,
        k: int = 10,
        min_confidence: float = 0.4,
    ) -> StrategyRecommendation | None:

        try:
            if self.embedder is not None:
                issue_embedding = self.embedder.embed_issue(issue)
            else:
                from crackerjack.memory.fallback_embedder import (
                    FallbackIssueEmbedder,
                )

                fallback_embedder = FallbackIssueEmbedder()
                issue_embedding = fallback_embedder.embed_issue(issue)
        except Exception as e:
            logger.error(f"Failed to embed issue: {e}")
            return None

        similar_issues = self.storage.find_similar_issues(
            issue_embedding=issue_embedding,
            issue_type=issue.type.value,
            k=k,
            min_similarity=self.MIN_SIMILARITY_THRESHOLD,
        )

        if not similar_issues:
            logger.debug("No similar issues found for recommendation")
            return None

        successful_attempts = [at for at in similar_issues if at.success]

        if len(successful_attempts) < self.MIN_SAMPLE_SIZE:
            logger.debug(
                f"Not enough successful attempts "
                f"({len(successful_attempts)} < {self.MIN_SAMPLE_SIZE})"
            )
            return None

        strategy_scores = self._calculate_strategy_scores(
            successful_attempts, issue_embedding
        )

        if not strategy_scores:
            return None

        best_strategy_key = max(strategy_scores.items(), key=operator.itemgetter(1))[0]  # type: ignore
        best_score = strategy_scores[best_strategy_key]

        alternatives = [
            (key, score)
            for key, score in strategy_scores.items()
            if key != best_strategy_key
        ]
        alternatives.sort(key=operator.itemgetter(1), reverse=True)  # type: ignore
        top_alternatives = alternatives[:3]

        strategy_attempts = [
            at
            for at in successful_attempts
            if f"{at.agent_used}:{at.strategy}" == best_strategy_key
        ]

        success_rate = sum(1 for at in strategy_attempts if at.success) / len(
            strategy_attempts
        )

        avg_similarity = sum(
            self._compute_similarity(at.issue_embedding, issue_embedding)
            for at in strategy_attempts
            if at.issue_embedding is not None
        ) / len(strategy_attempts)

        confidence = self._calculate_confidence(
            best_score, avg_similarity, len(strategy_attempts)
        )

        if confidence < min_confidence:
            logger.debug(f"Confidence too low: {confidence:.3f} < {min_confidence}")
            return None

        reasoning = self._generate_reasoning(
            best_strategy_key,
            len(strategy_attempts),
            success_rate,
            avg_similarity,
        )

        return StrategyRecommendation(
            agent_strategy=best_strategy_key,
            confidence=confidence,
            similarity_score=avg_similarity,
            success_rate=success_rate,
            sample_count=len(strategy_attempts),
            alternatives=top_alternatives,
            reasoning=reasoning,
        )

    def _calculate_strategy_scores(
        self,
        attempts: list[FixAttempt],
        query_embedding: np.ndarray,
    ) -> dict[str, float]:
        strategy_scores: dict[str, float] = {}

        for attempt in attempts:
            strategy_key = f"{attempt.agent_used}:{attempt.strategy}"

            if attempt.tfidf_vector is not None:
                weight = self._calculate_tfidf_weight(
                    attempt.tfidf_vector, query_embedding
                )
            elif attempt.issue_embedding is not None:
                weight = self._calculate_similarity_weight(
                    attempt.issue_embedding, query_embedding
                )
            else:
                continue

            boost = attempt.confidence if attempt.confidence > 0 else 0.5
            weighted_score = weight * (1.0 + boost)

            if strategy_key not in strategy_scores:
                strategy_scores[strategy_key] = 0.0

            strategy_scores[strategy_key] += weighted_score

        return strategy_scores

    def _calculate_similarity_weight(
        self,
        stored_embedding: np.ndarray,
        query_embedding: np.ndarray,
    ) -> float:
        similarity = self._compute_similarity(stored_embedding, query_embedding)

        return 1.0 / (1.0 + np.exp(-5 * (similarity - 0.5)))

    def _calculate_tfidf_weight(
        self,
        stored_tfidf: np.ndarray,
        query_tfidf: np.ndarray,
    ) -> float:
        try:
            from sklearn.metrics.pairwise import cosine_similarity

            similarity_matrix = cosine_similarity(query_tfidf, stored_tfidf)
            similarity = float(similarity_matrix[0, 0])

            return 1.0 / (1.0 + np.exp(-5 * (similarity - 0.5)))

        except Exception:
            return 0.0

    def _compute_similarity(
        self,
        embedding_a: np.ndarray,
        embedding_b: np.ndarray,
    ) -> float:
        try:
            norm_a = np.linalg.norm(embedding_a)
            norm_b = np.linalg.norm(embedding_b)

            if 0 in (norm_a, norm_b):
                return 0.0

            return float(np.dot(embedding_a, embedding_b) / (norm_a * norm_b))
        except Exception:
            return 0.0

    def _calculate_confidence(
        self,
        weighted_score: float,
        avg_similarity: float,
        sample_count: int,
    ) -> float:

        normalized_score = min(weighted_score / (self.MIN_SAMPLE_SIZE * 2.0), 1.0)

        sample_boost = min(0.1, np.log(sample_count) * 0.03)

        confidence = (normalized_score * 0.6) + (avg_similarity * 0.3) + sample_boost

        return min(confidence, 1.0)

    def _generate_reasoning(
        self,
        strategy_key: str,
        sample_count: int,
        success_rate: float,
        avg_similarity: float,
    ) -> str:
        agent_name, strategy_name = strategy_key.split(":", 1)

        parts = [
            f"Recommended {agent_name} using {strategy_name} strategy. ",
            f"Based on {sample_count} similar issues with "
            f"{success_rate:.1%} success rate. ",
            f"Average similarity: {avg_similarity:.1%}.",
        ]

        return "".join(parts)

    def track_click_through(
        self,
        recommendation: StrategyRecommendation,
        accepted: bool,
    ) -> None:
        # TODO: Store click-through events in separate table

        logger.debug(
            f"Click-through: {recommendation.agent_strategy} accepted={accepted}"
        )


__all__ = [
    "StrategyRecommender",
    "StrategyRecommendation",
]

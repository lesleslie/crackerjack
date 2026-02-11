"""
Skill Strategy Effectiveness Tracking

Track which skills/agents work best for specific problem contexts.
Enables learning and optimization of skill/agent selection over time.
"""

from __future__ import annotations

import logging
import sqlite3
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

if t.TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SkillAttemptRecord:
    """Record of a skill/agent invocation attempt."""

    skill_name: str
    agent_name: str | None  # If skill invoked agent
    user_query: str
    query_embedding: np.ndarray  # Semantic embedding of query
    context: dict[str, t.Any]  # Phase, time, project, complexity
    success: bool
    confidence: float
    execution_time_ms: int
    alternatives_considered: list[str]  # Other skills/agents that could have been used
    timestamp: datetime

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for storage."""
        return {
            "skill_name": self.skill_name,
            "agent_name": self.agent_name,
            "user_query": self.user_query,
            "query_embedding": self.query_embedding.tolist(),
            "context": self.context,
            "success": self.success,
            "confidence": self.confidence,
            "execution_time_ms": self.execution_time_ms,
            "alternatives_considered": self.alternatives_considered,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> SkillAttemptRecord:
        """Create from dictionary storage."""
        return cls(
            skill_name=data["skill_name"],
            agent_name=data.get("agent_name"),
            user_query=data["user_query"],
            query_embedding=np.array(data["query_embedding"]),
            context=data["context"],
            success=data["success"],
            confidence=data["confidence"],
            execution_time_ms=data["execution_time_ms"],
            alternatives_considered=data["alternatives_considered"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass(frozen=True)
class SkillEffectivenessMetrics:
    """Aggregated metrics for skill effectiveness."""

    skill_name: str
    total_attempts: int
    successful_attempts: int
    success_rate: float
    avg_confidence_when_successful: float
    avg_execution_time_ms: float
    best_contexts: list[dict[str, t.Any]]  # Contexts where this skill excels
    worst_contexts: list[dict[str, t.Any]]  # Contexts where this skill struggles
    last_attempted: datetime | None

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary."""
        return {
            "skill_name": self.skill_name,
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "success_rate": self.success_rate,
            "avg_confidence_when_successful": self.avg_confidence_when_successful,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "best_contexts": self.best_contexts,
            "worst_contexts": self.worst_contexts,
            "last_attempted": self.last_attempted.isoformat()
            if self.last_attempted
            else None,
        }


@t.runtime_checkable
class SkillsEffectivenessProtocol(t.Protocol):
    """Protocol for skills effectiveness tracking."""

    def record_attempt(self, attempt: SkillAttemptRecord) -> None: ...

    def get_effectiveness_metrics(
        self,
        skill_name: str,
        min_sample_size: int = 10,
    ) -> SkillEffectivenessMetrics | None: ...

    def find_effective_skills_for_context(
        self,
        query_embedding: np.ndarray,
        context: dict[str, t.Any],
        limit: int = 5,
    ) -> list[tuple[str, float]]: ...  # [(skill_name, similarity_score)]

    def get_recommended_skill(
        self,
        user_query: str,
        query_embedding: np.ndarray,
        context: dict[str, t.Any],
        candidates: list[str],
    ) -> str | None: ...

    def is_enabled(self) -> bool: ...


@dataclass
class NoOpSkillsEffectivenessTracker:
    """No-op implementation when effectiveness tracking is disabled."""

    backend_name: str = "none"

    def record_attempt(self, attempt: SkillAttemptRecord) -> None:
        logger.debug("No-op effectiveness tracker: skipping record_attempt")

    def get_effectiveness_metrics(
        self,
        skill_name: str,
        min_sample_size: int = 10,
    ) -> SkillEffectivenessMetrics | None:
        return None

    def find_effective_skills_for_context(
        self,
        query_embedding: np.ndarray,
        context: dict[str, t.Any],
        limit: int = 5,
    ) -> list[tuple[str, float]]:
        return []

    def get_recommended_skill(
        self,
        user_query: str,
        query_embedding: np.ndarray,
        context: dict[str, t.Any],
        candidates: list[str],
    ) -> str | None:
        return None

    def is_enabled(self) -> bool:
        return False


@dataclass
class SQLiteSkillsEffectivenessTracker:
    """SQLite-based skills effectiveness tracking."""

    db_path: Path
    min_sample_size: int = 10
    _initialized: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Initialize SQLite database for effectiveness tracking."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Create skills_attempts table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT NOT NULL,
                    agent_name TEXT,
                    user_query TEXT NOT NULL,
                    query_embedding BLOB NOT NULL,
                    context TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    confidence REAL NOT NULL,
                    execution_time_ms INTEGER NOT NULL,
                    alternatives_considered TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )

            # Create indexes for common queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_skill_name
                ON skill_attempts(skill_name)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_success
                ON skill_attempts(success)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON skill_attempts(timestamp DESC)
                """
            )

            conn.commit()
            conn.close()

            self._initialized = True
            logger.info(f"✅ Skills effectiveness tracker initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize skills effectiveness tracker: {e}")
            raise

    def record_attempt(self, attempt: SkillAttemptRecord) -> None:
        """Record a skill attempt for learning."""
        if not self._initialized:
            logger.warning("Skills effectiveness tracker not initialized")
            return

        try:
            import json

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Store embedding as bytes
            embedding_bytes = attempt.query_embedding.tobytes()

            # Store complex types as JSON
            context_json = json.dumps(attempt.context)
            alternatives_json = json.dumps(attempt.alternatives_considered)

            cursor.execute(
                """
                INSERT INTO skill_attempts (
                    skill_name, agent_name, user_query, query_embedding,
                    context, success, confidence, execution_time_ms,
                    alternatives_considered, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.skill_name,
                    attempt.agent_name,
                    attempt.user_query,
                    embedding_bytes,
                    context_json,
                    attempt.success,
                    attempt.confidence,
                    attempt.execution_time_ms,
                    alternatives_json,
                    attempt.timestamp.isoformat(),
                ),
            )

            conn.commit()
            conn.close()

            logger.debug(
                f"Recorded skill attempt: {attempt.skill_name} (success={attempt.success})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to record skill attempt: {e}")

    def get_effectiveness_metrics(
        self,
        skill_name: str,
        min_sample_size: int = 10,
    ) -> SkillEffectivenessMetrics | None:
        """Get effectiveness metrics for a specific skill."""
        if not self._initialized:
            return None

        try:
            import json

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Get all attempts for this skill
            cursor.execute(
                """
                SELECT
                    success, confidence, execution_time_ms,
                    context, timestamp
                FROM skill_attempts
                WHERE skill_name = ?
                ORDER BY timestamp DESC
                """,
                (skill_name,),
            )

            rows = cursor.fetchall()
            conn.close()

            if len(rows) == 0:
                logger.debug(f"No data for {skill_name}")
                return None

            # Note: min_sample_size passed but not enforced here to allow transparency
            # Cross-skill recommendation methods should respect min_sample_size for confidence
            if len(rows) < min_sample_size:
                logger.debug(
                    f"Limited data for {skill_name}: "
                    f"{len(rows)} < {min_sample_size} (returning available metrics)"
                )
                # Continue to calculate metrics anyway
            # Calculate metrics
            successful_rows = [r for r in rows if r[0]]
            total_attempts = len(rows)
            successful_attempts = len(successful_rows)
            success_rate = (
                successful_attempts / total_attempts if total_attempts > 0 else 0.0
            )

            # Average confidence when successful
            avg_confidence = (
                sum(r[1] for r in successful_rows) / len(successful_rows)
                if successful_rows
                else 0.0
            )

            # Average execution time
            avg_execution_time = sum(r[2] for r in rows) / len(rows) if rows else 0.0

            # Find best/worst contexts
            contexts_with_scores = []
            for r in rows:
                context = json.loads(r[3])
                score = 1.0 if r[0] else 0.0  # Binary score
                contexts_with_scores.append((context, score))

            # Sort by score
            contexts_with_scores.sort(key=lambda x: x[1], reverse=True)
            best_contexts = [c[0] for c in contexts_with_scores[:3]]
            worst_contexts = [c[0] for c in contexts_with_scores[-3:]]

            # Last attempted timestamp
            last_attempted = datetime.fromisoformat(rows[0][4]) if rows else None

            return SkillEffectivenessMetrics(
                skill_name=skill_name,
                total_attempts=total_attempts,
                successful_attempts=successful_attempts,
                success_rate=success_rate,
                avg_confidence_when_successful=avg_confidence,
                avg_execution_time_ms=avg_execution_time,
                best_contexts=best_contexts,
                worst_contexts=worst_contexts,
                last_attempted=last_attempted,
            )

        except Exception as e:
            logger.error(f"❌ Failed to get effectiveness metrics: {e}")
            return None

    def find_effective_skills_for_context(
        self,
        query_embedding: np.ndarray,
        context: dict[str, t.Any],
        limit: int = 5,
    ) -> list[tuple[str, float]]:
        """Find skills that have been effective for similar contexts."""
        if not self._initialized:
            return []

        try:
            import json

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Get all successful attempts
            cursor.execute(
                """
                SELECT skill_name, query_embedding, context, success
                FROM skill_attempts
                WHERE success = 1
                ORDER BY timestamp DESC
                LIMIT 1000
                """
            )

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return []

            # Calculate similarity scores
            skill_scores: dict[str, list[float]] = {}

            for row in rows:
                skill_name = row[0]
                stored_embedding_bytes = row[1]
                stored_context = json.loads(row[2])
                row[3]

                # Reconstruct embedding
                stored_embedding = np.frombuffer(
                    stored_embedding_bytes, dtype=np.float64
                )

                # Calculate cosine similarity
                similarity = float(
                    np.dot(query_embedding, stored_embedding)
                    / (
                        np.linalg.norm(query_embedding)
                        * np.linalg.norm(stored_embedding)
                    )
                )

                # Boost score if context matches
                context_match = self._calculate_context_similarity(
                    context, stored_context
                )
                final_score = similarity * (1.0 + context_match * 0.5)

                if skill_name not in skill_scores:
                    skill_scores[skill_name] = []
                skill_scores[skill_name].append(final_score)

            # Aggregate by skill (average similarity)
            avg_scores = [
                (skill, np.mean(scores)) for skill, scores in skill_scores.items()
            ]

            # Sort by score
            avg_scores.sort(key=lambda x: x[1], reverse=True)

            return avg_scores[:limit]

        except Exception as e:
            logger.error(f"❌ Failed to find effective skills: {e}")
            return []

    def get_recommended_skill(
        self,
        user_query: str,
        query_embedding: np.ndarray,
        context: dict[str, t.Any],
        candidates: list[str],
    ) -> str | None:
        """Get recommended skill based on effectiveness metrics."""
        # Find effective skills for this context
        effective_skills = self.find_effective_skills_for_context(
            query_embedding=query_embedding,
            context=context,
            limit=10,
        )

        # Filter to candidates
        candidate_scores = [
            (skill, score) for skill, score in effective_skills if skill in candidates
        ]

        if not candidate_scores:
            return None

        # Return highest-scoring candidate
        return max(candidate_scores, key=lambda x: x[1])[0]

    def _calculate_context_similarity(
        self,
        context1: dict[str, t.Any],
        context2: dict[str, t.Any],
    ) -> float:
        """Calculate similarity between two contexts (0.0 to 1.0)."""
        matches = 0
        total_keys = 0

        for key in set(context1.keys()) | set(context2.keys()):
            total_keys += 1
            if context1.get(key) == context2.get(key):
                matches += 1

        return matches / total_keys if total_keys > 0 else 0.0

    def is_enabled(self) -> bool:
        return self._initialized


def create_skills_effectiveness_tracker(
    enabled: bool = True,
    db_path: Path | None = None,
    min_sample_size: int = 10,
) -> SkillsEffectivenessProtocol:
    """Factory function to create skills effectiveness tracker."""
    if not enabled:
        logger.info("Skills effectiveness tracking is disabled")
        return NoOpSkillsEffectivenessTracker()

    db_path = db_path or Path(".crackerjack/skills_effectiveness.db")

    try:
        return SQLiteSkillsEffectivenessTracker(
            db_path=db_path,
            min_sample_size=min_sample_size,
        )
    except Exception as e:
        logger.error(f"Failed to create skills effectiveness tracker: {e}")
        return NoOpSkillsEffectivenessTracker()


@dataclass
class SkillsEffectivenessIntegration:
    """Integration layer for skills effectiveness tracking."""

    effectiveness_tracker: SkillsEffectivenessProtocol
    min_sample_size: int = 10

    def track_skill_attempt(
        self,
        skill_name: str,
        agent_name: str | None,
        user_query: str,
        query_embedding: np.ndarray,
        context: dict[str, t.Any],
        alternatives_considered: list[str] | None = None,
    ) -> Callable[..., None]:
        """Track a skill attempt and return a completer callback."""

        def completer(
            *,
            success: bool = True,
            confidence: float = 1.0,
            execution_time_ms: int = 0,
        ) -> None:
            attempt = SkillAttemptRecord(
                skill_name=skill_name,
                agent_name=agent_name,
                user_query=user_query,
                query_embedding=query_embedding,
                context=context,
                success=success,
                confidence=confidence,
                execution_time_ms=execution_time_ms,
                alternatives_considered=alternatives_considered or [],
                timestamp=datetime.now(),
            )

            self.effectiveness_tracker.record_attempt(attempt)

        return completer

    def get_skill_boosts(
        self,
        user_query: str,
        query_embedding: np.ndarray,
        context: dict[str, t.Any],
        candidates: list[str],
    ) -> dict[str, float]:
        """Get effectiveness-based boost scores for candidate skills."""
        if not self.effectiveness_tracker.is_enabled():
            return {}

        recommended = self.effectiveness_tracker.get_recommended_skill(
            user_query=user_query,
            query_embedding=query_embedding,
            context=context,
            candidates=candidates,
        )

        if not recommended:
            return {}

        # Provide boost for recommended skill
        boost_factor = 0.2  # 20% boost
        return {recommended: boost_factor}

    def get_skill_metrics(
        self,
        skill_name: str,
    ) -> SkillEffectivenessMetrics | None:
        """Get effectiveness metrics for a skill."""
        return self.effectiveness_tracker.get_effectiveness_metrics(
            skill_name=skill_name,
            min_sample_size=self.min_sample_size,
        )


__all__ = [
    "SkillsEffectivenessProtocol",
    "NoOpSkillsEffectivenessTracker",
    "SQLiteSkillsEffectivenessTracker",
    "SkillsEffectivenessIntegration",
    "SkillEffectivenessMetrics",
    "SkillAttemptRecord",
    "create_skills_effectiveness_tracker",
]

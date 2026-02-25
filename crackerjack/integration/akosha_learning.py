from __future__ import annotations

import json
import logging
import sqlite3
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

if t.TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryInteractionRecord:
    query: str
    query_embedding: list[float]
    results_returned: list[str]
    results_clicked: list[str]
    results_skipped: list[str]
    user_satisfaction: float
    outcome: t.Literal["success", "partial", "failure"]
    timestamp: datetime
    session_id: str | None = None

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "query": self.query,
            "query_embedding": self.query_embedding,
            "results_returned": self.results_returned,
            "results_clicked": self.results_clicked,
            "results_skipped": self.results_skipped,
            "user_satisfaction": self.user_satisfaction,
            "outcome": self.outcome,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> QueryInteractionRecord:
        return cls(
            query=data["query"],
            query_embedding=data["query_embedding"],
            results_returned=data["results_returned"],
            results_clicked=data["results_clicked"],
            results_skipped=data["results_skipped"],
            user_satisfaction=data["user_satisfaction"],
            outcome=data["outcome"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_id=data.get("session_id"),
        )


@dataclass(frozen=True)
class QuerySuggestion:
    original_query: str
    suggested_query: str
    confidence: float
    expected_improvement: float
    reason: str


@t.runtime_checkable
class QueryOptimizerProtocol(t.Protocol):
    def track_search_interaction(
        self,
        query: str,
        results_clicked: list[str],
        results_skipped: list[str],
        user_satisfaction: float,
        outcome: t.Literal["success", "partial", "failure"],
        session_id: str | None = None,
    ) -> None: ...

    def get_query_suggestions(
        self,
        partial_query: str,
        similar_queries: list[str],
    ) -> list[QuerySuggestion]: ...

    def adapt_ranking(
        self,
        query: str,
        candidate_results: list[dict],
    ) -> list[dict]: ...

    def get_click_through_rate(self, query: str) -> float: ...

    def is_enabled(self) -> bool: ...


@dataclass
class NoOpQueryOptimizer:
    backend_name: str = "none"

    def track_search_interaction(
        self,
        query: str,
        results_clicked: list[str],
        results_skipped: list[str],
        user_satisfaction: float,
        outcome: t.Literal["success", "partial", "failure"],
        session_id: str | None = None,
    ) -> None:
        logger.debug("No-op query optimizer: skipping track_search_interaction")

    def get_query_suggestions(
        self,
        partial_query: str,
        similar_queries: list[str],
    ) -> list[QuerySuggestion]:
        return []

    def adapt_ranking(
        self,
        query: str,
        candidate_results: list[dict],
    ) -> list[dict]:
        return candidate_results

    def get_click_through_rate(self, query: str) -> float:
        return 0.0

    def is_enabled(self) -> bool:
        return False


@dataclass
class SQLiteQueryOptimizer:
    db_path: Path
    min_interactions: int = 5
    _initialized: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self._initialize_db()

    def _initialize_db(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS query_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    results_returned TEXT NOT NULL,
                    results_clicked TEXT NOT NULL,
                    results_skipped TEXT NOT NULL,
                    user_satisfaction REAL NOT NULL,
                    outcome TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    session_id TEXT
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS query_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_pattern TEXT NOT NULL UNIQUE,
                    success_count INTEGER DEFAULT 0,
                    total_count INTEGER DEFAULT 1,
                    avg_satisfaction REAL DEFAULT 0.0,
                    last_updated TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_query
                ON query_interactions(query)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_outcome
                ON query_interactions(outcome)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON query_interactions(timestamp DESC)
                """
            )

            conn.commit()
            conn.close()

            self._initialized = True
            logger.info(f"✅ Query optimizer initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize query optimizer: {e}")
            raise

    def track_search_interaction(
        self,
        query: str,
        results_clicked: list[str],
        results_skipped: list[str],
        user_satisfaction: float,
        outcome: t.Literal["success", "partial", "failure"],
        session_id: str | None = None,
    ) -> None:
        if not self._initialized:
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO query_interactions (
                    query, results_returned, results_clicked, results_skipped,
                    user_satisfaction, outcome, timestamp, session_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query,
                    json.dumps(results_clicked + results_skipped),
                    json.dumps(results_clicked),
                    json.dumps(results_skipped),
                    user_satisfaction,
                    outcome,
                    datetime.now().isoformat(),
                    session_id,
                ),
            )

            self._update_query_pattern(cursor, query, outcome, user_satisfaction)

            conn.commit()
            conn.close()

            logger.debug(
                f"Recorded query interaction: {query[:50]}... "
                f"(outcome={outcome}, satisfaction={user_satisfaction:.2f})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to track search interaction: {e}")

    def _update_query_pattern(
        self,
        cursor: sqlite3.Cursor,
        query: str,
        outcome: t.Literal["success", "partial", "failure"],
        satisfaction: float,
    ) -> None:

        pattern = " ".join(query.lower().split())

        cursor.execute(
            """
            INSERT OR IGNORE INTO query_patterns (
                query_pattern, success_count, total_count,
                avg_satisfaction, last_updated
            ) VALUES (?, 0, 1, 0.0, ?)
            """,
            (pattern, datetime.now().isoformat()),
        )

        if outcome == "success":
            cursor.execute(
                """
                UPDATE query_patterns
                SET success_count = success_count + 1,
                    total_count = total_count + 1,
                    avg_satisfaction = (avg_satisfaction * (total_count - 1) + ?) / total_count,
                    last_updated = ?
                WHERE query_pattern = ?
                """,
                (satisfaction, datetime.now().isoformat(), pattern),
            )
        else:
            cursor.execute(
                """
                UPDATE query_patterns
                SET total_count = total_count + 1,
                    avg_satisfaction = (avg_satisfaction * (total_count - 1) + ?) / total_count,
                    last_updated = ?
                WHERE query_pattern = ?
                """,
                (satisfaction, datetime.now().isoformat(), pattern),
            )

    def get_query_suggestions(
        self,
        partial_query: str,
        similar_queries: list[str],
    ) -> list[QuerySuggestion]:
        if not self._initialized:
            return []

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            suggestions = []

            for similar_query in similar_queries:
                pattern = " ".join(similar_query.lower().split())

                cursor.execute(
                    """
                    SELECT success_count, total_count, avg_satisfaction
                    FROM query_patterns
                    WHERE query_pattern LIKE ?
                    AND total_count >= ?
                    ORDER BY avg_satisfaction DESC
                    LIMIT 1
                    """,
                    (f"%{pattern}%", self.min_interactions),
                )

                row = cursor.fetchone()
                if row:
                    success_count, total_count, avg_satisfaction = row
                    success_rate = success_count / total_count if total_count > 0 else 0

                    if success_rate > 0.7 and avg_satisfaction > 0.7:
                        suggestions.append(
                            QuerySuggestion(
                                original_query=partial_query,
                                suggested_query=similar_query,
                                confidence=success_rate,
                                expected_improvement=avg_satisfaction,
                                reason=f"Similar query has {success_rate:.0%} success rate",
                            )
                        )

            conn.close()
            return suggestions[:5]

        except Exception as e:
            logger.error(f"❌ Failed to get query suggestions: {e}")
            return []

    def adapt_ranking(
        self,
        query: str,
        candidate_results: list[dict],
    ) -> list[dict]:
        if not self._initialized:
            return candidate_results

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            pattern = " ".join(query.lower().split())

            cursor.execute(
                """
                SELECT results_clicked, results_returned
                FROM query_interactions
                WHERE query LIKE ?
                ORDER BY timestamp DESC
                LIMIT 50
                """,
                (f"%{pattern}%",),
            )

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return candidate_results

            click_counts: dict[str, int] = {}
            total_shown: dict[str, int] = {}

            for row in rows:
                clicked = json.loads(row[0])
                returned = json.loads(row[1])

                for result_id in returned:
                    total_shown[result_id] = total_shown.get(result_id, 0) + 1

                for result_id in clicked:
                    click_counts[result_id] = click_counts.get(result_id, 0) + 1

            ctr_scores = {}
            for result_id in total_shown:
                ctr_scores[result_id] = (
                    click_counts.get(result_id, 0) / total_shown[result_id]
                )

            ranked_results = []
            for result in candidate_results:
                result_id = result.get("id", "")
                boost = ctr_scores.get(result_id, 0.0)

                original_score = result.get("score", 0.0)
                boosted_score = original_score * (1.0 + boost * 0.5)

                result_copy = result.copy()
                result_copy["score"] = boosted_score
                result_copy["original_score"] = original_score
                result_copy["ctr_boost"] = boost

                ranked_results.append(result_copy)

            ranked_results.sort(key=operator.itemgetter("score"), reverse=True)

            return ranked_results

        except Exception as e:
            logger.error(f"❌ Failed to adapt ranking: {e}")
            return candidate_results

    def get_click_through_rate(self, query: str) -> float:
        if not self._initialized:
            return 0.0

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            pattern = " ".join(query.lower().split())

            cursor.execute(
                """
                SELECT results_clicked, results_returned
                FROM query_interactions
                WHERE query LIKE ?
                ORDER BY timestamp DESC
                LIMIT 50
                """,
                (f"%{pattern}%",),
            )

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return 0.0

            total_clicked = 0
            total_shown = 0

            for row in rows:
                clicked = len(json.loads(row[0]))
                returned = len(json.loads(row[1]))

                total_clicked += clicked
                total_shown += returned

            return total_clicked / total_shown if total_shown > 0 else 0.0

        except Exception as e:
            logger.error(f"❌ Failed to get click-through rate: {e}")
            return 0.0

    def is_enabled(self) -> bool:
        return self._initialized


def create_query_optimizer(
    enabled: bool = True,
    db_path: Path | None = None,
    min_interactions: int = 5,
) -> QueryOptimizerProtocol:
    if not enabled:
        logger.info("Query optimization learning is disabled")
        return NoOpQueryOptimizer()

    db_path = db_path or Path(".crackerjack/query_learning.db")

    try:
        return SQLiteQueryOptimizer(
            db_path=db_path,
            min_interactions=min_interactions,
        )
    except Exception as e:
        logger.error(f"Failed to create query optimizer: {e}")
        return NoOpQueryOptimizer()


@dataclass
class AkoshaLearningIntegration:
    query_optimizer: QueryOptimizerProtocol
    session_id: str | None = None

    def track_search_results(
        self,
        query: str,
        results: list[dict],
    ) -> Callable[..., None]:

        def completer(
            *,
            results_clicked: list[str] | None = None,
            user_satisfaction: float = 0.8,
            outcome: t.Literal["success", "partial", "failure"] = "partial",
        ) -> None:
            results_clicked = results_clicked or []
            results_returned = [r.get("id", "") for r in results]
            results_skipped = [r for r in results_returned if r not in results_clicked]

            self.query_optimizer.track_search_interaction(
                query=query,
                results_clicked=results_clicked,
                results_skipped=results_skipped,
                user_satisfaction=user_satisfaction,
                outcome=outcome,
                session_id=self.session_id,
            )

        return completer

    def enhance_search_results(
        self,
        query: str,
        results: list[dict],
    ) -> list[dict]:
        return self.query_optimizer.adapt_ranking(query, results)

    def get_query_improvements(
        self,
        partial_query: str,
        similar_queries: list[str],
    ) -> list[QuerySuggestion]:
        return self.query_optimizer.get_query_suggestions(
            partial_query=partial_query,
            similar_queries=similar_queries,
        )

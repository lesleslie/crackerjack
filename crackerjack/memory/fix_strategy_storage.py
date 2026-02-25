import logging
import sqlite3
import threading
import typing as t
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from crackerjack.agents.base import FixResult, Issue

logger = logging.getLogger(__name__)


_thread_local = threading.local()


@dataclass
class FixAttempt:
    issue_type: str
    issue_message: str
    file_path: str | None
    stage: str
    issue_embedding: np.ndarray | None
    tfidf_vector: np.ndarray | None
    agent_used: str
    strategy: str
    success: bool
    confidence: float
    timestamp: str
    session_id: str | None


class FixStrategyStorage:
    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(_thread_local, "conn") or _thread_local.conn is None:
            _thread_local.conn = sqlite3.connect(str(self.db_path))
            _thread_local.conn.row_factory = sqlite3.Row
        return _thread_local.conn

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

        self._initialize_db()

    def _initialize_db(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            _thread_local.conn = conn

            schema_path = Path(__file__).parent / "fix_strategy_schema.sql"
            if schema_path.exists():
                schema_sql = schema_path.read_text(encoding="utf-8")
                conn.executescript(schema_sql)
                conn.commit()  # type: ignore
                logger.info(f"✅ Fix strategy memory initialized: {self.db_path}")
            else:
                logger.warning(f"Schema file not found: {schema_path}")
                self._create_fallback_schema()
        except Exception as e:
            logger.error(f"❌ Failed to initialize fix strategy database: {e}")
            raise

    def _create_fallback_schema(self) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS fix_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_type TEXT NOT NULL,
                issue_message TEXT NOT NULL,
                file_path TEXT,
                stage TEXT,
                issue_embedding BLOB NOT NULL,
                tfidf_vector BLOB,
                agent_used TEXT NOT NULL,
                strategy TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                confidence REAL,
                timestamp TEXT NOT NULL,
                session_id TEXT
            )
        """)
        conn.commit()  # type: ignore

    def record_attempt(
        self,
        issue: Issue,
        result: FixResult,
        agent_used: str,
        strategy: str,
        issue_embedding: np.ndarray,
        session_id: str | None = None,
    ) -> None:
        if self.conn is None:
            logger.warning("Database connection not initialized")
            return
        try:
            timestamp = datetime.now().isoformat()

            from io import BytesIO

            from scipy import sparse as sp
            from scipy.sparse import issparse

            is_tfidf = issparse(issue_embedding) and issue_embedding.shape[1] == 100
            if is_tfidf:
                from scipy import sparse as sp

                buffer = BytesIO()
                sp.save_npz(buffer, arr_0=issue_embedding)  # type: ignore
                tfidf_bytes = buffer.getvalue()
                embedding_bytes = b"\x00" * 1536
                logger.debug(
                    f"Recording TF-IDF embedding (shape={issue_embedding.shape})"
                )
            else:
                embedding_bytes = issue_embedding.astype(np.float32).tobytes()
                tfidf_bytes = None
                logger.debug(
                    f"Recording neural embedding (shape={issue_embedding.shape})"
                )

            insert_sql = """
                INSERT INTO fix_attempts
                (issue_type, issue_message, file_path, stage, issue_embedding,
                 tfidf_vector, agent_used, strategy, success, confidence,
                 timestamp, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            self.conn.execute(
                insert_sql,
                (
                    issue.type.value,
                    issue.message,
                    issue.file_path,
                    issue.stage,
                    embedding_bytes,
                    tfidf_bytes,
                    agent_used,
                    strategy,
                    result.success,
                    result.confidence,
                    timestamp,
                    session_id,
                ),
            )
            self.conn.commit()
            logger.debug(
                f"Recorded fix attempt: {agent_used}:{strategy} "
                f"(success={result.success}, confidence={result.confidence:.2f})"
            )
        except Exception as e:
            logger.error(f"Failed to record fix attempt: {e}")

    def find_similar_issues(
        self,
        issue_embedding: np.ndarray,
        issue_type: str | None = None,
        k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[FixAttempt]:
        if self.conn is None:
            return []

        try:
            query = "SELECT * FROM fix_attempts"
            params: list[t.Any] = []

            if issue_type:
                query += " WHERE issue_type = ?"
                params.append(issue_type)

            cursor = self.conn.execute(query, params)
            rows = cursor.fetchall()

            if not rows:
                logger.debug("No historical issues found")
                return []

            similar_issues: list[tuple[float, FixAttempt]] = []

            for row in rows:
                tfidf_blob = row["tfidf_vector"]
                issue_blob = row["issue_embedding"]

                if tfidf_blob is not None:
                    from io import BytesIO

                    from scipy import sparse as sp

                    stored = sp.load_npz(BytesIO(tfidf_blob))["arr_0"]
                    similarity_matrix = cosine_similarity(issue_embedding, stored)
                    similarity = float(similarity_matrix[0, 0])
                else:
                    stored = np.frombuffer(issue_blob, dtype=np.float32)
                    similarity = self._cosine_similarity(issue_embedding, stored)

                if similarity >= min_similarity:
                    tfidf_blob = row["tfidf_vector"]
                    issue_blob = row["issue_embedding"]

                    if tfidf_blob is not None:
                        from io import BytesIO

                        from scipy import sparse as sp

                        attempt = FixAttempt(
                            issue_type=row["issue_type"],
                            issue_message=row["issue_message"],
                            file_path=row["file_path"],
                            stage=row["stage"],
                            issue_embedding=None,
                            tfidf_vector=stored_tfidf,
                            agent_used=row["agent_used"],
                            strategy=row["strategy"],
                            success=bool(row["success"]),
                            confidence=row["confidence"] or 0.0,
                            timestamp=row["timestamp"],
                            session_id=row["session_id"],
                        )
                    else:
                        stored_neural = np.frombuffer(issue_blob, dtype=np.float32)
                        attempt = FixAttempt(
                            issue_type=row["issue_type"],
                            issue_message=row["issue_message"],
                            file_path=row["file_path"],
                            stage=row["stage"],
                            issue_embedding=stored_neural,
                            tfidf_vector=None,
                            agent_used=row["agent_used"],
                            strategy=row["strategy"],
                            success=bool(row["success"]),
                            confidence=row["confidence"] or 0.0,
                            timestamp=row["timestamp"],
                            session_id=row["session_id"],
                        )

                similar_issues.append((similarity, attempt))

            similar_issues.sort(key=operator.itemgetter(0), reverse=True)  # type: ignore

            top_k = similar_issues[:k]

            if top_k:
                logger.debug(
                    f"Found {len(top_k)} similar issues "
                    f"(similarity: {top_k[0][0]:.3f}...)"
                )
            else:
                logger.debug("No similar issues found above threshold")
            return [attempt for _, attempt in top_k]

        except Exception as e:
            logger.error(f"Failed to find similar issues: {e}")
            return []

    def get_strategy_recommendation(
        self,
        issue: Issue,
        issue_embedding: np.ndarray,
        k: int = 10,
    ) -> tuple[str, float] | None:
        similar_issues = self.find_similar_issues(
            issue_embedding=issue_embedding,
            issue_type=issue.type.value,
            k=k,
        )

        successful_attempts = [
            attempt
            for _, attempt in similar_issues  # type: ignore
            if attempt.success  # type: ignore[untyped]
        ]

        if not successful_attempts:
            logger.debug("No successful similar attempts found for recommendation")
            return None

        strategy_scores: dict[str, float] = {}
        strategy_counts: dict[str, int] = {}

        for attempt in successful_attempts:
            strategy_key = f"{attempt.agent_used}:{attempt.strategy}"
            if attempt.tfidf_vector is not None:
                weight = self._calculate_similarity_weight_tfidf(
                    attempt.tfidf_vector, issue_embedding
                )
            else:
                weight = self._calculate_similarity_weight(
                    attempt.issue_embedding, issue_embedding
                )

            if strategy_key not in strategy_scores:
                strategy_scores[strategy_key] = 0.0
                strategy_counts[strategy_key] = 0

            strategy_scores[strategy_key] += weight * attempt.confidence
            strategy_counts[strategy_key] += 1

        if not strategy_scores:
            return None

        best_strategy = max(strategy_scores, key=strategy_scores.get)
        count = strategy_counts[best_strategy]
        base_confidence = strategy_scores[best_strategy] / count
        confidence_boost = min(0.1, count * 0.02)
        final_confidence = min(base_confidence + confidence_boost, 1.0)

        logger.info(
            f"Strategy recommendation: {best_strategy} "
            f"(confidence={final_confidence:.3f}, based on {count} attempts)"
        )
        return best_strategy, final_confidence

    def update_strategy_effectiveness(self) -> None:
        if self.conn is None:
            return
        try:
            self.conn.execute("DELETE FROM strategy_effectiveness")
            rebuild_sql = """
                INSERT OR REPLACE INTO strategy_effectiveness
                (agent_strategy, total_attempts, successful_attempts,
                 success_rate, last_attempted, last_successful)
                SELECT
                    agent_strategy,
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END)
                        as successful_attempts,
                    CAST(SUM(CASE WHEN success THEN 1 ELSE 0 END) AS REAL) / COUNT(*) as success_rate,
                    MAX(timestamp) as last_attempted,
                    MAX(CASE WHEN success THEN timestamp END)
                        as last_successful
                FROM fix_attempts
                GROUP BY agent_strategy
            """
            self.conn.execute(rebuild_sql)
            self.conn.commit()
            logger.info("Strategy effectiveness statistics updated")
        except Exception as e:
            logger.error(f"Failed to update strategy effectiveness: {e}")

    def get_statistics(self) -> dict[str, t.Any]:
        if self.conn is None:
            return {}
        try:
            stats_sql = """
                SELECT
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END)
                        as successful_attempts,
                    CAST(SUM(CASE WHEN success THEN 1 ELSE 0 END) AS REAL) / COUNT(*) as success_rate,
                    MAX(timestamp) as last_attempted,
                    MAX(CASE WHEN success THEN timestamp END)
                        as last_successful
                FROM fix_attempts
            """
            cursor = self.conn.execute(stats_sql)
            row = cursor.fetchone()

            strategies_sql = """
                SELECT agent_strategy, success_rate, total_attempts
                FROM strategy_effectiveness
                WHERE total_attempts >= 1
                ORDER BY success_rate DESC, total_attempts DESC
                LIMIT 10
            """
            cursor = self.conn.execute(strategies_sql)
            top_strategies = cursor.fetchall()

            return {
                "total_attempts": row["total_attempts"] if row else 0,
                "successful_attempts": row["successful_attempts"] if row else 0,
                "overall_success_rate": row["success_rate"] if row else 0.0,
                "last_attempted": row["last_attempted"] if row else "",
                "last_successful": row["last_successful"] if row else "",
                "top_strategies": top_strategies,
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        try:
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if 0 in (norm_a, norm_b):
                return 0.0
            return dot_product / (norm_a * norm_b)
        except Exception:
            return 0.0

    @staticmethod
    def _calculate_similarity_weight(
        stored_embedding: np.ndarray,
        query_embedding: np.ndarray,
    ) -> float:
        try:
            from sklearn.metrics.pairwise import cosine_similarity

            similarity_matrix = cosine_similarity(query_embedding, stored_embedding)
            similarity = float(similarity_matrix[0, 0])
            return 1.0 / (1.0 + np.exp(-5 * (similarity - 0.5)))
        except Exception:
            return 0.0

    @staticmethod
    def _calculate_similarity_weight_tfidf(
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

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Fix strategy storage closed")

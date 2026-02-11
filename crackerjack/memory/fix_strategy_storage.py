"""Storage for fix strategy memory with neural pattern matching.

This module provides persistent storage and retrieval of fix attempts,
using semantic similarity to recommend successful strategies.
"""

import logging
import sqlite3
import typing as t
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

from crackerjack.agents.base import FixResult, Issue

logger = logging.getLogger(__name__)


@dataclass
class FixAttempt:
    """Record of a fix attempt for learning."""
    issue_type: str
    issue_message: str
    file_path: str | None
    stage: str
    issue_embedding: np.ndarray | None  # Can be neural (384-dim) or TF-IDF (sparse)
    tfidf_vector: np.ndarray | None  # TF-IDF sparse matrix (fallback)
    agent_used: str
    strategy: str
    success: bool
    confidence: float
    timestamp: str
    session_id: str | None


class FixStrategyStorage:
    """Persistent storage for fix strategy memory.

    Provides:
    - Recording of fix attempts
    - Finding similar historical issues via cosine similarity
    - Recommending strategies based on past success
    - Strategy effectiveness tracking
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize storage with database path.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Create database schema if not exists."""
        try:
            # Ensure parent directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row  # Enable dict-like access

            # Load and execute schema
            schema_path = Path(__file__).parent / "fix_strategy_schema.sql"
            if schema_path.exists():
                schema_sql = schema_path.read_text(encoding="utf-8")
                self.conn.executescript(schema_sql)
                self.conn.commit()
                logger.info(f"✅ Fix strategy memory initialized: {self.db_path}")
            else:
                logger.warning(f"Schema file not found: {schema_path}")
                # Fallback: create basic table
                self._create_fallback_schema()

        except Exception as e:
            logger.error(f"❌ Failed to initialize fix strategy database: {e}")
            raise

    def _create_fallback_schema(self) -> None:
        """Create basic schema if SQL file not found."""
        self.conn.execute("""
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
        self.conn.commit()

    def record_attempt(
        self,
        issue: Issue,
        result: FixResult,
        agent_used: str,
        strategy: str,
        issue_embedding: np.ndarray,
        session_id: str | None = None,
    ) -> None:
        """Record a fix attempt for future learning.

        Args:
            issue: The issue that was fixed
            result: Result of fix attempt
            agent_used: Name of agent that attempted fix
            strategy: Strategy used by agent
            issue_embedding: Dense (384-dim) or sparse TF-IDF embedding
            session_id: Optional session identifier
        """
        if self.conn is None:
            logger.warning("Database connection not initialized")
            return

        try:
            timestamp = datetime.now().isoformat()

            # Detect embedding type (TF-IDF sparse vs neural dense)
            from io import BytesIO

            from scipy.sparse import issparse

            is_tfidf = issparse(issue_embedding) and issue_embedding.shape[1] == 100

            if is_tfidf:
                # TF-IDF fallback: sparse matrix (max_features=100)
                from scipy import sparse as sp
                buffer = BytesIO()
                sp.save_npz(buffer, arr_0=issue_embedding)
                tfidf_bytes = buffer.getvalue()
                # Use zero bytes for neural column (TF-IDF mode)
                embedding_bytes = b"\x00" * 1536  # 384 * 4 bytes placeholder
                logger.debug(
                    f"Recording TF-IDF embedding (shape={issue_embedding.shape})"
                )
            else:
                # Neural embedding: dense vector (384-dim)
                embedding_bytes = issue_embedding.astype(np.float32).tobytes()
                tfidf_bytes = None  # No TF-IDF vector (neural mode)
                logger.debug(
                    f"Recording neural embedding (shape={issue_embedding.shape})"
                )

            # Build INSERT statement
            insert_sql = """
                INSERT INTO fix_attempts
                (issue_type, issue_message, file_path, stage, issue_embedding,
                 tfidf_vector, agent_used, strategy, success, confidence,
                 timestamp, session_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        """Find k most similar historical issues using cosine similarity.

        Args:
            issue_embedding: Query issue embedding (384-dim)
            issue_type: Optional filter by issue type
            k: Number of results to return
            min_similarity: Minimum cosine similarity threshold (0-1)

        Returns:
            List[FixAttempt]: Most similar historical attempts
        """
        if self.conn is None:
            return []

        try:
            # Fetch all candidate embeddings
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

            # Calculate similarities
            similar_issues: list[tuple[float, FixAttempt]] = []

            for row in rows:
                # Check if we have TF-IDF vector (fallback embedder)
                tfidf_blob = row["tfidf_vector"]
                issue_blob = row["issue_embedding"]

                if tfidf_blob is not None:
                    # TF-IDF fallback: decompress sparse matrix
                    from io import BytesIO

                    from scipy import sparse as sp

                    stored = sp.load_npz(BytesIO(tfidf_blob))["arr_0"]
                    # Use sklearn cosine similarity for sparse matrices
                    from sklearn.metrics.pairwise import cosine_similarity

                    similarity_matrix = cosine_similarity(
                        issue_embedding, stored
                    )
                    similarity = float(similarity_matrix[0, 0])
                else:
                    # Neural embedding: unpack dense vector from BLOB
                    stored = np.frombuffer(issue_blob, dtype=np.float32)
                    # Calculate cosine similarity for dense vectors
                    similarity = self._cosine_similarity(issue_embedding, stored)

                if similarity >= min_similarity:
                    # Determine which embedding type we have
                    tfidf_blob = row["tfidf_vector"]
                    issue_blob = row["issue_embedding"]

                    if tfidf_blob is not None:
                        # TF-IDF embedding
                        from io import BytesIO

                        from scipy import sparse as sp
                        stored_tfidf = sp.load_npz(BytesIO(tfidf_blob))['arr_0']
                        attempt = FixAttempt(
                            issue_type=row["issue_type"],
                            issue_message=row["issue_message"],
                            file_path=row["file_path"],
                            stage=row["stage"],
                            issue_embedding=None,  # TF-IDF mode
                            tfidf_vector=stored_tfidf,
                            agent_used=row["agent_used"],
                            strategy=row["strategy"],
                            success=bool(row["success"]),
                            confidence=row["confidence"] or 0.0,
                            timestamp=row["timestamp"],
                            session_id=row["session_id"],
                        )
                    else:
                        # Neural embedding
                        stored_neural = np.frombuffer(issue_blob, dtype=np.float32)
                        attempt = FixAttempt(
                            issue_type=row["issue_type"],
                            issue_message=row["issue_message"],
                            file_path=row["file_path"],
                            stage=row["stage"],
                            issue_embedding=stored_neural,
                            tfidf_vector=None,  # Neural mode
                            agent_used=row["agent_used"],
                            strategy=row["strategy"],
                            success=bool(row["success"]),
                            confidence=row["confidence"] or 0.0,
                            timestamp=row["timestamp"],
                            session_id=row["session_id"],
                        )
                    similar_issues.append((similarity, attempt))

            # Sort by similarity (descending) and return top k
            similar_issues.sort(key=lambda x: x[0], reverse=True)
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
        """Recommend best strategy for this issue based on history.

        Finds similar successful attempts and recommends the strategy
        with highest weighted success rate.

        Args:
            issue: Current issue to fix
            issue_embedding: Query embedding
            k: Number of similar issues to consider

        Returns:
            Tuple of (agent_strategy, confidence) or None if no recommendation
        """
        similar_issues = self.find_similar_issues(
            issue_embedding=issue_embedding,
            issue_type=issue.type.value,
            k=k,
        )

        # Filter only successful attempts
        successful_attempts = [
            attempt
            for attempt in similar_issues
            if attempt.success
        ]

        if not successful_attempts:
            logger.debug("No successful similar attempts found for recommendation")
            return None

        # Group by agent:strategy and calculate weighted scores
        strategy_scores: dict[str, float] = {}
        strategy_counts: dict[str, int] = {}

        for attempt in successful_attempts:
            strategy_key = f"{attempt.agent_used}:{attempt.strategy}"

            # Handle both neural and TF-IDF embeddings
            if attempt.tfidf_vector is not None:
                # TF-IDF mode: use sparse matrix similarity
                weight = self._calculate_similarity_weight_tfidf(
                    attempt.tfidf_vector, issue_embedding
                )
            else:
                # Neural mode: use dense vector similarity
                weight = self._calculate_similarity_weight(
                    attempt.issue_embedding, issue_embedding
                )

            # Accumulate weighted scores
            if strategy_key not in strategy_scores:
                strategy_scores[strategy_key] = 0.0
                strategy_counts[strategy_key] = 0

            strategy_scores[strategy_key] += weight * attempt.confidence
            strategy_counts[strategy_key] += 1

        # Find best strategy
        if not strategy_scores:
            return None

        best_strategy = max(strategy_scores, key=strategy_scores.get)

        # Normalize confidence by count (more attempts = higher confidence)
        count = strategy_counts[best_strategy]
        base_confidence = strategy_scores[best_strategy] / count

        # Boost confidence if we have multiple data points
        confidence_boost = min(0.1, count * 0.02)
        final_confidence = min(base_confidence + confidence_boost, 1.0)

        logger.info(
            f"Strategy recommendation: {best_strategy} "
            f"(confidence={final_confidence:.3f}, based on {count} attempts)"
        )

        return best_strategy, final_confidence

    def update_strategy_effectiveness(self) -> None:
        """Recalculate strategy effectiveness summaries.

        This is typically handled by the trigger, but can be
        called manually to rebuild statistics.
        """
        if self.conn is None:
            return

        try:
            # Clear existing effectiveness data
            self.conn.execute("DELETE FROM strategy_effectiveness")

            # Rebuild from fix_attempts
            rebuild_sql = """
                INSERT OR REPLACE INTO strategy_effectiveness
                (agent_strategy, total_attempts, successful_attempts,
                 success_rate, last_attempted, last_successful)
                SELECT
                    agent_strategy,
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END)
                        as successful_attempts,
                    CAST(SUM(CASE WHEN success THEN 1 ELSE 0 END)
                        AS REAL) / COUNT(*) as success_rate,
                    MAX(timestamp) as last_attempted,
                    MAX(CASE WHEN success THEN timestamp END)
                        as last_successful
                FROM (
                    SELECT agent_used || ':' || strategy as agent_strategy, *
                    FROM fix_attempts
                )
                GROUP BY agent_strategy
            """

            self.conn.execute(rebuild_sql)
            self.conn.commit()

            logger.info("Strategy effectiveness statistics updated")

        except Exception as e:
            logger.error(f"Failed to update strategy effectiveness: {e}")

    def get_statistics(self) -> dict[str, t.Any]:
        """Get overall statistics about fix strategy memory.

        Returns:
            Dict with stats: total_attempts, success_rate, top_strategies
        """
        if self.conn is None:
            return {}

        try:
            # Overall stats query
            stats_sql = """
                SELECT
                    COUNT(*) as total_attempts,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END)
                        as successful_attempts,
                    CAST(SUM(CASE WHEN success THEN 1 ELSE 0 END)
                        AS REAL) / COUNT(*) as success_rate
                FROM fix_attempts
            """

            cursor = self.conn.execute(stats_sql)
            row = cursor.fetchone()

            # Top strategies query (require >=1 attempt per strategy)
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
                "top_strategies": top_strategies,
            }

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            a: First vector
            b: Second vector

        Returns:
            float: Cosine similarity (0 to 1, where 1 is identical)
        """
        try:
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            return dot_product / (norm_a * norm_b)

        except Exception:
            return 0.0

    @staticmethod
    def _calculate_similarity_weight(
        stored_embedding: np.ndarray,
        query_embedding: np.ndarray,
    ) -> float:
        """Calculate weight for similarity-based voting.

        Args:
            stored_embedding: Historical issue embedding
            query_embedding: Current issue embedding

        Returns:
            float: Weight between 0 and 1 (closer = higher weight)
        """
        # Calculate cosine similarity
        similarity = FixStrategyStorage._cosine_similarity(
            stored_embedding, query_embedding
        )

        # Use sigmoid-like function to smooth weights
        # similarity=1.0 -> weight=1.0
        # similarity=0.5 -> weight=0.73
        # similarity=0.3 -> weight=0.5
        return 1.0 / (1.0 + np.exp(-5 * (similarity - 0.5)))

    @staticmethod
    def _calculate_similarity_weight_tfidf(
        stored_tfidf: np.ndarray,
        query_tfidf: np.ndarray,
    ) -> float:
        """Calculate weight for TF-IDF similarity.

        Args:
            stored_tfidf: Historical issue TF-IDF vector (sparse)
            query_tfidf: Current issue TF-IDF vector (sparse)

        Returns:
            float: Weight between 0 and 1
        """
        try:
            from sklearn.metrics.pairwise import cosine_similarity

            # Cosine similarity for sparse matrices
            similarity_matrix = cosine_similarity(query_tfidf, stored_tfidf)
            similarity = float(similarity_matrix[0, 0])

            # Sigmoid-like function to smooth weights
            # similarity=1.0 -> weight=1.0
            # similarity=0.5 -> weight=0.73
            # similarity=0.3 -> weight=0.5
            return 1.0 / (1.0 + np.exp(-5 * (similarity - 0.5)))

        except Exception:
            return 0.0

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Fix strategy storage closed")

    def __enter__(self) -> "FixStrategyStorage":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

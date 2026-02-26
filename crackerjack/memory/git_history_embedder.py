from __future__ import annotations

import logging
import operator
import sqlite3
import threading
import typing as t
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


_thread_local = threading.local()


@dataclass
class GitHistoryEmbedder:
    path: str
    timestamp: datetime
    embedding: np.ndarray | None = None

    def __init__(
        self,
        db_path: Path,
        embedding_model: str | None = None,
    ) -> None:
        self.db_path = db_path
        self.embedding_model = embedding_model
        self.conn = None
        self._initialize()

    def _initialize(self) -> None:

        try:
            from sentence_transformers import SentenceTransformer

            self._SENTENCE_TRANSFORMERS_AVAILABLE = True
            self._model_class = SentenceTransformer
            logger.info(
                "✅ sentence-transformers is available for git history embeddings"
            )
        except ImportError as e:
            logger.warning(
                f"⚠️ sentence-transformers not available: {e}. "
                "Install with: uv pip install -e '.[neural]'"
            )
            self._SENTENCE_TRANSFORMERS_AVAILABLE = False
            self._model_class = None
            logger.debug(
                f"⚠️ sentence-transformers initialization failed: {e}. "
                "Git history embeddings will be disabled."
            )

        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            schema_path = Path(__file__).parent / "git_history_schema.sql"
            if schema_path.exists():
                schema_sql = schema_path.read_text(encoding="utf-8")
                self.conn.executescript(schema_sql)
                self.conn.commit()
                logger.info(f"✅ Git history embedder initialized: {self.db_path}")
            else:
                logger.warning(f"Schema file not found: {schema_path}")
                raise FileNotFoundError(f"Schema file not found: {schema_path}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize git history embedder: {e}")
            raise

    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(_thread_local, "conn") or _thread_local.conn is None:
            _thread_local.conn = sqlite3.connect(str(self.db_path))
            _thread_local.conn.row_factory = sqlite3.Row
        return _thread_local.conn

    def store_embedding(
        self,
        path: str,
        embedding: np.ndarray,
        timestamp: datetime | None = None,
    ) -> None:
        if not self._SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning("sentence-transformers not available, skipping storage")
            return

        try:
            timestamp = timestamp or datetime.now()
            compressed_embedding = sqlite3.adapt_compression(embedding)

            insert_sql = """
                INSERT INTO git_history_embeddings
                (path, embedding, timestamp)
                VALUES (?, ?, ?)
            """

            self.conn.execute(
                insert_sql,
                (path, compressed_embedding, timestamp.isoformat()),
            )
            self.conn.commit()
            logger.debug(f"Stored embedding for {path}")
        except Exception as e:
            logger.error(f"Failed to store embedding: {e}")

    def find_similar_embeddings(
        self,
        query_embedding: np.ndarray,
        k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[tuple[str, float, np.ndarray]]:
        if self.conn is None:
            return []

        try:
            query = """
                SELECT path, embedding, timestamp FROM git_history_embeddings
                WHERE path IS NOT NULL AND embedding IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT ?
                """

            if _SENTENCE_TRANSFORMERS_AVAILABLE:
                query += f" LIMIT {k}"
            else:
                query = """
                    SELECT path, embedding, timestamp FROM git_history_embeddings
                    WHERE path IS NOT NULL AND tfidf_vector IS NOT NULL
                    ORDER BY timestamp DESC
                    LIMIT ?
                """
                query += f" LIMIT {k}"

            cursor = self.conn.execute(query, (k,))
            rows = cursor.fetchall()

            if not rows:
                logger.debug("No historical embeddings found")
                return []

            results: list[tuple[str, float, np.ndarray]] = []

            for row in rows:
                stored_blob = row["embedding"]

                if stored_blob is None:
                    logger.warning(
                        f"Skipping row with NULL embedding for {row['path']}"
                    )
                    continue

                try:
                    stored = np.frombuffer(stored_blob, dtype=np.float32)
                    similarity = float(
                        np.dot(query_embedding, stored)
                        / (np.linalg.norm(query_embedding) * np.linalg.norm(stored))
                    )
                    if np.isnan(similarity):
                        similarity = 0.0
                except Exception as e:
                    logger.error(f"Failed to compute similarity for {row['path']}: {e}")
                    continue

                results.append((row["path"], similarity, stored))

            results.sort(key=operator.itemgetter(1), reverse=True)

            return results[:k]

        except Exception as e:
            logger.error(f"Failed to find similar embeddings: {e}")
            return []

    def get_statistics(self) -> dict[str, t.Any]:
        if self.conn is None:
            return {}

        try:
            cursor = self.conn.execute(
                "SELECT COUNT(*) as total_embeddings FROM git_history_embeddings"
            )
            row = cursor.fetchone()
            total_count = row["total_embeddings"] if row else 0

            stats: dict[str, t.Any] = {
                "total_embeddings": total_count,
            }
            return stats
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Git history embedder closed")

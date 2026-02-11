"""Git history embedder for semantic search over commit messages, branches, and workflow events.

Integrates sentence-transformers (all-MiniLM-L6-v2) to generate 384-dimensional embeddings
for git history data, enabling semantic search and similarity matching.

Usage:
    from crackerjack.memory.git_history_embedder import GitHistoryEmbedder

    embedder = GitHistoryEmbedder(repo_path=Path("."))
    await embedder.index_history(since=datetime.now() - timedelta(days=30))

    results = await embedder.semantic_search("fix memory leak", limit=10)
"""

from __future__ import annotations

import logging
import sqlite3
import typing as t
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from crackerjack.memory.git_metrics_collector import (
    BranchEvent,
    CommitData,
    GitMetricsCollector,
    MergeEvent,
)

logger = logging.getLogger(__name__)

# Model configuration
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
BATCH_SIZE = 32

# Check if sentence-transformers is available
_SENTENCE_TRANSFORMERS_AVAILABLE = False
_model_class = None

try:
    from sentence_transformers import SentenceTransformer

    _SENTENCE_TRANSFORMERS_AVAILABLE = True
    _model_class = SentenceTransformer
    logger.info("✅ sentence-transformers is available for git history embeddings")
except ImportError as e:
    logger.warning(
        f"⚠️ sentence-transformers not available: {e}. "
        "Install with: uv pip install -e '.[neural]'"
    )
    _SENTENCE_TRANSFORMERS_AVAILABLE = False
except Exception as e:
    logger.warning(
        f"⚠️ sentence-transformers initialization failed: {e}. "
        "Git history embeddings will be disabled."
    )
    _SENTENCE_TRANSFORMERS_AVAILABLE = False


@dataclass(frozen=True)
class GitHistoryEntry:
    """A single git history entry with embedding data."""

    entry_id: str
    entry_type: t.Literal["commit", "branch", "merge"]
    timestamp: datetime
    content: str
    metadata: dict[str, t.Any]
    embedding: np.ndarray | None = None
    semantic_tags: list[str] = field(default_factory=list)

    def to_searchable_text(self) -> str:
        """Build searchable text from entry content and metadata."""
        parts = [self.content]

        if self.semantic_tags:
            parts.append(f"tags: {', '.join(self.semantic_tags)}")

        if self.metadata.get("author"):
            parts.append(f"by {self.metadata['author']}")

        if self.metadata.get("branch"):
            parts.append(f"branch: {self.metadata['branch']}")

        return ". ".join(parts)

    def get_embedding_bytes(self) -> bytes | None:
        """Convert embedding to bytes for storage."""
        if self.embedding is None:
            return None
        return self.embedding.astype(np.float32).tobytes()


@dataclass(frozen=True)
class SearchResult:
    """Semantic search result with similarity score."""

    entry_id: str
    entry_type: str
    content: str
    metadata: dict[str, t.Any]
    similarity: float
    timestamp: datetime
    semantic_tags: list[str] = field(default_factory=list)


class GitHistoryStorage:
    """SQLite storage for git history embeddings."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        """Initialize database schema for git history embeddings."""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS git_history_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id TEXT UNIQUE NOT NULL,
                    entry_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    semantic_tags TEXT,
                    embedding BLOB NOT NULL,
                    indexed_at TEXT NOT NULL
                )
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_embeddings_type
                ON git_history_embeddings(entry_type)
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_embeddings_timestamp
                ON git_history_embeddings(timestamp)
            """)

            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_history_embeddings_tags
                ON git_history_embeddings(semantic_tags)
            """)

            self.conn.commit()
            logger.info(
                f"✅ Git history embeddings storage initialized: {self.db_path}"
            )

        except Exception as e:
            logger.error(
                f"❌ Failed to initialize git history embeddings database: {e}"
            )
            raise

    def store_entry(self, entry: GitHistoryEntry) -> bool:
        """Store a single git history entry with embedding."""
        if self.conn is None:
            logger.warning("Database connection not initialized")
            return False

        try:
            import json

            embedding_bytes = entry.get_embedding_bytes()
            if embedding_bytes is None:
                logger.warning(f"No embedding for entry {entry.entry_id}")
                return False

            indexed_at = datetime.now().isoformat()

            self.conn.execute(
                """
                INSERT OR REPLACE INTO git_history_embeddings
                (entry_id, entry_type, timestamp, content, metadata, semantic_tags,
                 embedding, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.entry_type,
                    entry.timestamp.isoformat(),
                    entry.content,
                    json.dumps(entry.metadata),
                    ",".join(entry.semantic_tags),
                    embedding_bytes,
                    indexed_at,
                ),
            )
            self.conn.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to store entry {entry.entry_id}: {e}")
            return False

    def store_batch(self, entries: list[GitHistoryEntry]) -> int:
        """Store multiple entries in a batch transaction."""
        if not entries:
            return 0

        if self.conn is None:
            logger.warning("Database connection not initialized")
            return 0

        stored_count = 0
        try:
            import json

            indexed_at = datetime.now().isoformat()

            cursor = self.conn.cursor()
            for entry in entries:
                try:
                    embedding_bytes = entry.get_embedding_bytes()
                    if embedding_bytes is None:
                        continue

                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO git_history_embeddings
                        (entry_id, entry_type, timestamp, content, metadata, semantic_tags,
                         embedding, indexed_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            entry.entry_id,
                            entry.entry_type,
                            entry.timestamp.isoformat(),
                            entry.content,
                            json.dumps(entry.metadata),
                            ",".join(entry.semantic_tags),
                            embedding_bytes,
                            indexed_at,
                        ),
                    )
                    stored_count += 1

                except Exception as e:
                    logger.debug(f"Failed to store entry {entry.entry_id}: {e}")

            self.conn.commit()
            logger.info(f"Stored {stored_count}/{len(entries)} git history entries")

            return stored_count

        except Exception as e:
            logger.error(f"Failed to store batch entries: {e}")
            return stored_count

    def get_all_entries(
        self,
        entry_type: str | None = None,
        since: datetime | None = None,
    ) -> list[dict[str, t.Any]]:
        """Retrieve all entries with optional filtering."""
        if self.conn is None:
            return []

        try:
            import json

            query = "SELECT * FROM git_history_embeddings WHERE 1=1"
            params: list[t.Any] = []

            if entry_type:
                query += " AND entry_type = ?"
                params.append(entry_type)

            if since:
                query += " AND timestamp >= ?"
                params.append(since.isoformat())

            cursor = self.conn.execute(query, params)
            rows = cursor.fetchall()

            entries = []
            for row in rows:
                entries.append(
                    {
                        "entry_id": row["entry_id"],
                        "entry_type": row["entry_type"],
                        "timestamp": datetime.fromisoformat(row["timestamp"]),
                        "content": row["content"],
                        "metadata": json.loads(row["metadata"]),
                        "semantic_tags": row["semantic_tags"].split(",")
                        if row["semantic_tags"]
                        else [],
                        "embedding": np.frombuffer(row["embedding"], dtype=np.float32),
                    }
                )

            return entries

        except Exception as e:
            logger.error(f"Failed to retrieve entries: {e}")
            return []

    def search_by_similarity(
        self,
        query_embedding: np.ndarray,
        limit: int = 10,
        min_similarity: float = 0.3,
        entry_type: str | None = None,
    ) -> list[tuple[float, dict[str, t.Any]]]:
        """Search entries by cosine similarity to query embedding."""
        entries = self.get_all_entries(entry_type=entry_type)

        if not entries:
            return []

        results: list[tuple[float, dict[str, t.Any]]] = []

        for entry in entries:
            stored_embedding = entry["embedding"]

            if stored_embedding is None or stored_embedding.size != EMBEDDING_DIM:
                continue

            similarity = self._cosine_similarity(query_embedding, stored_embedding)

            if similarity >= min_similarity:
                results.append((similarity, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return results[:limit]

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two embeddings."""
        try:
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            return float(dot_product / (norm_a * norm_b))

        except Exception:
            return 0.0

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Git history storage closed")


class GitHistoryEmbedder:
    """Generate and search embeddings for git history.

    Uses sentence-transformers (all-MiniLM-L6-v2) to generate 384-dimensional
    embeddings for commit messages, file paths, branch patterns, and workflow events.
    """

    def __init__(
        self,
        repo_path: Path,
        executor: t.Any,  # SecureSubprocessExecutorProtocol
        storage_path: Path | None = None,
        model_name: str = MODEL_NAME,
    ) -> None:
        if not _SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers is not available. "
                "Install with: uv pip install -e '.[neural]'"
            )

        self.repo_path = repo_path.resolve()
        self.executor = executor
        self.model_name = model_name

        self.git_collector = GitMetricsCollector(
            repo_path=repo_path,
            executor=executor,
            storage_path=storage_path,
        )

        if storage_path is None:
            storage_path = repo_path / ".git" / "git_history_embeddings.db"

        self.storage = GitHistoryStorage(storage_path)

        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning)
                self.model = _model_class(model_name)

            self.embedding_dim = self.model.get_sentence_embedding_dimension()

            if self.embedding_dim != EMBEDDING_DIM:
                logger.warning(
                    f"Model {model_name} has embedding_dim={self.embedding_dim}, "
                    f"expected {EMBEDDING_DIM}"
                )

            logger.info(
                f"✅ GitHistoryEmbedder initialized with {model_name} "
                f"(embedding_dim={self.embedding_dim})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to load sentence transformer model: {e}")
            raise RuntimeError(f"Model loading failed: {e}") from e

    async def index_history(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        batch_size: int = BATCH_SIZE,
    ) -> dict[str, int]:
        """Index git history with embeddings.

        Args:
            since: Start date for history collection (default: 30 days ago)
            until: End date for history collection (default: now)
            batch_size: Batch size for embedding generation

        Returns:
            Dictionary with counts of indexed entries by type
        """
        if since is None:
            since = datetime.now() - timedelta(days=30)
        if until is None:
            until = datetime.now()

        logger.info(f"🔄 Indexing git history from {since} to {until}")

        indexed_counts = {
            "commits": 0,
            "branches": 0,
            "merges": 0,
            "failed": 0,
        }

        # Collect commits
        try:
            commits = self.git_collector.git.get_commits(since=since, until=until)
            commit_entries = self._create_commit_entries(commits)

            if commit_entries:
                embeddings = self._embed_batch_texts(
                    [entry.to_searchable_text() for entry in commit_entries],
                    batch_size=batch_size,
                )

                indexed_commits = self._store_with_embeddings(
                    commit_entries,
                    embeddings,
                )
                indexed_counts["commits"] = indexed_commits

        except Exception as e:
            logger.error(f"Failed to index commits: {e}")
            indexed_counts["failed"] += 1

        # Collect branch events
        try:
            branch_events = self.git_collector.git.get_reflog_events(since=since)
            branch_entries = self._create_branch_entries(branch_events)

            if branch_entries:
                embeddings = self._embed_batch_texts(
                    [entry.to_searchable_text() for entry in branch_entries],
                    batch_size=batch_size,
                )

                indexed_branches = self._store_with_embeddings(
                    branch_entries,
                    embeddings,
                )
                indexed_counts["branches"] = indexed_branches

        except Exception as e:
            logger.error(f"Failed to index branch events: {e}")
            indexed_counts["failed"] += 1

        # Collect merge events
        try:
            merge_events = self.git_collector.git.get_merge_history(
                since=since, until=until
            )
            merge_entries = self._create_merge_entries(merge_events)

            if merge_entries:
                embeddings = self._embed_batch_texts(
                    [entry.to_searchable_text() for entry in merge_entries],
                    batch_size=batch_size,
                )

                indexed_merges = self._store_with_embeddings(
                    merge_entries,
                    embeddings,
                )
                indexed_counts["merges"] = indexed_merges

        except Exception as e:
            logger.error(f"Failed to index merge events: {e}")
            indexed_counts["failed"] += 1

        total_indexed = sum(v for k, v in indexed_counts.items() if k != "failed")
        logger.info(
            f"✅ Git history indexing complete: {total_indexed} entries "
            f"(commits={indexed_counts['commits']}, "
            f"branches={indexed_counts['branches']}, "
            f"merges={indexed_counts['merges']})"
        )

        return indexed_counts

    def _create_commit_entries(
        self, commits: list[CommitData]
    ) -> list[GitHistoryEntry]:
        """Create GitHistoryEntry objects from commits."""
        entries = []

        for commit in commits:
            entry_id = f"commit-{commit.hash}"

            content = f"Commit: {commit.message}"

            metadata = {
                "commit_hash": commit.hash,
                "author": commit.author_name,
                "author_email": commit.author_email,
                "is_merge": commit.is_merge,
                "is_conventional": commit.is_conventional,
            }

            if commit.is_conventional:
                metadata["conventional_type"] = commit.conventional_type or ""
                metadata["conventional_scope"] = commit.conventional_scope or ""
                metadata["breaking_change"] = commit.has_breaking_change

            semantic_tags = self._extract_semantic_tags(commit)

            entries.append(
                GitHistoryEntry(
                    entry_id=entry_id,
                    entry_type="commit",
                    timestamp=commit.author_timestamp,
                    content=content,
                    metadata=metadata,
                    semantic_tags=semantic_tags,
                )
            )

        return entries

    def _create_branch_entries(
        self, events: list[BranchEvent]
    ) -> list[GitHistoryEntry]:
        """Create GitHistoryEntry objects from branch events."""
        entries = []

        for event in events:
            entry_id = f"branch-{event.timestamp.timestamp()}-{event.branch_name}"

            content = f"Branch {event.event_type}: {event.branch_name}"

            metadata = {
                "branch_name": event.branch_name,
                "event_type": event.event_type,
            }

            if event.commit_hash:
                metadata["commit_hash"] = event.commit_hash

            semantic_tags = [f"branch:{event.event_type}"]

            entries.append(
                GitHistoryEntry(
                    entry_id=entry_id,
                    entry_type="branch",
                    timestamp=event.timestamp,
                    content=content,
                    metadata=metadata,
                    semantic_tags=semantic_tags,
                )
            )

        return entries

    def _create_merge_entries(self, events: list[MergeEvent]) -> list[GitHistoryEntry]:
        """Create GitHistoryEntry objects from merge events."""
        entries = []

        for event in events:
            entry_id = f"merge-{event.merge_hash}"

            content_parts = [f"Merge {event.merge_type}"]
            if event.source_branch:
                content_parts.append(f"from {event.source_branch}")
            if event.target_branch:
                content_parts.append(f"to {event.target_branch}")
            if event.has_conflicts:
                content_parts.append(f"with {len(event.conflict_files)} conflicts")

            content = " ".join(content_parts)

            metadata = {
                "merge_hash": event.merge_hash,
                "merge_type": event.merge_type,
                "has_conflicts": event.has_conflicts,
                "conflict_count": len(event.conflict_files),
            }

            if event.source_branch:
                metadata["source_branch"] = event.source_branch
            if event.target_branch:
                metadata["target_branch"] = event.target_branch

            semantic_tags = [f"merge:{event.merge_type}"]
            if event.has_conflicts:
                semantic_tags.append("conflict")

            entries.append(
                GitHistoryEntry(
                    entry_id=entry_id,
                    entry_type="merge",
                    timestamp=event.merge_timestamp,
                    content=content,
                    metadata=metadata,
                    semantic_tags=semantic_tags,
                )
            )

        return entries

    def _extract_semantic_tags(self, commit: CommitData) -> list[str]:
        """Extract semantic tags from commit data."""
        tags = []

        if commit.is_conventional and commit.conventional_type:
            tags.append(f"type:{commit.conventional_type}")
            if commit.conventional_scope:
                tags.append(f"scope:{commit.conventional_scope}")

        if commit.has_breaking_change:
            tags.append("breaking")

        if commit.is_merge:
            tags.append("merge")

        return tags

    def _embed_batch_texts(
        self,
        texts: list[str],
        batch_size: int = BATCH_SIZE,
    ) -> np.ndarray:
        """Generate embeddings for a batch of texts."""
        if not texts:
            return np.array([]).reshape(0, self.embedding_dim)

        try:
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=batch_size,
            )

            return embeddings.astype(np.float32)

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            return np.zeros((len(texts), self.embedding_dim), dtype=np.float32)

    def _store_with_embeddings(
        self,
        entries: list[GitHistoryEntry],
        embeddings: np.ndarray,
    ) -> int:
        """Store entries with their embeddings."""
        if len(entries) != len(embeddings):
            logger.warning(
                f"Mismatch: {len(entries)} entries vs {len(embeddings)} embeddings"
            )
            return 0

        entries_with_embeddings = []
        for entry, embedding in zip(entries, embeddings):
            entry_with_emb = GitHistoryEntry(
                entry_id=entry.entry_id,
                entry_type=entry.entry_type,
                timestamp=entry.timestamp,
                content=entry.content,
                metadata=entry.metadata,
                embedding=embedding,
                semantic_tags=entry.semantic_tags,
            )
            entries_with_embeddings.append(entry_with_emb)

        return self.storage.store_batch(entries_with_embeddings)

    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        min_similarity: float = 0.3,
        entry_type: str | None = None,
    ) -> list[SearchResult]:
        """Perform semantic search over git history.

        Args:
            query: Natural language query
            limit: Maximum number of results
            min_similarity: Minimum similarity threshold (0-1)
            entry_type: Filter by entry type ('commit', 'branch', 'merge')

        Returns:
            List of search results sorted by similarity
        """
        try:
            query_embedding = self.model.encode(
                query,
                convert_to_numpy=True,
                show_progress_bar=False,
            ).astype(np.float32)

            results = self.storage.search_by_similarity(
                query_embedding,
                limit=limit,
                min_similarity=min_similarity,
                entry_type=entry_type,
            )

            search_results = []
            for similarity, entry in results:
                search_results.append(
                    SearchResult(
                        entry_id=entry["entry_id"],
                        entry_type=entry["entry_type"],
                        content=entry["content"],
                        metadata=entry["metadata"],
                        similarity=similarity,
                        timestamp=entry["timestamp"],
                        semantic_tags=entry["semantic_tags"],
                    )
                )

            if search_results:
                logger.info(
                    f"Found {len(search_results)} results for query '{query}' "
                    f"(similarity: {search_results[0].similarity:.3f}...)"
                )

            return search_results

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def close(self) -> None:
        """Close resources."""
        self.storage.close()
        self.git_collector.close()


def is_git_history_embedder_available() -> bool:
    """Check if sentence-transformers is available for git history embeddings."""
    return _SENTENCE_TRANSFORMERS_AVAILABLE


__all__ = [
    "GitHistoryEntry",
    "SearchResult",
    "GitHistoryStorage",
    "GitHistoryEmbedder",
    "is_git_history_embedder_available",
]

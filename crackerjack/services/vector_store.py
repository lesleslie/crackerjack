"""Core vector store service for semantic search functionality."""

import json
import logging
import sqlite3
import tempfile
import typing as t
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from crackerjack.services.ai.embeddings import EmbeddingService

from ..models.semantic_models import (
    EmbeddingVector,
    IndexingProgress,
    IndexStats,
    SearchQuery,
    SearchResult,
    SemanticConfig,
)

logger = logging.getLogger(__name__)


class VectorStore:
    """Core vector store for managing embeddings and semantic search."""

    def __init__(
        self,
        config: SemanticConfig,
        db_path: Path | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        """Initialize the vector store.

        Args:
            config: Semantic search configuration
            db_path: Optional path to SQLite database (uses temp file if None)
            embedding_service: Optional embedding service (creates new if None)
        """
        self.config = config
        self.embedding_service = embedding_service or EmbeddingService(config)

        # Database setup
        self._temp_db: tempfile._TemporaryFileWrapper[bytes] | None = None
        if db_path is None:
            # Create temporary database file
            self._temp_db = tempfile.NamedTemporaryFile(
                suffix=".db", delete=False, prefix="crackerjack_vectors_"
            )
            self.db_path = Path(self._temp_db.name)
        else:
            self.db_path = db_path

        self._initialize_database()

    def _initialize_database(self) -> None:
        """Initialize SQLite database with required tables."""
        with self._get_connection() as conn:
            # Create embeddings table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    chunk_id TEXT PRIMARY KEY,
                    file_path TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    file_hash TEXT NOT NULL,
                    start_line INTEGER NOT NULL,
                    end_line INTEGER NOT NULL,
                    file_type TEXT NOT NULL
                )
            """)

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_path ON embeddings(file_path)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_hash ON embeddings(file_hash)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_type ON embeddings(file_type)
            """)

            # Create file tracking table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_tracking (
                    file_path TEXT PRIMARY KEY,
                    file_hash TEXT NOT NULL,
                    last_indexed TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0
                )
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self) -> t.Iterator[sqlite3.Connection]:
        """Get a database connection with proper error handling."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def index_file(
        self,
        file_path: Path,
        progress_callback: t.Callable[[IndexingProgress], None] | None = None,
    ) -> list[EmbeddingVector]:
        """Index a single file and return created embeddings.

        Args:
            file_path: Path to file to index
            progress_callback: Optional callback for progress updates

        Returns:
            List of embedding vectors created for the file

        Raises:
            OSError: If file cannot be read
            ValueError: If file is too large or has unsupported extension
        """
        # Validate file and check if reindexing is needed
        current_hash = self._prepare_file_for_indexing(file_path)
        if current_hash is None:  # File up to date
            return self._get_existing_embeddings(file_path)

        logger.info(f"Indexing file: {file_path}")

        try:
            # Process file content into chunks and metadata
            chunk_data = self._process_file_content(file_path, current_hash)
            if not chunk_data["chunks"]:
                logger.warning(f"No chunks generated for file: {file_path}")
                return []

            # Generate embeddings and create vector objects
            embeddings = self._create_embedding_vectors(
                file_path, current_hash, chunk_data, progress_callback
            )

            # Store results and update tracking
            self._store_embeddings(embeddings)
            self._update_file_tracking(file_path, current_hash, len(embeddings))

            logger.info(
                f"Successfully indexed {len(embeddings)} chunks from {file_path}"
            )
            return embeddings

        except Exception as e:
            logger.error(f"Failed to index file {file_path}: {e}")
            raise

    def _prepare_file_for_indexing(self, file_path: Path) -> str | None:
        """Prepare file for indexing and return hash if reindexing needed.

        Args:
            file_path: Path to prepare for indexing

        Returns:
            File hash if reindexing needed, None if file is up to date
        """
        self._validate_file_for_indexing(file_path)

        current_hash = self.embedding_service.get_file_hash(file_path)
        if not self._needs_reindexing(file_path, current_hash):
            logger.debug(f"File {file_path} is up to date, skipping")
            return None

        return current_hash

    def _process_file_content(
        self, file_path: Path, current_hash: str
    ) -> dict[str, t.Any]:
        """Process file content into chunks and metadata.

        Args:
            file_path: Path to process
            current_hash: File hash for chunk IDs

        Returns:
            Dictionary with chunks, texts, and metadata
        """
        content = file_path.read_text(encoding="utf-8")
        chunks = self.embedding_service.chunk_text(content)

        chunk_texts = []
        chunk_metadata = []

        for i, chunk_content in enumerate(chunks):
            chunk_id = f"{file_path.stem}_{current_hash[:8]}_{i}"
            start_line = i * (self.config.chunk_size // 50) + 1  # Rough estimate
            end_line = start_line + (len(chunk_content.split("\n")) - 1)

            chunk_texts.append(chunk_content)
            chunk_metadata.append(
                {
                    "chunk_id": chunk_id,
                    "start_line": start_line,
                    "end_line": end_line,
                }
            )

        return {
            "chunks": chunks,
            "chunk_texts": chunk_texts,
            "chunk_metadata": chunk_metadata,
        }

    def _create_embedding_vectors(
        self,
        file_path: Path,
        current_hash: str,
        chunk_data: dict[str, t.Any],
        progress_callback: t.Callable[[IndexingProgress], None] | None = None,
    ) -> list[EmbeddingVector]:
        """Create embedding vectors from chunk data.

        Args:
            file_path: Path being indexed
            current_hash: File hash
            chunk_data: Processed chunk data
            progress_callback: Optional progress callback

        Returns:
            List of embedding vectors
        """
        chunk_texts = chunk_data["chunk_texts"]
        chunk_metadata = chunk_data["chunk_metadata"]

        # Generate embeddings in batch for efficiency
        embedding_vectors = self.embedding_service.generate_embeddings_batch(
            chunk_texts
        )

        embeddings = []
        for i, (embedding_vector, metadata) in enumerate(
            zip(embedding_vectors, chunk_metadata)
        ):
            if not embedding_vector:  # Skip empty embeddings
                continue

            # Progress callback
            if progress_callback:
                progress = IndexingProgress(
                    current_file=file_path,
                    files_processed=0,
                    total_files=1,
                    chunks_created=i,
                    elapsed_time=0.0,
                )
                progress_callback(progress)

            embedding = EmbeddingVector(
                file_path=file_path,
                chunk_id=metadata["chunk_id"],
                content=chunk_texts[i],
                embedding=embedding_vector,
                created_at=datetime.now(),
                file_hash=current_hash,
                start_line=metadata["start_line"],
                end_line=metadata["end_line"],
                file_type=file_path.suffix,
            )
            embeddings.append(embedding)

        return embeddings

    def _validate_file_for_indexing(self, file_path: Path) -> None:
        """Validate that a file can be indexed.

        Args:
            file_path: Path to validate

        Raises:
            ValueError: If file cannot be indexed
            OSError: If file cannot be accessed
        """
        if not file_path.exists():
            raise OSError(f"File does not exist: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")

        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.config.max_file_size_mb:
            raise ValueError(
                f"File too large: {file_size_mb:.1f}MB > {self.config.max_file_size_mb}MB"
            )

        # Check file extension
        if (
            self.config.included_extensions
            and file_path.suffix not in self.config.included_extensions
        ):
            raise ValueError(f"File extension not included: {file_path.suffix}")

        # Check exclusion patterns
        file_str = str(file_path)
        for pattern in self.config.excluded_patterns:
            if self._matches_pattern(file_str, pattern):
                raise ValueError(f"File matches exclusion pattern: {pattern}")

    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if file path matches exclusion pattern."""
        import fnmatch

        return fnmatch.fnmatch(file_path, pattern)

    def _needs_reindexing(self, file_path: Path, current_hash: str) -> bool:
        """Check if file needs to be reindexed.

        Args:
            file_path: Path to check
            current_hash: Current file hash

        Returns:
            True if file needs reindexing
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT file_hash FROM file_tracking WHERE file_path = ?",
                (str(file_path),),
            )
            row = cursor.fetchone()

            if row is None:
                return True  # File not indexed yet

            return row["file_hash"] != current_hash

    def _get_existing_embeddings(self, file_path: Path) -> list[EmbeddingVector]:
        """Get existing embeddings for a file.

        Args:
            file_path: Path to get embeddings for

        Returns:
            List of existing embeddings
        """
        embeddings = []

        with self._get_connection() as conn:
            cursor = conn.execute(
                """SELECT chunk_id, file_path, content, embedding, created_at,
                          file_hash, start_line, end_line, file_type
                   FROM embeddings WHERE file_path = ?""",
                (str(file_path),),
            )

            for row in cursor.fetchall():
                # Deserialize embedding
                embedding_data = json.loads(row["embedding"])

                embedding = EmbeddingVector(
                    file_path=Path(row["file_path"]),
                    chunk_id=row["chunk_id"],
                    content=row["content"],
                    embedding=embedding_data,
                    created_at=datetime.fromisoformat(row["created_at"]),
                    file_hash=row["file_hash"],
                    start_line=row["start_line"],
                    end_line=row["end_line"],
                    file_type=row["file_type"],
                )
                embeddings.append(embedding)

        return embeddings

    def _store_embeddings(self, embeddings: list[EmbeddingVector]) -> None:
        """Store embeddings in database.

        Args:
            embeddings: List of embeddings to store
        """
        if not embeddings:
            return

        with self._get_connection() as conn:
            # Remove existing embeddings for these files
            file_paths = {str(emb.file_path) for emb in embeddings}
            for file_path in file_paths:
                conn.execute("DELETE FROM embeddings WHERE file_path = ?", (file_path,))

            # Insert new embeddings
            for embedding in embeddings:
                conn.execute(
                    """
                    INSERT INTO embeddings
                    (chunk_id, file_path, content, embedding, created_at,
                     file_hash, start_line, end_line, file_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        embedding.chunk_id,
                        str(embedding.file_path),
                        embedding.content,
                        json.dumps(embedding.embedding),
                        embedding.created_at.isoformat(),
                        embedding.file_hash,
                        embedding.start_line,
                        embedding.end_line,
                        embedding.file_type,
                    ),
                )

            conn.commit()

    def _update_file_tracking(
        self, file_path: Path, file_hash: str, chunk_count: int
    ) -> None:
        """Update file tracking information.

        Args:
            file_path: Path of indexed file
            file_hash: Hash of file content
            chunk_count: Number of chunks created
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO file_tracking
                (file_path, file_hash, last_indexed, chunk_count)
                VALUES (?, ?, ?, ?)
            """,
                (str(file_path), file_hash, datetime.now().isoformat(), chunk_count),
            )
            conn.commit()

    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Perform semantic search and return results.

        Args:
            query: Search query with parameters

        Returns:
            List of search results sorted by similarity score
        """
        # Generate embedding for query
        query_embedding = self.embedding_service.generate_embedding(query.query)

        # Get all embeddings from database
        embeddings_data: list[dict[str, t.Any]] = self._get_all_embeddings(
            query.file_types
        )

        if not embeddings_data:
            return []

        # Calculate similarities
        similarities = self.embedding_service.calculate_similarities_batch(
            query_embedding, [data["embedding"] for data in embeddings_data]
        )

        # Create search results
        results = []
        for i, (data, similarity) in enumerate(zip(embeddings_data, similarities)):
            if similarity >= query.min_similarity:
                # Get context lines if requested
                context_lines = []
                if query.include_context:
                    context_lines = self._get_context_lines(
                        Path(data["file_path"]),
                        data["start_line"],
                        data["end_line"],
                        query.context_lines,
                    )

                result = SearchResult(
                    file_path=Path(data["file_path"]),
                    chunk_id=data["chunk_id"],
                    content=data["content"],
                    similarity_score=similarity,
                    start_line=data["start_line"],
                    end_line=data["end_line"],
                    file_type=data["file_type"],
                    context_lines=context_lines,
                )
                results.append(result)

        # Sort by similarity score (descending) and limit results
        results.sort(key=lambda x: x.similarity_score, reverse=True)
        return results[: query.max_results]

    def _get_all_embeddings(
        self, file_types: list[str] | None = None
    ) -> list[dict[str, t.Any]]:
        """Get all embeddings from database with optional file type filtering.

        Args:
            file_types: Optional list of file types to filter by

        Returns:
            List of embedding data dictionaries
        """
        embeddings_data = []

        with self._get_connection() as conn:
            if file_types:
                # Build parameterized query safely with proper placeholders
                placeholders = ",".join("?" * len(file_types))
                # Use static query template with placeholders - safe from injection
                query_template = (
                    "SELECT chunk_id, file_path, content, embedding, start_line, end_line, file_type "
                    "FROM embeddings WHERE file_type IN ({})"
                )
                query_sql = query_template.format(placeholders)  # nosec B608
                cursor = conn.execute(query_sql, file_types)
            else:
                cursor = conn.execute("""
                    SELECT chunk_id, file_path, content, embedding, start_line, end_line, file_type
                    FROM embeddings
                """)

            for row in cursor.fetchall():
                data = {
                    "chunk_id": row["chunk_id"],
                    "file_path": row["file_path"],
                    "content": row["content"],
                    "embedding": json.loads(row["embedding"]),
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                    "file_type": row["file_type"],
                }
                embeddings_data.append(data)

        return embeddings_data

    def _get_context_lines(
        self, file_path: Path, start_line: int, end_line: int, context_count: int
    ) -> list[str]:
        """Get context lines around a text chunk.

        Args:
            file_path: Path to source file
            start_line: Starting line of chunk
            end_line: Ending line of chunk
            context_count: Number of context lines to include

        Returns:
            List of context lines
        """
        try:
            if not file_path.exists():
                return []

            lines = file_path.read_text(encoding="utf-8").splitlines()

            # Calculate context range
            context_start = max(0, start_line - context_count - 1)
            context_end = min(len(lines), end_line + context_count)

            return lines[context_start:context_end]

        except Exception as e:
            logger.warning(f"Failed to get context lines for {file_path}: {e}")
            return []

    def get_stats(self) -> IndexStats:
        """Get statistics about the vector store index.

        Returns:
            Index statistics
        """
        with self._get_connection() as conn:
            # Get total counts
            cursor = conn.execute("SELECT COUNT(*) as total_chunks FROM embeddings")
            total_chunks = cursor.fetchone()["total_chunks"]

            cursor = conn.execute(
                "SELECT COUNT(DISTINCT file_path) as total_files FROM embeddings"
            )
            total_files = cursor.fetchone()["total_files"]

            # Get file type distribution
            cursor = conn.execute("""
                SELECT file_type, COUNT(*) as count
                FROM embeddings
                GROUP BY file_type
            """)
            file_types = {row["file_type"]: row["count"] for row in cursor.fetchall()}

            # Get last update time
            cursor = conn.execute(
                "SELECT MAX(created_at) as last_updated FROM embeddings"
            )
            last_updated_str = cursor.fetchone()["last_updated"]
            last_updated = (
                datetime.fromisoformat(last_updated_str)
                if last_updated_str
                else datetime.now()
            )

            # Calculate average chunk size
            cursor = conn.execute(
                "SELECT AVG(LENGTH(content)) as avg_size FROM embeddings"
            )
            avg_chunk_size = cursor.fetchone()["avg_size"] or 0.0

            # Estimate index size (rough approximation)
            index_size_mb = (total_chunks * 384 * 4) / (
                1024 * 1024
            )  # Assuming 384-dim embeddings

        return IndexStats(
            total_files=total_files,
            total_chunks=total_chunks,
            index_size_mb=index_size_mb,
            last_updated=last_updated,
            file_types=file_types,
            embedding_model=self.config.embedding_model,
            avg_chunk_size=avg_chunk_size,
        )

    def remove_file(self, file_path: Path) -> bool:
        """Remove a file's embeddings from the index.

        Args:
            file_path: Path of file to remove

        Returns:
            True if file was removed, False if not found
        """
        with self._get_connection() as conn:
            # Check if file exists in index
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM embeddings WHERE file_path = ?",
                (str(file_path),),
            )
            count = cursor.fetchone()["count"]

            if count == 0:
                return False

            # Remove embeddings
            conn.execute(
                "DELETE FROM embeddings WHERE file_path = ?", (str(file_path),)
            )

            # Remove from file tracking
            conn.execute(
                "DELETE FROM file_tracking WHERE file_path = ?", (str(file_path),)
            )

            conn.commit()
            logger.info(f"Removed {count} embeddings for file: {file_path}")
            return True

    def clear_index(self) -> None:
        """Clear all embeddings from the index."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM embeddings")
            conn.execute("DELETE FROM file_tracking")
            conn.commit()
            logger.info("Cleared all embeddings from index")

    def close(self) -> None:
        """Clean up resources."""
        if self._temp_db:
            self._temp_db.close()
            if self.db_path.exists():
                self.db_path.unlink()
            logger.debug("Cleaned up temporary database")

    def __enter__(self) -> "VectorStore":
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        """Context manager exit."""
        self.close()

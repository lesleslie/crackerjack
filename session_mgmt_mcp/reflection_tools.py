#!/usr/bin/env python3
"""Reflection Tools for Claude Session Management.

Provides memory and conversation search capabilities using DuckDB and local embeddings.
"""

import asyncio
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Database and embedding imports
try:
    import duckdb

    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

try:
    import onnxruntime as ort
    from transformers import AutoTokenizer

    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False

import numpy as np


class ReflectionDatabase:
    """Manages DuckDB database for conversation memory and reflection."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path or os.path.expanduser("~/.claude/data/reflection.duckdb")
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn: duckdb.DuckDBPyConnection | None = None
        self.onnx_session: ort.InferenceSession | None = None
        self.tokenizer = None
        self.embedding_dim = 384  # all-MiniLM-L6-v2 dimension

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: vulture
        """Context manager exit with cleanup."""
        self.close()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # noqa: vulture
        """Async context manager exit with cleanup."""
        self.close()

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass  # Ignore errors during cleanup
            finally:
                self.conn = None

    def __del__(self) -> None:
        """Destructor to ensure cleanup."""
        self.close()

    async def initialize(self) -> None:
        """Initialize database and embedding models."""
        if not DUCKDB_AVAILABLE:
            msg = "DuckDB not available. Install with: pip install duckdb"
            raise ImportError(msg)

        # Initialize DuckDB connection with appropriate settings for concurrency
        self.conn = duckdb.connect(self.db_path)
        # DuckDB doesn't use SQLite-style PRAGMA commands
        # DuckDB handles concurrency automatically with MVCC

        # Initialize ONNX embedding model
        if ONNX_AVAILABLE:
            try:
                # Load tokenizer
                self.tokenizer = AutoTokenizer.from_pretrained(
                    "sentence-transformers/all-MiniLM-L6-v2",
                )

                # Try to load ONNX model
                model_path = os.path.expanduser(
                    "~/.claude/all-MiniLM-L6-v2/onnx/model.onnx",
                )
                if not os.path.exists(model_path):
                    print("ONNX model not found, will use text search fallback")
                    self.onnx_session = None
                else:
                    self.onnx_session = ort.InferenceSession(model_path)
                    self.embedding_dim = 384
            except Exception as e:
                print(f"ONNX model loading failed, using text search: {e}")
                self.onnx_session = None
        else:
            print("ONNX not available, using text search fallback")

        # Create tables if they don't exist
        await self._ensure_tables()

    async def _ensure_tables(self) -> None:
        """Ensure required tables exist."""
        # Create conversations table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id VARCHAR PRIMARY KEY,
                content TEXT NOT NULL,
                embedding FLOAT[384],
                project VARCHAR,
                timestamp TIMESTAMP,
                metadata JSON
            )
        """)

        # Create reflections table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS reflections (
                id VARCHAR PRIMARY KEY,
                content TEXT NOT NULL,
                embedding FLOAT[384],
                tags VARCHAR[],
                timestamp TIMESTAMP,
                metadata JSON
            )
        """)

        # Create project_groups table for multi-project coordination
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS project_groups (
                id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                description TEXT,
                projects VARCHAR[] NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                metadata JSON
            )
        """)

        # Create project_dependencies table for project relationships
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS project_dependencies (
                id VARCHAR PRIMARY KEY,
                source_project VARCHAR NOT NULL,
                target_project VARCHAR NOT NULL,
                dependency_type VARCHAR NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                metadata JSON,
                UNIQUE(source_project, target_project, dependency_type)
            )
        """)

        # Create session_links table for cross-project session coordination
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS session_links (
                id VARCHAR PRIMARY KEY,
                source_session_id VARCHAR NOT NULL,
                target_session_id VARCHAR NOT NULL,
                link_type VARCHAR NOT NULL,
                context TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                metadata JSON,
                UNIQUE(source_session_id, target_session_id, link_type)
            )
        """)

        # Create search_index table for advanced search capabilities
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS search_index (
                id VARCHAR PRIMARY KEY,
                content_type VARCHAR NOT NULL,  -- 'conversation', 'reflection', 'file', 'project'
                content_id VARCHAR NOT NULL,
                indexed_content TEXT NOT NULL,
                search_metadata JSON,
                last_indexed TIMESTAMP DEFAULT NOW(),
                UNIQUE(content_type, content_id)
            )
        """)

        # Create search_facets table for faceted search
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS search_facets (
                id VARCHAR PRIMARY KEY,
                content_type VARCHAR NOT NULL,
                content_id VARCHAR NOT NULL,
                facet_name VARCHAR NOT NULL,
                facet_value VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create indices for better performance
        await self._ensure_indices()

        self.conn.commit()

    async def _ensure_indices(self) -> None:
        """Create indices for better query performance."""
        indices = [
            # Existing table indices
            "CREATE INDEX IF NOT EXISTS idx_conversations_project ON conversations(project)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_timestamp ON conversations(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_reflections_timestamp ON reflections(timestamp)",
            # New multi-project indices
            "CREATE INDEX IF NOT EXISTS idx_project_deps_source ON project_dependencies(source_project)",
            "CREATE INDEX IF NOT EXISTS idx_project_deps_target ON project_dependencies(target_project)",
            "CREATE INDEX IF NOT EXISTS idx_session_links_source ON session_links(source_session_id)",
            "CREATE INDEX IF NOT EXISTS idx_session_links_target ON session_links(target_session_id)",
            # Search indices
            "CREATE INDEX IF NOT EXISTS idx_search_index_type ON search_index(content_type)",
            "CREATE INDEX IF NOT EXISTS idx_search_index_last_indexed ON search_index(last_indexed)",
            "CREATE INDEX IF NOT EXISTS idx_search_facets_name_value ON search_facets(facet_name, facet_value)",
            "CREATE INDEX IF NOT EXISTS idx_search_facets_content ON search_facets(content_type, content_id)",
        ]

        for index_sql in indices:
            try:
                self.conn.execute(index_sql)
            except Exception as e:
                # Some indices might not be supported in all DuckDB versions, continue
                print(f"Index creation skipped: {e}")

    async def get_embedding(self, text: str) -> list[float]:
        """Get embedding for text using ONNX model."""
        if self.onnx_session and self.tokenizer:

            def _get_embedding():
                # Tokenize text
                encoded = self.tokenizer(
                    text,
                    truncation=True,
                    padding=True,
                    return_tensors="np",
                )

                # Run inference
                outputs = self.onnx_session.run(
                    None,
                    {
                        "input_ids": encoded["input_ids"],
                        "attention_mask": encoded["attention_mask"],
                        "token_type_ids": encoded.get(
                            "token_type_ids",
                            np.zeros_like(encoded["input_ids"]),
                        ),
                    },
                )

                # Mean pooling
                embeddings = outputs[0]
                attention_mask = encoded["attention_mask"]
                masked_embeddings = embeddings * np.expand_dims(attention_mask, axis=-1)
                summed = np.sum(masked_embeddings, axis=1)
                counts = np.sum(attention_mask, axis=1, keepdims=True)
                mean_pooled = summed / counts

                # Normalize
                norms = np.linalg.norm(mean_pooled, axis=1, keepdims=True)
                normalized = mean_pooled / norms

                # Convert to float32 to match DuckDB FLOAT type
                return normalized[0].astype(np.float32).tolist()

            return await asyncio.get_event_loop().run_in_executor(None, _get_embedding)

        msg = "No embedding model available"
        raise RuntimeError(msg)

    async def store_conversation(self, content: str, metadata: dict[str, Any]) -> str:
        """Store conversation with optional embedding."""
        conversation_id = hashlib.md5(f"{content}_{time.time()}".encode()).hexdigest()

        if ONNX_AVAILABLE and self.onnx_session:
            try:
                embedding = await self.get_embedding(content)
            except Exception:
                embedding = None  # Fallback to no embedding
        else:
            embedding = None  # Store without embedding

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.conn.execute(
                """
                INSERT INTO conversations (id, content, embedding, project, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    conversation_id,
                    content,
                    embedding,
                    metadata.get("project"),
                    datetime.now(UTC),
                    json.dumps(metadata),
                ],
            ),
        )

        self.conn.commit()
        return conversation_id

    async def store_reflection(
        self,
        content: str,
        tags: list[str] | None = None,
    ) -> str:
        """Store reflection/insight with optional embedding."""
        reflection_id = hashlib.md5(
            f"reflection_{content}_{time.time()}".encode(),
        ).hexdigest()

        if ONNX_AVAILABLE and self.onnx_session:
            try:
                embedding = await self.get_embedding(content)
            except Exception:
                embedding = None  # Fallback to no embedding
        else:
            embedding = None  # Store without embedding

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.conn.execute(
                """
                INSERT INTO reflections (id, content, embedding, tags, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    reflection_id,
                    content,
                    embedding,
                    tags or [],
                    datetime.now(UTC),
                    json.dumps({"type": "reflection"}),
                ],
            ),
        )

        self.conn.commit()
        return reflection_id

    async def search_conversations(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.7,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search conversations by text similarity (fallback to text search if no embeddings)."""
        if ONNX_AVAILABLE and self.onnx_session:
            # Use semantic search with embeddings
            try:
                query_embedding = await self.get_embedding(query)

                sql = """
                    SELECT
                        id, content, embedding, project, timestamp, metadata,
                        array_cosine_similarity(embedding, CAST(? AS FLOAT[384])) as score
                    FROM conversations
                    WHERE embedding IS NOT NULL
                """
                params = [query_embedding]

                if project:
                    sql += " AND project = ?"
                    params.append(project)

                sql += """
                    ORDER BY score DESC
                    LIMIT ?
                """
                params.append(limit)

                results = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.conn.execute(sql, params).fetchall(),
                )

                return [
                    {
                        "content": row[1],
                        "score": float(row[6]),
                        "timestamp": row[4],
                        "project": row[3],
                        "metadata": json.loads(row[5]) if row[5] else {},
                    }
                    for row in results
                    if float(row[6]) >= min_score
                ]
            except Exception as e:
                print(f"Semantic search failed, falling back to text search: {e}")
                # Fall through to text search

        # Fallback to text search (if ONNX failed or not available)
        search_terms = query.lower().split()
        sql = "SELECT id, content, project, timestamp, metadata FROM conversations"
        params = []

        if project:
            sql += " WHERE project = ?"
            params.append(project)

        sql += " ORDER BY timestamp DESC"

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.conn.execute(sql, params).fetchall(),
        )

        # Simple text matching score
        matches = []
        for row in results:
            content_lower = row[1].lower()
            score = sum(1 for term in search_terms if term in content_lower) / len(
                search_terms,
            )

            if score > 0:  # At least one term matches
                matches.append(
                    {
                        "content": row[1],
                        "score": score,
                        "timestamp": row[3],
                        "project": row[2],
                        "metadata": json.loads(row[4]) if row[4] else {},
                    },
                )

        # Sort by score and return top matches
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]

    async def search_reflections(
        self,
        query: str,
        limit: int = 5,
        min_score: float = 0.7,
    ) -> list[dict[str, Any]]:
        """Search stored reflections by semantic similarity with text fallback."""
        if ONNX_AVAILABLE and self.onnx_session:
            # Try semantic search first
            try:
                query_embedding = await self.get_embedding(query)

                sql = """
                    SELECT
                        id, content, embedding, tags, timestamp, metadata,
                        array_cosine_similarity(embedding, CAST(? AS FLOAT[384])) as score
                    FROM reflections
                    WHERE embedding IS NOT NULL
                    ORDER BY score DESC
                    LIMIT ?
                """

                results = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.conn.execute(sql, [query_embedding, limit]).fetchall(),
                )

                semantic_results = [
                    {
                        "content": row[1],
                        "score": float(row[6]),
                        "tags": row[3] if row[3] else [],
                        "timestamp": row[4],
                        "metadata": json.loads(row[5]) if row[5] else {},
                    }
                    for row in results
                    if float(row[6]) >= min_score
                ]

                # If semantic search found results, return them
                if semantic_results:
                    return semantic_results

            except Exception as e:
                print(f"Semantic search failed, falling back to text search: {e}")

        # Fallback to text search for reflections
        search_terms = query.lower().split()
        sql = "SELECT id, content, tags, timestamp, metadata FROM reflections ORDER BY timestamp DESC"

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.conn.execute(sql).fetchall(),
        )

        # Simple text matching score for reflections
        matches = []
        for row in results:
            content_lower = row[1].lower()
            tags_lower = " ".join(row[2] if row[2] else []).lower()
            combined_text = f"{content_lower} {tags_lower}"

            # Calculate match score
            if search_terms:
                score = sum(1 for term in search_terms if term in combined_text) / len(
                    search_terms,
                )
            else:
                # For empty query, return all results with score 1.0
                score = 1.0

            if score > 0:  # At least one term matches or empty query
                matches.append(
                    {
                        "content": row[1],
                        "score": score,
                        "tags": row[2] if row[2] else [],
                        "timestamp": row[3],
                        "metadata": json.loads(row[4]) if row[4] else {},
                    },
                )

        # Sort by score and return top matches
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:limit]

    async def search_by_file(
        self,
        file_path: str,
        limit: int = 10,
        project: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search conversations that mention a specific file."""
        sql = """
            SELECT id, content, project, timestamp, metadata
            FROM conversations
            WHERE content LIKE ?
        """
        params = [f"%{file_path}%"]

        if project:
            sql += " AND project = ?"
            params.append(project)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        results = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.conn.execute(sql, params).fetchall(),
        )

        return [
            {
                "content": row[1],
                "project": row[2],
                "timestamp": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
            }
            for row in results
        ]

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        try:
            conv_count = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.conn.execute(
                    "SELECT COUNT(*) FROM conversations",
                ).fetchone()[0],
            )

            refl_count = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.conn.execute(
                    "SELECT COUNT(*) FROM reflections",
                ).fetchone()[0],
            )

            provider = (
                "onnx-runtime"
                if (self.onnx_session and ONNX_AVAILABLE)
                else "text-search-only"
            )
            return {
                "conversations_count": conv_count,
                "reflections_count": refl_count,
                "embedding_provider": provider,
                "embedding_dimension": self.embedding_dim,
                "database_path": str(self.db_path),
            }
        except Exception as e:
            return {"error": f"Failed to get stats: {e}"}


# Global database instance
_reflection_db: ReflectionDatabase | None = None


async def get_reflection_database() -> ReflectionDatabase:
    """Get or create reflection database instance."""
    global _reflection_db
    if _reflection_db is None:
        _reflection_db = ReflectionDatabase()
        await _reflection_db.initialize()
    return _reflection_db


def cleanup_reflection_database() -> None:
    """Clean up global reflection database instance."""
    global _reflection_db
    if _reflection_db:
        _reflection_db.close()
        _reflection_db = None


def get_current_project() -> str | None:
    """Get current project name from working directory."""
    try:
        cwd = Path.cwd()
        # Try to detect project from common indicators
        if (cwd / "pyproject.toml").exists() or (cwd / "package.json").exists():
            return cwd.name
        # Fallback to directory name
        return cwd.name if cwd.name != "." else None
    except Exception:
        return None

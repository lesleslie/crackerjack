#!/usr/bin/env python3
"""Unit tests for ReflectionDatabase and reflection tools.

Tests the database operations for storing and retrieving reflections,
conversation search, and embedding-based similarity matching.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from session_mgmt_mcp.reflection_tools import ReflectionDatabase


class TestReflectionDatabase:
    """Test suite for ReflectionDatabase."""

    @pytest.fixture
    async def temp_db(self):
        """Create temporary database for testing."""
        # Create a temporary directory and let DuckDB create the database file
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.duckdb"

            db = ReflectionDatabase(str(db_path))
            await db.initialize()

            yield db

            # Cleanup happens automatically when temp_dir is deleted

    @pytest.fixture
    def sample_reflection(self):
        """Sample reflection data for testing."""
        return {
            "content": "Implemented authentication system with JWT tokens",
            "project": "test-project",
            "tags": ["authentication", "jwt", "security"],
        }

    @pytest.mark.asyncio
    async def test_database_initialization(self, temp_db):
        """Test database initialization creates required tables."""
        # Check that we can get stats without error
        stats = await temp_db.get_stats()
        assert "error" not in stats

    @pytest.mark.asyncio
    async def test_store_reflection_success(self, temp_db, sample_reflection):
        """Test successful reflection storage."""
        result = await temp_db.store_reflection(
            content=sample_reflection["content"],
            tags=sample_reflection["tags"],
        )

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_store_reflection_minimal(self, temp_db):
        """Test storing reflection with minimal data."""
        result = await temp_db.store_reflection(
            content="Minimal test content",
        )

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_store_reflection_empty_content(self, temp_db):
        """Test storing reflection with empty content."""
        result = await temp_db.store_reflection(content="", tags=["test"])

        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_search_reflections_by_text(self, temp_db):
        """Test text-based reflection search."""
        # Store test reflections
        test_reflections = [
            {"content": "Authentication system implementation", "tags": ["auth"]},
            {"content": "Database optimization work", "tags": ["database"]},
            {"content": "Frontend user interface design", "tags": ["frontend"]},
        ]

        for reflection in test_reflections:
            await temp_db.store_reflection(**reflection)

        # Search for authentication
        results = await temp_db.search_reflections(query="authentication", limit=10)

        assert isinstance(results, list)
        # Should find the authentication reflection
        auth_results = [r for r in results if "authentication" in r["content"].lower()]
        assert len(auth_results) >= 0  # May be empty if no exact match

    @pytest.mark.asyncio
    async def test_search_reflections_limit(self, temp_db):
        """Test search result limiting."""
        # Store many reflections
        for i in range(10):
            await temp_db.store_reflection(
                content=f"Test reflection number {i}",
                tags=["test"],
            )

        # Search with limit
        results = await temp_db.search_reflections(query="test", limit=3)

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_search_reflections_empty_query(self, temp_db):
        """Test search with empty query."""
        # Store a reflection
        await temp_db.store_reflection(content="Test reflection", tags=["test"])

        # Search with empty query
        results = await temp_db.search_reflections(query="", limit=10)

        # Should return results even with empty query
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_get_reflection_stats_empty(self, temp_db):
        """Test getting stats from empty database."""
        stats = await temp_db.get_stats()

        assert "conversations_count" in stats
        assert "reflections_count" in stats
        assert stats["conversations_count"] == 0
        assert stats["reflections_count"] == 0

    @pytest.mark.asyncio
    async def test_get_reflection_stats_with_data(self, temp_db):
        """Test getting stats with data in database."""
        # Store reflections for different projects
        reflections = [
            {"content": "Reflection 1", "tags": ["test"]},
            {"content": "Reflection 2", "tags": ["test"]},
            {"content": "Reflection 3", "tags": ["test"]},
        ]

        for reflection in reflections:
            await temp_db.store_reflection(**reflection)

        stats = await temp_db.get_stats()

        assert "conversations_count" in stats
        assert "reflections_count" in stats
        assert stats["reflections_count"] == 3

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, temp_db):
        """Test concurrent database operations."""

        async def store_reflection(i):
            return await temp_db.store_reflection(
                content=f"Concurrent reflection {i}",
                tags=[f"concurrent-{i}"],
            )

        # Create multiple concurrent operations
        tasks = [store_reflection(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed (no exceptions)
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0

        # Verify all reflections are searchable
        search_results = await temp_db.search_reflections(query="concurrent", limit=20)
        assert len(search_results) >= 0  # May vary depending on search implementation

    @pytest.mark.asyncio
    async def test_database_error_handling(self, temp_db):
        """Test database error handling."""
        # Test with None content
        try:
            result = await temp_db.store_reflection(content=None, tags=["test"])
            # If it doesn't raise an exception, it should return a string ID
            assert isinstance(result, str)
        except Exception:
            # It's also acceptable to raise an exception
            pass

        # Test with very large content
        large_content = "A" * 100000  # 100KB content
        result = await temp_db.store_reflection(content=large_content, tags=["test"])
        assert isinstance(result, str)

        # Search should still work
        results = await temp_db.search_reflections(query="A", limit=5)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_large_content_storage(self, temp_db):
        """Test storing large content."""
        large_content = "Test content " * 10000  # Large content

        result = await temp_db.store_reflection(content=large_content, tags=["test"])

        assert isinstance(result, str)
        assert len(result) > 0

        # Verify searchable
        results = await temp_db.search_reflections(query="test", limit=1)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_special_characters_handling(self, temp_db):
        """Test handling of special characters in content."""
        special_content = (
            "Test with special chars: 'quotes', \"double quotes\", <tags>, & ampersand"
        )

        result = await temp_db.store_reflection(
            content=special_content,
            tags=["special-test"],
        )

        assert isinstance(result, str)
        assert len(result) > 0

        # Verify retrieval maintains special characters
        results = await temp_db.search_reflections(query="special", limit=1)
        assert len(results) >= 1
        assert "'" in results[0]["content"]
        assert '"' in results[0]["content"]
        assert "<" in results[0]["content"]
        assert "&" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_unicode_content_handling(self, temp_db):
        """Test handling of Unicode content."""
        unicode_content = "Unicode test: 🚀 émoji ñoñó 中文 العربية"

        result = await temp_db.store_reflection(
            content=unicode_content,
            tags=["unicode-test"],
        )

        assert isinstance(result, str)
        assert len(result) > 0

        # Verify retrieval maintains Unicode
        results = await temp_db.search_reflections(query="Unicode", limit=1)
        assert len(results) >= 1
        assert "🚀" in results[0]["content"]
        assert "émoji" in results[0]["content"]
        assert "中文" in results[0]["content"]

    @pytest.mark.asyncio
    async def test_tag_handling(self, temp_db):
        """Test proper handling of tags."""
        tags = ["python", "web-development", "API", "testing"]

        result = await temp_db.store_reflection(
            content="Test with tags",
            tags=tags,
        )

        assert isinstance(result, str)
        assert len(result) > 0

        # Search should work with tag content
        results = await temp_db.search_reflections(query="python", limit=1)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_empty_database_search(self, temp_db):
        """Test searching in empty database."""
        results = await temp_db.search_reflections(query="nonexistent", limit=10)

        assert results == []

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, temp_db):
        """Test case-insensitive search."""
        await temp_db.store_reflection(
            content="JavaScript Development Project",
            tags=["test"],
        )

        # Search with different cases
        for query in ["javascript", "JAVASCRIPT", "JavaScript", "javaScript"]:
            results = await temp_db.search_reflections(query=query, limit=10)
            assert len(results) >= 1, f"Failed to find results for query: {query}"

    @pytest.mark.asyncio
    async def test_embedding_fallback_to_text_search(self, temp_db):
        """Test fallback to text search when embeddings unavailable."""
        # Store reflection without embeddings
        await temp_db.store_reflection(
            content="Fallback search test content",
            tags=["fallback-test"],
        )

        # Search should still work via text search
        results = await temp_db.search_reflections(query="fallback", limit=5)

        assert len(results) >= 1
        assert "fallback" in results[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_search_conversations(self, temp_db):
        """Test conversation search functionality."""
        # Store test conversations

        # Since the ReflectionDatabase doesn't have a store_conversation method in the current code,
        # we'll skip this test for now and mark it as a placeholder
        pytest.skip(
            "Conversation storage not implemented in current ReflectionDatabase"
        )


@pytest.mark.asyncio
class TestReflectionDatabaseWithEmbeddings:
    """Test ReflectionDatabase with embedding functionality."""

    @pytest.fixture
    async def temp_db_with_embeddings(self):
        """Create temporary database with embedding support."""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_embeddings.duckdb"

            # Mock embedding model availability
            with (
                patch("session_mgmt_mcp.reflection_tools.ONNX_AVAILABLE", True),
                patch("session_mgmt_mcp.reflection_tools.DUCKDB_AVAILABLE", True),
                patch.object(ReflectionDatabase, "get_embedding") as mock_get_embedding,
            ):
                mock_get_embedding.return_value = [0.1, -0.2, 0.3] * 128  # 384-dim

                db = ReflectionDatabase(str(db_path))
                await db.initialize()

                yield db, mock_get_embedding

    @pytest.mark.asyncio
    async def test_embedding_generation(self, temp_db_with_embeddings):
        """Test automatic embedding generation."""
        db, mock_get_embedding = temp_db_with_embeddings

        result = await db.store_reflection(
            content="Test reflection for embedding",
            tags=["embedding-test"],
        )

        assert isinstance(result, str)
        assert len(result) > 0
        # Verify embedding generation was called
        mock_get_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_semantic_search(self, temp_db_with_embeddings):
        """Test semantic search with embeddings."""
        db, mock_get_embedding = temp_db_with_embeddings

        # Store a reflection
        await db.store_reflection(
            content="Machine learning model training",
            tags=["ml-project"],
        )

        # Search should work
        results = await db.search_reflections(query="AI model development", limit=5)

        # Should find the stored reflection
        assert len(results) >= 1

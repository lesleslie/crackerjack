"""Unit tests for ReflectionDatabase and reflection tools.

Tests the database operations for storing and retrieving reflections,
conversation search, and embedding-based similarity matching.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from session_mgmt_mcp.reflection_tools import ReflectionDatabase

# Import with fallback for test environment
try:
    from tests.fixtures.data_factories import ReflectionDataFactory
except ImportError:
    # Create mock for testing when fixtures unavailable
    class ReflectionDataFactory:
        @staticmethod
        def build(**kwargs):
            return {
                "content": kwargs.get("content", "test reflection content"),
                "tags": kwargs.get("tags", ["test"]),
                "project": kwargs.get("project", "test-project"),
            }


class TestReflectionDatabase:
    """Test suite for ReflectionDatabase."""

    @pytest.fixture
    async def temp_db(self):
        """Create temporary database for testing."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_file.close()

        db = ReflectionDatabase(temp_file.name)
        await db._ensure_tables()

        yield db

        # Cleanup
        try:
            if db.conn:
                db.conn.close()
            Path(temp_file.name).unlink(missing_ok=True)
        except Exception:
            pass

    @pytest.fixture
    def sample_reflection(self):
        """Sample reflection data for testing."""
        return {
            "content": "Implemented authentication system with JWT tokens",
            "project": "test-project",
            "tags": ["authentication", "jwt", "security"],
            "embedding": [0.1, -0.2, 0.3] * 128,  # 384-dimensional vector
        }

    @pytest.mark.asyncio
    async def test_database_initialization(self, temp_db):
        """Test database initialization creates required tables."""
        # Check if tables exist by querying them
        result = await temp_db._execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'",
        )

        table_names = [row[0] for row in result]
        assert "reflections" in table_names
        assert "conversation_metadata" in table_names

    @pytest.mark.asyncio
    async def test_store_reflection_success(self, temp_db, sample_reflection):
        """Test successful reflection storage."""
        result = await temp_db.store_reflection(
            content=sample_reflection["content"],
            project=sample_reflection["project"],
            tags=sample_reflection["tags"],
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_store_reflection_with_embedding(self, temp_db, sample_reflection):
        """Test storing reflection with custom embedding."""
        result = await temp_db.store_reflection(
            content=sample_reflection["content"],
            project=sample_reflection["project"],
            tags=sample_reflection["tags"],
            embedding=sample_reflection["embedding"],
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_store_reflection_minimal(self, temp_db):
        """Test storing reflection with minimal data."""
        result = await temp_db.store_reflection(
            content="Minimal reflection",
            project="test",
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_store_reflection_empty_content(self, temp_db):
        """Test storing reflection with empty content."""
        result = await temp_db.store_reflection(content="", project="test")

        # Should still succeed with empty content
        assert result is True

    @pytest.mark.asyncio
    async def test_search_reflections_by_text(self, temp_db):
        """Test text-based reflection search."""
        # Store test reflections
        test_reflections = [
            {"content": "Authentication system implementation", "project": "proj1"},
            {"content": "Database optimization work", "project": "proj1"},
            {"content": "Frontend user interface design", "project": "proj2"},
        ]

        for reflection in test_reflections:
            await temp_db.store_reflection(**reflection)

        # Search for authentication
        results = await temp_db.search_reflections(query="authentication", limit=10)

        assert len(results) >= 1
        # Should find the authentication reflection
        auth_results = [r for r in results if "authentication" in r["content"].lower()]
        assert len(auth_results) >= 1

    @pytest.mark.asyncio
    async def test_search_reflections_by_project(self, temp_db):
        """Test searching reflections filtered by project."""
        # Store reflections for different projects
        reflections = [
            {"content": "Feature A implementation", "project": "project-alpha"},
            {"content": "Feature B implementation", "project": "project-beta"},
            {"content": "Feature C implementation", "project": "project-alpha"},
        ]

        for reflection in reflections:
            await temp_db.store_reflection(**reflection)

        # Search within specific project
        results = await temp_db.search_reflections(
            query="feature",
            project="project-alpha",
            limit=10,
        )

        assert len(results) == 2
        for result in results:
            assert result["project"] == "project-alpha"

    @pytest.mark.asyncio
    async def test_search_reflections_limit(self, temp_db):
        """Test search result limiting."""
        # Store many reflections
        for i in range(10):
            await temp_db.store_reflection(
                content=f"Test reflection number {i}",
                project="test",
            )

        # Search with limit
        results = await temp_db.search_reflections(query="test", limit=3)

        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_search_reflections_empty_query(self, temp_db):
        """Test search with empty query."""
        # Store a reflection
        await temp_db.store_reflection(content="Test reflection", project="test")

        results = await temp_db.search_reflections(query="", limit=10)

        # Should return results even with empty query
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_get_reflection_stats_empty(self, temp_db):
        """Test getting stats from empty database."""
        stats = await temp_db.get_reflection_stats()

        expected_stats = {
            "total_reflections": 0,
            "projects": 0,
            "date_range": None,
            "recent_activity": [],
        }

        assert stats == expected_stats

    @pytest.mark.asyncio
    async def test_get_reflection_stats_with_data(self, temp_db):
        """Test getting stats with data in database."""
        # Store reflections for different projects
        reflections = [
            {"content": "Reflection 1", "project": "proj-a"},
            {"content": "Reflection 2", "project": "proj-b"},
            {"content": "Reflection 3", "project": "proj-a"},
        ]

        for reflection in reflections:
            await temp_db.store_reflection(**reflection)

        stats = await temp_db.get_reflection_stats()

        assert stats["total_reflections"] == 3
        assert stats["projects"] == 2  # proj-a and proj-b
        assert stats["date_range"] is not None
        assert "start" in stats["date_range"]
        assert "end" in stats["date_range"]

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, temp_db):
        """Test concurrent database operations."""

        async def store_reflection(i):
            return await temp_db.store_reflection(
                content=f"Concurrent reflection {i}",
                project=f"project-{i % 3}",
                tags=[f"tag-{i}"],
            )

        # Create multiple concurrent operations
        tasks = [store_reflection(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All operations should succeed
        assert all(results)

        # Verify all reflections were stored
        search_results = await temp_db.search_reflections(query="concurrent", limit=20)
        assert len(search_results) == 10

    @pytest.mark.asyncio
    async def test_database_error_handling(self, temp_db):
        """Test database error handling."""
        # Close the database connection to simulate error
        if temp_db.conn:
            temp_db.conn.close()
            temp_db.conn = None

        # Operations should handle the error gracefully
        result = await temp_db.store_reflection(
            content="This should fail",
            project="test",
        )

        # Should return False on failure rather than raising exception
        assert result is False

    @pytest.mark.asyncio
    async def test_large_content_storage(self, temp_db):
        """Test storing large content."""
        large_content = "A" * 10000  # 10KB content

        result = await temp_db.store_reflection(content=large_content, project="test")

        assert result is True

        # Verify retrieval
        results = await temp_db.search_reflections(query="AAAA", limit=1)
        assert len(results) >= 1
        assert len(results[0]["content"]) == 10000

    @pytest.mark.asyncio
    async def test_special_characters_handling(self, temp_db):
        """Test handling of special characters in content."""
        special_content = (
            "Test with special chars: 'quotes', \"double quotes\", <tags>, & ampersand"
        )

        result = await temp_db.store_reflection(
            content=special_content,
            project="special-test",
        )

        assert result is True

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
            project="unicode-test",
        )

        assert result is True

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
            project="tag-test",
            tags=tags,
        )

        assert result is True

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
            project="test",
        )

        # Search with different cases
        for query in ["javascript", "JAVASCRIPT", "JavaScript", "javaScript"]:
            results = await temp_db.search_reflections(query=query, limit=10)
            assert len(results) >= 1, f"Failed to find results for query: {query}"

    @pytest.mark.asyncio
    async def test_performance_large_dataset(self, temp_db, performance_monitor):
        """Test performance with large dataset."""
        performance_monitor.start_monitoring()

        # Store many reflections
        reflections = ReflectionDataFactory.build_batch(100)

        for reflection in reflections:
            await temp_db.store_reflection(
                content=reflection["content"],
                project=reflection["project"],
                tags=reflection.get("tags", []),
            )

        # Perform searches
        for i in range(10):
            await temp_db.search_reflections(query=f"test {i}", limit=5)

        metrics = performance_monitor.stop_monitoring()

        # Performance assertions
        assert metrics["duration"] < 10.0  # Should complete within 10 seconds
        assert metrics["memory_delta"] < 50  # Memory growth less than 50MB

    @pytest.mark.asyncio
    async def test_database_file_permissions(self, temp_db):
        """Test database file has correct permissions."""
        db_path = Path(temp_db.db_path)

        # Check file exists
        assert db_path.exists()

        # Check file is readable and writable
        assert db_path.is_file()

        # Permissions should allow read/write for owner
        stat_info = db_path.stat()
        # Convert to octal string for easier checking
        permissions = oct(stat_info.st_mode)[-3:]

        # Should have at least read/write for owner (6xx)
        assert int(permissions[0]) >= 6


@pytest.mark.asyncio
class TestReflectionDatabaseWithEmbeddings:
    """Test ReflectionDatabase with embedding functionality."""

    @pytest.fixture
    async def temp_db_with_embeddings(self):
        """Create temporary database with embedding support."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_file.close()

        # Mock embedding model availability
        with patch(
            "session_mgmt_mcp.reflection_tools.ReflectionDatabase._load_embedding_model",
        ) as mock_load:
            mock_model = Mock()
            mock_tokenizer = Mock()
            mock_load.return_value = (mock_model, mock_tokenizer)

            db = ReflectionDatabase(temp_file.name)
            await db._ensure_tables()

            yield db, mock_model, mock_tokenizer

        # Cleanup
        try:
            if db.conn:
                db.conn.close()
            Path(temp_file.name).unlink(missing_ok=True)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_embedding_generation(self, temp_db_with_embeddings):
        """Test automatic embedding generation."""
        db, mock_model, mock_tokenizer = temp_db_with_embeddings

        # Configure mocks
        mock_tokenizer.encode.return_value = [1, 2, 3]
        mock_model.predict.return_value = [[0.1, -0.2, 0.3] * 128]  # 384-dim

        result = await db.store_reflection(
            content="Test reflection for embedding",
            project="embedding-test",
        )

        assert result is True
        # Verify tokenizer and model were called
        mock_tokenizer.encode.assert_called_once()
        mock_model.predict.assert_called_once()

    @pytest.mark.asyncio
    async def test_semantic_search(self, temp_db_with_embeddings):
        """Test semantic search with embeddings."""
        db, mock_model, mock_tokenizer = temp_db_with_embeddings

        # Setup mock responses for similar embeddings
        mock_tokenizer.encode.return_value = [1, 2, 3]

        # First embedding (for storage)
        storage_embedding = [0.1, 0.2, 0.3] * 128
        mock_model.predict.return_value = [storage_embedding]

        # Store a reflection
        await db.store_reflection(
            content="Machine learning model training",
            project="ml-project",
        )

        # Search embedding (similar to storage)
        search_embedding = [0.11, 0.21, 0.31] * 128  # Similar values
        mock_model.predict.return_value = [search_embedding]

        results = await db.search_reflections(query="AI model development", limit=5)

        # Should find the stored reflection due to embedding similarity
        assert len(results) >= 1
        assert "machine learning" in results[0]["content"].lower()

    @pytest.mark.asyncio
    async def test_embedding_fallback_to_text_search(self, temp_db):
        """Test fallback to text search when embeddings unavailable."""
        # Store reflection without embeddings
        await temp_db.store_reflection(
            content="Fallback search test content",
            project="fallback-test",
        )

        # Search should still work via text search
        results = await temp_db.search_reflections(query="fallback", limit=5)

        assert len(results) >= 1
        assert "fallback" in results[0]["content"].lower()

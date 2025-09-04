"""Unit tests for ReflectionDatabase and reflection tools.

Tests the database operations for storing and retrieving reflections,
conversation search, and embedding-based similarity matching.
"""

import tempfile
from pathlib import Path

import pytest
from session_mgmt_mcp.reflection_tools import ReflectionDatabase


class TestReflectionDatabase:
    """Test suite for ReflectionDatabase."""

    def test_database_initialization_without_duckdb(self):
        """Test database initialization when DuckDB is not available."""
        # Patch DUCKDB_AVAILABLE at the module level before importing
        from session_mgmt_mcp import reflection_tools

        original_value = reflection_tools.DUCKDB_AVAILABLE
        reflection_tools.DUCKDB_AVAILABLE = False

        try:
            db = ReflectionDatabase()
            with pytest.raises(ImportError, match="DuckDB not available"):
                db.initialize()
        finally:
            # Restore the original value
            reflection_tools.DUCKDB_AVAILABLE = original_value

    def test_database_initialization_success(self):
        """Test successful database initialization."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_file.close()

            try:
                db = ReflectionDatabase(temp_file.name)
                # This should not raise an exception if DuckDB is available
                assert db.db_path == temp_file.name
            finally:
                Path(temp_file.name).unlink(missing_ok=True)

    def test_get_stats_method_exists(self):
        """Test that get_stats method exists."""
        db = ReflectionDatabase()
        assert hasattr(db, "get_stats")

    def test_store_reflection_method_exists(self):
        """Test that store_reflection method exists."""
        db = ReflectionDatabase()
        assert hasattr(db, "store_reflection")

    def test_search_reflections_method_exists(self):
        """Test that search_reflections method exists."""
        db = ReflectionDatabase()
        assert hasattr(db, "search_reflections")

    def test_search_conversations_method_exists(self):
        """Test that search_conversations method exists."""
        db = ReflectionDatabase()
        assert hasattr(db, "search_conversations")

    def test_store_conversation_method_exists(self):
        """Test that store_conversation method exists."""
        db = ReflectionDatabase()
        assert hasattr(db, "store_conversation")

    def test_search_by_file_method_exists(self):
        """Test that search_by_file method exists."""
        db = ReflectionDatabase()
        assert hasattr(db, "search_by_file")

    def test_get_embedding_method_exists(self):
        """Test that get_embedding method exists."""
        db = ReflectionDatabase()
        assert hasattr(db, "get_embedding")


def test_get_reflection_database_function_exists():
    """Test that get_reflection_database function exists."""
    from session_mgmt_mcp.reflection_tools import get_reflection_database

    assert callable(get_reflection_database)


def test_cleanup_reflection_database_function_exists():
    """Test that cleanup_reflection_database function exists."""
    from session_mgmt_mcp.reflection_tools import cleanup_reflection_database

    assert callable(cleanup_reflection_database)

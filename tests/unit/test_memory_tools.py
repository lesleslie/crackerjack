#!/usr/bin/env python3
"""Unit tests for memory tools.

Tests the MCP tools for storing, searching, and managing reflections and conversation memories.
"""

from unittest.mock import AsyncMock, patch

import pytest
from session_mgmt_mcp.tools.memory_tools import (
    _check_reflection_tools_available,
    _quick_search_impl,
    _reflection_stats_impl,
    _reset_reflection_database_impl,
    _search_by_concept_impl,
    _search_by_file_impl,
    _search_summary_impl,
    _store_reflection_impl,
)


class TestMemoryToolsAvailability:
    """Test reflection tools availability checking."""

    def test_check_reflection_tools_available_when_none(self):
        """Test availability check when status is unknown."""
        # Reset the global state
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = None

        # Mock the import check to return True
        with patch("importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = True
            result = _check_reflection_tools_available()
            assert result is True

    def test_check_reflection_tools_available_when_false(self):
        """Test availability check when tools are known to be unavailable."""
        # Set the global state to False
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = False

        result = _check_reflection_tools_available()
        assert result is False

    def test_check_reflection_tools_available_when_true(self):
        """Test availability check when tools are known to be available."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        result = _check_reflection_tools_available()
        assert result is True

    def test_check_reflection_tools_import_error(self):
        """Test availability check when import fails."""
        # Reset the global state
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = None

        # Mock the import check to raise ImportError
        with patch("importlib.util.find_spec", side_effect=ImportError):
            result = _check_reflection_tools_available()
            assert result is False


class TestStoreReflectionImpl:
    """Test store reflection implementation."""

    @pytest.mark.asyncio
    async def test_store_reflection_when_tools_unavailable(self):
        """Test storing reflection when tools are unavailable."""
        # Set the global state to False
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = False

        result = await _store_reflection_impl("Test content")
        assert "Reflection tools not available" in result

    @pytest.mark.asyncio
    async def test_store_reflection_success(self):
        """Test successful reflection storage."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database and its store_reflection method
        mock_db = AsyncMock()
        mock_db.store_reflection = AsyncMock(return_value="test-id-123")

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _store_reflection_impl("Test content", ["tag1", "tag2"])

            assert "Reflection stored successfully" in result
            assert "Test content" in result
            assert "tag1, tag2" in result
            mock_db.store_reflection.assert_called_once_with(
                "Test content", tags=["tag1", "tag2"]
            )

    @pytest.mark.asyncio
    async def test_store_reflection_failure(self):
        """Test reflection storage failure."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database to raise an exception
        mock_db = AsyncMock()
        mock_db.store_reflection = AsyncMock(side_effect=Exception("Database error"))

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _store_reflection_impl("Test content")

            assert "Error storing reflection" in result
            assert "Database error" in result

    @pytest.mark.asyncio
    async def test_store_reflection_without_tags(self):
        """Test storing reflection without tags."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database
        mock_db = AsyncMock()
        mock_db.store_reflection = AsyncMock(return_value="test-id-456")

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _store_reflection_impl("Test content without tags")

            assert "Reflection stored successfully" in result
            assert "Test content without tags" in result
            mock_db.store_reflection.assert_called_once_with(
                "Test content without tags", tags=[]
            )


class TestQuickSearchImpl:
    """Test quick search implementation."""

    @pytest.mark.asyncio
    async def test_quick_search_when_tools_unavailable(self):
        """Test quick search when tools are unavailable."""
        # Set the global state to False
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = False

        result = await _quick_search_impl("test query")
        assert "Reflection tools not available" in result

    @pytest.mark.asyncio
    async def test_quick_search_with_results(self):
        """Test quick search with results."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database and search results
        mock_db = AsyncMock()
        mock_results = [
            {
                "content": "Test result content",
                "project": "test-project",
                "score": 0.85,
                "timestamp": "2023-01-01T12:00:00Z",
            }
        ]
        mock_db.search_reflections = AsyncMock(return_value=mock_results)

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _quick_search_impl("test query", min_score=0.7)

            assert "Quick search for: 'test query'" in result
            assert "Test result content" in result
            assert "test-project" in result
            assert "0.85" in result
            mock_db.search_reflections.assert_called_once_with(
                query="test query", project=None, limit=1, min_score=0.7
            )

    @pytest.mark.asyncio
    async def test_quick_search_no_results(self):
        """Test quick search with no results."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database with no results
        mock_db = AsyncMock()
        mock_db.search_reflections = AsyncMock(return_value=[])

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _quick_search_impl("nonexistent query")

            assert "No results found" in result
            assert "nonexistent query" in result

    @pytest.mark.asyncio
    async def test_quick_search_with_exception(self):
        """Test quick search with exception."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database to raise an exception
        mock_db = AsyncMock()
        mock_db.search_reflections = AsyncMock(side_effect=Exception("Search error"))

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _quick_search_impl("test query")

            assert "Search error" in result


class TestSearchSummaryImpl:
    """Test search summary implementation."""

    @pytest.mark.asyncio
    async def test_search_summary_when_tools_unavailable(self):
        """Test search summary when tools are unavailable."""
        # Set the global state to False
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = False

        result = await _search_summary_impl("test query")
        assert "Reflection tools not available" in result

    @pytest.mark.asyncio
    async def test_search_summary_with_results(self):
        """Test search summary with results."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database and search results
        mock_db = AsyncMock()
        mock_results = [
            {
                "content": "Result 1 content",
                "project": "project-a",
                "score": 0.9,
                "timestamp": "2023-01-01T12:00:00Z",
            },
            {
                "content": "Result 2 content",
                "project": "project-b",
                "score": 0.8,
                "timestamp": "2023-01-02T12:00:00Z",
            },
            {
                "content": "Result 3 content",
                "project": "project-a",
                "score": 0.75,
                "timestamp": "2023-01-03T12:00:00Z",
            },
        ]
        mock_db.search_reflections = AsyncMock(return_value=mock_results)

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _search_summary_impl("test query")

            assert "Search Summary for: 'test query'" in result
            assert "Total results: 3" in result
            assert "project-a" in result
            assert "project-b" in result
            mock_db.search_reflections.assert_called_once_with(
                query="test query", project=None, limit=20, min_score=0.7
            )

    @pytest.mark.asyncio
    async def test_search_summary_no_results(self):
        """Test search summary with no results."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database with no results
        mock_db = AsyncMock()
        mock_db.search_reflections = AsyncMock(return_value=[])

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _search_summary_impl("nonexistent query")

            assert "No results found" in result

    @pytest.mark.asyncio
    async def test_search_summary_with_exception(self):
        """Test search summary with exception."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database to raise an exception
        mock_db = AsyncMock()
        mock_db.search_reflections = AsyncMock(side_effect=Exception("Search error"))

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _search_summary_impl("test query")

            assert "Search summary error" in result


class TestSearchByFileImpl:
    """Test search by file implementation."""

    @pytest.mark.asyncio
    async def test_search_by_file_when_tools_unavailable(self):
        """Test search by file when tools are unavailable."""
        # Set the global state to False
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = False

        result = await _search_by_file_impl("test_file.py")
        assert "Reflection tools not available" in result

    @pytest.mark.asyncio
    async def test_search_by_file_with_results(self):
        """Test search by file with results."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database and search results
        mock_db = AsyncMock()
        mock_results = [
            {
                "content": "Discussion about test_file.py implementation",
                "project": "test-project",
                "score": 0.85,
                "timestamp": "2023-01-01T12:00:00Z",
            }
        ]
        mock_db.search_reflections = AsyncMock(return_value=mock_results)

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _search_by_file_impl("test_file.py", limit=5)

            assert "Searching conversations about: test_file.py" in result
            assert "Found 1 relevant conversations" in result
            assert "test_file.py" in result
            mock_db.search_reflections.assert_called_once_with(
                query="test_file.py", project=None, limit=5
            )

    @pytest.mark.asyncio
    async def test_search_by_file_no_results(self):
        """Test search by file with no results."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database with no results
        mock_db = AsyncMock()
        mock_db.search_reflections = AsyncMock(return_value=[])

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _search_by_file_impl("nonexistent.py")

            assert "No conversations found about this file" in result

    @pytest.mark.asyncio
    async def test_search_by_file_with_exception(self):
        """Test search by file with exception."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database to raise an exception
        mock_db = AsyncMock()
        mock_db.search_reflections = AsyncMock(side_effect=Exception("Search error"))

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _search_by_file_impl("test_file.py")

            assert "File search error" in result


class TestSearchByConceptImpl:
    """Test search by concept implementation."""

    @pytest.mark.asyncio
    async def test_search_by_concept_when_tools_unavailable(self):
        """Test search by concept when tools are unavailable."""
        # Set the global state to False
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = False

        result = await _search_by_concept_impl("authentication")
        assert "Reflection tools not available" in result

    @pytest.mark.asyncio
    async def test_search_by_concept_with_results(self):
        """Test search by concept with results."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database and search results
        mock_db = AsyncMock()
        mock_results = [
            {
                "content": "Discussion about authentication patterns",
                "project": "auth-service",
                "score": 0.9,
                "timestamp": "2023-01-01T12:00:00Z",
            }
        ]
        mock_db.search_reflections = AsyncMock(return_value=mock_results)

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _search_by_concept_impl("authentication", limit=5)

            assert "Searching for concept: 'authentication'" in result
            assert "Found 1 related conversations" in result
            assert "authentication" in result
            mock_db.search_reflections.assert_called_once_with(
                query="authentication", project=None, limit=5
            )

    @pytest.mark.asyncio
    async def test_search_by_concept_no_results(self):
        """Test search by concept with no results."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database with no results
        mock_db = AsyncMock()
        mock_db.search_reflections = AsyncMock(return_value=[])

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _search_by_concept_impl("nonexistent_concept")

            assert "No conversations found about this concept" in result

    @pytest.mark.asyncio
    async def test_search_by_concept_with_exception(self):
        """Test search by concept with exception."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database to raise an exception
        mock_db = AsyncMock()
        mock_db.search_reflections = AsyncMock(side_effect=Exception("Search error"))

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _search_by_concept_impl("authentication")

            assert "Concept search error" in result


class TestReflectionStatsImpl:
    """Test reflection stats implementation."""

    @pytest.mark.asyncio
    async def test_reflection_stats_when_tools_unavailable(self):
        """Test reflection stats when tools are unavailable."""
        # Set the global state to False
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = False

        result = await _reflection_stats_impl()
        assert "Reflection tools not available" in result

    @pytest.mark.asyncio
    async def test_reflection_stats_success(self):
        """Test successful reflection stats retrieval."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database and stats
        mock_db = AsyncMock()
        mock_stats = {
            "total_reflections": 42,
            "projects": 5,
            "date_range": {"start": "2023-01-01", "end": "2023-12-31"},
        }
        mock_db.get_reflection_stats = AsyncMock(return_value=mock_stats)

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _reflection_stats_impl()

            assert "Reflection Database Statistics" in result
            assert "Total reflections: 42" in result
            assert "Projects: 5" in result
            mock_db.get_reflection_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_reflection_stats_with_exception(self):
        """Test reflection stats with exception."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database to raise an exception
        mock_db = AsyncMock()
        mock_db.get_reflection_stats = AsyncMock(side_effect=Exception("Stats error"))

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            result = await _reflection_stats_impl()

            assert "Stats error" in result


class TestResetReflectionDatabaseImpl:
    """Test reset reflection database implementation."""

    @pytest.mark.asyncio
    async def test_reset_reflection_database_when_tools_unavailable(self):
        """Test reset reflection database when tools are unavailable."""
        # Set the global state to False
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = False

        result = await _reset_reflection_database_impl()
        assert "Reflection tools not available" in result

    @pytest.mark.asyncio
    async def test_reset_reflection_database_success(self):
        """Test successful reflection database reset."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database connection
        mock_db = AsyncMock()
        mock_db.conn = AsyncMock()
        mock_db.conn.close = AsyncMock()

        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            return_value=mock_db,
        ):
            # Set up the global database instance
            from session_mgmt_mcp.tools import memory_tools

            memory_tools._reflection_db = mock_db

            result = await _reset_reflection_database_impl()

            assert "Reflection database connection reset" in result
            assert "New connection established successfully" in result
            # Verify the old connection was closed
            mock_db.conn.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_reflection_database_with_exception(self):
        """Test reflection database reset with exception."""
        # Set the global state to True
        from session_mgmt_mcp.tools import memory_tools

        memory_tools._reflection_tools_available = True

        # Mock the database to raise an exception
        with patch(
            "session_mgmt_mcp.tools.memory_tools._get_reflection_database",
            side_effect=Exception("Reset error"),
        ):
            result = await _reset_reflection_database_impl()

            assert "Reset error" in result

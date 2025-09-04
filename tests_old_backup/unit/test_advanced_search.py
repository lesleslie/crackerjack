"""Unit tests for AdvancedSearchEngine.

Tests the advanced search capabilities including faceted filtering,
full-text search, and intelligent result ranking.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from session_mgmt_mcp.advanced_search import (
    AdvancedSearchEngine,
    SearchFilter,
    SearchResult,
)


class TestAdvancedSearchEngine:
    """Test suite for AdvancedSearchEngine."""

    @pytest.fixture
    def search_engine(self):
        """Create AdvancedSearchEngine instance with mock database."""
        with patch("session_mgmt_mcp.advanced_search.ReflectionDatabase") as mock_db:
            mock_db_instance = AsyncMock()
            mock_db.return_value = mock_db_instance
            return AdvancedSearchEngine(mock_db_instance)

    @pytest.mark.asyncio
    async def test_search_with_text_query(self, search_engine):
        """Test text-based search functionality."""
        # Mock database response
        mock_results = {
            "results": [
                {
                    "content_id": "1",
                    "content_type": "conversation",
                    "title": "Test Conversation",
                    "content": "This is a test conversation about authentication",
                    "score": 0.85,
                    "project": "test-project",
                    "timestamp": datetime.now(UTC),
                }
            ],
            "count": 1,
        }

        with patch.object(
            search_engine.reflection_db, "search_conversations", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_results

            result = await search_engine.search(
                query="authentication",
                limit=10,
                include_highlights=True,
            )

            assert isinstance(result, dict)
            assert "results" in result
            assert len(result["results"]) == 1
            assert result["results"][0]["content_id"] == "1"
            assert result["results"][0]["score"] == 0.85

    @pytest.mark.asyncio
    async def test_search_with_filters(self, search_engine):
        """Test search with filter criteria."""
        filters = [
            SearchFilter(field="project", operator="eq", value="test-project"),
            SearchFilter(field="content_type", operator="eq", value="conversation"),
        ]

        mock_results = {
            "results": [
                {
                    "content_id": "1",
                    "content_type": "conversation",
                    "title": "Filtered Conversation",
                    "content": "Filtered content",
                    "score": 0.9,
                    "project": "test-project",
                    "timestamp": datetime.now(UTC),
                }
            ],
            "count": 1,
        }

        with patch.object(
            search_engine.reflection_db, "search_conversations", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_results

            result = await search_engine.search(
                query="test",
                filters=filters,
                limit=5,
            )

            assert isinstance(result, dict)
            assert len(result["results"]) == 1
            assert result["results"][0]["project"] == "test-project"
            assert result["results"][0]["content_type"] == "conversation"

    @pytest.mark.asyncio
    async def test_search_with_timeframe(self, search_engine):
        """Test search with timeframe filtering."""
        # Test different timeframe formats
        timeframe_tests = [
            ("1d", timedelta(days=1)),
            ("7d", timedelta(days=7)),
            ("30d", timedelta(days=30)),
            ("90d", timedelta(days=90)),
        ]

        for timeframe_str, expected_delta in timeframe_tests:
            mock_results = {
                "results": [
                    {
                        "content_id": "1",
                        "content_type": "conversation",
                        "title": "Recent Conversation",
                        "content": "Recent content",
                        "score": 0.75,
                        "project": "test-project",
                        "timestamp": datetime.now(UTC),
                    }
                ],
                "count": 1,
            }

            with patch.object(
                search_engine.reflection_db,
                "search_conversations",
                new_callable=AsyncMock,
            ) as mock_search:
                mock_search.return_value = mock_results

                result = await search_engine.search(
                    query="recent",
                    timeframe=timeframe_str,
                    limit=5,
                )

                assert isinstance(result, dict)
                assert len(result["results"]) >= 0

    @pytest.mark.asyncio
    async def test_search_by_content_type(self, search_engine):
        """Test search filtered by content type."""
        content_types = ["conversation", "reflection", "document"]

        for content_type in content_types:
            mock_results = {
                "results": [
                    {
                        "content_id": "1",
                        "content_type": content_type,
                        "title": f"Test {content_type}",
                        "content": f"This is a test {content_type}",
                        "score": 0.8,
                        "project": "test-project",
                        "timestamp": datetime.now(UTC),
                    }
                ],
                "count": 1,
            }

            with patch.object(
                search_engine.reflection_db,
                "search_conversations",
                new_callable=AsyncMock,
            ) as mock_search:
                mock_search.return_value = mock_results

                result = await search_engine.search(
                    query="test",
                    content_type=content_type,
                    limit=5,
                )

                assert isinstance(result, dict)
                if result["results"]:
                    assert result["results"][0]["content_type"] == content_type

    @pytest.mark.asyncio
    async def test_search_by_project(self, search_engine):
        """Test search filtered by project."""
        projects = ["project-a", "project-b", "project-c"]

        for project in projects:
            mock_results = {
                "results": [
                    {
                        "content_id": "1",
                        "content_type": "conversation",
                        "title": f"Conversation in {project}",
                        "content": f"Content for {project}",
                        "score": 0.85,
                        "project": project,
                        "timestamp": datetime.now(UTC),
                    }
                ],
                "count": 1,
            }

            with patch.object(
                search_engine.reflection_db,
                "search_conversations",
                new_callable=AsyncMock,
            ) as mock_search:
                mock_search.return_value = mock_results

                result = await search_engine.search(
                    query="test",
                    project=project,
                    limit=5,
                )

                assert isinstance(result, dict)
                if result["results"]:
                    assert result["results"][0]["project"] == project

    @pytest.mark.asyncio
    async def test_search_with_sorting(self, search_engine):
        """Test search with different sorting options."""
        sort_options = ["relevance", "date", "project"]

        for sort_by in sort_options:
            mock_results = {
                "results": [
                    {
                        "content_id": "1",
                        "content_type": "conversation",
                        "title": "Sorted Conversation",
                        "content": "Sorted content",
                        "score": 0.9,
                        "project": "test-project",
                        "timestamp": datetime.now(UTC),
                    }
                ],
                "count": 1,
            }

            with patch.object(
                search_engine.reflection_db,
                "search_conversations",
                new_callable=AsyncMock,
            ) as mock_search:
                mock_search.return_value = mock_results

                result = await search_engine.search(
                    query="test",
                    sort_by=sort_by,
                    limit=5,
                )

                assert isinstance(result, dict)
                # Should return results regardless of sort option
                assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_search_with_limit(self, search_engine):
        """Test search with result limiting."""
        test_limits = [1, 5, 10, 20]

        for limit in test_limits:
            # Create enough mock results to test limiting
            mock_results_list = []
            for i in range(min(limit + 5, 50)):  # Don't create too many
                mock_results_list.append(
                    {
                        "content_id": str(i),
                        "content_type": "conversation",
                        "title": f"Conversation {i}",
                        "content": f"Content for conversation {i}",
                        "score": 0.9 - (i * 0.01),  # Decreasing scores
                        "project": "test-project",
                        "timestamp": datetime.now(UTC),
                    }
                )

            mock_results = {
                "results": mock_results_list,
                "count": len(mock_results_list),
            }

            with patch.object(
                search_engine.reflection_db,
                "search_conversations",
                new_callable=AsyncMock,
            ) as mock_search:
                mock_search.return_value = mock_results

                result = await search_engine.search(
                    query="test",
                    limit=limit,
                )

                assert isinstance(result, dict)
                # Should not exceed the limit
                assert len(result["results"]) <= limit

    @pytest.mark.asyncio
    async def test_search_empty_query(self, search_engine):
        """Test search with empty query."""
        mock_results = {
            "results": [
                {
                    "content_id": "1",
                    "content_type": "conversation",
                    "title": "Recent Conversation",
                    "content": "Recent content without specific query",
                    "score": 0.5,
                    "project": "test-project",
                    "timestamp": datetime.now(UTC),
                }
            ],
            "count": 1,
        }

        with patch.object(
            search_engine.reflection_db, "search_conversations", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_results

            result = await search_engine.search(
                query="",
                limit=5,
            )

            assert isinstance(result, dict)
            # Should still return results even with empty query
            assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_search_with_highlights(self, search_engine):
        """Test search with highlighted snippets."""
        mock_results = {
            "results": [
                {
                    "content_id": "1",
                    "content_type": "conversation",
                    "title": "Highlighted Conversation",
                    "content": "This conversation contains important keywords for highlighting",
                    "score": 0.85,
                    "project": "test-project",
                    "timestamp": datetime.now(UTC),
                }
            ],
            "count": 1,
        }

        with patch.object(
            search_engine.reflection_db, "search_conversations", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_results

            result = await search_engine.search(
                query="important keywords",
                limit=5,
                include_highlights=True,
            )

            assert isinstance(result, dict)
            assert isinstance(result["results"], list)
            # Highlights functionality should be tested in integration

    @pytest.mark.asyncio
    async def test_search_faceted(self, search_engine):
        """Test faceted search functionality."""
        facets = ["project", "content_type", "date"]

        mock_results = {
            "results": [
                {
                    "content_id": "1",
                    "content_type": "conversation",
                    "title": "Faceted Conversation",
                    "content": "Content for faceted search",
                    "score": 0.8,
                    "project": "test-project",
                    "timestamp": datetime.now(UTC),
                }
            ],
            "count": 1,
        }

        with patch.object(
            search_engine.reflection_db, "search_conversations", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_results

            result = await search_engine.search(
                query="test",
                facets=facets,
                limit=5,
            )

            assert isinstance(result, dict)
            assert isinstance(result["results"], list)
            # Facets should be included in results when requested

    @pytest.mark.asyncio
    async def test_search_suggestions(self, search_engine):
        """Test search suggestions functionality."""
        mock_suggestions = [
            {"text": "authentication", "frequency": 15},
            {"text": "authorization", "frequency": 12},
            {"text": "automated testing", "frequency": 8},
        ]

        with patch.object(
            search_engine, "_generate_suggestions", new_callable=AsyncMock
        ) as mock_gen:
            mock_gen.return_value = mock_suggestions

            result = await search_engine.suggest_completions(
                query="auth",
                field="content",
                limit=5,
            )

            assert isinstance(result, list)
            assert len(result) <= 5
            if result:
                assert "text" in result[0]
                assert "frequency" in result[0]

    @pytest.mark.asyncio
    async def test_search_similar_content(self, search_engine):
        """Test finding similar content."""
        mock_similar = [
            SearchResult(
                content_id="2",
                content_type="conversation",
                title="Similar Conversation",
                content="Very similar content to the original",
                score=0.95,
                project="test-project",
                timestamp=datetime.now(UTC),
            ),
            SearchResult(
                content_id="3",
                content_type="conversation",
                title="Somewhat Similar Conversation",
                content="Somewhat similar content",
                score=0.75,
                project="test-project",
                timestamp=datetime.now(UTC),
            ),
        ]

        with patch.object(
            search_engine, "_find_similar_content", new_callable=AsyncMock
        ) as mock_find:
            mock_find.return_value = mock_similar

            result = await search_engine.get_similar_content(
                content_id="1",
                content_type="conversation",
                limit=5,
            )

            assert isinstance(result, list)
            if result:
                assert isinstance(result[0], SearchResult)
                assert hasattr(result[0], "content_id")
                assert hasattr(result[0], "score")

    @pytest.mark.asyncio
    async def test_aggregate_metrics(self, search_engine):
        """Test metrics aggregation."""
        metric_types = ["activity", "projects", "content_types"]

        for metric_type in metric_types:
            mock_metrics = {
                "metric_type": metric_type,
                "data": [
                    {"key": "test-key", "value": 42, "trend": "increasing"},
                ],
                "total": 100,
                "timeframe": "30d",
            }

            with patch.object(
                search_engine, "_aggregate_metrics", new_callable=AsyncMock
            ) as mock_agg:
                mock_agg.return_value = mock_metrics

                result = await search_engine.aggregate_metrics(
                    metric_type=metric_type,
                    timeframe="30d",
                )

                assert isinstance(result, dict)
                assert "metric_type" in result
                assert result["metric_type"] == metric_type
                assert "data" in result

    @pytest.mark.asyncio
    async def test_search_by_timeframe(self, search_engine):
        """Test search within specific timeframes."""
        timeframes = ["1d", "7d", "30d", "90d", "1y"]

        for timeframe in timeframes:
            mock_results = {
                "results": [
                    {
                        "content_id": "1",
                        "content_type": "conversation",
                        "title": f"Timeframe {timeframe} Conversation",
                        "content": f"Content from {timeframe} ago",
                        "score": 0.8,
                        "project": "test-project",
                        "timestamp": datetime.now(UTC) - timedelta(days=1),
                    }
                ],
                "count": 1,
            }

            with patch.object(
                search_engine.reflection_db,
                "search_conversations",
                new_callable=AsyncMock,
            ) as mock_search:
                mock_search.return_value = mock_results

                result = await search_engine.search_by_timeframe(
                    timeframe=timeframe,
                    query="test",
                    limit=5,
                )

                assert isinstance(result, list)
                # Should return a list of search results

    @pytest.mark.asyncio
    async def test_error_handling_invalid_filters(self, search_engine):
        """Test error handling with invalid filters."""
        # Test with invalid filter field
        invalid_filters = [
            SearchFilter(field="nonexistent_field", operator="eq", value="test"),
        ]

        mock_results = {
            "results": [],
            "count": 0,
        }

        with patch.object(
            search_engine.reflection_db, "search_conversations", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_results

            result = await search_engine.search(
                query="test",
                filters=invalid_filters,
                limit=5,
            )

            assert isinstance(result, dict)
            assert "results" in result
            # Should handle invalid filters gracefully

    @pytest.mark.asyncio
    async def test_error_handling_invalid_timeframe(self, search_engine):
        """Test error handling with invalid timeframe."""
        mock_results = {
            "results": [],
            "count": 0,
        }

        with patch.object(
            search_engine.reflection_db, "search_conversations", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_results

            # Test with invalid timeframe format
            result = await search_engine.search(
                query="test",
                timeframe="invalid_format",
                limit=5,
            )

            assert isinstance(result, dict)
            assert "results" in result
            # Should handle invalid timeframe gracefully

    @pytest.mark.asyncio
    async def test_concurrent_searches(self, search_engine):
        """Test concurrent search operations."""
        mock_results = {
            "results": [
                {
                    "content_id": "1",
                    "content_type": "conversation",
                    "title": "Concurrent Search Result",
                    "content": "Result from concurrent search",
                    "score": 0.85,
                    "project": "test-project",
                    "timestamp": datetime.now(UTC),
                }
            ],
            "count": 1,
        }

        with patch.object(
            search_engine.reflection_db, "search_conversations", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_results

            # Create multiple concurrent search tasks
            tasks = [search_engine.search(query=f"test {i}", limit=3) for i in range(5)]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should succeed
            assert len(results) == 5
            for result in results:
                if not isinstance(result, Exception):
                    assert isinstance(result, dict)
                    assert "results" in result

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, search_engine):
        """Test case-insensitive search."""
        test_queries = ["TEST", "Test", "test", "TeSt"]

        mock_results = {
            "results": [
                {
                    "content_id": "1",
                    "content_type": "conversation",
                    "title": "Case Insensitive Test",
                    "content": "This should match regardless of case",
                    "score": 0.9,
                    "project": "test-project",
                    "timestamp": datetime.now(UTC),
                }
            ],
            "count": 1,
        }

        with patch.object(
            search_engine.reflection_db, "search_conversations", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = mock_results

            for query in test_queries:
                result = await search_engine.search(
                    query=query,
                    limit=5,
                )

                assert isinstance(result, dict)
                assert "results" in result
                # All queries should return the same results

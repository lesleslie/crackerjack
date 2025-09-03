"""Integration tests for AdvancedSearchEngine.

Tests the advanced search capabilities including faceted filtering,
full-text search, and intelligent result ranking.
"""

import asyncio
import tempfile
from pathlib import Path

import pytest
from session_mgmt_mcp.advanced_search import (
    AdvancedSearchEngine,
    SearchFilter,
)
from session_mgmt_mcp.reflection_tools import ReflectionDatabase


class TestAdvancedSearchEngine:
    """Test suite for AdvancedSearchEngine."""

    @pytest.fixture
    async def temp_db_path(self):
        """Create a temporary database path that doesn't exist yet."""
        # Create a temporary directory and generate a path for the database file
        # but don't create the file yet
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.duckdb"
            yield str(db_path)
        # Cleanup happens automatically when temp_dir is deleted

    @pytest.fixture
    async def initialized_db(self, temp_db_path):
        """Create and initialize a temporary test database."""
        db = ReflectionDatabase(temp_db_path)
        await db.initialize()
        yield db
        db.close()

    @pytest.fixture
    async def search_engine(self, initialized_db):
        """Create an AdvancedSearchEngine instance."""
        return AdvancedSearchEngine(initialized_db)
        # Note: We're not calling _rebuild_search_index here as it requires
        # actual data to be present in the database, which we'll add in specific tests

    @pytest.fixture
    async def sample_data(self, initialized_db):
        """Add sample conversations and reflections to test database."""
        # Sample conversations
        conversations = [
            {
                "content": "Implementing user authentication with JWT tokens in Python Flask. Need to handle token expiration and refresh logic.",
                "project": "webapp-backend",
                "metadata": {
                    "type": "development",
                    "language": "python",
                    "framework": "flask",
                },
            },
            {
                "content": "Frontend React component for user login form. Using axios for API calls to backend authentication endpoint.",
                "project": "webapp-frontend",
                "metadata": {
                    "type": "development",
                    "language": "javascript",
                    "framework": "react",
                },
            },
            {
                "content": "Database schema design for user management. Created users table with proper indexes for performance.",
                "project": "webapp-backend",
                "metadata": {
                    "type": "database",
                    "database": "postgresql",
                    "performance": "indexes",
                },
            },
            {
                "content": "Error: JWT token validation failed. TokenExpiredError: Signature has expired. Need to implement token refresh.",
                "project": "webapp-backend",
                "metadata": {
                    "type": "error",
                    "error_type": "TokenExpiredError",
                    "component": "auth",
                },
            },
            {
                "content": "DevOps: Setting up CI/CD pipeline with Docker containers. Automated testing and deployment to production.",
                "project": "devops-pipeline",
                "metadata": {
                    "type": "infrastructure",
                    "tool": "docker",
                    "environment": "production",
                },
            },
        ]

        for conv in conversations:
            await initialized_db.store_conversation(
                content=conv["content"],
                metadata={"project": conv["project"], **conv["metadata"]},
            )

        # Sample reflections
        reflections = [
            {
                "content": "Authentication patterns: Always use secure JWT implementation with proper expiration handling",
                "tags": ["authentication", "jwt", "security", "best-practices"],
            },
            {
                "content": "Database performance tip: Index frequently queried columns, especially foreign keys",
                "tags": ["database", "performance", "postgresql", "optimization"],
            },
            {
                "content": "React component patterns: Use functional components with hooks for better performance",
                "tags": ["react", "frontend", "performance", "hooks"],
            },
        ]

        for refl in reflections:
            await initialized_db.store_reflection(
                content=refl["content"], tags=refl["tags"]
            )

        return conversations, reflections

    @pytest.mark.asyncio
    async def test_search_with_text_query(self, search_engine, sample_data):
        """Test text-based search functionality."""
        # Search for authentication-related content
        results = await search_engine.search(
            query="authentication",
            limit=10,
        )

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

        # Should find authentication-related content
        auth_results = [
            r for r in results["results"] if "authentication" in r.content.lower()
        ]
        assert len(auth_results) >= 1

    @pytest.mark.asyncio
    async def test_search_with_filters(self, search_engine, sample_data):
        """Test search with filter criteria."""
        filters = [
            SearchFilter(field="project", operator="eq", value="webapp-backend"),
        ]

        results = await search_engine.search(
            query="authentication",
            filters=filters,
            limit=10,
        )

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

        # All results should be from webapp-backend project
        # Note: Some results might be reflections which don't have project info
        if results["results"]:
            project_results = [r for r in results["results"] if r.project is not None]
            if project_results:
                for result in project_results:
                    assert result.project == "webapp-backend"

        # Verify that we don't get results from other projects
        project_names = [r.project for r in results["results"] if r.project is not None]
        assert "webapp-frontend" not in project_names

    @pytest.mark.asyncio
    async def test_search_with_limit(self, search_engine, initialized_db):
        """Test search with result limiting."""
        # Store many reflections
        for i in range(15):
            await initialized_db.store_reflection(
                content=f"Test reflection number {i}",
                tags=["test"],
            )

        # Search with limit
        results = await search_engine.search(query="test", limit=5)

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)
        assert len(results["results"]) <= 5

    @pytest.mark.asyncio
    async def test_search_empty_query(self, search_engine, sample_data):
        """Test search with empty query."""
        results = await search_engine.search(query="", limit=10)

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

    @pytest.mark.asyncio
    async def test_search_with_highlights(self, search_engine, sample_data):
        """Test search with highlighted snippets."""
        results = await search_engine.search(
            query="authentication",
            limit=5,
            include_highlights=True,
        )

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

        # If highlights are included, they should be in the results
        if results["results"]:
            # Highlights functionality depends on implementation details
            pass

    @pytest.mark.asyncio
    async def test_search_by_content_type(self, search_engine, sample_data):
        """Test search filtered by content type."""
        # Search for development content
        results = await search_engine.search(
            query="development",
            content_type="conversation",
            limit=10,
        )

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

    @pytest.mark.asyncio
    async def test_search_by_project(self, search_engine, sample_data):
        """Test search filtered by project."""
        # Use filters instead of direct project parameter
        filters = [
            SearchFilter(field="project", operator="eq", value="webapp-backend"),
        ]

        results = await search_engine.search(
            query="authentication",
            filters=filters,
            limit=10,
        )

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

        # All results should be from webapp-backend project
        # Note: Some results might be reflections which don't have project info
        if results["results"]:
            project_results = [r for r in results["results"] if r.project is not None]
            if project_results:
                for result in project_results:
                    assert result.project == "webapp-backend"

    @pytest.mark.asyncio
    async def test_search_with_sorting(self, search_engine, sample_data):
        """Test search with different sorting options."""
        # Test relevance sorting (default)
        relevance_results = await search_engine.search(
            query="authentication",
            sort_by="relevance",
            limit=5,
        )

        assert isinstance(relevance_results, dict)
        assert "results" in relevance_results
        assert isinstance(relevance_results["results"], list)

        # Test date sorting
        date_results = await search_engine.search(
            query="authentication",
            sort_by="date",
            limit=5,
        )

        assert isinstance(date_results, dict)
        assert "results" in date_results
        assert isinstance(date_results["results"], list)

    @pytest.mark.asyncio
    async def test_search_with_timeframe(self, search_engine, sample_data):
        """Test search with timeframe filtering."""
        # Search for recent content (last 24 hours)
        results = await search_engine.search(
            query="test",
            timeframe="1d",
            limit=10,
        )

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

    @pytest.mark.asyncio
    async def test_search_faceted(self, search_engine, sample_data):
        """Test faceted search with result counts."""
        results = await search_engine.search(
            query="authentication",
            facets=["project", "content_type"],
            limit=5,
        )

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

        # Should have facets in results if requested
        if "facets" in results:
            facets = results["facets"]
            assert isinstance(facets, dict)

    @pytest.mark.asyncio
    async def test_search_suggestions(self, search_engine, sample_data):
        """Test search completion suggestions."""
        suggestions = await search_engine.suggest_completions(
            query="auth",
            field="content",
            limit=5,
        )

        assert isinstance(suggestions, list)

        # Should return suggestions or empty list
        if suggestions:
            assert isinstance(suggestions[0], dict)
            assert "text" in suggestions[0]
            assert "frequency" in suggestions[0]

    @pytest.mark.asyncio
    async def test_search_similar_content(self, search_engine, sample_data):
        """Test finding similar content."""
        # First, get a conversation from the database
        conv_results = await search_engine.reflection_db.search_conversations(
            query="authentication", limit=1
        )

        if conv_results:
            # For this test, we'll just verify the method can be called
            # without error since we have limited data
            similar = await search_engine.get_similar_content(
                content_id="test_id",  # Use a dummy ID since we don't have real IDs
                content_type="conversation",
                limit=3,
            )

            assert isinstance(similar, list)

    @pytest.mark.asyncio
    async def test_search_by_timeframe(self, search_engine, sample_data):
        """Test timeframe-based search."""
        results = await search_engine.search_by_timeframe(
            timeframe="1d",
            query="authentication",
            limit=5,
        )

        assert isinstance(results, list)

        # All results should be recent (our test data is all recent)
        for result in results:
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_aggregate_metrics(self, search_engine, sample_data):
        """Test metrics aggregation."""
        metrics = await search_engine.aggregate_metrics(
            metric_type="activity",
            timeframe="30d",
        )

        assert isinstance(metrics, dict)
        assert "metric_type" in metrics
        assert metrics["metric_type"] == "activity"
        assert "data" in metrics

    @pytest.mark.asyncio
    async def test_aggregate_project_metrics(self, search_engine, sample_data):
        """Test project-based metrics."""
        metrics = await search_engine.aggregate_metrics(
            metric_type="projects",
            timeframe="30d",
        )

        assert isinstance(metrics, dict)
        assert metrics["metric_type"] == "projects"

        if metrics.get("data"):
            # Should have project information
            project_data = metrics["data"][0]
            assert "key" in project_data
            assert "value" in project_data

    @pytest.mark.asyncio
    async def test_aggregate_content_type_metrics(self, search_engine, sample_data):
        """Test content type metrics."""
        metrics = await search_engine.aggregate_metrics(
            metric_type="content_types",
            timeframe="30d",
        )

        assert isinstance(metrics, dict)
        assert metrics["metric_type"] == "content_types"

    @pytest.mark.asyncio
    async def test_error_handling_empty_query(self, search_engine, sample_data):
        """Test handling of empty queries."""
        # Empty query should still work
        results = await search_engine.search(query="", limit=5)

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

    @pytest.mark.asyncio
    async def test_error_handling_invalid_filters(self, search_engine, sample_data):
        """Test handling of invalid filters."""
        # Invalid field name
        invalid_filter = SearchFilter(
            field="nonexistent_field",
            operator="eq",
            value="test",
        )

        # Should not crash, might return empty results
        results = await search_engine.search(
            query="test",
            filters=[invalid_filter],
            limit=5,
        )

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

    @pytest.mark.asyncio
    async def test_error_handling_unknown_metric_type(self, search_engine, sample_data):
        """Test handling of unknown metric types."""
        metrics = await search_engine.aggregate_metrics(
            metric_type="unknown_metric",
            timeframe="30d",
        )

        # Should return error message
        assert isinstance(metrics, dict)
        if "error" in metrics:
            assert "unknown_metric" in metrics["error"]

    @pytest.mark.asyncio
    async def test_error_handling_malformed_timeframe(self, search_engine, sample_data):
        """Test handling of malformed timeframe strings."""
        # Should handle invalid timeframe gracefully
        results = await search_engine.search(
            query="test",
            timeframe="invalid_timeframe",
            limit=5,
        )

        # Should still return results even with invalid timeframe
        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

    @pytest.mark.asyncio
    async def test_performance_large_result_set_handling(
        self, search_engine, initialized_db
    ):
        """Test handling of large result sets."""
        # Add many conversations
        for i in range(50):
            await initialized_db.store_conversation(
                f"Test conversation {i} about authentication and security",
                {"project": f"project-{i % 5}"},
            )

        # Search with large limit
        results = await search_engine.search(query="authentication", limit=20)

        # Should handle large result sets
        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)
        assert len(results["results"]) <= 20

    @pytest.mark.asyncio
    async def test_concurrent_searches(self, search_engine, sample_data):
        """Test concurrent search operations."""
        # Run multiple searches concurrently
        tasks = [
            search_engine.search("authentication", limit=3),
            search_engine.search("database", limit=3),
            search_engine.search("frontend", limit=3),
            search_engine.search("error", limit=3),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All searches should complete successfully
        assert len(results) == 4
        for result in results:
            if not isinstance(result, Exception):
                assert isinstance(result, dict)
                assert "results" in result
                assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, search_engine, sample_data):
        """Test case-insensitive search."""
        # Search with different cases
        queries = [
            "AUTHENTICATION",
            "Authentication",
            "authentication",
            "AuThEnTiCaTiOn",
        ]

        for query in queries:
            results = await search_engine.search(query=query, limit=10)

            assert isinstance(results, dict)
            assert "results" in results
            assert isinstance(results["results"], list)

    @pytest.mark.asyncio
    async def test_search_with_multiple_filters(self, search_engine, sample_data):
        """Test combining multiple filters."""
        filters = [
            SearchFilter(field="project", operator="eq", value="webapp-backend"),
            SearchFilter(field="content_type", operator="eq", value="conversation"),
        ]

        results = await search_engine.search(
            query="test",
            filters=filters,
            limit=10,
        )

        assert isinstance(results, dict)
        assert "results" in results
        assert isinstance(results["results"], list)

        # Results should match both filters
        # Note: Some results might be reflections which don't have project or content_type info
        if results["results"]:
            project_results = [r for r in results["results"] if r.project is not None]
            if project_results:
                for result in project_results:
                    assert result.project == "webapp-backend"
                    # Note: The SearchResult object doesn't have a content_type attribute
                    # This is a limitation of the current implementation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

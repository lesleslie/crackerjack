#!/usr/bin/env python3
"""Integration tests for Multi-Project MCP Tools."""

# Import the MCP tools we want to test
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from session_mgmt_mcp.advanced_search import AdvancedSearchEngine
from session_mgmt_mcp.multi_project_coordinator import MultiProjectCoordinator
from session_mgmt_mcp.reflection_tools import ReflectionDatabase


# Mock the server functions to simulate MCP tool calls
async def mock_create_project_group(name: str, projects: list, description: str = ""):
    """Mock MCP tool: create_project_group."""
    from session_mgmt_mcp.server import create_project_group

    return await create_project_group(name, projects, description)


async def mock_add_project_dependency(
    source_project: str,
    target_project: str,
    dependency_type: str,
    description: str = "",
):
    """Mock MCP tool: add_project_dependency."""
    from session_mgmt_mcp.server import add_project_dependency

    return await add_project_dependency(
        source_project,
        target_project,
        dependency_type,
        description,
    )


async def mock_search_across_projects(
    query: str,
    current_project: str,
    limit: int = 10,
):
    """Mock MCP tool: search_across_projects."""
    from session_mgmt_mcp.server import search_across_projects

    return await search_across_projects(query, current_project, limit)


async def mock_advanced_search(
    query: str,
    content_type=None,
    project=None,
    timeframe=None,
    sort_by="relevance",
    limit=10,
):
    """Mock MCP tool: advanced_search."""
    from session_mgmt_mcp.server import advanced_search

    return await advanced_search(
        query,
        content_type,
        project,
        timeframe,
        sort_by,
        limit,
    )


@pytest.fixture
async def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name

    db = ReflectionDatabase(db_path)
    await db.initialize()

    yield db

    # Cleanup
    db.close()
    Path(db_path).unlink()


@pytest.fixture
async def setup_test_environment(temp_db):
    """Setup test environment with sample data."""
    # Add sample conversations
    conversations = [
        {
            "content": "Implementing OAuth2 authentication flow in React frontend. Need to handle token refresh and secure storage.",
            "project": "frontend-app",
            "metadata": {
                "type": "development",
                "feature": "auth",
                "technology": "react",
            },
        },
        {
            "content": "Backend API endpoints for user authentication. Using FastAPI with JWT tokens and password hashing.",
            "project": "backend-api",
            "metadata": {
                "type": "development",
                "feature": "auth",
                "technology": "fastapi",
            },
        },
        {
            "content": "Database migration to add user roles table. Added foreign key constraints and proper indexing.",
            "project": "backend-api",
            "metadata": {
                "type": "database",
                "operation": "migration",
                "technology": "postgresql",
            },
        },
        {
            "content": "DevOps: Containerizing applications with Docker. Created multi-stage builds for production optimization.",
            "project": "infrastructure",
            "metadata": {
                "type": "devops",
                "tool": "docker",
                "environment": "production",
            },
        },
        {
            "content": "Frontend testing setup with Jest and React Testing Library. Writing unit tests for authentication components.",
            "project": "frontend-app",
            "metadata": {"type": "testing", "framework": "jest", "focus": "unit-tests"},
        },
    ]

    for conv in conversations:
        await temp_db.store_conversation(
            content=conv["content"],
            metadata={"project": conv["project"], **conv["metadata"]},
        )

    # Add sample reflections
    reflections = [
        {
            "content": "Authentication best practice: Always validate JWT tokens on server-side and implement proper token refresh flow",
            "tags": ["authentication", "jwt", "security", "best-practices"],
        },
        {
            "content": "Testing strategy: Focus on integration tests for authentication flows, unit tests for individual components",
            "tags": ["testing", "strategy", "authentication", "integration"],
        },
    ]

    for refl in reflections:
        await temp_db.store_reflection(content=refl["content"], tags=refl["tags"])

    return conversations, reflections


class TestMultiProjectMCPTools:
    """Test multi-project MCP tools integration."""

    @pytest.mark.asyncio
    async def test_create_project_group_mcp(self, temp_db, setup_test_environment):
        """Test create_project_group MCP tool."""
        # Mock the global coordinator
        coordinator = MultiProjectCoordinator(temp_db)

        with patch("session_mgmt_mcp.server.multi_project_coordinator", coordinator):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                result = await mock_create_project_group(
                    name="Web Development Stack",
                    projects=["frontend-app", "backend-api"],
                    description="Full-stack web application components",
                )

        # Check result format
        assert "✅ **Project Group Created**" in result
        assert "Web Development Stack" in result
        assert "frontend-app" in result
        assert "backend-api" in result
        assert "Full-stack web application components" in result

    @pytest.mark.asyncio
    async def test_add_project_dependency_mcp(self, temp_db, setup_test_environment):
        """Test add_project_dependency MCP tool."""
        coordinator = MultiProjectCoordinator(temp_db)

        with patch("session_mgmt_mcp.server.multi_project_coordinator", coordinator):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                result = await mock_add_project_dependency(
                    source_project="frontend-app",
                    target_project="backend-api",
                    dependency_type="uses",
                    description="Frontend calls backend API endpoints",
                )

        # Check result format
        assert "✅ **Project Dependency Added**" in result
        assert "frontend-app" in result
        assert "backend-api" in result
        assert "uses" in result
        assert "Frontend calls backend API endpoints" in result

    @pytest.mark.asyncio
    async def test_search_across_projects_mcp(self, temp_db, setup_test_environment):
        """Test search_across_projects MCP tool."""
        coordinator = MultiProjectCoordinator(temp_db)

        # First add a dependency to enable cross-project search
        await coordinator.add_project_dependency(
            "frontend-app",
            "backend-api",
            "uses",
            "API calls",
        )

        with patch("session_mgmt_mcp.server.multi_project_coordinator", coordinator):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                result = await mock_search_across_projects(
                    query="authentication",
                    current_project="frontend-app",
                    limit=5,
                )

        # Should find authentication-related conversations
        assert (
            "🔍 **Cross-Project Search Results**" in result
            or "No results found" in result
        )

        # If results found, check format
        if "Cross-Project Search Results" in result:
            assert "authentication" in result.lower()

    @pytest.mark.asyncio
    async def test_get_project_insights_mcp(self, temp_db, setup_test_environment):
        """Test get_project_insights MCP tool."""
        coordinator = MultiProjectCoordinator(temp_db)

        with patch("session_mgmt_mcp.server.multi_project_coordinator", coordinator):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                from session_mgmt_mcp.server import get_project_insights

                result = await get_project_insights(
                    projects=["frontend-app", "backend-api", "infrastructure"],
                    time_range_days=30,
                )

        # Check result format
        assert "📊 **Cross-Project Insights**" in result
        assert "(Last 30 days)" in result


class TestAdvancedSearchMCPTools:
    """Test advanced search MCP tools integration."""

    @pytest.mark.asyncio
    async def test_advanced_search_mcp(self, temp_db, setup_test_environment):
        """Test advanced_search MCP tool."""
        search_engine = AdvancedSearchEngine(temp_db)
        await search_engine._rebuild_search_index()

        with patch("session_mgmt_mcp.server.advanced_search_engine", search_engine):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                result = await mock_advanced_search(
                    query="authentication",
                    content_type="conversation",
                    project="frontend-app",
                    limit=3,
                )

        # Check result format
        assert (
            "🔍 **Advanced Search Results**" in result or "No results found" in result
        )

    @pytest.mark.asyncio
    async def test_search_suggestions_mcp(self, temp_db, setup_test_environment):
        """Test search_suggestions MCP tool."""
        search_engine = AdvancedSearchEngine(temp_db)
        await search_engine._rebuild_search_index()

        with patch("session_mgmt_mcp.server.advanced_search_engine", search_engine):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                from session_mgmt_mcp.server import search_suggestions

                result = await search_suggestions(
                    query="auth",
                    field="content",
                    limit=5,
                )

        # Check result format
        assert "💡 **Search Suggestions**" in result or "No suggestions found" in result

    @pytest.mark.asyncio
    async def test_get_search_metrics_mcp(self, temp_db, setup_test_environment):
        """Test get_search_metrics MCP tool."""
        search_engine = AdvancedSearchEngine(temp_db)
        await search_engine._rebuild_search_index()

        with patch("session_mgmt_mcp.server.advanced_search_engine", search_engine):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                from session_mgmt_mcp.server import get_search_metrics

                result = await get_search_metrics(
                    metric_type="activity",
                    timeframe="30d",
                )

        # Check result format
        assert "📊 **Activity Metrics**" in result or "❌" in result


class TestMCPToolErrorHandling:
    """Test MCP tool error handling."""

    @pytest.mark.asyncio
    async def test_missing_coordinator_handling(self):
        """Test handling when multi_project_coordinator is not available."""
        with patch("session_mgmt_mcp.server.multi_project_coordinator", None):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                result = await mock_create_project_group(
                    name="Test Group",
                    projects=["project1"],
                    description="Test",
                )

        # Should return error message
        assert "❌ Multi-project coordination not available" in result

    @pytest.mark.asyncio
    async def test_missing_search_engine_handling(self):
        """Test handling when advanced_search_engine is not available."""
        with patch("session_mgmt_mcp.server.advanced_search_engine", None):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                result = await mock_advanced_search(query="test", limit=5)

        # Should return error message
        assert "❌ Advanced search not available" in result

    @pytest.mark.asyncio
    async def test_initialization_failure_handling(self, temp_db):
        """Test handling when initialization fails."""
        with patch("session_mgmt_mcp.server.multi_project_coordinator", None):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                # Mock initialization failure
                mock_init.side_effect = Exception("Database connection failed")

                result = await mock_create_project_group(
                    name="Test Group",
                    projects=["project1"],
                )

        # Should handle error gracefully
        assert "❌" in result or "not available" in result

    @pytest.mark.asyncio
    async def test_invalid_project_dependency_handling(self, temp_db):
        """Test handling of invalid project dependency parameters."""
        coordinator = MultiProjectCoordinator(temp_db)

        with patch("session_mgmt_mcp.server.multi_project_coordinator", coordinator):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                # Try with empty project names
                result = await mock_add_project_dependency(
                    source_project="",
                    target_project="",
                    dependency_type="invalid_type",
                    description="",
                )

        # Should either succeed (empty strings are valid) or return specific error
        assert isinstance(result, str)
        assert "Dependency Added" in result or "❌" in result


class TestMCPWorkflowIntegration:
    """Test complete multi-project workflows."""

    @pytest.mark.asyncio
    async def test_complete_multi_project_workflow(
        self,
        temp_db,
        setup_test_environment,
    ):
        """Test complete workflow: create group, add dependencies, search."""
        coordinator = MultiProjectCoordinator(temp_db)
        search_engine = AdvancedSearchEngine(temp_db)
        await search_engine._rebuild_search_index()

        with patch("session_mgmt_mcp.server.multi_project_coordinator", coordinator):
            with patch("session_mgmt_mcp.server.advanced_search_engine", search_engine):
                with patch(
                    "session_mgmt_mcp.server.initialize_new_features",
                ) as mock_init:
                    mock_init.return_value = None

                    # Step 1: Create project group
                    group_result = await mock_create_project_group(
                        name="Full Stack App",
                        projects=["frontend-app", "backend-api", "infrastructure"],
                        description="Complete application stack",
                    )

                    assert "✅ **Project Group Created**" in group_result

                    # Step 2: Add dependencies
                    dep1_result = await mock_add_project_dependency(
                        "frontend-app",
                        "backend-api",
                        "uses",
                        "API calls",
                    )

                    dep2_result = await mock_add_project_dependency(
                        "backend-api",
                        "infrastructure",
                        "deployed_on",
                        "Docker containers",
                    )

                    assert "✅ **Project Dependency Added**" in dep1_result
                    assert "✅ **Project Dependency Added**" in dep2_result

                    # Step 3: Search across projects
                    search_result = await mock_search_across_projects(
                        query="authentication",
                        current_project="frontend-app",
                        limit=5,
                    )

                    # Should find results from related projects
                    assert isinstance(search_result, str)

                    # Step 4: Get project insights
                    from session_mgmt_mcp.server import get_project_insights

                    insights_result = await get_project_insights(
                        projects=["frontend-app", "backend-api", "infrastructure"],
                        time_range_days=30,
                    )

                    assert "📊 **Cross-Project Insights**" in insights_result

    @pytest.mark.asyncio
    async def test_advanced_search_workflow(self, temp_db, setup_test_environment):
        """Test advanced search workflow with different filters and metrics."""
        search_engine = AdvancedSearchEngine(temp_db)
        await search_engine._rebuild_search_index()

        with patch("session_mgmt_mcp.server.advanced_search_engine", search_engine):
            with patch("session_mgmt_mcp.server.initialize_new_features") as mock_init:
                mock_init.return_value = None

                # Step 1: Basic search
                basic_result = await mock_advanced_search(
                    query="authentication",
                    limit=5,
                )

                assert isinstance(basic_result, str)

                # Step 2: Filtered search
                filtered_result = await mock_advanced_search(
                    query="testing",
                    content_type="conversation",
                    project="frontend-app",
                    limit=3,
                )

                assert isinstance(filtered_result, str)

                # Step 3: Get search suggestions
                from session_mgmt_mcp.server import search_suggestions

                suggestions_result = await search_suggestions(query="auth", limit=5)

                assert isinstance(suggestions_result, str)

                # Step 4: Get activity metrics
                from session_mgmt_mcp.server import get_search_metrics

                metrics_result = await get_search_metrics(
                    metric_type="projects",
                    timeframe="30d",
                )

                assert isinstance(metrics_result, str)


class TestMCPToolConfiguration:
    """Test MCP tools with configuration management."""

    @pytest.mark.asyncio
    async def test_tools_with_config(self, temp_db, setup_test_environment):
        """Test MCP tools with configuration support."""
        # Mock configuration
        mock_config = AsyncMock()
        mock_config.database.enable_multi_project = True
        mock_config.search.enable_faceted_search = True
        mock_config.search.max_facet_values = 25

        coordinator = MultiProjectCoordinator(temp_db)

        with patch("session_mgmt_mcp.server.multi_project_coordinator", coordinator):
            with patch("session_mgmt_mcp.server.app_config", mock_config):
                with patch(
                    "session_mgmt_mcp.server.initialize_new_features",
                ) as mock_init:
                    mock_init.return_value = None

                    result = await mock_create_project_group(
                        name="Configured Group",
                        projects=["proj1", "proj2"],
                    )

                    assert "✅ **Project Group Created**" in result

    @pytest.mark.asyncio
    async def test_feature_availability_flags(self):
        """Test MCP tools respect feature availability flags."""
        # Test when features are disabled
        with patch("session_mgmt_mcp.server.MULTI_PROJECT_AVAILABLE", False):
            with patch("session_mgmt_mcp.server.ADVANCED_SEARCH_AVAILABLE", False):
                # Multi-project tools should be unavailable
                group_result = await mock_create_project_group(
                    name="Test Group",
                    projects=["proj1"],
                )

                search_result = await mock_advanced_search(query="test")

                # Both should indicate feature unavailability
                assert "not available" in group_result or "❌" in group_result
                assert "not available" in search_result or "❌" in search_result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

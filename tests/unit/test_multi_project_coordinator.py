#!/usr/bin/env python3
"""Unit tests for Multi-Project Coordinator."""

import asyncio
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from session_mgmt_mcp.multi_project_coordinator import (
    MultiProjectCoordinator,
)
from session_mgmt_mcp.reflection_tools import ReflectionDatabase


@pytest.fixture
async def temp_db():
    """Create a temporary test database."""
    # Create a temporary directory and let DuckDB create the database file
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.duckdb"

        db = ReflectionDatabase(str(db_path))
        await db.initialize()

        yield db

        # Cleanup happens automatically when temp_dir is deleted


@pytest.fixture
async def coordinator(temp_db):
    """Create a coordinator with test database."""
    return MultiProjectCoordinator(temp_db)


@pytest.fixture
async def sample_conversations(temp_db):
    """Add sample conversations to test database."""
    conversations = [
        {
            "content": "Working on authentication system for web app. Need to implement JWT tokens.",
            "project": "webapp-frontend",
            "metadata": {"type": "development", "priority": "high"},
        },
        {
            "content": "Created API endpoints for user management. Using FastAPI framework.",
            "project": "webapp-backend",
            "metadata": {"type": "development", "api": "REST"},
        },
        {
            "content": "Debugging database connection issues. PostgreSQL timeout errors.",
            "project": "webapp-backend",
            "metadata": {"type": "bug", "severity": "medium"},
        },
        {
            "content": "Setting up CI/CD pipeline with GitHub Actions for deployment.",
            "project": "devops-tools",
            "metadata": {"type": "infrastructure", "tool": "github-actions"},
        },
    ]

    for conv in conversations:
        await temp_db.store_conversation(
            content=conv["content"],
            metadata={"project": conv["project"], **conv["metadata"]},
        )

    return conversations


class TestProjectGroup:
    """Test ProjectGroup functionality."""

    @pytest.mark.asyncio
    async def test_create_project_group(self, coordinator):
        """Test creating a project group."""
        group = await coordinator.create_project_group(
            name="Web Development",
            projects=["webapp-frontend", "webapp-backend"],
            description="Frontend and backend for web application",
        )

        assert group.name == "Web Development"
        assert "webapp-frontend" in group.projects
        assert "webapp-backend" in group.projects
        assert group.description == "Frontend and backend for web application"
        assert group.id is not None
        assert isinstance(group.created_at, datetime)

    @pytest.mark.asyncio
    async def test_get_project_groups(self, coordinator):
        """Test retrieving project groups."""
        # Create test groups
        await coordinator.create_project_group(
            name="Web Apps",
            projects=["webapp-frontend", "webapp-backend"],
        )

        await coordinator.create_project_group(
            name="DevOps",
            projects=["devops-tools", "monitoring"],
        )

        # Get all groups
        all_groups = await coordinator.get_project_groups()
        assert len(all_groups) == 2

        group_names = [g.name for g in all_groups]
        assert "Web Apps" in group_names
        assert "DevOps" in group_names

        # Get groups for specific project
        webapp_groups = await coordinator.get_project_groups(project="webapp-frontend")
        assert len(webapp_groups) == 1
        assert webapp_groups[0].name == "Web Apps"


class TestProjectDependencies:
    """Test project dependency functionality."""

    @pytest.mark.asyncio
    async def test_add_project_dependency(self, coordinator):
        """Test adding project dependencies."""
        dependency = await coordinator.add_project_dependency(
            source_project="webapp-frontend",
            target_project="webapp-backend",
            dependency_type="uses",
            description="Frontend uses backend API",
        )

        assert dependency.source_project == "webapp-frontend"
        assert dependency.target_project == "webapp-backend"
        assert dependency.dependency_type == "uses"
        assert dependency.description == "Frontend uses backend API"
        assert dependency.id is not None

    @pytest.mark.asyncio
    async def test_get_project_dependencies(self, coordinator):
        """Test retrieving project dependencies."""
        # Add test dependencies
        await coordinator.add_project_dependency(
            "webapp-frontend",
            "webapp-backend",
            "uses",
            "API calls",
        )
        await coordinator.add_project_dependency(
            "webapp-backend",
            "database",
            "uses",
            "Data storage",
        )
        await coordinator.add_project_dependency(
            "monitoring",
            "webapp-backend",
            "monitors",
            "Health checks",
        )

        # Test outbound dependencies
        outbound = await coordinator.get_project_dependencies(
            "webapp-backend",
            "outbound",
        )
        assert len(outbound) == 1
        assert outbound[0].target_project == "database"

        # Test inbound dependencies
        inbound = await coordinator.get_project_dependencies(
            "webapp-backend",
            "inbound",
        )
        assert len(inbound) == 2
        source_projects = [dep.source_project for dep in inbound]
        assert "webapp-frontend" in source_projects
        assert "monitoring" in source_projects

        # Test both directions
        both = await coordinator.get_project_dependencies("webapp-backend", "both")
        assert len(both) == 3

    @pytest.mark.asyncio
    async def test_dependency_caching(self, coordinator):
        """Test dependency caching mechanism."""
        # Add a dependency
        await coordinator.add_project_dependency(
            "project-a",
            "project-b",
            "uses",
            "Test dependency",
        )

        # First call should populate cache
        deps1 = await coordinator.get_project_dependencies("project-a")

        # Second call should use cache (same result)
        deps2 = await coordinator.get_project_dependencies("project-a")

        assert len(deps1) == len(deps2)
        assert deps1[0].target_project == deps2[0].target_project

        # Adding new dependency should clear cache
        await coordinator.add_project_dependency(
            "project-a",
            "project-c",
            "uses",
            "Another dependency",
        )

        # Next call should show updated results
        deps3 = await coordinator.get_project_dependencies("project-a")
        assert len(deps3) == 2


class TestSessionLinks:
    """Test session linking functionality."""

    @pytest.mark.asyncio
    async def test_link_sessions(self, coordinator):
        """Test creating session links."""
        link = await coordinator.link_sessions(
            source_session_id="session-123",
            target_session_id="session-456",
            link_type="related",
            context="Both working on authentication feature",
        )

        assert link.source_session_id == "session-123"
        assert link.target_session_id == "session-456"
        assert link.link_type == "related"
        assert link.context == "Both working on authentication feature"
        assert link.id is not None

    @pytest.mark.asyncio
    async def test_get_session_links(self, coordinator):
        """Test retrieving session links."""
        # Add test session links
        await coordinator.link_sessions("session-1", "session-2", "continuation")
        await coordinator.link_sessions("session-1", "session-3", "related")
        await coordinator.link_sessions("session-4", "session-1", "reference")

        # Get links for session-1
        links = await coordinator.get_session_links("session-1")
        assert len(links) == 3

        # Check that all link types are represented
        link_types = [link.link_type for link in links]
        assert "continuation" in link_types
        assert "related" in link_types
        assert "reference" in link_types


class TestCrossProjectSearch:
    """Test cross-project search functionality."""

    @pytest.mark.asyncio
    async def test_find_related_conversations(self, coordinator, sample_conversations):
        """Test finding conversations across related projects."""
        # Set up project dependencies
        await coordinator.add_project_dependency(
            "webapp-frontend",
            "webapp-backend",
            "uses",
        )
        await coordinator.add_project_dependency(
            "webapp-backend",
            "devops-tools",
            "uses",
        )

        # Search for authentication-related conversations
        results = await coordinator.find_related_conversations(
            current_project="webapp-frontend",
            query="authentication",
            limit=10,
        )

        assert len(results) >= 1

        # Should find the authentication conversation
        auth_result = next((r for r in results if "JWT tokens" in r["content"]), None)
        assert auth_result is not None
        assert auth_result["source_project"] == "webapp-frontend"
        assert auth_result["is_current_project"] is True

    @pytest.mark.asyncio
    async def test_cross_project_insights(self, coordinator, sample_conversations):
        """Test getting cross-project insights."""
        projects = ["webapp-frontend", "webapp-backend", "devops-tools"]

        insights = await coordinator.get_cross_project_insights(
            projects=projects,
            time_range_days=30,
        )

        assert "project_activity" in insights
        assert "common_patterns" in insights

        # Check project activity
        activity = insights["project_activity"]
        assert len(activity) > 0

        for project in projects:
            if project in activity:
                project_stats = activity[project]
                assert "conversation_count" in project_stats
                assert isinstance(project_stats["conversation_count"], int)

    @pytest.mark.asyncio
    async def test_common_patterns_detection(self, coordinator, sample_conversations):
        """Test detection of common patterns across projects."""
        # Add more conversations with common patterns
        await coordinator.reflection_db.store_conversation(
            "Working on API development using FastAPI framework",
            {"project": "webapp-frontend"},
        )
        await coordinator.reflection_db.store_conversation(
            "API testing with FastAPI and pytest framework",
            {"project": "devops-tools"},
        )

        insights = await coordinator.get_cross_project_insights(
            projects=["webapp-frontend", "webapp-backend", "devops-tools"],
            time_range_days=30,
        )

        patterns = insights["common_patterns"]
        assert len(patterns) > 0

        # Look for "fastapi" pattern across projects
        fastapi_pattern = next(
            (p for p in patterns if "fastapi" in p["pattern"].lower()),
            None,
        )
        if fastapi_pattern:
            assert len(fastapi_pattern["projects"]) >= 2


class TestCleanup:
    """Test cleanup functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_old_links(self, coordinator):
        """Test cleanup of old session links."""
        # Add some session links with different ages
        await coordinator.link_sessions("old-1", "old-2", "related")
        await coordinator.link_sessions("new-1", "new-2", "related")

        # Manually set old timestamp for testing
        old_date = datetime.now(UTC) - timedelta(days=400)

        await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: coordinator.reflection_db.conn.execute(
                "UPDATE session_links SET created_at = ? WHERE source_session_id = ?",
                [old_date, "old-1"],
            ),
        )
        coordinator.reflection_db.conn.commit()

        # Cleanup links older than 365 days
        result = await coordinator.cleanup_old_links(max_age_days=365)

        assert "deleted_session_links" in result
        assert result["deleted_session_links"] >= 1

        # Verify recent link still exists
        new_links = await coordinator.get_session_links("new-1")
        assert len(new_links) >= 1


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_duplicate_project_group(self, coordinator):
        """Test creating duplicate project groups."""
        # Create initial group
        group1 = await coordinator.create_project_group(
            name="Test Group",
            projects=["project-a"],
        )

        # Create another group with same name (should work - names can be duplicate)
        group2 = await coordinator.create_project_group(
            name="Test Group",
            projects=["project-b"],
        )

        assert group1.id != group2.id
        assert group1.projects != group2.projects

    @pytest.mark.asyncio
    async def test_circular_dependencies(self, coordinator):
        """Test handling of circular project dependencies."""
        # Create circular dependency
        await coordinator.add_project_dependency("project-a", "project-b", "uses")
        await coordinator.add_project_dependency("project-b", "project-c", "uses")
        await coordinator.add_project_dependency("project-c", "project-a", "uses")

        # Getting dependencies should still work
        deps_a = await coordinator.get_project_dependencies("project-a")
        deps_b = await coordinator.get_project_dependencies("project-b")
        deps_c = await coordinator.get_project_dependencies("project-c")

        assert len(deps_a) == 2  # outbound to b, inbound from c
        assert len(deps_b) == 2  # outbound to c, inbound from a
        assert len(deps_c) == 2  # outbound to a, inbound from b

    @pytest.mark.asyncio
    async def test_empty_search_results(self, coordinator):
        """Test handling of empty search results."""
        # Search with project that has no dependencies
        results = await coordinator.find_related_conversations(
            current_project="nonexistent-project",
            query="authentication",
            limit=5,
        )

        # Should return results from the project itself (even if empty)
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_malformed_data_handling(self, coordinator):
        """Test handling of malformed data."""
        # Try to create group with empty project list
        group = await coordinator.create_project_group(
            name="Empty Group",
            projects=[],
            description="Group with no projects",
        )

        assert group.name == "Empty Group"
        assert group.projects == []

        # Try to add dependency with empty strings
        dep = await coordinator.add_project_dependency("", "project-b", "uses")
        assert dep.source_project == ""
        assert dep.target_project == "project-b"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

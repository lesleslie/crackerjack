"""Integration tests for Akosha git semantic search.

Tests the integration between Crackerjack's git metrics collector
and Akosha's semantic search capabilities.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Import test fixtures
from crackerjack.integration.akosha_integration import (
    AkoshaClientConfig,
    AkoshaGitIntegration,
    DirectAkoshaClient,
    GitEvent,
    GitVelocityMetrics,
    NoOpAkoshaClient,
    create_akosha_client,
    create_akosha_git_integration,
)

logger = logging.getLogger(__name__)


@pytest.fixture
def sample_repo_path(tmp_path: Path) -> Path:
    """Create a sample git repository for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to test repository
    """
    import subprocess

    repo_path = tmp_path / "test-repo"
    repo_path.mkdir()

    # Initialize git repo
    subprocess.run(
        ["git", "init"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Configure git
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    test_file = repo_path / "test.txt"
    test_file.write_text("Initial content")

    subprocess.run(
        ["git", "add", "test.txt"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "feat: initial implementation"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    return repo_path


class TestGitEvent:
    """Tests for GitEvent dataclass."""

    def test_to_searchable_text_commit(self) -> None:
        """Test searchable text generation for commits."""
        event = GitEvent(
            commit_hash="abc123",
            timestamp=datetime.now(),
            author_name="Test User",
            message="feat: add new feature",
            event_type="commit",
            semantic_tags=["type:feat"],
        )

        text = event.to_searchable_text()

        assert "commit: feat: add new feature" in text
        assert "by Test User" in text
        assert "tags: type:feat" in text

    def test_to_searchable_text_merge(self) -> None:
        """Test searchable text generation for merges."""
        event = GitEvent(
            commit_hash="def456",
            timestamp=datetime.now(),
            author_name="Test User",
            message="Merge pull request #123",
            event_type="merge",
            semantic_tags=["merge"],
        )

        text = event.to_searchable_text()

        assert "merge: Merge pull request #123" in text

    def test_to_searchable_text_with_tags(self) -> None:
        """Test searchable text with multiple semantic tags."""
        event = GitEvent(
            commit_hash="ghi789",
            timestamp=datetime.now(),
            author_name="Test User",
            message="feat(api)!: breaking API change",
            event_type="commit",
            semantic_tags=["type:feat", "scope:api", "breaking"],
        )

        text = event.to_searchable_text()

        assert "tags: type:feat, scope:api, breaking" in text


class TestGitVelocityMetrics:
    """Tests for GitVelocityMetrics dataclass."""

    def test_to_searchable_text(self) -> None:
        """Test searchable text generation for velocity metrics."""
        metrics = GitVelocityMetrics(
            repository_path="/path/to/repo",
            period_start=datetime.now() - timedelta(days=30),
            period_end=datetime.now(),
            total_commits=150,
            avg_commits_per_day=5.0,
            avg_commits_per_week=35.0,
            conventional_compliance_rate=0.85,
            breaking_changes=3,
            merge_conflict_rate=0.1,
            most_active_hour=14,
            most_active_day=2,
        )

        text = metrics.to_searchable_text()

        assert "5.0 commits/day" in text
        assert "35.0 commits/week" in text
        assert "85.0% conventional compliance" in text
        assert "3 breaking changes" in text
        assert "10.0% conflict rate" in text


class TestNoOpAkoshaClient:
    """Tests for NoOpAkoshaClient."""

    @pytest.mark.asyncio
    async def test_store_memory_returns_id(self) -> None:
        """Test that store_memory returns a valid ID."""
        client = NoOpAkoshaClient()

        memory_id = await client.store_memory(
            content="test content",
            metadata={"key": "value"},
        )

        assert memory_id == "noop-id"

    @pytest.mark.asyncio
    async def test_semantic_search_returns_empty(self) -> None:
        """Test that semantic_search returns empty list."""
        client = NoOpAkoshaClient()

        results = await client.semantic_search(
            query="test query",
            limit=10,
        )

        assert results == []

    def test_is_connected_returns_false(self) -> None:
        """Test that is_connected returns False."""
        client = NoOpAkoshaClient()
        assert not client.is_connected()


class TestDirectAkoshaClient:
    """Tests for DirectAkoshaClient."""

    @pytest.mark.asyncio
    async def test_initialize_without_akosha(self) -> None:
        """Test initialization when Akosha package is unavailable."""
        client = DirectAkoshaClient()

        # Should not raise exception even if akosha not installed
        await client.initialize()

        # Client should gracefully handle unavailability
        assert not client.is_connected()

    @pytest.mark.asyncio
    async def test_store_memory_with_unavailable_service(self) -> None:
        """Test store_memory when service is unavailable."""
        client = DirectAkoshaClient()

        result = await client.store_memory(
            content="test",
            metadata={},
        )

        assert result in ("unavailable", "error")

    @pytest.mark.asyncio
    async def test_semantic_search_with_unavailable_service(self) -> None:
        """Test semantic_search when service is unavailable."""
        client = DirectAkoshaClient()

        results = await client.semantic_search(
            query="test query",
            limit=10,
        )

        assert results == []


class TestAkoshaGitIntegration:
    """Tests for AkoshaGitIntegration."""

    @pytest.mark.asyncio
    async def test_initialization(self, sample_repo_path: Path) -> None:
        """Test integration initialization."""
        client = NoOpAkoshaClient()
        integration = AkoshaGitIntegration(
            client=client,
            repo_path=sample_repo_path,
        )

        await integration.initialize()

        # Should complete without errors
        assert integration.repo_path == sample_repo_path

    @pytest.mark.asyncio
    async def test_index_repository_history(
        self,
        sample_repo_path: Path,
    ) -> None:
        """Test indexing repository history."""
        client = NoOpAkoshaClient()
        integration = AkoshaGitIntegration(
            client=client,
            repo_path=sample_repo_path,
        )

        await integration.initialize()

        # Index repository history (should complete without errors)
        indexed_count = await integration.index_repository_history(days_back=30)

        # Should have indexed at least the initial commit
        assert indexed_count >= 1

    @pytest.mark.asyncio
    async def test_search_git_history(self, sample_repo_path: Path) -> None:
        """Test semantic search over git history."""
        client = NoOpAkoshaClient()
        integration = AkoshaGitIntegration(
            client=client,
            repo_path=sample_repo_path,
        )

        await integration.initialize()
        await integration.index_repository_history(days_back=30)

        # Search for commits
        results = await integration.search_git_history(
            query="initial implementation",
            limit=10,
        )

        # NoOp client returns empty list
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_extract_semantic_tags(self) -> None:
        """Test semantic tag extraction from commits."""
        from dataclasses import dataclass

        @dataclass
        class MockCommit:
            hash: str
            author_timestamp: datetime
            author_name: str
            author_email: str
            message: str
            is_merge: bool
            is_conventional: bool
            conventional_type: str | None
            conventional_scope: str | None
            has_breaking_change: bool

        client = NoOpAkoshaClient()
        integration = AkoshaGitIntegration(
            client=client,
            repo_path=Path("/test"),
        )

        # Test conventional commit
        commit = MockCommit(
            hash="abc123",
            author_timestamp=datetime.now(),
            author_name="Test",
            author_email="test@example.com",
            message="feat(api): add authentication",
            is_merge=False,
            is_conventional=True,
            conventional_type="feat",
            conventional_scope="api",
            has_breaking_change=False,
        )

        tags = integration._extract_semantic_tags(commit)

        assert "type:feat" in tags
        assert "scope:api" in tags
        assert "breaking" not in tags

        # Test breaking change
        commit2 = MockCommit(
            hash="def456",
            author_timestamp=datetime.now(),
            author_name="Test",
            author_email="test@example.com",
            message="feat!: breaking API change",
            is_merge=False,
            is_conventional=True,
            conventional_type="feat",
            conventional_scope=None,
            has_breaking_change=True,
        )

        tags2 = integration._extract_semantic_tags(commit2)

        assert "type:feat" in tags2
        assert "breaking" in tags2


class TestClientFactory:
    """Tests for client factory functions."""

    def test_create_noop_client(self) -> None:
        """Test creating no-op client."""
        client = create_akosha_client(backend="none")

        assert isinstance(client, NoOpAkoshaClient)
        assert not client.is_connected()

    @pytest.mark.asyncio
    async def test_create_direct_client(self) -> None:
        """Test creating direct client."""
        client = create_akosha_client(backend="direct")

        assert isinstance(client, DirectAkoshaClient)

        # Initialize to check availability
        await client.initialize()

        # Should handle gracefully even if akosha not installed

    def test_create_auto_backend(self) -> None:
        """Test auto backend selection."""
        client = create_akosha_client(backend="auto")

        # Should return some client implementation
        assert client is not None
        assert hasattr(client, "store_memory")
        assert hasattr(client, "semantic_search")

    def test_create_integration_with_factory(self) -> None:
        """Test creating integration via factory function."""
        integration = create_akosha_git_integration(
            repo_path=Path("/test/repo"),
            backend="none",
        )

        assert isinstance(integration, AkoshaGitIntegration)
        assert integration.repo_path == Path("/test/repo")
        assert isinstance(integration.client, NoOpAkoshaClient)


class TestIntegrationScenarios:
    """End-to-end integration scenario tests."""

    @pytest.mark.asyncio
    async def test_full_workflow_with_sample_repo(
        self,
        sample_repo_path: Path,
    ) -> None:
        """Test complete workflow: index -> search -> retrieve."""
        integration = create_akosha_git_integration(
            repo_path=sample_repo_path,
            backend="none",
        )

        await integration.initialize()

        # Step 1: Index repository
        indexed = await integration.index_repository_history(days_back=30)
        assert indexed >= 1

        # Step 2: Semantic search
        results = await integration.search_git_history(
            query="feat: initial",
            limit=10,
        )

        # Should return list (even if empty from NoOp)
        assert isinstance(results, list)

        # Step 3: Get velocity trends
        trends = await integration.get_velocity_trends(
            query="repository velocity",
        )

        assert isinstance(trends, list)

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, sample_repo_path: Path) -> None:
        """Test concurrent indexing and searching."""
        integration = create_akosha_git_integration(
            repo_path=sample_repo_path,
            backend="none",
        )

        await integration.initialize()

        # Run operations concurrently
        tasks = [
            integration.index_repository_history(days_back=30),
            integration.search_git_history(query="test", limit=5),
            integration.get_velocity_trends(query="velocity"),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All operations should complete (or return gracefully)
        for result in results:
            if not isinstance(result, Exception):
                assert result is not None

    @pytest.mark.asyncio
    async def test_velocity_trends_query(self, sample_repo_path: Path) -> None:
        """Test velocity trends semantic queries."""
        integration = create_akosha_git_integration(
            repo_path=sample_repo_path,
            backend="none",
        )

        await integration.initialize()
        await integration.index_repository_history(days_back=30)

        # Query for different patterns
        queries = [
            "high velocity",
            "declining commit rate",
            "frequent conflicts",
        ]

        for query in queries:
            trends = await integration.get_velocity_trends(query=query)
            assert isinstance(trends, list)


@pytest.mark.integration
class TestRealAkoshaIntegration:
    """Integration tests with real Akosha instance.

    These tests require Akosha to be installed and running.
    Run with: pytest tests/integration/test_akosha_integration.py::TestRealAkoshaIntegration -v
    """

    @pytest.mark.asyncio
    async def test_real_akosha_client(self) -> None:
        """Test with real Akosha package (if available)."""
        client = create_akosha_client(backend="direct")

        await client.initialize()

        if client.is_connected():
            # Test actual operations
            memory_id = await client.store_memory(
                content="test memory",
                metadata={"test": True},
            )

            assert memory_id not in ("unavailable", "error")

            # Test search
            results = await client.semantic_search("test query", limit=5)

            assert isinstance(results, list)
        else:
            pytest.skip("Akosha package not available")

    @pytest.mark.asyncio
    async def test_real_repo_indexing(
        self,
        sample_repo_path: Path,
    ) -> None:
        """Test real repository indexing with Akosha (if available)."""
        integration = create_akosha_git_integration(
            repo_path=sample_repo_path,
            backend="direct",
        )

        await integration.initialize()

        if integration.client.is_connected():
            indexed = await integration.index_repository_history(days_back=30)

            # Should have indexed commits
            assert indexed > 0

            # Test search
            results = await integration.search_git_history("initial", limit=5)

            # Should return results
            assert isinstance(results, list)
        else:
            pytest.skip("Akosha package not available")

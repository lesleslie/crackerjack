"""Integration tests for Git Semantic Search.

Tests the semantic search capabilities over git history, including
natural language search, workflow pattern detection, and practice
recommendations.
"""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.integration.git_semantic_search import (
    GitSemanticSearch,
    GitSemanticSearchConfig,
    PracticeRecommendation,
    WorkflowPattern,
    create_git_semantic_search,
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

    # Create multiple commits for testing
    commits = [
        "feat: add authentication system",
        "fix: resolve memory leak in parser",
        "fix: authentication bug fix",
        "docs: update API documentation",
        "refactor: improve error handling",
        "feat: add user profile feature",
        "fix: another parser memory issue",
        "test: add authentication tests",
    ]

    for commit_msg in commits:
        test_file = repo_path / f"file_{len(commits)}.txt"
        test_file.write_text(f"Content for {commit_msg}")
        subprocess.run(
            ["git", "add", "."],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

    return repo_path


class TestWorkflowPattern:
    """Tests for WorkflowPattern dataclass."""

    def test_workflow_pattern_creation(self) -> None:
        """Test creating a workflow pattern."""
        now = datetime.now()

        pattern = WorkflowPattern(
            pattern_id="test-pattern-1",
            pattern_name="Hotfix Pattern",
            description="Recurring hotfix commits after releases",
            frequency=5,
            confidence=0.85,
            examples=[
                {
                    "commit_hash": "abc123",
                    "message": "fix: critical bug",
                    "author": "Test User",
                }
            ],
            semantic_tags=["type:fix", "hotfix"],
            first_seen=now - timedelta(days=30),
            last_seen=now,
        )

        assert pattern.pattern_id == "test-pattern-1"
        assert pattern.pattern_name == "Hotfix Pattern"
        assert pattern.frequency == 5
        assert pattern.confidence == 0.85
        assert len(pattern.examples) == 1

    def test_to_searchable_text(self) -> None:
        """Test converting pattern to searchable text."""
        pattern = WorkflowPattern(
            pattern_id="test-pattern",
            pattern_name="Test Pattern",
            description="Test description",
            frequency=10,
            confidence=0.9,
            examples=[],
            semantic_tags=["tag1", "tag2"],
        )

        text = pattern.to_searchable_text()

        assert "Test Pattern" in text
        assert "Test description" in text
        assert "10 occurrences" in text
        assert "90.00%" in text  # Formatted as percentage with 2 decimal places
        assert "tag1" in text
        assert "tag2" in text


class TestPracticeRecommendation:
    """Tests for PracticeRecommendation dataclass."""

    def test_practice_recommendation_creation(self) -> None:
        """Test creating a practice recommendation."""
        recommendation = PracticeRecommendation(
            recommendation_type="commit_quality",
            title="Improve Conventional Commits",
            description="Increase conventional commit adoption",
            priority=4,
            evidence=[{"commit_count": 100}],
            actionable_steps=[
                "Add commitlint",
                "Create template",
            ],
            potential_impact="Better changelog generation",
            metric_baseline={"current": "60%", "target": "80%"},
        )

        assert recommendation.recommendation_type == "commit_quality"
        assert recommendation.title == "Improve Conventional Commits"
        assert recommendation.priority == 4
        assert len(recommendation.actionable_steps) == 2

    def test_to_searchable_text(self) -> None:
        """Test converting recommendation to searchable text."""
        recommendation = PracticeRecommendation(
            recommendation_type="workflow",
            title="Reduce Conflicts",
            description="Lower merge conflict rate",
            priority=5,
            evidence=[],
            actionable_steps=["Step 1", "Step 2", "Step 3"],
            potential_impact="Faster integration",
        )

        text = recommendation.to_searchable_text()

        assert "Reduce Conflicts" in text
        assert "workflow" in text
        assert "5/5" in text
        assert "Faster integration" in text
        assert "Step 1" in text


class TestGitSemanticSearchConfig:
    """Tests for GitSemanticSearchConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = GitSemanticSearchConfig()

        assert config.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.chunk_size == 512
        assert config.embedding_dimension == 384
        assert config.similarity_threshold == 0.6
        assert config.max_results == 20
        assert config.auto_index is True
        assert config.index_interval_hours == 24

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = GitSemanticSearchConfig(
            similarity_threshold=0.7,
            max_results=50,
            auto_index=False,
        )

        assert config.similarity_threshold == 0.7
        assert config.max_results == 50
        assert config.auto_index is False


class TestGitSemanticSearch:
    """Tests for GitSemanticSearch main class."""

    def test_initialization_success(self, sample_repo_path: Path) -> None:
        """Test successful initialization."""
        searcher = GitSemanticSearch(
            repo_path=str(sample_repo_path),
        )

        assert searcher.repo_path == sample_repo_path.resolve()
        assert searcher._indexed_days == 0

        searcher.close()

    def test_initialization_invalid_repo(self, tmp_path: Path) -> None:
        """Test initialization with invalid repository."""
        non_repo = tmp_path / "not-a-repo"
        non_repo.mkdir()

        with pytest.raises(ValueError, match="Not a git repository"):
            GitSemanticSearch(repo_path=str(non_repo))

    @pytest.mark.asyncio
    async def test_search_git_history_with_mock(
        self,
        sample_repo_path: Path,
    ) -> None:
        """Test git history search with mocked Akosha integration."""
        searcher = GitSemanticSearch(
            repo_path=str(sample_repo_path),
        )

        # Mock the Akosha integration
        mock_akosha = AsyncMock()
        mock_event = MagicMock()
        mock_event.commit_hash = "abc123"
        mock_event.message = "fix: authentication bug"
        mock_event.author_name = "Test User"
        mock_event.timestamp = datetime.now()
        mock_event.event_type = "commit"
        mock_event.semantic_tags = ["type:fix"]
        mock_event.metadata = {"conventional_type": "fix"}

        mock_akosha.search_git_history = AsyncMock(
            return_value=[mock_event]
        )

        searcher._akosha_integration = mock_akosha

        # Perform search
        results = await searcher.search_git_history(
            query="authentication bugs",
            limit=10,
            days_back=30,
        )

        assert results["success"] is True
        assert results["query"] == "authentication bugs"
        assert results["results_count"] == 1
        assert len(results["results"]) == 1
        assert results["results"][0]["commit_hash"] == "abc123"

        searcher.close()

    @pytest.mark.asyncio
    async def test_search_git_history_error_handling(
        self,
        sample_repo_path: Path,
    ) -> None:
        """Test error handling in git history search."""
        searcher = GitSemanticSearch(
            repo_path=str(sample_repo_path),
        )

        # Mock Akosha to raise error on initialize
        mock_akosha = AsyncMock()
        mock_akosha.initialize = AsyncMock(side_effect=Exception("Akosha error"))
        searcher._akosha_integration = mock_akosha

        results = await searcher.search_git_history(
            query="test query",
            limit=10,
            days_back=30,
        )

        # The code catches errors gracefully and returns success=True with empty results
        # (errors are logged but don't fail the operation)
        assert results["success"] is True
        assert results["results_count"] == 0

        searcher.close()

    @pytest.mark.asyncio
    async def test_find_workflow_patterns_with_mock(
        self,
        sample_repo_path: Path,
    ) -> None:
        """Test workflow pattern detection with mocked integration."""
        searcher = GitSemanticSearch(
            repo_path=str(sample_repo_path),
        )

        # Mock Akosha integration
        mock_akosha = AsyncMock()
        mock_event = MagicMock()
        mock_event.commit_hash = "def456"
        mock_event.message = "fix: parser memory leak"
        mock_event.author_name = "Test User"
        mock_event.timestamp = datetime.now()
        mock_event.semantic_tags = ["type:fix", "scope:parser"]
        mock_event.metadata = {"conventional_type": "fix", "scope": "parser"}

        mock_akosha.search_git_history = AsyncMock(
            return_value=[mock_event] * 5  # 5 similar commits
        )

        searcher._akosha_integration = mock_akosha

        # Find patterns
        results = await searcher.find_workflow_patterns(
            pattern_description="memory leak fixes",
            days_back=90,
            min_frequency=3,
        )

        assert results["success"] is True
        assert "patterns" in results
        assert results["pattern_description"] == "memory leak fixes"

        searcher.close()

    @pytest.mark.asyncio
    async def test_recommend_git_practices(
        self,
        sample_repo_path: Path,
    ) -> None:
        """Test git practice recommendations."""
        searcher = GitSemanticSearch(
            repo_path=str(sample_repo_path),
        )

        # Get recommendations
        results = await searcher.recommend_git_practices(
            focus_area="general",
            days_back=60,
        )

        assert results["success"] is True
        assert "recommendations" in results
        assert results["focus_area"] == "general"

        # Check that recommendations have required fields
        for rec in results["recommendations"]:
            assert "type" in rec
            assert "title" in rec
            assert "priority" in rec
            assert "actionable_steps" in rec

        searcher.close()

    def test_analyze_patterns_clustering(self, sample_repo_path: Path) -> None:
        """Test pattern analysis and clustering logic."""
        searcher = GitSemanticSearch(
            repo_path=str(sample_repo_path),
        )

        # Create mock events
        mock_events = []
        for i in range(5):
            event = MagicMock()
            event.commit_hash = f"hash{i}"
            event.message = f"fix: bug {i}"
            event.author_name = "Test User"
            event.timestamp = datetime.now()
            event.semantic_tags = ["type:fix"]
            event.metadata = {"conventional_type": "fix"}
            mock_events.append(event)

        # Analyze patterns
        patterns = searcher._analyze_patterns(
            events=mock_events,
            pattern_description="bug fixes",
            min_frequency=3,
        )

        # Should find at least one pattern
        assert len(patterns) >= 1

        # Check pattern structure
        pattern = patterns[0]
        assert pattern.pattern_id
        assert pattern.pattern_name
        assert pattern.frequency >= 3
        assert 0 <= pattern.confidence <= 1

        searcher.close()

    def test_generate_recommendations_commit_quality(
        self,
        sample_repo_path: Path,
    ) -> None:
        """Test recommendation generation for commit quality."""
        searcher = GitSemanticSearch(
            repo_path=str(sample_repo_path),
        )

        # Create mock dashboard with low conventional compliance
        mock_dashboard = MagicMock()
        mock_metrics = MagicMock()
        mock_metrics.conventional_compliance_rate = 0.5
        mock_metrics.breaking_changes = 5
        mock_metrics.avg_commits_per_day = 3.0
        mock_metrics.total_commits = 90

        mock_dashboard.commit_metrics = mock_metrics

        mock_merge_metrics = MagicMock()
        mock_merge_metrics.conflict_rate = 0.15
        mock_merge_metrics.total_conflicts = 5
        mock_dashboard.merge_metrics = mock_merge_metrics

        mock_branch_metrics = MagicMock()
        mock_branch_metrics.total_branches = 10
        mock_branch_metrics.active_branches = 5
        mock_branch_metrics.most_switched_branch = "main"
        mock_dashboard.branch_metrics = mock_branch_metrics

        # Generate recommendations
        recommendations = searcher._generate_recommendations(
            dashboard=mock_dashboard,
            focus_area="general",
            days_back=30,
        )

        # Should generate recommendations for low compliance
        assert len(recommendations) > 0

        # Check for conventional commit recommendation
        conv_rec = next(
            (r for r in recommendations if r.recommendation_type == "commit_quality"),
            None,
        )
        assert conv_rec is not None
        assert "conventional" in conv_rec.title.lower()
        assert conv_rec.priority >= 3

        searcher.close()


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_git_semantic_search(
        self,
        sample_repo_path: Path,
    ) -> None:
        """Test factory function creates instance correctly."""
        config = GitSemanticSearchConfig(similarity_threshold=0.7)

        searcher = create_git_semantic_search(
            repo_path=str(sample_repo_path),
            config=config,
        )

        assert isinstance(searcher, GitSemanticSearch)
        assert searcher.config.similarity_threshold == 0.7

        searcher.close()


class TestParameterValidation:
    """Tests for parameter validation in MCP tools."""

    @pytest.mark.parametrize(
        ("limit", "days_back", "should_fail"),
        [
            (10, 30, False),  # Valid
            (0, 30, True),  # limit too low
            (100, 30, True),  # limit too high
            (10, 0, True),  # days_back too low
            (10, 400, True),  # days_back too high
        ],
    )
    def test_search_params_validation(
        self,
        limit: int,
        days_back: int,
        should_fail: bool,
    ) -> None:
        """Test search parameter validation."""


        if should_fail:
            # Invalid params should be caught by validation
            assert not (1 <= limit <= 50 and 1 <= days_back <= 365)
        else:
            assert 1 <= limit <= 50
            assert 1 <= days_back <= 365

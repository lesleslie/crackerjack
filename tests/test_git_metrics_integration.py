"""Test suite for GitMetricsSessionCollector.

Tests the integration between SessionMetrics and GitMetricsCollector,
including collection of commit velocity, branch metrics, merge patterns,
and conventional commit compliance.
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from crackerjack.integration.git_metrics_integration import (
    GitMetricsSessionCollector,
)
from crackerjack.models.session_metrics import SessionMetrics


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_session_metrics():
    """Fixture providing empty SessionMetrics for population."""
    return SessionMetrics(
        session_id="git-collector-test-123",
        project_path=Path("/tmp/test_git_project"),
        start_time=datetime(2025, 2, 11, 10, 0, 0),
    )


@pytest.fixture
def mock_git_collector():
    """Mock GitMetricsCollector with predefined return values."""
    collector = MagicMock()

    # Mock collect_commit_metrics for velocity (1-hour window)
    velocity_metrics = MagicMock()
    velocity_metrics.avg_commits_per_hour = 4.5
    velocity_metrics.conventional_compliance_rate = 0.85

    # Mock collect_commit_metrics for conventional compliance (30-day window)
    compliance_metrics = MagicMock()
    compliance_metrics.conventional_compliance_rate = 0.92

    def mock_collect_commit_metrics(since=None):
        """Return different metrics based on time window."""
        if since and (datetime.now() - since) < timedelta(hours=2):
            return velocity_metrics
        return compliance_metrics

    collector.collect_commit_metrics = MagicMock(side_effect=mock_collect_commit_metrics)

    # Mock collect_branch_activity
    branch_metrics = MagicMock()
    branch_metrics.total_branches = 7
    collector.collect_branch_activity = MagicMock(return_value=branch_metrics)

    # Mock collect_merge_patterns
    merge_metrics = MagicMock()
    merge_metrics.merge_success_rate = 0.88
    collector.collect_merge_patterns = MagicMock(return_value=merge_metrics)

    return collector


@pytest.fixture
def mock_executor():
    """Mock SecureSubprocessExecutorProtocol."""
    return MagicMock()


@pytest.fixture
def temp_git_repo(tmp_path):
    """Fixture creating a temporary git repository."""
    import subprocess

    repo_path = tmp_path / "git_repo"
    repo_path.mkdir()

    # Initialize git repository
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    # Create initial commit
    test_file = repo_path / "test.txt"
    test_file.write_text("Initial content")
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: initial commit"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    )

    return repo_path


# ============================================================================
# Initialization Tests
# ============================================================================


def test_collector_initialization(sample_session_metrics, mock_executor):
    """Test that GitMetricsSessionCollector initializes correctly."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=None,
    )
    assert collector.session_metrics == sample_session_metrics
    assert collector.project_path == str(sample_session_metrics.project_path)
    assert collector._collector is None


def test_collector_initialization_with_provided_collector(
    sample_session_metrics, mock_git_collector
):
    """Test that collector can be initialized with explicit GitMetricsCollector."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=mock_git_collector,
    )
    assert collector._collector is mock_git_collector


# ============================================================================
# Auto-Instantiation Tests
# ============================================================================


@patch('crackerjack.integration.git_metrics_integration.GitMetricsCollector')
def test_auto_instantiates_collector(mock_git_collector_class, sample_session_metrics, mock_executor):
    """Test that _get_collector auto-instantiates GitMetricsCollector if None."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=None,
    )

    assert collector._collector is None
    result = collector._get_collector(mock_executor)
    assert result is not None
    assert collector._collector is result
    mock_git_collector_class.assert_called_once()


def test_get_collector_reuses_instance(
    sample_session_metrics, mock_executor, mock_git_collector
):
    """Test that _get_collector reuses existing instance."""
    session_collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=mock_git_collector,
    )

    result1 = session_collector._get_collector(mock_executor)
    result2 = session_collector._get_collector(mock_executor)
    assert result1 is result2
    assert result1 is mock_git_collector


# ============================================================================
# Collection Tests (Success Paths)
# ============================================================================


@pytest.mark.asyncio
async def test_collect_commit_velocity(sample_session_metrics, mock_git_collector):
    """Test collection of commit velocity metrics."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=mock_git_collector,
    )

    mock_executor = MagicMock()
    velocity = await collector._collect_commit_velocity(mock_git_collector)

    assert velocity == 4.5
    mock_git_collector.collect_commit_metrics.assert_called()


@pytest.mark.asyncio
async def test_collect_branch_count(sample_session_metrics, mock_git_collector):
    """Test collection of branch count metrics."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=mock_git_collector,
    )

    mock_executor = MagicMock()
    count = await collector._collect_branch_count(mock_git_collector)

    assert count == 7
    mock_git_collector.collect_branch_activity.assert_called_once()


@pytest.mark.asyncio
async def test_collect_merge_success_rate(sample_session_metrics, mock_git_collector):
    """Test collection of merge success rate."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=mock_git_collector,
    )

    mock_executor = MagicMock()
    rate = await collector._collect_merge_success_rate(mock_git_collector)

    assert rate == 0.88
    mock_git_collector.collect_merge_patterns.assert_called_once()


@pytest.mark.asyncio
async def test_collect_conventional_compliance(
    sample_session_metrics, mock_git_collector
):
    """Test collection of conventional commit compliance."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=mock_git_collector,
    )

    mock_executor = MagicMock()
    compliance = await collector._collect_conventional_compliance(mock_git_collector)

    assert compliance == 0.92


def test_workflow_efficiency_calculation():
    """Test workflow efficiency score calculation."""
    # Create a dummy instance for testing the method
    dummy_metrics = SessionMetrics(
        session_id="dummy",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
    )
    collector = GitMetricsSessionCollector(
        session_metrics=dummy_metrics,
        project_path="/tmp/test",
        collector=None,
    )

    # Test case 1: All metrics available
    score = collector._calculate_workflow_score(
        commit_velocity=5.0,  # Normalized to 0.5
        merge_success_rate=0.8,
        conventional_compliance=0.9,
    )
    expected = (0.5 * 0.40) + (0.8 * 0.35) + (0.9 * 0.25)
    assert score == round(expected * 100, 1)

    # Test case 2: Some metrics None
    score2 = collector._calculate_workflow_score(
        commit_velocity=None,
        merge_success_rate=0.7,
        conventional_compliance=0.6,
    )
    expected2 = (0.0 * 0.40) + (0.7 * 0.35) + (0.6 * 0.25)
    assert score2 == round(expected2 * 100, 1)

    # Test case 3: High velocity (>10 caps at 1.0)
    score3 = collector._calculate_workflow_score(
        commit_velocity=15.0,  # Normalized to 1.0
        merge_success_rate=0.9,
        conventional_compliance=0.95,
    )
    expected3 = (1.0 * 0.40) + (0.9 * 0.35) + (0.95 * 0.25)
    assert score3 == round(expected3 * 100, 1)


# ============================================================================
# Full Session Collection Tests
# ============================================================================


@pytest.mark.asyncio
async def test_collect_session_metrics_full(
    sample_session_metrics, mock_git_collector, mock_executor
):
    """Test complete session metrics collection."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=mock_git_collector,
    )

    result = await collector.collect_session_metrics(mock_executor)

    assert result is sample_session_metrics
    assert sample_session_metrics.git_commit_velocity == 4.5
    assert sample_session_metrics.git_branch_count == 7
    assert sample_session_metrics.git_merge_success_rate == 0.88
    assert sample_session_metrics.conventional_commit_compliance == 0.92
    assert sample_session_metrics.git_workflow_efficiency_score is not None


@pytest.mark.asyncio
async def test_collection_updates_session_metrics_in_place(
    sample_session_metrics, mock_git_collector, mock_executor
):
    """Test that collection updates the same SessionMetrics instance."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=mock_git_collector,
    )

    original_id = sample_session_metrics.session_id
    await collector.collect_session_metrics(mock_executor)

    assert sample_session_metrics.session_id == original_id
    assert sample_session_metrics.git_commit_velocity is not None


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
async def test_collect_commit_velocity_error_returns_zero(
    sample_session_metrics,
):
    """Test that _collect_commit_velocity returns 0.0 on error."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=None,
    )

    mock_collector = MagicMock()
    mock_collector.collect_commit_metrics.side_effect = Exception("Collection failed")

    velocity = await collector._collect_commit_velocity(mock_collector)
    assert velocity == 0.0


@pytest.mark.asyncio
async def test_collect_branch_count_error_returns_zero(sample_session_metrics):
    """Test that _collect_branch_count returns 0 on error."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=None,
    )

    mock_collector = MagicMock()
    mock_collector.collect_branch_activity.side_effect = Exception("Branch failed")

    count = await collector._collect_branch_count(mock_collector)
    assert count == 0


@pytest.mark.asyncio
async def test_collect_merge_success_rate_error_returns_one(
    sample_session_metrics,
):
    """Test that _collect_merge_success_rate returns 1.0 on error."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=None,
    )

    mock_collector = MagicMock()
    mock_collector.collect_merge_patterns.side_effect = Exception("Merge failed")

    rate = await collector._collect_merge_success_rate(mock_collector)
    assert rate == 1.0


@pytest.mark.asyncio
async def test_collect_conventional_compliance_error_returns_zero(
    sample_session_metrics,
):
    """Test that _collect_conventional_compliance returns 0.0 on error."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=None,
    )

    mock_collector = MagicMock()
    mock_collector.collect_commit_metrics.side_effect = Exception("Compliance failed")

    compliance = await collector._collect_conventional_compliance(mock_collector)
    assert compliance == 0.0


@pytest.mark.asyncio
async def test_git_not_repository_error(sample_session_metrics, mock_executor):
    """Test handling of non-git repository paths."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path="/tmp/nonexistent_repo_12345",
        collector=None,
    )

    # Should not raise exception, but set null metrics
    result = await collector.collect_session_metrics(mock_executor)

    assert result is sample_session_metrics
    assert sample_session_metrics.git_commit_velocity is None


def test_set_null_metrics_clears_all_git_metrics(sample_session_metrics):
    """Test that _set_null_metrics clears all git-related fields."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=None,
    )

    # Set some values
    sample_session_metrics.git_commit_velocity = 5.0
    sample_session_metrics.git_branch_count = 10
    sample_session_metrics.git_merge_success_rate = 0.8
    sample_session_metrics.conventional_commit_compliance = 0.9
    sample_session_metrics.git_workflow_efficiency_score = 75.0

    # Clear them
    collector._set_null_metrics()

    assert sample_session_metrics.git_commit_velocity is None
    assert sample_session_metrics.git_branch_count is None
    assert sample_session_metrics.git_merge_success_rate is None
    assert sample_session_metrics.conventional_commit_compliance is None
    assert sample_session_metrics.git_workflow_efficiency_score is None


# ============================================================================
# Async Execution Tests
# ============================================================================


@pytest.mark.asyncio
async def test_async_execution_non_blocking(sample_session_metrics, mock_git_collector):
    """Test that collection methods are async and non-blocking."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=mock_git_collector,
    )

    mock_executor = MagicMock()

    # All these should return awaitable coroutines
    assert hasattr(collector.collect_session_metrics(mock_executor), "__await__")
    assert hasattr(collector._collect_commit_velocity(mock_git_collector), "__await__")
    assert hasattr(collector._collect_branch_count(mock_git_collector), "__await__")
    assert hasattr(
        collector._collect_merge_success_rate(mock_git_collector), "__await__"
    )
    assert hasattr(
        collector._collect_conventional_compliance(mock_git_collector), "__await__"
    )


@pytest.mark.asyncio
async def test_multiple_collections_sequential(sample_session_metrics, mock_git_collector):
    """Test that multiple sequential collections work correctly."""
    collector = GitMetricsSessionCollector(
        session_metrics=sample_session_metrics,
        project_path=str(sample_session_metrics.project_path),
        collector=mock_git_collector,
    )

    mock_executor = MagicMock()

    # First collection
    await collector.collect_session_metrics(mock_executor)
    first_velocity = sample_session_metrics.git_commit_velocity

    # Reset metrics
    sample_session_metrics.git_commit_velocity = None

    # Second collection
    await collector.collect_session_metrics(mock_executor)
    second_velocity = sample_session_metrics.git_commit_velocity

    assert first_velocity == second_velocity


# ============================================================================
# Scoring Edge Cases
# ============================================================================


def test_workflow_score_all_none():
    """Test workflow score calculation with all None values."""
    dummy_metrics = SessionMetrics(
        session_id="dummy",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
    )
    collector = GitMetricsSessionCollector(
        session_metrics=dummy_metrics,
        project_path="/tmp/test",
        collector=None,
    )
    score = collector._calculate_workflow_score(
        commit_velocity=None,
        merge_success_rate=None,
        conventional_compliance=None,
    )
    expected = (0.0 * 0.40) + (1.0 * 0.35) + (0.0 * 0.25)
    assert score == round(expected * 100, 1)


def test_workflow_score_zero_velocity():
    """Test workflow score with zero velocity."""
    dummy_metrics = SessionMetrics(
        session_id="dummy",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
    )
    collector = GitMetricsSessionCollector(
        session_metrics=dummy_metrics,
        project_path="/tmp/test",
        collector=None,
    )
    score = collector._calculate_workflow_score(
        commit_velocity=0.0,
        merge_success_rate=0.8,
        conventional_compliance=0.7,
    )
    expected = (0.0 * 0.40) + (0.8 * 0.35) + (0.7 * 0.25)
    assert score == round(expected * 100, 1)


def test_workflow_score_perfect_metrics():
    """Test workflow score with perfect metrics."""
    dummy_metrics = SessionMetrics(
        session_id="dummy",
        project_path=Path("/tmp/test"),
        start_time=datetime.now(),
    )
    collector = GitMetricsSessionCollector(
        session_metrics=dummy_metrics,
        project_path="/tmp/test",
        collector=None,
    )
    score = collector._calculate_workflow_score(
        commit_velocity=10.0,  # Caps at 1.0 normalized
        merge_success_rate=1.0,
        conventional_compliance=1.0,
    )
    expected = (1.0 * 0.40) + (1.0 * 0.35) + (1.0 * 0.25)
    assert score == round(expected * 100, 1)


# ============================================================================
# Set Null Metrics Tests
# ============================================================================

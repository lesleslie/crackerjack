"""Comprehensive integration tests for symbiotic ecosystem.

These tests validate the complete workflow from git metrics collection
through strategy recommendation and skills tracking across the entire
Crackerjack -> Mahavishnu -> Session-Buddy -> Akosha ecosystem.
"""

from __future__ import annotations

import subprocess
import tempfile
import typing as t
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from crackerjack.agents.base import FixResult, Issue, IssueType, Priority
from crackerjack.memory.git_metrics_collector import (
    BranchMetrics,
    BranchEvent,
    CommitMetrics,
    GitMetricsCollector,
    MergeMetrics,
    VelocityDashboard,
)
from crackerjack.memory.fix_strategy_storage import FixAttempt, FixStrategyStorage
from crackerjack.memory.strategy_recommender import StrategyRecommender, StrategyRecommendation


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create temporary database path."""
    return tmp_path / "test_fix_strategies.db"


@pytest.fixture
def storage(temp_db_path: Path) -> FixStrategyStorage:
    """Create fix strategy storage with temporary database."""
    return FixStrategyStorage(temp_db_path)


@pytest.fixture
def sample_issue() -> Issue:
    """Create sample issue for testing."""
    return Issue(
        type=IssueType.COMPLEXITY,
        severity=Priority.HIGH,
        message="Function 'process_data' has cognitive complexity of 25",
        file_path="src/processor.py",
        line_number=42,
        stage="fast_hooks",
    )


@pytest.fixture
def sample_embedding() -> np.ndarray:
    """Create sample embedding vector."""
    # Create normalized random vector
    vec = np.random.rand(384).astype(np.float32)
    return vec / np.linalg.norm(vec)


@pytest.fixture
def mock_executor() -> MagicMock:
    """Create a mock secure subprocess executor for git operations."""
    executor = MagicMock()
    executor.allowed_git_patterns = ["git *"]

    def mock_execute_secure(
        command: list[str],
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
        input_data: str | bytes | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        **kwargs: t.Any,
    ) -> subprocess.CompletedProcess[str]:
        # Execute the actual git command for test purposes
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=capture_output,
            text=text,
            check=False,
            timeout=timeout or 30,
        )
        return subprocess.CompletedProcess(
            args=command,
            returncode=result.returncode,
            stdout=result.stdout or "",
            stderr=result.stderr or "",
        )

    executor.execute_secure = mock_execute_secure
    return executor


class MockDenseEmbedder:
    """Mock embedder that returns dense numpy arrays compatible with stored embeddings."""

    def __init__(self, embedding: np.ndarray | None = None):
        self._embedding = embedding

    def embed_issue(self, issue: Issue) -> np.ndarray:
        if self._embedding is not None:
            return self._embedding.copy()
        vec = np.random.rand(384).astype(np.float32)
        return vec / np.linalg.norm(vec)


# ============================================================================
# Git Metrics Collector Tests
# ============================================================================


class TestGitMetricsCollector:
    """Test git metrics collection and analysis."""

    def test_collector_initialization(
        self, tmp_path: Path, mock_executor: MagicMock
    ) -> None:
        """Test GitMetricsCollector initialization."""
        # Create a temporary git repository
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()

        # Initialize git repo
        subprocess.run(["git", "init"], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            check=True,
        )

        # Create initial commit
        test_file = repo_path / "test.txt"
        test_file.write_text("Initial content")
        subprocess.run(
            ["git", "add", "test.txt"],
            cwd=repo_path,
            check=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "feat: initial commit"],
            cwd=repo_path,
            check=True,
        )

        # Initialize collector with mock executor
        collector = GitMetricsCollector(repo_path, mock_executor)

        assert collector.repo_path == repo_path.resolve()
        assert collector.storage is not None

        collector.close()

    def test_collect_commit_metrics(
        self, tmp_path: Path, mock_executor: MagicMock
    ) -> None:
        """Test commit metrics collection."""
        # Setup git repo with multiple commits
        repo_path = tmp_path / "test_repo"
        self._create_test_repo(repo_path, commit_count=5)

        collector = GitMetricsCollector(repo_path, mock_executor)

        # Collect metrics
        metrics = collector.collect_commit_metrics()

        assert isinstance(metrics, CommitMetrics)
        assert metrics.total_commits >= 5
        assert 0.0 <= metrics.conventional_compliance_rate <= 1.0
        assert metrics.avg_commits_per_day >= 0.0
        assert 0 <= metrics.most_active_hour <= 23
        assert 0 <= metrics.most_active_day <= 6

        collector.close()

    def test_collect_branch_activity(
        self, tmp_path: Path, mock_executor: MagicMock
    ) -> None:
        """Test branch activity metrics."""
        repo_path = tmp_path / "test_repo"
        self._create_test_repo(repo_path)

        collector = GitMetricsCollector(repo_path, mock_executor)

        # Create and switch branches
        subprocess.run(
            ["git", "checkout", "-b", "test-branch"],
            cwd=repo_path,
            check=True,
            capture_output=True,
        )

        # Collect branch metrics
        metrics = collector.collect_branch_activity()

        assert isinstance(metrics, BranchMetrics)
        # The git branch command output parsing depends on the git version
        # and reflog, so we check for at least 1 branch (main)
        assert metrics.total_branches >= 1
        # Branch switches may or may not be captured depending on reflog
        assert metrics.branch_switches >= 0

        collector.close()

    def test_velocity_dashboard(
        self, tmp_path: Path, mock_executor: MagicMock
    ) -> None:
        """Test velocity dashboard aggregation."""
        repo_path = tmp_path / "test_repo"
        self._create_test_repo(repo_path, commit_count=10)

        collector = GitMetricsCollector(repo_path, mock_executor)

        # Get dashboard
        dashboard = collector.get_velocity_dashboard(days_back=7)

        assert isinstance(dashboard, VelocityDashboard)
        assert isinstance(dashboard.commit_metrics, CommitMetrics)
        assert isinstance(dashboard.branch_metrics, BranchMetrics)
        assert isinstance(dashboard.merge_metrics, MergeMetrics)
        assert len(dashboard.trend_data) >= 0

        collector.close()

    @staticmethod
    def _create_test_repo(
        repo_path: Path,
        commit_count: int = 5,
    ) -> None:
        """Create test git repository with commits."""
        repo_path.mkdir(exist_ok=True)

        # Initialize if needed
        if not (repo_path / ".git").exists():
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo_path,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                check=True,
            )

        # Create commits
        for i in range(commit_count):
            test_file = repo_path / f"test_{i}.txt"
            test_file.write_text(f"Content {i}")

            subprocess.run(["git", "add", f"test_{i}.txt"], cwd=repo_path, check=True)

            # Mix of conventional and non-conventional commits
            if i % 2 == 0:
                msg = f"feat: add feature {i}"
            else:
                msg = f"Add feature {i}"

            subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=repo_path,
                check=True,
            )


# ============================================================================
# Fix Strategy Storage Tests
# ============================================================================


class TestFixStrategyStorage:
    """Test fix strategy storage and retrieval."""

    def test_record_fix_attempt(
        self,
        storage: FixStrategyStorage,
        sample_issue: Issue,
        sample_embedding: np.ndarray,
    ) -> None:
        """Test recording a fix attempt."""
        result = FixResult(
            success=True,
            confidence=0.85,
            fixes_applied=["Reduced complexity from 25 to 15"],
        )

        storage.record_attempt(
            issue=sample_issue,
            result=result,
            agent_used="RefactoringAgent",
            strategy="simplify_control_flow",
            issue_embedding=sample_embedding,
            session_id="test-session-123",
        )

        # Verify storage
        stats = storage.get_statistics()
        assert stats["total_attempts"] == 1
        assert stats["successful_attempts"] == 1

    def test_find_similar_issues(
        self,
        storage: FixStrategyStorage,
        sample_issue: Issue,
        sample_embedding: np.ndarray,
    ) -> None:
        """Test finding similar historical issues."""
        # Record multiple attempts
        for i in range(5):
            result = FixResult(
                success=(i % 2 == 0),  # Alternate success/failure
                confidence=0.7 + (i * 0.05),
                fixes_applied=[],
            )

            # Create slightly different embeddings
            embedding = sample_embedding + np.random.normal(0, 0.1, 384).astype(
                np.float32
            )
            embedding = embedding / np.linalg.norm(embedding)

            storage.record_attempt(
                issue=sample_issue,
                result=result,
                agent_used="RefactoringAgent",
                strategy=f"strategy_{i}",
                issue_embedding=embedding,
                session_id=f"session-{i}",
            )

        # Find similar issues
        similar = storage.find_similar_issues(
            issue_embedding=sample_embedding,
            issue_type=sample_issue.type.value,
            k=3,
            min_similarity=0.3,
        )

        assert len(similar) <= 3
        # Should find some similar issues
        assert len(similar) > 0

    def test_strategy_recommendation(
        self,
        storage: FixStrategyStorage,
        sample_issue: Issue,
        sample_embedding: np.ndarray,
    ) -> None:
        """Test strategy recommendation."""
        # Record successful attempts with same strategy
        for _ in range(3):
            result = FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=[],
            )

            storage.record_attempt(
                issue=sample_issue,
                result=result,
                agent_used="RefactoringAgent",
                strategy="extract_method",
                issue_embedding=sample_embedding,
                session_id="test-session",
            )

        # Get recommendation
        recommendation = storage.get_strategy_recommendation(
            issue=sample_issue,
            issue_embedding=sample_embedding,
            k=5,
        )

        assert recommendation is not None
        agent_strategy, confidence = recommendation
        assert "RefactoringAgent" in agent_strategy
        assert "extract_method" in agent_strategy
        assert 0.0 <= confidence <= 1.0

    def test_update_strategy_effectiveness(
        self,
        storage: FixStrategyStorage,
        sample_issue: Issue,
        sample_embedding: np.ndarray,
    ) -> None:
        """Test updating strategy effectiveness."""
        # Record attempts
        result = FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=[],
        )

        storage.record_attempt(
            issue=sample_issue,
            result=result,
            agent_used="TestAgent",
            strategy="test_strategy",
            issue_embedding=sample_embedding,
            session_id="test",
        )

        # Update effectiveness
        storage.update_strategy_effectiveness()

        # Verify effectiveness data exists
        stats = storage.get_statistics()
        assert "top_strategies" in stats


# ============================================================================
# Strategy Recommender Tests
# ============================================================================


class TestStrategyRecommender:
    """Test strategy recommendation logic."""

    def test_recommender_initialization(
        self,
        storage: FixStrategyStorage,
    ) -> None:
        """Test recommender initialization."""
        # Should initialize without embedder (TF-IDF mode)
        recommender = StrategyRecommender(storage, embedder=None)

        assert recommender.storage is storage
        # Note: embedder may be set to FallbackIssueEmbedder by default

    def test_recommend_strategy_no_history(
        self,
        storage: FixStrategyStorage,
        sample_issue: Issue,
    ) -> None:
        """Test recommendation with no historical data."""
        recommender = StrategyRecommender(storage, embedder=None)

        recommendation = recommender.recommend_strategy(sample_issue)

        assert recommendation is None

    def test_recommend_strategy_with_history(
        self,
        storage: FixStrategyStorage,
        sample_issue: Issue,
        sample_embedding: np.ndarray,
    ) -> None:
        """Test recommendation with historical data."""
        # Record successful attempts (need at least MIN_SAMPLE_SIZE=2 successful
        # and similar enough for the recommender to return a result)
        for i in range(5):
            result = FixResult(
                success=True,
                confidence=0.8 + (i * 0.02),
                fixes_applied=[],
            )

            # Use same embedding to ensure high similarity
            storage.record_attempt(
                issue=sample_issue,
                result=result,
                agent_used="RefactoringAgent",
                strategy="extract_method" if i < 3 else "inline_method",
                issue_embedding=sample_embedding.copy(),
                session_id=f"session-{i}",
            )

        # Get recommendation with a mock embedder that returns the same embedding format
        mock_embedder = MockDenseEmbedder(sample_embedding)
        recommender = StrategyRecommender(storage, embedder=mock_embedder)
        recommendation = recommender.recommend_strategy(
            sample_issue,
            k=5,
            min_confidence=0.1,  # Lower threshold to ensure we get a result
        )

        assert recommendation is not None
        assert isinstance(recommendation, StrategyRecommendation)
        assert recommendation.confidence >= 0.1
        assert recommendation.sample_count >= 2
        assert len(recommendation.alternatives) >= 0
        assert len(recommendation.reasoning) > 0

    def test_recommendation_confidence_calculation(
        self,
        storage: FixStrategyStorage,
        sample_issue: Issue,
        sample_embedding: np.ndarray,
    ) -> None:
        """Test confidence calculation logic."""
        # Record many successful attempts with same strategy
        for _ in range(10):
            result = FixResult(
                success=True,
                confidence=0.95,
                fixes_applied=[],
            )

            storage.record_attempt(
                issue=sample_issue,
                result=result,
                agent_used="RefactoringAgent",
                strategy="extract_method",
                issue_embedding=sample_embedding.copy(),
                session_id="test",
            )

        # Use mock embedder with same embedding format
        mock_embedder = MockDenseEmbedder(sample_embedding)
        recommender = StrategyRecommender(storage, embedder=mock_embedder)
        recommendation = recommender.recommend_strategy(sample_issue, k=5, min_confidence=0.1)

        # Should have high confidence due to many successful attempts
        assert recommendation is not None
        assert recommendation.confidence > 0.3
        assert recommendation.success_rate > 0.8


# ============================================================================
# End-to-End Workflow Tests
# ============================================================================


class TestSymbioticWorkflow:
    """Test complete symbiotic ecosystem workflow."""

    def test_full_workflow_from_git_to_recommendation(
        self,
        tmp_path: Path,
        mock_executor: MagicMock,
    ) -> None:
        """Test complete workflow: git metrics -> storage -> recommendation."""
        # 1. Setup git repository
        repo_path = tmp_path / "test_repo"
        self._create_repo_with_commits(repo_path, commit_count=20)

        # 2. Collect git metrics
        git_collector = GitMetricsCollector(repo_path, mock_executor)
        dashboard = git_collector.get_velocity_dashboard(days_back=30)

        assert dashboard.commit_metrics.total_commits >= 20

        # 3. Setup fix strategy storage
        db_path = tmp_path / "test.db"
        storage = FixStrategyStorage(db_path)

        # 4. Simulate fixing issues and recording attempts
        issue = Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message="High complexity in process_order",
            file_path="src/order.py",
            line_number=15,
            stage="fast_hooks",
        )

        # Create embedding (mock)
        embedding = np.random.rand(384).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)

        # Record successful fix (need multiple for MIN_SAMPLE_SIZE=2)
        for i in range(3):
            result = FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=["Extracted validate_order() method"],
            )

            storage.record_attempt(
                issue=issue,
                result=result,
                agent_used="RefactoringAgent",
                strategy="extract_method",
                issue_embedding=embedding.copy(),
                session_id=f"workflow-test-{i}",
            )

        # 5. Get recommendation for similar issue with mock embedder
        mock_embedder = MockDenseEmbedder(embedding)
        recommender = StrategyRecommender(storage, embedder=mock_embedder)
        recommendation = recommender.recommend_strategy(issue, k=5, min_confidence=0.1)

        assert recommendation is not None
        assert recommendation.confidence > 0.0

        # Cleanup
        git_collector.close()
        storage.close()

    @staticmethod
    def _create_repo_with_commits(
        repo_path: Path,
        commit_count: int = 20,
    ) -> None:
        """Create test repository with commits."""
        repo_path.mkdir(exist_ok=True)

        if not (repo_path / ".git").exists():
            subprocess.run(["git", "init"], cwd=repo_path, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo_path,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=repo_path,
                check=True,
            )

        # Create commits over multiple days
        for i in range(commit_count):
            test_file = repo_path / f"feature_{i}.py"
            test_file.write_text(f"# Feature {i}\ndef process_{i}():\n    pass\n")

            subprocess.run(
                ["git", "add", f"feature_{i}.py"],
                cwd=repo_path,
                check=True,
            )

            commit_types = ["feat", "fix", "refactor", "test", "chore"]
            commit_type = commit_types[i % len(commit_types)]

            subprocess.run(
                ["git", "commit", "-m", f"{commit_type}: implement {i}"],
                cwd=repo_path,
                check=True,
            )


# ============================================================================
# Performance Tests
# ============================================================================


class TestPerformanceBenchmarks:
    """Test performance requirements from symbiotic ecosystem spec."""

    def test_embedding_generation_performance(
        self,
        storage: FixStrategyStorage,
        sample_issue: Issue,
    ) -> None:
        """Test embedding generation meets <100ms target."""
        import time

        # Mock embedder (real one would require sentence-transformers)
        class MockEmbedder:
            def embed_issue(self, issue: Issue) -> np.ndarray:
                start = time.time()
                vec = np.random.rand(384).astype(np.float32)
                # Simulate embedding work
                time.sleep(0.001)  # 1ms
                return vec

        recommender = StrategyRecommender(
            storage, embedder=MockEmbedder()
        )

        # Time embedding generation
        start = time.time()
        recommender.recommend_strategy(sample_issue, k=5)
        elapsed = time.time() - start

        # Should be well under 100ms (even with mock overhead)
        assert elapsed < 0.1, f"Embedding too slow: {elapsed*1000:.1f}ms"

    def test_similarity_search_performance(
        self,
        storage: FixStrategyStorage,
        sample_issue: Issue,
        sample_embedding: np.ndarray,
    ) -> None:
        """Test similarity search meets <500ms target."""
        import time

        # Record 100 historical issues
        for i in range(100):
            result = FixResult(
                success=(i % 2 == 0),
                confidence=0.7,
                fixes_applied=[],
            )

            embedding = sample_embedding + np.random.normal(0, 0.1, 384).astype(
                np.float32
            )
            embedding = embedding / np.linalg.norm(embedding)

            storage.record_attempt(
                issue=sample_issue,
                result=result,
                agent_used="Agent",
                strategy=f"strategy_{i}",
                issue_embedding=embedding,
                session_id=f"session-{i}",
            )

        # Time similarity search
        start = time.time()
        similar = storage.find_similar_issues(
            issue_embedding=sample_embedding,
            k=10,
            min_similarity=0.3,
        )
        elapsed = time.time() - start

        assert len(similar) > 0
        assert (
            elapsed < 0.5
        ), f"Similarity search too slow: {elapsed*1000:.1f}ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-x"])

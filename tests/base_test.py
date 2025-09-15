"""Base test class for all new crackerjack features."""

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@dataclass
class GitCommit:
    hash: str
    message: str
    author: str
    date: str


class IssueType(Enum):
    COMPLEXITY = "complexity"
    SECURITY = "security"
    FORMATTING = "formatting"
    DOCUMENTATION = "documentation"
    TEST_FAILURE = "test_failure"
    DRY_VIOLATION = "dry_violation"
    PERFORMANCE = "performance"
    IMPORTS = "imports"


@dataclass
class Issue:
    id: str
    type: IssueType
    message: str
    file_path: Path
    line_number: int = 0
    confidence: float = 0.0


class BaseCrackerjackFeatureTest:
    """Base test class with common utilities and fixtures for new features."""

    @pytest.fixture(scope="session")
    def test_project_structure(self, tmp_path_factory):
        """Create a complete test project structure for comprehensive testing."""
        project_root = tmp_path_factory.mktemp("crackerjack_test_project")

        # Create realistic project structure
        (project_root / "crackerjack").mkdir()
        (project_root / "tests").mkdir()
        (project_root / "docs").mkdir()

        # Create pyproject.toml
        pyproject_content = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "1.2.3"
description = "Test project for crackerjack testing"
"""
        (project_root / "pyproject.toml").write_text(pyproject_content)

        # Create CHANGELOG.md
        changelog_content = """# Changelog
All notable changes to this project will be documented in this file.

## [1.2.3] - 2024-01-01
### Added
- Initial implementation

"""
        (project_root / "CHANGELOG.md").write_text(changelog_content)

        return project_root

    @pytest.fixture
    def mock_git_service(self):
        """Mock GitService with realistic commit history."""
        mock = MagicMock()
        mock.get_commits_since_last_release.return_value = [
            GitCommit(
                hash="abc123",
                message="feat(auth): add password reset functionality",
                author="Test Author",
                date="2024-01-01",
            ),
            GitCommit(
                hash="def456",
                message="fix(api): resolve race condition in user creation",
                author="Test Author",
                date="2024-01-02",
            ),
            GitCommit(
                hash="ghi789",
                message="docs: update API documentation",
                author="Test Author",
                date="2024-01-03",
            ),
        ]
        return mock

    @pytest.fixture
    def performance_benchmark_context(self):
        """Context for performance testing with realistic data sets."""
        return {
            "small_codebase": {"files": 10, "issues": 25, "agents": 3},
            "medium_codebase": {"files": 100, "issues": 150, "agents": 5},
            "large_codebase": {"files": 1000, "issues": 500, "agents": 8},
        }

    def assert_performance_improvement(
        self, baseline_time: float, optimized_time: float, min_improvement: float = 0.30
    ):
        """Assert that performance improvement meets minimum threshold."""
        improvement = (baseline_time - optimized_time) / baseline_time
        assert improvement >= min_improvement, (
            f"Expected ≥{min_improvement:.0%} improvement, got {improvement:.0%} "
            f"(baseline: {baseline_time:.3f}s, optimized: {optimized_time:.3f}s)"
        )

    def assert_no_regression(self, before_metrics: dict, after_metrics: dict):
        """Assert that new features don't regress existing functionality."""
        for metric_name, before_value in before_metrics.items():
            after_value = after_metrics.get(metric_name)
            assert after_value is not None, f"Missing metric: {metric_name}"
            assert after_value >= before_value, (
                f"Regression in {metric_name}: {before_value} -> {after_value}"
            )


def create_mock_issues(
    count: int, types: int = 5, complexity_distribution: str = "normal"
) -> list[Issue]:
    """Create realistic mock issues for testing."""
    import random

    issue_types = [
        IssueType.COMPLEXITY,
        IssueType.SECURITY,
        IssueType.FORMATTING,
        IssueType.DOCUMENTATION,
        IssueType.TEST_FAILURE,
        IssueType.DRY_VIOLATION,
    ]

    issues = []
    for i in range(count):
        issue_type = random.choice(issue_types[:types])

        # Vary complexity based on distribution
        if complexity_distribution == "realistic":
            confidence = random.triangular(
                0.3, 0.95, 0.7
            )  # Most issues medium confidence
        else:
            confidence = random.uniform(0.3, 0.95)

        issue = Issue(
            id=f"test-issue-{i}",
            type=issue_type,
            message=f"Test issue {i} of type {issue_type.value}",
            file_path=Path(f"test_file_{i % 20}.py"),
            line_number=random.randint(1, 100),
            confidence=confidence,
        )
        issues.append(issue)

    return issues


def create_mock_git_commits(count: int, conventional: bool = True) -> list[GitCommit]:
    """Create mock git commits with optional conventional commit format."""
    import random

    commit_types = ["feat", "fix", "docs", "style", "refactor", "test", "chore"]
    commits = []

    for i in range(count):
        if conventional:
            commit_type = random.choice(commit_types)
            message = f"{commit_type}: implement feature {i}"
        else:
            message = f"Implement feature {i}"

        commit = GitCommit(
            hash=f"{'a' * 8}{i:03d}",
            message=message,
            author="Test Author",
            date=f"2024-01-{i % 28 + 1:02d}",
        )
        commits.append(commit)

    return commits


class PerformanceTestHelper:
    """Helper class for performance testing."""

    @staticmethod
    def measure_execution_time(func):
        """Decorator to measure function execution time."""

        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = time.time() - start_time
            result._execution_time = execution_time
            return result

        return wrapper

    @staticmethod
    def assert_performance_target(
        baseline_time: float,
        optimized_time: float,
        target_improvement: float,
        feature_name: str,
    ):
        """Assert performance improvement meets target."""
        actual_improvement = (baseline_time - optimized_time) / baseline_time
        assert actual_improvement >= target_improvement, (
            f"{feature_name} performance improvement "
            f"({actual_improvement:.1%}) below target ({target_improvement:.1%})"
        )

    @staticmethod
    def benchmark_memory_usage(func):
        """Measure memory usage of function."""
        try:
            import psutil

            process = psutil.Process()

            async def wrapper(*args, **kwargs):
                initial_memory = process.memory_info().rss
                result = await func(*args, **kwargs)
                final_memory = process.memory_info().rss

                result._memory_delta = final_memory - initial_memory
                return result

            return wrapper
        except ImportError:
            # If psutil is not available, return the function unchanged
            return func

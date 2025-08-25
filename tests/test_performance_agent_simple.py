"""Simple tests for PerformanceAgent."""

import tempfile
from pathlib import Path

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.performance_agent import PerformanceAgent


@pytest.fixture
def temp_context():
    """Create a temporary AgentContext for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        context = AgentContext(project_path=Path(temp_dir))
        yield context


@pytest.fixture
def performance_agent(temp_context):
    """Create a PerformanceAgent instance for testing."""
    return PerformanceAgent(temp_context)


class TestPerformanceAgentSimple:
    """Simple test cases for PerformanceAgent."""

    def test_get_supported_types(self, performance_agent) -> None:
        """Test that PerformanceAgent supports PERFORMANCE type."""
        supported_types = performance_agent.get_supported_types()
        assert IssueType.PERFORMANCE in supported_types
        assert len(supported_types) == 1

    @pytest.mark.asyncio
    async def test_can_handle_performance_issue(self, performance_agent) -> None:
        """Test that PerformanceAgent can handle performance issues with correct confidence."""
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            message="Inefficient list concatenation",
            file_path="/test/main.py",
            severity=Priority.MEDIUM,
        )

        confidence = await performance_agent.can_handle(issue)
        assert confidence == 0.85

    @pytest.mark.asyncio
    async def test_cannot_handle_other_issue_types(self, performance_agent) -> None:
        """Test that PerformanceAgent returns 0.0 confidence for non-performance issues."""
        issue = Issue(
            id="sec-001",
            type=IssueType.SECURITY,
            message="Security vulnerability",
            file_path="/test/main.py",
            severity=Priority.HIGH,
        )

        confidence = await performance_agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_analyze_and_fix_with_nonexistent_file(
        self, performance_agent
    ) -> None:
        """Test handling of nonexistent file."""
        issue = Issue(
            id="perf-002",
            type=IssueType.PERFORMANCE,
            message="Performance issue",
            file_path="/nonexistent/file.py",
            severity=Priority.MEDIUM,
        )

        result = await performance_agent.analyze_and_fix(issue)

        # Should not crash and should return a failure result
        assert result is not None
        assert result.success is False
        assert len(result.remaining_issues) > 0

    @pytest.mark.asyncio
    async def test_analyze_and_fix_with_no_file_path(self, performance_agent) -> None:
        """Test handling of issue without file path."""
        issue = Issue(
            id="perf-003",
            type=IssueType.PERFORMANCE,
            message="Performance issue without file",
            file_path=None,
            severity=Priority.HIGH,
        )

        result = await performance_agent.analyze_and_fix(issue)

        # Should not crash and should return a failure result
        assert result is not None
        assert result.success is False
        assert len(result.remaining_issues) > 0

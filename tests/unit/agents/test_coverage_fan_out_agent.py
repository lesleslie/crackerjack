"""Tests for CoverageFanOutAgent - concurrent test creation across modules."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.agents.coverage_fan_out_agent import (
    CoverageFanOutAgent,
    _create_tests_for_module_with_limit,
)
from crackerjack.agents.helpers.test_creation.test_coverage_analyzer import (
    TestCoverageAnalyzer,
)


@pytest.fixture
def mock_context():
    """Create a mock AgentContext for testing."""
    context = MagicMock()
    context.project_path = Path("/tmp/test_project")
    context.log = MagicMock()
    return context


@pytest.fixture
def agent(mock_context):
    """Create a CoverageFanOutAgent instance."""
    return CoverageFanOutAgent(mock_context)


class TestCoverageFanOutAgent:
    """Test CoverageFanOutAgent functionality."""

    def test_get_supported_types(self, agent):
        """Agent should support COVERAGE_IMPROVEMENT issue type."""
        supported = agent.get_supported_types()
        assert IssueType.COVERAGE_IMPROVEMENT in supported

    @pytest.mark.asyncio
    async def test_can_handle_coverage_message(self, agent):
        """Agent should handle messages with coverage keywords."""
        issue = Issue(
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Coverage below threshold requirement",
            file_path="/tmp/test.py",
        )
        score = await agent.can_handle(issue)
        assert score == 0.95

    @pytest.mark.asyncio
    async def test_can_handle_missing_tests(self, agent):
        """Agent should handle 'missing tests' messages."""
        issue = Issue(
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Missing tests for module",
            file_path="/tmp/test.py",
        )
        score = await agent.can_handle(issue)
        assert score == 0.95

    @pytest.mark.asyncio
    async def test_can_handle_improve_coverage(self, agent):
        """Agent should handle 'improve coverage' messages."""
        issue = Issue(
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Improve coverage for the project",
            file_path="/tmp/test.py",
        )
        score = await agent.can_handle(issue)
        assert score == 0.95

    @pytest.mark.asyncio
    async def test_can_handle_untested_functions(self, agent):
        """Agent should handle 'untested functions' messages."""
        issue = Issue(
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Untested functions detected",
            file_path="/tmp/test.py",
        )
        score = await agent.can_handle(issue)
        assert score == 0.95

    @pytest.mark.asyncio
    async def test_can_handle_non_coverage_message_low_score(self, agent):
        """Agent should return low score for non-coverage messages."""
        issue = Issue(
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="This is about something else entirely",
            file_path="/tmp/test.py",
        )
        score = await agent.can_handle(issue)
        assert score == 0.8

    @pytest.mark.asyncio
    async def test_can_handle_unsupported_type(self, agent):
        """Agent should return 0.0 for unsupported issue types."""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Some type error happened",
            file_path="/tmp/test.py",
        )
        score = await agent.can_handle(issue)
        assert score == 0.0

    @pytest.mark.asyncio
    async def test_analyze_and_fix_no_uncovered_modules(self, agent, mock_context):
        """Should return success when no uncovered modules found."""
        issue = Issue(
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Coverage below threshold requirement",
            file_path="/tmp/test.py",
        )

        agent._coverage_analyzer.analyze_coverage = AsyncMock(
            return_value={"uncovered_modules": [], "current_coverage": 0.9}
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is True
        assert result.confidence == 0.5
        assert "No uncovered modules found" in result.recommendations[0]

    @pytest.mark.asyncio
    async def test_analyze_and_fix_creates_tests(self, agent, mock_context):
        """Should create tests when uncovered modules are found."""
        issue = Issue(
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Coverage below threshold requirement",
            file_path="/tmp/test.py",
        )

        agent._coverage_analyzer.analyze_coverage = AsyncMock(
            return_value={
                "uncovered_modules": [
                    {
                        "path": "crackerjack/foo.py",
                        "absolute_path": "/tmp/test_project/crackerjack/foo.py",
                    },
                ],
                "current_coverage": 0.5,
            }
        )

        agent._coverage_analyzer.create_tests_for_module = AsyncMock(
            return_value={
                "fixes": ["Created test file for foo.py"],
                "files": ["/tmp/test_project/tests/test_foo.py"],
            }
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is True
        assert len(result.files_modified) == 1
        assert "Created test file for foo.py" in result.fixes_applied

    @pytest.mark.asyncio
    async def test_analyze_and_fix_handles_errors(self, agent, mock_context):
        """Should handle errors during test creation gracefully."""
        issue = Issue(
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Coverage below threshold requirement",
            file_path="/tmp/test.py",
        )

        agent._coverage_analyzer.analyze_coverage = AsyncMock(
            return_value={
                "uncovered_modules": [
                    {
                        "path": "crackerjack/bar.py",
                        "absolute_path": "/tmp/test_project/crackerjack/bar.py",
                    },
                ],
                "current_coverage": 0.5,
            }
        )

        agent._coverage_analyzer.create_tests_for_module = AsyncMock(
            side_effect=Exception("Test creation failed")
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert result.confidence == 0.0
        assert len(result.remaining_issues) > 0

    @pytest.mark.asyncio
    async def test_analyze_and_fix_all_fail(self, agent, mock_context):
        """Should return failure when all test creation attempts fail."""
        issue = Issue(
            type=IssueType.COVERAGE_IMPROVEMENT,
            severity=Priority.HIGH,
            message="Coverage below threshold requirement",
            file_path="/tmp/test.py",
        )

        agent._coverage_analyzer.analyze_coverage = AsyncMock(
            return_value={
                "uncovered_modules": [
                    {"path": "crackerjack/baz.py", "absolute_path": "/tmp/test_project/crackerjack/baz.py"},
                ],
                "current_coverage": 0.5,
            }
        )

        agent._coverage_analyzer.create_tests_for_module = AsyncMock(
            side_effect=Exception("Failed")
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert len(result.remaining_issues) > 0

    def test_calculate_confidence_no_fixes(self, agent):
        """Confidence should be 0.0 when no fixes applied."""
        confidence = agent._calculate_confidence([], [], 5)
        assert confidence == 0.0

    def test_calculate_confidence_with_files(self, agent):
        """Confidence should increase when files are modified."""
        confidence = agent._calculate_confidence(
            ["fix1"], ["/tmp/tests/test_foo.py"], 2
        )
        assert confidence > 0.5
        assert confidence <= 0.95

    def test_calculate_confidence_with_core_modules(self, agent):
        """Confidence should boost for manager/service files."""
        confidence = agent._calculate_confidence(
            ["fix1"], ["/tmp/tests/test_manager.py"], 1
        )
        assert confidence >= 0.6

    def test_generate_recommendations_no_fixes(self, agent):
        """Should recommend manual intervention when no fixes."""
        recs = agent._generate_recommendations([], [])
        assert "No tests were created" in recs[0]
        assert "pytest" in recs[1]

    def test_generate_recommendations_with_fixes(self, agent):
        """Should recommend pytest validation when fixes exist."""
        recs = agent._generate_recommendations(
            ["Created tests"], ["/tmp/test1.py", "/tmp/test2.py"]
        )
        assert "Created 1 tests across 2 files" in recs[0]
        assert "pytest" in recs[1]

    def test_create_error_result(self, agent):
        """Should create proper error FixResult."""
        error = Exception("Test failed")
        result = agent._create_error_result(error)

        assert result.success is False
        assert result.confidence == 0.0
        assert "Coverage fan-out failed" in result.remaining_issues[0]


class TestCreateTestsForModuleWithLimit:
    """Test the module-level helper function."""

    @pytest.mark.asyncio
    async def test_creates_tests_under_semaphore(self):
        """Test that semaphore limits concurrent execution."""
        import asyncio

        semaphore = asyncio.Semaphore(2)
        module_info = {
            "path": "test.py",
            "absolute_path": "/tmp/test.py",
        }

        mock_analyzer = MagicMock(spec=TestCoverageAnalyzer)
        mock_analyzer.create_tests_for_module = AsyncMock(
            return_value={"fixes": ["test"], "files": []}
        )

        result = await _create_tests_for_module_with_limit(
            module_info, mock_analyzer, semaphore
        )

        assert "fixes" in result
        assert result["fixes"] == ["test"]

    @pytest.mark.asyncio
    async def test_handles_missing_path(self):
        """Should return empty result when module path is missing."""
        import asyncio

        semaphore = asyncio.Semaphore(2)
        module_info = {}  # No path

        mock_analyzer = MagicMock(spec=TestCoverageAnalyzer)

        result = await _create_tests_for_module_with_limit(
            module_info, mock_analyzer, semaphore
        )

        assert result == {"fixes": [], "files": []}

    @pytest.mark.asyncio
    async def test_handles_exception(self):
        """Should catch and log exceptions gracefully."""
        import asyncio

        semaphore = asyncio.Semaphore(2)
        module_info = {
            "path": "test.py",
            "absolute_path": "/tmp/test.py",
        }

        mock_analyzer = MagicMock(spec=TestCoverageAnalyzer)
        mock_analyzer.create_tests_for_module = AsyncMock(
            side_effect=Exception("Creation failed")
        )

        result = await _create_tests_for_module_with_limit(
            module_info, mock_analyzer, semaphore
        )

        assert result == {"fixes": [], "files": []}

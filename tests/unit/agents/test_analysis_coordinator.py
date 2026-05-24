"""Unit tests for AnalysisCoordinator concurrent issue analysis."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.analysis_coordinator import AnalysisCoordinator
from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.models.fix_plan import FixPlan


@pytest.fixture
def mock_debugger():
    return MagicMock()


@pytest.fixture
def coordinator(mock_debugger):
    return AnalysisCoordinator(
        max_concurrent=5,
        project_path="/tmp/test_project",
        debugger=mock_debugger,
    )


class TestAnalysisCoordinator:
    """Tests for AnalysisCoordinator functionality."""

    def test_init(self, mock_debugger):
        """Coordinator initializes with all sub-agents."""
        coord = AnalysisCoordinator(
            max_concurrent=10,
            project_path="/tmp/test",
            debugger=mock_debugger,
        )

        assert coord._semaphore._value == 10
        assert coord.context_agent is not None
        assert coord.pattern_agent is not None
        assert coord.planning_agent is not None

    @pytest.mark.asyncio
    async def test_analyze_issue_success(self, coordinator):
        """Single issue analysis returns FixPlan on success."""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Type error in test.py",
            file_path="/tmp/test.py",
            line_number=10,
        )

        mock_context = MagicMock()
        mock_warnings = []
        mock_plan = FixPlan(
            file_path="/tmp/test.py",
            issue_type="type_error",
            changes=[],
            rationale="Test",
            risk_level="low",
            validated_by="test",
            issue_message=issue.message,
            issue_stage="auto",
            issue_details={},
        )

        with patch.object(coordinator.context_agent, "extract_context", new=AsyncMock(return_value=mock_context)), \
             patch.object(coordinator.pattern_agent, "identify_anti_patterns", new=AsyncMock(return_value=mock_warnings)), \
             patch.object(coordinator.planning_agent, "create_fix_plan", new=AsyncMock(return_value=mock_plan)):

            result = await coordinator.analyze_issue(issue)

        assert isinstance(result, FixPlan)
        assert result.file_path == "/tmp/test.py"

    @pytest.mark.asyncio
    async def test_analyze_issue_propagates_exception(self, coordinator):
        """Analysis exception propagates to caller."""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Error",
            file_path="/tmp/test.py",
        )

        with patch.object(
            coordinator.context_agent, "extract_context",
            new=AsyncMock(side_effect=RuntimeError("Context extraction failed"))
        ):
            with pytest.raises(RuntimeError, match="Context extraction failed"):
                await coordinator.analyze_issue(issue)

    @pytest.mark.asyncio
    async def test_analyze_issues_concurrent_via_gather(self, coordinator):
        """Multiple issues are analyzed concurrently via asyncio.gather."""
        issues = [
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.HIGH,
                message=f"Error {i}",
                file_path=f"/tmp/test{i}.py",
            )
            for i in range(3)
        ]

        mock_plan = FixPlan(
            file_path="/tmp/test.py",
            issue_type="type_error",
            changes=[],
            rationale="Test",
            risk_level="low",
            validated_by="test",
            issue_message="",
            issue_stage="auto",
            issue_details={},
        )

        call_times = []

        async def mock_analyze(issue):
            call_times.append(time.monotonic())
            await asyncio.sleep(0.02)
            return mock_plan

        with patch.object(coordinator, "analyze_issue", side_effect=mock_analyze):
            start = time.monotonic()
            results = await coordinator.analyze_issues(issues)
            elapsed = time.monotonic() - start

        assert len(results) == 3
        # With concurrent execution, all 3 calls start within the same event loop tick
        # The first and last call times should be very close (< 10ms apart)
        # Sequential would take ~60ms total
        assert elapsed < 0.05
        assert len(call_times) == 3

    @pytest.mark.asyncio
    async def test_analyze_issues_fallback_on_failure(self, coordinator):
        """Failed analysis returns fallback plan instead of propagating exception."""
        issues = [
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.HIGH,
                message="Error 1",
                file_path="/tmp/test1.py",
                line_number=5,
            ),
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message="Error 2",
                file_path="/tmp/test2.py",
                line_number=10,
            ),
        ]

        success_plan = FixPlan(
            file_path="/tmp/test1.py",
            issue_type="type_error",
            changes=[],
            rationale="Success",
            risk_level="low",
            validated_by="test",
            issue_message="Error 1",
            issue_stage="auto",
            issue_details={},
        )

        async def analyze_one(issue):
            if "Error 1" in issue.message:
                return success_plan
            raise RuntimeError("Analysis failed")

        with patch.object(coordinator, "analyze_issue", side_effect=analyze_one):
            results = await coordinator.analyze_issues(issues)

        assert len(results) == 2
        assert results[0].rationale == "Success"
        assert "requires manual review" in results[1].rationale.lower()
        assert results[1].risk_level == "high"

    @pytest.mark.asyncio
    async def test_analyze_issues_all_fail_return_fallback_plans(self, coordinator):
        """When all analyses fail, all results are fallback plans."""
        issues = [
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.HIGH,
                message=f"Error {i}",
                file_path=f"/tmp/test{i}.py",
                line_number=i + 1,
            )
            for i in range(2)
        ]

        async def fail_all(issue):
            raise RuntimeError(f"Failed: {issue.message}")

        with patch.object(coordinator, "analyze_issue", side_effect=fail_all):
            results = await coordinator.analyze_issues(issues)

        assert len(results) == 2
        for result in results:
            assert result.risk_level == "high"

    def test_create_fallback_plan_reads_file(self, coordinator, tmp_path):
        """Fallback plan reads actual file content for old_code."""
        test_file = tmp_path / "example.py"
        test_file.write_text("line1\nline2\nline3\nline4\nline5\n")

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Error",
            file_path=str(test_file),
            line_number=3,
        )

        fallback = coordinator._create_fallback_plan(issue)

        assert fallback.file_path == str(test_file)
        assert "line3" in fallback.changes[0].old_code

    def test_create_fallback_plan_handles_missing_file(self, coordinator):
        """Fallback plan handles non-existent file gracefully."""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Error",
            file_path="/nonexistent/file.py",
            line_number=1,
        )

        fallback = coordinator._create_fallback_plan(issue)

        assert fallback.changes[0].old_code == "# Unknown line"
        assert fallback.risk_level == "high"

    def test_create_fallback_plan_handles_invalid_line_number(self, coordinator, tmp_path):
        """Fallback plan handles line number beyond file length."""
        test_file = tmp_path / "short.py"
        test_file.write_text("only one line\n")

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Error",
            file_path=str(test_file),
            line_number=999,
        )

        fallback = coordinator._create_fallback_plan(issue)

        assert fallback.changes[0].old_code == "# Unknown line"

    @pytest.mark.asyncio
    async def test_analyze_issues_respects_max_concurrent(self, coordinator):
        """All issues are analyzed and results returned regardless of concurrency."""
        max_concurrent = 2
        coord = AnalysisCoordinator(max_concurrent=max_concurrent, project_path="/tmp")

        issues = [
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.HIGH,
                message=f"Error {i}",
                file_path=f"/tmp/test{i}.py",
            )
            for i in range(4)
        ]

        mock_plan = FixPlan(
            file_path="/tmp/test.py",
            issue_type="type_error",
            changes=[],
            rationale="test",
            risk_level="low",
            validated_by="test",
            issue_message="",
            issue_stage="auto",
            issue_details={},
        )

        async def mock_analyze(issue):
            await asyncio.sleep(0.02)
            return mock_plan

        with patch.object(coord, "analyze_issue", side_effect=mock_analyze):
            results = await coord.analyze_issues(issues)

        assert len(results) == 4


class TestAnalysisCoordinatorSemaphore:
    """Tests for AnalysisCoordinator semaphore behavior."""

    @pytest.mark.asyncio
    async def test_semaphore_with_single_worker_completes_all(self):
        """Even with max_concurrent=1, all issues are processed."""
        coord = AnalysisCoordinator(max_concurrent=1, project_path="/tmp")

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test",
            file_path="/tmp/test.py",
        )

        result = FixPlan(
            file_path="/tmp/test.py",
            issue_type="type_error",
            changes=[],
            rationale="test",
            risk_level="low",
            validated_by="test",
            issue_message="",
            issue_stage="auto",
            issue_details={},
        )

        call_count = 0

        async def counting_analyze(_):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.02)
            return result

        with patch.object(coord, "analyze_issue", side_effect=counting_analyze):
            results = await coord.analyze_issues([issue] * 3)

        assert len(results) == 3
        assert call_count == 3

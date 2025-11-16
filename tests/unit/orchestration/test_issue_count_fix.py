"""Tests for the issue count fix - distinguishing config errors from code issues.

This test suite verifies that hooks correctly report issue counts:
- Config/tool errors should show 0 issues (not forced to 1)
- Code quality failures should show actual count
- Parsing failures may show 1 if no parseable output
"""

import pytest
from unittest.mock import MagicMock
from uuid import uuid4
from pathlib import Path

from crackerjack.orchestration.hook_orchestrator import HookOrchestratorAdapter
from crackerjack.models.qa_results import QAResult, QAResultStatus, QACheckType


class TestIssueCountFix:
    """Test the fix for misleading '1 issue' display."""

    @pytest.fixture
    def orchestrator(self):
        """Create a mock HookOrchestratorAdapter for testing."""
        orchestrator = HookOrchestratorAdapter()
        return orchestrator

    def test_config_error_shows_zero_issues(self, orchestrator):
        """Config errors (status=ERROR, issues=0) should show 0 issues, not 1."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="ruff-format",
            check_type=QACheckType.FORMAT,
            status=QAResultStatus.ERROR,  # Config error
            message="Tool failed with exit code 1",
            details="",
            files_checked=[],
            files_modified=[],
            issues_found=0,  # No parseable issues
            issues_fixed=0,
            execution_time_ms=100.0,
            metadata={"exit_code": 1},
        )

        status = "failed"
        issues = []

        total_issues = orchestrator._calculate_total_issues(qa_result, status, issues)

        assert total_issues == 0, (
            "Config errors should show 0 issues, not 1. "
            "The '1 issue' was misleading users into thinking there were code problems."
        )

    def test_code_violations_show_actual_count(self, orchestrator):
        """Code violations should show the actual count (e.g., 95 E402 violations)."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="ruff-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.FAILURE,  # Actual violations
            message="Found 95 errors",
            details="file1.py:1:1: E402...\n" * 10 + "... and 85 more issues",
            files_checked=[Path("file1.py")],
            files_modified=[],
            issues_found=95,  # Actual count
            issues_fixed=0,
            execution_time_ms=100.0,
        )

        status = "failed"
        issues = ["file1.py:1:1: E402..."] * 10

        total_issues = orchestrator._calculate_total_issues(qa_result, status, issues)

        assert total_issues == 95, (
            "Actual code violations should show the real count, not forced to 1."
        )

    def test_parsing_failure_shows_one_issue(self, orchestrator):
        """Parsing failures (status=FAILURE, issues=0) may show 1 issue."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="custom-tool",
            check_type=QACheckType.LINT,
            status=QAResultStatus.FAILURE,  # Tool ran but output not parseable
            message="Tool returned non-zero exit",
            details="Unexpected output format",
            files_checked=[Path("file1.py")],
            files_modified=[],
            issues_found=0,  # Couldn't parse any issues
            issues_fixed=0,
            execution_time_ms=100.0,
        )

        status = "failed"
        issues = ["Tool output not parseable"]

        total_issues = orchestrator._calculate_total_issues(qa_result, status, issues)

        # For parsing failures, we may show 1 to indicate something went wrong
        # This is acceptable since the tool DID fail (status=FAILURE)
        assert total_issues in [0, 1], (
            "Parsing failures may show 0 or 1 depending on implementation."
        )

    def test_passed_hook_with_zero_issues(self, orchestrator):
        """Passed hooks with 0 issues should show 0."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="complexipy",
            check_type=QACheckType.COMPLEXITY,
            status=QAResultStatus.SUCCESS,  # Passed
            message="Total complexity 8909, no violations",
            details="",
            files_checked=[Path("file1.py")],
            files_modified=[],
            issues_found=0,  # No violations above threshold
            issues_fixed=0,
            execution_time_ms=100.0,
        )

        status = "passed"
        issues = []

        total_issues = orchestrator._calculate_total_issues(qa_result, status, issues)

        assert total_issues == 0, (
            "Passed hooks should show 0 issues when there are none."
        )

    def test_warning_status_shows_actual_count(self, orchestrator):
        """Warnings should show the actual count."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="custom-linter",
            check_type=QACheckType.LINT,
            status=QAResultStatus.WARNING,  # Warnings found
            message="Found 3 warnings",
            details="file1.py:1:1: W001...\nfile2.py:2:2: W002...\nfile3.py:3:3: W003...",
            files_checked=[Path("file1.py")],
            files_modified=[],
            issues_found=3,  # 3 warnings
            issues_fixed=0,
            execution_time_ms=100.0,
        )

        status = "passed"  # Warnings don't fail the hook
        issues = ["file1.py:1:1: W001...", "file2.py:2:2: W002...", "file3.py:3:3: W003..."]

        total_issues = orchestrator._calculate_total_issues(qa_result, status, issues)

        assert total_issues == 3, (
            "Warnings should show the actual count."
        )

    def test_tool_error_with_stderr_output(self, orchestrator):
        """Tool errors with stderr should show 0 issues."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="codespell",
            check_type=QACheckType.LINT,
            status=QAResultStatus.ERROR,  # Tool error
            message="Tool execution failed",
            details="ERROR: Invalid configuration file",
            files_checked=[],
            files_modified=[],
            issues_found=0,  # No code issues found
            issues_fixed=0,
            execution_time_ms=100.0,
            metadata={"exit_code": 1, "stderr": "ERROR: Invalid configuration file"},
        )

        status = "failed"
        issues = ["Hook codespell failed with no detailed output (exit code: 1)"]

        total_issues = orchestrator._calculate_total_issues(qa_result, status, issues)

        assert total_issues == 0, (
            "Tool errors with stderr should show 0 issues. "
            "The error message is already in the issues list for display."
        )


class TestIssueCountEdgeCases:
    """Test edge cases for issue count calculation."""

    @pytest.fixture
    def orchestrator(self):
        """Create a mock HookOrchestratorAdapter for testing."""
        return HookOrchestratorAdapter()

    def test_missing_qa_result_status_attribute(self, orchestrator):
        """Handle qa_result without status attribute gracefully."""
        # Create a mock qa_result without 'status' attribute
        qa_result = MagicMock()
        qa_result.issues_found = 0
        del qa_result.status  # Remove the status attribute

        status = "failed"
        issues = []

        # Should not crash, may show 0 or 1 depending on implementation
        total_issues = orchestrator._calculate_total_issues(qa_result, status, issues)

        assert isinstance(total_issues, int), (
            "Should return an integer even without status attribute."
        )

    def test_status_passed_with_nonzero_issues(self, orchestrator):
        """Edge case: status=passed but issues_found > 0 (shouldn't happen in practice)."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="weird-tool",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            message="Passed but found issues?",
            details="file1.py:1:1: Issue",
            files_checked=[Path("file1.py")],
            files_modified=[],
            issues_found=5,  # Non-zero but status=SUCCESS
            issues_fixed=0,
            execution_time_ms=100.0,
        )

        status = "passed"
        issues = ["file1.py:1:1: Issue"]

        total_issues = orchestrator._calculate_total_issues(qa_result, status, issues)

        # Should show the actual count even if status is inconsistent
        assert total_issues == 5, (
            "Even with inconsistent status, should show actual issues_found count."
        )

    def test_large_issue_count(self, orchestrator):
        """Test with a very large issue count."""
        qa_result = QAResult(
            check_id=uuid4(),
            check_name="ruff-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.FAILURE,
            message="Found 10000 errors",
            details="Too many to show...",
            files_checked=[Path("file1.py")],
            files_modified=[],
            issues_found=10000,  # Large count
            issues_fixed=0,
            execution_time_ms=100.0,
        )

        status = "failed"
        issues = ["file1.py:1:1: Error"] * 20  # Truncated display list

        total_issues = orchestrator._calculate_total_issues(qa_result, status, issues)

        assert total_issues == 10000, (
            "Should preserve large issue counts accurately."
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

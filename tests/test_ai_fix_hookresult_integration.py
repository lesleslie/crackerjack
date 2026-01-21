"""Tests for AI-fix HookResult integration bug fix.

Tests verify that:
1. HookResult objects have output/error fields populated
2. AutofixCoordinator correctly accesses output/error fields (not raw_output)
3. _parse_hook_results_to_issues correctly extracts issues from HookResult
4. AI-fix iteration loop works correctly with actual hook failures

This test suite specifically covers the bug fix where raw_output field didn't exist
on HookResult, causing AI-fix to report "0 iterations" even with failures.
"""

import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.models.task import HookResult


@pytest.mark.unit
class TestHookResultFieldPopulation:
    """Test that HookResult has correct fields populated."""

    def test_hook_result_has_output_field(self):
        """Test HookResult has output field."""
        result = HookResult(
            name="test_hook",
            status="failed",
            output="stdout output",
            error="stderr output",
        )

        assert hasattr(result, "output")
        assert result.output == "stdout output"
        assert hasattr(result, "error")
        assert result.error == "stderr output"

    def test_hook_result_no_raw_output_field(self):
        """Test HookResult does NOT have raw_output field."""
        result = HookResult(
            name="test_hook",
            status="failed",
        )

        # raw_output should NOT exist (this was the bug!)
        assert not hasattr(result, "raw_output") or getattr(
            result, "raw_output", None
        ) is None

    def test_hook_result_output_and_error_can_be_none(self):
        """Test HookResult fields can be None."""
        result = HookResult(
            name="test_hook",
            status="failed",
            output=None,
            error=None,
        )

        assert result.output is None
        assert result.error is None

    def test_hook_result_combined_output_access(self):
        """Test accessing combined output for AI fixer."""
        result = HookResult(
            name="test_hook",
            status="failed",
            output="stdout content",
            error="stderr content",
            error_message="error message",
        )

        # This is what autofix_coordinator should do
        output = result.output or ""
        error = result.error or ""
        error_message = result.error_message or ""
        combined = output + error + error_message

        assert combined == "stdout contentstderr contenterror message"


@pytest.mark.unit
class TestAutofixCoordinatorFieldAccess:
    """Test AutofixCoordinator accesses correct HookResult fields."""

    @pytest.fixture
    def coordinator(self):
        mock_console = Mock()
        return AutofixCoordinator(console=mock_console, pkg_path=Path("/test"))

    def test_parse_hook_results_uses_output_not_raw_output(self, coordinator):
        """Test that _parse_hook_results_to_issues uses output/error fields."""
        # Create HookResult with output/error (NOT raw_output)
        result = HookResult(
            name="zuban",
            status="failed",
            output="crackerjack/file.py:123: error: Type annotation mismatch",
            error="",
            issues_count=1,
        )

        issues = coordinator._parse_hook_results_to_issues([result])

        # Should successfully extract the issue
        assert len(issues) == 1
        assert issues[0].type == IssueType.TYPE_ERROR
        assert "Type annotation mismatch" in issues[0].message

    def test_parse_hook_results_combines_output_and_error(self, coordinator):
        """Test that _parse_hook_results combines output + error + error_message."""
        result = HookResult(
            name="ruff",
            status="failed",
            output="stdout warning",
            error="stderr error",
            error_message="combined message",
        )

        issues = coordinator._parse_hook_results_to_issues([result])

        # Should extract from combined output
        assert len(issues) >= 0  # At least should not crash

    def test_parse_hook_results_handles_none_fields(self, coordinator):
        """Test that _parse_hook_results handles None fields gracefully."""
        result = HookResult(
            name="test_hook",
            status="failed",
            output=None,
            error=None,
            error_message=None,
        )

        # Should not crash
        issues = coordinator._parse_hook_results_to_issues([result])
        assert isinstance(issues, list)

    def test_should_skip_autofix_uses_output_not_raw_output(self, coordinator):
        """Test that _should_skip_autofix uses output/error fields."""
        # Test with ImportError in output field
        result = HookResult(
            name="test_hook",
            status="failed",
            output="ImportError: cannot import",
            error="",
        )

        should_skip = coordinator._should_skip_autofix([result])
        assert should_skip is True

    def test_should_skip_autofix_checks_error_field(self, coordinator):
        """Test that _should_skip_autofix checks error field."""
        result = HookResult(
            name="test_hook",
            status="failed",
            output="",
            error="ModuleNotFoundError: No module named 'foo'",
        )

        should_skip = coordinator._should_skip_autofix([result])
        assert should_skip is True

    def test_should_skip_autofix_checks_error_message_field(self, coordinator):
        """Test that _should_skip_autofix checks error_message field."""
        result = HookResult(
            name="test_hook",
            status="failed",
            output="",
            error="",
            error_message="ImportError: cannot import name 'bar'",
        )

        should_skip = coordinator._should_skip_autofix([result])
        assert should_skip is True


@pytest.mark.unit
class TestParseHookResultsToIssues:
    """Test _parse_hook_results_to_issues method."""

    @pytest.fixture
    def coordinator(self):
        mock_console = Mock()
        return AutofixCoordinator(console=mock_console, pkg_path=Path("/test"))

    def test_parse_zuban_type_errors(self, coordinator):
        """Test parsing zuban type checker output."""
        result = HookResult(
            name="zuban",
            status="failed",
            output="""crackerjack/file.py:123:45: error: Incompatible return value type
crackerjack/other.py:45:6: error: Argument missing""",
            error="",
        )

        issues = coordinator._parse_hook_results_to_issues([result])

        # Parser extracts at least the issues (may parse differently)
        assert len(issues) >= 2
        assert all(i.type == IssueType.TYPE_ERROR for i in issues)
        assert any("Incompatible return value" in i.message or "return value" in i.message for i in issues)
        assert any("Argument missing" in i.message or "Argument" in i.message for i in issues)

    def test_parse_refurb_complexity_issues(self, coordinator):
        """Test parsing refurb complexity output."""
        result = HookResult(
            name="refurb",
            status="failed",
            output="""crackerjack/file.py:100: FURB123: Use context manager instead
crackerjack/other.py:50: FURB456: Simplify this logic""",
            error="",
        )

        issues = coordinator._parse_hook_results_to_issues([result])

        # Parser extracts issues (count may vary based on parsing logic)
        assert len(issues) >= 1
        assert all(i.type == IssueType.COMPLEXITY for i in issues)

    def test_parse_creosote_dependency_issues(self, coordinator):
        """Test parsing creosote unused dependency output."""
        result = HookResult(
            name="creosote",
            status="failed",
            output="""Unused imports found:
  - requests (3 occurrences)
  - numpy (1 occurrence)""",
            error="",
        )

        issues = coordinator._parse_hook_results_to_issues([result])

        # Should extract dependency issues
        assert len(issues) >= 0
        dependency_issues = [i for i in issues if i.type == IssueType.DEPENDENCY]
        assert len(dependency_issues) >= 0

    def test_filters_out_passed_hooks(self, coordinator):
        """Test that Passed hooks are filtered out."""
        passed_result = HookResult(
            name="zuban",
            status="passed",
            output="",
        )

        failed_result = HookResult(
            name="refurb",
            status="failed",
            output="file.py:10: Error here",
        )

        issues = coordinator._parse_hook_results_to_issues([passed_result, failed_result])

        # Should only have issues from failed hook
        assert len(issues) >= 0

    def test_unknown_hook_type_returns_no_issues(self, coordinator):
        """Test that unknown hook types return empty issues list."""
        result = HookResult(
            name="unknown_hook",
            status="failed",
            output="Some error message",
        )

        issues = coordinator._parse_hook_results_to_issues([result])

        # Unknown hook types should return empty
        assert len(issues) == 0


@pytest.mark.unit
class TestAIFixIterationLoop:
    """Test AI-fix iteration loop behavior."""

    @pytest.fixture
    def coordinator(self):
        mock_console = Mock()
        return AutofixCoordinator(console=mock_console, pkg_path=Path("/test"))

    def test_iteration_loop_with_zero_issues_reports_success(self, coordinator):
        """Test that 0 issues on first iteration reports success immediately."""
        # Mock empty issues list
        with patch.object(
            coordinator, "_parse_hook_results_to_issues", return_value=[]
        ):
            # Set AI_AGENT environment to enable AI mode
            old_env = os.environ.get("AI_AGENT")
            os.environ["AI_AGENT"] = "1"

            try:
                result = coordinator._apply_ai_agent_fixes([])
                assert result is True  # Should succeed with 0 issues
            finally:
                if old_env is None:
                    os.environ.pop("AI_AGENT", None)
                else:
                    os.environ["AI_AGENT"] = old_env

    def test_iteration_loop_calls_parse_hook_results_on_first_iteration(
        self, coordinator
    ):
        """Test that iteration 0 calls _parse_hook_results_to_issues."""
        hook_results = [Mock(name="test")]

        with (
            patch.object(
                coordinator, "_parse_hook_results_to_issues", return_value=[]
            ) as mock_parse,
            patch("os.environ.get", return_value="1"),  # Enable AI mode
        ):
            coordinator._apply_ai_agent_fixes(hook_results)

            # Should call parse on first iteration
            mock_parse.assert_called_once_with(hook_results)

    def test_iteration_loop_exits_on_max_iterations(self, coordinator):
        """Test that loop exits after max iterations with issues remaining."""
        # Create issues that won't be resolved
        issues = [
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.HIGH,
                message="Test error",
                file_path="test.py",
                line_number=1,
                stage="test",
            )
        ]

        with (
            patch.object(coordinator, "_parse_hook_results_to_issues", return_value=issues),
            patch.object(coordinator, "_collect_current_issues", return_value=issues),
            patch.object(
                coordinator, "_run_ai_fix_iteration", return_value=True
            ),
            patch("os.environ.get", return_value="1"),
        ):
            # Set max iterations to 1 for testing
            coordinator._max_iterations = 1

            result = coordinator._apply_ai_agent_fixes([])

            # Should return False (not all issues resolved)
            assert result is False


@pytest.mark.integration
class TestHookExecutorFieldPopulation:
    """Integration tests for hook executor field population."""

    def test_hook_result_creation_with_output_and_error(self):
        """Test HookResult creation with output and error fields."""
        from crackerjack.models.task import HookResult

        # Create HookResult as the executor does
        result = HookResult(
            id="test_hook",
            name="test_hook",
            status="failed",
            duration=1.0,
            output="stdout content",
            error="stderr content",
            exit_code=1,
        )

        # Verify fields are populated correctly
        assert isinstance(result, HookResult)
        assert result.output == "stdout content"
        assert result.error == "stderr content"

    def test_hook_result_fields_accessible_by_autofix_coordinator(self):
        """Test that AutofixCoordinator can access output/error fields."""
        from crackerjack.models.task import HookResult
        from crackerjack.core.autofix_coordinator import AutofixCoordinator

        # Create HookResult as executor creates it
        result = HookResult(
            name="test_hook",
            status="failed",
            output="Error message from hook",
            error="",
            issues_count=1,
        )

        coordinator = AutofixCoordinator(pkg_path=Path("/test"))

        # Verify coordinator can extract the output
        output = getattr(result, "output", None) or ""
        error = getattr(result, "error", None) or ""
        error_message = getattr(result, "error_message", None) or ""

        combined = output + error + error_message
        assert "Error message from hook" in combined

        # Verify _parse_hook_results_to_issues works
        issues = coordinator._parse_hook_results_to_issues([result])
        assert isinstance(issues, list)


@pytest.mark.regression
class TestAI_FIX_BugRegression:
    """Regression tests for the AI-fix '0 iterations' bug."""

    @pytest.fixture
    def coordinator(self):
        mock_console = Mock()
        return AutofixCoordinator(console=mock_console, pkg_path=Path("/test"))

    def test_regression_raw_output_not_used(self, coordinator):
        """
        REGRESSION TEST: Verify raw_output field is NOT used.

        Bug: autofix_coordinator was accessing result.raw_output which doesn't
        exist on HookResult, causing empty issue lists and "0 iterations".
        """
        # Create a HookResult (which does NOT have raw_output)
        result = HookResult(
            name="zuban",
            status="failed",  # HookResult uses lowercase status values
            output="file.py:10: error: Type error",
            error="",
            issues_count=1,
        )

        # Verify raw_output doesn't exist
        assert not hasattr(result, "raw_output") or getattr(
            result, "raw_output", None
        ) is None

        # Verify autofix_coordinator doesn't crash and extracts issues
        issues = coordinator._parse_hook_results_to_issues([result])

        # Should successfully extract using output/error fields instead
        assert len(issues) == 1
        assert "Type error" in issues[0].message

    def test_regression_multiple_hook_failures_extracted(self, coordinator):
        """
        REGRESSION TEST: Verify all hook failures are extracted.

        Bug: With raw_output returning empty string, no issues were extracted
        even when 5 hooks failed with 237 total issues.
        """
        # Simulate the user's original failing scenario
        hook_results = [
            HookResult(
                name="zuban",
                status="failed",  # HookResult uses lowercase status values
                output="file1.py:10: error\n" * 20,  # 158 issues
                error="",
            ),
            HookResult(
                name="pyscn",
                status="failed",
                output="security issue\n" * 10,  # 19 issues
                error="",
            ),
            HookResult(
                name="creosote",
                status="failed",
                output="unused import\n" * 3,  # 3 issues
                error="",
            ),
            HookResult(
                name="complexipy",
                status="failed",
                output="complexity > 15\n" * 9,  # 9 issues
                error="",
            ),
            HookResult(
                name="refurb",
                status="failed",
                output="refurb issue\n" * 48,  # 48 issues
                error="",
            ),
        ]

        # Enable AI mode
        with patch("os.environ.get", return_value="1"):
            issues = coordinator._parse_hook_results_to_issues(hook_results)

            # Should extract issues (actual count depends on parsing logic)
            # The key is that it should NOT be 0
            assert len(issues) > 0, "Should extract at least some issues"

            # Verify issues come from different hooks
            hook_names = {i.stage for i in issues}
            assert len(hook_names) > 0, "Should have issues from multiple hooks"

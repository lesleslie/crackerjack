"""Regression test for check-yaml AI-fix parsing bug.

This test ensures that check-yaml errors are correctly parsed and passed
to the AI agent system, fixing the bug where AI-fix reported "0 issues to fix"
even when check-yaml failed with multiple errors.

Bug Report Date: 2026-01-28
Related: GitHub issue discussions on AI-fix parsing bugs
"""

from unittest.mock import Mock

import pytest
from rich.console import Console

from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.agents.base import IssueType


class TestCheckYamlAIFixRegression:
    """Regression tests for check-yaml AI-fix parsing bug."""

    @pytest.fixture
    def coordinator(self) -> AutofixCoordinator:
        """Create an AutofixCoordinator instance for testing."""
        console = Console()
        return AutofixCoordinator(console=console)

    def test_regression_check_yaml_27_errors_parsed(self, coordinator) -> None:
        """Test that 27 check-yaml errors are correctly parsed.

        This was the original bug: check-yaml reported 27 errors but
        AI-fix iteration 1 showed "0 issues to fix".

        Expected behavior: All 27 errors should be parsed and counted.
        """
        # Simulate check-yaml output with 27 errors
        yaml_output = "\n".join([
            f"✗ settings/config{i}.yaml: duplicate key 'database'"
            for i in range(27)
        ])

        hook_result = Mock()
        hook_result.status = "failed"
        hook_result.name = "check-yaml"
        hook_result.output = yaml_output
        hook_result.error = "27 YAML file(s) with errors"
        hook_result.error_message = None

        # Parse the hook result
        issues = coordinator._parse_single_hook_result(hook_result)

        # CRITICAL: All 27 errors should be parsed
        assert len(issues) == 27, (
            f"Expected 27 issues to be parsed, but got {len(issues)}. "
            "This indicates the check-yaml parsing bug has regressed."
        )

        # Verify all issues have correct properties
        for i, issue in enumerate(issues):
            assert issue.file_path == f"settings/config{i}.yaml"
            assert "duplicate key" in issue.message
            assert issue.type == IssueType.FORMATTING
            assert issue.line_number is None  # File-level validation

    def test_regression_check_yaml_in_iteration_1(self, coordinator) -> None:
        """Test that check-yaml errors appear in iteration 1 of AI-fix.

        This ensures the issue count is correct when AI-fix starts,
        not zero due to parsing failure.
        """
        # Simulate actual check-yaml output from a failed run
        yaml_output = """✗ settings/crackerjack.yaml: could not determine a constructor for the tag '!!python/object/apply:os.getenv'
✗ .github/workflows/ci.yml: mapping values are not allowed here
✗ docs/config.yaml: duplicate key 'database'
✗ settings/local.yaml: unexpected character '!'
✗ tests/fixtures/test.yaml: invalid escape sequence '\\x'
"""

        hook_result = Mock()
        hook_result.status = "failed"
        hook_result.name = "check-yaml"
        hook_result.output = yaml_output
        hook_result.error = "5 YAML file(s) with errors"
        hook_result.error_message = None

        issues = coordinator._parse_hook_results_to_issues([hook_result])

        # CRITICAL: Should parse 5 errors, not 0
        assert len(issues) == 5, (
            f"Regression detected: Expected 5 issues, got {len(issues)}. "
            "AI-fix would show '0 issues to fix' in iteration 1."
        )

    def test_regression_mixed_hooks_with_check_yaml(self, coordinator) -> None:
        """Test check-yaml errors are parsed alongside other hook failures."""
        from crackerjack.agents.base import IssueType

        # Simulate multiple hook failures including check-yaml
        yaml_hook = Mock()
        yaml_hook.status = "failed"
        yaml_hook.name = "check-yaml"
        yaml_hook.output = "✗ config.yaml: error 1\n✗ settings.yaml: error 2\n"
        yaml_hook.error = "2 YAML file(s) with errors"
        yaml_hook.error_message = None

        ruff_hook = Mock()
        ruff_hook.status = "failed"
        ruff_hook.name = "ruff"
        ruff_hook.output = "file.py:1:1: F401 unused import\n"
        ruff_hook.error = ""
        ruff_hook.error_message = None

        issues = coordinator._parse_hook_results_to_issues([yaml_hook, ruff_hook])

        # Should parse both YAML and ruff errors
        assert len(issues) == 3, (
            f"Expected 3 total issues (2 YAML + 1 ruff), got {len(issues)}"
        )

        # Verify YAML errors are present
        yaml_issues = [i for i in issues if i.file_path and i.file_path.endswith('.yaml')]
        assert len(yaml_issues) == 2, "Both YAML errors should be parsed"

    def test_regression_check_yaml_deduplication(self, coordinator) -> None:
        """Test that duplicate YAML errors are deduplicated correctly."""
        yaml_hook = Mock()
        yaml_hook.status = "failed"
        yaml_hook.name = "check-yaml"
        # Same error appears twice
        yaml_hook.output = "✗ config.yaml: duplicate key 'test'\n✗ config.yaml: duplicate key 'test'\n"
        yaml_hook.error = "1 YAML file(s) with errors"
        yaml_hook.error_message = None

        issues = coordinator._parse_hook_results_to_issues([yaml_hook])

        # Should deduplicate to 1 issue
        assert len(issues) == 1, (
            f"Expected 1 issue after deduplication, got {len(issues)}"
        )
        assert issues[0].file_path == "config.yaml"

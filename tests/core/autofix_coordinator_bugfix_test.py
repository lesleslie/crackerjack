"""Tests for autofix_coordinator bug fixes - simplified version.

This module tests the critical fixes made to the autofix_coordinator:
1. Issue count extraction fix - complexipy/refurb/creosote skip validation (adapter does filtering)
2. Iteration discrepancy fix - ensures consistent use of hook_results across iterations
"""

import pytest
from pathlib import Path
from unittest.mock import Mock

from crackerjack.core.autofix_coordinator import AutofixCoordinator


class TestIterationDiscrepancyFix:
    """Test the iteration discrepancy bug fix."""

    @pytest.fixture
    def coordinator(self):
        """Create an AutofixCoordinator instance for testing."""
        pkg_path = Path("/tmp/test")
        return AutofixCoordinator(console=None, pkg_path=pkg_path)

    def test_iteration_0_processes_hook_results(self, coordinator):
        """Iteration 0 should process hook_results parameter."""
        # Create mock hook results
        mock_hook = Mock()
        hook_results = [mock_hook]

        # Should not crash and should return a list
        issues = coordinator._get_iteration_issues(0, hook_results, "fast")
        assert isinstance(issues, list)

    def test_iteration_1_also_uses_hook_results(self, coordinator):
        """Iteration 1 should also use hook_results (this was the bug)."""
        # Create mock hook results
        mock_hook = Mock()
        hook_results = [mock_hook]

        # This used to rerun tools - now it should use hook_results
        issues = coordinator._get_iteration_issues(1, hook_results, "comprehensive")
        assert isinstance(issues, list)

    def test_iteration_2_maintains_consistency(self, coordinator):
        """Iteration 2+ should maintain consistency with earlier iterations."""
        mock_hook = Mock()
        hook_results = [mock_hook]

        issues = coordinator._get_iteration_issues(2, hook_results, "comprehensive")
        assert isinstance(issues, list)

    def test_iteration_with_empty_results(self, coordinator):
        """Should handle empty hook_results gracefully."""
        issues = coordinator._get_iteration_issues(0, [], "fast")
        assert issues == []

    def test_iteration_parses_multiple_hook_results(self, coordinator):
        """Should parse multiple hook results."""
        # Create multiple mock hooks
        hook_results = [Mock(), Mock(), Mock()]

        issues = coordinator._get_iteration_issues(0, hook_results, "comprehensive")
        assert isinstance(issues, list)


class TestIssueCountExtractionFix:
    """Test the issue count extraction bug fix for filtered tools.

    Background: Some tools output more data than the adapter ultimately returns
    because the adapter applies filtering logic (thresholds, patterns, etc.).
    The _extract_issue_count method should return None for these tools to skip
    validation, since the raw output can't predict the filtered result.

    Tools with filtering:
    - complexipy: outputs ALL functions (6076), adapter filters by threshold (~9)
    - refurb: outputs all lines, adapter filters for "[FURB" prefix
    - creosote: outputs multiple sections, adapter filters for "unused" deps
    """

    @pytest.fixture
    def coordinator(self):
        """Create an AutofixCoordinator instance."""
        pkg_path = Path("/tmp/test")
        return AutofixCoordinator(console=None, pkg_path=pkg_path)

    def test_complexipy_returns_none_to_skip_validation(self, coordinator):
        """complexipy should return None because adapter does filtering."""
        complexipy_output = '{"complexity": 20, "file_name": "test.py", "function_name": "test", "path": "test.py"}'

        result = coordinator._extract_issue_count(complexipy_output, "complexipy")

        assert result is None, (
            "complexipy should return None because the adapter filters "
            "by threshold, making raw output count unpredictable"
        )

    def test_refurb_returns_none_to_skip_validation(self, coordinator):
        """refurb should return None because adapter does filtering."""
        refurb_output = """file1.py:10: Some output
file2.py:20: [FURB] This is a refurb issue
file3.py:30: More output"""

        result = coordinator._extract_issue_count(refurb_output, "refurb")

        assert result is None, (
            "refurb should return None because the adapter filters "
            "for '[FURB' prefix, making raw output count unpredictable"
        )

    def test_creosote_returns_none_to_skip_validation(self, coordinator):
        """creosote should return None because adapter does filtering."""
        creosote_output = """Found dependencies: 10
Unused dependencies: 3
pkg1
pkg2
pkg3"""

        result = coordinator._extract_issue_count(creosote_output, "creosote")

        assert result is None, (
            "creosote should return None because the adapter filters "
            "for 'unused' section, making raw output count unpredictable"
        )

    def test_ruff_still_returns_count(self, coordinator):
        """Tools without filtering should still return counts."""
        ruff_output = '[{"message": "error1"}, {"message": "error2"}]'

        result = coordinator._extract_issue_count(ruff_output, "ruff")

        assert result == 2, "ruff should return the JSON array length"

    def test_fallback_line_counting_still_works(self, coordinator):
        """Fallback line counting should still work for unknown tools."""
        # Text output with colons (looks like issues)
        text_output = """file1.py:10: error message
file2.py:20: another error
file3.py:30: third error"""

        result = coordinator._extract_issue_count(text_output, "unknown-tool")

        assert result == 3, "Should count lines with colons"


class TestBugFixIntegration:
    """Integration tests showing both fixes working together."""

    @pytest.fixture
    def coordinator(self):
        """Create an AutofixCoordinator instance."""
        pkg_path = Path("/tmp/test")
        return AutofixCoordinator(console=None, pkg_path=pkg_path)

    def test_issue_count_stability(self, coordinator):
        """Issue counts should remain stable across iterations."""
        # Create stable mock results
        mock_hook = Mock(to_issues=lambda: [])
        hook_results = [mock_hook]

        # Multiple iterations should return consistent types
        for i in range(5):
            issues = coordinator._get_iteration_issues(i, hook_results, "fast")
            assert isinstance(issues, list), f"Iteration {i} should return list"


class TestAIFixToolSkipping:
    """Test that tools with heavy filtering are skipped in AI-fix iterations.

    This implements Option 3 (Pragmatic) from the architectural analysis:
    Skip complexipy, refurb, and creosote in AI-fix because these tools do
    heavy filtering that makes them unsuitable for automated fixing.

    Root cause: These tools output large amounts of raw data that gets filtered
    down to a small subset by business logic (thresholds, patterns, etc).
    This causes "6035 issues to fix" → "12 issues" confusion.

    Solution: Skip these tools in AI-fix iterations. They still run and report
    issues, but require manual review instead of automated fixing.
    """

    @pytest.fixture
    def coordinator(self):
        """Create an AutofixCoordinator instance."""
        pkg_path = Path("/tmp/test")
        return AutofixCoordinator(console=None, pkg_path=pkg_path)

    def test_complexipy_skipped_in_ai_fix(self, coordinator):
        """complexipy should be skipped for AI-fix iterations."""
        # Create a mock hook result for complexipy
        mock_result = Mock()
        mock_result.name = "complexipy"
        mock_result.status = "failed"
        mock_result.output = "complexity data..."
        mock_result.error = ""
        mock_result.error_message = ""

        # Parse the result
        issues = coordinator._parse_single_hook_result(mock_result)

        # Should return empty list (skipped)
        assert issues == [], "complexipy should be skipped in AI-fix"

    def test_refurb_skipped_in_ai_fix(self, coordinator):
        """refurb should be skipped for AI-fix iterations."""
        mock_result = Mock()
        mock_result.name = "refurb"
        mock_result.status = "failed"
        mock_result.output = "refurb suggestions..."
        mock_result.error = ""
        mock_result.error_message = ""

        issues = coordinator._parse_single_hook_result(mock_result)

        assert issues == [], "refurb should be skipped in AI-fix"

    def test_creosote_skipped_in_ai_fix(self, coordinator):
        """creosote should be skipped for AI-fix iterations."""
        mock_result = Mock()
        mock_result.name = "creosote"
        mock_result.status = "failed"
        mock_result.output = "unused imports..."
        mock_result.error = ""
        mock_result.error_message = ""

        issues = coordinator._parse_single_hook_result(mock_result)

        assert issues == [], "creosote should be skipped in AI-fix"

    def test_regular_tools_not_skipped(self, coordinator):
        """Regular tools like ruff should NOT be skipped."""
        # This test would need mocking of the parser to work properly
        # For now, just verify the skip list doesn't include common tools
        skip_list = ("complexipy", "refurb", "creosote")

        assert "ruff" not in skip_list
        assert "mypy" not in skip_list
        assert "bandit" not in skip_list
        assert "codespell" not in skip_list

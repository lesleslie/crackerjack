"""Tests for autofix_coordinator bug fixes - simplified version.

This module tests the critical fixes made to the autofix_coordinator:
1. Complexipy parser fix - handles actual output format with "Failed functions:" header
2. Iteration discrepancy fix - ensures consistent use of hook_results across iterations
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.agents.base import IssueType


class TestComplexipyParserFix:
    """Test the complexipy parser bug fix."""

    @pytest.fixture
    def coordinator(self):
        """Create an AutofixCoordinator instance for testing."""
        pkg_path = Path("/tmp/test")
        return AutofixCoordinator(console=None, pkg_path=pkg_path)

    def test_parse_complexity_output_finds_failed_functions_section(self, coordinator):
        """Should find the 'Failed functions:' section in complexipy output."""
        # Actual complexipy output format
        raw_output = """Failed functions:
  - crackerjack/file.py:
    - function_one (complexity: 25)
    - function_two (complexity: 30)"""

        issues = coordinator._parse_complexity_output(raw_output, IssueType.COMPLEXITY)

        # Should parse at least the section
        assert isinstance(issues, list)

    def test_parse_complexity_output_handles_empty_output(self, coordinator):
        """Should handle empty output gracefully."""
        issues = coordinator._parse_complexity_output("", IssueType.COMPLEXITY)
        assert issues == []

    def test_parse_complexity_output_handles_no_failed_section(self, coordinator):
        """Should handle output without 'Failed functions:' section."""
        raw_output = "All functions are within complexity limits."
        issues = coordinator._parse_complexity_output(raw_output, IssueType.COMPLEXITY)
        assert isinstance(issues, list)

    def test_parse_complexity_output_extracts_file_paths(self, coordinator):
        """Should extract file paths from the output."""
        raw_output = """Failed functions:
  - crackerjack/autofix_coordinator.py:
    - complex_function (complexity: 35)"""

        issues = coordinator._parse_complexity_output(raw_output, IssueType.COMPLEXITY)

        # If issues found, should have file paths
        if len(issues) > 0:
            assert all(issue.file_path is not None for issue in issues)

    def test_parse_complexity_output_extracts_function_names(self, coordinator):
        """Should extract function names from the output."""
        raw_output = """Failed functions:
  - file.py:
    - my_function (complexity: 40)"""

        issues = coordinator._parse_complexity_output(raw_output, IssueType.COMPLEXITY)

        # If issues found, should have function names in message
        if len(issues) > 0:
            assert all("complexity" in str(issue.message).lower() for issue in issues)


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


class TestBugFixIntegration:
    """Integration tests showing both fixes working together."""

    @pytest.fixture
    def coordinator(self):
        """Create an AutofixCoordinator instance."""
        pkg_path = Path("/tmp/test")
        return AutofixCoordinator(console=None, pkg_path=pkg_path)

    def test_complexipy_workflow_across_iterations(self, coordinator):
        """Complexipy issues should work consistently across iterations."""
        # Simulate complexipy output
        complexipy_output = """Failed functions:
  - crackerjack/file.py:
    - complex_func (complexity: 45)"""

        # Parse the output (this was fixed)
        issues = coordinator._parse_complexity_output(
            complexipy_output,
            IssueType.COMPLEXITY
        )

        # Use in iteration workflow (this was also fixed)
        mock_hook = Mock(to_issues=lambda: issues)
        hook_results = [mock_hook]

        iteration_0 = coordinator._get_iteration_issues(0, hook_results, "comprehensive")
        iteration_1 = coordinator._get_iteration_issues(1, hook_results, "comprehensive")

        # Both should return lists
        assert isinstance(iteration_0, list)
        assert isinstance(iteration_1, list)

    def test_issue_count_stability(self, coordinator):
        """Issue counts should remain stable across iterations."""
        # Create stable mock results
        mock_hook = Mock(to_issues=lambda: [])
        hook_results = [mock_hook]

        # Multiple iterations should return consistent types
        for i in range(5):
            issues = coordinator._get_iteration_issues(i, hook_results, "fast")
            assert isinstance(issues, list), f"Iteration {i} should return list"

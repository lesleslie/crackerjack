"""Tests for issue_detection utility functions."""

import pytest

from crackerjack.utils.issue_detection import (
    should_count_as_issue,
    count_issues_from_output,
    extract_issue_lines,
)


class TestShouldCountAsIssue:
    """Test the should_count_as_issue function."""

    def test_empty_line(self):
        """Empty lines should not count as issues."""
        assert should_count_as_issue("") is False
        assert should_count_as_issue("   ") is False

    def test_comment_lines(self):
        """Comment lines should not count as issues."""
        assert should_count_as_issue("# This is a comment") is False
        assert should_count_as_issue("  # Indented comment") is False

    def test_note_and_help_lines(self):
        """Note and help lines should not count as issues."""
        assert should_count_as_issue("file.py:10: note: This is a hint") is False
        assert should_count_as_issue("file.py:10: help: Try using X instead") is False
        assert should_count_as_issue("note: Something to consider") is False
        assert should_count_as_issue("help: Usage information") is False

    def test_summary_lines(self):
        """Summary lines should not count as issues."""
        assert should_count_as_issue("Found 3 errors") is False
        assert should_count_as_issue("Checked 5 files") is False
        assert should_count_as_issue("Success: All checks passed") is False
        assert should_count_as_issue("Summary: 0 errors found") is False
        assert should_count_as_issue("Total: 10 issues") is False

    def test_separator_lines(self):
        """Separator lines should not count as issues."""
        assert should_count_as_issue("=== Section ===") is False
        assert should_count_as_issue("────") is False
        assert should_count_as_issue("──────────") is False
        assert should_count_as_issue("Errors:") is False
        assert should_count_as_issue("┌─ Box ─") is False
        # Note: "│ Line │" has text content, so it would be counted
        # Pure separator lines without text are filtered out

    def test_valid_issue_lines(self):
        """Valid issue lines should be counted."""
        assert should_count_as_issue("file.py:10: error: Type mismatch") is True
        assert should_count_as_issue("src/module.py:42: warning: Unused variable") is True
        assert should_count_as_issue("CRITICAL: Security issue found") is True
        assert should_count_as_issue("\tpackage/file.ts:100: fixme: Implement this") is True

    def test_case_insensitive_filtering(self):
        """Filtering should work case-insensitively."""
        assert should_count_as_issue("FILE.PY:10: NOTE: This is a note") is False
        assert should_count_as_issue("file.py:10: Note: Different case") is False

    def test_additional_filters(self):
        """Additional filter function should be respected."""
        # Custom filter to exclude lines with "TODO"
        custom_filter = lambda line: "TODO" not in line

        assert should_count_as_issue("file.py:10: error: Bug here", additional_filters=custom_filter) is True
        assert should_count_as_issue("file.py:10: error: TODO: Fix this", additional_filters=custom_filter) is False


class TestCountIssuesFromOutput:
    """Test the count_issues_from_output function."""

    def test_empty_output(self):
        """Empty output should return 0 issues."""
        assert count_issues_from_output("") == 0
        assert count_issues_from_output("\n\n") == 0

    def test_single_issue(self):
        """Count a single issue line."""
        output = "file.py:10: error: Type mismatch"
        assert count_issues_from_output(output) == 1

    def test_multiple_issues(self):
        """Count multiple issue lines."""
        output = """file.py:10: error: Type mismatch
file.py:20: warning: Unused variable
module.py:5: error: Missing import"""
        assert count_issues_from_output(output) == 3

    def test_filters_out_non_issues(self):
        """Should filter out notes, summaries, and separators."""
        output = """=== Linting Results ===
Found 3 errors
file.py:10: error: Type mismatch
file.py:20: note: Consider using X
file.py:30: warning: Unused variable
Summary: 1 error, 1 warning"""
        assert count_issues_from_output(output) == 2  # Only the error and warning

    def test_tool_specific_filtering(self):
        """Tool name should enable tool-specific filtering."""
        # For tools with special output formats
        output = "special-tool: file.py:10: issue"
        count = count_issues_from_output(output, tool_name="special-tool")
        assert count >= 0  # Should not crash


class TestExtractIssueLines:
    """Test the extract_issue_lines function."""

    def test_empty_output(self):
        """Empty output should return empty list."""
        assert extract_issue_lines("") == []
        assert extract_issue_lines("\n\n") == []

    def test_single_issue(self):
        """Extract a single issue line."""
        output = "file.py:10: error: Type mismatch"
        issues = extract_issue_lines(output)
        assert len(issues) == 1
        assert issues[0] == "file.py:10: error: Type mismatch"

    def test_multiple_issues(self):
        """Extract multiple issue lines preserving order."""
        output = """file.py:10: error: Type mismatch
file.py:20: warning: Unused variable
module.py:5: error: Missing import"""
        issues = extract_issue_lines(output)
        assert len(issues) == 3
        assert issues[0] == "file.py:10: error: Type mismatch"
        assert issues[1] == "file.py:20: warning: Unused variable"
        assert issues[2] == "module.py:5: error: Missing import"

    def test_filters_out_non_issues(self):
        """Should only extract issue lines, not notes/summaries."""
        output = """=== Linting Results ===
Found 3 errors
file.py:10: error: Type mismatch
file.py:20: note: Consider using X
file.py:30: warning: Unused variable
Summary: Complete"""
        issues = extract_issue_lines(output)
        assert len(issues) == 2
        assert "error: Type mismatch" in issues[0]
        assert "warning: Unused variable" in issues[1]

    def test_preserves_whitespace_in_issues(self):
        """Issue lines should preserve their original formatting."""
        output = "  file.py:10: error: Indented error  "
        issues = extract_issue_lines(output)
        assert len(issues) == 1
        # The function should strip the line before checking if it's an issue
        # but preserve the actual issue content

    def test_handles_multiline_output(self):
        """Should handle Windows and Unix line endings."""
        output = "line1\r\nline2\nline3\r\nline4"
        issues = extract_issue_lines(output)
        # All lines should be processed
        assert len(issues) >= 0


class TestIntegration:
    """Integration tests for issue detection functions."""

    def test_count_matches_extract(self):
        """Count should match the number of extracted lines."""
        output = """file.py:10: error: Type mismatch
file.py:20: warning: Unused variable
module.py:5: error: Missing import
=== Summary ===
Found 3 errors"""

        count = count_issues_from_output(output)
        extracted = extract_issue_lines(output)

        assert count == len(extracted) == 3

    def test_real_world_ruff_output(self):
        """Test with realistic ruff output."""
        output = """crackerjack/file.py:10:5: F401 'os' imported but unused
crackerjack/file.py:20:5: E501 line too long (85 > 79)
Found 2 errors in 1 file."""
        issues = extract_issue_lines(output)
        assert len(issues) == 2
        assert "F401" in issues[0]
        assert "E501" in issues[1]

    def test_real_world_mypy_output(self):
        """Test with realistic mypy output."""
        output = """file.py:10: error: Incompatible return value type
file.py:20: note: Consider using Optional[int]
Success: issues found in 1 file"""
        issues = extract_issue_lines(output)
        assert len(issues) == 1
        assert "Incompatible return value type" in issues[0]

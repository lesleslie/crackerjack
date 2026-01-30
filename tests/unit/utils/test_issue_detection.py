"""Tests for issue detection utility.

This test suite verifies that the shared issue detection logic works correctly
and is used consistently by both the hook execution layer and the AI fixing layer.
"""

import pytest

from crackerjack.utils.issue_detection import (
    count_issues_from_output,
    extract_issue_lines,
    should_count_as_issue,
)


class TestShouldCountAsIssue:
    """Test the should_count_as_issue function."""

    def test_counts_error_lines(self):
        """Error lines should be counted as issues."""
        assert should_count_as_issue("file.py:10: error: Type mismatch")
        assert should_count_as_issue("file.py:20: error: Undefined variable")
        assert should_count_as_issue("module.py:5: TypeError: Invalid argument")

    def test_filters_note_lines(self):
        """Note lines should not be counted as issues."""
        assert not should_count_as_issue("file.py:10: note: This is a hint")
        assert not should_count_as_issue("file.py:20: note: Consider using X instead")
        assert not should_count_as_issue("module.py:5: note: Optional suggestion")

    def test_filters_help_lines(self):
        """Help lines should not be counted as issues."""
        assert not should_count_as_issue("file.py:10: help: Try using method Y")
        assert not should_count_as_issue("file.py:20: help: See documentation")

    def test_filters_summary_lines(self):
        """Summary lines should not be counted as issues."""
        assert not should_count_as_issue("Found 3 errors")
        assert not should_count_as_issue("Checked 150 files")
        assert not should_count_as_issue("N errors found in 5 files")
        assert not should_count_as_issue("Success: no issues found")
        assert not should_count_as_issue("errors in 2 modules")

    def test_filters_separator_lines(self):
        """Separator lines should not be counted as issues."""
        assert not should_count_as_issue("===")
        assert not should_count_as_issue("---")
        assert not should_count_as_issue("Errors: 3")
        assert not should_count_as_issue("┌─────────┐")
        assert not should_count_as_issue("└─────────┘")
        assert not should_count_as_issue("├─────────┤")
        assert not should_count_as_issue("┃         ┃")

    def test_filters_header_lines(self):
        """Table header lines should not be counted as issues."""
        assert not should_count_as_issue("Path | Function | Complexity")
        assert not should_count_as_issue("─────┼──────────┼────────────")
        assert not should_count_as_issue("File | Line | Issue")
        assert not should_count_as_issue("Function | Complexity")

    def test_filters_empty_lines(self):
        """Empty lines should not be counted as issues."""
        assert not should_count_as_issue("")
        assert not should_count_as_issue("   ")
        assert not should_count_as_issue("\t")

    def test_counts_valid_variations(self):
        """Valid error lines with various formats should be counted."""
        assert should_count_as_issue("file.py:10:5: E001 error message")
        assert should_count_as_issue("src/module.py:20: warning: Deprecation")
        assert should_count_as_issue("FURB123: Refactor this code")
        assert should_count_as_issue("C901: Function is too complex")


class TestCountIssuesFromOutput:
    """Test the count_issues_from_output function."""

    def test_counts_all_issues(self):
        """Should count all issue lines, filtering out non-issues."""
        output = """
file.py:10: error: Type mismatch
file.py:20: note: This is a hint
file.py:30: error: Undefined variable
Found 2 errors
"""
        count = count_issues_from_output(output)
        assert count == 2  # Only the two error lines, not note or summary

    def test_returns_zero_for_empty_output(self):
        """Empty output should return zero count."""
        assert count_issues_from_output("") == 0
        assert count_issues_from_output("   ") == 0

    def test_returns_zero_for_output_with_only_summaries(self):
        """Output with only summary lines should return zero."""
        output = """
Found 5 errors
Checked 100 files
Success: 3 issues fixed
"""
        assert count_issues_from_output(output) == 0

    def test_filters_mypy_style_output(self):
        """Should correctly count mypy-style type errors."""
        output = """
module.py:10: error: Incompatible return value type
module.py:15: note: Consider returning Optional[str]
module.py:20: error: Argument 1 has incompatible type
Found 2 errors in 1 file
"""
        count = count_issues_from_output(output, tool_name="mypy")
        assert count == 2  # Two error lines, note and summary filtered

    def test_filters_zuban_style_output(self):
        """Should correctly count zuban-style type errors."""
        output = """
src/file.py:25: error: Type annotation mismatch for 'x'
src/file.py:30: note: Expected 'int' but got 'str'
src/file.py:35: error: Missing type annotation
=== Errors found: 2 ===
"""
        count = count_issues_from_output(output, tool_name="zuban")
        assert count == 2  # Two error lines, note and separator filtered


class TestExtractIssueLines:
    """Test the extract_issue_lines function."""

    def test_extracts_only_issue_lines(self):
        """Should return only issue lines, stripped."""
        output = """
  file.py:10: error: Type mismatch
file.py:20: note: This is a hint
  file.py:30: error: Undefined variable
Found 2 errors
"""
        issues = extract_issue_lines(output)
        assert len(issues) == 2
        assert issues == [
            "file.py:10: error: Type mismatch",
            "file.py:30: error: Undefined variable",
        ]

    def test_returns_empty_list_for_empty_output(self):
        """Empty output should return empty list."""
        assert extract_issue_lines("") == []
        assert extract_issue_lines("   ") == []

    def test_preserves_order_of_issues(self):
        """Should preserve the order of issue lines."""
        output = """
file.py:10: error: First error
file.py:20: error: Second error
file.py:30: error: Third error
"""
        issues = extract_issue_lines(output)
        assert len(issues) == 3
        assert "First" in issues[0]
        assert "Second" in issues[1]
        assert "Third" in issues[2]

    def test_filters_complex_output(self):
        """Should handle complex realistic output."""
        output = """
=== Type Checking Report ===
Checked 15 files in 2.3s

src/module.py:10: error: Type mismatch
src/module.py:15: note: Expected 'int'
src/module.py:20: error: Missing annotation
src/utils.py:5: error: Undefined name

─────────────────
Summary: 3 errors found
"""
        issues = extract_issue_lines(output, tool_name="zuban")
        assert len(issues) == 3
        assert all("error:" in issue for issue in issues)
        assert not any("note:" in issue for issue in issues)


class TestIntegrationWithHookExecution:
    """Integration tests verifying consistency with hook execution layer."""

    def test_hook_count_matches_ai_count(self):
        """Verify that hook execution counting matches AI fixing counting.

        This is the core test for the bug fix: both layers should count
        the same number of issues from the same output.
        """
        # Simulated zuban output with 10 lines where 1 is a note
        output = """
src/file1.py:10: error: Type mismatch for 'x'
src/file1.py:20: error: Missing type annotation
src/file2.py:15: error: Incompatible return type
src/file2.py:25: error: Argument type mismatch
src/file3.py:5: error: Undefined variable 'y'
src/file3.py:30: note: Consider using Optional[str] instead
src/file4.py:12: error: Invalid type hint
src/file4.py:22: error: Type annotation missing
src/file5.py:8: error: Cannot assign to type
src/file5.py:18: error: Type checker found issue
"""

        # Both methods should return 9 (10 - 1 note)
        issue_lines = extract_issue_lines(output, tool_name="zuban")
        count = count_issues_from_output(output, tool_name="zuban")

        assert count == 9, f"Expected 9 issues, got {count}"
        assert len(issue_lines) == 9, f"Expected 9 issue lines, got {len(issue_lines)}"
        assert count == len(issue_lines), "Count should match number of extracted lines"

        # Verify the note line was filtered out
        assert not any("note:" in line for line in issue_lines)

    def test_no_false_positives_from_summaries(self):
        """Ensure summary lines don't get counted as issues."""
        output = """
file.py:10: error: Actual error
Found 1 error in 1 file
Checked 150 files
"""
        count = count_issues_from_output(output)
        assert count == 1, "Only the actual error should be counted"

    def test_multiple_tools_output(self):
        """Test handling of combined output from multiple tools."""
        output = """
# mypy output
module.py:10: error: Type mismatch
module.py:20: note: Hint here

# ruff output
file.py:5: E001 Line too long
file.py:15: W503 Line break before binary operator

# Summary
Total: 2 errors
"""
        issues = extract_issue_lines(output)
        # Should get: 1 mypy error + 2 ruff errors = 3 total
        # (the mypy note is filtered)
        assert len(issues) == 3

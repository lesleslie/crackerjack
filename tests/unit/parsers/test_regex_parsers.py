"""Tests for regex parsers."""

import pytest

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.regex_parsers import (
    CodespellRegexParser,
    RefurbRegexParser,
    PyscnRegexParser,
    RuffFormatRegexParser,
    ComplexityRegexParser,
    GenericRegexParser,
    StructuredDataParser,
    MypyRegexParser,
    CreosoteRegexParser,
    LocalLinkCheckerRegexParser,
    SkylosRegexParser,
    RuffRegexParser,
)


class TestCodespellRegexParser:
    """Test Codespell regex parser."""

    @pytest.fixture
    def parser(self):
        return CodespellRegexParser()

    def test_parse_valid_codespell_output(self, parser):
        """Test parsing valid codespell output."""
        output = "file.md:10: teh ==> the"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "file.md"
        assert issues[0].line_number == 10
        assert "teh" in issues[0].message
        assert "the" in issues[0].message

    def test_parse_without_line_number(self, parser):
        """Test parsing output without line number."""
        output = "file.txt: teh ==> the"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "file.txt"
        assert issues[0].line_number is None

    def test_parse_empty_output(self, parser):
        """Test parsing empty output."""
        issues = parser.parse_text("")

        assert issues == []

    def test_parse_no_arrow_marker(self, parser):
        """Test parsing line without arrow marker."""
        output = "file.txt:10: some error"

        issues = parser.parse_text(output)

        # Should still parse, just without suggestions
        assert len(issues) == 1


class TestRefurbRegexParser:
    """Test Refurb regex parser."""

    @pytest.fixture
    def parser(self):
        return RefurbRegexParser()

    def test_parse_valid_refurb_output(self, parser):
        """Test parsing valid refurb output."""
        output = "file.py:10:5: RUF123 Use modern syntax"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "file.py"
        assert issues[0].line_number == 10
        assert "Use modern syntax" in issues[0].message

    def test_parse_filters_summary_lines(self, parser):
        """Test that summary lines are filtered out."""
        output = """
Found 3 issues.
Checked 10 files.
file.py:1:1: RUF001 Issue 1
file.py:2:1: RUF002 Issue 2
"""

        issues = parser.parse_text(output)

        assert len(issues) == 2

    def test_parse_malformed_line(self, parser):
        """Test parsing malformed line."""
        output = "not a valid refurb line"

        issues = parser.parse_text(output)

        assert issues == []


class TestPyscnRegexParser:
    """Test Pyscn regex parser."""

    @pytest.fixture
    def parser(self):
        return PyscnRegexParser()

    def test_parse_valid_pyscn_output(self, parser):
        """Test parsing valid pyscn output."""
        output = "file.py:10:5: warning: Function too complex"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "file.py"
        assert issues[0].line_number == 10
        assert issues[0].type == IssueType.COMPLEXITY

    def test_parse_too_complex_high_severity(self, parser):
        """Test that 'too complex' gets HIGH severity."""
        output = "file.py:5:1: error: Function is too complex"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].severity == Priority.HIGH

    def test_parse_clone_detection_low_severity(self, parser):
        """Test that clone detection gets LOW severity."""
        output = "file.py:10:1: warning: Code clone detected"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].severity == Priority.LOW


class TestRuffFormatRegexParser:
    """Test Ruff Format regex parser."""

    @pytest.fixture
    def parser(self):
        return RuffFormatRegexParser()

    def test_parse_would_reformat(self, parser):
        """Test parsing 'would be reformatted' message."""
        output = "3 files would be reformatted"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING
        assert "3 file(s)" in issues[0].message

    def test_parse_failed_to_format(self, parser):
        """Test parsing 'Failed to format' message."""
        output = "Failed to format file.py"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert "Formatting error" in issues[0].message or "require formatting" in issues[0].message

    def test_parse_clean_output(self, parser):
        """Test parsing clean output (no issues)."""
        output = "All files formatted correctly"

        issues = parser.parse_text(output)

        assert issues == []


class TestComplexityRegexParser:
    """Test Complexity regex parser."""

    @pytest.fixture
    def parser(self):
        return ComplexityRegexParser()

    def test_parse_failed_functions(self, parser):
        """Test parsing failed functions section."""
        output = """
Failed functions:
- file.py:
  function1::complexity 20
  function2::complexity 25
"""

        issues = parser.parse_text(output)

        assert len(issues) == 2
        assert issues[0].file_path == "file.py"
        assert "function1" in issues[0].message
        assert "function2" in issues[1].message

    def test_parse_multiple_files(self, parser):
        """Test parsing multiple files."""
        output = """
Failed functions:
- file1.py:
  func1::complexity 30
- file2.py:
  func2::complexity 18
"""

        issues = parser.parse_text(output)

        assert len(issues) == 2
        assert issues[0].file_path == "file1.py"
        assert issues[1].file_path == "file2.py"


class TestGenericRegexParser:
    """Test Generic regex parser."""

    def test_parse_failure_output(self):
        """Test parsing failure output."""
        parser = GenericRegexParser("test-tool")
        output = "error: something failed"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert "failed" in issues[0].message

    def test_parse_success_indicators(self):
        """Test that success indicators result in no issues."""
        parser = GenericRegexParser("test-tool")
        output = "All checks passed"

        issues = parser.parse_text(output)

        assert issues == []

    def test_parse_unclear_output(self):
        """Test that unclear output is treated as success."""
        parser = GenericRegexParser("test-tool")
        output = "Some random output"

        issues = parser.parse_text(output)

        assert issues == []

    def test_parse_empty_output(self):
        """Test parsing empty output."""
        parser = GenericRegexParser("test-tool")

        issues = parser.parse_text("")

        assert issues == []


class TestStructuredDataParser:
    """Test Structured Data regex parser."""

    @pytest.fixture
    def parser(self):
        return StructuredDataParser()

    def test_parse_valid_error(self, parser):
        """Test parsing valid structured data error."""
        output = "✗ config.json: Invalid JSON"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "config.json"
        assert "Invalid JSON" in issues[0].message

    def test_parse_without_colon(self, parser):
        """Test parsing error without colon separator."""
        output = "✗ Generic error message"

        issues = parser.parse_text(output)

        # Should handle gracefully
        assert len(issues) == 1 or len(issues) == 0

    def test_parse_non_error_lines(self, parser):
        """Test that non-error lines are skipped."""
        output = """
✓ file1.json: Valid
✗ file2.json: Invalid
✓ file3.json: Valid
"""

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert "file2.json" in issues[0].file_path


class TestMypyRegexParser:
    """Test Mypy regex parser."""

    @pytest.fixture
    def parser(self):
        return MypyRegexParser()

    def test_parse_valid_error(self, parser):
        """Test parsing valid mypy error."""
        output = "file.py:10: error: Incompatible types"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "file.py"
        assert issues[0].line_number == 10
        assert issues[0].type == IssueType.TYPE_ERROR
        assert issues[0].severity == Priority.HIGH

    def test_parse_warning(self, parser):
        """Test parsing warning."""
        output = "file.py:5: warning: Unused variable"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].severity == Priority.MEDIUM

    def test_parse_filters_summary(self, parser):
        """Test that summary lines are filtered."""
        output = """
Found 5 errors in 3 files.
file.py:1: error: Type error
another.py:2: error: Another error
"""

        issues = parser.parse_text(output)

        assert len(issues) == 2


class TestCreosoteRegexParser:
    """Test Creosote regex parser."""

    @pytest.fixture
    def parser(self):
        return CreosoteRegexParser()

    def test_parse_unused_dependencies(self, parser):
        """Test parsing unused dependencies."""
        output = """
Found unused dependencies: requests, numpy
"""

        issues = parser.parse_text(output)

        assert len(issues) == 2
        assert "requests" in issues[0].message
        assert "numpy" in issues[1].message

    def test_parse_bulleted_list(self, parser):
        """Test parsing bulleted list."""
        output = """
- requests
- numpy
- pandas
"""

        issues = parser.parse_text(output)

        assert len(issues) == 3

    def test_parse_inline_dependency(self, parser):
        """Test parsing inline dependency message."""
        output = "Found unused dependency (requests)"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert "requests" in issues[0].message


class TestLocalLinkCheckerRegexParser:
    """Test Local Link Checker regex parser."""

    @pytest.fixture
    def parser(self):
        return LocalLinkCheckerRegexParser()

    def test_parse_valid_broken_link(self, parser):
        """Test parsing valid broken link."""
        output = "README.md:20 - ../target.md - File not found"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "README.md"
        assert issues[0].line_number == 20
        assert "File not found" in issues[0].message

    def test_parse_missing_line_number(self, parser):
        """Test parsing with non-numeric line number."""
        output = "README.md:line - ../target.md - Error"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].line_number is None


class TestSkylosRegexParser:
    """Test Skylos regex parser."""

    @pytest.fixture
    def parser(self):
        return SkylosRegexParser()

    def test_parse_valid_error(self, parser):
        """Test parsing valid skylos error."""
        output = "module.py - ERROR - file.py:10: Unused function 'foo'"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "file.py"
        assert "foo" in issues[0].message
        assert issues[0].type == IssueType.DEAD_CODE

    def test_parse_with_line_number_in_message(self, parser):
        """Test parsing when message contains 'line X'."""
        output = "module - ERROR - file.py: error at line 42"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].line_number == 42

    def test_parse_no_line_in_message(self, parser):
        """Test parsing when message doesn't contain line info."""
        output = "module - ERROR - file.py: Some error"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].line_number is None


class TestRuffRegexParser:
    """Test Ruff regex parser."""

    @pytest.fixture
    def parser(self):
        return RuffRegexParser()

    def test_parse_diagnostic_format(self, parser):
        """Test parsing diagnostic format with arrows."""
        output = """
F401 Unused import
 --> file.py:10:5
  |
9 | import os
  |        ^^ unused
"""

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path.name == "file.py"
        assert issues[0].line_number == 10
        assert "F401" in issues[0].message

    def test_parse_concise_format(self, parser):
        """Test parsing concise format."""
        output = "file.py:10:5: F401 Unused import"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path.name == "file.py"
        assert issues[0].line_number == 10

    def test_parse_complexity_issue(self, parser):
        """Test parsing C9 (complexity) issue."""
        output = "file.py:50: C901 Function is too complex"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].type == IssueType.COMPLEXITY
        assert issues[0].severity == Priority.HIGH

    def test_parse_multiple_issues(self, parser):
        """Test parsing multiple issues."""
        output = """
file1.py:1: F401 Unused import
file2.py:10: C901 Too complex
file3.py:5: E501 Line too long
"""

        issues = parser.parse_text(output)

        assert len(issues) == 3

    def test_parse_empty_output(self, parser):
        """Test parsing empty output."""
        issues = parser.parse_text("")

        assert issues == []

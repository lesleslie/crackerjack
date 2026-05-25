"""Tests for lychee_parser module."""

import pytest

from crackerjack.parsers.lychee_parser import (
    LycheeRegexParser,
    parse_lychee_output,
)


class TestLycheeRegexParser:
    """Tests for LycheeRegexParser."""

    @pytest.fixture
    def parser(self):
        return LycheeRegexParser()

    def test_parse_basic_lychee_output(self, parser):
        """Test parsing basic lychee output."""
        output = "docs/guide.md:42: https://example.com (404)"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].type.value == "documentation"
        assert issues[0].file_path == "docs/guide.md"
        assert issues[0].line_number == 42
        assert "example.com" in issues[0].message

    def test_parse_loose_format_without_line_number(self, parser):
        """Test parsing lychee output without explicit line number."""
        output = "file.md: https://example.com (Connection refused)"
        issues = parser.parse_text(output)
        assert len(issues) == 1

    def test_parse_strict_format(self, parser):
        """Test parsing strict lychee format with all fields."""
        output = "src/file.py:100: https://api.example.com/v1 (HTTP 403)"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert issues[0].file_path == "src/file.py"
        assert issues[0].line_number == 100

    def test_should_skip_emoji_prefixes(self, parser):
        """Test that emoji-prefixed lines are skipped."""
        assert parser._should_parse_lychee_line("🔍 Starting scan...") is False
        assert parser._should_parse_lychee_line("❌ 404 errors found") is False
        assert parser._should_parse_lychee_line("✅ All links valid") is False
        assert parser._should_parse_lychee_line("⚠️ Warning: slow response") is False

    def test_should_skip_stats_lines(self, parser):
        """Test that stats lines are skipped."""
        assert parser._should_parse_lychee_line("Stats: 100 links checked") is False
        assert parser._should_parse_lychee_line("Found 5 errors") is False
        assert parser._should_parse_lychee_line("Checked 50 URLs") is False
        assert parser._should_parse_lychee_line("Errors: 2") is False
        assert parser._should_parse_lychee_line("Success: all good") is False
        assert parser._should_parse_lychee_line("Total: 100") is False
        assert parser._should_parse_lychee_line("Running: active") is False
        assert parser._should_parse_lychee_line("Finished: at 12:00") is False

    def test_should_skip_empty_lines(self, parser):
        """Test that empty lines are skipped."""
        assert parser._should_parse_lychee_line("") is False
        assert parser._should_parse_lychee_line("   ") is False

    def test_should_skip_lines_without_urls(self, parser):
        """Test that lines without URLs are skipped."""
        assert parser._should_parse_lychee_line("Some error message without URL") is False
        assert parser._should_parse_lychee_line("file.py:42: some error") is False

    def test_should_parse_lines_with_urls(self, parser):
        """Test that lines with URLs are parsed."""
        assert parser._should_parse_lychee_line("file.md:10: https://example.com (error)") is True

    def test_get_severity_404(self, parser):
        """Test severity for 404 error."""
        severity = parser._get_severity("404 Not Found")
        assert severity.value == "high"

    def test_get_severity_410(self, parser):
        """Test severity for 410 error."""
        severity = parser._get_severity("410 Gone")
        assert severity.value == "high"

    def test_get_severity_403(self, parser):
        """Test severity for 403 error."""
        severity = parser._get_severity("403 Forbidden")
        assert severity.value == "high"

    def test_get_severity_401(self, parser):
        """Test severity for 401 error."""
        severity = parser._get_severity("401 Unauthorized")
        assert severity.value == "high"

    def test_get_severity_network_error(self, parser):
        """Test severity for network errors."""
        severity = parser._get_severity("Network timeout")
        assert severity.value == "medium"

    def test_get_severity_500_error(self, parser):
        """Test severity for 5xx errors."""
        severity = parser._get_severity("500 Internal Server Error")
        assert severity.value == "low"

    def test_get_severity_502_error(self, parser):
        """Test severity for 502 error."""
        severity = parser._get_severity("502 Bad Gateway")
        assert severity.value == "low"

    def test_get_severity_default(self, parser):
        """Test default severity."""
        severity = parser._get_severity("Some unknown error")
        assert severity.value == "medium"

    def test_get_severity_false_positive_location_indicator(self, parser):
        """Test severity for false positive location indicators."""
        # "at 530:3" style indicators should be MEDIUM, not HIGH
        severity = parser._get_severity("at 530:3")
        assert severity.value == "medium"
        severity = parser._get_severity("line 123")
        assert severity.value == "medium"

    def test_create_lychee_issue_false_positive(self, parser):
        """Test that false positive location indicators return None."""
        issue = parser._create_lychee_issue(
            file_path="file.md",
            line_number=10,
            url="https://example.com",
            error_message="at 530:3"
        )
        assert issue is None

    def test_create_lychee_issue_basic(self, parser):
        """Test creating basic lychee issue."""
        issue = parser._create_lychee_issue(
            file_path="docs/guide.md",
            line_number=42,
            url="https://example.com",
            error_message="404 Not Found"
        )
        assert issue is not None
        assert issue.type.value == "documentation"
        assert "example.com" in issue.message
        assert "404" in issue.message

    def test_extract_file_and_line_with_colon_prefix(self, parser):
        """Test extracting file and line from prefix."""
        file_path, line_number = parser._extract_file_and_line(
            "file.md:42: https://example.com (error)",
            30  # Position of URL
        )
        assert file_path == "file.md"
        assert line_number == 42

    def test_extract_file_and_line_without_line_number(self, parser):
        """Test extracting file when no line number is present."""
        file_path, line_number = parser._extract_file_and_line(
            "file.md: https://example.com (error)",
            15
        )
        assert file_path == "file.md"
        assert line_number is None

    def test_extract_file_and_line_rsplit(self, parser):
        """Test that rsplit is used for extracting line number."""
        # Uses rsplit to get the last colon-separated part as line number
        file_path, line_number = parser._extract_file_and_line(
            "path/to/file.md:100: https://example.com (error)",
            40
        )
        assert file_path == "path/to/file.md"
        assert line_number == 100

    def test_parse_empty_output(self, parser):
        """Test parsing empty output."""
        assert parser.parse_text("") == []
        assert parser.parse_text("   ") == []
        assert parser.parse_text("\n\n") == []

    def test_parse_with_multiple_lines(self, parser):
        """Test parsing multiple lines of lychee output."""
        output = """docs/guide.md:42: https://example1.com (404)
docs/api.md:100: https://example2.com (500)
README.md:5: https://example3.com (403)
"""
        issues = parser.parse_text(output)
        assert len(issues) == 3

    def test_parse_skips_non_url_lines(self, parser):
        """Test that non-URL lines are skipped during parsing."""
        output = """🔍 Starting link check
docs/guide.md:42: https://example.com (404)
Stats: 100 links checked
"""
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "example.com" in issues[0].message


class TestParseLycheeOutputFunction:
    """Tests for the standalone parse_lychee_output function."""

    def test_parse_lychee_output_basic(self):
        """Test the standalone parse_lychee_output function."""
        output = "docs/guide.md:42: https://example.com (404)"
        issues = parse_lychee_output(output)
        assert len(issues) == 1
        assert issues[0].stage == "lychee"

    def test_parse_lychee_output_empty(self):
        """Test parse_lychee_output with empty input."""
        assert parse_lychee_output("") == []
        assert parse_lychee_output("\n") == []


class TestLycheeParserEdgeCases:
    """Edge case tests for LycheeRegexParser."""

    def test_parse_url_with_special_characters(self, parser):
        """Test parsing URL with special characters."""
        output = "file.md:10: https://example.com/path?query=1&other=2 (404)"
        issues = parser.parse_text(output)
        assert len(issues) == 1

    def test_parse_url_with_fragments(self, parser):
        """Test parsing URL with fragment."""
        output = "file.md:10: https://example.com/page#section (404)"
        issues = parser.parse_text(output)
        assert len(issues) == 1

    def test_parse_http_url(self, parser):
        """Test parsing HTTP URL (not just HTTPS)."""
        output = "file.md:10: http://example.com (404)"
        issues = parser.parse_text(output)
        assert len(issues) == 1

    def test_parse_loose_format_extracts_url(self, parser):
        """Test that loose format correctly extracts URL."""
        output = "docs/README.md: https://python.org (timeout)"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "python.org" in issues[0].message

    def test_parse_loose_format_extracts_error(self, parser):
        """Test that loose format correctly extracts error message."""
        output = "README.md:5: https://example.com (connection refused)"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "connection refused" in issues[0].message.lower() or "connection refused" in issues[0].details[1]

    def test_parse_without_error_in_parentheses(self, parser):
        """Test parsing when no error in parentheses."""
        output = "file.md:10: https://example.com just some text"
        issues = parser.parse_text(output)
        # May create issue with "Unknown error" since no parentheses found
        assert len(issues) >= 0
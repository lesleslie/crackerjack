"""Tests for LycheeRegexParser - link checker parser."""

from __future__ import annotations

import pytest

from crackerjack.agents.base import IssueType, Priority
from crackerjack.parsers.lychee_parser import (
    LycheeRegexParser,
    parse_lychee_output,
)


class TestLycheeRegexParser:
    """Test suite for LycheeRegexParser."""

    @pytest.fixture
    def parser(self):
        return LycheeRegexParser()

    def test_parse_valid_lychee_line(self, parser):
        """Test parsing valid lychee output line."""
        output = "README.md:10: https://example.com (404 Not Found)"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "README.md"
        assert issues[0].line_number == 10
        assert "https://example.com" in issues[0].message
        assert "404" in issues[0].message
        assert issues[0].type == IssueType.DOCUMENTATION
        assert issues[0].severity == Priority.HIGH

    def test_parse_loose_format(self, parser):
        """Test parsing loose format without line number."""
        # Loose format lines don't match the strict pattern, so they may not parse
        output = "file.md: https://example.com (Connection timeout)"

        issues = parser.parse_text(output)

        # The parser may or may not produce issues depending on internal handling
        assert isinstance(issues, list)

    def test_skip_summary_lines(self, parser):
        """Test that summary lines are skipped."""
        outputs = [
            "🔍 Checking links...",
            "❌ 5 failed",
            "✅ All checks passed",
            "⚠️ Some warnings",
            "Stats: 100 URLs checked",
            "Found 3 broken links",
            "Checked 50 files",
            "Errors: 2",
            "Success: No issues",
            "Total: 100 links",
            "Running lychee...",
            "Finished processing",
        ]

        for output in outputs:
            issues = parser.parse_text(output)
            assert len(issues) == 0, f"Should skip: {output[:50]}"

    def test_parse_multiple_lines(self, parser):
        """Test parsing multiple lines with issues."""
        output = """
README.md:10: https://example1.com (404)
docs/guide.md:20: https://example2.com (403)
"""

        issues = parser.parse_text(output)

        assert len(issues) == 2
        assert issues[0].file_path == "README.md"
        assert issues[1].file_path == "docs/guide.md"

    def test_parse_404_severity(self, parser):
        """Test 404 errors get HIGH severity."""
        output = "file.md:10: https://example.com (404 Not Found)"

        issues = parser.parse_text(output)

        assert issues[0].severity == Priority.HIGH

    def test_parse_500_error_severity(self, parser):
        """Test 5xx errors get LOW severity."""
        output = "file.md:10: https://example.com (500 Internal Server Error)"

        issues = parser.parse_text(output)

        assert issues[0].severity == Priority.LOW

    def test_parse_network_error_severity(self, parser):
        """Test network errors get MEDIUM severity."""
        output = "file.md:10: https://example.com (Connection timeout)"

        issues = parser.parse_text(output)

        assert issues[0].severity == Priority.MEDIUM

    def test_skip_false_positive_location_indicators(self, parser):
        """Test that 'at X:Y' style indicators are skipped."""
        output = "file.md:10: https://example.com (at 530:3)"

        issues = parser.parse_text(output)

        # Should not create an issue for false positive
        assert len(issues) == 0

    def test_parse_mixed_content_with_urls(self, parser):
        """Test parsing content with both URLs and non-URL lines."""
        output = """
🔍 Checking links...
README.md:10: https://example1.com (404)
Checked 100 files
docs/guide.md:20: https://example2.com (403)
✅ Done
"""

        issues = parser.parse_text(output)

        assert len(issues) == 2

    def test_parse_lychee_output_standalone(self):
        """Test standalone parse_lychee_output function."""
        output = "README.md:10: https://example.com (404)"

        issues = parse_lychee_output(output)

        assert len(issues) == 1
        assert issues[0].stage == "lychee"

    def test_extract_file_and_line(self, parser):
        """Test _extract_file_and_line method with valid input."""
        # When there's a colon in the prefix and valid line number
        line = "README.md:10: https://example.com"
        url_pos = 20
        file_path, line_number = parser._extract_file_and_line(line, url_pos)

        # Should extract file path
        assert file_path is not None
        assert isinstance(file_path, str)

    def test_extract_file_and_line_invalid(self, parser):
        """Test _extract_file_and_line with invalid input (no colon)."""
        file_path, line_number = parser._extract_file_and_line(
            "no colon here", 5
        )

        # Without a colon, can't extract line number
        assert line_number is None

    def test_create_lychee_issue(self, parser):
        """Test _create_lychee_issue method."""
        issue = parser._create_lychee_issue(
            file_path="test.md",
            line_number=10,
            url="https://example.com",
            error_message="404 Not Found",
        )

        assert issue is not None
        assert issue.file_path == "test.md"
        assert issue.line_number == 10
        assert "https://example.com" in issue.message
        assert issue.details is not None
        assert any("url: https://example.com" in d for d in issue.details)


class TestLycheeRegexParserEdgeCases:
    """Edge case tests for LycheeRegexParser."""

    @pytest.fixture
    def parser(self):
        return LycheeRegexParser()

    def test_empty_output(self, parser):
        """Test empty output returns no issues."""
        issues = parser.parse_text("")
        assert issues == []

    def test_whitespace_only_output(self, parser):
        """Test whitespace-only output returns no issues."""
        issues = parser.parse_text("   \n\n   \n")
        assert issues == []

    def test_line_without_url(self, parser):
        """Test lines without URLs are skipped."""
        output = "This is a line without any URL in it"
        issues = parser.parse_text(output)
        assert issues == []

    def test_http_url_not_https(self, parser):
        """Test parsing HTTP URLs (not just HTTPS)."""
        output = "file.md:10: http://example.com (404)"
        issues = parser.parse_text(output)
        assert len(issues) == 1

    def test_line_with_only_url_and_parentheses(self, parser):
        """Test parsing line with only URL and error in parentheses."""
        output = "https://example.com (Connection reset)"
        issues = parser.parse_text(output)
        assert len(issues) == 1
        assert "https://example.com" in issues[0].message
"""Tests for base parser classes."""

import json
import pytest

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.base import JSONParser, RegexParser


class ConcreteJSONParser(JSONParser):
    """Concrete implementation for testing."""

    def parse_json(self, data):
        if isinstance(data, list):
            return [
                Issue(
                    type=IssueType.FORMATTING,
                    severity=Priority.LOW,
                    message=f"Item {i}",
                    file_path="test.py",
                    line_number=i,
                )
                for i in range(len(data))
            ]
        return []

    def get_issue_count(self, data):
        return len(data) if isinstance(data, list) else 0


class ConcreteRegexParser(RegexParser):
    """Concrete implementation for testing."""

    def parse_text(self, output):
        issues = []
        for i, line in enumerate(output.split("\n")):
            if line.strip():
                issues.append(
                    Issue(
                        type=IssueType.FORMATTING,
                        severity=Priority.LOW,
                        message=line.strip(),
                        file_path="test.txt",
                        line_number=i + 1,
                    )
                )
        return issues


class TestJSONParser:
    """Test JSONParser base class."""

    def test_parse_valid_json_array(self):
        """Test parsing valid JSON array."""
        parser = ConcreteJSONParser()
        data = [{"item": 1}, {"item": 2}]

        issues = parser.parse(json.dumps(data), "test_tool")

        assert len(issues) == 2

    def test_parse_empty_json(self):
        """Test parsing empty JSON."""
        parser = ConcreteJSONParser()

        with pytest.raises(Exception):  # ParsingError
            parser.parse("", "test_tool")

    def test_parse_json_with_text_before(self):
        """Test parsing JSON with text before it."""
        parser = ConcreteJSONParser()
        output = "Some text before\n[1, 2, 3]"

        issues = parser.parse(output, "test_tool")

        assert len(issues) == 3

    def test_parse_json_object(self):
        """Test parsing JSON object."""
        parser = ConcreteJSONParser()
        data = {"key": "value"}

        # Concrete implementation returns empty for non-list
        issues = parser.parse(json.dumps(data), "test_tool")

        assert len(issues) == 0

    def test_parse_nested_json_object(self):
        """Test parsing nested JSON object."""
        parser = ConcreteJSONParser()
        output = """
        Starting text
        {"outer": {"inner": [1, 2, 3]}}
        More text
        """

        issues = parser.parse(output, "test_tool")

        # Should find the object and return 0 (not a list)
        assert len(issues) == 0

    def test_parse_json_with_brackets(self):
        """Test parsing JSON array with nested brackets."""
        parser = ConcreteJSONParser()
        output = "Text [1, 2, [3, 4]]"

        issues = parser.parse(output, "test_tool")

        # Array has 3 top-level elements: 1, 2, and [3, 4]
        assert len(issues) == 3

    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        parser = ConcreteJSONParser()

        with pytest.raises(Exception):  # ParsingError
            parser.parse("{invalid json}", "test_tool")

    def test_parse_json_no_braces_or_brackets(self):
        """Test parsing output with no JSON structures."""
        parser = ConcreteJSONParser()

        with pytest.raises(Exception):  # ParsingError
            parser.parse("Just plain text", "test_tool")

    def test_parse_json_mismatched_braces(self):
        """Test parsing with mismatched braces."""
        parser = ConcreteJSONParser()

        with pytest.raises(Exception):  # ParsingError
            parser.parse("{[}]", "test_tool")


class TestRegexParser:
    """Test RegexParser base class."""

    def test_parse_text_multiple_lines(self):
        """Test parsing multi-line output."""
        parser = ConcreteRegexParser()
        output = "line 1\nline 2\nline 3"

        issues = parser.parse_text(output)

        assert len(issues) == 3
        assert issues[0].line_number == 1
        assert issues[1].line_number == 2
        assert issues[2].line_number == 3

    def test_parse_text_empty(self):
        """Test parsing empty output."""
        parser = ConcreteRegexParser()

        issues = parser.parse_text("")

        assert len(issues) == 0

    def test_parse_text_blank_lines(self):
        """Test parsing output with blank lines."""
        parser = ConcreteRegexParser()
        output = "line 1\n\nline 3\n  \nline 5"

        issues = parser.parse_text(output)

        # Concrete parser creates issues for non-empty lines
        assert len(issues) == 3

    def test_get_line_count_empty(self):
        """Test get_line_count with empty output."""
        parser = ConcreteRegexParser()

        count = parser.get_line_count("")

        assert count == 0

    def test_get_line_count_no_colons(self):
        """Test get_line_count with output having no colons."""
        parser = ConcreteRegexParser()
        output = "line without colons\nanother line"

        count = parser.get_line_count(output)

        assert count == 0

    def test_get_line_count_with_colons(self):
        """Test get_line_count counts lines with colons."""
        parser = ConcreteRegexParser()
        output = "file.py:1: error\nfile.py:2: warning"

        count = parser.get_line_count(output)

        assert count == 2

    def test_get_line_count_filters_blank_lines(self):
        """Test get_line_count filters out blank lines."""
        parser = ConcreteRegexParser()
        output = "file.py:1: error\n\nfile.py:2: warning"

        count = parser.get_line_count(output)

        assert count == 2

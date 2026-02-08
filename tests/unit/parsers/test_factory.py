"""Tests for parser factory."""

import json
import pytest

from crackerjack.parsers.factory import ParserFactory, ParsingError
from crackerjack.parsers.base import JSONParser, RegexParser
from crackerjack.agents.base import Issue, IssueType, Priority


class TestParserFactory:
    """Test ParserFactory class."""

    @pytest.fixture
    def factory(self):
        return ParserFactory()

    def test_factory_initialization(self, factory):
        """Test factory initializes with parsers registered."""
        assert len(factory._json_parsers) > 0
        assert len(factory._regex_parsers) > 0

    def test_register_json_parser(self, factory):
        """Test registering a JSON parser."""

        class CustomJSONParser(JSONParser):
            def parse_json(self, data):
                return []

            def get_issue_count(self, data):
                return 0

        factory.register_json_parser("custom-tool", CustomJSONParser)

        assert "custom-tool" in factory._json_parsers
        parser = factory.create_parser("custom-tool")
        assert isinstance(parser, CustomJSONParser)

    def test_register_regex_parser(self, factory):
        """Test registering a regex parser."""

        class CustomRegexParser(RegexParser):
            def parse_text(self, output):
                return []

        factory.register_regex_parser("custom-regex", CustomRegexParser)

        assert "custom-regex" in factory._regex_parsers
        parser = factory.create_parser("custom-regex")
        assert isinstance(parser, CustomRegexParser)

    def test_create_json_parser(self, factory):
        """Test creating JSON parser for supported tool."""
        parser = factory.create_parser("ruff")

        assert isinstance(parser, JSONParser)
        assert not isinstance(parser, RegexParser)

    def test_create_regex_parser(self, factory):
        """Test creating regex parser for tool."""
        parser = factory.create_parser("codespell")

        assert isinstance(parser, RegexParser)

    def test_create_parser_caching(self, factory):
        """Test that parsers are cached."""
        parser1 = factory.create_parser("ruff")
        parser2 = factory.create_parser("ruff")

        assert parser1 is parser2

    def test_create_parser_unknown_tool(self, factory):
        """Test creating parser for unknown tool raises error."""
        with pytest.raises(ValueError, match="No parser available"):
            factory.create_parser("unknown-tool-xyz")

    def test_parse_with_validation_json(self, factory):
        """Test parse_with_validation with JSON output."""
        output = json.dumps([{"filename": "test.py", "location": {"row": 5}, "code": "F401", "message": "error"}])

        # Mock parser
        class MockJSONParser(JSONParser):
            def parse_json(self, data):
                return [
                    Issue(
                        type=IssueType.FORMATTING,
                        severity=Priority.LOW,
                        message="test",
                        file_path="test.py",
                        line_number=5,
                    )
                ]

            def get_issue_count(self, data):
                return 1

        factory.register_json_parser("mock-tool", MockJSONParser)
        issues = factory.parse_with_validation("mock-tool", output, expected_count=1)

        assert len(issues) == 1

    def test_parse_with_validation_count_mismatch(self, factory):
        """Test parse_with_validation with count mismatch."""
        output = "[]"

        class MockJSONParser(JSONParser):
            def parse_json(self, data):
                return []

            def get_issue_count(self, data):
                return 0

        factory.register_json_parser("mock-tool", MockJSONParser)

        with pytest.raises(ParsingError, match="Issue count mismatch"):
            factory.parse_with_validation("mock-tool", output, expected_count=5)

    def test_is_json_output(self, factory):
        """Test _is_json_output detection."""
        assert factory._is_json_output('{"key": "value"}')
        assert factory._is_json_output('[1, 2, 3]')
        assert factory._is_json_output('text\n{"key": "value"}')
        assert not factory._is_json_output("plain text output")
        assert not factory._is_json_output("")

    def test_is_json_output_ruff_empty(self, factory):
        """Test _is_json_output handles ruff empty pattern."""
        assert factory._is_json_output("[*]")

    def test_is_json_output_with_quotes_and_colon(self, factory):
        """Test _is_json_output detects JSON-like patterns."""
        assert factory._is_json_output('{"version": "1.0"}')
        assert factory._is_json_output('{"results": []}')

    def test_parse_json_output_with_regex_parser(self, factory):
        """Test parsing JSON output with regex parser."""
        output = '{"key": "value"}'

        class MockRegexParser(RegexParser):
            def parse_text(self, output):
                return [
                    Issue(
                        type=IssueType.FORMATTING,
                        severity=Priority.LOW,
                        message="parsed",
                        file_path="test.txt",
                        line_number=1,
                    )
                ]

        factory.register_regex_parser("mock-regex", MockRegexParser)

        # Should attempt to parse and succeed with valid JSON
        issues = factory._parse_json_output(MockRegexParser(), output, "mock-regex")
        assert len(issues) == 1

    def test_parse_json_output_invalid_json(self, factory):
        """Test parsing invalid JSON raises ParsingError."""

        class MockJSONParser(JSONParser):
            def parse_json(self, data):
                return []

            def get_issue_count(self, data):
                return 0

        factory.register_json_parser("mock-tool", MockJSONParser)

        with pytest.raises(ParsingError, match="Invalid JSON output"):
            factory._parse_json_output(MockJSONParser(), "{invalid json", "mock-tool")

    def test_parse_text_output_with_regex_parser(self, factory):
        """Test parsing text output with regex parser."""

        class MockRegexParser(RegexParser):
            def parse_text(self, output):
                return [
                    Issue(
                        type=IssueType.FORMATTING,
                        severity=Priority.LOW,
                        message=output,
                        file_path="test.txt",
                        line_number=1,
                    )
                ]

        factory.register_regex_parser("mock-regex", MockRegexParser)

        parser = factory.create_parser("mock-regex")
        issues = factory._parse_text_output(parser, "error message", "mock-regex")

        assert len(issues) == 1

    def test_validate_issue_count_pass(self, factory):
        """Test _validate_issue_count when counts match."""
        issues = [
            Issue(
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message="test",
                file_path="test.py",
            )
        ]

        # Should not raise
        factory._validate_issue_count(issues, 1, "test-tool", "output")

    def test_validate_issue_count_fail(self, factory):
        """Test _validate_issue_count when counts don't match."""
        issues = [
            Issue(
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message="test",
                file_path="test.py",
            )
        ]

        with pytest.raises(ParsingError, match="Issue count mismatch"):
            factory._validate_issue_count(issues, 5, "test-tool", "output")

    def test_parse_with_validation_no_expected_count(self, factory):
        """Test parse_with_validation without expected count."""
        output = "text output"

        class MockRegexParser(RegexParser):
            def parse_text(self, output):
                return [
                    Issue(
                        type=IssueType.FORMATTING,
                        severity=Priority.LOW,
                        message=output,
                        file_path="test.txt",
                    )
                ]

        factory.register_regex_parser("mock-tool", MockRegexParser)

        # Should not validate count when expected_count is None
        issues = factory.parse_with_validation("mock-tool", output, expected_count=None)

        assert len(issues) == 1

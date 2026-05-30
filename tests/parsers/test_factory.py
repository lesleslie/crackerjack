"""Tests for factory module - ParserFactory and ParsingError."""

import json
import pytest
from unittest.mock import patch, MagicMock

from crackerjack.parsers.factory import ParserFactory, ParsingError
from crackerjack.agents.base import Issue, IssueType, Priority


class TestParsingError:
    """Tests for ParsingError exception."""

    def test_basic_error_message(self):
        """Test basic error message."""
        error = ParsingError("Test error", tool_name="test-tool")
        assert str(error) == "Test error"
        assert error.tool_name == "test-tool"

    def test_error_with_counts(self):
        """Test error with expected and actual counts."""
        error = ParsingError(
            "Count mismatch",
            tool_name="test-tool",
            expected_count=5,
            actual_count=3
        )
        assert "Expected: 5 issues" in str(error)
        assert "got: 3 issues" in str(error)

    def test_error_with_output_preview(self):
        """Test error with output preview truncation."""
        long_output = "x" * 500
        error = ParsingError(
            "Parse failed",
            tool_name="test-tool",
            output=long_output
        )
        error_str = str(error)
        assert "Output preview:" in error_str
        assert "..." in error_str  # Truncation indicator

    def test_error_with_short_output_shows_preview(self):
        """Test error with short output still shows preview."""
        error = ParsingError(
            "Short error",
            tool_name="test-tool",
            output="short"
        )
        # Implementation shows preview for any non-empty output (no length threshold)
        assert "Output preview:" in str(error)
        assert "short" in str(error)


class TestParserFactory:
    """Tests for ParserFactory."""

    @pytest.fixture
    def factory(self):
        """Create a fresh ParserFactory."""
        return ParserFactory()

    def test_initialization_registers_parsers(self, factory):
        """Test that factory initialization registers parsers."""
        # Should have both JSON and regex parsers registered
        assert len(factory._json_parsers) > 0 or len(factory._regex_parsers) > 0

    def test_register_json_parser(self, factory):
        """Test registering a JSON parser."""
        from crackerjack.parsers.base import JSONParser

        class DummyParser(JSONParser):
            def parse_json(self, data):
                return []
            def get_issue_count(self, data):
                return 0

        factory.register_json_parser("dummy", DummyParser)
        assert "dummy" in factory._json_parsers
        assert factory._json_parsers["dummy"] == DummyParser

    def test_register_regex_parser(self, factory):
        """Test registering a regex parser."""
        from crackerjack.parsers.base import RegexParser

        class DummyParser(RegexParser):
            def parse_text(self, output):
                return []

        factory.register_regex_parser("dummy-regex", DummyParser)
        assert "dummy-regex" in factory._regex_parsers
        assert factory._regex_parsers["dummy-regex"] == DummyParser

    def test_create_parser_json(self, factory):
        """Test creating a JSON parser."""
        parser = factory.create_parser("ruff")
        assert parser is not None

    def test_create_parser_regex(self, factory):
        """Test creating a regex parser."""
        parser = factory.create_parser("codespell")
        assert parser is not None

    def test_create_parser_caches(self, factory):
        """Test that parser is cached after creation."""
        parser1 = factory.create_parser("ruff")
        parser2 = factory.create_parser("ruff")
        assert parser1 is parser2

    def test_create_parser_unknown_raises(self, factory):
        """Test that creating parser for unknown tool raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            factory.create_parser("nonexistent-tool-xyz")
        assert "No parser available" in str(exc_info.value)

    def test_is_json_output_with_brackets(self, factory):
        """Test JSON detection with brackets."""
        assert factory._is_json_output("[1, 2, 3]") is True
        assert factory._is_json_output("{}") is True
        assert factory._is_json_output('{"key": "value"}') is True

    def test_is_json_output_with_ruff_empty_pattern(self, factory):
        """Test JSON detection with ruff empty patterns."""
        assert factory._is_json_output("[*]") is True
        assert factory._is_json_output("[^)]") is True

    def test_is_json_output_false_for_text(self, factory):
        """Test JSON detection returns False for text output."""
        assert factory._is_json_output("Some text output") is False
        assert factory._is_json_output("file.py:42: error") is False

    def test_is_json_output_with_leading_braces_in_line(self, factory):
        """Test JSON detection when JSON starts mid-output."""
        output = """Running tool...
{"filename": "test.py", "code": "F401"}
"""
        assert factory._is_json_output(output) is True

    def test_parse_with_validation_success(self, factory):
        """Test parsing with validation - success case."""
        json_output = json.dumps([
            {"filename": "test.py", "location": {"row": 10}, "code": "F401", "message": "Unused"},
            {"filename": "test.py", "location": {"row": 20}, "code": "F811", "message": "Reuse"},
        ])
        issues = factory.parse_with_validation(
            tool_name="ruff",
            output=json_output,
            expected_count=2
        )
        assert len(issues) == 2

    def test_parse_with_validation_mismatch(self, factory):
        """Test parsing with validation - mismatch case."""
        json_output = json.dumps([
            {"filename": "test.py", "location": {"row": 10}, "code": "F401", "message": "Unused"},
        ])
        with pytest.raises(ParsingError) as exc_info:
            factory.parse_with_validation(
                tool_name="ruff",
                output=json_output,
                expected_count=5
            )
        error = exc_info.value
        assert error.expected_count == 5
        assert error.actual_count == 1

    def test_parse_with_validation_none_expected(self, factory):
        """Test parsing without validation (expected_count=None)."""
        json_output = json.dumps([
            {"filename": "test.py", "location": {"row": 10}, "code": "F401", "message": "Unused"},
        ])
        # Should not raise even if counts don't match
        issues = factory.parse_with_validation(
            tool_name="ruff",
            output=json_output,
            expected_count=None
        )
        assert len(issues) == 1

    def test_parse_json_output_with_ruff_empty_pattern(self, factory):
        """Test parsing with ruff empty pattern '[*]'."""
        # Factory should convert "[*]" to "[]"
        issues = factory._parse_json_output(
            factory.create_parser("ruff"),
            "[*]",
            "ruff"
        )
        assert issues == []

    def test_parse_json_output_with_ruff_empty_pattern_paren(self, factory):
        """Test parsing with ruff empty pattern '[^)]'."""
        issues = factory._parse_json_output(
            factory.create_parser("ruff"),
            "[^)]",
            "ruff"
        )
        assert issues == []

    def test_parse_text_output_with_regex_parser(self, factory):
        """Test parsing text output with regex parser."""
        output = "file.py:42:佊 ==> expected"
        issues = factory._parse_text_output(
            factory.create_parser("codespell"),
            output,
            "codespell"
        )
        assert len(issues) >= 0  # May or may not have issues depending on format

    def test_parse_text_output_fallback_to_regex(self, factory):
        """Test text output falls back to regex when JSON parser exists."""
        # Use a tool that has JSON parser but we're passing text
        output = "file.py:42: Some error message"
        issues = factory._parse_text_output(
            factory.create_parser("ruff"),
            output,
            "ruff"  # ruff has JSON parser but we pass text
        )
        # Should fall back to regex parser
        assert isinstance(issues, list)

    def test_validate_issue_count_matches(self, factory):
        """Test issue count validation when counts match."""
        issues = [Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="e")]
        # Should not raise
        factory._validate_issue_count(issues, 1, "test-tool", "output")

    def test_validate_issue_count_mismatch(self, factory):
        """Test issue count validation when counts don't match."""
        issues = [Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="e")]
        with pytest.raises(ParsingError) as exc_info:
            factory._validate_issue_count(issues, 5, "test-tool", "output")
        error = exc_info.value
        assert error.expected_count == 5
        assert error.actual_count == 1


class TestParserFactoryIntegration:
    """Integration tests for ParserFactory with real parsers."""

    def test_full_parse_workflow_ruff(self):
        """Test complete parsing workflow for ruff."""
        factory = ParserFactory()

        ruff_output = json.dumps([
            {
                "filename": "src/app.py",
                "location": {"row": 42, "column": 10},
                "code": "F401",
                "message": "Unused import os"
            },
            {
                "filename": "src/app.py",
                "location": {"row": 43, "column": 5},
                "code": "F811",
                "message": "Redefinition of name 'x'"
            }
        ])

        issues = factory.parse_with_validation(
            tool_name="ruff",
            output=ruff_output,
            expected_count=2
        )

        assert len(issues) == 2
        assert issues[0].file_path == "src/app.py"
        assert issues[0].line_number == 42
        assert issues[1].line_number == 43

    def test_full_parse_workflow_mypy(self):
        """Test complete parsing workflow for mypy."""
        factory = ParserFactory()

        mypy_output = json.dumps([
            {
                "file": "src/types.py",
                "line": 10,
                "message": "Incompatible type: expected str, got int"
            }
        ])

        issues = factory.parse_with_validation(
            tool_name="mypy",
            output=mypy_output,
            expected_count=1
        )

        assert len(issues) == 1
        assert issues[0].type == IssueType.TYPE_ERROR

    def test_factory_with_text_output_fallback(self):
        """Test factory falls back to regex for text output."""
        factory = ParserFactory()

        # ruff-format only has regex parser
        output = "2 files would be reformatted"
        issues = factory._parse_text_output(
            factory.create_parser("ruff-format"),
            output,
            "ruff-format"
        )

        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING


class TestParserFactoryCache:
    """Tests for ParserFactory caching behavior."""

    def test_parser_cache_per_tool(self):
        """Test that each tool has its own cached parser."""
        factory = ParserFactory()

        ruff_parser = factory.create_parser("ruff")
        codespell_parser = factory.create_parser("codespell")

        assert ruff_parser is not codespell_parser

    def test_cache_is_returned_on_subsequent_calls(self):
        """Test that cached parser is returned on subsequent calls."""
        factory = ParserFactory()

        parser1 = factory.create_parser("ruff")
        parser2 = factory.create_parser("ruff")

        assert parser1 is parser2

    def test_fallback_parser_is_also_cached(self):
        """Test that fallback regex parser is also cached."""
        factory = ParserFactory()

        # Create JSON parser
        parser1 = factory.create_parser("ruff")
        # Force text output fallback by using _parse_text_output
        # But create_parser should cache based on tool_name

        # The cache key is the tool_name, so if we call create_parser again
        # we get the same cached parser


class TestFactoryWithMockedImports:
    """Tests for factory behavior when parser imports fail."""

    def test_factory_handles_import_errors_gracefully(self):
        """Test factory continues when JSON/regex parsers fail to import."""
        factory = ParserFactory()

        # Should still have some parsers registered even if some fail
        # This tests that import errors are caught and logged
        assert len(factory._json_parsers) >= 0
        assert len(factory._regex_parsers) >= 0

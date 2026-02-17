"""Tests for structured data parser (check-yaml, check-toml, check-json)."""

import pytest
from rich.console import Console

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.parsers.regex_parsers import StructuredDataParser


class TestStructuredDataParser:
    """Test parsing of check-yaml, check-toml, and check-json output."""

    @pytest.fixture
    def parser(self) -> StructuredDataParser:
        """Create a StructuredDataParser instance for testing."""
        return StructuredDataParser()

    # ========================================================================
    # Test _should_parse_structured_data_line
    # ========================================================================

    def test_should_parse_error_line(self, parser) -> None:
        """Test that error lines starting with ✗ are parsed."""
        line = "✗ settings/crackerjack.yaml: could not determine a constructor"
        assert parser._should_parse_structured_data_line(line) is True

    def test_should_parse_success_line(self, parser) -> None:
        """Test that success lines starting with ✓ are NOT parsed."""
        line = "✓ settings/crackerjack.yaml: Valid YAML"
        assert parser._should_parse_structured_data_line(line) is False

    def test_should_parse_empty_line(self, parser) -> None:
        """Test that empty lines are NOT parsed."""
        assert parser._should_parse_structured_data_line("") is False

    def test_should_parse_summary_line(self, parser) -> None:
        """Test that summary lines are NOT parsed."""
        line = "27 YAML file(s) with errors"
        assert parser._should_parse_structured_data_line(line) is False

    # ========================================================================
    # Test _extract_structured_data_parts
    # ========================================================================

    def test_extract_valid_error_line(self, parser) -> None:
        """Test extracting parts from a valid error line."""
        line = "✗ settings/crackerjack.yaml: could not determine a constructor"
        file_path, error_message = parser._extract_structured_data_parts(line)

        assert file_path == "settings/crackerjack.yaml"
        assert error_message == "could not determine a constructor"

    def test_extract_error_with_colon_in_message(self, parser) -> None:
        """Test extraction when error message contains colons."""
        line = "✗ config.yml: error: found unexpected ':' at line 5"
        file_path, error_message = parser._extract_structured_data_parts(line)

        assert file_path == "config.yml"
        assert error_message == "error: found unexpected ':' at line 5"

    def test_extract_error_without_file_path(self, parser) -> None:
        """Test extraction when line has no colon separator."""
        line = "✗ this line has no colon separator"
        file_path, error_message = parser._extract_structured_data_parts(line)

        assert file_path == ""
        assert error_message == "this line has no colon separator"

    def test_extract_error_with_spaces(self, parser) -> None:
        """Test extraction with extra whitespace."""
        line = "✗   settings/config.yaml  :  error message  "
        file_path, error_message = parser._extract_structured_data_parts(line)

        assert file_path == "settings/config.yaml"
        assert error_message == "error message"

    # ========================================================================
    # Test _parse_single_structured_data_line
    # ========================================================================

    def test_parse_valid_yaml_error(self, parser) -> None:
        """Test parsing a valid YAML error line."""
        line = "✗ settings/crackerjack.yaml: could not determine a constructor for the tag '!!python/object/apply:os.getenv'"
        issue = parser._parse_single_structured_data_line(line)

        assert issue is not None
        assert issue.file_path == "settings/crackerjack.yaml"
        assert "could not determine a constructor" in issue.message
        assert issue.severity == Priority.MEDIUM
        assert issue.type == IssueType.FORMATTING
        assert issue.line_number is None  # File-level validation
        assert issue.stage == "structured-data"

    def test_parse_valid_toml_error(self, parser) -> None:
        """Test parsing a valid TOML error line."""
        line = "✗ pyproject.toml: invalid key name 'test-key'"
        issue = parser._parse_single_structured_data_line(line)

        assert issue is not None
        assert issue.file_path == "pyproject.toml"
        assert "invalid key name" in issue.message
        assert issue.severity == Priority.MEDIUM
        assert issue.type == IssueType.FORMATTING

    def test_parse_valid_json_error(self, parser) -> None:
        """Test parsing a valid JSON error line."""
        line = "✗ package.json: Expecting property name, got '}'"
        issue = parser._parse_single_structured_data_line(line)

        assert issue is not None
        assert issue.file_path == "package.json"
        assert "Expecting property name" in issue.message
        assert issue.severity == Priority.MEDIUM
        assert issue.type == IssueType.FORMATTING

    def test_parse_invalid_line_returns_none(self, parser) -> None:
        """Test that invalid lines return None."""
        line = "not a valid error line"
        issue = parser._parse_single_structured_data_line(line)

        assert issue is None

    def test_parse_line_with_nested_path(self, parser) -> None:
        """Test parsing error with nested file path."""
        line = "✗ settings/local/dev.yaml: duplicate key 'database'"
        issue = parser._parse_single_structured_data_line(line)

        assert issue is not None
        assert issue.file_path == "settings/local/dev.yaml"
        assert "duplicate key" in issue.message

    # ========================================================================
    # Test _parse_structured_data_output
    # ========================================================================

    def test_parse_multiple_yaml_errors(self, parser) -> None:
        """Test parsing multiple YAML errors."""
        output = """
✗ settings/crackerjack.yaml: could not determine a constructor
✓ settings/local.yaml: Valid YAML
✗ .github/workflows/ci.yml: mapping values are not allowed here
✗ docs/config.yml: duplicate key 'name'
27 YAML file(s) with errors
""".strip()

        issues = parser.parse_text(output)

        assert len(issues) == 3
        assert issues[0].file_path == "settings/crackerjack.yaml"
        assert issues[1].file_path == ".github/workflows/ci.yml"
        assert issues[2].file_path == "docs/config.yml"

    def test_parse_toml_errors(self, parser) -> None:
        """Test parsing TOML errors."""
        output = """
✗ pyproject.toml: invalid string escape sequence
✓ README.toml: Valid TOML
✗ config/tool.toml: expected '=' after key
2 TOML file(s) with errors
""".strip()

        issues = parser.parse_text(output)

        assert len(issues) == 2
        assert issues[0].file_path == "pyproject.toml"
        assert issues[1].file_path == "config/tool.toml"

    def test_parse_json_errors(self, parser) -> None:
        """Test parsing JSON errors."""
        output = """
✗ package.json: Unexpected token '<'
✗ tsconfig.json: Trailing comma in object
✓ manifest.json: Valid JSON
2 JSON file(s) with errors
""".strip()

        issues = parser.parse_text(output)

        assert len(issues) == 2
        assert issues[0].file_path == "package.json"
        assert issues[1].file_path == "tsconfig.json"

    def test_parse_empty_output(self, parser) -> None:
        """Test parsing empty output."""
        issues = parser.parse_text("")
        assert len(issues) == 0

    def test_parse_output_with_only_valid_files(self, parser) -> None:
        """Test parsing output with only valid files (no errors)."""
        output = """
✓ settings/crackerjack.yaml: Valid YAML
✓ settings/local.yaml: Valid YAML
All 2 YAML file(s) are valid
""".strip()

        issues = parser.parse_text(output)
        assert len(issues) == 0

    # ========================================================================
    # Test integration with ParserFactory
    # ========================================================================

    def test_parser_factory_includes_check_yaml(self, parser) -> None:
        """Test that check-yaml is registered in ParserFactory."""
        from crackerjack.parsers.factory import ParserFactory

        factory = ParserFactory()
        output = "✗ test.yaml: test error"
        issues = factory.parse_with_validation("check-yaml", output, 1)

        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING

    def test_parser_factory_includes_check_toml(self, parser) -> None:
        """Test that check-toml is registered in ParserFactory."""
        from crackerjack.parsers.factory import ParserFactory

        factory = ParserFactory()
        output = "✗ test.toml: test error"
        issues = factory.parse_with_validation("check-toml", output, 1)

        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING

    def test_parser_factory_includes_check_json(self, parser) -> None:
        """Test that check-json is registered in ParserFactory."""
        from crackerjack.parsers.factory import ParserFactory

        factory = ParserFactory()
        output = "✗ test.json: test error"
        issues = factory.parse_with_validation("check-json", output, 1)

        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING


class TestStructuredDataParserIntegration:
    """Integration tests with mock HookResult objects."""

    @pytest.fixture
    def parser(self) -> StructuredDataParser:
        """Create a StructuredDataParser instance for testing."""
        return StructuredDataParser()

    def test_parse_hook_result_with_yaml_errors(self, parser) -> None:
        """Test parsing a complete HookResult with YAML errors."""
        output = "✓ file1.yaml: Valid YAML\n✗ file2.yaml: error message\n"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "file2.yaml"
        assert "error message" in issues[0].message

    def test_parse_hook_result_with_toml_errors(self, parser) -> None:
        """Test parsing a complete HookResult with TOML errors."""
        output = "✗ config.toml: invalid syntax\n"

        issues = parser.parse_text(output)

        assert len(issues) == 1
        assert issues[0].file_path == "config.toml"
        assert "invalid syntax" in issues[0].message

    def test_parse_hook_results_no_deduplication(self, parser) -> None:
        """Test that parser does NOT deduplicate (happens at higher level)."""
        output = "✗ file.yaml: error 1\n✗ file.yaml: error 1\n"

        issues = parser.parse_text(output)

        # Parser returns all issues, deduplication happens in AutofixCoordinator
        assert len(issues) == 2

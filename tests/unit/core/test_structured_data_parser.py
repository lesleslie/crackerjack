"""Tests for structured data parser (check-yaml, check-toml, check-json)."""

from unittest.mock import MagicMock

import pytest
from rich.console import Console

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.core.autofix_coordinator import AutofixCoordinator


class TestStructuredDataParser:
    """Test parsing of check-yaml, check-toml, and check-json output."""

    @pytest.fixture
    def coordinator(self) -> AutofixCoordinator:
        """Create an AutofixCoordinator instance for testing."""
        console = Console()
        return AutofixCoordinator(console=console)

    # ========================================================================
    # Test _should_parse_structured_data_line
    # ========================================================================

    def test_should_parse_error_line(self, coordinator) -> None:
        """Test that error lines starting with ✗ are parsed."""
        line = "✗ settings/crackerjack.yaml: could not determine a constructor"
        assert coordinator._should_parse_structured_data_line(line) is True

    def test_should_parse_success_line(self, coordinator) -> None:
        """Test that success lines starting with ✓ are NOT parsed."""
        line = "✓ settings/crackerjack.yaml: Valid YAML"
        assert coordinator._should_parse_structured_data_line(line) is False

    def test_should_parse_empty_line(self, coordinator) -> None:
        """Test that empty lines are NOT parsed."""
        assert coordinator._should_parse_structured_data_line("") is False

    def test_should_parse_summary_line(self, coordinator) -> None:
        """Test that summary lines are NOT parsed."""
        line = "27 YAML file(s) with errors"
        assert coordinator._should_parse_structured_data_line(line) is False

    # ========================================================================
    # Test _extract_structured_data_parts
    # ========================================================================

    def test_extract_valid_error_line(self, coordinator) -> None:
        """Test extracting parts from a valid error line."""
        line = "✗ settings/crackerjack.yaml: could not determine a constructor"
        file_path, error_message = coordinator._extract_structured_data_parts(line)

        assert file_path == "settings/crackerjack.yaml"
        assert error_message == "could not determine a constructor"

    def test_extract_error_with_colon_in_message(self, coordinator) -> None:
        """Test extraction when error message contains colons."""
        line = "✗ config.yml: error: found unexpected ':' at line 5"
        file_path, error_message = coordinator._extract_structured_data_parts(line)

        assert file_path == "config.yml"
        assert error_message == "error: found unexpected ':' at line 5"

    def test_extract_error_without_file_path(self, coordinator) -> None:
        """Test extraction when line has no colon separator."""
        line = "✗ this line has no colon separator"
        file_path, error_message = coordinator._extract_structured_data_parts(line)

        assert file_path == ""
        assert error_message == "this line has no colon separator"

    def test_extract_error_with_spaces(self, coordinator) -> None:
        """Test extraction with extra whitespace."""
        line = "✗   settings/config.yaml  :  error message  "
        file_path, error_message = coordinator._extract_structured_data_parts(line)

        assert file_path == "settings/config.yaml"
        assert error_message == "error message"

    # ========================================================================
    # Test _parse_single_structured_data_line
    # ========================================================================

    def test_parse_valid_yaml_error(self, coordinator) -> None:
        """Test parsing a valid YAML error line."""
        line = "✗ settings/crackerjack.yaml: could not determine a constructor for the tag '!!python/object/apply:os.getenv'"
        issue = coordinator._parse_single_structured_data_line(
            line, IssueType.FORMATTING
        )

        assert issue is not None
        assert issue.file_path == "settings/crackerjack.yaml"
        assert "could not determine a constructor" in issue.message
        assert issue.severity == Priority.MEDIUM
        assert issue.type == IssueType.FORMATTING
        assert issue.line_number is None  # File-level validation
        assert issue.stage == "structured-data"

    def test_parse_valid_toml_error(self, coordinator) -> None:
        """Test parsing a valid TOML error line."""
        line = "✗ pyproject.toml: invalid key name 'test-key'"
        issue = coordinator._parse_single_structured_data_line(
            line, IssueType.FORMATTING
        )

        assert issue is not None
        assert issue.file_path == "pyproject.toml"
        assert "invalid key name" in issue.message
        assert issue.severity == Priority.MEDIUM
        assert issue.type == IssueType.FORMATTING

    def test_parse_valid_json_error(self, coordinator) -> None:
        """Test parsing a valid JSON error line."""
        line = "✗ package.json: Expecting property name, got '}'"
        issue = coordinator._parse_single_structured_data_line(
            line, IssueType.FORMATTING
        )

        assert issue is not None
        assert issue.file_path == "package.json"
        assert "Expecting property name" in issue.message
        assert issue.severity == Priority.MEDIUM
        assert issue.type == IssueType.FORMATTING

    def test_parse_invalid_line_returns_none(self, coordinator) -> None:
        """Test that invalid lines return None."""
        line = "not a valid error line"
        issue = coordinator._parse_single_structured_data_line(
            line, IssueType.FORMATTING
        )

        assert issue is None

    def test_parse_line_with_nested_path(self, coordinator) -> None:
        """Test parsing error with nested file path."""
        line = "✗ settings/local/dev.yaml: duplicate key 'database'"
        issue = coordinator._parse_single_structured_data_line(
            line, IssueType.FORMATTING
        )

        assert issue is not None
        assert issue.file_path == "settings/local/dev.yaml"
        assert "duplicate key" in issue.message

    # ========================================================================
    # Test _parse_structured_data_output
    # ========================================================================

    def test_parse_multiple_yaml_errors(self, coordinator) -> None:
        """Test parsing multiple YAML errors."""
        output = """
✗ settings/crackerjack.yaml: could not determine a constructor
✓ settings/local.yaml: Valid YAML
✗ .github/workflows/ci.yml: mapping values are not allowed here
✗ docs/config.yml: duplicate key 'name'
27 YAML file(s) with errors
""".strip()

        issues = coordinator._parse_structured_data_output(output, IssueType.FORMATTING)

        assert len(issues) == 3
        assert issues[0].file_path == "settings/crackerjack.yaml"
        assert issues[1].file_path == ".github/workflows/ci.yml"
        assert issues[2].file_path == "docs/config.yml"

    def test_parse_toml_errors(self, coordinator) -> None:
        """Test parsing TOML errors."""
        output = """
✗ pyproject.toml: invalid string escape sequence
✓ README.toml: Valid TOML
✗ config/tool.toml: expected '=' after key
2 TOML file(s) with errors
""".strip()

        issues = coordinator._parse_structured_data_output(output, IssueType.FORMATTING)

        assert len(issues) == 2
        assert issues[0].file_path == "pyproject.toml"
        assert issues[1].file_path == "config/tool.toml"

    def test_parse_json_errors(self, coordinator) -> None:
        """Test parsing JSON errors."""
        output = """
✗ package.json: Unexpected token '<'
✗ tsconfig.json: Trailing comma in object
✓ manifest.json: Valid JSON
2 JSON file(s) with errors
""".strip()

        issues = coordinator._parse_structured_data_output(output, IssueType.FORMATTING)

        assert len(issues) == 2
        assert issues[0].file_path == "package.json"
        assert issues[1].file_path == "tsconfig.json"

    def test_parse_empty_output(self, coordinator) -> None:
        """Test parsing empty output."""
        issues = coordinator._parse_structured_data_output("", IssueType.FORMATTING)
        assert len(issues) == 0

    def test_parse_output_with_only_valid_files(self, coordinator) -> None:
        """Test parsing output with only valid files (no errors)."""
        output = """
✓ settings/crackerjack.yaml: Valid YAML
✓ settings/local.yaml: Valid YAML
All 2 YAML file(s) are valid
""".strip()

        issues = coordinator._parse_structured_data_output(output, IssueType.FORMATTING)
        assert len(issues) == 0

    # ========================================================================
    # Test integration with _parse_hook_to_issues
    # ========================================================================

    def test_hook_type_map_includes_check_yaml(self, coordinator) -> None:
        """Test that check-yaml is in hook_type_map."""
        from crackerjack.core.autofix_coordinator import IssueType

        # Access the internal map through _parse_hook_to_issues
        output = "✗ test.yaml: test error"
        issues = coordinator._parse_hook_to_issues("check-yaml", output)

        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING

    def test_hook_type_map_includes_check_toml(self, coordinator) -> None:
        """Test that check-toml is in hook_type_map."""
        output = "✗ test.toml: test error"
        issues = coordinator._parse_hook_to_issues("check-toml", output)

        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING

    def test_hook_type_map_includes_check_json(self, coordinator) -> None:
        """Test that check-json is in hook_type_map."""
        output = "✗ test.json: test error"
        issues = coordinator._parse_hook_to_issues("check-json", output)

        assert len(issues) == 1
        assert issues[0].type == IssueType.FORMATTING


class TestStructuredDataParserIntegration:
    """Integration tests with mock HookResult objects."""

    @pytest.fixture
    def coordinator(self) -> AutofixCoordinator:
        """Create an AutofixCoordinator instance for testing."""
        console = Console()
        return AutofixCoordinator(console=console)

    def test_parse_hook_result_with_yaml_errors(self, coordinator) -> None:
        """Test parsing a complete HookResult with YAML errors."""
        from unittest.mock import Mock

        hook_result = Mock()
        hook_result.status = "failed"
        hook_result.name = "check-yaml"
        hook_result.output = "✓ file1.yaml: Valid YAML\n✗ file2.yaml: error message\n"
        hook_result.error = "1 YAML file(s) with errors"
        hook_result.error_message = None

        issues = coordinator._parse_single_hook_result(hook_result)

        assert len(issues) == 1
        assert issues[0].file_path == "file2.yaml"
        assert "error message" in issues[0].message

    def test_parse_hook_result_with_toml_errors(self, coordinator) -> None:
        """Test parsing a complete HookResult with TOML errors."""
        from unittest.mock import Mock

        hook_result = Mock()
        hook_result.status = "failed"
        hook_result.name = "check-toml"
        hook_result.output = "✗ config.toml: invalid syntax\n"
        hook_result.error = ""
        hook_result.error_message = None

        issues = coordinator._parse_single_hook_result(hook_result)

        assert len(issues) == 1
        assert issues[0].file_path == "config.toml"
        assert "invalid syntax" in issues[0].message

    def test_parse_hook_results_to_issues_deduplicates(
        self, coordinator
    ) -> None:
        """Test that duplicate issues are deduplicated."""
        from unittest.mock import Mock

        hook1 = Mock()
        hook1.status = "failed"
        hook1.name = "check-yaml"
        hook1.output = "✗ file.yaml: error 1\n✗ file.yaml: error 1\n"
        hook1.error = ""
        hook1.error_message = None

        issues = coordinator._parse_hook_results_to_issues([hook1])

        # Should deduplicate identical errors
        assert len(issues) == 1

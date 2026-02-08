"""Integration tests for tool-parser workflow."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from crackerjack.parsers.factory import ParserFactory


class TestToolParserIntegration:
    """Test end-to-end tool-parser workflows."""

    @pytest.fixture
    def parser_factory(self):
        return ParserFactory()

    def test_json_validation_workflow(self, tmp_path, parser_factory, capsys):
        """Test complete JSON validation workflow."""
        # Create test file
        json_file = tmp_path / "test.json"
        json_file.write_text('{"valid": "json"}')

        # Run tool
        from crackerjack.tools.check_json import validate_json_file

        is_valid, error = validate_json_file(json_file)

        assert is_valid is True

    def test_json_validation_with_error(self, tmp_path, parser_factory):
        """Test JSON validation detects errors."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text('{"invalid": }')

        from crackerjack.tools.check_json import validate_json_file

        is_valid, error = validate_json_file(json_file)

        assert is_valid is False
        assert error is not None

    def test_yaml_validation_workflow(self, tmp_path, parser_factory):
        """Test complete YAML validation workflow."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value\nlist:\n  - item")

        from crackerjack.tools.check_yaml import validate_yaml_file

        is_valid, error = validate_yaml_file(yaml_file)

        assert is_valid is True

    def test_yaml_duplicate_key_detection(self, tmp_path, parser_factory):
        """Test YAML validation catches duplicate keys."""
        yaml_file = tmp_path / "duplicate.yaml"
        yaml_file.write_text("key: value1\nkey: value2")

        from crackerjack.tools.check_yaml import validate_yaml_file

        is_valid, error = validate_yaml_file(yaml_file)

        assert is_valid is False
        assert "Duplicate key" in error

    def test_toml_validation_workflow(self, tmp_path, parser_factory):
        """Test complete TOML validation workflow."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('[section]\nkey = "value"')

        from crackerjack.tools.check_toml import validate_toml_file

        is_valid, error = validate_toml_file(toml_file)

        assert is_valid is True

    def test_toml_validation_with_error(self, tmp_path, parser_factory):
        """Test TOML validation detects errors."""
        toml_file = tmp_path / "invalid.toml"
        toml_file.write_text('[invalid')

        from crackerjack.tools.check_toml import validate_toml_file

        is_valid, error = validate_toml_file(toml_file)

        assert is_valid is False
        assert error is not None

    def test_ruff_parser_with_json_output(self, parser_factory):
        """Test ruff parser handles JSON output."""
        output = json.dumps([
            {
                "filename": "test.py",
                "location": {"row": 10, "column": 5},
                "code": "F401",
                "message": "Unused import",
            }
        ])

        issues = parser_factory.parse_with_validation("ruff", output, expected_count=1)

        assert len(issues) == 1
        assert issues[0].file_path == "test.py"
        assert issues[0].line_number == 10
        assert "F401" in issues[0].message

    def test_codespell_parser_integration(self, parser_factory):
        """Test codespell parser integration."""
        output = "README.md:10: the ==> the"

        issues = parser_factory.parse_with_validation("codespell", output)

        assert len(issues) == 1
        assert issues[0].file_path == "README.md"
        assert issues[0].line_number == 10

    def test_mypy_parser_integration(self, parser_factory):
        """Test mypy parser integration."""
        output = json.dumps([
            {
                "file": "test.py",
                "line": 5,
                "message": "Incompatible types",
                "severity": "error",
            }
        ])

        issues = parser_factory.parse_with_validation("mypy", output, expected_count=1)

        assert len(issues) == 1
        assert issues[0].type.name == "TYPE_ERROR"

    def test_bandit_parser_integration(self, parser_factory):
        """Test bandit parser integration."""
        output = json.dumps({
            "results": [
                {
                    "filename": "test.py",
                    "line_number": 10,
                    "issue_text": "Use of assert detected",
                    "issue_severity": "MEDIUM",
                    "test_id": "S101",
                }
            ]
        })

        issues = parser_factory.parse_with_validation("bandit", output, expected_count=1)

        assert len(issues) == 1
        assert issues[0].type.name == "SECURITY"
        assert "S101" in issues[0].message

    def test_semgrep_parser_integration(self, parser_factory):
        """Test semgrep parser integration."""
        output = json.dumps({
            "results": [
                {
                    "path": "test.py",
                    "start": {"line": 15},
                    "extra": {
                        "message": "Dangerous function",
                        "severity": "ERROR",
                    },
                    "check_id": "python.lang.security.dangerous",
                }
            ]
        })

        issues = parser_factory.parse_with_validation("semgrep", output, expected_count=1)

        assert len(issues) == 1
        assert issues[0].severity.name == "CRITICAL"

    def test_empty_output_handling(self, parser_factory):
        """Test that empty output is handled correctly."""
        # Different tools handle empty output differently
        # Most should return no issues

        codespell_output = ""
        issues = parser_factory.parse_with_validation("codespell", codespell_output)

        assert len(issues) == 0

    def test_malformed_output_handling(self, parser_factory):
        """Test that malformed output is handled gracefully."""
        malformed_output = "This is not valid tool output"

        # Generic parsers should handle this
        issues = parser_factory.parse_with_validation("codespell", malformed_output)

        # Should either return empty or best-effort parse
        assert isinstance(issues, list)

    def test_parser_factory_caching(self, parser_factory):
        """Test that parser factory caches parsers."""
        parser1 = parser_factory.create_parser("ruff")
        parser2 = parser_factory.create_parser("ruff")

        assert parser1 is parser2

    def test_multiple_tools_same_session(self, parser_factory):
        """Test using multiple parsers in same session."""
        ruff_output = json.dumps([{
            "filename": "test.py",
            "location": {"row": 1},
            "code": "F401",
            "message": "error",
        }])

        codespell_output = "README.md:5: the ==> the"

        ruff_issues = parser_factory.parse_with_validation("ruff", ruff_output)
        codespell_issues = parser_factory.parse_with_validation("codespell", codespell_output)

        assert len(ruff_issues) == 1
        assert len(codespell_issues) == 1

    def test_validation_with_correct_count(self, parser_factory):
        """Test validation passes when count matches."""
        output = json.dumps([{
            "filename": "test.py",
            "location": {"row": 1},
            "code": "F401",
            "message": "error",
        }])

        # Should not raise
        issues = parser_factory.parse_with_validation("ruff", output, expected_count=1)

        assert len(issues) == 1

    def test_validation_with_incorrect_count(self, parser_factory):
        """Test validation fails when count doesn't match."""
        from crackerjack.parsers.factory import ParsingError

        output = json.dumps([{
            "filename": "test.py",
            "location": {"row": 1},
            "code": "F401",
            "message": "error",
        }])

        with pytest.raises(ParsingError, match="Issue count mismatch"):
            parser_factory.parse_with_validation("ruff", output, expected_count=5)

    def test_complexity_parser_integration(self, parser_factory):
        """Test complexity parser integration."""
        output = """
Failed functions:
- file.py:
  function1::complexity 20
  function2::complexity 25
"""

        issues = parser_factory.parse_with_validation("complexity", output)

        assert len(issues) == 2
        assert all(i.type.name == "COMPLEXITY" for i in issues)

    def test_structured_data_parser_integration(self, parser_factory):
        """Test structured data parser integration."""
        output = "✗ config.json: Invalid JSON syntax"

        issues = parser_factory.parse_with_validation("check-json", output)

        assert len(issues) == 1
        assert "config.json" in issues[0].file_path

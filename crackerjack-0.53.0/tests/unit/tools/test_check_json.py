"""Tests for check_json tool."""

import json
from pathlib import Path

import pytest

from crackerjack.tools.check_json import main, validate_json_file


class TestValidateJsonFile:
    """Test JSON file validation."""

    def test_valid_json(self, tmp_path):
        """Test validation of valid JSON file."""
        test_file = tmp_path / "valid.json"
        test_file.write_text('{"name": "test", "value": 123}')

        is_valid, error = validate_json_file(test_file)

        assert is_valid is True
        assert error is None

    def test_invalid_json_syntax(self, tmp_path):
        """Test validation of invalid JSON file."""
        test_file = tmp_path / "invalid.json"
        test_file.write_text('{"name": "test", invalid}')

        is_valid, error = validate_json_file(test_file)

        assert is_valid is False
        assert error is not None
        assert "Expecting" in error or "JSONDecodeError" in error

    def test_empty_json(self, tmp_path):
        """Test validation of empty JSON file."""
        test_file = tmp_path / "empty.json"
        test_file.write_text("{}")

        is_valid, error = validate_json_file(test_file)

        assert is_valid is True
        assert error is None

    def test_json_array(self, tmp_path):
        """Test validation of JSON array."""
        test_file = tmp_path / "array.json"
        test_file.write_text('[1, 2, 3, {"key": "value"}]')

        is_valid, error = validate_json_file(test_file)

        assert is_valid is True
        assert error is None

    def test_nonexistent_file(self, tmp_path):
        """Test validation of nonexistent file."""
        test_file = tmp_path / "nonexistent.json"

        is_valid, error = validate_json_file(test_file)

        assert is_valid is False
        assert "Error reading file" in error


class TestCheckJsonMain:
    """Test check_json main function."""

    def test_main_with_valid_files(self, tmp_path, capsys):
        """Test main with valid JSON files."""
        valid_file = tmp_path / "valid.json"
        valid_file.write_text('{"test": "data"}')

        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([str(valid_file)])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "Valid JSON" in captured.out

    def test_main_with_invalid_files(self, tmp_path, capsys):
        """Test main with invalid JSON files."""
        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text('{"invalid": }')

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([str(invalid_file)])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 1
        assert "with errors" in captured.err

    def test_main_no_files(self, tmp_path, capsys):
        """Test main with no JSON files."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "No JSON files to check" in captured.out

    def test_main_multiple_files_mixed(self, tmp_path, capsys):
        """Test main with multiple files (valid and invalid)."""
        valid_file = tmp_path / "valid.json"
        valid_file.write_text('{"ok": true}')

        invalid_file = tmp_path / "invalid.json"
        invalid_file.write_text('{broken}')

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([str(valid_file), str(invalid_file)])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 1
        assert "1 JSON file(s) with errors" in captured.err

    def test_main_nested_json(self, tmp_path, capsys):
        """Test main with nested JSON structures."""
        nested_file = tmp_path / "nested.json"
        nested_data = {
            "level1": {
                "level2": {
                    "level3": ["a", "b", "c"]
                }
            },
            "array": [{"key": "value"}, {"another": "item"}]
        }
        nested_file.write_text(json.dumps(nested_data))

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([str(nested_file)])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "Valid JSON" in captured.out

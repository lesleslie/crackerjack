"""Tests for JSON file validation tool."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.tools.check_json import main, validate_json_file


class TestValidateJsonFile:
    """Tests for validate_json_file function."""

    def test_valid_json_object(self, tmp_path: Path) -> None:
        """Verify valid JSON object is accepted."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')
        is_valid, error = validate_json_file(json_file)
        assert is_valid is True
        assert error is None

    def test_valid_json_array(self, tmp_path: Path) -> None:
        """Verify valid JSON array is accepted."""
        json_file = tmp_path / "test.json"
        json_file.write_text('[1, 2, 3]')
        is_valid, error = validate_json_file(json_file)
        assert is_valid is True
        assert error is None

    def test_valid_json_nested(self, tmp_path: Path) -> None:
        """Verify nested JSON structures are valid."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"nested": {"key": [1, 2, 3]}}')
        is_valid, error = validate_json_file(json_file)
        assert is_valid is True
        assert error is None

    def test_valid_json_empty_object(self, tmp_path: Path) -> None:
        """Verify empty JSON object is valid."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{}')
        is_valid, error = validate_json_file(json_file)
        assert is_valid is True
        assert error is None

    def test_valid_json_empty_array(self, tmp_path: Path) -> None:
        """Verify empty JSON array is valid."""
        json_file = tmp_path / "test.json"
        json_file.write_text('[]')
        is_valid, error = validate_json_file(json_file)
        assert is_valid is True
        assert error is None

    def test_invalid_json_trailing_comma(self, tmp_path: Path) -> None:
        """Verify JSON with trailing comma is invalid."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value",}')
        is_valid, error = validate_json_file(json_file)
        assert is_valid is False
        assert error is not None
        assert "trailing comma" in error.lower() or "Expecting" in error

    def test_invalid_json_single_quotes(self, tmp_path: Path) -> None:
        """Verify JSON with single quotes is invalid."""
        json_file = tmp_path / "test.json"
        json_file.write_text("{'key': 'value'}")
        is_valid, error = validate_json_file(json_file)
        assert is_valid is False
        assert error is not None

    def test_invalid_json_missing_comma(self, tmp_path: Path) -> None:
        """Verify JSON missing comma is invalid."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key1": "value1" "key2": "value2"}')
        is_valid, error = validate_json_file(json_file)
        assert is_valid is False
        assert error is not None

    def test_invalid_json_syntax_error(self, tmp_path: Path) -> None:
        """Verify malformed JSON is invalid."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"')
        is_valid, error = validate_json_file(json_file)
        assert is_valid is False
        assert error is not None

    def test_file_not_found(self, tmp_path: Path) -> None:
        """Verify error when file does not exist."""
        json_file = tmp_path / "nonexistent.json"
        is_valid, error = validate_json_file(json_file)
        assert is_valid is False
        assert error is not None
        assert "Error reading file" in error

    def test_invalid_json_comments(self, tmp_path: Path) -> None:
        """Verify JSON with comments is invalid."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value" /* comment */}')
        is_valid, error = validate_json_file(json_file)
        assert is_valid is False
        assert error is not None


class TestMain:
    """Tests for main CLI function."""

    def test_main_no_files_empty_directory(self, tmp_path: Path) -> None:
        """Verify exit code 0 when no JSON files found."""
        with patch("crackerjack.tools.check_json.get_files_by_extension") as mock_get:
            mock_get.return_value = []
            with patch("pathlib.Path.cwd") as mock_cwd:
                mock_cwd.return_value = tmp_path
                with patch("builtins.print"):
                    result = main([])
        assert result == 0

    def test_main_single_valid_file(self, tmp_path: Path) -> None:
        """Verify success with single valid JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')
        with patch("builtins.print") as mock_print:
            result = main([str(json_file)])
        assert result == 0
        # Verify success message printed
        calls = [c[0][0] for c in mock_print.call_args_list]
        assert any("Valid JSON" in str(c) for c in calls)

    def test_main_single_invalid_file(self, tmp_path: Path) -> None:
        """Verify failure with single invalid JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value",}')
        with patch("builtins.print"):
            result = main([str(json_file)])
        assert result == 1

    def test_main_multiple_valid_files(self, tmp_path: Path) -> None:
        """Verify success with multiple valid JSON files."""
        file1 = tmp_path / "test1.json"
        file2 = tmp_path / "test2.json"
        file1.write_text('{"key": "value"}')
        file2.write_text('[1, 2, 3]')
        with patch("builtins.print") as mock_print:
            result = main([str(file1), str(file2)])
        assert result == 0
        calls = [c[0][0] for c in mock_print.call_args_list]
        assert any("All" in str(c) and "valid" in str(c) for c in calls)

    def test_main_mixed_valid_invalid_files(self, tmp_path: Path) -> None:
        """Verify failure when some files are invalid."""
        valid_file = tmp_path / "valid.json"
        invalid_file = tmp_path / "invalid.json"
        valid_file.write_text('{"key": "value"}')
        invalid_file.write_text('{"key": "value",}')
        with patch("builtins.print"):
            result = main([str(valid_file), str(invalid_file)])
        assert result == 1

    def test_main_filters_out_directories(self, tmp_path: Path) -> None:
        """Verify directories are filtered out from file list."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        json_file = tmp_path / "test.json"
        json_file.write_text('{}')
        with patch("builtins.print"):
            result = main([str(subdir), str(json_file)])
        assert result == 0

    def test_main_no_json_files_message(self, tmp_path: Path) -> None:
        """Verify message when no JSON files to check."""
        with patch("crackerjack.tools.check_json.get_files_by_extension") as mock_get:
            mock_get.return_value = []
            with patch("pathlib.Path.cwd") as mock_cwd:
                mock_cwd.return_value = tmp_path
                with patch("builtins.print") as mock_print:
                    result = main([])
        assert result == 0
        mock_print.assert_called()
        calls = [c[0][0] for c in mock_print.call_args_list]
        assert any("No JSON files" in str(c) for c in calls)

    def test_main_error_count_message(self, tmp_path: Path) -> None:
        """Verify error count message is printed."""
        file1 = tmp_path / "invalid1.json"
        file2 = tmp_path / "invalid2.json"
        file1.write_text('{"bad":}')
        file2.write_text('[1, 2,]')
        with patch("builtins.print") as mock_print:
            result = main([str(file1), str(file2)])
        assert result == 1
        # Check that error count message was printed
        calls = [c[0][0] for c in mock_print.call_args_list]
        assert any("2 JSON file(s) with errors" in str(c) for c in calls)

    def test_main_prints_file_paths(self, tmp_path: Path) -> None:
        """Verify file paths are printed in output."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{}')
        with patch("builtins.print") as mock_print:
            result = main([str(json_file)])
        assert result == 0
        calls = [c[0][0] for c in mock_print.call_args_list]
        assert any(str(json_file) in str(c) for c in calls)

    def test_main_uses_sys_stderr_for_errors(self, tmp_path: Path) -> None:
        """Verify errors are written to stderr."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"bad":}')
        with patch("builtins.print") as mock_print:
            result = main([str(json_file)])
        assert result == 1
        # Check that at least one call wrote to stderr
        stderr_calls = [c for c in mock_print.call_args_list if c[1].get("file") == sys.stderr]
        assert len(stderr_calls) > 0

    def test_main_success_message_to_stdout(self, tmp_path: Path) -> None:
        """Verify success messages go to stdout."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{}')
        with patch("builtins.print") as mock_print:
            result = main([str(json_file)])
        assert result == 0
        # Check that success message doesn't use stderr
        all_calls = mock_print.call_args_list
        assert len(all_calls) > 0

    def test_main_default_nargs_allows_no_args(self) -> None:
        """Verify main can be called with empty argv."""
        with patch("crackerjack.tools.check_json.get_files_by_extension") as mock_get:
            mock_get.return_value = []
            with patch("pathlib.Path.cwd"):
                with patch("builtins.print"):
                    result = main([])
        assert result == 0

    def test_main_accepts_multiple_paths(self, tmp_path: Path) -> None:
        """Verify main accepts multiple file paths as arguments."""
        file1 = tmp_path / "file1.json"
        file2 = tmp_path / "file2.json"
        file3 = tmp_path / "file3.json"
        file1.write_text('{}')
        file2.write_text('[]')
        file3.write_text('{"a": 1}')
        with patch("builtins.print"):
            result = main([str(file1), str(file2), str(file3)])
        assert result == 0

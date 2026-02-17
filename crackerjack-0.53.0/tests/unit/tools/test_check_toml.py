"""Tests for check_toml tool."""

import pytest
from pathlib import Path

from crackerjack.tools.check_toml import main, validate_toml_file


class TestValidateTomlFile:
    """Test TOML file validation."""

    def test_valid_toml(self, tmp_path):
        """Test validation of valid TOML file."""
        test_file = tmp_path / "valid.toml"
        test_file.write_text("""
[tool.section]
key = "value"
number = 123
boolean = true
""")

        is_valid, error = validate_toml_file(test_file)

        assert is_valid is True
        assert error is None

    def test_invalid_toml_syntax(self, tmp_path):
        """Test validation of invalid TOML file."""
        test_file = tmp_path / "invalid.toml"
        test_file.write_text("""
[key = unclosed bracket
""")

        is_valid, error = validate_toml_file(test_file)

        assert is_valid is False
        assert error is not None

    def test_empty_toml(self, tmp_path):
        """Test validation of empty TOML file."""
        test_file = tmp_path / "empty.toml"
        test_file.write_text("")

        is_valid, error = validate_toml_file(test_file)

        assert is_valid is True
        assert error is None

    def test_toml_with_arrays(self, tmp_path):
        """Test validation of TOML with arrays."""
        test_file = tmp_path / "array.toml"
        test_file.write_text("""
items = ["one", "two", "three"]
numbers = [1, 2, 3]
""")

        is_valid, error = validate_toml_file(test_file)

        assert is_valid is True
        assert error is None

    def test_toml_nested_tables(self, tmp_path):
        """Test validation of TOML with nested tables."""
        test_file = tmp_path / "nested.toml"
        test_file.write_text("""
[parent]
  [parent.child]
    key = "value"
""")

        is_valid, error = validate_toml_file(test_file)

        assert is_valid is True
        assert error is None

    def test_toml_datetime(self, tmp_path):
        """Test validation of TOML with datetime values."""
        test_file = tmp_path / "datetime.toml"
        test_file.write_text("""
date = 2024-01-01
time = 12:00:00
datetime = 2024-01-01T12:00:00-04:00
""")

        is_valid, error = validate_toml_file(test_file)

        assert is_valid is True
        assert error is None

    def test_nonexistent_file(self, tmp_path):
        """Test validation of nonexistent file."""
        test_file = tmp_path / "nonexistent.toml"

        is_valid, error = validate_toml_file(test_file)

        assert is_valid is False
        assert "Error reading file" in error


class TestCheckTomlMain:
    """Test check_toml main function."""

    def test_main_with_valid_files(self, tmp_path, capsys):
        """Test main with valid TOML files."""
        valid_file = tmp_path / "valid.toml"
        valid_file.write_text('[section]\nkey = "value"')

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([str(valid_file)])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "Valid TOML" in captured.out

    def test_main_with_invalid_files(self, tmp_path, capsys):
        """Test main with invalid TOML files."""
        invalid_file = tmp_path / "invalid.toml"
        invalid_file.write_text('[invalid')

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
        """Test main with no TOML files."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "No TOML files to check" in captured.out

    def test_main_multiple_files(self, tmp_path, capsys):
        """Test main with multiple TOML files."""
        file1 = tmp_path / "file1.toml"
        file1.write_text('[section1]\nkey = "value1"')

        file2 = tmp_path / "file2.toml"
        file2.write_text('[section2]\nkey = "value2"')

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([str(file1), str(file2)])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "All 2 TOML file(s) are valid" in captured.out

    def test_main_pyproject_toml(self, tmp_path, capsys):
        """Test main with typical pyproject.toml structure."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
version = "1.0.0"
dependencies = ["requests>=2.0"]

[tool.ruff]
line-length = 100
""")

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([str(pyproject)])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "Valid TOML" in captured.out

"""Tests for check_yaml tool."""

import pytest
from pathlib import Path

from crackerjack.tools.check_yaml import (
    _UniqueKeyLoader,
    main,
    validate_yaml_file,
)


class TestUniqueKeyLoader:
    """Test YAML unique key loader."""

    def test_valid_yaml(self, tmp_path):
        """Test loading valid YAML."""
        test_file = tmp_path / "valid.yaml"
        test_file.write_text("""
name: test
value: 123
nested:
  key: value
""")

        is_valid, error = validate_yaml_file(test_file)

        assert is_valid is True
        assert error is None

    def test_duplicate_key_detection(self, tmp_path):
        """Test detection of duplicate keys."""
        test_file = tmp_path / "duplicate.yaml"
        test_file.write_text("""
name: test
name: duplicate
""")

        is_valid, error = validate_yaml_file(test_file)

        assert is_valid is False
        assert "Duplicate key" in error

    def test_empty_yaml(self, tmp_path):
        """Test validation of empty YAML file."""
        test_file = tmp_path / "empty.yaml"
        test_file.write_text("")

        is_valid, error = validate_yaml_file(test_file)

        assert is_valid is True
        assert error is None

    def test_yaml_list(self, tmp_path):
        """Test validation of YAML list."""
        test_file = tmp_path / "list.yaml"
        test_file.write_text("""
- item1
- item2
- key: value
""")

        is_valid, error = validate_yaml_file(test_file)

        assert is_valid is True
        assert error is None

    def test_invalid_yaml_syntax(self, tmp_path):
        """Test validation of invalid YAML syntax."""
        test_file = tmp_path / "invalid.yaml"
        test_file.write_text("""
key:
  - item1
  - item2
  - unclosed bracket: [
""")

        is_valid, error = validate_yaml_file(test_file)

        assert is_valid is False
        assert error is not None

    def test_nested_duplicate_keys(self, tmp_path):
        """Test detection of duplicate keys in nested structures."""
        test_file = tmp_path / "nested_dup.yaml"
        test_file.write_text("""
outer:
  inner: value1
  inner: value2
""")

        is_valid, error = validate_yaml_file(test_file)

        assert is_valid is False
        assert "Duplicate key" in error


class TestCheckYamlMain:
    """Test check_yaml main function."""

    def test_main_with_valid_files(self, tmp_path, capsys):
        """Test main with valid YAML files."""
        valid_file = tmp_path / "valid.yaml"
        valid_file.write_text("key: value\nlist:\n  - item")

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([str(valid_file)])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "Valid YAML" in captured.out

    def test_main_with_invalid_files(self, tmp_path, capsys):
        """Test main with invalid YAML files."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("{invalid yaml: ]")

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
        """Test main with no YAML files."""
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "No YAML files to check" in captured.out

    def test_main_yml_extension(self, tmp_path, capsys):
        """Test main with .yml extension."""
        yml_file = tmp_path / "config.yml"
        yml_file.write_text("key: value")

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([str(yml_file)])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "Valid YAML" in captured.out

    def test_main_multiple_files(self, tmp_path, capsys):
        """Test main with multiple YAML files."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value")

        yml_file = tmp_path / "test.yml"
        yml_file.write_text("another: value")

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = main([str(yaml_file), str(yml_file)])
        finally:
            os.chdir(original_cwd)

        captured = capsys.readouterr()
        assert result == 0
        assert "All 2 YAML file(s) are valid" in captured.out

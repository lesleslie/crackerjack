"""Tests for check_toml native tool (Phase 8)."""

import pytest

from crackerjack.tools.check_toml import main, validate_toml_file


class TestTOMLValidation:
    """Test TOML validation logic."""

    def test_validates_simple_toml(self, tmp_path):
        """Test validation of simple TOML."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('key = "value"\n')

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_validates_nested_tables(self, tmp_path):
        """Test validation of nested TOML tables."""
        toml_file = tmp_path / "test.toml"
        content = """
[parent]
key1 = "value1"

[parent.child]
key2 = "value2"

[parent.child.nested]
key3 = "value3"
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_validates_arrays(self, tmp_path):
        """Test validation of TOML arrays."""
        toml_file = tmp_path / "test.toml"
        content = """
items = ["item1", "item2", "item3"]
numbers = [1, 2, 3, 4, 5]

[[array_of_tables]]
name = "first"

[[array_of_tables]]
name = "second"
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_detects_invalid_syntax(self, tmp_path):
        """Test detection of invalid TOML syntax."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('key = "unclosed string\n')

        is_valid, error_msg = validate_toml_file(toml_file)
        assert not is_valid
        assert error_msg is not None

    def test_detects_duplicate_keys(self, tmp_path):
        """Test detection of duplicate keys."""
        toml_file = tmp_path / "test.toml"
        content = """
key = "value1"
key = "value2"
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert not is_valid
        assert error_msg is not None

    def test_detects_invalid_table_syntax(self, tmp_path):
        """Test detection of invalid table syntax."""
        toml_file = tmp_path / "test.toml"
        content = """
[parent]
key = "value"

[parent]
key = "duplicate_table"
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert not is_valid
        assert error_msg is not None

    def test_handles_empty_file(self, tmp_path):
        """Test handling of empty TOML file."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text("")

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid  # Empty TOML is valid
        assert error_msg is None

    def test_handles_comments(self, tmp_path):
        """Test handling of TOML comments."""
        toml_file = tmp_path / "test.toml"
        content = """
# This is a comment
key = "value"  # Inline comment

[section]  # Section comment
nested = "value"
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None


class TestTOMLCLI:
    """Test check_toml CLI interface."""

    def test_cli_help(self):
        """Test --help displays correctly."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0

    def test_cli_no_args_default_behavior(self, tmp_path, monkeypatch):
        """Test CLI with no arguments uses current directory."""
        monkeypatch.chdir(tmp_path)

        # Create test files
        (tmp_path / "test1.toml").write_text('key1 = "value1"\n')
        (tmp_path / "test2.toml").write_text('key2 = "value2"\n')

        # Run main with no args
        exit_code = main([])

        # Should validate both files and return 0
        assert exit_code == 0

    def test_cli_with_file_arguments(self, tmp_path):
        """Test CLI with explicit file arguments."""
        test_file1 = tmp_path / "test1.toml"
        test_file2 = tmp_path / "test2.toml"

        test_file1.write_text('key1 = "value1"\n')
        test_file2.write_text('key2 = "value2"\n')

        exit_code = main([str(test_file1), str(test_file2)])

        assert exit_code == 0  # All files valid

    def test_cli_detects_errors(self, tmp_path):
        """Test CLI detects TOML errors."""
        invalid_file = tmp_path / "invalid.toml"
        invalid_file.write_text('key = "unclosed\n')

        exit_code = main([str(invalid_file)])

        assert exit_code == 1  # Errors found

    def test_cli_no_files_to_check(self, tmp_path, monkeypatch, capsys):
        """Test CLI with no files to check."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        monkeypatch.chdir(empty_dir)

        exit_code = main([])

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "No TOML files to check" in captured.out

    def test_cli_nonexistent_file(self, tmp_path):
        """Test CLI with nonexistent file."""
        exit_code = main([str(tmp_path / "nonexistent.toml")])

        # Should handle gracefully
        assert exit_code == 0  # No files processed

    def test_cli_mixed_valid_and_invalid(self, tmp_path, capsys):
        """Test CLI with mix of valid and invalid files."""
        valid_file = tmp_path / "valid.toml"
        invalid_file = tmp_path / "invalid.toml"

        valid_file.write_text('key = "value"\n')
        invalid_file.write_text('key = "unclosed\n')

        exit_code = main([str(valid_file), str(invalid_file)])

        assert exit_code == 1  # At least one error
        captured = capsys.readouterr()
        assert "✓" in captured.out  # Valid file marked
        assert "✗" in captured.err  # Invalid file marked



class TestTOMLEdgeCases:
    """Test edge cases and error conditions."""

    def test_unicode_content(self, tmp_path):
        """Test handling of Unicode content."""
        toml_file = tmp_path / "test.toml"
        toml_file.write_text('greeting = "你好世界"\n', encoding="utf-8")

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_very_large_toml(self, tmp_path):
        """Test handling of very large TOML files."""
        toml_file = tmp_path / "test.toml"
        # Generate large TOML with 1000 keys
        content = "\n".join([f'key{i} = "value{i}"' for i in range(1000)])
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_deeply_nested_tables(self, tmp_path):
        """Test handling of deeply nested TOML tables."""
        toml_file = tmp_path / "test.toml"
        # Create deeply nested structure
        content = "[root]\n"
        for i in range(10):
            content += f"[root.{'level' + str(i)}]\n"
        content += 'value = "final"\n'
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_multiline_strings(self, tmp_path):
        """Test handling of multiline strings."""
        toml_file = tmp_path / "test.toml"
        content = '''
description = """
This is a multiline
string with multiple
lines of content
"""
'''
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_special_toml_values(self, tmp_path):
        """Test handling of special TOML values."""
        toml_file = tmp_path / "test.toml"
        content = """
bool_true = true
bool_false = false
int_value = 42
float_value = 3.14
date = 1979-05-27T07:32:00Z
array = [1, 2, 3]
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_missing_file(self, tmp_path):
        """Test handling of missing file."""
        missing_file = tmp_path / "nonexistent.toml"

        is_valid, error_msg = validate_toml_file(missing_file)
        assert not is_valid
        assert "Error reading file" in error_msg

    def test_inline_tables(self, tmp_path):
        """Test handling of inline tables."""
        toml_file = tmp_path / "test.toml"
        content = """
person = { name = "John", age = 30 }
point = { x = 1, y = 2 }
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None


class TestTOMLIntegration:
    """Integration tests with real-world scenarios."""

    def test_pyproject_toml(self, tmp_path):
        """Test validation of pyproject.toml."""
        toml_file = tmp_path / "pyproject.toml"
        content = """
[project]
name = "example-project"
version = "0.1.0"
description = "An example project"
authors = [
    {name = "Author Name", email = "author@example.com"}
]
requires-python = ">=3.13"
dependencies = [
    "requests>=2.31.0",
    "pytest>=7.4.0",
]

[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_cargo_toml(self, tmp_path):
        """Test validation of Cargo.toml (Rust)."""
        toml_file = tmp_path / "Cargo.toml"
        content = """
[package]
name = "example"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1.0", features = ["derive"] }
tokio = { version = "1", features = ["full"] }

[dev-dependencies]
criterion = "0.5"
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_config_toml(self, tmp_path):
        """Test validation of application config.toml."""
        toml_file = tmp_path / "config.toml"
        content = """
[server]
host = "0.0.0.0"
port = 8080
workers = 4

[database]
url = "postgresql://localhost/mydb"
max_connections = 10
timeout = 30

[logging]
level = "info"
format = "json"
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

    def test_mixed_file_extensions(self, tmp_path):
        """Test CLI with various TOML files."""
        toml_file1 = tmp_path / "config.toml"
        toml_file2 = tmp_path / "settings.toml"

        toml_file1.write_text('key1 = "value1"\n')
        toml_file2.write_text('key2 = "value2"\n')

        exit_code = main([str(toml_file1), str(toml_file2)])

        assert exit_code == 0  # Both files valid

    def test_dotted_keys(self, tmp_path):
        """Test validation of dotted keys."""
        toml_file = tmp_path / "test.toml"
        content = """
name = "Orange"
physical.color = "orange"
physical.shape = "round"
site."google.com" = true
"""
        toml_file.write_text(content)

        is_valid, error_msg = validate_toml_file(toml_file)
        assert is_valid
        assert error_msg is None

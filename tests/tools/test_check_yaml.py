"""Tests for check_yaml native tool (Phase 8)."""

import pytest

from crackerjack.tools.check_yaml import main, validate_yaml_file


class TestYAMLValidation:
    """Test YAML validation logic."""

    def test_validates_simple_yaml(self, tmp_path):
        """Test validation of simple YAML."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value\n")

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_validates_nested_yaml(self, tmp_path):
        """Test validation of nested YAML."""
        yaml_file = tmp_path / "test.yaml"
        content = """
parent:
  child1: value1
  child2: value2
  nested:
    key: value
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_validates_list_yaml(self, tmp_path):
        """Test validation of YAML with lists."""
        yaml_file = tmp_path / "test.yaml"
        content = """
items:
  - item1
  - item2
  - item3
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_detects_invalid_indentation(self, tmp_path):
        """Test detection of invalid indentation."""
        yaml_file = tmp_path / "test.yaml"
        content = """
parent:
child: value
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert not is_valid
        assert error_msg is not None

    def test_detects_invalid_syntax(self, tmp_path):
        """Test detection of invalid YAML syntax."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: [unclosed array\n")

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert not is_valid
        assert error_msg is not None

    def test_detects_duplicate_keys(self, tmp_path):
        """Test detection of duplicate keys."""
        yaml_file = tmp_path / "test.yaml"
        content = """
key: value1
key: value2
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert not is_valid
        assert error_msg is not None

    def test_handles_empty_file(self, tmp_path):
        """Test handling of empty YAML file."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("")

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid  # Empty YAML is valid
        assert error_msg is None

    def test_handles_comments(self, tmp_path):
        """Test handling of YAML comments."""
        yaml_file = tmp_path / "test.yaml"
        content = """
# This is a comment
key: value  # Inline comment
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None


class TestYAMLCLI:
    """Test check_yaml CLI interface."""

    def test_cli_help(self):
        """Test --help displays correctly."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0

    def test_cli_no_args_default_behavior(self, tmp_path, monkeypatch):
        """Test CLI with no arguments uses current directory."""
        monkeypatch.chdir(tmp_path)

        # Create test files
        (tmp_path / "test1.yaml").write_text("key1: value1\n")
        (tmp_path / "test2.yml").write_text("key2: value2\n")

        # Run main with no args
        exit_code = main([])

        # Should validate both files and return 0
        assert exit_code == 0

    def test_cli_with_file_arguments(self, tmp_path):
        """Test CLI with explicit file arguments."""
        test_file1 = tmp_path / "test1.yaml"
        test_file2 = tmp_path / "test2.yaml"

        test_file1.write_text("key1: value1\n")
        test_file2.write_text("key2: value2\n")

        exit_code = main([str(test_file1), str(test_file2)])

        assert exit_code == 0  # All files valid

    def test_cli_detects_errors(self, tmp_path):
        """Test CLI detects YAML errors."""
        invalid_file = tmp_path / "invalid.yaml"
        invalid_file.write_text("key: [unclosed\n")

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
        assert "No YAML files to check" in captured.out

    def test_cli_nonexistent_file(self, tmp_path):
        """Test CLI with nonexistent file."""
        exit_code = main([str(tmp_path / "nonexistent.yaml")])

        # Should handle gracefully
        assert exit_code == 0  # No files processed

    def test_cli_mixed_valid_and_invalid(self, tmp_path, capsys):
        """Test CLI with mix of valid and invalid files."""
        valid_file = tmp_path / "valid.yaml"
        invalid_file = tmp_path / "invalid.yaml"

        valid_file.write_text("key: value\n")
        invalid_file.write_text("key: [unclosed\n")

        exit_code = main([str(valid_file), str(invalid_file)])

        assert exit_code == 1  # At least one error
        captured = capsys.readouterr()
        assert "✓" in captured.out  # Valid file marked
        assert "✗" in captured.err  # Invalid file marked

    def test_cli_unsafe_flag(self, tmp_path):
        """Test --unsafe flag (currently doesn't change behavior)."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("key: value\n")

        # Should work with --unsafe flag
        exit_code = main(["--unsafe", str(yaml_file)])
        assert exit_code == 0


class TestYAMLEdgeCases:
    """Test edge cases and error conditions."""

    def test_unicode_content(self, tmp_path):
        """Test handling of Unicode content."""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text("greeting: 你好世界\n", encoding="utf-8")

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_very_large_yaml(self, tmp_path):
        """Test handling of very large YAML files."""
        yaml_file = tmp_path / "test.yaml"
        # Generate large YAML with 1000 keys
        content = "\n".join([f"key{i}: value{i}" for i in range(1000)])
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_deeply_nested_yaml(self, tmp_path):
        """Test handling of deeply nested YAML."""
        yaml_file = tmp_path / "test.yaml"
        # Create deeply nested structure
        content = "root:\n"
        indent = "  "
        for i in range(10):
            content += f"{indent * (i + 1)}level{i}:\n"
        content += f"{indent * 11}value: final\n"
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_multiline_strings(self, tmp_path):
        """Test handling of multiline strings."""
        yaml_file = tmp_path / "test.yaml"
        content = """
description: |
  This is a multiline
  string with multiple
  lines of content
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_yaml_anchors_and_aliases(self, tmp_path):
        """Test handling of YAML anchors and aliases."""
        yaml_file = tmp_path / "test.yaml"
        content = """
default: &default_settings
  timeout: 30
  retries: 3

production:
  <<: *default_settings
  timeout: 60
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_special_yaml_values(self, tmp_path):
        """Test handling of special YAML values."""
        yaml_file = tmp_path / "test.yaml"
        content = """
null_value: null
true_value: true
false_value: false
int_value: 42
float_value: 3.14
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_missing_file(self, tmp_path):
        """Test handling of missing file."""
        missing_file = tmp_path / "nonexistent.yaml"

        is_valid, error_msg = validate_yaml_file(missing_file)
        assert not is_valid
        assert "Error reading file" in error_msg


class TestYAMLIntegration:
    """Integration tests with real-world scenarios."""

    def test_github_actions_workflow(self, tmp_path):
        """Test validation of GitHub Actions workflow."""
        yaml_file = tmp_path / "workflow.yml"
        content = """
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: pytest
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_docker_compose_file(self, tmp_path):
        """Test validation of docker-compose.yml."""
        yaml_file = tmp_path / "docker-compose.yml"
        content = """
version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - ./html:/usr/share/nginx/html
  db:
    image: postgres:13
    environment:
      POSTGRES_PASSWORD: secret
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_kubernetes_manifest(self, tmp_path):
        """Test validation of Kubernetes manifest."""
        yaml_file = tmp_path / "deployment.yaml"
        content = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 3
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:1.14.2
        ports:
        - containerPort: 80
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_pre_commit_config(self, tmp_path):
        """Test validation of .pre-commit-config.yaml."""
        yaml_file = tmp_path / ".pre-commit-config.yaml"
        content = """
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.0.1
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
"""
        yaml_file.write_text(content)

        is_valid, error_msg = validate_yaml_file(yaml_file)
        assert is_valid
        assert error_msg is None

    def test_mixed_file_extensions(self, tmp_path):
        """Test CLI with .yaml and .yml files."""
        yaml_file = tmp_path / "test.yaml"
        yml_file = tmp_path / "test.yml"

        yaml_file.write_text("key1: value1\n")
        yml_file.write_text("key2: value2\n")

        exit_code = main([str(yaml_file), str(yml_file)])

        assert exit_code == 0  # Both files valid

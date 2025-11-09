"""Tests for the check-ast tool implementation."""

import tempfile
from pathlib import Path

from crackerjack.tools.check_ast import validate_ast_file, main


def test_validate_ast_file_valid_syntax():
    """Test that validate_ast_file returns True for valid Python syntax."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def hello():\n    print('Hello, world!')\n")
        f.flush()
        file_path = Path(f.name)

    try:
        is_valid, error_msg = validate_ast_file(file_path)
        assert is_valid is True
        assert error_msg is None
    finally:
        file_path.unlink()


def test_validate_ast_file_invalid_syntax():
    """Test that validate_ast_file returns False for invalid Python syntax."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("def hello(\n    print('Hello, world!')\n")  # Missing closing parenthesis
        f.flush()
        file_path = Path(f.name)

    try:
        is_valid, error_msg = validate_ast_file(file_path)
        assert is_valid is False
        assert error_msg is not None
        assert "Syntax error" in error_msg
    finally:
        file_path.unlink()


def test_main_with_valid_file():
    """Test main function with a file that has valid AST."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("x = 1\ny = 2\n")
        f.flush()
        file_path = Path(f.name)

    try:
        result = main([str(file_path)])
        assert result == 0  # Success exit code
    finally:
        file_path.unlink()


def test_main_with_invalid_file():
    """Test main function with a file that has invalid AST."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("if True:\n    x =\n")  # Invalid syntax
        f.flush()
        file_path = Path(f.name)

    try:
        result = main([str(file_path)])
        assert result == 1  # Error exit code
    finally:
        file_path.unlink()


def test_main_with_multiple_files():
    """Test main function with multiple files."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f1:
        f1.write("x = 1\n")
        f1.flush()
        file1_path = Path(f1.name)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f2:
        f2.write("y =\n")  # Invalid syntax
        f2.flush()
        file2_path = Path(f2.name)

    try:
        result = main([str(file1_path), str(file2_path)])
        assert result == 1  # Error exit code due to invalid file
    finally:
        file1_path.unlink()
        file2_path.unlink()


def test_main_with_nonexistent_file():
    """Test main function with a nonexistent file."""
    nonexistent_path = Path("/nonexistent/file.py")
    result = main([str(nonexistent_path)])
    assert result == 0  # Should not error if no files provided

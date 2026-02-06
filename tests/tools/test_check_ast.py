"""Tests for check_ast tool."""

import tempfile
from pathlib import Path

from crackerjack.tools.check_ast import validate_ast_file


def test_check_ast_valid_python():
    """Test check_ast with valid Python code."""
    valid_code = """
def hello_world():
    print("Hello, world!")
    return True
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(valid_code)
        f.flush()

    try:
        result, error = validate_ast_file(Path(f.name))
        assert result, "Valid Python should return True"
        assert error is None, f"Should not have error: {error}"
    finally:
        Path(f.name).unlink()


def test_check_ast_invalid_python():
    """Test check_ast with invalid Python code."""
    invalid_code = """
def hello_world(
    print("Hello, world!")
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(invalid_code)
        f.flush()

    try:
        result, error = validate_ast_file(Path(f.name))
        assert not result, "Invalid Python should return False"
        assert error is not None, "Should have error message"
    finally:
        Path(f.name).unlink()


def test_check_ast_empty_file():
    """Test check_ast with empty file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        pass  # Empty file

    try:
        result, error = validate_ast_file(Path(f.name))
        assert result, "Empty Python file should be valid"
        assert error is None
    finally:
        Path(f.name).unlink()

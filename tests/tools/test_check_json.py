"""Tests for check_json tool."""

import json
import tempfile
from pathlib import Path

from crackerjack.tools.check_json import validate_json_file


def test_check_json_valid():
    """Test check_json with valid JSON."""
    valid_json = '{"name": "test", "value": 123}'
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(valid_json)

    try:
        result, error = validate_json_file(Path(f.name))
        assert result, "Valid JSON should return True"
        assert error is None, f"Should not have error: {error}"
    finally:
        Path(f.name).unlink()


def test_check_json_invalid():
    """Test check_json with invalid JSON."""
    invalid_json = '{"name": "test", value: 123}'  # Missing quotes
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(invalid_json)

    try:
        result, error = validate_json_file(Path(f.name))
        assert not result, "Invalid JSON should return False"
        assert error is not None, "Should have error message"
    finally:
        Path(f.name).unlink()


def test_check_json_empty_file():
    """Test check_json with empty file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        pass  # Empty file

    try:
        result, error = validate_json_file(Path(f.name))
        assert not result, "Empty JSON file should fail"
        assert error is not None, "Should have error message"
    finally:
        Path(f.name).unlink()


def test_check_json_complex():
    """Test check_json with complex nested JSON."""
    complex_json = {
        "users": [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25}
        ],
        "metadata": {"version": "1.0", "count": 2}
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(json.dumps(complex_json))

    try:
        result, error = validate_json_file(Path(f.name))
        assert result, "Complex JSON should be valid"
        assert error is None
    finally:
        Path(f.name).unlink()

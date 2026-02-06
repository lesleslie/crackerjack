"""Tests for format_json tool."""

import json
import tempfile
from pathlib import Path

from crackerjack.tools.format_json import format_json_file


def test_format_json_valid():
    """Test format_json with valid JSON that needs formatting."""
    # Create JSON with poor formatting
    poorly_formatted = '{"name":"test","value":123,"nested":{"key":"val"}}'
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(poorly_formatted)

    try:
        result, error = format_json_file(Path(f.name))
        assert result, "Formatting should succeed"
        assert error is None, f"Should not have error: {error}"

        # Verify the file was properly formatted
        with Path(f.name).open(encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)

        # Should be properly formatted with indent=2 and sorted keys
        assert data["name"] == "test"
        assert data["value"] == 123
        assert data["nested"]["key"] == "val"
    finally:
        Path(f.name).unlink()


def test_format_json_empty_file():
    """Test format_json with empty file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        pass  # Empty file

    try:
        result, error = format_json_file(Path(f.name))
        assert result, "Empty file should succeed"
        assert error == "File is empty, nothing to format"
    finally:
        Path(f.name).unlink()


def test_format_json_invalid():
    """Test format_json with invalid JSON."""
    invalid_json = '{"name": "test", value: 123}'  # Missing quotes
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(invalid_json)

    try:
        result, error = format_json_file(Path(f.name))
        assert not result, "Invalid JSON should fail"
        assert error is not None, "Should have error message"
        assert "Invalid JSON syntax" in error
    finally:
        Path(f.name).unlink()


def test_format_json_already_formatted():
    """Test format_json with already properly formatted JSON."""
    already_formatted = '{\n  "key": "value",\n  "number": 42\n}\n'
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write(already_formatted)

    try:
        result, error = format_json_file(Path(f.name))
        assert result, "Already formatted JSON should succeed"
        assert error is None, "Should not have error"

        # Verify it's still properly formatted
        with Path(f.name).open(encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)

        assert data["key"] == "value"
        assert data["number"] == 42
    finally:
        Path(f.name).unlink()


def test_format_json_complex():
    """Test format_json with complex nested JSON."""
    complex_json = {
        "users": [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25}
        ],
        "metadata": {"version": "1.0", "count": 2},
        "active": True,
        "items": None
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        # Write with poor formatting
        f.write(json.dumps(complex_json, separators=(',', ':')))

    try:
        result, error = format_json_file(Path(f.name))
        assert result, "Complex JSON should format successfully"
        assert error is None, "Should not have error"

        # Verify content is preserved
        with Path(f.name).open(encoding='utf-8') as f:
            content = f.read()
            data = json.loads(content)

        assert data["users"][0]["name"] == "Alice"
        assert data["users"][0]["age"] == 30
        assert data["metadata"]["version"] == "1.0"
        assert data["active"] is True
        assert data["items"] is None
    finally:
        Path(f.name).unlink()

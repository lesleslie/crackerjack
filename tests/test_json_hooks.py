"""Tests for the JSON validation tools."""

import tempfile
from pathlib import Path

from crackerjack.tools.check_json import validate_json_file, main as check_json_main
from crackerjack.tools.format_json import format_json_file, main as format_json_main


def test_validate_json_file_valid():
    """Test that validate_json_file returns True for valid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"name": "test", "value": 123}')
        f.flush()
        file_path = Path(f.name)

    try:
        is_valid, error_msg = validate_json_file(file_path)
        assert is_valid is True
        assert error_msg is None
    finally:
        file_path.unlink()


def test_validate_json_file_invalid():
    """Test that validate_json_file returns False for invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"name": "test", "value": }')  # Invalid JSON
        f.flush()
        file_path = Path(f.name)

    try:
        is_valid, error_msg = validate_json_file(file_path)
        assert is_valid is False
        assert error_msg is not None
        # The error message should contain information about the parsing issue
        assert "line" in error_msg.lower() or "char" in error_msg.lower() or "expecting" in error_msg.lower()
    finally:
        file_path.unlink()


def test_format_json_file_valid():
    """Test that format_json_file formats JSON correctly."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"name":"test","value":123}')  # Unformatted JSON
        f.flush()
        file_path = Path(f.name)

    try:
        # Read initial content to compare
        with open(file_path, "r") as fr:
            initial_content = fr.read()

        # Format the file
        success, error_msg = format_json_file(file_path)
        assert success is True
        assert error_msg is None

        # Check that it was formatted (has whitespace/indentation)
        with open(file_path, "r") as fr:
            formatted_content = fr.read()

        # The formatted content should be different (more whitespace) but still valid
        assert formatted_content != initial_content
    finally:
        file_path.unlink()


def test_format_json_file_invalid():
    """Test that format_json_file returns False for invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"name": "test", "value": }')  # Invalid JSON
        f.flush()
        file_path = Path(f.name)

    try:
        success, error_msg = format_json_file(file_path)
        assert success is False
        assert error_msg is not None
    finally:
        file_path.unlink()


def test_check_json_main_valid():
    """Test check-json main with valid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"valid": "json"}')
        f.flush()
        file_path = Path(f.name)

    try:
        result = check_json_main([str(file_path)])
        assert result == 0  # Success exit code
    finally:
        file_path.unlink()


def test_check_json_main_invalid():
    """Test check-json main with invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"invalid": json}')  # Invalid JSON
        f.flush()
        file_path = Path(f.name)

    try:
        result = check_json_main([str(file_path)])
        assert result == 1  # Error exit code
    finally:
        file_path.unlink()


def test_format_json_main_valid():
    """Test format-json main with valid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"formatted":"json"}')
        f.flush()
        file_path = Path(f.name)

    try:
        result = format_json_main([str(file_path)])
        assert result == 0  # Success exit code
    finally:
        file_path.unlink()


def test_format_json_main_invalid():
    """Test format-json main with invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write('{"invalid": json}')  # Invalid JSON
        f.flush()
        file_path = Path(f.name)

    try:
        result = format_json_main([str(file_path)])
        assert result == 1  # Error exit code
    finally:
        file_path.unlink()

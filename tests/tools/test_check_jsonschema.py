"""Tests for check_jsonschema tool."""

import json
import tempfile
from pathlib import Path

from crackerjack.tools.check_jsonschema import (
    find_schema_for_json,
    load_schema,
    validate_json_against_schema,
)


def test_find_schema_filename_pattern():
    """Test finding schema with filename pattern (file.schema.json)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create JSON file
        json_file = tmpdir / "config.json"
        json_file.write_text('{"key": "value"}')

        # Create schema file with filename pattern
        schema_file = tmpdir / "config.schema.json"
        schema_file.write_text('{"type": "object"}')

        result = find_schema_for_json(json_file)
        assert result == schema_file, "Should find schema with filename pattern"


def test_find_schema_internal_ref():
    """Test finding schema via $schema reference in JSON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create JSON file with $schema reference
        json_file = tmpdir / "config.json"
        json_file.write_text('{"$schema": "schema.json", "key": "value"}')

        # Create referenced schema
        schema_file = tmpdir / "schema.json"
        schema_file.write_text('{"type": "object"}')

        result = find_schema_for_json(json_file)
        assert result == schema_file, "Should find schema via $schema reference"


def test_find_schema_same_directory():
    """Test finding schema.json in same directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create JSON file
        json_file = tmpdir / "config.json"
        json_file.write_text('{"key": "value"}')

        # Create schema.json in same directory
        schema_file = tmpdir / "schema.json"
        schema_file.write_text('{"type": "object"}')

        result = find_schema_for_json(json_file)
        assert result == schema_file, "Should find schema.json in same directory"


def test_find_schema_parent_directory():
    """Test finding schema.json in parent directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create subdirectory with JSON file
        subdir = tmpdir / "subdir"
        subdir.mkdir()

        json_file = subdir / "config.json"
        json_file.write_text('{"key": "value"}')

        # Create schema.json in parent directory
        schema_file = tmpdir / "schema.json"
        schema_file.write_text('{"type": "object"}')

        result = find_schema_for_json(json_file)
        assert result == schema_file, "Should find schema.json in parent directory"


def test_find_schema_not_found():
    """Test when no schema is found."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create JSON file without any schema
        json_file = tmpdir / "config.json"
        json_file.write_text('{"key": "value"}')

        result = find_schema_for_json(json_file)
        assert result is None, "Should return None when no schema found"


def test_load_schema_valid():
    """Test loading a valid schema."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"type": "object", "properties": {"key": {"type": "string"}}}, f)
        schema_path = Path(f.name)

    try:
        result = load_schema(schema_path)
        assert result is not None, "Should load valid schema"
        assert result["type"] == "object"
        assert "properties" in result
    finally:
        schema_path.unlink()


def test_load_schema_invalid_json():
    """Test loading schema with invalid JSON."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"invalid": }')  # Invalid JSON
        schema_path = Path(f.name)

    try:
        result = load_schema(schema_path)
        assert result is None, "Should return None for invalid JSON"
    finally:
        schema_path.unlink()


def test_load_schema_not_dict():
    """Test loading schema that is not a dict (e.g., array)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(["item1", "item2"], f)  # Array instead of dict
        schema_path = Path(f.name)

    try:
        result = load_schema(schema_path)
        assert result is None, "Should return None for non-dict schema"
    finally:
        schema_path.unlink()


def test_validate_json_valid_against_schema():
    """Test validating valid JSON against schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create schema
        schema_path = tmpdir / "schema.json"
        schema_path.write_text('{"type": "object", "properties": {"name": {"type": "string"}}}')

        # Create valid JSON
        json_path = tmpdir / "data.json"
        json_path.write_text('{"name": "Alice"}')

        is_valid, error = validate_json_against_schema(json_path, schema_path)
        assert is_valid, "Valid JSON should pass validation"
        assert error is None, f"Should not have error: {error}"


def test_validate_json_invalid_against_schema():
    """Test validating invalid JSON against schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create schema requiring string name
        schema_path = tmpdir / "schema.json"
        schema_path.write_text('{"type": "object", "properties": {"name": {"type": "string"}}}')

        # Create invalid JSON (name is number, not string)
        json_path = tmpdir / "data.json"
        json_path.write_text('{"name": 123}')

        is_valid, error = validate_json_against_schema(json_path, schema_path)
        assert not is_valid, "Invalid JSON should fail validation"
        assert error is not None, "Should have error message"
        assert "Schema validation failed" in error


def test_validate_json_invalid_json_file():
    """Test validating file with invalid JSON syntax."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create schema
        schema_path = tmpdir / "schema.json"
        schema_path.write_text('{"type": "object"}')

        # Create file with invalid JSON
        json_path = tmpdir / "data.json"
        json_path.write_text('{"invalid": }')

        is_valid, error = validate_json_against_schema(json_path, schema_path)
        # The function returns False for invalid JSON, with error message
        assert not is_valid, "Invalid JSON should fail validation"
        assert error is not None, "Should have error message"
        # Error could be either "Invalid JSON in file" or "Invalid JSON syntax"
        assert "Invalid JSON" in error or "JSONDecodeError" in error or "Expecting" in error


def test_validate_json_invalid_schema():
    """Test validating against an invalid schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create invalid schema
        schema_path = tmpdir / "schema.json"
        schema_path.write_text('{"type": "invalid_type"}')

        # Create valid JSON
        json_path = tmpdir / "data.json"
        json_path.write_text('{"name": "Alice"}')

        is_valid, error = validate_json_against_schema(json_path, schema_path)
        assert not is_valid, "Invalid schema should cause failure"
        assert error is not None, "Should have error message"
        assert "Invalid schema" in error


def test_validate_json_complex_schema():
    """Test validating against complex nested schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create complex schema
        schema = {
            "type": "object",
            "properties": {
                "users": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "number"}
                        },
                        "required": ["name"]
                    }
                }
            }
        }
        schema_path = tmpdir / "schema.json"
        schema_path.write_text(json.dumps(schema))

        # Create valid JSON matching schema
        data = {
            "users": [
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]
        }
        json_path = tmpdir / "data.json"
        json_path.write_text(json.dumps(data))

        is_valid, error = validate_json_against_schema(json_path, schema_path)
        assert is_valid, "Valid complex JSON should pass validation"
        assert error is None

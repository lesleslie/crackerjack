"""Validate JSON files against JSON Schema definitions.

This tool is a native Python implementation for validating JSON files
against their corresponding JSON Schema definitions. It automatically
finds .json files and attempts to validate them against similarly named
.schema.json or .json files that follow the JSON Schema standard.

Usage:
    python -m crackerjack.tools.check_jsonschema [files...]

Exit Codes:
    0: All JSON files are valid against their schemas
    1: One or more JSON files fail schema validation
"""

from __future__ import annotations

import argparse
import json
import sys
import typing as t
from pathlib import Path

from ._git_utils import get_files_by_extension

if t.TYPE_CHECKING:
    pass


def _check_filename_pattern_schema(json_file: Path) -> Path | None:
    """Check for {name}.schema.json pattern."""
    schema_path = json_file.with_name(f"{json_file.stem}.schema.json")
    if schema_path.is_file():
        return schema_path
    return None


def _resolve_local_schema_path(json_file: Path, schema_ref: str) -> Path | None:
    """Resolve a local schema file path.

    Args:
        json_file: The JSON file containing the schema reference
        schema_ref: The schema reference string

    Returns:
        Path to schema file if found, None otherwise
    """
    if schema_ref.endswith((".json", ".schema.json")):
        schema_path = json_file.parent / schema_ref
        if schema_path.is_file():
            return schema_path
    return None


def _check_internal_schema_ref(json_file: Path) -> Path | None:
    """Try to find a schema reference inside the JSON file."""
    try:
        with json_file.open(encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            schema_ref = data.get("$schema")
            if schema_ref and isinstance(schema_ref, str):
                return _resolve_local_schema_path(json_file, schema_ref)
    except (OSError, json.JSONDecodeError):
        pass
    return None


def _check_same_dir_schema(json_file: Path) -> Path | None:
    """Try schema.json in the same directory."""
    schema_path = json_file.with_name("schema.json")
    if schema_path.is_file():
        return schema_path
    return None


def _check_parent_dir_schemas(json_file: Path) -> Path | None:
    """Try finding schema.json in parent directories (up to 3 levels)."""
    current_dir = json_file.parent
    for _ in range(3):
        schema_path = current_dir / "schema.json"
        if schema_path.is_file():
            return schema_path
        if current_dir.parent == current_dir:  # reached root
            break
        current_dir = current_dir.parent
    return None


def find_schema_for_json(json_file: Path) -> Path | None:
    """Find the corresponding schema file for a JSON file.

    Looks for schema files in common patterns:
    - {name}.schema.json
    - {name}.json (if it contains $schema reference)
    - schema.json in the same directory
    - schema.json in parent directories

    Args:
        json_file: Path to the JSON file to validate

    Returns:
        Path to schema file, or None if not found
    """
    # Try {name}.schema.json pattern
    result = _check_filename_pattern_schema(json_file)
    if result:
        return result

    # Try to find a schema reference inside the JSON file
    result = _check_internal_schema_ref(json_file)
    if result:
        return result

    # Try schema.json in the same directory
    result = _check_same_dir_schema(json_file)
    if result:
        return result

    # Try finding schema.json in parent directories (up to 3 levels)
    return _check_parent_dir_schemas(json_file)


def load_schema(schema_path: Path) -> dict[str, t.Any] | None:
    """Load a JSON schema from file.

    Args:
        schema_path: Path to the schema file

    Returns:
        Schema as dictionary, or None if loading fails
    """
    try:
        with schema_path.open(encoding="utf-8") as f:
            schema = json.load(f)

        # Basic validation that this looks like a schema
        if not isinstance(schema, dict):
            return None

        return schema
    except (OSError, json.JSONDecodeError) as e:
        print(f"Could not load schema {schema_path}: {e}", file=sys.stderr)  # noqa: T201
        return None


def validate_json_against_schema(
    json_file: Path, schema_path: Path
) -> tuple[bool, str | None]:
    """Validate a JSON file against a schema.

    Args:
        json_file: Path to the JSON file to validate
        schema_path: Path to the schema file

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if file validates against schema
        - error_message: Error description if is_valid is False, None otherwise
    """
    try:
        # Load schema
        schema = load_schema(schema_path)
        if not schema:
            return False, f"Could not load schema: {schema_path}"

        # Load JSON data
        with json_file.open(encoding="utf-8") as f:
            data = json.load(f)

        # Import jsonschema only when needed to avoid dependency issues
        import jsonschema

        # Validate the data against the schema
        validator_class = jsonschema.Draft7Validator
        if hasattr(validator_class, "check_schema"):
            # Validate the schema itself first
            validator_class.check_schema(schema)

        validator = validator_class(schema)
        errors = list(validator.iter_errors(data))

        if errors:
            error_messages = [
                f"  {error.message}" for error in errors[:5]
            ]  # Limit to first 5 errors
            if len(errors) > 5:
                error_messages.append(f"  ... and {len(errors) - 5} more errors")
            return False, "Schema validation failed:\n" + "\n".join(error_messages)

        return True, None

    except ImportError:
        return (
            False,
            "jsonschema library not available. Install with: pip install jsonschema",
        )
    except jsonschema.SchemaError as e:
        return False, f"Invalid schema: {e}"
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in file: {e}"
    except Exception as e:
        return False, f"Validation error: {e}"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate JSON files against JSON Schema definitions"
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="JSON files to validate against schemas (default: all .json files)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if no schema is found for a JSON file",
    )

    return parser.parse_args(argv)


def _get_json_files(args: argparse.Namespace) -> list[Path]:
    """Get list of JSON files to validate."""
    if not args.files:
        # Get all tracked JSON files (respects .gitignore via git ls-files)
        files = get_files_by_extension([".json"])
        if not files:
            # Fallback to rglob if not in git repo
            files = list(Path.cwd().rglob("*.json"))
    else:
        files = args.files

    # Filter to existing files only
    return [f for f in files if f.is_file()]


def _process_file(file_path: Path, schema_path: Path | None, strict: bool) -> int:
    """Process a single file and return error count increment."""
    if not schema_path:
        if strict:
            print(f"✗ {file_path}: No schema found", file=sys.stderr)  # noqa: T201
            return 1
        else:
            print(f"→ {file_path}: No schema found, skipping validation")  # noqa: T201
            return 0

    is_valid, error_msg = validate_json_against_schema(file_path, schema_path)

    if not is_valid:
        print(f"✗ {file_path}: {error_msg}", file=sys.stderr)  # noqa: T201
        return 1
    else:
        print(f"✓ {file_path}: Valid against {schema_path.name}")  # noqa: T201
        return 0


def main(argv: list[str] | None = None) -> int:
    """Main entry point for check-jsonschema tool.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code: 0 if all JSON files validate against schemas, 1 if any errors found
    """
    args = _parse_args(argv)

    files = _get_json_files(args)

    if not files:
        print("No JSON files to validate")  # noqa: T201
        return 0

    # Process files
    error_count = 0
    for file_path in files:
        schema_path = find_schema_for_json(file_path)
        error_count += _process_file(file_path, schema_path, args.strict)

    # Return appropriate exit code
    if error_count > 0:
        print(f"\n{error_count} JSON file(s) failed schema validation", file=sys.stderr)  # noqa: T201
        return 1

    print(
        f"\nAll {len([f for f in files if find_schema_for_json(f)])} JSON file(s) passed schema validation"
    )  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

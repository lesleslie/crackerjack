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
    schema_path = json_file.with_name(f"{json_file.stem}.schema.json")
    if schema_path.is_file():
        return schema_path
    return None


def _resolve_local_schema_path(json_file: Path, schema_ref: str) -> Path | None:
    if schema_ref.endswith((".json", ".schema.json")):
        schema_path = json_file.parent / schema_ref
        if schema_path.is_file():
            return schema_path
    return None


def _check_internal_schema_ref(json_file: Path) -> Path | None:
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
    schema_path = json_file.with_name("schema.json")
    if schema_path.is_file():
        return schema_path
    return None


def _check_parent_dir_schemas(json_file: Path) -> Path | None:
    current_dir = json_file.parent
    for _ in range(3):
        schema_path = current_dir / "schema.json"
        if schema_path.is_file():
            return schema_path
        if current_dir.parent == current_dir:
            break
        current_dir = current_dir.parent
    return None


def find_schema_for_json(json_file: Path) -> Path | None:
    result = _check_filename_pattern_schema(json_file)
    if result:
        return result

    result = _check_internal_schema_ref(json_file)
    if result:
        return result

    result = _check_same_dir_schema(json_file)
    if result:
        return result

    return _check_parent_dir_schemas(json_file)


def load_schema(schema_path: Path) -> dict[str, t.Any] | None:
    try:
        with schema_path.open(encoding="utf-8") as f:
            schema = json.load(f)

        if not isinstance(schema, dict):
            return None

        return schema
    except (OSError, json.JSONDecodeError) as e:
        print(f"Could not load schema {schema_path}: {e}", file=sys.stderr)  # noqa: T201
        return None


def validate_json_against_schema(
    json_file: Path, schema_path: Path
) -> tuple[bool, str | None]:
    try:
        schema = load_schema(schema_path)
        if not schema:
            return False, f"Could not load schema: {schema_path}"

        with json_file.open(encoding="utf-8") as f:
            data = json.load(f)

        import jsonschema

        validator_class = jsonschema.Draft7Validator
        if hasattr(validator_class, "check_schema"):
            validator_class.check_schema(schema)

        validator = validator_class(schema)
        errors = list(validator.iter_errors(data))

        if errors:
            error_messages = [f" {error.message}" for error in errors[:5]]
            if len(errors) > 5:
                error_messages.append(f" ... and {len(errors) - 5} more errors")
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
    if not args.files:
        files = get_files_by_extension([".json"])
        if not files:
            files = list(Path.cwd().rglob("*.json"))
    else:
        files = args.files

    return [f for f in files if f.is_file()]


def _process_file(file_path: Path, schema_path: Path | None, strict: bool) -> int:
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
    args = _parse_args(argv)

    files = _get_json_files(args)

    if not files:
        print("No JSON files to validate")  # noqa: T201
        return 0

    error_count = 0
    for file_path in files:
        schema_path = find_schema_for_json(file_path)
        error_count += _process_file(file_path, schema_path, args.strict)

    if error_count > 0:
        print(f"\n{error_count} JSON file(s) failed schema validation", file=sys.stderr)  # noqa: T201
        return 1

    print(
        f"\nAll {len([f for f in files if find_schema_for_json(f)])} JSON file(s) passed schema validation"
    )  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import argparse
import json
import sys
import typing as t
from contextlib import suppress
from pathlib import Path

from ._git_utils import get_files_by_extension


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
    with suppress(OSError, json.JSONDecodeError):
        with json_file.open(encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            schema_ref = data.get("$schema")
            if schema_ref and isinstance(schema_ref, str):
                return _resolve_local_schema_path(json_file, schema_ref)
    return None


def _check_same_dir_schema(json_file: Path) -> Path | None:
    schema_path = json_file.with_name("schema.json")
    if schema_path.is_file() and schema_path != json_file:
        return schema_path
    return None


def _check_parent_dir_schemas(json_file: Path) -> Path | None:
    current_dir = json_file.parent
    for _ in range(3):
        schema_path = current_dir / "schema.json"
        if schema_path.is_file() and schema_path != json_file:
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
    json_file: Path,
    schema_path: Path,
) -> tuple[bool, str | None]:
    import jsonschema

    try:
        schema = load_schema(schema_path)
        if not schema:
            return False, f"Could not load schema: {schema_path}"

        with json_file.open(encoding="utf-8") as f:
            data = json.load(f)

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
        description="Validate JSON files against JSON Schema definitions",
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
    # Supports both --output-format=json (crackerjack convention) and
    # -o json (mimics the check-jsonschema CLI convention). Defaults to
    # text so existing pre-commit invocations behave unchanged.
    parser.add_argument(
        "--output-format",
        "-o",
        choices=("text", "json"),
        default="text",
        help="Output format (default: text)",
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


def _process_file(
    file_path: Path,
    schema_path: Path | None,
    strict: bool,
    json_mode: bool,
) -> tuple[int, list[dict[str, t.Any]]]:
    """Validate a single file. Returns (exit_code, errors_list)."""
    if not schema_path:
        if strict:
            if not json_mode:
                print(  # noqa: T201
                    f"✗ {file_path}: No schema found",
                    file=sys.stderr,
                )
            else:
                print(  # noqa: T201
                    json.dumps(
                        {
                            "success": False,
                            "errors": [
                                {
                                    "path": "",
                                    "message": f"No schema found for {file_path}",
                                    "validator": "schema_lookup",
                                }
                            ],
                            "files": [{"path": str(file_path), "valid": False}],
                        }
                    )
                )
            return 1, []
        if not json_mode:
            print(f"→ {file_path}: No schema found, skipping validation")  # noqa: T201
        return 0, []

    is_valid, error_msg = validate_json_against_schema(file_path, schema_path)

    if not is_valid:
        if json_mode:
            # Re-run validation to harvest structured errors. validate_json_against_schema
            # already iterates validator.iter_errors; we just collect them here.
            structured_errors = _collect_structured_errors(file_path, schema_path)
            print(  # noqa: T201
                json.dumps(
                    {
                        "success": False,
                        "errors": structured_errors,
                        "files": [{"path": str(file_path), "valid": False}],
                    }
                )
            )
        else:
            print(f"✗ {file_path}: {error_msg}", file=sys.stderr)  # noqa: T201
        return 1, []
    if not json_mode:
        print(f"✓ {file_path}: Valid against {schema_path.name}")  # noqa: T201
    return 0, []


def _collect_structured_errors(json_file: Path, schema_path: Path) -> list[dict[str, t.Any]]:
    """Run validation and return a list of structured error dicts.

    WHY: The existing validate_json_against_schema flattens errors into a string for the
    pre-JSON text path. We need the raw jsonschema.ValidationError objects here so the
    parser downstream gets path/validator/instance fields rather than re-parsing text.
    """
    import jsonschema

    schema = load_schema(schema_path)
    if not schema:
        return [
            {
                "path": "",
                "message": f"Could not load schema: {schema_path}",
                "validator": "schema_load",
            }
        ]

    try:
        with json_file.open(encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        return [
            {
                "path": "",
                "message": f"Invalid JSON in file: {exc}",
                "validator": "json_decode",
            }
        ]

    try:
        validator_class = jsonschema.Draft7Validator
        validator = validator_class(schema)
        raw_errors = list(validator.iter_errors(data))
    except jsonschema.SchemaError as exc:
        return [
            {
                "path": "",
                "message": f"Invalid schema: {exc}",
                "validator": "schema_validation",
            }
        ]

    structured: list[dict[str, t.Any]] = []
    for err in raw_errors:
        path_str = (
            "/" + "/".join(str(p) for p in err.absolute_path)
            if err.absolute_path
            else ""
        )
        structured.append(
            {
                "path": path_str,
                "message": err.message,
                "validator": err.validator or "unknown",
            }
        )
    return structured


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    json_mode = args.output_format == "json"

    files = _get_json_files(args)

    if not files:
        if json_mode:
            print(  # noqa: T201
                json.dumps({"success": True, "errors": [], "files": []})
            )
        else:
            print("No JSON files to validate")  # noqa: T201
        return 0

    error_count = 0
    for file_path in files:
        schema_path = find_schema_for_json(file_path)
        exit_code, _ = _process_file(
            file_path, schema_path, args.strict, json_mode
        )
        error_count += exit_code

    if error_count > 0:
        if not json_mode:
            print(  # noqa: T201
                f"\n{error_count} JSON file(s) failed schema validation",
                file=sys.stderr,
            )
        return 1

    if json_mode:
        # Final all-pass frame so the parser always has a dict-shaped JSON
        # document to read on a clean run. CheckJSONSchemaJSONParser
        # requires a top-level dict.
        print(  # noqa: T201
            json.dumps(
                {
                    "success": True,
                    "errors": [],
                    "files": [
                        {"path": str(f), "valid": True}
                        for f in files
                    ],
                }
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

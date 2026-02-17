from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ._git_utils import get_files_by_extension


def validate_json_file(file_path: Path) -> tuple[bool, str | None]:
    try:
        with file_path.open(encoding="utf-8") as f:
            json.load(f)
        return True, None
    except json.JSONDecodeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error reading file: {e}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate JSON file syntax")
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="JSON files to check (default: all .json files)",
    )

    args = parser.parse_args(argv)

    if not args.files:
        files = get_files_by_extension([".json"])
        if not files:
            files = list(Path.cwd().rglob("*.json"))
    else:
        files = args.files

    files = [f for f in files if f.is_file()]

    if not files:
        print("No JSON files to check")  # noqa: T201
        return 0

    error_count = 0
    for file_path in files:
        is_valid, error_msg = validate_json_file(file_path)

        if not is_valid:
            print(f"✗ {file_path}: {error_msg}", file=sys.stderr)  # noqa: T201
            error_count += 1
        else:
            print(f"✓ {file_path}: Valid JSON")  # noqa: T201

    if error_count > 0:
        print(f"\n{error_count} JSON file(s) with errors", file=sys.stderr)  # noqa: T201
        return 1

    print(f"\nAll {len(files)} JSON file(s) are valid")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

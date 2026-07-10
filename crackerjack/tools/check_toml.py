from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from ._git_utils import get_files_by_extension


def validate_toml_file(file_path: Path) -> tuple[bool, str | None]:
    try:
        with file_path.open("rb") as f:
            tomllib.load(f)
        return True, None
    except tomllib.TOMLDecodeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error reading file: {e}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate TOML file syntax")
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="TOML files to check (default: all .toml files)",
    )

    args = parser.parse_args(argv)

    if not args.files:
        files = get_files_by_extension([".toml"])
        if not files:
            files = list(Path.cwd().rglob("*.toml"))
    else:
        files = args.files

    files = [f for f in files if f.is_file()]

    if not files:
        print("No TOML files to check")  # noqa: T201
        return 0

    error_count = 0
    for file_path in files:
        is_valid, error_msg = validate_toml_file(file_path)

        if not is_valid:
            print(f"✗ {file_path}: {error_msg}", file=sys.stderr)  # noqa: T201
            error_count += 1
        else:
            print(f"✓ {file_path}: Valid TOML")  # noqa: T201

    if error_count > 0:
        print(f"\n{error_count} TOML file(s) with errors", file=sys.stderr)  # noqa: T201
        return 1

    print(f"\nAll {len(files)} TOML file(s) are valid")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

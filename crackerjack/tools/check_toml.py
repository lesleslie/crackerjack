"""Validate TOML file syntax.

This tool is a native Python implementation replacing pre-commit's
check-toml hook. It scans TOML files and validates their syntax.

Usage:
    python -m crackerjack.tools.check_toml [files...]

Exit Codes:
    0: All TOML files are valid
    1: One or more TOML files have syntax errors
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

from ._git_utils import get_files_by_extension


def validate_toml_file(file_path: Path) -> tuple[bool, str | None]:
    """Validate a TOML file's syntax.

    Args:
        file_path: Path to TOML file to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if file has valid TOML syntax
        - error_message: Error description if is_valid is False, None otherwise
    """
    try:
        with file_path.open("rb") as f:
            # Load TOML and validate structure
            tomllib.load(f)
        return True, None
    except tomllib.TOMLDecodeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error reading file: {e}"


def main(argv: list[str] | None = None) -> int:
    """Main entry point for check-toml tool.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code: 0 if all TOML valid, 1 if any errors found
    """
    parser = argparse.ArgumentParser(description="Validate TOML file syntax")
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="TOML files to check (default: all .toml files)",
    )

    args = parser.parse_args(argv)

    # Default to all git-tracked TOML files if none specified
    if not args.files:
        # Get all tracked TOML files (respects .gitignore via git ls-files)
        files = get_files_by_extension([".toml"])
        if not files:
            # Fallback to rglob if not in git repo
            files = list(Path.cwd().rglob("*.toml"))
    else:
        files = args.files

    # Filter to existing files only
    files = [f for f in files if f.is_file()]

    if not files:
        print("No TOML files to check")  # noqa: T201
        return 0

    # Process files
    error_count = 0
    for file_path in files:
        is_valid, error_msg = validate_toml_file(file_path)

        if not is_valid:
            print(f"✗ {file_path}: {error_msg}", file=sys.stderr)  # noqa: T201
            error_count += 1
        else:
            print(f"✓ {file_path}: Valid TOML")  # noqa: T201

    # Return appropriate exit code
    if error_count > 0:
        print(f"\n{error_count} TOML file(s) with errors", file=sys.stderr)  # noqa: T201
        return 1

    print(f"\nAll {len(files)} TOML file(s) are valid")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

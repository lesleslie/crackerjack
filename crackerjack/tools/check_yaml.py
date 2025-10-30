"""Validate YAML file syntax.

This tool is a native Python implementation replacing pre-commit's
check-yaml hook. It scans YAML files and validates their syntax.

Usage:
    python -m crackerjack.tools.check_yaml [files...]

Exit Codes:
    0: All YAML files are valid
    1: One or more YAML files have syntax errors
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from ._git_utils import get_files_by_extension


def validate_yaml_file(file_path: Path) -> tuple[bool, str | None]:
    """Validate a YAML file's syntax.

    Args:
        file_path: Path to YAML file to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if file has valid YAML syntax
        - error_message: Error description if is_valid is False, None otherwise
    """
    try:
        with file_path.open(encoding="utf-8") as f:
            # Load YAML and validate structure
            yaml.safe_load(f)
        return True, None
    except yaml.YAMLError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error reading file: {e}"


def main(argv: list[str] | None = None) -> int:
    """Main entry point for check-yaml tool.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code: 0 if all YAML valid, 1 if any errors found
    """
    parser = argparse.ArgumentParser(description="Validate YAML file syntax")
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="YAML files to check (default: all .yaml/.yml files)",
    )
    parser.add_argument(
        "--unsafe",
        action="store_true",
        help="Use unsafe YAML loader (allows Python object instantiation)",
    )

    args = parser.parse_args(argv)

    # Default to all git-tracked YAML files if none specified
    if not args.files:
        # Get all tracked YAML files (respects .gitignore via git ls-files)
        files = get_files_by_extension([".yaml", ".yml"])
        if not files:
            # Fallback to rglob if not in git repo
            files = list(Path.cwd().rglob("*.yaml"))
            files.extend(Path.cwd().rglob("*.yml"))
    else:
        files = args.files

    # Filter to existing files only
    files = [f for f in files if f.is_file()]

    if not files:
        print("No YAML files to check")  # noqa: T201
        return 0

    # Process files
    error_count = 0
    for file_path in files:
        is_valid, error_msg = validate_yaml_file(file_path)

        if not is_valid:
            print(f"✗ {file_path}: {error_msg}", file=sys.stderr)  # noqa: T201
            error_count += 1
        else:
            print(f"✓ {file_path}: Valid YAML")  # noqa: T201

    # Return appropriate exit code
    if error_count > 0:
        print(f"\n{error_count} YAML file(s) with errors", file=sys.stderr)  # noqa: T201
        return 1

    print(f"\nAll {len(files)} YAML file(s) are valid")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

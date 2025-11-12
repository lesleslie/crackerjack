"""Format JSON files to ensure consistent style.

This tool is a native Python implementation for formatting JSON files
to ensure consistent indentation and style. It reads JSON files and
writes them back with standardized formatting.

Usage:
    python -m crackerjack.tools.format_json [files...]

Exit Codes:
    0: All JSON files formatted successfully
    1: One or more JSON files have syntax errors or could not be formatted
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ._git_utils import get_files_by_extension


def format_json_file(file_path: Path) -> tuple[bool, str | None]:
    """Format a JSON file to ensure consistent style.

    Args:
        file_path: Path to JSON file to format

    Returns:
        Tuple of (is_success, error_message)
        - is_success: True if file was formatted successfully
        - error_message: Error description if is_success is False, None otherwise
    """
    try:
        # Read the file content
        with file_path.open(encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return True, "File is empty, nothing to format"

        # Parse the JSON
        data = json.loads(content)

        # Format with consistent indentation
        formatted_content = json.dumps(
            data, indent=2, ensure_ascii=False, sort_keys=True
        )

        # Add a newline at the end to match common formatting practices
        formatted_content += "\n"

        # Write the formatted content back to the file
        with file_path.open("w", encoding="utf-8") as f:
            f.write(formatted_content)

        return True, None

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON syntax: {e}"
    except Exception as e:
        return False, f"Error formatting file: {e}"


def main(argv: list[str] | None = None) -> int:
    """Main entry point for format-json tool.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code: 0 if all JSON files formatted successfully, 1 if any errors
    """
    parser = argparse.ArgumentParser(
        description="Format JSON files to ensure consistent style"
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="JSON files to format (default: all .json files)",
    )

    args = parser.parse_args(argv)

    # Default to all git-tracked JSON files if none specified
    if not args.files:
        # Get all tracked JSON files (respects .gitignore via git ls-files)
        files = get_files_by_extension([".json"])
        if not files:
            # Fallback to rglob if not in git repo
            files = list(Path.cwd().rglob("*.json"))
    else:
        files = args.files

    # Filter to existing files only
    files = [f for f in files if f.is_file()]

    if not files:
        print("No JSON files to format")  # noqa: T201
        return 0

    # Process files
    error_count = 0
    for file_path in files:
        is_success, error_msg = format_json_file(file_path)

        if not is_success:
            print(f"✗ {file_path}: {error_msg}", file=sys.stderr)  # noqa: T201
            error_count += 1
        else:
            if error_msg:  # File was empty
                print(f"→ {file_path}: {error_msg}")  # noqa: T201
            else:
                print(f"✓ {file_path}: Formatted successfully")  # noqa: T201

    # Return appropriate exit code
    if error_count > 0:
        print(f"\n{error_count} JSON file(s) failed to format", file=sys.stderr)  # noqa: T201
        return 1

    print(f"\nAll {len(files)} JSON file(s) formatted successfully")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

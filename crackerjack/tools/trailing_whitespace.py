"""Remove trailing whitespace from files.

This tool is a native Python implementation replacing pre-commit's
trailing-whitespace hook. It scans files for lines with trailing whitespace
and automatically removes it.

Usage:
    python -m crackerjack.tools.trailing_whitespace [files...]

Exit Codes:
    0: No trailing whitespace found (or successfully fixed)
    1: Trailing whitespace found and fixed (files modified)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def has_trailing_whitespace(line: str) -> bool:
    """Check if a line has trailing whitespace.

    Args:
        line: Line to check (should include newline if present)

    Returns:
        True if line has trailing whitespace before newline
    """
    # Remove trailing newline for checking
    line_stripped = line.rstrip("\n\r")
    # Check if there's whitespace at the end
    return line_stripped != line_stripped.rstrip()


def fix_trailing_whitespace(file_path: Path) -> bool:
    """Remove trailing whitespace from a file.

    Args:
        file_path: Path to file to process

    Returns:
        True if file was modified, False if no changes needed
    """
    try:
        # Read file content
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)

        # Process lines
        modified = False
        new_lines = []
        for line in lines:
            if has_trailing_whitespace(line):
                # Remove trailing whitespace but preserve newline
                stripped = line.rstrip()
                if line.endswith("\n"):
                    stripped += "\n"
                elif line.endswith("\r\n"):
                    stripped += "\r\n"
                new_lines.append(stripped)
                modified = True
            else:
                new_lines.append(line)

        # Write back if modified
        if modified:
            file_path.write_text("".join(new_lines), encoding="utf-8")
            print(f"Fixed trailing whitespace: {file_path}")  # noqa: T201

        return modified

    except UnicodeDecodeError:
        # Skip binary files
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)  # noqa: T201
        return False


def main(argv: list[str] | None = None) -> int:
    """Main entry point for trailing-whitespace tool.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code: 0 if no files modified, 1 if files were modified
    """
    parser = argparse.ArgumentParser(
        description="Remove trailing whitespace from files"
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Files to check (default: all Python files in current directory)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check only, don't modify files",
    )

    args = parser.parse_args(argv)

    # Default to all tracked files if none specified
    if not args.files:
        # Get all Python files in current directory
        files = list(Path.cwd().rglob("*.py"))
    else:
        files = args.files

    # Filter to existing files only
    files = [f for f in files if f.is_file()]

    if not files:
        print("No files to check")  # noqa: T201
        return 0

    # Process files
    modified_count = 0
    for file_path in files:
        if args.check:
            # Check mode: just detect, don't fix
            content = file_path.read_text(encoding="utf-8")
            lines = content.splitlines(keepends=True)
            if any(has_trailing_whitespace(line) for line in lines):
                print(f"Trailing whitespace found: {file_path}")  # noqa: T201
                modified_count += 1
        else:
            # Fix mode: remove trailing whitespace
            if fix_trailing_whitespace(file_path):
                modified_count += 1

    # Return appropriate exit code
    if modified_count > 0:
        if args.check:
            print(f"\n{modified_count} file(s) with trailing whitespace")  # noqa: T201
        else:
            print(f"\nFixed {modified_count} file(s)")  # noqa: T201
        return 1

    print("No trailing whitespace found")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

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

from ._git_utils import get_files_by_extension


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


def _collect_files_to_check(args: argparse.Namespace) -> list[Path]:
    """Collect files to check for trailing whitespace.

    Args:
        args: Parsed command-line arguments

    Returns:
        List of file paths to process
    """
    # Default to all git-tracked files if none specified
    if not args.files:
        # Get all tracked text files (respects .gitignore via git ls-files)
        files = get_files_by_extension(
            [".py", ".md", ".txt", ".yaml", ".yml", ".toml", ".json"]
        )
        if not files:
            # Fallback to Python files if not in git repo
            files = list(Path.cwd().rglob("*.py"))
    else:
        files = args.files

    # Filter to existing files only
    return [f for f in files if f.is_file()]


def _process_files_in_check_mode(files: list[Path]) -> int:
    """Process files in check-only mode.

    Args:
        files: List of file paths to check

    Returns:
        Count of files with trailing whitespace
    """
    modified_count = 0
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        if any(has_trailing_whitespace(line) for line in lines):
            print(f"Trailing whitespace found: {file_path}")  # noqa: T201
            modified_count += 1
    return modified_count


def _process_files_in_fix_mode(files: list[Path]) -> int:
    """Process files in fix mode.

    Args:
        files: List of file paths to fix

    Returns:
        Count of files modified
    """
    modified_count = 0
    for file_path in files:
        if fix_trailing_whitespace(file_path):
            modified_count += 1
    return modified_count


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

    files = _collect_files_to_check(args)

    if not files:
        print("No files to check")  # noqa: T201
        return 0

    # Process files based on mode
    if args.check:
        modified_count = _process_files_in_check_mode(files)
    else:
        modified_count = _process_files_in_fix_mode(files)

    # Return appropriate exit code
    if modified_count > 0:
        if args.check:
            print(f"\n{modified_count} file(s) with trailing whitespace")  # noqa: T201
        else:
            print(f"\nFixed {modified_count} file(s)")  # noqa: T201
            # Align with pre-commit semantics so HookExecutor treats this as pass
            # when a formatter modifies files but exits with code 1.
            print("files were modified by this hook")  # noqa: T201
        return 1

    print("No trailing whitespace found")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

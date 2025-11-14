"""Ensure files end with a newline.

This tool is a native Python implementation replacing pre-commit's
end-of-file-fixer hook. It scans files and ensures they end with exactly
one newline character.

Usage:
    python -m crackerjack.tools.end_of_file_fixer [files...]

Exit Codes:
    0: All files end with newline (or successfully fixed)
    1: Files were modified to add/fix ending newline
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._git_utils import get_files_by_extension


def needs_newline_fix(content: bytes) -> tuple[bool, bytes | None]:
    """Check if file needs newline added or fixed.

    Args:
        content: File content as bytes

    Returns:
        Tuple of (needs_fix, fixed_content)
        - needs_fix: True if file needs modification
        - fixed_content: Fixed content if needs_fix is True, None otherwise
    """
    if not content:
        # Empty file doesn't need newline
        return False, None

    # Check if file ends with newline
    if content.endswith(b"\n"):
        # Check for multiple trailing newlines
        stripped = content.rstrip(b"\n")
        if len(content) - len(stripped) > 1:
            # Multiple trailing newlines, fix to exactly one
            return True, stripped + b"\n"
        # Exactly one newline, no fix needed
        return False, None

    # No trailing newline, add one
    return True, content + b"\n"


def fix_end_of_file(file_path: Path) -> bool:
    """Ensure file ends with exactly one newline.

    Args:
        file_path: Path to file to process

    Returns:
        True if file was modified, False if no changes needed
    """
    try:
        # Read file content as bytes to preserve encoding
        content = file_path.read_bytes()

        # Check if fix is needed
        needs_fix, fixed_content = needs_newline_fix(content)

        if needs_fix and fixed_content is not None:
            # Write fixed content
            file_path.write_bytes(fixed_content)
            print(f"Fixed end-of-file: {file_path}")  # noqa: T201
            return True

        return False

    except Exception as e:
        print(f"Error processing {file_path}: {e}", file=sys.stderr)  # noqa: T201
        return False


def _collect_files_to_check(args: argparse.Namespace) -> list[Path]:
    """Collect files to check for end-of-file issues.

    Args:
        args: Parsed command-line arguments

    Returns:
        List of file paths to process
    """
    # Default to all git-tracked text files if none specified
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
        Count of files with end-of-file issues
    """
    modified_count = 0
    for file_path in files:
        try:
            content = file_path.read_bytes()
            needs_fix, _ = needs_newline_fix(content)

            if needs_fix:
                print(f"Missing/incorrect end-of-file: {file_path}")  # noqa: T201
                modified_count += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)  # noqa: T201
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
        try:
            if fix_end_of_file(file_path):
                modified_count += 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}", file=sys.stderr)  # noqa: T201
    return modified_count


def main(argv: list[str] | None = None) -> int:
    """Main entry point for end-of-file-fixer tool.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code: 0 if no files modified, 1 if files were modified
    """
    parser = argparse.ArgumentParser(
        description="Ensure files end with exactly one newline"
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Files to check (default: all text files in current directory)",
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
            print(f"\n{modified_count} file(s) with incorrect end-of-file")  # noqa: T201
        else:
            print(f"\nFixed {modified_count} file(s)")  # noqa: T201
            # Align with pre-commit semantics so HookExecutor treats this as pass
            print("files were modified by this hook")  # noqa: T201
        return 1

    print("All files end with correct newline")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

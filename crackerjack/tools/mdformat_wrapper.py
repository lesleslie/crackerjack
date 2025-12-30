"""Git-aware wrapper for mdformat.

This wrapper ensures mdformat only checks git-tracked markdown files,
automatically respecting .gitignore patterns without needing manual skip
configuration.

Usage:
    python -m crackerjack.tools.mdformat_wrapper [mdformat args...]

Exit Codes:
    Same as mdformat (0 = no issues, 1 = issues found, etc.)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ._git_utils import get_git_tracked_files


def main(argv: list[str] | None = None) -> int:
    """Run mdformat on git-tracked markdown files only.

    This wrapper automatically discovers git-tracked .md and .markdown files
    and passes them to mdformat, ensuring .gitignore patterns are respected.

    Behavior:
    - First run: Formats files and returns exit code 1 (fail to signal changes)
    - Second run: Files already formatted, returns exit code 0 (pass)

    Args:
        argv: Optional arguments to pass to mdformat

    Returns:
        Exit code: 0 if no changes needed, 1 if files were formatted
    """
    # Get all git-tracked markdown files (automatically respects .gitignore)
    md_files = get_git_tracked_files("*.md")
    markdown_files = get_git_tracked_files("*.markdown")
    files = md_files + markdown_files

    if not files:
        print("No git-tracked markdown files found", file=sys.stderr)  # noqa: T201
        return 0  # No files is not an error for formatters

    # Build mdformat command with git-tracked files
    cmd = ["mdformat", "--no-codeformatters"]

    # Add any additional arguments passed to wrapper
    if argv:
        cmd.extend(argv)

    # Add file paths at the end
    cmd.extend([str(f) for f in files])

    # Execute mdformat
    try:
        # First, check if files need formatting (dry-run)
        check_cmd = cmd + ["--check"]
        check_result = subprocess.run(
            check_cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        # If check passed (exit code 0), files are already formatted
        if check_result.returncode == 0:
            print(f"All {len(files)} markdown files already formatted correctly")
            return 0

        # Files need formatting - run mdformat to fix them
        format_result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        # Forward output to stdout/stderr
        if format_result.stdout:
            print(format_result.stdout, end="")
        if format_result.stderr:
            print(format_result.stderr, end="", file=sys.stderr)

        # Return exit code 1 to indicate files were formatted (changes made)
        # This causes the hook to fail on first run, pass on second run
        files_formatted = (
            check_result.returncode
        )  # Non-zero means files needed formatting
        if files_formatted:
            print(
                f"Formatted {len(files)} markdown files - run crackerjack again to verify"
            )
            return 1  # Fail to signal changes were made

        return 0
    except FileNotFoundError:
        print(
            "Error: mdformat not found. Install with: uv pip install mdformat mdformat-ruff",
            file=sys.stderr,
        )  # noqa: T201
        return 127  # Command not found
    except Exception as e:
        print(f"Error running mdformat: {e}", file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

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

    Args:
        argv: Optional arguments to pass to mdformat

    Returns:
        Exit code from mdformat command
    """
    # Get all git-tracked markdown files (automatically respects .gitignore)
    md_files = get_git_tracked_files("*.md")
    markdown_files = get_git_tracked_files("*.markdown")
    files = md_files + markdown_files

    if not files:
        print("No git-tracked markdown files found", file=sys.stderr)  # noqa: T201
        return 0  # No files is not an error for formatters

    # Build mdformat command with git-tracked files
    cmd = ["mdformat"]

    # Add any additional arguments passed to wrapper
    if argv:
        cmd.extend(argv)

    # Add file paths at the end
    cmd.extend([str(f) for f in files])

    # Execute mdformat
    try:
        result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            check=False,  # Don't raise on non-zero exit (mdformat returns 1 for issues found)
        )
        return result.returncode
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

"""Git-aware wrapper for codespell.

This wrapper ensures codespell only checks git-tracked files, automatically
respecting .gitignore patterns without needing manual skip configuration.

Usage:
    python -m crackerjack.tools.codespell_wrapper [codespell args...]

Exit Codes:
    Same as codespell (0 = no issues, 1 = issues found, etc.)
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ._git_utils import get_git_tracked_files


def main(argv: list[str] | None = None) -> int:
    """Run codespell on git-tracked files only.

    This wrapper automatically discovers git-tracked files and passes them
    to codespell, ensuring .gitignore patterns are respected without manual
    skip configuration.

    Args:
        argv: Optional arguments to pass to codespell

    Returns:
        Exit code from codespell command
    """
    # Get all git-tracked files (automatically respects .gitignore)
    files = get_git_tracked_files()

    if not files:
        print("No git-tracked files found", file=sys.stderr)  # noqa: T201
        return 1

    # Build codespell command with git-tracked files
    cmd = ["codespell"]

    # Add any additional arguments passed to wrapper
    if argv:
        cmd.extend(argv)

    # Add file paths at the end
    cmd.extend([str(f) for f in files])

    # Execute codespell
    try:
        result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            check=False,  # Don't raise on non-zero exit (codespell returns 1 for issues found)
        )
        return result.returncode
    except FileNotFoundError:
        print(
            "Error: codespell not found. Install with: uv pip install codespell",
            file=sys.stderr,
        )  # noqa: T201
        return 127  # Command not found
    except Exception as e:
        print(f"Error running codespell: {e}", file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

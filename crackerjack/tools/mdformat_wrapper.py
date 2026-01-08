from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ._git_utils import get_git_tracked_files


def main(argv: list[str] | None = None) -> int:
    md_files = get_git_tracked_files("*.md")
    markdown_files = get_git_tracked_files("*.markdown")
    files = md_files + markdown_files

    if not files:
        print("No git-tracked markdown files found", file=sys.stderr)  # noqa: T201
        return 0

    cmd = ["mdformat", "--no-codeformatters"]

    if argv:
        cmd.extend(argv)

    cmd.extend([str(f) for f in files])

    try:
        check_cmd = cmd + ["--check"]
        check_result = subprocess.run(
            check_cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        if check_result.returncode == 0:
            print(f"All {len(files)} markdown files already formatted correctly")
            return 0

        format_result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        if format_result.stdout:
            print(format_result.stdout, end="")
        if format_result.stderr:
            print(format_result.stderr, end="", file=sys.stderr)

        files_formatted = check_result.returncode
        if files_formatted:
            print(
                f"Formatted {len(files)} markdown files - run crackerjack again to verify"
            )
            return 1

        return 0
    except FileNotFoundError:
        print(
            "Error: mdformat not found. Install with: uv pip install mdformat mdformat-ruff",
            file=sys.stderr,
        )  # noqa: T201
        return 127
    except Exception as e:
        print(f"Error running mdformat: {e}", file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

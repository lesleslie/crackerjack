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
        check_cmd = [*cmd, "--check"]
        check_result = subprocess.run(
            check_cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        if check_result.returncode == 0:
            return 0

        format_result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        if format_result.stdout:
            pass
        if format_result.stderr:
            pass

        files_formatted = check_result.returncode
        if files_formatted:
            return 1

        return 0
    except FileNotFoundError:
        return 127
    except Exception as e:
        print(f"Error running mdformat: {e}", file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

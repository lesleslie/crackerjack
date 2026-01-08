from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from ._git_utils import get_git_tracked_files


def main(argv: list[str] | None = None) -> int:
    files = get_git_tracked_files()

    if not files:
        print("No git-tracked files found", file=sys.stderr)  # noqa: T201
        return 1

    cmd = ["codespell"]

    if argv:
        cmd.extend(argv)

    cmd.extend([str(f) for f in files])

    try:
        result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            check=False,
        )
        return result.returncode
    except FileNotFoundError:
        print(
            "Error: codespell not found. Install with: uv pip install codespell",
            file=sys.stderr,
        )  # noqa: T201
        return 127
    except Exception as e:
        print(f"Error running codespell: {e}", file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from ._git_utils import get_git_tracked_files

_SKIP_DIRS = {"htmlcov", ".git", ".venv", "node_modules", "__pycache__"}


_SKIP_FILENAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
}
_LOCK_EXTENSIONS = {".lock"}


def _is_ignored_file(path: Path) -> bool:
    name = path.name

    if name.endswith((".backup", ".bak")):
        return True

    if name in _SKIP_FILENAMES or path.suffix.lower() in _LOCK_EXTENSIONS:
        return True

    parts = path.parts
    for skip in _SKIP_DIRS:
        if skip in parts:
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    files = get_git_tracked_files()

    files = [f for f in files if not _is_ignored_file(f)]

    if not files:
        print("No git-tracked files found", file=sys.stderr) # noqa: T201
        return 1

    codespell_bin = Path.cwd() / ".venv" / "bin" / "codespell"
    if codespell_bin.exists():
        cmd = [str(codespell_bin), "--write-changes"]
    else:
        resolved = shutil.which("codespell")
        cmd = [resolved or "codespell", "--write-changes"]

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
        return 127
    except Exception as e:
        print(f"Error running codespell: {e}", file=sys.stderr) # noqa: T201
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from crackerjack.tools._git_utils import get_git_tracked_files


def get_file_size(file_path: Path) -> int:
    try:
        return file_path.stat().st_size
    except (FileNotFoundError, OSError):
        return 0


def format_size(size_bytes: float) -> str:
    size: float = size_bytes
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def suggest_gitignore_action(file_path: Path) -> str | None:
    """Suggest a gitignore action for a large file, or None if no suggestion."""
    name = file_path.name
    parts = file_path.parts

    suggestions: list[str] = []

    if name.endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".zip", ".7z", ".rar")):
        if any(p.startswith(".backup") or p.startswith(".backups") for p in parts):
            return f"git rm --cached -r '{file_path.parent}'  # backup archives should not be tracked"
        suggestions.append(f"Archive file: consider removing from tracking")

    if name.endswith(".bak"):
        return f"git rm --cached '{file_path}'  # .bak files should not be tracked"

    if any(p.startswith(".backup") or p == ".backups" for p in parts):
        return f"git rm --cached -r '{file_path.parent}'  # backup directory should not be tracked"

    if any(p.startswith(".cache") or p == ".cache" for p in parts):
        return f"git rm --cached -r '{file_path.parent}'  # cache directory should not be tracked"

    if name in ("uv.lock",):
        return None  # lock files are intentionally tracked

    if ".venv" in parts or "venv" in parts or "node_modules" in parts:
        return f"git rm --cached -r '{file_path.parent}'  # virtual environment should not be tracked"

    if name.endswith((".png", ".jpg", ".jpeg", ".gif", ".svg")):
        if any(p in ("docs/diagrams", "docs/.backups") for p in parts):
            return None  # documentation diagrams are intentionally tracked

    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check for large files in git repository",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Files to check (default: all git-tracked files)",
    )
    parser.add_argument(
        "--maxkb",
        type=int,
        default=1000,
        help="Maximum file size in KB (default: 1000)",
    )
    parser.add_argument(
        "--enforce-all",
        action="store_true",
        help="Check all files, not just newly added ones",
    )
    parser.add_argument(
        "--suggest-gitignore",
        action="store_true",
        help="Suggest gitignore actions for large files",
    )

    if argv is None:
        argv = []
    args = parser.parse_args(argv)

    max_size_bytes = args.maxkb * 1024

    if not args.files:
        files = get_git_tracked_files()
        if not files:
            files = list(Path.cwd().rglob("*"))
            files = [f for f in files if f.is_file()]
    else:
        files = args.files

    files = [f for f in files if f.is_file()]

    if not files:
        print("No files to check")  # noqa: T201
        return 0

    large_files = []
    for file_path in files:
        size = get_file_size(file_path)
        if size > max_size_bytes:
            large_files.append((file_path, size))

    if large_files:
        print("Large files detected:", file=sys.stderr)  # noqa: T201
        suggestions_found = False
        for file_path, size in large_files:
            print(f" {file_path}: {format_size(size)}", file=sys.stderr)  # noqa: T201
            if args.suggest_gitignore:
                action = suggest_gitignore_action(file_path)
                if action:
                    print(f"  SUGGESTION: {action}", file=sys.stderr)  # noqa: T201
                    suggestions_found = True
        if suggestions_found:
            print(  # noqa: T201
                "\nSome large files appear to be tracked but should be gitignored.",
                file=sys.stderr,
            )
        return 1

    print("All files are under size limit")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

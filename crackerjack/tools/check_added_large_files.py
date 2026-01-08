from __future__ import annotations

import argparse
import sys
from pathlib import Path

from crackerjack.tools._git_utils import get_git_tracked_files


def get_file_size(file_path: Path) -> int:
    try:
        return file_path.stat().st_size
    except (FileNotFoundError, OSError):
        return 0


def format_size(size_bytes: int | float) -> str:
    size: float = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check for large files in git repository"
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
        for file_path, size in large_files:
            print(
                f" {file_path}: {format_size(size)} "
                f"(exceeds {format_size(max_size_bytes)})",
                file=sys.stderr,
            )  # noqa: T201
        print(
            f"\n{len(large_files)} large file(s) found. "
            f"Consider using Git LFS for large files.",
            file=sys.stderr,
        )  # noqa: T201
        return 1

    print("All files are under size limit")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

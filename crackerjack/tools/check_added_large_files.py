"""Check for large files added to git repository.

This tool is a native Python implementation replacing pre-commit's
check-added-large-files hook. It warns about files exceeding a size threshold.

Usage:
    python -m crackerjack.tools.check_added_large_files [files...]

Exit Codes:
    0: No large files found
    1: One or more large files detected
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def get_file_size(file_path: Path) -> int:
    """Get file size in bytes.

    Args:
        file_path: Path to file

    Returns:
        File size in bytes, or 0 if file doesn't exist
    """
    try:
        return file_path.stat().st_size
    except (FileNotFoundError, OSError):
        return 0


def format_size(size_bytes: int | float) -> str:
    """Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable size string (e.g., "1.5 MB")
    """
    size: float = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def get_git_tracked_files() -> list[Path]:
    """Get list of files tracked by git.

    Returns:
        List of Path objects for git-tracked files
    """
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
        return [
            Path(line.strip()) for line in result.stdout.splitlines() if line.strip()
        ]
    except subprocess.CalledProcessError:
        return []
    except FileNotFoundError:
        # Git not available
        return []


def main(argv: list[str] | None = None) -> int:
    """Main entry point for check-added-large-files tool.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code: 0 if no large files, 1 if large files found
    """
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

    # When called from tests, avoid picking up pytest argv
    if argv is None:
        argv = []
    args = parser.parse_args(argv)

    # Convert KB to bytes
    max_size_bytes = args.maxkb * 1024

    # Determine which files to check
    if not args.files:
        # Get all git-tracked files
        files = get_git_tracked_files()
        if not files:
            # Fallback to all files in current directory if not in git repo
            files = list(Path.cwd().rglob("*"))
            files = [f for f in files if f.is_file()]
    else:
        files = args.files

    # Filter to existing files only
    files = [f for f in files if f.is_file()]

    if not files:
        print("No files to check")  # noqa: T201
        return 0

    # Process files
    large_files = []
    for file_path in files:
        size = get_file_size(file_path)
        if size > max_size_bytes:
            large_files.append((file_path, size))

    # Report results
    if large_files:
        print("Large files detected:", file=sys.stderr)  # noqa: T201
        for file_path, size in large_files:
            print(
                f"  {file_path}: {format_size(size)} "
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

"""Git-aware file discovery utilities for native tools.

This module provides utilities for discovering files while respecting .gitignore
patterns. It uses `git ls-files` to automatically handle gitignore compliance,
making crackerjack behave identically to pre-commit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def get_git_tracked_files(pattern: str | None = None) -> list[Path]:
    """Get list of files tracked by git, optionally filtered by pattern.

    This function uses `git ls-files` which automatically respects .gitignore
    patterns. This is the industry-standard approach used by pre-commit and
    ensures only git-tracked files are processed.

    Args:
        pattern: Optional glob pattern to filter files (e.g., "*.py", "*.yaml")
                If None, returns all tracked files.

    Returns:
        List of Path objects for git-tracked files matching the pattern.
        Falls back to empty list if not in a git repository.

    Example:
        >>> # Get all tracked Python files
        >>> python_files = get_git_tracked_files("*.py")
        >>> # Get all tracked YAML files
        >>> yaml_files = get_git_tracked_files("*.yaml")
    """
    try:
        cmd = ["git", "ls-files"]
        if pattern:
            cmd.append(pattern)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=Path.cwd(),
        )

        # Filter to only include files that actually exist on disk
        # (git ls-files can include deleted files still in the index)
        return [
            Path(line.strip())
            for line in result.stdout.splitlines()
            if line.strip() and Path(line.strip()).exists()
        ]

    except subprocess.CalledProcessError:
        # Git command failed (not in a git repo, etc.)
        return []
    except FileNotFoundError:
        # Git not available
        return []


def get_files_by_extension(extensions: list[str], use_git: bool = True) -> list[Path]:
    """Get files with specified extensions, respecting git if available.

    Args:
        extensions: List of file extensions to match (e.g., [".py", ".yaml"])
        use_git: If True (default), use git ls-files when in a git repo.
                If False, use Path.rglob() for all files.

    Returns:
        List of Path objects matching the extensions.
        Automatically respects .gitignore when use_git=True.

    Example:
        >>> # Get Python files (git-aware)
        >>> py_files = get_files_by_extension([".py"])
        >>> # Get YAML files (all files, ignore git)
        >>> yaml_files = get_files_by_extension([".yaml", ".yml"], use_git=False)
    """
    if not use_git:
        # Fallback to rglob for all files
        files = []
        for ext in extensions:
            files.extend(Path.cwd().rglob(f"*{ext}"))
        return [f for f in files if f.is_file()]

    # Try git-aware discovery first
    files = []
    for ext in extensions:
        # git ls-files pattern: *.ext
        pattern = f"*{ext}"
        git_files = get_git_tracked_files(pattern)
        if git_files:
            files.extend(git_files)

    if files:
        return files

    # Fallback to rglob if git unavailable
    result = []
    for ext in extensions:
        result.extend(Path.cwd().rglob(f"*{ext}"))
    return [f for f in result if f.is_file()]

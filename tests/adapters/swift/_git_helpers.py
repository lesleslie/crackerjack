"""Shared test helpers for Swift adapter tests.

Avoids duplicating `_init_git_repo` across multiple test files.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def init_git_repo(tmp_path: Path, tag: str | None = None) -> Path:
    """Initialize a git repo with one commit. Optionally tag the commit."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path,
        check=True,
    )
    (tmp_path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=tmp_path,
        check=True,
    )
    if tag is not None:
        subprocess.run(["git", "tag", tag], cwd=tmp_path, check=True)
    return tmp_path
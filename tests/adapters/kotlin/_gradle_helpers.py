"""Shared test helpers for Kotlin adapter tests.

Avoids duplicating ``init_git_repo`` across multiple test files.

Mirrors ``tests/adapters/swift/_git_helpers.py::init_git_repo`` and additionally
sets ``crackerjack.adapters.kotlin.git_backend._PROJECT_ROOT`` so that the
module-level ``commit``/``tag``/``push``/``delete_tag``/``reset``/``gh_release``
functions operate on the test's temporary git repo (pytest does not chdir).
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def init_git_repo(tmp_path: Path, tag: str | None = None) -> Path:
    """Initialize a git repo with one commit. Optionally tag the commit.

    Sets the module-level active project root on
    :mod:`crackerjack.adapters.kotlin.git_backend` so the module-level
    functions (``commit``, ``tag``, etc.) target this directory instead of
    pytest's CWD.
    """
    from crackerjack.adapters.kotlin import git_backend

    git_backend._PROJECT_ROOT = tmp_path

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

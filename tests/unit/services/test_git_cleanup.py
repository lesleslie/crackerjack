"""Stage 3 working-tree guard tests for git_cleanup_service.

These tests cover the public `validate_working_tree_clean(allow_dirty)` helper
added in Stage 3 of the Ruff fix-safety policy. The guard is exercised via a
real git repository in a tmp_path because the existing internal
`_validate_working_tree_clean` is tied to a GitInterface instance — the new
module-level wrapper has to run `git status --porcelain` itself.
"""

from __future__ import annotations

import subprocess


def test_dirty_tree_refuses_fix(tmp_path, monkeypatch) -> None:
    """When the tree is dirty and allow_dirty=False, validate_working_tree_clean raises."""
    from crackerjack.services.git_cleanup_service import validate_working_tree_clean

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "a.txt").write_text("clean\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@x",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@x",
            "PATH": __import__("os").environ["PATH"],
        },
    )
    (repo / "a.txt").write_text("dirty\n")

    monkeypatch.chdir(repo)

    try:
        validate_working_tree_clean(allow_dirty=False)
    except Exception as exc:
        assert "dirty" in str(exc).lower() or "clean" in str(exc).lower()
        return

    raise AssertionError("validate_working_tree_clean must refuse a dirty tree")

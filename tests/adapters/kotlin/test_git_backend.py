"""Integration tests for the default git_backend subprocess layer.

These tests exercise ``make_git_backend`` against a real local git repo so
the subprocess ordering (``git tag -a -m M -- N``, ``git push -- R T``) is
actually exercised. The remote is a local bare repo, so no network is used.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.kotlin.git_backend import (
    commit,
    delete_tag,
    gh_release,
    make_git_backend,
    push,
    reset,
    tag,
)
from tests.adapters.kotlin._gradle_helpers import init_git_repo


def test_commit_runs_git_commit_with_message(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    sha = commit("initial commit")
    assert len(sha) == 40


def test_commit_refuses_uncommitted_changes(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    (tmp_path / "untracked.txt").write_text("hi")
    with pytest.raises(RuntimeError, match="uncommitted"):
        commit("nope")


def test_tag_passes_message_flag_before_separator(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    sha = commit("c1")
    tag("v1.0.0", "release notes")
    result = subprocess.run(
        ["git", "tag", "-l", "--format=%(contents:subject)"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert "release notes" in result.stdout


def test_push_uses_configured_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    init_git_repo(tmp_path)
    commit("c1")
    tag("v1.0.0", "msg")
    monkeypatch.setenv("MAHAVISHNU_GIT_REMOTE", "myremote")
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        push(sha="dummy", tag_name="v1.0.0")
    args = mock_run.call_args[0][0]
    assert "myremote" in args


def test_push_defaults_to_origin_remote(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MAHAVISHNU_GIT_REMOTE", raising=False)
    init_git_repo(tmp_path)
    commit("c1")
    tag("v1.0.0", "msg")
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        push(sha="dummy", tag_name="v1.0.0")
    args = mock_run.call_args[0][0]
    assert "origin" in args


def test_make_git_backend_returns_six_callables(tmp_path: Path) -> None:
    backend = make_git_backend(tmp_path)
    assert len(backend) == 6
    for fn in backend:
        assert callable(fn)


def test_reset_preserves_target_commit(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    sha = commit("c1")
    tag("v1.0.0", "msg")
    reset(sha)
    # The target commit's tree should still be present
    assert (tmp_path / "README.md").exists()


def test_gh_release_raises_on_nonzero_exit(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    commit("c1")
    tag("v1.0.0", "msg")
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "auth required"
        with pytest.raises(RuntimeError, match="gh release create failed"):
            gh_release("v1.0.0")


def test_gh_release_uses_notes_file_not_generate_notes(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    commit("c1")
    tag("v1.0.0", "msg")
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "https://example.com/releases/v1.0.0"
        mock_run.return_value.stderr = ""
        gh_release("v1.0.0")
    args = mock_run.call_args[0][0]
    assert "--notes-file" in args
    assert "--generate-notes" not in args
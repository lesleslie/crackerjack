"""Integration tests for the default git_backend subprocess layer.

These tests exercise ``make_git_backend`` against a real local git repo so
the subprocess ordering (``git tag -a -m M -- N``, ``git push -- R T``) is
actually exercised. The remote is a local bare repo, so no network is used.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from crackerjack.adapters.swift.git_backend import make_git_backend
from tests.adapters.swift._git_helpers import init_git_repo


def _init_bare_remote(parent: Path, name: str) -> Path:
    bare = parent / name
    subprocess.run(["git", "init", "--bare", "-q", str(bare)], check=True)
    return bare


def test_tag_with_name_and_message_creates_annotated_tag(tmp_path: Path) -> None:
    """Bug 1 regression: ``git tag -a -m M -- N`` must succeed.

    The pre-fix ordering (``-a -- N -m M``) placed the `--` separator
    before the message flag, causing git to treat `-m` as a positional
    argument and fail with ``fatal: too many arguments``.
    """
    init_git_repo(tmp_path)
    _commit, tag, _push, _delete_tag, _reset, _gh_release = make_git_backend(tmp_path)

    tag("v1.2.3", "Release v1.2.3")

    # Verify the tag exists, is annotated, and carries the annotation text.
    verify = subprocess.run(
        ["git", "cat-file", "-t", "v1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert verify.stdout.strip() == "tag", (
        "Expected an annotated tag object; the subprocess flag ordering "
        f"is wrong. git cat-file output: {verify.stdout!r}"
    )

    # Confirm the -m message was actually attached.
    subject = subprocess.run(
        ["git", "tag", "-n99", "v1.2.3"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Release v1.2.3" in subject.stdout, (
        "Annotation message not attached to tag. "
        f"`git tag -n99` output: {subject.stdout!r}"
    )


def test_tag_rejects_name_starting_with_dash(tmp_path: Path) -> None:
    """Per Security F7: tag names beginning with ``-`` are rejected client-side."""
    init_git_repo(tmp_path)
    _commit, tag, _push, _delete_tag, _reset, _gh_release = make_git_backend(tmp_path)

    with pytest.raises(ValueError, match="Invalid tag name"):
        tag("--evil", "Release")


def test_tag_rejects_empty_name(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    _commit, tag, _push, _delete_tag, _reset, _gh_release = make_git_backend(tmp_path)

    with pytest.raises(ValueError, match="Invalid tag name"):
        tag("", "Release")


def test_push_defaults_to_origin_remote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bug 2 regression: push uses ``origin`` when MAHAVISHNU_GIT_REMOTE is unset."""
    monkeypatch.delenv("MAHAVISHNU_GIT_REMOTE", raising=False)

    init_git_repo(tmp_path, tag="v1.0.0")
    bare_origin = _init_bare_remote(tmp_path.parent, "origin.git")
    bare_upstream = _init_bare_remote(tmp_path.parent, "upstream.git")
    subprocess.run(["git", "remote", "add", "origin", str(bare_origin)], cwd=tmp_path, check=True)
    subprocess.run(["git", "remote", "add", "upstream", str(bare_upstream)], cwd=tmp_path, check=True)

    # Bump to v1.0.1 via the lifecycle's tag call.
    _commit, tag, push, _delete_tag, _reset, _gh_release = make_git_backend(tmp_path)
    tag("v1.0.1", "Release v1.0.1")
    push("deadbeef", "v1.0.1")

    origin_tags = subprocess.run(
        ["git", "tag", "-l"],
        cwd=bare_origin,
        capture_output=True,
        text=True,
        check=True,
    )
    upstream_tags = subprocess.run(
        ["git", "tag", "-l"],
        cwd=bare_upstream,
        capture_output=True,
        text=True,
    )
    assert "v1.0.1" in origin_tags.stdout, (
        f"Push landed on origin: {origin_tags.stdout!r}"
    )
    assert "v1.0.1" not in upstream_tags.stdout, (
        f"Push leaked to upstream when MAHAVISHNU_GIT_REMOTE unset: "
        f"{upstream_tags.stdout!r}"
    )


def test_push_honors_mahavishnu_git_remote_env_var(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bug 2: push targets MAHAVISHNU_GIT_REMOTE when set."""
    monkeypatch.setenv("MAHAVISHNU_GIT_REMOTE", "upstream")

    init_git_repo(tmp_path, tag="v1.0.0")
    bare_origin = _init_bare_remote(tmp_path.parent, "origin.git")
    bare_upstream = _init_bare_remote(tmp_path.parent, "upstream.git")
    subprocess.run(["git", "remote", "add", "origin", str(bare_origin)], cwd=tmp_path, check=True)
    subprocess.run(["git", "remote", "add", "upstream", str(bare_upstream)], cwd=tmp_path, check=True)

    _commit, tag, push, _delete_tag, _reset, _gh_release = make_git_backend(tmp_path)
    tag("v1.0.2", "Release v1.0.2")
    push("deadbeef", "v1.0.2")

    origin_tags = subprocess.run(
        ["git", "tag", "-l"],
        cwd=bare_origin,
        capture_output=True,
        text=True,
    )
    upstream_tags = subprocess.run(
        ["git", "tag", "-l"],
        cwd=bare_upstream,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "v1.0.2" not in origin_tags.stdout, (
        "Push should have targeted upstream, not origin. "
        f"origin tags: {origin_tags.stdout!r}"
    )
    assert "v1.0.2" in upstream_tags.stdout, (
        f"Push did not land on upstream: {upstream_tags.stdout!r}"
    )


def test_push_rejects_tag_name_starting_with_dash(tmp_path: Path) -> None:
    """Per Security F7: the tag_name positional must be validated client-side."""
    init_git_repo(tmp_path)
    _commit, _tag, push, _delete_tag, _reset, _gh_release = make_git_backend(tmp_path)

    with pytest.raises(ValueError, match="Invalid tag name"):
        push("deadbeef", "--evil-tag")


def test_push_rejects_empty_tag_name(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    _commit, _tag, push, _delete_tag, _reset, _gh_release = make_git_backend(tmp_path)

    with pytest.raises(ValueError, match="Invalid tag name"):
        push("deadbeef", "")
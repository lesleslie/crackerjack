from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.adapters.base import VersionNotFoundError
from crackerjack.adapters.swift.version_source import GitTagVersionSource
from tests.adapters.swift._git_helpers import init_git_repo


def test_read_returns_semver_version_from_tag(tmp_path: Path) -> None:
    """A repo tagged ``v1.2.3`` reports the version ``1.2.3`` (no ``v`` prefix)."""
    project_root = init_git_repo(tmp_path, tag="v1.2.3")
    source = GitTagVersionSource(project_root)

    assert source.read() == "1.2.3"


def test_read_returns_latest_semver_tag_when_multiple_exist(tmp_path: Path) -> None:
    """``git describe --tags --abbrev=0`` returns the most recent tag."""
    project_root = init_git_repo(tmp_path)
    # After the initial commit we have to create extra commits before tagging
    # so that "most recent" is well-defined.
    import subprocess

    (project_root / "CHANGELOG.md").write_text("# changelog\n")
    subprocess.run(["git", "add", "."], cwd=project_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "second"],
        cwd=project_root,
        check=True,
    )
    subprocess.run(["git", "tag", "v0.1.0"], cwd=project_root, check=True)

    (project_root / "CHANGELOG.md").write_text("# changelog\nmore\n")
    subprocess.run(["git", "add", "."], cwd=project_root, check=True)
    subprocess.run(
        ["git", "commit", "-m", "third"],
        cwd=project_root,
        check=True,
    )
    subprocess.run(["git", "tag", "v0.2.0"], cwd=project_root, check=True)

    source = GitTagVersionSource(project_root)

    assert source.read() == "0.2.0"


def test_read_raises_versionnotfounderror_when_no_tags_exist(tmp_path: Path) -> None:
    """A repo with zero ``v*`` tags raises :class:`VersionNotFoundError`."""
    project_root = init_git_repo(tmp_path)
    source = GitTagVersionSource(project_root)

    with pytest.raises(VersionNotFoundError):
        source.read()


def test_read_raises_versionnotfounderror_for_malformed_tag(tmp_path: Path) -> None:
    """A tag that does not match the semver regex is treated as 'no version found'."""
    project_root = init_git_repo(tmp_path, tag="not-a-version")
    source = GitTagVersionSource(project_root)

    with pytest.raises(VersionNotFoundError):
        source.read()


def test_read_rejects_tag_starting_with_double_dash(tmp_path: Path) -> None:
    """A tag beginning with ``--`` is rejected before being passed to ``git``.

    This guards against arg-injection via a crafted tag name. The rejection
    happens at the validation layer, so ``git describe`` is never invoked
    with attacker-controlled content.
    """
    project_root = init_git_repo(tmp_path)
    # Bypass ``git tag``'s own validation by writing the ref directly.
    import subprocess

    subprocess.run(
        [
            "git",
            "update-ref",
            "refs/tags/--upload-pack=foo",
            "HEAD",
        ],
        cwd=project_root,
        check=True,
    )

    source = GitTagVersionSource(project_root)

    with pytest.raises(VersionNotFoundError):
        source.read()


def test_read_handles_pre_release_suffix(tmp_path: Path) -> None:
    """A tag like ``v1.2.3-rc1`` is read as ``1.2.3-rc1``."""
    project_root = init_git_repo(tmp_path, tag="v1.2.3-rc1")
    source = GitTagVersionSource(project_root)

    assert source.read() == "1.2.3-rc1"


def test_write_is_a_no_op_for_phase_two(tmp_path: Path) -> None:
    """Per spec Swift F1, ``write`` is a no-op for v1.

    The Swift adapter treats the git tag as the source of truth; the Lifecycle
    invokes ``_reset`` to undo version bumps rather than rewriting a manifest.
    ``write`` therefore accepts the new version but does not modify the repo,
    and the next ``read`` still reports the existing tag.
    """
    project_root = init_git_repo(tmp_path, tag="v1.0.0")
    source = GitTagVersionSource(project_root)

    source.write("9.9.9")  # must not raise

    # Subsequent read still sees the original tag.
    assert source.read() == "1.0.0"

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.base import LifecycleOptions
from crackerjack.adapters.swift.lifecycle import SwiftLifecycle, _bump
from crackerjack.adapters.swift.version_source import GitTagVersionSource
from tests.adapters.swift._git_helpers import init_git_repo

# --- Pure-function tests ---


def test_bump_minor() -> None:
    assert _bump("1.2.3", "minor") == "1.3.0"
    assert _bump("0.1.0", "minor") == "0.2.0"


def test_bump_major() -> None:
    # Pre-1.0 semantics: "major" bumps minor (per docstring on _bump).
    assert _bump("1.2.3", "major") == "1.3.0"
    assert _bump("0.1.0", "major") == "0.2.0"


def test_bump_patch() -> None:
    assert _bump("1.2.3", "patch") == "1.2.4"
    assert _bump("0.1.0", "patch") == "0.1.1"


def test_bump_rejects_invalid_level() -> None:
    with pytest.raises(ValueError):
        _bump("1.0.0", "epic")  # type: ignore[arg-type]


# --- Lifecycle tests with constructor-injected fakes ---


def _make_lifecycle(tmp_path: Path, tag: str = "v1.0.0"):
    init_git_repo(tmp_path, tag=tag)
    version_source = GitTagVersionSource(tmp_path)
    return version_source, SwiftLifecycle(
        version_source=version_source,
        project_root=tmp_path,
        commit=mock.Mock(return_value="abc123"),
        tag=mock.Mock(),
        push=mock.Mock(),
        delete_tag=mock.Mock(),
        reset=mock.Mock(),
        gh_release=mock.Mock(return_value="https://github.com/x/y/releases/tag/v1.1.0"),
    )


def test_swift_lifecycle_run_dry_run_does_not_mutate(tmp_path: Path) -> None:
    _version_source, lifecycle = _make_lifecycle(tmp_path)
    result = lifecycle.run(LifecycleOptions(level="minor", dry_run=True))

    assert result.new_version == "1.1.0"
    assert "dry_run" in result.skipped_steps
    assert result.commit_sha is None
    assert result.tag_name is None


def test_swift_lifecycle_run_minor_bumps_tags_pushes(tmp_path: Path) -> None:
    _version_source, lifecycle = _make_lifecycle(tmp_path)
    result = lifecycle.run(LifecycleOptions(level="minor"))

    assert result.new_version == "1.1.0"
    assert result.commit_sha == "abc123"
    assert result.tag_name == "v1.1.0"
    lifecycle._commit.assert_called_once()
    lifecycle._tag.assert_called_once_with("v1.1.0", message="Release v1.1.0")
    lifecycle._push.assert_called_once_with("abc123", "v1.1.0")


def test_swift_lifecycle_run_minor_with_release_creates_release(tmp_path: Path) -> None:
    _version_source, lifecycle = _make_lifecycle(tmp_path)
    result = lifecycle.run(LifecycleOptions(level="minor", release=True))

    assert result.release_url == "https://github.com/x/y/releases/tag/v1.1.0"
    lifecycle._gh_release.assert_called_once_with("v1.1.0")


def test_swift_lifecycle_rollback_on_push_failure(tmp_path: Path) -> None:
    _version_source, lifecycle = _make_lifecycle(tmp_path)
    lifecycle._push.side_effect = RuntimeError("network")

    with pytest.raises(RuntimeError, match="network"):
        lifecycle.run(LifecycleOptions(level="minor"))

    lifecycle._delete_tag.assert_called_once_with("v1.1.0")
    lifecycle._reset.assert_called_once_with("abc123")


def test_swift_lifecycle_rollback_on_gh_release_failure(tmp_path: Path) -> None:
    """Per MEDIUM M5: _gh_release failure must also trigger rollback."""
    _version_source, lifecycle = _make_lifecycle(tmp_path)
    lifecycle._gh_release.side_effect = RuntimeError("gh auth expired")

    with pytest.raises(RuntimeError, match="gh auth expired"):
        lifecycle.run(LifecycleOptions(level="minor", release=True))

    lifecycle._delete_tag.assert_called_once_with("v1.1.0")
    lifecycle._reset.assert_called_once_with("abc123")


def test_swift_lifecycle_rejects_invalid_level(tmp_path: Path) -> None:
    """Per MEDIUM M2: invalid level values raise ValueError."""
    _version_source, lifecycle = _make_lifecycle(tmp_path)
    with pytest.raises(ValueError, match="level must be"):
        lifecycle.run(LifecycleOptions(level="epic"))  # type: ignore[arg-type]


def test_swift_lifecycle_does_not_mutate_package_swift(tmp_path: Path) -> None:
    """Per spec Swift F1: v1 does not mutate Package.swift."""
    init_git_repo(tmp_path, tag="v1.0.0")
    (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9\n")
    original = (tmp_path / "Package.swift").read_text()

    vs = GitTagVersionSource(tmp_path)
    lifecycle = SwiftLifecycle(
        version_source=vs,
        project_root=tmp_path,
        commit=mock.Mock(return_value="abc123"),
        tag=mock.Mock(),
        push=mock.Mock(),
        delete_tag=mock.Mock(),
        reset=mock.Mock(),
        gh_release=mock.Mock(return_value="https://github.com/x/y/releases/tag/v1.1.0"),
    )
    lifecycle.run(LifecycleOptions(level="minor"))

    assert (tmp_path / "Package.swift").read_text() == original

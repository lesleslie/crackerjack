"""Tests for the Kotlin adapter lifecycle implementation.

Covers real-semver bump semantics (with pre-release qualifier preservation),
dry_run ordering (no file mutation), and gradle.properties snapshot/restore on
rollback. Phase 3 Rev 2 fixes — see :mod:`crackerjack.adapters.kotlin.lifecycle`.
"""
from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.base import LifecycleOptions
from crackerjack.adapters.kotlin.lifecycle import KotlinLifecycle, _bump
from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource


def test_bump_major_real_semver() -> None:
    assert _bump("1.2.3", "major") == "2.0.0"


def test_bump_minor_real_semver() -> None:
    assert _bump("1.2.3", "minor") == "1.3.0"


def test_bump_patch() -> None:
    assert _bump("1.2.3", "patch") == "1.2.4"


def test_bump_major_from_zero() -> None:
    assert _bump("0.1.0", "major") == "1.0.0"


def test_bump_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="level must be"):
        _bump("1.2.3", "epic")


def _make_lifecycle(tmp_path: Path) -> tuple[GradlePropertiesVersionSource, KotlinLifecycle]:
    (tmp_path / "gradle.properties").write_text("version=1.2.3\n")
    src = GradlePropertiesVersionSource(tmp_path)
    commit = mock.Mock(return_value="abc123def456" + "0" * 32)
    tag = mock.Mock()
    push = mock.Mock()
    delete_tag = mock.Mock()
    reset = mock.Mock()
    gh_release = mock.Mock(return_value="https://example.com/v1.3.0")
    lifecycle = KotlinLifecycle(
        version_source=src,
        project_root=tmp_path,
        commit=commit,
        tag=tag,
        push=push,
        delete_tag=delete_tag,
        reset=reset,
        gh_release=gh_release,
    )
    return src, lifecycle


def test_kotlin_lifecycle_run_dry_run_does_not_mutate(tmp_path: Path) -> None:
    """Per spec Error Handling: dry_run=True skips ALL mutations.

    Per CRITICAL-1 (Security F-3 + API CRITICAL #1): the gradle.properties
    file MUST NOT be rewritten when dry_run=True. This test asserts both
    the LifecycleResult shape AND the file's unchanged content.
    """
    src, lifecycle = _make_lifecycle(tmp_path)
    original = (tmp_path / "gradle.properties").read_text()
    result = lifecycle.run(LifecycleOptions(level="minor", dry_run=True))
    assert result.new_version == "1.3.0"
    assert result.commit_sha is None
    assert result.tag_name is None
    assert "dry_run" in result.skipped_steps
    # gradle.properties untouched (API CRITICAL #1)
    assert (tmp_path / "gradle.properties").read_text() == original
    lifecycle._commit.assert_not_called()
    lifecycle._tag.assert_not_called()
    lifecycle._push.assert_not_called()


def test_kotlin_lifecycle_run_minor_bumps_gradle_properties_tags_pushes(tmp_path: Path) -> None:
    src, lifecycle = _make_lifecycle(tmp_path)
    result = lifecycle.run(LifecycleOptions(level="minor"))
    assert result.new_version == "1.3.0"
    # gradle.properties was rewritten
    assert src.read() == "1.3.0"
    lifecycle._tag.assert_called_once_with("v1.3.0", mock.ANY)


def test_kotlin_lifecycle_rollback_on_push_failure(tmp_path: Path) -> None:
    """Per API CRITICAL #2: rollback must restore both git state AND gradle.properties."""
    src, lifecycle = _make_lifecycle(tmp_path)
    lifecycle._push.side_effect = RuntimeError("network down")
    with pytest.raises(RuntimeError, match="network down"):
        lifecycle.run(LifecycleOptions(level="minor"))
    # gradle.properties rolled back to original
    assert src.read() == "1.2.3"
    lifecycle._delete_tag.assert_called_once_with("v1.3.0")
    lifecycle._reset.assert_called_once()


def test_kotlin_lifecycle_rollback_on_commit_failure_restores_gradle_properties(tmp_path: Path) -> None:
    """Per API CRITICAL #2: if _commit fails AFTER write succeeded,
    rollback must restore gradle.properties (the uncommitted file change
    that _reset cannot undo, since _reset targets a prior commit)."""
    src, lifecycle = _make_lifecycle(tmp_path)
    lifecycle._commit.side_effect = RuntimeError("commit failed")
    with pytest.raises(RuntimeError, match="commit failed"):
        lifecycle.run(LifecycleOptions(level="minor"))
    # gradle.properties rolled back
    assert src.read() == "1.2.3"
    # No tag was created (commit failed before tag step)
    lifecycle._tag.assert_not_called()
    lifecycle._push.assert_not_called()


def test_bump_preserves_snapshot_qualifier() -> None:
    """Kotlin BLOCKER #1: real Kotlin projects use -SNAPSHOT, -RC1, etc."""
    assert _bump("1.2.3-SNAPSHOT", "minor") == "1.3.0-SNAPSHOT"


def test_bump_preserves_rc_qualifier() -> None:
    assert _bump("2.0.0-RC1", "major") == "3.0.0-RC1"


def test_bump_preserves_build_metadata() -> None:
    assert _bump("1.2.3+build.5", "patch") == "1.2.4+build.5"


def test_bump_rejects_invalid_semver() -> None:
    """Kotlin BLOCKER #1 follow-up: must raise on malformed input."""
    with pytest.raises(ValueError, match="not valid semver"):
        _bump("not-a-version", "minor")


def test_lifecycle_options_rejects_invalid_level() -> None:
    """Per Phase 2 final-review M-3 fix: LifecycleOptions.__post_init__ raises
    during construction. KotlinLifecycle.run does NOT re-validate (Phase 2
    ruling carried forward). This test asserts the construction-time validation.
    """
    with pytest.raises(ValueError, match="level must be"):
        LifecycleOptions(level="epic")


def test_kotlin_lifecycle_writes_gradle_properties_only_not_build_script(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text('version = "1.2.3"\n')
    (tmp_path / "gradle.properties").write_text("version=1.2.3\n")
    src = GradlePropertiesVersionSource(tmp_path)
    lifecycle = KotlinLifecycle(
        version_source=src,
        project_root=tmp_path,
        commit=mock.Mock(return_value="a" * 40),
        tag=mock.Mock(),
        push=mock.Mock(),
        delete_tag=mock.Mock(),
        reset=mock.Mock(),
        gh_release=mock.Mock(return_value=""),
    )
    lifecycle.run(LifecycleOptions(level="minor"))
    # build.gradle.kts untouched
    assert (tmp_path / "build.gradle.kts").read_text() == 'version = "1.2.3"\n'
"""Tests for crackerjack.checks.gitignore_conformance."""
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.checks.gitignore_conformance import (
    MARKER_BEGIN,
    MARKER_END,
    TEMPLATE_PATH,
    _bodai_fleet_paths,
    _parse_canonical_template,
    check_repo_gitignore,
    is_bodai_fleet_member,
    is_canonical_template_single_source,
    sync_repo_gitignore,
)


@pytest.fixture
def fleet_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A Bodai fleet repo with the canonical snippet already installed."""
    repo = tmp_path / "fleet_repo"
    repo.mkdir()
    # Force the registry lookup to recognise this path by registering it
    # via the module-level cache reset hook.
    monkeypatch.setattr(
        "crackerjack.checks.gitignore_conformance._bodai_fleet_paths",
        lambda: frozenset({repo.resolve()}),
    )
    # Re-seed the cached lookup so check_repo_gitignore sees the override.
    _bodai_fleet_paths.cache_clear()
    snippet = TEMPLATE_PATH.read_text()
    (repo / ".gitignore").write_text(snippet)
    return repo


@pytest.fixture
def non_fleet_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A non-Bodai repo (not in the registry)."""
    repo = tmp_path / "non_fleet"
    repo.mkdir()
    monkeypatch.setattr(
        "crackerjack.checks.gitignore_conformance._bodai_fleet_paths",
        lambda: frozenset(),
    )
    _bodai_fleet_paths.cache_clear()
    return repo


def test_canonical_template_exists_and_has_markers() -> None:
    """The single source of truth at TEMPLATE_PATH must include both markers."""
    assert is_canonical_template_single_source()
    canonical = _parse_canonical_template(TEMPLATE_PATH)
    assert canonical, "Template must contain at least one pattern"
    assert all(p and not p.startswith("#") for p in canonical)


def test_fleet_repo_with_snippet_passes(fleet_repo: Path) -> None:
    result = check_repo_gitignore(fleet_repo)
    assert result.is_fleet_member
    assert result.snippet_present
    assert result.missing_patterns == []


def test_fleet_repo_without_snippet_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "no_snippet"
    repo.mkdir()
    (repo / ".gitignore").write_text("# only project-specific patterns\n__pycache__/\n")
    monkeypatch.setattr(
        "crackerjack.checks.gitignore_conformance._bodai_fleet_paths",
        lambda: frozenset({repo.resolve()}),
    )
    _bodai_fleet_paths.cache_clear()
    result = check_repo_gitignore(repo)
    assert result.is_fleet_member
    assert not result.snippet_present
    assert result.missing_patterns  # at least one pattern reported


def test_fleet_repo_with_partial_drift_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Snippet block exists but a canonical pattern was hand-edited out."""
    repo = tmp_path / "drifted_repo"
    repo.mkdir()
    drifted = TEMPLATE_PATH.read_text().replace("*.bak\n", "")
    (repo / ".gitignore").write_text(drifted)
    monkeypatch.setattr(
        "crackerjack.checks.gitignore_conformance._bodai_fleet_paths",
        lambda: frozenset({repo.resolve()}),
    )
    _bodai_fleet_paths.cache_clear()
    result = check_repo_gitignore(repo)
    assert result.is_fleet_member
    assert result.snippet_present
    assert "*.bak" in result.missing_patterns


def test_non_fleet_repo_is_skipped(non_fleet_repo: Path) -> None:
    result = check_repo_gitignore(non_fleet_repo)
    assert not result.is_fleet_member
    assert result.snippet_present  # skipped silently = pass


def test_sync_installs_snippet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "needs_sync"
    repo.mkdir()
    monkeypatch.setattr(
        "crackerjack.checks.gitignore_conformance._bodai_fleet_paths",
        lambda: frozenset({repo.resolve()}),
    )
    _bodai_fleet_paths.cache_clear()
    result = sync_repo_gitignore(repo)
    assert result.is_fleet_member
    assert result.snippet_present
    assert result.missing_patterns == []
    assert result.backup_path is None  # no existing .gitignore, so no backup
    body = (repo / ".gitignore").read_text()
    assert MARKER_BEGIN in body
    assert MARKER_END in body


def test_sync_preserves_project_specific_patterns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "preserve_me"
    repo.mkdir()
    (repo / ".gitignore").write_text("__pycache__/\nmy_special_local_dir/\n")
    monkeypatch.setattr(
        "crackerjack.checks.gitignore_conformance._bodai_fleet_paths",
        lambda: frozenset({repo.resolve()}),
    )
    _bodai_fleet_paths.cache_clear()
    sync_repo_gitignore(repo)
    body = (repo / ".gitignore").read_text()
    assert "__pycache__/" in body
    assert "my_special_local_dir/" in body
    assert MARKER_BEGIN in body


def test_sync_writes_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "backup_me"
    repo.mkdir()
    original = "ORIGINAL CONTENT\n"
    (repo / ".gitignore").write_text(original)
    monkeypatch.setattr(
        "crackerjack.checks.gitignore_conformance._bodai_fleet_paths",
        lambda: frozenset({repo.resolve()}),
    )
    _bodai_fleet_paths.cache_clear()
    result = sync_repo_gitignore(repo)
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert result.backup_path.read_text() == original
    assert result.backup_path.name.startswith(".gitignore.bak.")


def test_sync_refuses_non_bodai(non_fleet_repo: Path) -> None:
    """Sync must not mutate non-Bodai repos."""
    (non_fleet_repo / ".gitignore").write_text("untouched\n")
    result = sync_repo_gitignore(non_fleet_repo)
    assert not result.is_fleet_member
    assert (non_fleet_repo / ".gitignore").read_text() == "untouched\n"


def test_sync_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running sync twice produces the same final state (no duplicated block)."""
    repo = tmp_path / "idempotent"
    repo.mkdir()
    monkeypatch.setattr(
        "crackerjack.checks.gitignore_conformance._bodai_fleet_paths",
        lambda: frozenset({repo.resolve()}),
    )
    _bodai_fleet_paths.cache_clear()
    sync_repo_gitignore(repo, backup=False)
    body_after_first = (repo / ".gitignore").read_text()
    sync_repo_gitignore(repo, backup=False)
    body_after_second = (repo / ".gitignore").read_text()
    assert body_after_first == body_after_second
    assert body_after_first.count(MARKER_BEGIN) == 1
    assert body_after_first.count(MARKER_END) == 1


def test_is_bodai_fleet_member_recognises_registry(tmp_path: Path) -> None:
    """Sanity check: a path outside the registry is not a fleet member."""
    outside = tmp_path / "totally_unrelated"
    outside.mkdir()
    assert not is_bodai_fleet_member(outside)


def test_fleet_membership_lookup_handles_missing_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the registry file is missing, the check should not crash."""
    monkeypatch.setattr(
        "crackerjack.checks.gitignore_conformance.BODAI_REGISTRY_PATH",
        tmp_path / "does_not_exist.md",
    )
    _bodai_fleet_paths.cache_clear()
    assert _bodai_fleet_paths() == frozenset()
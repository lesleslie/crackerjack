"""Tests for crackerjack.checks.release_audit."""
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.checks.release_audit import check_release_audit

FIXTURES = Path("/Users/les/Projects/mcp-common/tests/release_audit/fixtures")


@pytest.fixture
def good_project(tmp_path: Path) -> Path:
    """Symlink the fixtures into a tmp dir for test isolation."""
    import shutil
    dst = tmp_path / "fixtures"
    shutil.copytree(FIXTURES, dst)
    return dst


def test_all_claims_valid(good_project: Path) -> None:
    """When CHANGELOG and CLAUDE.md claims match reality, report passes."""
    report = check_release_audit(
        project_root=good_project,
        changelog_path=good_project / "good_changelog.md",
        claude_md_path=good_project / "good_claude.md",
        pyproject_path=good_project / "pyproject.toml",
        ratchet_path=good_project / "ratchet.json",
        source_root=good_project / "source_root",
        test_root=good_project,
    )
    errors = [r for r in report.results if not r.passed]
    assert not errors, f"unexpected failures: {[r.message for r in errors]}"
    assert report.passed is True


def test_missing_symbol_claim_fails(good_project: Path) -> None:
    report = check_release_audit(
        project_root=good_project,
        changelog_path=good_project / "missing_symbol_changelog.md",
        claude_md_path=good_project / "good_claude.md",
        pyproject_path=good_project / "pyproject.toml",
        ratchet_path=good_project / "ratchet.json",
        source_root=good_project / "source_root",
        test_root=good_project,
    )
    assert not report.passed
    assert any("NonExistent" in r.message for r in report.results)


def test_lingering_symbol_claim_fails(good_project: Path) -> None:
    report = check_release_audit(
        project_root=good_project,
        changelog_path=good_project / "lingering_symbol_changelog.md",
        claude_md_path=good_project / "good_claude.md",
        pyproject_path=good_project / "pyproject.toml",
        ratchet_path=good_project / "ratchet.json",
        source_root=good_project / "source_root",
        test_root=good_project,
    )
    assert not report.passed
    assert any("new_method" in r.message and "removed" in r.message for r in report.results)


def test_wrong_version_fails(good_project: Path) -> None:
    report = check_release_audit(
        project_root=good_project,
        changelog_path=good_project / "good_changelog.md",
        claude_md_path=good_project / "wrong_version_claude.md",
        pyproject_path=good_project / "pyproject.toml",
        ratchet_path=good_project / "ratchet.json",
        source_root=good_project / "source_root",
        test_root=good_project,
    )
    assert not report.passed
    assert any("version" in r.message.lower() for r in report.results)


def test_wrong_coverage_fails(good_project: Path) -> None:
    report = check_release_audit(
        project_root=good_project,
        changelog_path=good_project / "good_changelog.md",
        claude_md_path=good_project / "wrong_coverage_claude.md",
        pyproject_path=good_project / "pyproject.toml",
        ratchet_path=good_project / "ratchet.json",
        source_root=good_project / "source_root",
        test_root=good_project,
    )
    assert not report.passed
    assert any("coverage" in r.message.lower() for r in report.results)


def test_wrong_test_count_fails(good_project: Path) -> None:
    report = check_release_audit(
        project_root=good_project,
        changelog_path=good_project / "good_changelog.md",
        claude_md_path=good_project / "wrong_count_claude.md",
        pyproject_path=good_project / "pyproject.toml",
        ratchet_path=good_project / "ratchet.json",
        source_root=good_project / "source_root",
        test_root=good_project,
    )
    assert not report.passed
    assert any("999" in r.message and "tests" in r.message for r in report.results)


def test_missing_path_fails(good_project: Path) -> None:
    report = check_release_audit(
        project_root=good_project,
        changelog_path=good_project / "good_changelog.md",
        claude_md_path=good_project / "missing_path_claude.md",
        pyproject_path=good_project / "pyproject.toml",
        ratchet_path=good_project / "ratchet.json",
        source_root=good_project / "source_root",
        test_root=good_project,
    )
    assert not report.passed
    assert any("does_not_exist" in r.message for r in report.results)


def test_empty_inputs_pass(good_project: Path) -> None:
    """Empty CHANGELOG + CLAUDE.md produces no claims → passes."""
    report = check_release_audit(
        project_root=good_project,
        changelog_path=good_project / "empty_changelog.md",
        claude_md_path=good_project / "empty_claude.md",
        pyproject_path=good_project / "pyproject.toml",
        ratchet_path=good_project / "ratchet.json",
        source_root=good_project / "source_root",
        test_root=good_project,
    )
    assert report.passed


def test_malformed_changelog_does_not_crash(good_project: Path) -> None:
    """Malformed CHANGELOG (no ### Added/### Removed headers) → no CHANGELOG claims, passes."""
    report = check_release_audit(
        project_root=good_project,
        changelog_path=good_project / "malformed_changelog.md",
        claude_md_path=good_project / "good_claude.md",
        pyproject_path=good_project / "pyproject.toml",
        ratchet_path=good_project / "ratchet.json",
        source_root=good_project / "source_root",
        test_root=good_project,
    )
    assert report.passed

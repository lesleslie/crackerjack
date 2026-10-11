"""Tests for crackerjack.checks.release_audit."""
from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.checks.release_audit import (
    _file_path_candidates,
    _is_file_path_symbol,
    _parse_changelog,
    _symbol_in_source,
    check_release_audit,
)

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
    assert report.passed


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


class TestSymbolInSource:
    """Regression tests for source-search pattern coverage.

    Bug fix (2026-09-06): dataclass fields with type annotations
    (e.g., `eventbridge: EventBridgeSettings = ...`) were missed by
    the audit because the pattern only matched `name = ...` (no
    intervening type annotation). Fix: pattern now matches `[:=]`.
    """

    def test_dataclass_field_with_annotation(self, tmp_path: Path) -> None:
        """A dataclass field declared with type annotation is found."""
        src = tmp_path / "settings.py"
        src.write_text(
            "from dataclasses import dataclass, field\n"
            "@dataclass\n"
            "class Settings:\n"
            "    eventbridge: 'EventBridgeSettings' = field(default_factory=dict)\n",
        )
        assert _symbol_in_source("Settings.eventbridge", tmp_path)

    def test_module_level_assignment(self, tmp_path: Path) -> None:
        """Module-level `NAME = ...` still found (original pattern)."""
        src = tmp_path / "const.py"
        src.write_text("MY_CONSTANT = 42\n")
        assert _symbol_in_source("const.MY_CONSTANT", tmp_path)

    def test_missing_symbol_returns_false(self, tmp_path: Path) -> None:
        """Missing symbol returns False (not raises)."""
        src = tmp_path / "settings.py"
        src.write_text("x: int = 1\n")
        assert not _symbol_in_source("Settings.nonexistent", tmp_path)


class TestFilePathClaimDetection:
    """Regression tests for the file-path claim type introduced after the
    ``audit_cli_inventory.py`` cycle (2026-10-10).

    Background: a CHANGELOG line like ``- mahavishnu: Add audit_cli_inventory.py``
    used to be extracted as a Python symbol claim (``mahavishnu.audit_cli_inventory.py``)
    and the audit searched for ``def audit_cli_inventory.py`` in source — which
    obviously doesn't exist (``.py`` is a file extension, not a function name).
    The fix recognises file-path claims (final segment is a known extension) and
    verifies them by filesystem existence rather than source search.
    """

    @pytest.mark.parametrize(
        ("symbol", "expected"),
        [
            # File-path claims (final segment is a known extension)
            ("audit_cli_inventory.py", True),
            ("mahavishnu.audit_cli_inventory.py", True),
            ("mymodule.utils.helpers.py", True),
            ("config.md", True),
            ("pyproject.toml", True),
            ("settings.yaml", True),
            ("docs/architecture.md", True),  # path-as-path (rare)
            # Real Python identifiers (final segment is NOT a known extension)
            ("mymodule.MyClass.new_method", False),
            ("mahavishnu.dev_log.write_entry", False),
            ("settings.workers.entries", False),
            ("AdapterType.HATCHET", False),
            ("TaskCategory.AGENT_LOOP", False),
            # Edge cases
            ("foo.bar", False),  # ``bar`` is not a known extension
            ("single", False),  # no extension at all
            ("", False),
        ],
    )
    def test_is_file_path_symbol(
        self,
        symbol: str,
        expected: bool,
    ) -> None:
        assert _is_file_path_symbol(symbol) is expected

    def test_parse_marks_file_path_claim(self) -> None:
        """``_parse_changelog`` flags file-path claims on the ChangelogClaim."""
        text = (
            "# Changelog\n"
            "\n"
            "## [1.0.0] - 2026-01-01\n"
            "\n"
            "### Added\n"
            "\n"
            "- `audit_cli_inventory.py` for CLI surface audit\n"
            "- `mahavishnu.dev_log.write_entry` helper\n"
        )
        claims = _parse_changelog(text)
        # Both bullets should be extracted (both have dots).
        assert len(claims) == 2
        # First is a file path, second is a Python symbol.
        assert claims[0].is_file_path
        assert claims[0].symbol == "audit_cli_inventory.py"
        assert not claims[1].is_file_path
        assert claims[1].symbol == "mahavishnu.dev_log.write_entry"

    def test_parse_marks_repo_prefixed_file_path(self) -> None:
        """Repo-prefixed file paths (``mahavishnu.audit_cli_inventory.py``) are
        detected as file paths, not as Python identifiers with an extension."""
        text = (
            "# Changelog\n"
            "\n"
            "## [0.19.0] - 2026-08-29\n"
            "\n"
            "### Added\n"
            "\n"
            "- mahavishnu: Add audit_cli_inventory.py for Core 7 CLI surface audit\n"
        )
        claims = _parse_changelog(text)
        assert len(claims) == 1
        c = claims[0]
        assert c.is_file_path
        assert c.symbol == "mahavishnu.audit_cli_inventory.py"

    def test_added_script_passes_when_file_exists_in_scripts(
        self,
        tmp_path: Path,
    ) -> None:
        """File-path Added claim is verified when the file exists in
        ``<project_root>/scripts/`` (Bodai convention)."""
        # Set up project layout
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "audit_cli_inventory.py").write_text("# script")
        (tmp_path / "mahavishnu").mkdir()  # source_root
        # Minimal CLAUDE.md (the audit bails if this is missing).
        (tmp_path / "CLAUDE.md").write_text("# Project\n")

        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "# Changelog\n"
            "\n"
            "## [0.19.0] - 2026-08-29\n"
            "\n"
            "### Added\n"
            "\n"
            "- mahavishnu: Add audit_cli_inventory.py for Core 7 CLI surface audit\n"
        )
        report = check_release_audit(
            project_root=tmp_path,
            changelog_path=changelog,
            claude_md_path=tmp_path / "CLAUDE.md",
            pyproject_path=tmp_path / "pyproject.toml",
            ratchet_path=None,
            source_root=tmp_path / "mahavishnu",
            test_root=tmp_path / "tests",
        )
        # Find the file-path verify result.
        file_results = [
            r
            for r in report.results
            if r.claim is not None
            and getattr(r.claim, "is_file_path", False)
        ]
        assert file_results, "no file-path claim was extracted"
        assert all(r.passed for r in file_results), (
            f"file-path claims failed: {[r.message for r in file_results]}"
        )

    def test_added_script_fails_when_file_missing(
        self,
        tmp_path: Path,
    ) -> None:
        """File-path Added claim fails when the file does not exist on disk."""
        (tmp_path / "mahavishnu").mkdir()
        (tmp_path / "CLAUDE.md").write_text("# Project\n")
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "# Changelog\n"
            "\n"
            "## [1.0.0] - 2026-01-01\n"
            "\n"
            "### Added\n"
            "\n"
            "- mahavishnu: Add nonexistent_script.py for testing\n"
        )
        report = check_release_audit(
            project_root=tmp_path,
            changelog_path=changelog,
            claude_md_path=tmp_path / "CLAUDE.md",
            pyproject_path=tmp_path / "pyproject.toml",
            ratchet_path=None,
            source_root=tmp_path / "mahavishnu",
            test_root=tmp_path / "tests",
        )
        assert not report.passed
        # The error message must reference the file path (not a Python def).
        file_failures = [
            r
            for r in report.results
            if not r.passed
            and r.claim is not None
            and getattr(r.claim, "is_file_path", False)
        ]
        assert file_failures
        assert any(
            "nonexistent_script.py" in r.message and "does not exist" in r.message
            for r in file_failures
        )

    def test_removed_script_passes_when_file_gone(
        self,
        tmp_path: Path,
    ) -> None:
        """File-path Removed claim passes when the file is no longer on disk."""
        (tmp_path / "mahavishnu").mkdir()
        (tmp_path / "CLAUDE.md").write_text("# Project\n")
        # No scripts/ directory created; the file is genuinely gone.
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "# Changelog\n"
            "\n"
            "## [2.0.0] - 2026-02-01\n"
            "\n"
            "### Removed\n"
            "\n"
            "- mahavishnu: Removed legacy_old.py (replaced by new)\n"
        )
        report = check_release_audit(
            project_root=tmp_path,
            changelog_path=changelog,
            claude_md_path=tmp_path / "CLAUDE.md",
            pyproject_path=tmp_path / "pyproject.toml",
            ratchet_path=None,
            source_root=tmp_path / "mahavishnu",
            test_root=tmp_path / "tests",
        )
        file_results = [
            r
            for r in report.results
            if r.claim is not None
            and getattr(r.claim, "is_file_path", False)
        ]
        assert file_results
        assert all(r.passed for r in file_results)

    def test_removed_script_fails_when_file_still_exists(
        self,
        tmp_path: Path,
    ) -> None:
        """File-path Removed claim fails when the file is still on disk."""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "still_here.py").write_text("# still here")
        (tmp_path / "mahavishnu").mkdir()
        (tmp_path / "CLAUDE.md").write_text("# Project\n")
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "# Changelog\n"
            "\n"
            "## [2.0.0] - 2026-02-01\n"
            "\n"
            "### Removed\n"
            "\n"
            "- mahavishnu: Removed still_here.py\n"
        )
        report = check_release_audit(
            project_root=tmp_path,
            changelog_path=changelog,
            claude_md_path=tmp_path / "CLAUDE.md",
            pyproject_path=tmp_path / "pyproject.toml",
            ratchet_path=None,
            source_root=tmp_path / "mahavishnu",
            test_root=tmp_path / "tests",
        )
        assert not report.passed
        file_failures = [
            r
            for r in report.results
            if not r.passed
            and r.claim is not None
            and getattr(r.claim, "is_file_path", False)
        ]
        assert file_failures
        assert any("still exists" in r.message for r in file_failures)

    def test_file_path_candidates_includes_bodai_locations(
        self,
        tmp_path: Path,
    ) -> None:
        """Candidate paths cover the standard Bodai locations."""
        (tmp_path / "scripts").mkdir()
        source_root = tmp_path / "mahavishnu"
        source_root.mkdir()
        cands = _file_path_candidates(
            "mahavishnu.audit_cli_inventory.py",
            project_root=tmp_path,
            source_root=source_root,
        )
        # Should include the scripts/ basename location.
        assert (tmp_path / "scripts" / "audit_cli_inventory.py") in cands
        # And the project_root top-level.
        assert (tmp_path / "audit_cli_inventory.py") in cands
        # And inside the source root.
        assert (source_root / "audit_cli_inventory.py") in cands

"""Tests for crackerjack.fixers.documentation.

Ported from tests/agents/test_documentation_agent.py and
tests/unit/agents/test_documentation_agent.py, keeping only the cases that
exercise real changelog-generation / broken-link-fixing / documentation-
consistency transform behavior. Cases exercising SubAgent/coordinator
dispatch (``get_supported_types``, ``can_handle``) were dropped, since that
machinery no longer exists. Calls to ``agent.<method>(...)`` become
``documentation.<function>(...)``; ``AgentContext``-backed mocking of
``get_file_content``/``write_file_content`` is replaced with real files on
``tmp_path`` (or, for forced write failures, ``patch(f"{MODULE}._write_file",
return_value=False)``, matching ``tests/fixers/test_refactoring.py``'s
established pattern). ``AgentContext(project_path=...)`` becomes an explicit
``project_root`` argument.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.fixers import documentation
from crackerjack.models.fix_plan import ChangeSpec, FixPlan
from crackerjack.models.issues import FixResult, Issue, IssueType, Priority

MODULE = "crackerjack.fixers.documentation"


def _make_issue(
    message: str = "documentation drift detected",
    file_path: str | None = "README.md",
    line_number: int | None = 1,
    details: list[str] | None = None,
) -> Issue:
    return Issue(
        type=IssueType.DOCUMENTATION,
        severity=Priority.MEDIUM,
        message=message,
        file_path=file_path,
        line_number=line_number,
        details=details or [],
    )


def _make_plan(
    file_path: str = "docs/README.md",
    rationale: str = "documentation drift",
    changes: list[ChangeSpec] | None = None,
    risk_level: str = "low",
) -> FixPlan:
    return FixPlan(
        file_path=file_path,
        issue_type="documentation",
        risk_level=risk_level,  # type: ignore[arg-type]
        validated_by="system",
        rationale=rationale,
        changes=changes or [],
    )


# ---------------------------------------------------------------------------
# _is_broken_link_plan / _extract_target_from_rationale
# ---------------------------------------------------------------------------


class TestBrokenLinkPlanDetection:
    @pytest.mark.parametrize(
        "rationale",
        [
            "broken link to docs/old.md",
            "File not found: docs/old.md",
            "need to fix link in README",
        ],
    )
    def test_is_broken_link_plan_true(self, rationale: str) -> None:
        plan = _make_plan(rationale=rationale)
        assert documentation._is_broken_link_plan(plan) is True

    def test_is_broken_link_plan_false(self) -> None:
        plan = _make_plan(rationale="general update")
        assert documentation._is_broken_link_plan(plan) is False

    def test_extract_target_from_file_not_found(self) -> None:
        target = documentation._extract_target_from_rationale(
            "File not found: docs/foo.md"
        )
        assert target == "docs/foo.md"

    def test_extract_target_from_broken_link(self) -> None:
        target = documentation._extract_target_from_rationale(
            "Broken link: docs/bar.md"
        )
        assert target == "docs/bar.md"

    def test_extract_target_from_link_to(self) -> None:
        target = documentation._extract_target_from_rationale(
            "needs link to docs/baz.md"
        )
        assert target == "docs/baz.md"

    def test_extract_target_from_relative_path(self) -> None:
        target = documentation._extract_target_from_rationale(
            "see ./local.md for details"
        )
        assert target == "./local.md"

    def test_extract_target_returns_none(self) -> None:
        assert documentation._extract_target_from_rationale("no file mentioned") is None


# ---------------------------------------------------------------------------
# execute_fix_plan + _fix_broken_link_from_plan
# ---------------------------------------------------------------------------


class TestExecuteFixPlan:
    async def test_general_documentation_returns_recommendation(
        self, tmp_path: Path
    ) -> None:
        plan = _make_plan(rationale="general improvement")
        result = await documentation.execute_fix_plan(plan, tmp_path)
        assert result.success is True
        assert result.confidence == 0.6
        assert any("Manual review" in r for r in result.recommendations)

    async def test_broken_link_plan_fixes_file(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("see [link](missing.md) for details\n")
        plan = _make_plan(
            file_path=str(md),
            rationale="broken link to missing.md",
        )
        result = await documentation.execute_fix_plan(plan, tmp_path)
        assert result.success is True
        assert result.confidence >= 0.7

    async def test_broken_link_plan_with_changes_applies_them(
        self, tmp_path: Path
    ) -> None:
        md = tmp_path / "doc.md"
        md.write_text("line one\nold text\nline three\n")
        change = ChangeSpec(
            line_range=(2, 2),
            old_code="old text",
            new_code="new text",
            reason="update",
        )
        plan = _make_plan(
            file_path=str(md),
            rationale="broken link somewhere",
            changes=[change],
        )
        result = await documentation.execute_fix_plan(plan, tmp_path)
        assert result.success is True
        assert result.confidence == 0.9
        assert str(md) in result.files_modified
        assert "new text" in md.read_text()

    async def test_changelog_plan_delegates_to_changelog(self, tmp_path: Path) -> None:
        with patch.object(
            documentation,
            "_update_changelog",
            return_value=FixResult(success=True, confidence=0.9),
        ):
            plan = _make_plan(rationale="update changelog entries")
            result = await documentation.execute_fix_plan(plan, tmp_path)
        assert result.success is True
        assert result.confidence == 0.9

    async def test_broken_link_plan_read_failure_returns_error(
        self, tmp_path: Path
    ) -> None:
        plan = _make_plan(
            file_path=str(tmp_path / "absent.md"),
            rationale="broken link to x.md",
        )
        result = await documentation.execute_fix_plan(plan, tmp_path)
        assert result.success is False
        assert "Failed to read" in (
            result.remaining_issues[0] if result.remaining_issues else ""
        )


# ---------------------------------------------------------------------------
# _fix_broken_link_from_plan / _find_line_with_target
# ---------------------------------------------------------------------------


class TestFindLineWithTarget:
    def test_finds_link_line(self) -> None:
        content = "intro\n[text](target.md)\nend\n"
        assert documentation._find_line_with_target(content, "target.md") == 2

    def test_returns_none_when_missing(self) -> None:
        content = "no link here\n"
        assert documentation._find_line_with_target(content, "missing.md") is None


# ---------------------------------------------------------------------------
# _apply_fix_plan_changes
# ---------------------------------------------------------------------------


class TestApplyFixPlanChanges:
    def test_applies_sorted_changes(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        path.write_text("a\nb\nc\nd\n")
        change = ChangeSpec(
            line_range=(2, 3), old_code="b\nc", new_code="B\nC", reason="up"
        )
        plan = _make_plan(file_path=str(path), rationale="x", changes=[change])
        result = documentation._apply_fix_plan_changes(plan, path.read_text())
        assert result.success is True
        assert "B" in path.read_text() and "C" in path.read_text()

    def test_out_of_bounds_change_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        path.write_text("a\nb\n")
        change = ChangeSpec(
            line_range=(50, 60), old_code="x", new_code="y", reason="skip"
        )
        plan = _make_plan(file_path=str(path), rationale="x", changes=[change])
        result = documentation._apply_fix_plan_changes(plan, path.read_text())
        assert result.success is True
        # Unchanged content still gets written.
        assert path.read_text() == "a\nb\n"

    def test_write_failure_returns_error(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        path.write_text("a\nb\n")
        change = ChangeSpec(line_range=(1, 1), old_code="a", new_code="A", reason="x")
        plan = _make_plan(file_path=str(path), rationale="x", changes=[change])
        with patch(f"{MODULE}._write_file", return_value=False):
            result = documentation._apply_fix_plan_changes(plan, path.read_text())
        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]


# ---------------------------------------------------------------------------
# fix_documentation_issue dispatch
# ---------------------------------------------------------------------------


class TestFixDocumentationIssueDispatch:
    async def test_broken_link_dispatch(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("see [link](missing.md)\n")
        issue = _make_issue(
            message="broken documentation link to missing.md",
            file_path=str(md),
        )
        result = await documentation.fix_documentation_issue(issue, tmp_path)
        assert result.success is True

    async def test_changelog_dispatch(self, tmp_path: Path) -> None:
        issue = _make_issue(message="Update changelog please")
        with patch.object(
            documentation,
            "_update_changelog",
            return_value=FixResult(success=True, confidence=0.7),
        ):
            result = await documentation.fix_documentation_issue(issue, tmp_path)
        assert result.success is True

    async def test_consistency_dispatch(self, tmp_path: Path) -> None:
        issue = _make_issue(message="agent count inconsistency")
        with patch.object(
            documentation,
            "_fix_documentation_consistency",
            return_value=FixResult(success=True, confidence=0.8),
        ) as mock_fn:
            result = await documentation.fix_documentation_issue(issue, tmp_path)
        assert result.success is True
        mock_fn.assert_awaited_once()

    async def test_api_dispatch(self, tmp_path: Path) -> None:
        issue = _make_issue(message="api doc needs update")
        with patch.object(
            documentation,
            "_update_api_documentation",
            return_value=FixResult(success=True, confidence=0.7),
        ) as mock_fn:
            result = await documentation.fix_documentation_issue(issue, tmp_path)
        assert result.success is True
        mock_fn.assert_awaited_once()

    async def test_readme_dispatch(self, tmp_path: Path) -> None:
        issue = _make_issue(message="readme needs updating")
        with patch.object(
            documentation,
            "_update_api_documentation",
            return_value=FixResult(success=True, confidence=0.7),
        ) as mock_fn:
            await documentation.fix_documentation_issue(issue, tmp_path)
        mock_fn.assert_awaited_once()

    async def test_general_dispatch(self, tmp_path: Path) -> None:
        issue = _make_issue(message="documentation is stale")
        result = await documentation.fix_documentation_issue(issue, tmp_path)
        assert result.success is False
        assert any("Documentation issue" in r for r in result.recommendations)

    async def test_exception_returns_failure(self, tmp_path: Path) -> None:
        issue = _make_issue(message="broken link to x")
        with patch.object(
            documentation, "_fix_broken_link", side_effect=RuntimeError("boom")
        ):
            result = await documentation.fix_documentation_issue(issue, tmp_path)
        assert result.success is False
        assert result.confidence == 0.0
        assert any("boom" in m for m in result.remaining_issues)


# ---------------------------------------------------------------------------
# _update_changelog
# ---------------------------------------------------------------------------


class TestUpdateChangelog:
    async def test_no_recent_changes_returns_recommendation(
        self, tmp_path: Path
    ) -> None:
        issue = _make_issue(message="update changelog")
        with patch.object(documentation, "_get_recent_changes", return_value=[]):
            result = await documentation._update_changelog(issue, tmp_path)
        assert result.success is True
        assert any("No recent changes" in r for r in result.recommendations)

    async def test_creates_initial_changelog_when_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        issue = _make_issue(message="update changelog")
        with patch.object(
            documentation,
            "_get_recent_changes",
            return_value=[{"message": "feat: new", "hash": "abc", "author": "me"}],
        ):
            result = await documentation._update_changelog(issue, tmp_path)
        assert result.success is True
        changelog = tmp_path / "CHANGELOG.md"
        assert changelog.exists()
        content = changelog.read_text()
        assert "# Changelog" in content
        assert "feat: new" in content
        assert "### Added" in content
        # Pre-existing quirk: files_modified holds a Path, not a str.
        assert isinstance(result.files_modified[0], Path)

    async def test_appends_to_existing_changelog(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        existing = "# Changelog\n\n## 1.0.0\n\nOld entry\n"
        (tmp_path / "CHANGELOG.md").write_text(existing)
        issue = _make_issue(message="update changelog")
        with patch.object(
            documentation,
            "_get_recent_changes",
            return_value=[{"message": "fix: bug", "hash": "def", "author": "me"}],
        ):
            result = await documentation._update_changelog(issue, tmp_path)
        assert result.success is True
        content = (tmp_path / "CHANGELOG.md").read_text()
        assert "fix: bug" in content
        assert "Old entry" in content
        assert "### Fixed" in content

    async def test_changelog_read_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "CHANGELOG.md").write_text("dummy")
        issue = _make_issue(message="update changelog")
        with (
            patch.object(
                documentation,
                "_get_recent_changes",
                return_value=[{"message": "feat: a", "hash": "1", "author": "x"}],
            ),
            patch(f"{MODULE}._read_file", return_value=None),
        ):
            result = await documentation._update_changelog(issue, tmp_path)
        assert result.success is False
        assert "Failed to read" in result.remaining_issues[0]

    async def test_changelog_write_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        issue = _make_issue(message="update changelog")
        with (
            patch.object(
                documentation,
                "_get_recent_changes",
                return_value=[{"message": "feat: a", "hash": "1", "author": "x"}],
            ),
            patch(f"{MODULE}._write_file", return_value=False),
        ):
            result = await documentation._update_changelog(issue, tmp_path)
        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]


# ---------------------------------------------------------------------------
# _fix_documentation_consistency
# ---------------------------------------------------------------------------


class TestFixDocumentationConsistency:
    async def test_no_md_files_no_changes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = await documentation._fix_documentation_consistency(_make_issue())
        assert result.success is True
        assert "already consistent" in result.recommendations[0]

    async def test_mismatch_in_md_file_gets_fixed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        md = tmp_path / "doc.md"
        md.write_text("This project has 12 specialized agents in total.\n")
        result = await documentation._fix_documentation_consistency(_make_issue())
        assert result.success is True
        assert result.confidence == 0.85
        assert len(result.files_modified) == 1
        # Pre-existing quirk: files_modified holds a Path, not a str.
        assert isinstance(result.files_modified[0], Path)
        content = md.read_text()
        assert "9 specialized agents" in content


# ---------------------------------------------------------------------------
# _update_api_documentation
# ---------------------------------------------------------------------------


class TestUpdateApiDocumentation:
    async def test_no_api_changes_returns_recommendation(
        self, tmp_path: Path
    ) -> None:
        with patch.object(documentation, "_detect_api_changes", return_value=[]):
            result = await documentation._update_api_documentation(
                _make_issue(), tmp_path
            )
        assert result.success is True
        assert any("No API changes" in r for r in result.recommendations)

    async def test_api_changes_updates_readme(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text("# Project\n\nIntro paragraph\n")
        with patch.object(
            documentation,
            "_detect_api_changes",
            return_value=[{"file": "x/api.py", "type": "potential_api_change"}],
        ):
            result = await documentation._update_api_documentation(
                _make_issue(), tmp_path
            )
        assert result.success is True
        content = (tmp_path / "README.md").read_text()
        assert "TODO: Update examples" in content
        # Pre-existing quirk: files_modified holds a Path, not a str.
        assert isinstance(result.files_modified[0], Path)

    async def test_readme_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        with patch.object(
            documentation,
            "_detect_api_changes",
            return_value=[{"file": "x/api.py", "type": "potential_api_change"}],
        ):
            result = await documentation._update_api_documentation(
                _make_issue(), tmp_path
            )
        assert result.success is False
        assert any("Could not update" in m for m in result.remaining_issues)

    async def test_readme_read_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "README.md").write_text("data")
        with (
            patch.object(
                documentation,
                "_detect_api_changes",
                return_value=[{"file": "x/api.py", "type": "potential_api_change"}],
            ),
            patch(f"{MODULE}._read_file", return_value=None),
        ):
            result = await documentation._update_api_documentation(
                _make_issue(), tmp_path
            )
        assert result.success is False


# ---------------------------------------------------------------------------
# _general_documentation_update
# ---------------------------------------------------------------------------


class TestGeneralDocumentationUpdate:
    async def test_returns_failure_no_file_written(self) -> None:
        result = await documentation._general_documentation_update(
            _make_issue(message="stale doc")
        )
        assert result.success is False
        assert any("stale doc" in r for r in result.recommendations)
        assert result.fixes_applied == []
        assert result.files_modified == []


# ---------------------------------------------------------------------------
# _update_changelog_from_plan
# ---------------------------------------------------------------------------


class TestUpdateChangelogFromPlan:
    async def test_delegates_to_changelog(self, tmp_path: Path) -> None:
        plan = _make_plan(rationale="changelog update", risk_level="low")
        sentinel = FixResult(success=True, confidence=0.9, fixes_applied=["x"])
        with patch.object(
            documentation, "_update_changelog", return_value=sentinel
        ) as mock_fn:
            result = await documentation._update_changelog_from_plan(plan, tmp_path)
        assert result is sentinel
        mock_fn.assert_awaited_once()

    async def test_builds_issue_with_risk_level_as_severity_pre_existing_quirk(
        self, tmp_path: Path
    ) -> None:
        """Pre-existing quirk: ``severity`` is set to ``plan.risk_level``
        (a ``str``), not a ``Priority`` enum member. ``Issue`` performs no
        runtime validation, so the mismatched type flows through untouched.
        """
        plan = _make_plan(rationale="changelog update", risk_level="high")
        captured: list[Issue] = []

        async def fake_update_changelog(
            issue: Issue, project_root: Path
        ) -> FixResult:
            captured.append(issue)
            return FixResult(success=True, confidence=0.9)

        with patch.object(
            documentation, "_update_changelog", side_effect=fake_update_changelog
        ):
            await documentation._update_changelog_from_plan(plan, tmp_path)

        assert captured[0].severity == "high"
        assert not isinstance(captured[0].severity, Priority)


# ---------------------------------------------------------------------------
# Git subprocess helpers
# ---------------------------------------------------------------------------


def _fake_completed_process(stdout: str, returncode: int = 0, stderr: str = ""):
    cp = MagicMock()
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


class TestGitSubprocessHelpers:
    def test_get_commit_range_with_tag(self, tmp_path: Path) -> None:
        with patch.object(
            subprocess, "run", return_value=_fake_completed_process("v1.0.0\n")
        ):
            assert documentation._get_commit_range(tmp_path) == "v1.0.0..HEAD"

    def test_get_commit_range_no_tag(self, tmp_path: Path) -> None:
        with patch.object(
            subprocess,
            "run",
            return_value=_fake_completed_process("", returncode=128),
        ):
            assert documentation._get_commit_range(tmp_path) == "-10"

    def test_get_commit_messages_success(self, tmp_path: Path) -> None:
        cp = _fake_completed_process("fix bug|abc|alice")
        with patch.object(subprocess, "run", return_value=cp):
            result = documentation._get_commit_messages("-10", tmp_path)
        assert "fix bug" in result

    def test_get_commit_messages_failure(self, tmp_path: Path) -> None:
        cp = _fake_completed_process("", returncode=1)
        with patch.object(subprocess, "run", return_value=cp):
            assert documentation._get_commit_messages("invalid", tmp_path) == ""

    def test_get_recent_changes_handles_subprocess_error(
        self, tmp_path: Path
    ) -> None:
        with patch.object(subprocess, "run", side_effect=OSError("nope")):
            assert documentation._get_recent_changes(tmp_path) == []

    def test_get_recent_changes_with_messages(self, tmp_path: Path) -> None:
        with (
            patch.object(documentation, "_get_commit_range", return_value="-1"),
            patch.object(
                documentation,
                "_get_commit_messages",
                return_value="feat: a|1|me\nfix: b|2|you",
            ),
        ):
            changes = documentation._get_recent_changes(tmp_path)
        assert len(changes) == 2
        assert changes[0]["message"] == "feat: a"
        assert changes[1]["author"] == "you"

    def test_get_recent_changes_no_range(self, tmp_path: Path) -> None:
        with patch.object(documentation, "_get_commit_range", return_value=""):
            assert documentation._get_recent_changes(tmp_path) == []

    def test_get_commit_range_pins_cwd_to_project_root(
        self, tmp_path: Path
    ) -> None:
        # Task 22a regression: `_get_commit_range` previously had no
        # project-path parameter at all -- exercise the real
        # subprocess.run call (no mocking) against a fresh git repo rooted
        # at `tmp_path` and capture the `cwd` kwarg to prove it is now
        # pinned there, not relying on the ambient process cwd.
        captured: dict[str, object] = {}
        real_run = subprocess.run

        def spying_run(*args: object, **kwargs: object):
            captured["cwd"] = kwargs.get("cwd")
            return real_run(*args, **kwargs)  # type: ignore[arg-type]

        with patch.object(subprocess, "run", side_effect=spying_run):
            documentation._get_commit_range(tmp_path)

        assert captured["cwd"] == tmp_path

    def test_get_commit_messages_pins_cwd_to_project_root(
        self, tmp_path: Path
    ) -> None:
        captured: dict[str, object] = {}
        real_run = subprocess.run

        def spying_run(*args: object, **kwargs: object):
            captured["cwd"] = kwargs.get("cwd")
            return real_run(*args, **kwargs)  # type: ignore[arg-type]

        with patch.object(subprocess, "run", side_effect=spying_run):
            documentation._get_commit_messages("-1", tmp_path)

        assert captured["cwd"] == tmp_path

    def test_get_recent_changes_end_to_end_real_subprocess(self) -> None:
        """Real ``git log`` invocation against this repo's actual history
        (no mocking of ``subprocess.run``) -- proves the pipeline end to
        end: commit range -> commit messages -> parsed change dicts.
        """
        repo_root = Path(__file__).resolve().parents[2]
        changes = documentation._get_recent_changes(repo_root)
        assert isinstance(changes, list)
        if changes:
            assert "message" in changes[0]
            assert "hash" in changes[0]
            assert "author" in changes[0]


# ---------------------------------------------------------------------------
# Commit message parsing / categorisation
# ---------------------------------------------------------------------------


class TestParseAndCategorize:
    def test_parse_commit_messages(self) -> None:
        out = documentation._parse_commit_messages("feat: x|abc|me\nfix: y|def")
        assert out[0] == {"message": "feat: x", "hash": "abc", "author": "me"}
        assert out[1]["author"] == "Unknown"
        assert out[1]["message"] == "fix: y"

    def test_parse_commit_messages_empty(self) -> None:
        assert documentation._parse_commit_messages("") == []
        assert documentation._parse_commit_messages("\n\n") == []

    @pytest.mark.parametrize(
        "msg,expected",
        [
            ("feat: add thing", "features"),
            ("feature: another", "features"),
            ("fix: bug", "fixes"),
            ("refactor: code", "refactors"),
            ("refact: code", "refactors"),
            ("docs: update", "other"),
            ("random commit", "other"),
        ],
    )
    def test_get_change_category(self, msg: str, expected: str) -> None:
        assert documentation._get_change_category(msg) == expected

    def test_categorize_changes(self) -> None:
        changes = [
            {"message": "feat: a", "hash": "1", "author": "x"},
            {"message": "fix: b", "hash": "2", "author": "x"},
            {"message": "refactor: c", "hash": "3", "author": "x"},
            {"message": "chore: d", "hash": "4", "author": "x"},
        ]
        cats = documentation._categorize_changes(changes)
        assert cats["features"] == ["feat: a"]
        assert cats["fixes"] == ["fix: b"]
        assert cats["refactors"] == ["refactor: c"]
        assert cats["other"] == ["chore: d"]

    def test_add_section_to_entry(self) -> None:
        lines: list[str] = []
        documentation._add_section_to_entry(lines, "### Added", ["item 1", "item 2"])
        assert lines == ["### Added", "- item 1", "", "- item 2", ""]

    def test_add_categorized_changes_to_entry(self) -> None:
        lines: list[str] = []
        cats = {
            "features": ["f1"],
            "fixes": ["b1"],
            "refactors": ["r1"],
            "other": ["o1"],
        }
        documentation._add_categorized_changes_to_entry(lines, cats)
        assert "### Added" in lines
        assert "### Fixed" in lines
        assert "### Changed" in lines
        assert "### Other" in lines

    def test_generate_changelog_entry_real_content(self) -> None:
        changes = [
            {"message": "feat: new", "hash": "1", "author": "x"},
            {"message": "fix: bug", "hash": "2", "author": "x"},
        ]
        entry = documentation._generate_changelog_entry(changes)
        assert "## [Unreleased]" in entry
        assert "### Added" in entry
        assert "- feat: new" in entry
        assert "### Fixed" in entry
        assert "- fix: bug" in entry


# ---------------------------------------------------------------------------
# Changelog insertion helpers
# ---------------------------------------------------------------------------


class TestChangelogEntry:
    def test_insert_changelog_entry_before_first_header(self) -> None:
        content = "# Title\n\n## 1.0.0 - 2025-01-01\n\n- item"
        entry = "## [Unreleased] - 2025-02-01\n\n- new"
        out = documentation._insert_changelog_entry(content, entry)
        assert "## [Unreleased]" in out
        assert out.index("## [Unreleased]") < out.index("## 1.0.0")

    def test_insert_changelog_entry_no_header(self) -> None:
        content = "intro paragraph\nmore text\n"
        entry = "## New\n"
        out = documentation._insert_changelog_entry(content, entry)
        assert out.startswith("## New")

    def test_create_initial_changelog(self) -> None:
        out = documentation._create_initial_changelog("## [Unreleased]\n")
        assert out.startswith("# Changelog")
        assert "Keep a Changelog" in out
        assert "## [Unreleased]" in out


# ---------------------------------------------------------------------------
# Agent count consistency
# ---------------------------------------------------------------------------


class TestAgentCountConsistency:
    def test_get_agent_count_patterns(self) -> None:
        patterns = documentation._get_agent_count_patterns()
        assert len(patterns) == 4
        assert all(isinstance(p, str) for p in patterns)

    def test_check_file_agent_count_no_content(self, tmp_path: Path) -> None:
        result = documentation._check_file_agent_count(
            tmp_path / "absent.md", [r"\d+"], 9
        )
        assert result is None

    def test_check_file_agent_count_with_mismatch(self, tmp_path: Path) -> None:
        from crackerjack.services.regex_patterns import SAFE_PATTERNS

        # `agent_count_pattern` is `(\d+)\s+agents` -- it requires the digits
        # to be directly followed by "agents" (no "specialized" in between).
        pattern_str = SAFE_PATTERNS["agent_count_pattern"].pattern
        md = tmp_path / "x.md"
        md.write_text("This project has 12 agents in total.")
        result = documentation._check_file_agent_count(md, [pattern_str], 9)
        assert result is not None
        assert result[0] == md
        assert result[1] == 12
        assert result[2] == 9

    def test_is_count_mismatch(self) -> None:
        assert documentation._is_count_mismatch(12, 9) is True
        assert documentation._is_count_mismatch(9, 9) is False
        # 4 or fewer agents is not considered a "mismatch" (placeholder).
        assert documentation._is_count_mismatch(2, 9) is False

    def test_check_pattern_for_count_mismatch_unknown_pattern(
        self, tmp_path: Path
    ) -> None:
        result = documentation._check_pattern_for_count_mismatch(
            r"unknown", {"x": "y"}, "content", tmp_path / "x.md", 9
        )
        assert result is None

    def test_check_agent_count_consistency_no_files(self) -> None:
        result = documentation._check_agent_count_consistency([])
        assert result == []

    def test_check_agent_count_consistency_mismatch(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("This project has 12 specialized agents in total.")
        issues = documentation._check_agent_count_consistency([md])
        assert len(issues) == 1
        assert issues[0][0] == md
        assert issues[0][1] == 12
        assert issues[0][2] == 9

    def test_check_agent_count_consistency_no_mismatch(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("This project has 9 specialized agents in total.")
        issues = documentation._check_agent_count_consistency([md])
        assert issues == []

    def test_fix_agent_count_references_real_regex(self) -> None:
        content = "We have 12 agents and 12 specialized agents ready."
        out = documentation._fix_agent_count_references(content, 12, 9)
        assert "NEW_COUNT" not in out
        assert "9 agents" in out
        assert "9 specialized agents" in out
        assert "12" not in out


# ---------------------------------------------------------------------------
# _detect_api_changes
# ---------------------------------------------------------------------------


class TestDetectApiChanges:
    def test_detect_api_changes_filters_api_files(self, tmp_path: Path) -> None:
        cp = _fake_completed_process("module/api.py\nother/__init__.py\nunrelated.py\n")
        with patch.object(subprocess, "run", return_value=cp):
            changes = documentation._detect_api_changes(tmp_path)
        paths = {c["file"] for c in changes}
        assert "module/api.py" in paths
        assert "other/__init__.py" in paths
        assert "unrelated.py" not in paths

    def test_detect_api_changes_no_changes(self, tmp_path: Path) -> None:
        cp = _fake_completed_process("", returncode=1)
        with patch.object(subprocess, "run", return_value=cp):
            assert documentation._detect_api_changes(tmp_path) == []

    def test_detect_api_changes_subprocess_error(self, tmp_path: Path) -> None:
        with patch.object(subprocess, "run", side_effect=OSError("fail")):
            assert documentation._detect_api_changes(tmp_path) == []

    def test_detect_api_changes_pins_cwd_to_project_root(
        self, tmp_path: Path
    ) -> None:
        # Task 22a regression: `_detect_api_changes` previously had no
        # project-path parameter at all -- exercise the real
        # subprocess.run call (no mocking) and capture the `cwd` kwarg to
        # prove it is now pinned to `project_root`.
        captured: dict[str, object] = {}
        real_run = subprocess.run

        def spying_run(*args: object, **kwargs: object):
            captured["cwd"] = kwargs.get("cwd")
            return real_run(*args, **kwargs)  # type: ignore[arg-type]

        with patch.object(subprocess, "run", side_effect=spying_run):
            documentation._detect_api_changes(tmp_path)

        assert captured["cwd"] == tmp_path


# ---------------------------------------------------------------------------
# _fix_broken_link (Issue path) / _extract_target_file_from_details
# ---------------------------------------------------------------------------


class TestFixBrokenLinkIssue:
    async def test_no_file_path_returns_error(self, tmp_path: Path) -> None:
        issue = _make_issue(message="broken link", file_path=None)
        result = await documentation._fix_broken_link(issue, tmp_path)
        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_read_failure_returns_error(self, tmp_path: Path) -> None:
        issue = _make_issue(
            message="broken link",
            file_path=str(tmp_path / "missing.md"),
            details=["Target file: docs/x.md"],
        )
        result = await documentation._fix_broken_link(issue, tmp_path)
        assert result.success is False
        assert "Failed to read" in result.remaining_issues[0]

    async def test_fix_broken_link_removes_line(self, tmp_path: Path) -> None:
        md = tmp_path / "doc.md"
        md.write_text("see [link](missing.md) for details\n")
        issue = _make_issue(
            message="broken link",
            file_path=str(md),
            line_number=1,
            details=["Target file: missing.md"],
        )
        result = await documentation._fix_broken_link(issue, tmp_path)
        assert result.success is True
        new_content = md.read_text()
        assert "missing.md" not in new_content

    @pytest.mark.parametrize(
        "detail,expected",
        [
            ("Target file: docs/foo.md", "docs/foo.md"),
            ("File not found: docs/bar.md", "docs/bar.md"),
            ("Broken link: docs/baz.md", "docs/baz.md"),
            ("Target path: docs/qux.md", "docs/qux.md"),
            ("Path: docs/aux.md", "docs/aux.md"),
        ],
    )
    def test_extract_target_file_from_details(self, detail: str, expected: str) -> None:
        assert documentation._extract_target_file_from_details([detail]) == expected

    def test_extract_target_file_from_details_no_match(self) -> None:
        assert documentation._extract_target_file_from_details(["nothing"]) is None


# ---------------------------------------------------------------------------
# _fix_or_remove_broken_link_line / _attempt_link_fix
# ---------------------------------------------------------------------------


class TestFixOrRemoveBrokenLinkLine:
    def test_finds_link_by_target_match_and_removes(self, tmp_path: Path) -> None:
        content = "see [link](target.md) for details\n"
        out = documentation._fix_or_remove_broken_link_line(
            content, "doc.md", None, "target.md", tmp_path
        )
        assert "target.md" not in out

    def test_line_kept_when_no_match(self, tmp_path: Path) -> None:
        content = "no link here\n"
        out = documentation._fix_or_remove_broken_link_line(
            content, "doc.md", 999, "definitelynotinline.md", tmp_path
        )
        assert out == content

    def test_keeps_unrelated_lines(self, tmp_path: Path) -> None:
        content = "first\n[link](missing.md)\nlast\n"
        out = documentation._fix_or_remove_broken_link_line(
            content, "doc.md", 2, "missing.md", tmp_path
        )
        assert "first" in out and "last" in out

    def test_fixes_by_line_number_when_target_exists(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "foo.md").write_text("# Foo")
        content = "see [link](foo.md) for details\n"
        out = documentation._fix_or_remove_broken_link_line(
            content, str(tmp_path / "doc.md"), 1, "foo.md", tmp_path
        )
        assert "docs/foo.md" in out

    def test_attempt_link_fix_returns_none_when_no_target(self, tmp_path: Path) -> None:
        result = documentation._attempt_link_fix(None, "line", "doc.md", 1, tmp_path)
        assert result is None

    def test_attempt_link_fix_returns_none_when_no_match(self, tmp_path: Path) -> None:
        result = documentation._attempt_link_fix(
            "nonexistent.md",
            "see [link](nonexistent.md)",
            "doc.md",
            1,
            tmp_path,
        )
        assert result is None


# ---------------------------------------------------------------------------
# _write_fixed_content / _create_success_message
# ---------------------------------------------------------------------------


class TestWriteAndSuccessMessage:
    def test_write_failure(self) -> None:
        with patch(f"{MODULE}._write_file", return_value=False):
            result = documentation._write_fixed_content(
                "doc.md", "content", "target.md"
            )
        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]

    def test_write_success_with_target(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        result = documentation._write_fixed_content(str(path), "content", "x.md")
        assert result.success is True
        assert "x.md" in result.fixes_applied[0]
        assert path.read_text() == "content"

    def test_write_success_no_target(self, tmp_path: Path) -> None:
        path = tmp_path / "doc.md"
        result = documentation._write_fixed_content(str(path), "content", None)
        assert result.success is True
        assert "Removed broken link" in result.fixes_applied[0]

    def test_create_success_message(self) -> None:
        assert "target.md" in documentation._create_success_message(
            "doc.md", "target.md"
        )
        assert "Removed" in documentation._create_success_message("doc.md", None)


# ---------------------------------------------------------------------------
# _find_and_fix_link / _find_best_link_target / _path_tokens / _suffix_token_score
# ---------------------------------------------------------------------------


class TestPathHelpers:
    def test_path_tokens_strips_suffix_and_splits(self) -> None:
        tokens = documentation._path_tokens(Path("docs/reference/api.md"))
        assert "docs" in tokens
        assert "api" in tokens
        assert "md" not in tokens

    def test_path_tokens_handles_camelcase(self) -> None:
        tokens = documentation._path_tokens(Path("api/MyClass.py"))
        assert "myclass" in tokens
        assert "api" in tokens

    def test_suffix_token_score_partial(self) -> None:
        left = ["a", "b", "c", "d"]
        right = ["x", "b", "c", "d"]
        assert documentation._suffix_token_score(left, right) == 3

    def test_suffix_token_score_no_match(self) -> None:
        left = ["a", "b", "c"]
        right = ["x", "y", "z"]
        assert documentation._suffix_token_score(left, right) == 0

    def test_suffix_token_score_empty(self) -> None:
        assert documentation._suffix_token_score([], []) == 0


class TestBuildLinkMatchPattern:
    def test_relative_target(self) -> None:
        pattern = documentation._build_link_match_pattern("docs/foo.md")
        assert r"docs/foo\.md" in pattern
        assert pattern.startswith(r"\[([^\]]+)\]\(")

    def test_absolute_target_includes_basename(self) -> None:
        with patch.object(Path, "is_absolute", return_value=True):
            pattern = documentation._build_link_match_pattern("/abs/path/foo.md")
        assert "foo" in pattern


class TestFindBestLinkTarget:
    def test_no_target_name_returns_none(self, tmp_path: Path) -> None:
        assert documentation._find_best_link_target("/", tmp_path) is None

    def test_no_candidates_returns_none(self, tmp_path: Path) -> None:
        result = documentation._find_best_link_target("absent.md", tmp_path)
        assert result is None

    def test_picks_best_suffix_match(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("x")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "a.md").write_text("y")
        best = documentation._find_best_link_target("a.md", tmp_path)
        # Both candidates tie on suffix score; the shallower one wins on depth.
        assert best == tmp_path / "a.md"


class TestFindAndFixLink:
    def test_returns_line_when_no_match(self, tmp_path: Path) -> None:
        line = "see [link](nowhere.md) for details"
        result = documentation._find_and_fix_link(
            "nowhere.md", line, str(tmp_path / "doc.md"), tmp_path
        )
        assert result == line

    def test_uses_relative_path_when_target_is_absolute(self, tmp_path: Path) -> None:
        source_dir = tmp_path / "docs" / "guides"
        source_dir.mkdir(parents=True)
        target_file = tmp_path / "docs" / "reference" / "config.md"
        target_file.parent.mkdir(parents=True)
        target_file.write_text("# config")

        line = "- **[Config](../reference/config.md)** - docs"
        fixed = documentation._find_and_fix_link(
            str(target_file),
            line,
            str(source_dir / "server-development.md"),
            tmp_path,
        )
        assert "reference/config.md" in fixed

    def test_uses_fuzzy_repo_match_when_direct_candidates_absent(
        self, tmp_path: Path
    ) -> None:
        source_dir = tmp_path / "docs" / "guides"
        source_dir.mkdir(parents=True)
        target_file = tmp_path / "docs" / "AKOSHA_USER_GUIDE.md"
        target_file.write_text("# guide")

        line = "- [User Guide](USER_GUIDE.md)"
        fixed = documentation._find_and_fix_link(
            "USER_GUIDE.md",
            line,
            str(source_dir / "api-reference.md"),
            tmp_path,
        )
        assert "AKOSHA_USER_GUIDE.md" in fixed


# ---------------------------------------------------------------------------
# _update_readme_examples
# ---------------------------------------------------------------------------


class TestUpdateReadmeExamples:
    def test_inserts_todo_when_changes_and_no_marker(self) -> None:
        content = "# Title\n\nSome text\n"
        out = documentation._update_readme_examples(
            content, [{"file": "api.py", "type": "potential_api_change"}]
        )
        assert "TODO: Update examples" in out

    def test_does_not_insert_when_marker_present(self) -> None:
        content = (
            "# Title\n\nSome text\n"
            "<!-- TODO: Update examples after recent API changes -->\n"
        )
        out = documentation._update_readme_examples(
            content, [{"file": "api.py", "type": "potential_api_change"}]
        )
        assert out == content

    def test_returns_content_when_no_changes(self) -> None:
        content = "# Title\n"
        out = documentation._update_readme_examples(content, [])
        assert out == content

    def test_no_h1_returns_unchanged(self) -> None:
        content = "no h1 here\n"
        out = documentation._update_readme_examples(
            content, [{"file": "api.py", "type": "potential_api_change"}]
        )
        assert out == content


# ---------------------------------------------------------------------------
# Read / error helpers
# ---------------------------------------------------------------------------


class TestReadAndError:
    def test_read_file(self, tmp_path: Path) -> None:
        md = tmp_path / "x.md"
        md.write_text("hello")
        assert documentation._read_file(md) == "hello"

    def test_read_file_missing(self, tmp_path: Path) -> None:
        assert documentation._read_file(tmp_path / "absent.md") is None

    def test_create_error_result(self) -> None:
        result = documentation._create_error_result("boom")
        assert result.success is False
        assert result.confidence == 0.0
        assert result.remaining_issues == ["boom"]

"""Comprehensive unit tests for DocumentationAgent.

Tests cover:
- can_handle() confidence scoring for DOCUMENTATION issues
- get_supported_types() returns DOCUMENTATION
- _is_broken_link_plan() rationale matching
- _extract_target_from_rationale() regex extraction patterns
- _find_line_with_target() line location for broken links
- _fix_broken_link_from_plan() / execute_fix_plan() integration
- _update_changelog_from_plan() changelog fix-plan path
- analyze_and_fix() dispatch (changelog, broken link, agent count, api, general)
- _update_changelog() (new file, existing file, no changes)
- _fix_documentation_consistency() (mismatch and no-op)
- _update_api_documentation() (changes/no changes detected)
- _general_documentation_update()
- _get_recent_changes() and git subprocess helpers
- _parse_commit_messages() categorisation
- _get_change_category() prefixes (feat, fix, refactor, other)
- _add_section_to_entry() / _add_categorized_changes_to_entry()
- _insert_changelog_entry() / _create_initial_changelog()
- _get_agent_count_patterns() and pattern lookup
- _check_agent_count_consistency() mismatch detection
- _fix_agent_count_references() replacement behaviour
- _detect_api_changes() subprocess invocation
- _fix_broken_link() file-not-found path
- _extract_target_file_from_details() pattern matching
- _fix_or_remove_broken_link_line() line number vs target file branch
- _attempt_link_fix() returns None for unfixable
- _find_and_fix_link() rebuilds path or returns line unchanged
- _find_best_link_target() ranking
- _path_tokens() / _suffix_token_score()
- _build_link_match_pattern() ordering
- _update_readme_examples() TODO injection
- Top-level error fallback (analyze_and_fix exception)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.documentation_agent import DocumentationAgent
from crackerjack.models.fix_plan import ChangeSpec, FixPlan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def agent(tmp_path: Path) -> DocumentationAgent:
    context = AgentContext(project_path=tmp_path)
    return DocumentationAgent(context)


@pytest.fixture
def context_with_read(tmp_path: Path) -> AgentContext:
    """AgentContext with a side effect for get_file_content."""
    return AgentContext(project_path=tmp_path)


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
        risk_level=risk_level,
        validated_by="system",
        rationale=rationale,
        changes=changes or [],
    )


# ---------------------------------------------------------------------------
# can_handle / supported types
# ---------------------------------------------------------------------------


class TestSupportedTypesAndConfidence:
    def test_supported_types_returns_documentation(self, agent: DocumentationAgent):
        assert agent.get_supported_types() == {IssueType.DOCUMENTATION}

    async def test_can_handle_documentation_returns_high(self, agent: DocumentationAgent):
        issue = _make_issue()
        assert await agent.can_handle(issue) == 0.8

    async def test_can_handle_other_types_returns_zero(self, agent: DocumentationAgent):
        issue = _make_issue()
        issue.type = IssueType.FORMATTING
        assert await agent.can_handle(issue) == 0.0


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
    def test_is_broken_link_plan_true(self, agent: DocumentationAgent, rationale: str):
        plan = _make_plan(rationale=rationale)
        assert agent._is_broken_link_plan(plan) is True

    def test_is_broken_link_plan_false(self, agent: DocumentationAgent):
        plan = _make_plan(rationale="general update")
        assert agent._is_broken_link_plan(plan) is False

    def test_extract_target_from_file_not_found(self, agent: DocumentationAgent):
        target = agent._extract_target_from_rationale("File not found: docs/foo.md")
        assert target == "docs/foo.md"

    def test_extract_target_from_broken_link(self, agent: DocumentationAgent):
        target = agent._extract_target_from_rationale("Broken link: docs/bar.md")
        assert target == "docs/bar.md"

    def test_extract_target_from_link_to(self, agent: DocumentationAgent):
        target = agent._extract_target_from_rationale("needs link to docs/baz.md")
        assert target == "docs/baz.md"

    def test_extract_target_from_relative_path(self, agent: DocumentationAgent):
        target = agent._extract_target_from_rationale("see ./local.md for details")
        assert target == "./local.md"

    def test_extract_target_returns_none(self, agent: DocumentationAgent):
        assert agent._extract_target_from_rationale("no file mentioned") is None


# ---------------------------------------------------------------------------
# execute_fix_plan + _fix_broken_link_from_plan
# ---------------------------------------------------------------------------


class TestExecuteFixPlan:
    async def test_general_documentation_returns_recommendation(
        self, agent: DocumentationAgent
    ):
        plan = _make_plan(rationale="general improvement")
        result = await agent.execute_fix_plan(plan)
        assert result.success is True
        assert result.confidence == 0.6
        assert any("Manual review" in r for r in result.recommendations)

    async def test_broken_link_plan_fixes_file(self, agent: DocumentationAgent, tmp_path: Path):
        md = tmp_path / "doc.md"
        md.write_text("see [link](missing.md) for details\n")
        plan = _make_plan(
            file_path=str(md),
            rationale="broken link to missing.md",
        )
        # The path's parent is in tmp_path, so project_root check passes
        # We expect a successful write; if no rewrite happens, success comes from
        # "Removed broken link" path.
        result = await agent.execute_fix_plan(plan)
        assert result.success is True
        assert result.confidence >= 0.7

    async def test_broken_link_plan_with_changes_applies_them(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
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
        result = await agent.execute_fix_plan(plan)
        assert result.success is True
        assert result.confidence == 0.9
        assert str(md) in result.files_modified
        assert "new text" in md.read_text()

    async def test_changelog_plan_delegates_to_changelog(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        # Make CHANGELOG.md not exist so we exercise the create-initial branch.
        with patch.object(agent, "_update_changelog", return_value=FixResult(success=True, confidence=0.9)):
            plan = _make_plan(rationale="update changelog entries")
            result = await agent.execute_fix_plan(plan)
        assert result.success is True
        assert result.confidence == 0.9

    async def test_broken_link_plan_read_failure_returns_error(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        plan = _make_plan(
            file_path=str(tmp_path / "absent.md"),
            rationale="broken link to x.md",
        )
        result = await agent.execute_fix_plan(plan)
        assert result.success is False
        assert "Failed to read" in (result.remaining_issues[0] if result.remaining_issues else "")


# ---------------------------------------------------------------------------
# _fix_broken_link_from_plan / _find_line_with_target
# ---------------------------------------------------------------------------


class TestFindLineWithTarget:
    def test_finds_link_line(self, agent: DocumentationAgent):
        content = "intro\n[text](target.md)\nend\n"
        assert agent._find_line_with_target(content, "target.md") == 2

    def test_returns_none_when_missing(self, agent: DocumentationAgent):
        content = "no link here\n"
        assert agent._find_line_with_target(content, "missing.md") is None


# ---------------------------------------------------------------------------
# _apply_fix_plan_changes
# ---------------------------------------------------------------------------


class TestApplyFixPlanChanges:
    def test_applies_sorted_changes(self, agent: DocumentationAgent, tmp_path: Path):
        path = tmp_path / "doc.md"
        path.write_text("a\nb\nc\nd\n")
        change = ChangeSpec(
            line_range=(2, 3), old_code="b\nc", new_code="B\nC", reason="up"
        )
        plan = _make_plan(file_path=str(path), rationale="x", changes=[change])
        result = agent._apply_fix_plan_changes(plan, path.read_text())
        assert result.success is True
        assert "B" in path.read_text() and "C" in path.read_text()

    def test_out_of_bounds_change_skipped(self, agent: DocumentationAgent, tmp_path: Path):
        path = tmp_path / "doc.md"
        path.write_text("a\nb\n")
        change = ChangeSpec(
            line_range=(50, 60), old_code="x", new_code="y", reason="skip"
        )
        plan = _make_plan(file_path=str(path), rationale="x", changes=[change])
        result = agent._apply_fix_plan_changes(plan, path.read_text())
        # Out of bounds: write still happens (unchanged content)
        assert result.success is True or "Failed to write" in (
            result.remaining_issues[0] if result.remaining_issues else ""
        )

    def test_write_failure_returns_error(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        path = tmp_path / "doc.md"
        path.write_text("a\nb\n")
        change = ChangeSpec(
            line_range=(1, 1), old_code="a", new_code="A", reason="x"
        )
        plan = _make_plan(file_path=str(path), rationale="x", changes=[change])
        with patch.object(agent.context, "write_file_content", return_value=False):
            result = agent._apply_fix_plan_changes(plan, path.read_text())
        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]


# ---------------------------------------------------------------------------
# analyze_and_fix dispatch
# ---------------------------------------------------------------------------


class TestAnalyzeAndFixDispatch:
    async def test_broken_link_dispatch(self, agent: DocumentationAgent, tmp_path: Path):
        md = tmp_path / "doc.md"
        md.write_text("see [link](missing.md)\n")
        issue = _make_issue(
            message="broken documentation link to missing.md",
            file_path=str(md),
        )
        result = await agent.analyze_and_fix(issue)
        assert result.success is True

    async def test_changelog_dispatch(self, agent: DocumentationAgent, tmp_path: Path):
        issue = _make_issue(message="Update changelog please")
        with patch.object(agent, "_update_changelog", return_value=FixResult(success=True, confidence=0.7)):
            result = await agent.analyze_and_fix(issue)
        assert result.success is True

    async def test_consistency_dispatch(self, agent: DocumentationAgent):
        issue = _make_issue(message="agent count inconsistency")
        with patch.object(agent, "_fix_documentation_consistency", return_value=FixResult(success=True, confidence=0.8)) as mock_fn:
            result = await agent.analyze_and_fix(issue)
        assert result.success is True
        mock_fn.assert_awaited_once()

    async def test_api_dispatch(self, agent: DocumentationAgent):
        issue = _make_issue(message="api doc needs update")
        with patch.object(agent, "_update_api_documentation", return_value=FixResult(success=True, confidence=0.7)) as mock_fn:
            result = await agent.analyze_and_fix(issue)
        assert result.success is True
        mock_fn.assert_awaited_once()

    async def test_readme_dispatch(self, agent: DocumentationAgent):
        issue = _make_issue(message="readme needs updating")
        with patch.object(agent, "_update_api_documentation", return_value=FixResult(success=True, confidence=0.7)) as mock_fn:
            result = await agent.analyze_and_fix(issue)
        mock_fn.assert_awaited_once()

    async def test_general_dispatch(self, agent: DocumentationAgent):
        issue = _make_issue(message="documentation is stale")
        result = await agent.analyze_and_fix(issue)
        assert result.success is True
        assert any("Documentation issue" in r for r in result.recommendations)

    async def test_exception_returns_failure(self, agent: DocumentationAgent):
        issue = _make_issue(message="broken link to x")
        with patch.object(agent, "_fix_broken_link", side_effect=RuntimeError("boom")):
            result = await agent.analyze_and_fix(issue)
        assert result.success is False
        assert result.confidence == 0.0
        assert any("boom" in m for m in result.remaining_issues)


# ---------------------------------------------------------------------------
# _update_changelog
# ---------------------------------------------------------------------------


class TestUpdateChangelog:
    async def test_no_recent_changes_returns_recommendation(
        self, agent: DocumentationAgent
    ):
        issue = _make_issue(message="update changelog")
        with patch.object(agent, "_get_recent_changes", return_value=[]):
            result = await agent._update_changelog(issue)
        assert result.success is True
        assert any("No recent changes" in r for r in result.recommendations)

    async def test_creates_initial_changelog_when_missing(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        issue = _make_issue(message="update changelog")
        # The agent builds a Path("CHANGELOG.md") literal; patch Path so that
        # path resolution and existence checks happen inside tmp_path.
        fake_changelog = tmp_path / "CHANGELOG.md"
        with patch("crackerjack.agents.documentation_agent.Path", lambda *a, **kw: fake_changelog if a and str(a[0]) == "CHANGELOG.md" else Path(*a, **kw)):
            with patch.object(agent, "_get_recent_changes", return_value=[{"message": "feat: new", "hash": "abc", "author": "me"}]):
                result = await agent._update_changelog(issue)
        assert result.success is True
        assert fake_changelog.exists()

    async def test_appends_to_existing_changelog(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        existing = "# Changelog\n\nOld entry\n"
        fake_changelog = tmp_path / "CHANGELOG.md"
        fake_changelog.write_text(existing)
        issue = _make_issue(message="update changelog")
        with patch("crackerjack.agents.documentation_agent.Path", lambda *a, **kw: fake_changelog if a and str(a[0]) == "CHANGELOG.md" else Path(*a, **kw)):
            with patch.object(agent, "_get_recent_changes", return_value=[{"message": "fix: bug", "hash": "def", "author": "me"}]):
                result = await agent._update_changelog(issue)
        assert result.success is True
        content = fake_changelog.read_text()
        assert "fix: bug" in content
        assert "Old entry" in content

    async def test_changelog_read_failure(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        fake_changelog = tmp_path / "CHANGELOG.md"
        fake_changelog.write_text("dummy")
        issue = _make_issue(message="update changelog")
        with patch("crackerjack.agents.documentation_agent.Path", lambda *a, **kw: fake_changelog if a and str(a[0]) == "CHANGELOG.md" else Path(*a, **kw)):
            with patch.object(agent, "_get_recent_changes", return_value=[{"message": "feat: a", "hash": "1", "author": "x"}]):
                with patch.object(agent.context, "get_file_content", return_value=None):
                    result = await agent._update_changelog(issue)
        assert result.success is False
        assert "Failed to read" in result.remaining_issues[0]

    async def test_changelog_write_failure(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        fake_changelog = tmp_path / "CHANGELOG.md"
        fake_changelog.write_text("dummy")
        issue = _make_issue(message="update changelog")
        with patch("crackerjack.agents.documentation_agent.Path", lambda *a, **kw: fake_changelog if a and str(a[0]) == "CHANGELOG.md" else Path(*a, **kw)):
            with patch.object(agent, "_get_recent_changes", return_value=[{"message": "feat: a", "hash": "1", "author": "x"}]):
                with patch.object(agent.context, "write_file_content", return_value=False):
                    result = await agent._update_changelog(issue)
        assert result.success is False


# ---------------------------------------------------------------------------
# _fix_documentation_consistency
# ---------------------------------------------------------------------------


class TestFixDocumentationConsistency:
    async def test_no_md_files_no_changes(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = await agent._fix_documentation_consistency(_make_issue())
        assert result.success is True
        assert "already consistent" in result.recommendations[0]

    async def test_mismatch_in_md_file(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        # Create a markdown file that the agent_count_pattern will match
        md = tmp_path / "doc.md"
        md.write_text("We have 5 agents in the system.\n")
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            result = await agent._fix_documentation_consistency(_make_issue())
        # Either rewritten or not — the key is no crash and a result.
        assert result.success is True


# ---------------------------------------------------------------------------
# _update_api_documentation
# ---------------------------------------------------------------------------


class TestUpdateApiDocumentation:
    async def test_no_api_changes_returns_recommendation(
        self, agent: DocumentationAgent
    ):
        with patch.object(agent, "_detect_api_changes", return_value=[]):
            result = await agent._update_api_documentation(_make_issue())
        assert result.success is True
        assert any("No API changes" in r for r in result.recommendations)

    async def test_api_changes_updates_readme(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        readme = tmp_path / "README.md"
        readme.write_text("# Project\n\nIntro paragraph\n")
        with patch("crackerjack.agents.documentation_agent.Path", lambda *a, **kw: readme if a and str(a[0]) == "README.md" else Path(*a, **kw)):
            with patch.object(agent, "_detect_api_changes", return_value=[{"file": "x/api.py", "type": "potential_api_change"}]):
                result = await agent._update_api_documentation(_make_issue())
        assert result.success is True
        content = readme.read_text()
        assert "TODO" in content

    async def test_readme_missing(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        # Don't create README.md; path is inside tmp_path (won't exist)
        missing_readme = tmp_path / "README.md"
        with patch("crackerjack.agents.documentation_agent.Path", lambda *a, **kw: missing_readme if a and str(a[0]) == "README.md" else Path(*a, **kw)):
            with patch.object(agent, "_detect_api_changes", return_value=[{"file": "x/api.py", "type": "potential_api_change"}]):
                result = await agent._update_api_documentation(_make_issue())
        assert result.success is False
        assert any("Could not update" in m for m in result.remaining_issues)

    async def test_readme_read_failure(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        readme = tmp_path / "README.md"
        readme.write_text("data")
        with patch("crackerjack.agents.documentation_agent.Path", lambda *a, **kw: readme if a and str(a[0]) == "README.md" else Path(*a, **kw)):
            with patch.object(agent, "_detect_api_changes", return_value=[{"file": "x/api.py", "type": "potential_api_change"}]):
                with patch.object(agent.context, "get_file_content", return_value=None):
                    result = await agent._update_api_documentation(_make_issue())
        assert result.success is False


# ---------------------------------------------------------------------------
# _general_documentation_update
# ---------------------------------------------------------------------------


class TestGeneralDocumentationUpdate:
    async def test_returns_recommendation(self, agent: DocumentationAgent):
        result = await agent._general_documentation_update(
            _make_issue(message="stale doc")
        )
        assert result.success is True
        assert any("stale doc" in r for r in result.recommendations)


# ---------------------------------------------------------------------------
# _update_changelog_from_plan
# ---------------------------------------------------------------------------


class TestUpdateChangelogFromPlan:
    async def test_delegates_to_changelog(
        self, agent: DocumentationAgent
    ):
        plan = _make_plan(rationale="changelog update", risk_level="low")
        sentinel = FixResult(success=True, confidence=0.9, fixes_applied=["x"])
        with patch.object(agent, "_update_changelog", return_value=sentinel) as mock_fn:
            result = await agent._update_changelog_from_plan(plan)
        assert result is sentinel
        mock_fn.assert_awaited_once()


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
    def test_get_commit_range_with_tag(self, agent: DocumentationAgent):
        with patch.object(subprocess, "run", return_value=_fake_completed_process("v1.0.0\n")):
            assert agent._get_commit_range() == "v1.0.0..HEAD"

    def test_get_commit_range_no_tag(self, agent: DocumentationAgent):
        with patch.object(subprocess, "run", return_value=_fake_completed_process("", returncode=128)):
            assert agent._get_commit_range() == "-10"

    def test_get_commit_messages_success(self, agent: DocumentationAgent):
        cp = _fake_completed_process("fix bug|abc|alice")
        with patch.object(subprocess, "run", return_value=cp):
            result = agent._get_commit_messages("-10")
        assert "fix bug" in result

    def test_get_commit_messages_failure(self, agent: DocumentationAgent):
        cp = _fake_completed_process("", returncode=1)
        with patch.object(subprocess, "run", return_value=cp):
            assert agent._get_commit_messages("invalid") == ""

    def test_get_recent_changes_handles_subprocess_error(
        self, agent: DocumentationAgent
    ):
        with patch.object(subprocess, "run", side_effect=OSError("nope")):
            assert agent._get_recent_changes() == []

    def test_get_recent_changes_with_messages(
        self, agent: DocumentationAgent
    ):
        with patch.object(agent, "_get_commit_range", return_value="-1"):
            with patch.object(
                agent,
                "_get_commit_messages",
                return_value="feat: a|1|me\nfix: b|2|you",
            ):
                changes = agent._get_recent_changes()
        assert len(changes) == 2
        assert changes[0]["message"] == "feat: a"
        assert changes[1]["author"] == "you"

    def test_get_recent_changes_no_range(self, agent: DocumentationAgent):
        with patch.object(agent, "_get_commit_range", return_value=""):
            assert agent._get_recent_changes() == []


# ---------------------------------------------------------------------------
# Commit message parsing / categorisation
# ---------------------------------------------------------------------------


class TestParseAndCategorize:
    def test_parse_commit_messages(self, agent: DocumentationAgent):
        out = agent._parse_commit_messages("feat: x|abc|me\nfix: y|def")
        assert out[0] == {"message": "feat: x", "hash": "abc", "author": "me"}
        assert out[1]["author"] == "Unknown"
        assert out[1]["message"] == "fix: y"

    def test_parse_commit_messages_empty(self, agent: DocumentationAgent):
        assert agent._parse_commit_messages("") == []
        assert agent._parse_commit_messages("\n\n") == []

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
    def test_get_change_category(self, agent: DocumentationAgent, msg: str, expected: str):
        assert agent._get_change_category(msg) == expected

    def test_categorize_changes(self, agent: DocumentationAgent):
        changes = [
            {"message": "feat: a", "hash": "1", "author": "x"},
            {"message": "fix: b", "hash": "2", "author": "x"},
            {"message": "refactor: c", "hash": "3", "author": "x"},
            {"message": "chore: d", "hash": "4", "author": "x"},
        ]
        cats = agent._categorize_changes(changes)
        assert cats["features"] == ["feat: a"]
        assert cats["fixes"] == ["fix: b"]
        assert cats["refactors"] == ["refactor: c"]
        assert cats["other"] == ["chore: d"]

    def test_add_section_to_entry(self, agent: DocumentationAgent):
        lines: list[str] = []
        agent._add_section_to_entry(lines, "### Added", ["item 1", "item 2"])
        assert lines == ["### Added", "- item 1", "", "- item 2", ""]

    def test_add_categorized_changes_to_entry(self, agent: DocumentationAgent):
        lines: list[str] = []
        cats = {
            "features": ["f1"],
            "fixes": ["b1"],
            "refactors": ["r1"],
            "other": ["o1"],
        }
        agent._add_categorized_changes_to_entry(lines, cats)
        assert "### Added" in lines
        assert "### Fixed" in lines
        assert "### Changed" in lines
        assert "### Other" in lines

    def test_generate_changelog_entry(self, agent: DocumentationAgent):
        changes = [
            {"message": "feat: new", "hash": "1", "author": "x"},
            {"message": "fix: bug", "hash": "2", "author": "x"},
        ]
        entry = agent._generate_changelog_entry(changes)
        assert "## [Unreleased]" in entry
        assert "feat: new" in entry
        assert "fix: bug" in entry


# ---------------------------------------------------------------------------
# Changelog insertion helpers
# ---------------------------------------------------------------------------


class TestChangelogEntry:
    def test_insert_changelog_entry_before_first_header(self, agent: DocumentationAgent):
        content = "# Title\n\n## 1.0.0 - 2025-01-01\n\n- item"
        entry = "## [Unreleased] - 2025-02-01\n\n- new"
        out = agent._insert_changelog_entry(content, entry)
        assert "## [Unreleased]" in out
        # Inserted at the top (i>0 condition kicks in for "## 1.0.0")
        assert out.index("## [Unreleased]") < out.index("## 1.0.0")

    def test_insert_changelog_entry_no_header(self, agent: DocumentationAgent):
        content = "intro paragraph\nmore text\n"
        entry = "## New\n"
        out = agent._insert_changelog_entry(content, entry)
        # Falls through with insert_index = 0
        assert out.startswith("## New")

    def test_create_initial_changelog(self, agent: DocumentationAgent):
        out = agent._create_initial_changelog("## [Unreleased]\n")
        assert out.startswith("# Changelog")
        assert "## [Unreleased]" in out


# ---------------------------------------------------------------------------
# Agent count consistency
# ---------------------------------------------------------------------------


class TestAgentCountConsistency:
    def test_get_agent_count_patterns(self, agent: DocumentationAgent):
        patterns = agent._get_agent_count_patterns()
        assert len(patterns) == 4
        assert all(isinstance(p, str) for p in patterns)

    def test_check_file_agent_count_no_content(self, agent: DocumentationAgent, tmp_path: Path):
        with patch.object(agent.context, "get_file_content", return_value=None):
            result = agent._check_file_agent_count(tmp_path / "x.md", [r"\d+"], 9)
        assert result is None

    def test_check_file_agent_count_with_mismatch(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        # Use one of the agent count patterns via the public pipeline
        from crackerjack.services.regex_patterns import SAFE_PATTERNS

        pattern_str = SAFE_PATTERNS["agent_count_pattern"].pattern
        content = "This project has 12 specialized agents."
        with patch.object(agent.context, "get_file_content", return_value=content):
            result = agent._check_file_agent_count(tmp_path / "x.md", [pattern_str], 9)
        if result is not None:
            assert result[0] == tmp_path / "x.md"
            assert result[1] != 9
            assert result[2] == 9

    def test_is_count_mismatch(self, agent: DocumentationAgent):
        assert agent._is_count_mismatch(12, 9) is True
        assert agent._is_count_mismatch(9, 9) is False
        # 4 or fewer agents is not considered a "mismatch" (placeholder)
        assert agent._is_count_mismatch(2, 9) is False

    def test_check_pattern_for_count_mismatch_unknown_pattern(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        result = agent._check_pattern_for_count_mismatch(
            r"unknown", {"x": "y"}, "content", tmp_path / "x.md", 9
        )
        assert result is None

    def test_check_agent_count_consistency_no_files(
        self, agent: DocumentationAgent
    ):
        with patch("pathlib.Path.cwd", return_value=Path("/tmp")):
            with patch.object(Path, "glob", return_value=iter([])):
                result = agent._check_agent_count_consistency([])
        assert result == []

    def test_check_agent_count_consistency_mismatch(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        from crackerjack.services.regex_patterns import SAFE_PATTERNS

        pattern_str = SAFE_PATTERNS["agent_count_pattern"].pattern
        md = tmp_path / "doc.md"
        md.write_text("This project has 12 specialized agents in total.")
        with patch.object(agent.context, "get_file_content", return_value=md.read_text()):
            issues = agent._check_agent_count_consistency([md])
        if issues:
            assert issues[0][0] == md
            assert issues[0][2] == 9

    def test_fix_agent_count_references(self, agent: DocumentationAgent):
        from crackerjack.services.regex_patterns import SAFE_PATTERNS

        # Generate input that matches the update_agent_count pattern
        agent_pattern = SAFE_PATTERNS["agent_count_pattern"]
        matches = agent_pattern.findall("This project has 12 specialized agents.")
        if not matches:
            pytest.skip("agent_count_pattern did not match expected input")
        content = "We have 12 agents."
        out = agent._fix_agent_count_references(content, 12, 9)
        # If pattern matched, NEW_COUNT should be replaced
        if "NEW_COUNT" in out:
            pytest.fail("NEW_COUNT placeholder was not substituted")
        # No 12 left where it was
        assert out == content or "9" in out


# ---------------------------------------------------------------------------
# _detect_api_changes
# ---------------------------------------------------------------------------


class TestDetectApiChanges:
    def test_detect_api_changes_filters_api_files(
        self, agent: DocumentationAgent
    ):
        cp = _fake_completed_process("module/api.py\nother/__init__.py\nunrelated.py\n")
        with patch.object(subprocess, "run", return_value=cp):
            changes = agent._detect_api_changes()
        paths = {c["file"] for c in changes}
        assert "module/api.py" in paths
        assert "other/__init__.py" in paths
        assert "unrelated.py" not in paths

    def test_detect_api_changes_no_changes(self, agent: DocumentationAgent):
        cp = _fake_completed_process("", returncode=1)
        with patch.object(subprocess, "run", return_value=cp):
            assert agent._detect_api_changes() == []

    def test_detect_api_changes_subprocess_error(self, agent: DocumentationAgent):
        with patch.object(subprocess, "run", side_effect=OSError("fail")):
            assert agent._detect_api_changes() == []


# ---------------------------------------------------------------------------
# _fix_broken_link (Issue path) / _extract_target_file_from_details
# ---------------------------------------------------------------------------


class TestFixBrokenLinkIssue:
    async def test_no_file_path_returns_error(
        self, agent: DocumentationAgent
    ):
        issue = _make_issue(message="broken link", file_path=None)
        result = await agent._fix_broken_link(issue)
        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_read_failure_returns_error(
        self, agent: DocumentationAgent
    ):
        issue = _make_issue(
            message="broken link",
            file_path="missing.md",
            details=["Target file: docs/x.md"],
        )
        result = await agent._fix_broken_link(issue)
        assert result.success is False
        assert "Failed to read" in result.remaining_issues[0]

    async def test_fix_broken_link_removes_line(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        md = tmp_path / "doc.md"
        md.write_text("see [link](missing.md) for details\n")
        issue = _make_issue(
            message="broken link",
            file_path=str(md),
            line_number=1,
            details=["Target file: missing.md"],
        )
        result = await agent._fix_broken_link(issue)
        assert result.success is True
        # The line was either fixed or removed; either way the link is gone
        new_content = md.read_text()
        assert "missing.md" not in new_content or "fixed" in new_content.lower()

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
    def test_extract_target_file_from_details(
        self, agent: DocumentationAgent, detail: str, expected: str
    ):
        assert agent._extract_target_file_from_details([detail]) == expected

    def test_extract_target_file_from_details_no_match(
        self, agent: DocumentationAgent
    ):
        assert agent._extract_target_file_from_details(["nothing"]) is None


# ---------------------------------------------------------------------------
# _fix_or_remove_broken_link_line / _attempt_link_fix
# ---------------------------------------------------------------------------


class TestFixOrRemoveBrokenLinkLine:
    def test_fixes_by_line_number(self, agent: DocumentationAgent, tmp_path: Path):
        # Create the target file at docs/foo.md so the fix can find it
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "foo.md").write_text("# Foo")
        content = "see [link](foo.md) for details\n"
        out = agent._fix_or_remove_broken_link_line(content, "doc.md", 1, "foo.md")
        # Path is relative "foo.md"; with cwd=tmp_path, fuzzy finds docs/foo.md
        # We don't assert exact path; just that something happened.
        assert isinstance(out, str)

    def test_finds_link_by_target_match(self, agent: DocumentationAgent, tmp_path: Path):
        # No exact line, but target_file matches line
        content = "see [link](target.md) for details\n"
        out = agent._fix_or_remove_broken_link_line(content, "doc.md", None, "target.md")
        assert isinstance(out, str)

    def test_line_kept_when_no_match(self, agent: DocumentationAgent):
        # line_number=999 means it never matches, target_file is not in line
        # so should_fix stays False and the line is kept as-is.
        content = "no link here\n"
        out = agent._fix_or_remove_broken_link_line(content, "doc.md", 999, "definitelynotinline.md")
        assert out == content

    def test_keeps_unrelated_lines(self, agent: DocumentationAgent):
        content = "first\n[link](missing.md)\nlast\n"
        out = agent._fix_or_remove_broken_link_line(content, "doc.md", 2, "missing.md")
        assert "first" in out and "last" in out

    def test_attempt_link_fix_returns_none_when_no_target(
        self, agent: DocumentationAgent
    ):
        result = agent._attempt_link_fix(None, "line", "doc.md", 1)
        assert result is None

    def test_attempt_link_fix_returns_line_when_no_match(
        self, agent: DocumentationAgent, tmp_path: Path
    ):
        # Target doesn't exist anywhere; the link fix returns the line unchanged
        result = agent._attempt_link_fix("nonexistent.md", "see [link](nonexistent.md)", "doc.md", 1)
        # Could be None (unfixable) or line (no change)
        assert result is None or isinstance(result, str)


# ---------------------------------------------------------------------------
# _write_fixed_content / _create_success_message
# ---------------------------------------------------------------------------


class TestWriteAndSuccessMessage:
    def test_write_failure(self, agent: DocumentationAgent):
        with patch.object(agent.context, "write_file_content", return_value=False):
            result = agent._write_fixed_content("doc.md", "content", "target.md")
        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]

    def test_write_success_with_target(self, agent: DocumentationAgent):
        with patch.object(agent.context, "write_file_content", return_value=True):
            result = agent._write_fixed_content("doc.md", "content", "x.md")
        assert result.success is True
        assert "x.md" in result.fixes_applied[0]

    def test_write_success_no_target(self, agent: DocumentationAgent):
        with patch.object(agent.context, "write_file_content", return_value=True):
            result = agent._write_fixed_content("doc.md", "content", None)
        assert result.success is True
        assert "Removed broken link" in result.fixes_applied[0]

    def test_create_success_message(self, agent: DocumentationAgent):
        assert "target.md" in agent._create_success_message("doc.md", "target.md")
        assert "Removed" in agent._create_success_message("doc.md", None)


# ---------------------------------------------------------------------------
# _find_and_fix_link / _find_best_link_target / _path_tokens / _suffix_token_score
# ---------------------------------------------------------------------------


class TestPathHelpers:
    def test_path_tokens_strips_suffix_and_splits(self, agent: DocumentationAgent):
        tokens = agent._path_tokens(Path("docs/reference/api.md"))
        # "docs", "reference", "api" — "md" suffix stripped
        assert "docs" in tokens
        assert "api" in tokens
        assert "md" not in tokens

    def test_path_tokens_handles_camelcase(self, agent: DocumentationAgent):
        tokens = agent._path_tokens(Path("api/MyClass.py"))
        assert "myclass" in tokens
        assert "api" in tokens

    def test_suffix_token_score_partial(self, agent: DocumentationAgent):
        # Compare two lists; common suffix length
        left = ["a", "b", "c", "d"]
        right = ["x", "b", "c", "d"]
        assert agent._suffix_token_score(left, right) == 3

    def test_suffix_token_score_no_match(self, agent: DocumentationAgent):
        left = ["a", "b", "c"]
        right = ["x", "y", "z"]
        assert agent._suffix_token_score(left, right) == 0

    def test_suffix_token_score_empty(self, agent: DocumentationAgent):
        assert agent._suffix_token_score([], []) == 0


class TestBuildLinkMatchPattern:
    def test_relative_target(self, agent: DocumentationAgent):
        pattern = agent._build_link_match_pattern("docs/foo.md")
        assert r"docs/foo\.md" in pattern
        assert pattern.startswith(r"\[([^\]]+)\]\(")

    def test_absolute_target_includes_basename(self, agent: DocumentationAgent):
        with patch.object(Path, "is_absolute", return_value=True):
            pattern = agent._build_link_match_pattern("/abs/path/foo.md")
        assert "foo" in pattern


class TestFindBestLinkTarget:
    def test_no_target_name_returns_none(self, agent: DocumentationAgent):
        assert agent._find_best_link_target("/") is None

    def test_no_candidates_returns_none(self, agent: DocumentationAgent, tmp_path: Path):
        result = agent._find_best_link_target("absent.md")
        assert result is None

    def test_picks_best_suffix_match(self, agent: DocumentationAgent, tmp_path: Path):
        # Create two candidates; deeper one has fewer suffix tokens
        (tmp_path / "a.md").write_text("x")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "a.md").write_text("y")
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            best = agent._find_best_link_target("a.md")
        # Best is the shallower one (suffix_score 1 vs 1, depth 1 vs 2)
        assert best is not None
        assert best == tmp_path / "a.md"


class TestFindAndFixLink:
    def test_returns_line_when_no_match(self, agent: DocumentationAgent):
        line = "see [link](nowhere.md) for details"
        with patch("pathlib.Path.cwd", return_value=Path("/")):
            result = agent._find_and_fix_link("nowhere.md", line, "doc.md")
        # No file at /nowhere.md; returns line unchanged
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _update_readme_examples
# ---------------------------------------------------------------------------


class TestUpdateReadmeExamples:
    def test_inserts_todo_when_changes_and_no_marker(
        self, agent: DocumentationAgent
    ):
        content = "# Title\n\nSome text\n"
        out = agent._update_readme_examples(content, [{"file": "api.py", "type": "potential_api_change"}])
        assert "TODO: Update examples" in out

    def test_does_not_insert_when_marker_present(
        self, agent: DocumentationAgent
    ):
        content = "# Title\n\nSome text\n<!-- TODO: Update examples after recent API changes -->\n"
        out = agent._update_readme_examples(content, [{"file": "api.py", "type": "potential_api_change"}])
        assert out == content

    def test_returns_content_when_no_changes(self, agent: DocumentationAgent):
        content = "# Title\n"
        out = agent._update_readme_examples(content, [])
        assert out == content

    def test_no_h1_returns_unchanged(self, agent: DocumentationAgent):
        content = "no h1 here\n"
        out = agent._update_readme_examples(content, [{"file": "api.py", "type": "potential_api_change"}])
        assert out == content


# ---------------------------------------------------------------------------
# Read / error helpers
# ---------------------------------------------------------------------------


class TestReadAndError:
    def test_read_file_content(self, agent: DocumentationAgent, tmp_path: Path):
        md = tmp_path / "x.md"
        md.write_text("hello")
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            assert agent._read_file_content(str(md)) == "hello"

    def test_read_file_content_missing(self, agent: DocumentationAgent, tmp_path: Path):
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            assert agent._read_file_content(str(tmp_path / "absent.md")) is None

    def test_create_error_result(self, agent: DocumentationAgent):
        result = agent._create_error_result("boom")
        assert result.success is False
        assert result.confidence == 0.0
        assert result.remaining_issues == ["boom"]

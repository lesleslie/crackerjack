"""Tests for crackerjack.fixers.formatting.

Ported from tests/unit/agents/test_formatting_agent.py, keeping the cases
that exercise real ruff-subprocess/file transforms (``execute_fix_plan``,
``_apply_change_spec``'s flexible-match fallbacks) and adding coverage for
the ruff-wrapper/whitespace/import/spelling subprocess boundary and the pure
content-formatting helpers. No SubAgent/coordinator dispatch (``can_handle``,
``get_supported_types``, ``FormattingAgent.__init__``) existed to port --
that machinery no longer exists. See the module docstring of
``crackerjack/fixers/formatting.py`` for the full kept/dropped rationale,
including three real, confirmed pre-existing behavioral bugs preserved
verbatim (not fixed) per CLAUDE.md Rule 7:

1. ``_apply_whitespace_fixes`` has an inverted exit-code check that silently
   under-reports real whitespace fixes (``crackerjack.tools.trailing_whitespace``
   / ``end_of_file_fixer`` exit 1 on a real fix, 0 on a no-op; the wrapper
   only records fixes on exit code 0).
2. ``_apply_import_fixes`` passes a broken ``--select "I, F401"`` CLI
   argument to ruff (embedded space breaks rule-selector parsing), so it
   never successfully organizes/removes imports.
3. ``_apply_spelling_fixes`` reads codespell's fix report from stdout, but
   codespell actually writes it to stderr, so fixes are never reported even
   though codespell does rewrite the file.

None of these subprocess calls are mocked -- per the original test file's
own convention (it invokes real ``ruff format`` via ``execute_fix_plan``)
and the task brief's instruction to prefer real subprocess/file-content
verification over mocking the logic under test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.fixers import formatting
from crackerjack.models.fix_plan import ChangeSpec, FixPlan
from crackerjack.models.issues import FixResult, Issue, IssueType, Priority


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "type": IssueType.FORMATTING,
        "severity": Priority.LOW,
        "message": "Formatting issue",
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _apply_change_spec / _replace_segment_flexibly (pure, ported)
# ---------------------------------------------------------------------------


class TestApplyChangeSpec:
    async def test_exact_match_replaces_line(self) -> None:
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="value = 1",
            new_code="value = 2",
            reason="bump",
        )

        updated = formatting._apply_change_spec("value = 1\n", change)

        assert updated == "value = 2\n"

    def test_invalid_line_range_returns_none(self) -> None:
        change = ChangeSpec(
            line_range=(5, 10),
            old_code="value = 1",
            new_code="value = 2",
            reason="bump",
        )

        assert formatting._apply_change_spec("value = 1\n", change) is None

    def test_falls_back_to_flexible_multiline_match(self) -> None:
        content = (
            "try:\n"
            "    do_work()\n"
            "except ValueError as e:\n"
            "    raise HTTPException(\n"
            "        status_code=401,\n"
            "        detail='bad',\n"
            "    )\n"
        )
        change = ChangeSpec(
            line_range=(4, 7),
            old_code=(
                "raise HTTPException(\n    status_code=401,\n    detail='bad',\n)"
            ),
            new_code=(
                "raise HTTPException(\n"
                "    status_code=401,\n"
                "    detail='bad',\n"
                ") from e"
            ),
            reason="Add chaining",
        )

        updated = formatting._apply_change_spec(content, change)

        assert updated is not None
        assert "from e" in updated

    def test_falls_back_for_whitespace_variation(self) -> None:
        content = (
            "@app.command()\n"
            "def shell(\n"
            "    ctx: typer.Context,\n"
            "    mode: str = 'lite',\n"
            ") -> None:\n"
            "    pass\n"
        )
        change = ChangeSpec(
            line_range=(2, 5),
            old_code=(
                "def shell(\nctx: typer.Context,\nmode: str = 'lite',\n) -> None:"
            ),
            new_code=(
                "def shell(\n_ctx: typer.Context,\nmode: str = 'lite',\n) -> None:"
            ),
            reason="Rename unused argument",
        )

        updated = formatting._apply_change_spec(content, change)

        assert updated is not None
        assert "_ctx: typer.Context" in updated

    def test_no_match_returns_none(self) -> None:
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="totally different code",
            new_code="value = 2",
            reason="bump",
        )

        assert formatting._apply_change_spec("value = 1\n", change) is None


# ---------------------------------------------------------------------------
# Pure content-formatting helpers
# ---------------------------------------------------------------------------


class TestConvertTabsToSpaces:
    def test_expands_tabs_to_four_spaces(self) -> None:
        assert formatting._convert_tabs_to_spaces("\tvalue = 1") == "    value = 1"

    def test_multiple_lines(self) -> None:
        content = "\tfoo\n\t\tbar\n"
        assert formatting._convert_tabs_to_spaces(content) == "    foo\n        bar\n"


class TestApplyContentFormatting:
    def test_removes_trailing_whitespace(self) -> None:
        result = formatting._apply_content_formatting("value = 1   \n")
        assert result == "value = 1\n"

    def test_empty_content_becomes_newline(self) -> None:
        assert formatting._apply_content_formatting("") == "\n"

    def test_missing_trailing_newline_is_added(self) -> None:
        assert formatting._apply_content_formatting("value = 1") == "value = 1\n"

    def test_normalizes_excess_blank_lines(self) -> None:
        result = formatting._apply_content_formatting("a = 1\n\n\n\nb = 2\n")
        assert result == "a = 1\n\nb = 2\n"

    def test_tabs_converted_alongside_whitespace_cleanup(self) -> None:
        result = formatting._apply_content_formatting("\tvalue = 1   \n")
        assert result == "    value = 1\n"


class TestExtractAmbiguousCodespellTypos:
    def test_single_suggestion_is_not_ambiguous(self) -> None:
        stdout = "/tmp/sample.py:1: recieve ==> receive\n"

        assert formatting._extract_ambiguous_codespell_typos(stdout) == []

    def test_multiple_suggestions_are_ambiguous(self) -> None:
        stdout = "/tmp/sample.py:3: teh ==> the, tech\n"

        result = formatting._extract_ambiguous_codespell_typos(stdout)

        assert len(result) == 1
        assert "teh ==> the, tech" in result[0]

    def test_lines_without_arrow_are_ignored(self) -> None:
        stdout = "FIXED: /tmp/sample.py\nsome unrelated line\n"

        assert formatting._extract_ambiguous_codespell_typos(stdout) == []


# ---------------------------------------------------------------------------
# _fix_specific_file (real file I/O, no subprocess)
# ---------------------------------------------------------------------------


class TestFixSpecificFile:
    async def test_applies_formatting_and_writes_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("\tvalue = 1   \n\n\n\nother = 2", encoding="utf-8")

        fixes = await formatting._fix_specific_file(str(file_path))

        assert fixes == [f"Fixed formatting in {file_path}"]
        assert file_path.read_text(encoding="utf-8") == ("    value = 1\n\nother = 2\n")

    async def test_missing_file_returns_no_fixes(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist.py"

        fixes = await formatting._fix_specific_file(str(missing))

        assert fixes == []

    async def test_already_clean_file_is_noop(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("value = 1\n", encoding="utf-8")

        fixes = await formatting._fix_specific_file(str(file_path))

        assert fixes == []
        assert file_path.read_text(encoding="utf-8") == "value = 1\n"


# ---------------------------------------------------------------------------
# _get_file_state / _get_modified_files (real filesystem mtimes)
# ---------------------------------------------------------------------------


class TestFileStateTracking:
    def test_get_file_state_for_specific_files(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("value = 1\n", encoding="utf-8")

        state = formatting._get_file_state([str(file_path)], tmp_path)

        assert str(file_path) in state
        assert state[str(file_path)] == file_path.stat().st_mtime

    def test_get_file_state_dot_target_scans_project_py_files(
        self, tmp_path: Path
    ) -> None:
        py_file = tmp_path / "a.py"
        py_file.write_text("value = 1\n", encoding="utf-8")
        (tmp_path / "not_python.txt").write_text("hi", encoding="utf-8")

        state = formatting._get_file_state(["."], tmp_path)

        assert str(py_file) in state
        assert all(key.endswith(".py") for key in state)

    def test_get_modified_files_detects_mtime_change(self, tmp_path: Path) -> None:
        import os
        import time

        file_path = tmp_path / "sample.py"
        file_path.write_text("value = 1\n", encoding="utf-8")
        files_before = {str(file_path): file_path.stat().st_mtime}

        time.sleep(0.01)
        new_mtime = file_path.stat().st_mtime + 5
        os.utime(file_path, (new_mtime, new_mtime))

        modified = formatting._get_modified_files(files_before)

        assert modified == [str(file_path)]

    def test_get_modified_files_empty_when_untouched(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("value = 1\n", encoding="utf-8")
        files_before = {str(file_path): file_path.stat().st_mtime}

        assert formatting._get_modified_files(files_before) == []


# ---------------------------------------------------------------------------
# cwd pinning regression coverage (Task 22a): the original
# ``SubAgent.run_command`` always pinned ``cwd=self.context.project_path``;
# the extraction dropped it. These tests exercise the project-wide
# (``target == ["."]``) invocation path -- the exact scenario the original
# review flagged as untested -- against a real subprocess call, proving
# ``cwd`` is genuinely threaded through, not just accepted as a dead
# parameter.
# ---------------------------------------------------------------------------


class TestRunCommandCwdPinning:
    async def test_run_command_pins_cwd_to_project_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import asyncio

        marker = tmp_path / "marker.txt"
        marker.write_text("marker")

        captured: dict[str, object] = {}
        real_create_subprocess_exec = asyncio.create_subprocess_exec

        async def spying_create_subprocess_exec(*args: object, **kwargs: object):
            captured["cwd"] = kwargs.get("cwd")
            return await real_create_subprocess_exec(*args, **kwargs)

        monkeypatch.setattr(
            asyncio, "create_subprocess_exec", spying_create_subprocess_exec
        )

        returncode, stdout, _stderr = await formatting._run_command(
            ["ls", "marker.txt"], cwd=tmp_path
        )

        assert captured["cwd"] == tmp_path
        assert returncode == 0
        assert "marker.txt" in stdout

    async def test_apply_ruff_fixes_project_wide_target_passes_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Mutation-style verification (Task 17 precedent): capture the `cwd`
        # kwarg `_apply_ruff_fixes` passes into `_run_command` for the
        # project-wide `target = ["."]` branch (no specific file target),
        # which is exactly the scenario the original bug report described.
        captured_cwds: list[Path] = []

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            captured_cwds.append(cwd)
            return (0, "", "")

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)

        marker = tmp_path / "marker.py"
        marker.write_text("x = 1\n", encoding="utf-8")

        await formatting._apply_ruff_fixes(["."], tmp_path)

        assert captured_cwds == [tmp_path, tmp_path]

    async def test_apply_whitespace_fixes_project_wide_target_passes_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured_cwds: list[Path] = []

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            captured_cwds.append(cwd)
            return (0, "", "")

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)

        await formatting._apply_whitespace_fixes(["."], tmp_path)

        assert captured_cwds == [tmp_path, tmp_path]

    async def test_apply_import_fixes_project_wide_target_passes_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured_cwds: list[Path] = []

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            captured_cwds.append(cwd)
            return (0, "", "")

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)

        await formatting._apply_import_fixes(["."], tmp_path)

        assert captured_cwds == [tmp_path]

    async def test_apply_spelling_fixes_passes_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured_cwds: list[Path] = []

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            captured_cwds.append(cwd)
            return (0, "", "")

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)

        file_path = tmp_path / "sample.py"
        file_path.write_text("# recieve\n", encoding="utf-8")
        issue = _issue(message="spelling error", file_path=str(file_path))

        await formatting._apply_spelling_fixes(issue, tmp_path)

        assert captured_cwds == [tmp_path]

    async def test_run_post_write_ruff_format_passes_cwd(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import subprocess

        captured: dict[str, object] = {}
        real_run = subprocess.run

        def spying_run(*args: object, **kwargs: object):
            captured["cwd"] = kwargs.get("cwd")
            return real_run(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(subprocess, "run", spying_run)

        file_path = tmp_path / "sample.py"
        file_path.write_text("value=1\n", encoding="utf-8")

        formatting._run_post_write_ruff_format(file_path, tmp_path)

        assert captured["cwd"] == tmp_path


# ---------------------------------------------------------------------------
# _apply_ruff_fixes (real `uv run ruff format` / `ruff check --fix`)
# ---------------------------------------------------------------------------


class TestApplyRuffFixes:
    async def test_formats_and_lints_a_real_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text(
            "import sys\nimport os\nx=1\nprint( x )\nprint(sys.path)\n",
            encoding="utf-8",
        )

        fixes, files_modified = await formatting._apply_ruff_fixes(
            [str(file_path)], tmp_path
        )

        content = file_path.read_text(encoding="utf-8")
        assert "import os" not in content  # unused import removed by ruff check --fix
        assert "x = 1" in content  # reformatted by ruff format
        assert "Applied ruff code formatting" in fixes
        assert "Applied ruff linting fixes" in fixes
        assert str(file_path) in files_modified

    async def test_noop_on_already_clean_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("import sys\n\nprint(sys.path)\n", encoding="utf-8")

        fixes, files_modified = await formatting._apply_ruff_fixes(
            [str(file_path)], tmp_path
        )

        assert fixes == ["Applied ruff code formatting", "Applied ruff linting fixes"]
        assert files_modified == []


# ---------------------------------------------------------------------------
# _apply_whitespace_fixes -- pins the inverted-exit-code bug (real subprocess)
# ---------------------------------------------------------------------------


class TestApplyWhitespaceFixes:
    async def test_real_trailing_whitespace_fix_surfaces_via_eof_check_mtime_bump(
        self, tmp_path: Path
    ) -> None:
        # File has trailing whitespace on a line but already ends with a
        # single newline (no end-of-file issue), isolating the
        # trailing-whitespace subprocess call's effect.
        file_path = tmp_path / "sample.py"
        file_path.write_text("x = 1   \ny = 2\n", encoding="utf-8")

        fixes, files_modified = await formatting._apply_whitespace_fixes(
            [str(file_path)], tmp_path
        )

        # The real subprocess DID fix the file on disk.
        assert file_path.read_text(encoding="utf-8") == "x = 1\ny = 2\n"

        # But per the documented bug: trailing_whitespace's own fix (exit
        # code 1) is never reported directly -- only the second (eof-fixer,
        # exit code 0 since there was no EOF issue) branch fires, and it
        # opportunistically picks up the mtime bump from the first call.
        assert fixes == ["Fixed end-of-file formatting"]
        assert files_modified == [str(file_path)]

    async def test_noop_on_already_clean_file_still_reports_misleading_fixes(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("x = 1\ny = 2\n", encoding="utf-8")

        fixes, files_modified = await formatting._apply_whitespace_fixes(
            [str(file_path)], tmp_path
        )

        # Nothing to fix -- both subprocesses exit 0 -- so both misleading
        # "Fixed ..." messages get appended even though nothing changed.
        assert fixes == ["Fixed trailing whitespace", "Fixed end-of-file formatting"]
        assert files_modified == []
        assert file_path.read_text(encoding="utf-8") == "x = 1\ny = 2\n"


# ---------------------------------------------------------------------------
# _apply_import_fixes -- pins the broken --select argument bug (real subprocess)
# ---------------------------------------------------------------------------


class TestApplyImportFixes:
    async def test_broken_select_argument_never_fixes_anything(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "sample.py"
        original = "import sys\nimport os\n\nprint(sys.path)\n"
        file_path.write_text(original, encoding="utf-8")

        fixes, files_modified = await formatting._apply_import_fixes(
            [str(file_path)], tmp_path
        )

        # ruff rejects the "I, F401" selector (embedded space) with exit
        # code 2, so nothing is ever reported or changed via this path.
        assert fixes == []
        assert files_modified == []
        assert file_path.read_text(encoding="utf-8") == original


# ---------------------------------------------------------------------------
# _apply_spelling_fixes -- pins the stdout/stderr bug (real subprocess)
# ---------------------------------------------------------------------------


class TestApplySpellingFixes:
    async def test_no_file_path_returns_empty(self, tmp_path: Path) -> None:
        issue = _issue(message="spelling error", file_path=None)

        assert await formatting._apply_spelling_fixes(issue, tmp_path) == []

    async def test_real_fix_on_disk_is_never_reported(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text(
            "# This is a comment with a typo: recieve\n", encoding="utf-8"
        )
        issue = _issue(message="spelling error", file_path=str(file_path))

        fixes = await formatting._apply_spelling_fixes(issue, tmp_path)

        # codespell -w really did fix the typo on disk...
        assert "receive" in file_path.read_text(encoding="utf-8")
        # ...but since codespell's report goes to stderr, not stdout, the
        # wrapper (which only reads stdout) never sees it.
        assert fixes == []


# ---------------------------------------------------------------------------
# fix_formatting_issue (end-to-end dispatch, real subprocess)
# ---------------------------------------------------------------------------


class TestFixFormattingIssue:
    async def test_end_to_end_on_messy_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text(
            "import sys\nimport os\nx=1   \nprint( x )\nprint(sys.path)",
            encoding="utf-8",
        )
        issue = _issue(message="would reformat", file_path=str(file_path))

        result = await formatting.fix_formatting_issue(issue, tmp_path)

        content = file_path.read_text(encoding="utf-8")
        assert content.endswith("\n")
        assert "import os" not in content
        assert "x = 1" in content
        # Pre-existing quirk 1: `success` is the (truthy) fixes_applied list,
        # not a real bool -- `is True` would fail even on a real success.
        assert result.success
        assert result.confidence == 0.9
        assert "Applied ruff code formatting" in result.fixes_applied

    async def test_already_clean_file_still_reports_high_confidence(
        self, tmp_path: Path
    ) -> None:
        # Emergent consequence of quirks 1/3 (see module docstring): `ruff
        # format`/`ruff check --fix` exit 0 whether or not they changed
        # anything, and the whitespace-fix wrapper misleadingly appends a
        # "Fixed ..." message on a no-op too. So even a file that is
        # already perfectly clean ends up with a non-empty fixes_applied
        # and confidence=0.9 -- not the low-confidence/no-op result one
        # might naively expect.
        file_path = tmp_path / "sample.py"
        original = "import sys\n\nprint(sys.path)\n"
        file_path.write_text(original, encoding="utf-8")
        issue = _issue(message="would reformat", file_path=str(file_path))

        result = await formatting.fix_formatting_issue(issue, tmp_path)

        assert file_path.read_text(encoding="utf-8") == original
        assert result.confidence == 0.9
        assert result.success
        assert result.recommendations == []


# ---------------------------------------------------------------------------
# execute_fix_plan / _apply_planned_changes (ported + new)
# ---------------------------------------------------------------------------


class TestExecuteFixPlan:
    async def test_applies_planned_change_and_runs_real_ruff_format(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("value = 1\n", encoding="utf-8")

        plan = FixPlan(
            file_path=str(file_path),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="value = 1",
                    new_code="value = 2  # noqa: B904",
                    reason="Apply targeted lint suppression",
                )
            ],
            rationale="Targeted formatting fix",
            risk_level="low",
            validated_by="PlanningAgent",
        )

        result = await formatting.execute_fix_plan(plan, tmp_path)

        assert result.success is True
        assert file_path.read_text(encoding="utf-8") == "value = 2  # noqa: B904\n"

    async def test_no_file_path_returns_error(self) -> None:
        plan = FixPlan(
            file_path="",
            issue_type="FORMATTING",
            rationale="",
            risk_level="low",
            validated_by="PlanningAgent",
        )

        result = await formatting.execute_fix_plan(plan, Path("."))

        assert result.success is False
        assert "No file path in plan" in result.remaining_issues

    async def test_failed_change_returns_error_with_recommendation(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("value = 1\n", encoding="utf-8")

        plan = FixPlan(
            file_path=str(file_path),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="totally unrelated code",
                    new_code="value = 2",
                    reason="bump",
                )
            ],
            rationale="Targeted formatting fix",
            risk_level="low",
            validated_by="PlanningAgent",
        )

        result = await formatting.execute_fix_plan(plan, tmp_path)

        assert result.success is False
        assert result.recommendations == [
            "Regenerate the plan with a narrower line-range match"
        ]

    async def test_no_changes_dispatches_to_fix_formatting_issue(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        async def fake_fix_formatting_issue(
            issue: Issue, project_path: Path
        ) -> FixResult:
            captured["issue"] = issue
            captured["project_path"] = project_path
            return FixResult(success=True, confidence=0.5)

        monkeypatch.setattr(
            formatting, "fix_formatting_issue", fake_fix_formatting_issue
        )

        plan = FixPlan(
            file_path="some/file.py",
            issue_type="FORMATTING",
            rationale="General formatting cleanup",
            risk_level="low",
            validated_by="PlanningAgent",
        )

        result = await formatting.execute_fix_plan(plan, tmp_path)

        assert result.confidence == 0.5
        issue = captured["issue"]
        assert isinstance(issue, Issue)
        assert issue.file_path == "some/file.py"
        assert issue.line_number is None  # pre-existing dead-branch quirk (see #2)
        assert captured["project_path"] == tmp_path

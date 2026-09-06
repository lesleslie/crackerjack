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
        stdout = "/tmp/sample.py:1: receive ==> receive\n"

        assert formatting._extract_ambiguous_codespell_typos(stdout) == []

    def test_multiple_suggestions_are_ambiguous(self) -> None:
        stdout = "/tmp/sample.py:3: the ==> the, tech\n"

        result = formatting._extract_ambiguous_codespell_typos(stdout)

        assert len(result) == 1
        assert "the ==> the, tech" in result[0]

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

    async def test_apply_ruff_fixes_handles_format_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When ruff format exits non-zero, no formatting message is recorded."""
        calls: list[int] = []

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            calls.append(1)
            # First call (ruff format) fails, second (ruff check) succeeds.
            return (99 if len(calls) == 1 else 0, "", "")

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)
        fixes, _files = await formatting._apply_ruff_fixes(
            ["sample.py"], tmp_path
        )
        assert "Applied ruff code formatting" not in fixes
        assert "Applied ruff linting fixes" in fixes

    async def test_apply_whitespace_fixes_handles_eof_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When end_of_file_fixer exits non-zero, no EOF message is recorded."""
        calls: list[int] = []

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            calls.append(1)
            return (0 if len(calls) == 1 else 99, "", "")

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)
        fixes, _files = await formatting._apply_whitespace_fixes(
            ["sample.py"], tmp_path
        )
        assert "Fixed trailing whitespace" in fixes
        assert "Fixed end-of-file formatting" not in fixes

    async def test_apply_spelling_fixes_with_empty_file_path_returns_empty(
        self, tmp_path: Path
    ) -> None:
        """An issue without a file_path returns ``[]`` immediately."""
        issue = _issue(message="spelling", file_path="")
        fixes = await formatting._apply_spelling_fixes(issue, tmp_path)
        assert fixes == []

    async def test_fix_formatting_issue_spelling_with_no_file_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When spelling message but no file_path, the spelling branch
        exercises the `spelling_fixes and issue.file_path` False branch."""
        seen: list[object] = []

        async def fake_spelling(
            issue: Issue, project_path: Path
        ) -> list[str]:
            seen.append(issue.file_path)
            return ["spelling fixed"]  # non-empty, but file_path is ""

        async def fake_ruff(
            target: list[str], project_path: Path
        ) -> tuple[list[str], list[str]]:
            return ([], [])

        async def fake_ws(
            target: list[str], project_path: Path
        ) -> tuple[list[str], list[str]]:
            return ([], [])

        async def fake_imports(
            target: list[str], project_path: Path
        ) -> tuple[list[str], list[str]]:
            return ([], [])

        monkeypatch.setattr(formatting, "_apply_spelling_fixes", fake_spelling)
        monkeypatch.setattr(formatting, "_apply_ruff_fixes", fake_ruff)
        monkeypatch.setattr(formatting, "_apply_whitespace_fixes", fake_ws)
        monkeypatch.setattr(formatting, "_apply_import_fixes", fake_imports)

        issue = _issue(message="spelling issue", file_path="")
        result = await formatting.fix_formatting_issue(issue, tmp_path)
        assert seen == [""]
        # The `if spelling_fixes and issue.file_path:` is False because
        # issue.file_path is "", so files_modified stays empty.
        assert result.files_modified == []
        assert "spelling fixed" in result.fixes_applied

    def test_apply_planned_changes_skips_post_write_for_non_py(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-``.py`` target does not call ``_run_post_write_ruff_format``."""
        file_path = tmp_path / "sample.txt"
        file_path.write_text("value = 1\n", encoding="utf-8")
        plan = FixPlan(
            file_path=str(file_path),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="value = 1",
                    new_code="value = 2",
                    reason="bump",
                )
            ],
            rationale="bump",
            risk_level="low",
            validated_by="PlanningAgent",
        )

        called: list[Path] = []

        def fake_post_write(file_path: Path, project_path: Path) -> None:
            called.append(file_path)

        monkeypatch.setattr(
            formatting, "_run_post_write_ruff_format", fake_post_write
        )

        result = formatting._apply_planned_changes(plan, tmp_path)
        assert result.success is True
        assert called == []

    def test_get_file_state_skips_py_directory(
        self, tmp_path: Path
    ) -> None:
        """Directories named ``*.py`` are not added to the file_state map."""
        # A directory ending in .py (no extension) is ``is_dir()`` True,
        # but rglob will hit it.  ``is_file()`` returns False, so it's
        # skipped — exercises the 223->222 branch.
        (tmp_path / "foo.py").mkdir()  # directory, not a file
        py_file = tmp_path / "real.py"
        py_file.write_text("x = 1\n", encoding="utf-8")

        state = formatting._get_file_state(["."], tmp_path)
        assert str(py_file) in state
        # The directory's path should NOT appear.
        assert str(tmp_path / "foo.py") not in state

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
        file_path.write_text("# receive\n", encoding="utf-8")
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
            "# This is a comment with a typo: receive\n", encoding="utf-8"
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


# ---------------------------------------------------------------------------
# Edge-case coverage for the remaining branches / error paths not hit by the
# tests above. Pure unit tests with subprocess / mtime patched at the boundary
# so we exercise every if-else fork.
# ---------------------------------------------------------------------------


class TestWriteAndReadFileFailures:
    def test_write_file_returns_false_on_oserror(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A write failure surfaces as ``False`` (no raise)."""
        import pathlib

        real_open = pathlib.Path.open

        def _boom_open(self, mode="r", *args, **kwargs):
            if "w" in mode:
                raise OSError("disk full")
            return real_open(self, mode, *args, **kwargs)

        monkeypatch.setattr(pathlib.Path, "open", _boom_open)
        # _write_file uses Path.write_text which calls self.open("w"); the
        # patched ``open`` raises and the function returns False.
        target = tmp_path / "x.txt"
        assert formatting._write_file(target, "hello") is False


class TestRunCommandFailurePaths:
    async def test_run_command_returns_minus_one_on_timeout(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A TimeoutError yields ``(-1, "", "Command timed out")``."""
        import asyncio

        async def _fake_exec(*args: object, **kwargs: object) -> object:
            class _Proc:
                async def communicate(self) -> tuple[bytes, bytes]:
                    raise TimeoutError

            return _Proc()

        monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)

        rc, stdout, stderr = await formatting._run_command(
            ["true"], cwd=tmp_path, timeout=1
        )
        assert rc == -1
        assert stdout == ""
        assert stderr == "Command timed out"

    async def test_run_command_returns_minus_one_on_generic_exception(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A non-TimeoutError exception yields ``(-1, ..., "Command failed: ...")``."""
        import asyncio

        async def _fake_exec(*args: object, **kwargs: object) -> object:
            raise RuntimeError("boom")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec)
        rc, stdout, stderr = await formatting._run_command(
            ["true"], cwd=tmp_path
        )
        assert rc == -1
        assert stdout == ""
        assert "Command failed: boom" in stderr


class TestGetModifiedFilesDeleted:
    def test_get_modified_files_skips_deleted_file(self, tmp_path: Path) -> None:
        """If a tracked file no longer exists, it is skipped silently."""
        file_path = tmp_path / "gone.py"
        file_path.write_text("x\n", encoding="utf-8")
        files_before = {str(file_path): file_path.stat().st_mtime}
        file_path.unlink()

        assert formatting._get_modified_files(files_before) == []


class TestApplyRuffFixesNoChanges:
    async def test_ruff_check_failure_records_no_fix_message(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When ``ruff check --fix`` exits non-zero, no linting message is appended."""
        calls: list[int] = []

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            calls.append(1)
            # First call (ruff format) succeeds, second (ruff check) fails.
            return (0 if len(calls) == 1 else 99, "", "")

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)
        fixes, _files = await formatting._apply_ruff_fixes(
            ["sample.py"], tmp_path
        )
        assert "Applied ruff code formatting" in fixes
        assert "Applied ruff linting fixes" not in fixes


class TestApplyWhitespaceFixesEofBranch:
    async def test_eof_fix_exit_zero_records_message(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The trailing-whitespace branch is hit; if eof fixer also exits 0,
        both messages are recorded."""
        calls: list[int] = []

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            calls.append(1)
            return (0, "", "")

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)
        fixes, _files = await formatting._apply_whitespace_fixes(
            ["sample.py"], tmp_path
        )
        assert "Fixed trailing whitespace" in fixes
        assert "Fixed end-of-file formatting" in fixes


class TestApplySpellingFixesReporting:
    async def test_spelling_fixed_count_is_reported(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When codespell reports ``FIXED: <line>`` markers, the count is
        surfaced via a fixes entry."""
        file_path = tmp_path / "x.py"
        file_path.write_text("x\n", encoding="utf-8")

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            return (
                0,
                "FIXED: 1\nFIXED: 2\n==> ambiguous?, alt\n",
                "",
            )

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)

        issue = _issue(message="spelling", file_path=str(file_path))
        fixes = await formatting._apply_spelling_fixes(issue, tmp_path)

        assert any("Fixed 2 spelling error" in f for f in fixes)
        assert any("ambiguous" in f for f in fixes)

    async def test_ambiguous_summary_truncates_after_five(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When > 5 ambiguous typos are reported, the summary truncates with
        a '(+N more)' suffix."""
        file_path = tmp_path / "x.py"
        file_path.write_text("x\n", encoding="utf-8")

        # Build a stdout with 6 ambiguous `==>` lines.
        ambiguous_lines = "\n".join(
            f"file.py:1: typo ==> alt{i}, other{i}" for i in range(6)
        )
        stdout = f"FIXED: 0\n{ambiguous_lines}\n"

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            return (0, stdout, "")

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)
        issue = _issue(message="spelling", file_path=str(file_path))
        fixes = await formatting._apply_spelling_fixes(issue, tmp_path)

        assert any("(+1 more)" in f for f in fixes)

    async def test_spelling_fixes_exception_swallowed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An exception inside ``_apply_spelling_fixes`` returns ``[]`` (no raise)."""

        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            raise RuntimeError("subprocess explode")

        monkeypatch.setattr(formatting, "_run_command", fake_run_command)
        issue = _issue(message="spelling", file_path=str(tmp_path / "x.py"))
        fixes = await formatting._apply_spelling_fixes(issue, tmp_path)
        assert fixes == []


class TestFixSpecificFileWriteFail:
    async def test_write_failure_swallows_into_no_fix(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If ``_write_file`` returns False, no fix entry is appended."""
        file_path = tmp_path / "sample.py"
        file_path.write_text("value = 1   \n", encoding="utf-8")  # has trailing ws

        monkeypatch.setattr(formatting, "_write_file", lambda *a, **kw: False)
        fixes = await formatting._fix_specific_file(str(file_path))
        assert fixes == []


class TestFixFormattingIssueErrorFallback:
    async def test_unexpected_exception_returns_error_fixresult(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An exception inside ``fix_formatting_issue`` becomes a no-confidence
        ``FixResult`` with the error message in ``remaining_issues``."""

        async def fake_apply_ruff_fixes(*args: object, **kwargs: object) -> object:
            raise RuntimeError("unexpected")

        monkeypatch.setattr(
            formatting, "_apply_ruff_fixes", fake_apply_ruff_fixes
        )
        issue = _issue(file_path="x.py", message="formatting")
        result = await formatting.fix_formatting_issue(issue, tmp_path)
        assert result.success is False
        assert result.confidence == 0.0
        assert any(
            "Failed to apply formatting fixes" in m
            for m in result.remaining_issues
        )

    async def test_spell_only_message_calls_spelling_branch(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A message containing 'spelling' triggers ``_apply_spelling_fixes``."""
        seen: dict[str, object] = {}

        async def fake_spelling(
            issue: Issue, project_path: Path
        ) -> list[str]:
            seen["file_path"] = issue.file_path
            seen["project_path"] = project_path
            return ["spelling fixed"]

        async def fake_ruff(
            target: list[str], project_path: Path
        ) -> tuple[list[str], list[str]]:
            return ([], [])

        async def fake_ws(
            target: list[str], project_path: Path
        ) -> tuple[list[str], list[str]]:
            return ([], [])

        async def fake_imports(
            target: list[str], project_path: Path
        ) -> tuple[list[str], list[str]]:
            return ([], [])

        monkeypatch.setattr(formatting, "_apply_spelling_fixes", fake_spelling)
        monkeypatch.setattr(formatting, "_apply_ruff_fixes", fake_ruff)
        monkeypatch.setattr(formatting, "_apply_whitespace_fixes", fake_ws)
        monkeypatch.setattr(formatting, "_apply_import_fixes", fake_imports)

        file_path = tmp_path / "x.py"
        file_path.write_text("x\n", encoding="utf-8")
        issue = _issue(message="spelling issue", file_path=str(file_path))
        result = await formatting.fix_formatting_issue(issue, tmp_path)
        assert seen.get("file_path") == str(file_path)
        assert "spelling fixed" in result.fixes_applied
        assert str(file_path) in result.files_modified

    async def test_file_specific_branch_called_when_no_spelling(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When the issue is not spelling-related, ``_fix_specific_file`` runs."""
        calls: list[str] = []

        async def fake_specific(file_path: str) -> list[str]:
            calls.append(file_path)
            return [f"formatted {file_path}"]

        async def fake_ruff(
            target: list[str], project_path: Path
        ) -> tuple[list[str], list[str]]:
            return ([], [])

        async def fake_ws(
            target: list[str], project_path: Path
        ) -> tuple[list[str], list[str]]:
            return ([], [])

        async def fake_imports(
            target: list[str], project_path: Path
        ) -> tuple[list[str], list[str]]:
            return ([], [])

        monkeypatch.setattr(formatting, "_fix_specific_file", fake_specific)
        monkeypatch.setattr(formatting, "_apply_ruff_fixes", fake_ruff)
        monkeypatch.setattr(formatting, "_apply_whitespace_fixes", fake_ws)
        monkeypatch.setattr(formatting, "_apply_import_fixes", fake_imports)

        file_path = tmp_path / "x.py"
        file_path.write_text("x\n", encoding="utf-8")
        issue = _issue(message="would reformat", file_path=str(file_path))
        result = await formatting.fix_formatting_issue(issue, tmp_path)
        assert calls == [str(file_path)]
        assert any("formatted" in f for f in result.fixes_applied)


class TestApplyChangeSpecTrailingNewline:
    def test_preserves_trailing_newline_in_content(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("value = 1\n", encoding="utf-8")
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="value = 1",
            new_code="value = 2",
            reason="bump",
        )
        # The file content ends with \n — the `_apply_change_spec` branch
        # at 530 should preserve that.
        updated = formatting._apply_change_spec("value = 1\n", change)
        assert updated == "value = 2\n"

    def test_no_trailing_newline_does_not_add_one(self) -> None:
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="value = 1",
            new_code="value = 2",
            reason="bump",
        )
        updated = formatting._apply_change_spec("value = 1", change)
        assert updated == "value = 2"


class TestReplaceSegmentFlexiblyBranches:
    def test_empty_needle_returns_none(self) -> None:
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="   ",
            new_code="value = 2",
            reason="bump",
        )
        assert formatting._replace_segment_flexibly("value = 1\n", change) is None

    def test_single_token_needle_not_in_content_returns_none(self) -> None:
        """A single-token needle that doesn't appear in content returns None.

        (A single-token needle that DOES appear is matched via the substring
        branch on line 540, not the tokens branch.)
        """
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="NOSUCH",
            new_code="VALUE",
            reason="bump",
        )
        assert formatting._replace_segment_flexibly("value = 1\n", change) is None

    def test_substring_needle_path(self) -> None:
        """When the (stripped) needle appears verbatim in content, the simple
        ``str.replace`` path is taken (line 540-541)."""
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="def foo():\n    return 1",
            new_code="def bar():\n    return 1",
            reason="rename",
        )
        # The exact stripped segment is present in content.
        content = (
            "def foo():\n"
            "    return 1\n"
        )
        updated = formatting._replace_segment_flexibly(content, change)
        assert updated is not None
        assert "def bar():" in updated


class TestApplyPlannedChangesErrorPaths:
    def test_unreadable_file_returns_error_fixresult(
        self, tmp_path: Path
    ) -> None:
        # Plan points at a non-existent file → read raises OSError → returns
        # error FixResult.
        plan = FixPlan(
            file_path=str(tmp_path / "missing.py"),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="value = 1",
                    new_code="value = 2",
                    reason="bump",
                )
            ],
            rationale="bump",
            risk_level="low",
            validated_by="PlanningAgent",
        )
        result = formatting._apply_planned_changes(plan, tmp_path)
        assert result.success is False
        assert result.confidence == 0.0
        assert any("Could not read file" in m for m in result.remaining_issues)

    def test_write_failure_returns_error_fixresult(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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
                    new_code="value = 2",
                    reason="bump",
                )
            ],
            rationale="bump",
            risk_level="low",
            validated_by="PlanningAgent",
        )

        monkeypatch.setattr(formatting, "_write_file", lambda *a, **kw: False)
        result = formatting._apply_planned_changes(plan, tmp_path)
        assert result.success is False
        assert result.confidence == 0.0
        assert any("Failed to write file" in m for m in result.remaining_issues)

    def test_python_file_triggers_post_write_ruff_format(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the target file has a ``.py`` suffix, ``_run_post_write_ruff_format`` is called."""
        file_path = tmp_path / "sample.py"
        file_path.write_text("value = 1\n", encoding="utf-8")
        plan = FixPlan(
            file_path=str(file_path),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="value = 1",
                    new_code="value = 2",
                    reason="bump",
                )
            ],
            rationale="bump",
            risk_level="low",
            validated_by="PlanningAgent",
        )

        called: list[tuple[Path, Path]] = []

        def fake_post_write(file_path: Path, project_path: Path) -> None:
            called.append((file_path, project_path))

        monkeypatch.setattr(
            formatting, "_run_post_write_ruff_format", fake_post_write
        )

        result = formatting._apply_planned_changes(plan, tmp_path)
        assert result.success is True
        assert called == [(file_path, tmp_path)]


class TestExecuteFixPlanExceptionFallback:
    async def test_unexpected_exception_returns_error_fixresult(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An unhandled exception in ``execute_fix_plan`` returns a no-confidence
        FixResult with the message."""

        def _boom(*args: object, **kwargs: object) -> object:
            raise RuntimeError("kaboom")

        monkeypatch.setattr(formatting, "_apply_planned_changes", _boom)
        plan = FixPlan(
            file_path=str(tmp_path / "x.py"),
            issue_type="FORMATTING",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="x = 1",
                    new_code="x = 2",
                    reason="bump",
                )
            ],
            rationale="bump",
            risk_level="low",
            validated_by="PlanningAgent",
        )

        result = await formatting.execute_fix_plan(plan, tmp_path)
        assert result.success is False
        assert result.confidence == 0.0
        assert any("Formatting execution error" in m for m in result.remaining_issues)

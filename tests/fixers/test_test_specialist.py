"""Tests for crackerjack.fixers.test_specialist.

Ported from tests/unit/agents/test_test_specialist_agent.py, keeping only the
cases that exercise real failure-type classification (SAFE_PATTERNS-based)
and templated fixture/import/mock/path fixes. Cases exercising
SubAgent/coordinator dispatch (``can_handle``, ``get_supported_types``,
``TestSpecialistAgent.__init__``, and the confidence-scoring helpers
``_check_perfect_test_matches``/``_check_test_patterns``/
``_check_test_file_path``/``_check_general_test_failure``) were dropped,
since that machinery no longer exists -- see the module docstring of
``crackerjack/fixers/test_specialist.py`` for the full kept/dropped
rationale, including two pre-existing behavioral quirks preserved verbatim
(not fixed) per CLAUDE.md Rule 7.

Unlike the original agent tests (which mocked ``agent.context.get_file_content``/
``write_file_content``), these tests use real files under ``tmp_path`` and
assert on real on-disk output, per this task's requirement to verify actual
transform behavior rather than mocked calls.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.fixers import test_specialist as ts
from crackerjack.models.issues import Issue, IssueType, Priority


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "id": "test-issue",
        "type": IssueType.TEST_FAILURE,
        "severity": Priority.HIGH,
        "message": "Test failed",
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


class TestIdentifyFailureType:
    def test_identify_fixture_not_found(self) -> None:
        issue = _issue(message="fixture 'temp_pkg_path' not found")

        assert ts._identify_failure_type(issue) == "fixture_not_found"

    def test_identify_import_error(self) -> None:
        issue = _issue(message="ImportError: No module named 'foo'")

        assert ts._identify_failure_type(issue) == "import_error"

    def test_identify_assertion_error(self) -> None:
        issue = _issue(message="assert result == expected")

        assert ts._identify_failure_type(issue) == "assertion_error"

    def test_identify_attribute_error(self) -> None:
        issue = _issue(message="AttributeError: 'Mock' has no attribute 'test'")

        assert ts._identify_failure_type(issue) == "attribute_error"

    def test_identify_mock_spec_error(self) -> None:
        issue = _issue(message="MockSpec error occurred")

        assert ts._identify_failure_type(issue) == "mock_spec_error"

    def test_identify_hardcoded_path(self) -> None:
        issue = _issue(message="Path '/test/path' should use tmp_path fixture")

        assert ts._identify_failure_type(issue) == "hardcoded_path"

    def test_identify_missing_import(self) -> None:
        issue = _issue(message="name 'pytest' is not defined")

        assert ts._identify_failure_type(issue) == "missing_import"

    def test_identify_pydantic_validation(self) -> None:
        issue = _issue(message="ValidationError: field required")

        assert ts._identify_failure_type(issue) == "pydantic_validation"

    def test_identify_unknown_failure(self) -> None:
        issue = _issue(message="Unexpected catastrophic failure")

        assert ts._identify_failure_type(issue) == "unknown"

    def test_priority_order_fixture_before_import(self) -> None:
        # "fixture_not_found" is checked before "import_error" in
        # _FAILURE_PATTERN_NAMES -- a message matching both patterns should
        # resolve to the earlier one. "fixture 'X' not found" alone doesn't
        # also match ImportError, so use a message that could plausibly
        # trip both patterns to confirm the fixture check runs first.
        issue = _issue(
            message="fixture 'foo' not found (also: ImportError elsewhere)"
        )

        assert ts._identify_failure_type(issue) == "fixture_not_found"


class TestIsValidFilePath:
    def test_existing_file_is_valid(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("content")

        assert ts._is_valid_file_path(str(f)) is True

    def test_missing_file_is_invalid(self, tmp_path: Path) -> None:
        assert ts._is_valid_file_path(str(tmp_path / "missing.py")) is False

    def test_none_is_invalid(self) -> None:
        assert ts._is_valid_file_path(None) is False


class TestImportNeedsChecks:
    def test_needs_pytest_import(self) -> None:
        assert ts._needs_pytest_import("def test_foo(): pass") is True
        assert ts._needs_pytest_import("import pytest\ndef test_foo(): pass") is False

    def test_needs_pathlib_import(self) -> None:
        assert ts._needs_pathlib_import("p = Path('test')") is True
        assert (
            ts._needs_pathlib_import("from pathlib import Path\np = Path('test')")
            is False
        )

    def test_needs_mock_import(self) -> None:
        assert ts._needs_mock_import("m = Mock()") is True
        assert (
            ts._needs_mock_import("from unittest.mock import Mock\nm = Mock()")
            is False
        )


class TestFindImportSectionEnd:
    def test_finds_end_of_import_block(self) -> None:
        lines = [
            "import os",
            "import sys",
            "from pathlib import Path",
            "",
            "def foo(): pass",
        ]

        assert ts._find_import_section_end(lines) == 3

    def test_no_imports_returns_zero(self) -> None:
        lines = ["def foo(): pass"]

        assert ts._find_import_section_end(lines) == 0


class TestFixImportErrors:
    async def test_adds_missing_pytest_import(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_something():\n    assert True\n")
        issue = _issue(
            type=IssueType.IMPORT_ERROR,
            message="name 'pytest' is not defined",
            file_path=str(test_file),
        )

        fixes = await ts._fix_import_errors(issue)

        assert fixes == [f"Added missing pytest import to {test_file}"]
        assert test_file.read_text().startswith("import pytest\n")

    async def test_adds_missing_pathlib_import(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("import pytest\n\ndef test_path():\n    p = Path('x')\n")
        issue = _issue(
            type=IssueType.IMPORT_ERROR,
            message="Path not defined",
            file_path=str(test_file),
        )

        fixes = await ts._fix_import_errors(issue)

        assert fixes == [f"Added missing pathlib import to {test_file}"]
        assert test_file.read_text().startswith("from pathlib import Path\n")

    async def test_adds_all_three_imports_in_reverse_insertion_order(
        self, tmp_path: Path
    ) -> None:
        # Pre-existing quirk preserved verbatim: pytest is inserted at the
        # computed import-section-end (0, since there are no existing
        # imports), then pathlib and mock are each unconditionally inserted
        # at index 0 -- so the final order at the top of the file is
        # mock, then pathlib, then pytest (last-inserted-at-0 wins).
        test_file = tmp_path / "test_module.py"
        test_file.write_text(
            'def test_foo():\n    p = Path("x")\n    m = Mock()\n'
        )
        issue = _issue(
            type=IssueType.IMPORT_ERROR,
            message="undefined names",
            file_path=str(test_file),
        )

        fixes = await ts._fix_import_errors(issue)

        assert fixes == [
            f"Added missing pytest import to {test_file}",
            f"Added missing pathlib import to {test_file}",
            f"Added missing Mock import to {test_file}",
        ]
        lines = test_file.read_text().split("\n")
        assert lines[0] == "from unittest.mock import Mock"
        assert lines[1] == "from pathlib import Path"
        assert lines[2] == "import pytest"

    async def test_invalid_file_path_returns_empty(self) -> None:
        issue = _issue(
            type=IssueType.IMPORT_ERROR,
            message="Import error",
            file_path=None,
        )

        fixes = await ts._fix_import_errors(issue)

        assert fixes == []

    async def test_no_changes_needed_returns_empty(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("import pytest\n\ndef test_foo():\n    pass\n")
        issue = _issue(
            type=IssueType.IMPORT_ERROR,
            message="some import error",
            file_path=str(test_file),
        )

        fixes = await ts._fix_import_errors(issue)

        assert fixes == []


class TestFixHardcodedPaths:
    async def test_replaces_quoted_hardcoded_path(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text('def test_path():\n    p = "/test/path"\n')
        issue = _issue(
            message="Hardcoded path detected",
            file_path=str(test_file),
        )

        fixes = await ts._fix_hardcoded_paths(issue)

        assert fixes == [f"Fixed hardcoded paths in {test_file}"]
        assert test_file.read_text() == "def test_path():\n    p = tmp_path\n"

    async def test_replaces_path_call_hardcoded_path(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text('def test_path():\n    p = Path("/test/path")\n')
        issue = _issue(
            message="Hardcoded path detected",
            file_path=str(test_file),
        )

        fixes = await ts._fix_hardcoded_paths(issue)

        assert fixes == [f"Fixed hardcoded paths in {test_file}"]
        assert test_file.read_text() == "def test_path():\n    p = tmp_path\n"

    async def test_no_file_path_returns_empty(self) -> None:
        issue = _issue(message="Hardcoded path", file_path=None)

        fixes = await ts._fix_hardcoded_paths(issue)

        assert fixes == []

    async def test_no_hardcoded_path_present_returns_empty(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_path():\n    p = tmp_path\n")
        issue = _issue(message="Hardcoded path", file_path=str(test_file))

        fixes = await ts._fix_hardcoded_paths(issue)

        assert fixes == []


class TestFixMockIssues:
    async def test_replaces_console_mock_and_adds_import(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_console():\n    console = Mock()\n")
        issue = _issue(
            message="Mock spec error",
            file_path=str(test_file),
        )

        fixes = await ts._fix_mock_issues(issue)

        assert fixes == [f"Fixed Mock usage in {test_file}"]
        new_content = test_file.read_text()
        assert "console = Console()" in new_content
        assert "from rich.console import Console" in new_content

    async def test_no_console_mock_present_returns_empty(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_other():\n    x = Mock()\n")
        issue = _issue(message="Mock issue", file_path=str(test_file))

        fixes = await ts._fix_mock_issues(issue)

        assert fixes == []

    async def test_needs_console_mock_fix(self) -> None:
        assert ts._needs_console_mock_fix("console = Mock()") is True
        assert ts._needs_console_mock_fix("console = Console()") is False

    async def test_none_file_path_returns_empty(self) -> None:
        issue = _issue(message="Mock issue", file_path=None)

        fixes = await ts._fix_mock_issues(issue)

        assert fixes == []


class TestFixPydanticIssues:
    async def test_always_returns_empty_list(self) -> None:
        """Preserved verbatim: this dispatch target has always been a
        no-op stub in TestSpecialistAgent -- not fixed, per CLAUDE.md
        Rule 7."""
        issue = _issue(message="ValidationError: field required")

        assert await ts._fix_pydantic_issues(issue) == []


class TestAddTempPkgPathFixture:
    async def test_adds_fixture_after_class_definition(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text(
            "class TestModule:\n"
            "    def test_something(self, temp_pkg_path):\n"
            "        pass\n"
        )

        fixes = await ts._add_temp_pkg_path_fixture(str(test_file))

        assert fixes == [f"Added temp_pkg_path fixture to {test_file}"]
        new_content = test_file.read_text()
        assert "@pytest.fixture" in new_content
        assert "def temp_pkg_path(tmp_path) -> Path:" in new_content

    async def test_already_has_fixture_is_noop(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text(
            "@pytest.fixture\ndef temp_pkg_path(tmp_path):\n    return tmp_path\n"
        )

        fixes = await ts._add_temp_pkg_path_fixture(str(test_file))

        assert fixes == []

    async def test_no_file_path_returns_empty(self) -> None:
        assert await ts._add_temp_pkg_path_fixture(None) == []


class TestAddConsoleFixture:
    async def test_adds_fixture_and_import(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_console(console): pass")

        fixes = await ts._add_console_fixture(str(test_file))

        assert fixes == [f"Added console fixture to {test_file}"]
        new_content = test_file.read_text()
        assert new_content.startswith("from rich.console import Console\n")
        assert "def console() -> Console:" in new_content

    async def test_no_file_path_returns_empty(self) -> None:
        assert await ts._add_console_fixture(None) == []


class TestAddTempPathFixture:
    async def test_returns_note_about_builtin_fixture(self) -> None:
        fixes = await ts._add_temp_path_fixture("/tests/test_file.py")

        assert len(fixes) == 1
        assert "built-in pytest fixture" in fixes[0]
        assert "/tests/test_file.py" in fixes[0]


class TestFixMissingFixtures:
    async def test_dispatches_temp_pkg_path(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text(
            "class TestModule:\n"
            "    def test_something(self, temp_pkg_path):\n"
            "        pass\n"
        )
        issue = _issue(
            message="fixture 'temp_pkg_path' not found",
            file_path=str(test_file),
        )

        fixes = await ts._fix_missing_fixtures(issue)

        assert fixes == [f"Added temp_pkg_path fixture to {test_file}"]

    async def test_dispatches_console(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_console(console): pass")
        issue = _issue(
            message="fixture 'console' not found",
            file_path=str(test_file),
        )

        fixes = await ts._fix_missing_fixtures(issue)

        assert fixes == [f"Added console fixture to {test_file}"]

    async def test_dispatches_tmp_path_builtin_note(self) -> None:
        issue = _issue(
            message="fixture 'tmp_path' not found",
            file_path="/tests/test_file.py",
        )

        fixes = await ts._fix_missing_fixtures(issue)

        assert len(fixes) == 1
        assert "built-in pytest fixture" in fixes[0]

    async def test_unrecognized_fixture_name_returns_empty(self) -> None:
        issue = _issue(
            message="fixture 'some_custom_fixture' not found",
            file_path="/tests/test_file.py",
        )

        fixes = await ts._fix_missing_fixtures(issue)

        assert fixes == []

    async def test_message_does_not_match_pattern_returns_empty(self) -> None:
        issue = _issue(message="totally unrelated failure")

        fixes = await ts._fix_missing_fixtures(issue)

        assert fixes == []


class TestFixTestFileIssues:
    async def test_adds_pytest_import(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_something():\n    assert True\n")

        fixes = await ts._fix_test_file_issues(str(test_file))

        assert fixes == [f"Added pytest import to {test_file}"]
        assert test_file.read_text().startswith("import pytest\n")

    async def test_normalizes_assert_spacing_but_reports_no_fix_quirk(
        self, tmp_path: Path
    ) -> None:
        """Pre-existing quirk preserved verbatim: apply_test_fixes changes
        are written to disk, but never appended to the returned fixes list
        (only the "Added pytest import" branch does that). See module
        docstring quirk (2) of crackerjack/fixers/test_specialist.py."""
        test_file = tmp_path / "test_module.py"
        test_file.write_text("import pytest\n\ndef test_foo():\n    assert a==b\n")

        fixes = await ts._fix_test_file_issues(str(test_file))

        assert fixes == []
        assert "assert a == b" in test_file.read_text()

    async def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        fixes = await ts._fix_test_file_issues(str(tmp_path / "missing.py"))

        assert fixes == []


class TestApplyGeneralTestFixes:
    async def test_no_issues_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            assert cmd == [
                "uv",
                "run",
                "python",
                "-m",
                "pytest",
                "--collect-only",
                "-q",
            ]
            assert cwd == tmp_path
            return (0, "", "")

        monkeypatch.setattr(ts, "_run_command", fake_run_command)

        fixes = await ts._apply_general_test_fixes(tmp_path)

        assert fixes == []

    async def test_import_error_in_stderr_is_reported(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            return (1, "", "ImportError: cannot import name 'foo'")

        monkeypatch.setattr(ts, "_run_command", fake_run_command)

        fixes = await ts._apply_general_test_fixes(tmp_path)

        assert fixes == ["Identified import issues in test collection"]

    async def test_non_import_failure_is_not_reported(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        async def fake_run_command(
            cmd: list[str], cwd: Path, timeout: int = 300
        ) -> tuple[int, str, str]:
            return (1, "", "SyntaxError: invalid syntax")

        monkeypatch.setattr(ts, "_run_command", fake_run_command)

        fixes = await ts._apply_general_test_fixes(tmp_path)

        assert fixes == []

    async def test_run_command_pins_cwd_to_project_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Task 22a regression: exercise the real `asyncio.create_subprocess_exec`
        # call chain (not a monkeypatched `_run_command`) to prove `cwd` is
        # genuinely threaded through for the project-wide entry point (no
        # per-file target at all -- `_apply_general_test_fixes` never took
        # one), matching the original `SubAgent.run_command`'s
        # `cwd=self.context.project_path` pinning.
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

        returncode, stdout, _stderr = await ts._run_command(
            ["ls", "marker.txt"], cwd=tmp_path
        )

        assert captured["cwd"] == tmp_path
        assert returncode == 0
        assert "marker.txt" in stdout


class TestApplyFileFixes:
    async def test_test_file_path_triggers_file_fixes(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_something():\n    assert True\n")
        issue = _issue(file_path=str(test_file))

        fixes, modified = await ts._apply_file_fixes(issue)

        assert fixes == [f"Added pytest import to {test_file}"]
        # Pre-existing quirk preserved verbatim: `modified` is the same list
        # object as `fixes`, not a real bool (see module docstring quirk 1).
        assert modified is fixes

    async def test_non_test_file_path_is_noop(self) -> None:
        # Deliberately not tmp_path-derived: pytest names tmp_path
        # directories after the test function, which always starts with
        # "test_" -- since _apply_file_fixes does a plain substring check
        # on the whole path, any tmp_path-based file would spuriously
        # match. The file need not exist; the check short-circuits first.
        issue = _issue(file_path="/private/project/module.py")

        fixes, modified = await ts._apply_file_fixes(issue)

        assert fixes == []
        assert modified is False

    async def test_no_file_path_is_noop(self) -> None:
        issue = _issue(file_path=None)

        fixes, modified = await ts._apply_file_fixes(issue)

        assert fixes == []
        assert modified is False


class TestGetFailureRecommendations:
    def test_with_fixes_returns_empty(self) -> None:
        assert ts._get_failure_recommendations(["Fixed something"]) == []

    def test_without_fixes_returns_recommendations(self) -> None:
        recommendations = ts._get_failure_recommendations([])

        assert len(recommendations) == 4
        assert any("import" in r for r in recommendations)
        assert any("mock" in r.lower() for r in recommendations)
        assert any("tmp_path" in r for r in recommendations)
        assert any("assertion" in r.lower() for r in recommendations)


class TestCreateFixResult:
    def test_success_result(self) -> None:
        result = ts._create_fix_result(["Fixed X"], ["file.py"], [])

        assert result.success is True
        assert result.confidence == 0.8
        assert result.fixes_applied == ["Fixed X"]
        assert result.files_modified == ["file.py"]

    def test_failure_result(self) -> None:
        result = ts._create_fix_result([], [], ["Do X"])

        assert result.success is False
        assert result.confidence == 0.4
        assert result.recommendations == ["Do X"]


class TestCreateErrorFixResult:
    def test_wraps_error_message(self) -> None:
        result = ts._create_error_fix_result(RuntimeError("boom"))

        assert result.success is False
        assert result.confidence == 0.0
        assert "Failed to fix test issue: boom" in result.remaining_issues


async def _fake_run_command_no_issues(
    cmd: list[str], cwd: Path, timeout: int = 300
) -> tuple[int, str, str]:
    # fix_test_issue's happy path always calls _apply_general_test_fixes,
    # which shells out to `uv run python -m pytest --collect-only -q` with
    # cwd pinned to the project root. Mock it in these end-to-end tests so
    # they don't spawn a real subprocess collecting this entire repo's test
    # suite.
    return (0, "", "")


class TestFixTestIssue:
    async def test_end_to_end_missing_fixture(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ts, "_run_command", _fake_run_command_no_issues)
        test_file = tmp_path / "test_module.py"
        test_file.write_text("def test_console(console): pass")
        issue = _issue(
            message="fixture 'console' not found",
            file_path=str(test_file),
        )

        result = await ts.fix_test_issue(issue, tmp_path)

        assert result.success
        assert result.confidence == 0.8
        assert f"Added console fixture to {test_file}" in result.fixes_applied
        new_content = test_file.read_text()
        assert "from rich.console import Console" in new_content
        assert "def console() -> Console:" in new_content

    async def test_end_to_end_hardcoded_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(ts, "_run_command", _fake_run_command_no_issues)
        test_file = tmp_path / "module.py"
        test_file.write_text('p = "/test/path"\n')
        issue = _issue(
            message="Path '/test/path' should use tmp_path fixture",
            file_path=str(test_file),
        )

        result = await ts.fix_test_issue(issue, tmp_path)

        assert result.success
        assert f"Fixed hardcoded paths in {test_file}" in result.fixes_applied
        new_content = test_file.read_text()
        assert "p = tmp_path" in new_content
        assert "/test/path" not in new_content
        # pytest's tmp_path directory name always contains "test_" (it is
        # derived from the test function name), so _apply_file_fixes's
        # "test_" in issue.file_path substring check also fires here and
        # additionally adds a missing "import pytest" -- real, observable
        # behavior of the extracted pipeline, not a test artifact to hide.
        assert f"Added pytest import to {test_file}" in result.fixes_applied
        assert new_content.startswith("import pytest\n")

    async def test_no_fixes_returns_recommendations(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(ts, "_run_command", _fake_run_command_no_issues)
        issue = _issue(message="Unexpected catastrophic failure")

        result = await ts.fix_test_issue(issue, tmp_path)

        assert not result.success
        assert result.confidence == 0.4
        assert len(result.recommendations) == 4

    async def test_error_handling_returns_error_fix_result(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def raise_error(issue: Issue) -> str:
            raise RuntimeError("boom")

        monkeypatch.setattr(ts, "_identify_failure_type", raise_error)

        issue = _issue(message="Test failed")

        result = await ts.fix_test_issue(issue, tmp_path)

        assert not result.success
        assert result.confidence == 0.0
        assert "Failed to fix test issue: boom" in result.remaining_issues[0]

"""Tests for crackerjack.fixers.dead_code.

Ported from tests/test_agents/test_dead_code_removal_agent.py, keeping only
the cases that exercise real AST/regex-based detection, safety-check, and
removal logic. Cases exercising SubAgent/coordinator dispatch
(``can_handle``, ``get_supported_types``, ``DeadCodeRemovalAgent.__init__``)
were dropped, since that machinery no longer exists -- see the module
docstring of ``crackerjack/fixers/dead_code.py`` for the full kept/dropped
rationale.

New tests were added (not present in the original suite, which never
exercised ``analyze_and_fix`` at all -- mocked or otherwise) for the
backup/rollback file-edit safety mechanism, since that is this task's
special focus: real files are written to ``tmp_path``, backed up, corrupted/
failed, and the tests assert on actual on-disk content after rollback, not
just return values.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.fixers import dead_code
from crackerjack.fixers.dead_code import DeadCodeInfo
from crackerjack.models.issues import Issue, IssueType, Priority


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "id": "dc-test",
        "type": IssueType.DEAD_CODE,
        "severity": Priority.MEDIUM,
        "message": "Unused code",
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


class TestExtractConfidence:
    def test_extract_confidence_from_message(self) -> None:
        assert dead_code._extract_confidence("80% confidence") == 0.80
        assert dead_code._extract_confidence("90% confidence") == 0.90

    def test_extract_confidence_certainty_words(self) -> None:
        assert dead_code._extract_confidence("definitely unused") == 0.95
        assert dead_code._extract_confidence("certainly dead") == 0.95
        assert dead_code._extract_confidence("likely unused") == 0.75
        assert dead_code._extract_confidence("probably dead") == 0.75
        assert dead_code._extract_confidence("possibly unused") == 0.50
        assert dead_code._extract_confidence("might be dead") == 0.50

    def test_extract_confidence_default(self) -> None:
        assert dead_code._extract_confidence("unused thing") == 0.70


class TestIsTestFile:
    def test_is_test_file(self) -> None:
        assert dead_code._is_test_file(Path("tests/test_foo.py")) is True
        assert dead_code._is_test_file(Path("test_foo.py")) is True
        assert dead_code._is_test_file(Path("foo_test.py")) is True
        assert dead_code._is_test_file(Path("conftest.py")) is True
        assert dead_code._is_test_file(Path("src/foo.py")) is False
        assert dead_code._is_test_file(Path("lib/bar.py")) is False


class TestParseDeadCodeIssue:
    def test_parse_dead_code_issue_skylos_format(self) -> None:
        issue = _issue(message="Unused function 'foo' at line 10", line_number=10)
        # Pad content so the function actually lives at line 10 -- the
        # parser also walks back to collect decorators, so we need the
        # line range to be valid.
        content = "\n" * 9 + "def foo():\n    pass\n"

        result = dead_code._parse_dead_code_issue_enhanced(issue, content)
        assert result is not None
        assert result.code_type == "function"
        assert result.name == "foo"
        assert result.line_number == 10

    def test_parse_dead_code_issue_vulture_format(self) -> None:
        issue = _issue(message="Unused function 'bar' at line 5", line_number=5)
        content = "\n" * 4 + "def bar():\n    pass\n"

        result = dead_code._parse_dead_code_issue_enhanced(issue, content)
        assert result is not None
        assert result.code_type == "function"
        assert result.name == "bar"
        assert result.line_number == 5

    def test_parse_dead_code_issue_no_match_falls_back_to_line_number(self) -> None:
        issue = _issue(message="This variable looks unused", line_number=3)
        content = "\n\nx = 1\n"

        result = dead_code._parse_dead_code_issue_enhanced(issue, content)
        assert result is not None
        assert result.code_type == "variable"
        assert result.name == "unknown"
        assert result.line_number == 3

    def test_parse_dead_code_issue_no_line_number_returns_none(self) -> None:
        issue = _issue(message="No location info", line_number=None)
        result = dead_code._parse_dead_code_issue_enhanced(issue, "x = 1\n")
        assert result is None


class TestFindBlockEnd:
    def test_find_block_end_function(self) -> None:
        content = """
def foo():
    x = 1
    y = 2
    return x + y

def bar():
    pass
"""
        result = dead_code._find_block_end(content, 2, "function")
        assert result == 5

    def test_find_block_end_class(self) -> None:
        content = """
class Foo:
    def __init__(self):
        pass

    def method(self):
        pass
"""
        result = dead_code._find_block_end(content, 2, "class")
        assert result is not None


class TestGetDecorators:
    def test_get_decorators(self) -> None:
        content = """
@property
@pytest.fixture
def foo():
    pass
"""
        decorators = dead_code._get_decorators(content, 4)
        assert "@property" in decorators
        assert "@pytest.fixture" in decorators


class TestHasDocstring:
    def test_has_docstring(self) -> None:
        content = '''
def foo():
    """This is a docstring."""
    pass
'''
        assert dead_code._has_docstring(content, 1) is True

    def test_has_docstring_no_docstring(self) -> None:
        content = """
def foo():
    pass
"""
        assert dead_code._has_docstring(content, 1) is False


class TestIsExported:
    def test_is_exported_in_all(self) -> None:
        content = """
__all__ = ["foo", "bar"]
"""
        assert dead_code._is_exported(content, "foo") is True
        assert dead_code._is_exported(content, "baz") is False


class TestAnalyzeUsage:
    def test_analyze_usage_dynamic_usage(self) -> None:
        content = """
class Foo:
    pass

getattr(sys, "Foo")
"""
        info = DeadCodeInfo(
            code_type="class", name="Foo", line_number=1, confidence=0.8
        )
        result = dead_code._analyze_usage(content, info)
        assert result["has_dynamic_usage"] is True


class TestPerformSafetyChecks:
    def test_perform_safety_checks_protected_decorator(self) -> None:
        info = DeadCodeInfo(
            code_type="function",
            name="foo",
            line_number=1,
            confidence=0.8,
            decorators=["@property"],
        )
        content = """
@property
def foo():
    pass
"""
        result = dead_code._perform_safety_checks_enhanced(content, info)
        assert result["safe_to_remove"] is False
        assert "Has protected decorator: @property" in result["reasons"]

    def test_perform_safety_checks_exported(self) -> None:
        info = DeadCodeInfo(
            code_type="function", name="foo", line_number=1, confidence=0.8
        )
        content = """
__all__ = ["foo"]

def foo():
    pass
"""
        result = dead_code._perform_safety_checks_enhanced(content, info)
        assert result["safe_to_remove"] is False
        assert any("exported in __all__" in r for r in result["reasons"])

    def test_high_confidence_types_boosted(self) -> None:
        info = DeadCodeInfo(
            code_type="import", name="os", line_number=1, confidence=0.7
        )
        content = "import os\n"
        result = dead_code._perform_safety_checks_enhanced(content, info)
        assert result["confidence"] >= 0.85

    def test_low_confidence_below_threshold_is_unsafe(self) -> None:
        info = DeadCodeInfo(
            code_type="function", name="maybe", line_number=1, confidence=0.30
        )
        content = "def maybe():\n    pass\n"
        result = dead_code._perform_safety_checks_enhanced(content, info)
        assert result["safe_to_remove"] is False


class TestRemovalHelpers:
    def test_remove_import_line_enhanced(self) -> None:
        lines = ["import os", "import sys", "from foo import bar"]
        new_lines, fix = dead_code._remove_import_line_enhanced(lines, "os", 1)
        assert "import os" not in new_lines
        assert fix == "Removed import: os"

    def test_remove_function_enhanced(self) -> None:
        lines = [
            "@property",
            "def foo():",
            "    pass",
            "",
            "def bar():",
            "    pass",
        ]
        new_lines, _fix = dead_code._remove_function_enhanced(
            lines, 2, 3, ["@property"]
        )
        assert "def foo" not in "\n".join(new_lines)
        assert "def bar" in "\n".join(new_lines)

    def test_remove_class_enhanced(self) -> None:
        lines = [
            "class Foo:",
            "    def __init__(self):",
            "        pass",
            "",
            "def bar():",
            "    pass",
        ]
        new_lines, _fix = dead_code._remove_class_enhanced(lines, 1, 3, None)
        assert "class Foo" not in "\n".join(new_lines)

    def test_remove_variable_enhanced(self) -> None:
        lines = ["x = 1", "y = 2", "z = 3"]
        new_lines, _fix = dead_code._remove_variable_enhanced(lines, 1, "x")
        assert len(new_lines) == 2
        assert "x = 1" not in new_lines


class TestExportListHelpers:
    def test_should_fix_export_list(self) -> None:
        issue_with_all = _issue(message='Undefined name "foo" in __all__')
        issue_with_undefined = _issue(message="undefined name 'bar'")
        assert dead_code._should_fix_export_list(issue_with_all) is True
        assert dead_code._should_fix_export_list(issue_with_undefined) is True

    def test_extract_undefined_export_names(self) -> None:
        message = 'Undefined name "foo" in __all__'
        names = dead_code._extract_undefined_export_names(message)
        assert "foo" in names

    def test_remove_undefined_exports(self) -> None:
        content = '__all__ = ["foo", "bar", "baz"]'
        updated_content, removed = dead_code._remove_undefined_exports(
            content, ["foo", "bar"]
        )
        assert "foo" not in updated_content
        assert "bar" not in updated_content
        assert "baz" in updated_content
        assert "foo" in removed
        assert "bar" in removed

    def test_fix_undefined_exports_writes_updated_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "module.py"
        file_path.write_text('__all__ = ["foo", "bar"]\n', encoding="utf-8")
        issue = _issue(message='Undefined name "foo" in __all__')
        content = file_path.read_text(encoding="utf-8")

        result = dead_code._fix_undefined_exports(file_path, content, issue)

        assert result is not None
        assert result.success is True
        new_content = file_path.read_text(encoding="utf-8")
        assert "foo" not in new_content
        assert "bar" in new_content

    def test_fix_undefined_exports_returns_none_when_nothing_to_remove(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "module.py"
        file_path.write_text('__all__ = ["bar"]\n', encoding="utf-8")
        issue = _issue(message='Undefined name "foo" in __all__')
        content = file_path.read_text(encoding="utf-8")

        result = dead_code._fix_undefined_exports(file_path, content, issue)

        assert result is None


class TestDeadCodeInfo:
    def test_dead_code_info_creation(self) -> None:
        info = DeadCodeInfo(
            code_type="function", name="foo", line_number=10, confidence=0.8
        )
        assert info.code_type == "function"
        assert info.name == "foo"
        assert info.line_number == 10
        assert info.confidence == 0.8
        assert info.end_line is None
        assert info.decorators is None

    def test_dead_code_info_full(self) -> None:
        info = DeadCodeInfo(
            code_type="class",
            name="Foo",
            line_number=5,
            confidence=0.9,
            end_line=10,
            decorators=["@property", "@staticmethod"],
        )
        assert info.end_line == 10
        assert info.decorators is not None
        assert len(info.decorators) == 2


class TestBackupRollbackMechanism:
    """Real-file tests for the backup/rollback safety mechanism.

    This is the special focus of this extraction: verify the exact
    ``.bak``-sibling-file backup/restore sequence still works after being
    converted from ``AgentContext``-coupled methods to plain functions.
    """

    @pytest.mark.asyncio
    async def test_backup_file_creates_bak_copy_with_original_content(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("original content\n", encoding="utf-8")

        assert await dead_code._backup_file(file_path) is True

        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == "original content\n"

    @pytest.mark.asyncio
    async def test_backup_file_returns_false_when_source_missing(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "does_not_exist.py"
        assert await dead_code._backup_file(file_path) is False

    @pytest.mark.asyncio
    async def test_rollback_file_restores_original_content_after_corruption(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("original content\n", encoding="utf-8")

        assert await dead_code._backup_file(file_path) is True

        # Simulate a failed/partial edit corrupting the file on disk.
        file_path.write_text("CORRUPTED MID-EDIT\n", encoding="utf-8")
        assert file_path.read_text(encoding="utf-8") == "CORRUPTED MID-EDIT\n"

        assert await dead_code._rollback_file(file_path) is True
        assert file_path.read_text(encoding="utf-8") == "original content\n"

    @pytest.mark.asyncio
    async def test_rollback_file_returns_false_when_no_backup_exists(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "sample.py"
        file_path.write_text("original content\n", encoding="utf-8")

        assert await dead_code._rollback_file(file_path) is False
        # File is untouched since there was nothing to roll back to.
        assert file_path.read_text(encoding="utf-8") == "original content\n"


class TestFixDeadCodeIssue:
    """End-to-end tests for the ``fix_dead_code_issue`` entry point.

    The original test suite never exercised ``analyze_and_fix`` (not even
    with mocks) -- these are new tests written for this extraction, using
    real files under ``tmp_path`` and asserting on real on-disk content.
    """

    @pytest.mark.asyncio
    async def test_fix_dead_code_issue_no_file_path(self) -> None:
        issue = _issue(file_path=None)
        result = await dead_code.fix_dead_code_issue(issue)
        assert result.success is False
        assert "No file path provided" in result.remaining_issues

    @pytest.mark.asyncio
    async def test_fix_dead_code_issue_skips_test_files(self, tmp_path: Path) -> None:
        file_path = tmp_path / "test_something.py"
        file_path.write_text("def unused():\n    pass\n", encoding="utf-8")
        issue = _issue(
            message="Unused function 'unused' at line 1",
            file_path=str(file_path),
            line_number=1,
        )

        result = await dead_code.fix_dead_code_issue(issue)

        assert result.success is False
        assert any("test files" in r for r in result.remaining_issues)
        assert file_path.read_text(encoding="utf-8") == "def unused():\n    pass\n"

    @pytest.mark.asyncio
    async def test_fix_dead_code_issue_missing_file_fails_gracefully(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "missing.py"
        issue = _issue(
            message="Unused function 'foo' at line 1",
            file_path=str(file_path),
            line_number=1,
        )

        result = await dead_code.fix_dead_code_issue(issue)

        assert result.success is False
        assert "Could not read file content" in result.remaining_issues

    @pytest.mark.asyncio
    async def test_fix_dead_code_issue_removes_unused_function_with_backup(
        self, tmp_path: Path
    ) -> None:
        content = "def unused():\n    pass\n\n\ndef used():\n    return 1\n"
        file_path = tmp_path / "module.py"
        file_path.write_text(content, encoding="utf-8")

        issue = _issue(
            message="Unused function 'unused' at line 1 (90% confidence)",
            file_path=str(file_path),
            line_number=1,
        )

        result = await dead_code.fix_dead_code_issue(issue)

        assert result.success is True
        new_content = file_path.read_text(encoding="utf-8")
        assert "def unused" not in new_content
        assert "def used" in new_content

        # The backup/rollback safety mechanism creates a .bak copy before
        # any removal write, holding the pre-fix content.
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == content

    @pytest.mark.asyncio
    async def test_fix_dead_code_issue_rejects_protected_decorator_without_backup(
        self, tmp_path: Path
    ) -> None:
        content = "@property\ndef foo(self):\n    return self._foo\n"
        file_path = tmp_path / "module.py"
        file_path.write_text(content, encoding="utf-8")

        issue = _issue(
            message="Unused method 'foo' at line 2 (90% confidence)",
            file_path=str(file_path),
            line_number=2,
        )

        result = await dead_code.fix_dead_code_issue(issue)

        assert result.success is False
        assert any("protected decorator" in r for r in result.remaining_issues)
        # Safety check failed before backup/removal ever ran: file and
        # absence of a .bak sibling both confirm nothing was touched.
        assert file_path.read_text(encoding="utf-8") == content
        assert not file_path.with_suffix(file_path.suffix + ".bak").exists()

    @pytest.mark.asyncio
    async def test_fix_dead_code_issue_undefined_export_path_bypasses_backup(
        self, tmp_path: Path
    ) -> None:
        """Preserved quirk: the __all__ export-fix path writes directly,

        with no backup/rollback safety net at all -- unlike the dead-code
        removal path. This mirrors the original agent's behavior exactly
        (``_fix_undefined_exports`` never calls ``_backup_file``).
        """
        file_path = tmp_path / "module.py"
        file_path.write_text('__all__ = ["foo", "bar"]\n', encoding="utf-8")

        issue = _issue(
            message='Undefined name "foo" in __all__',
            file_path=str(file_path),
        )

        result = await dead_code.fix_dead_code_issue(issue)

        assert result.success is True
        new_content = file_path.read_text(encoding="utf-8")
        assert "foo" not in new_content
        assert "bar" in new_content
        assert not file_path.with_suffix(file_path.suffix + ".bak").exists()

    @pytest.mark.asyncio
    async def test_fix_dead_code_issue_rollback_restores_original_on_write_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulates a failure mid-edit (after backup, during the removal

        write) and confirms the rollback mechanism restores the exact
        original on-disk content -- the core safety guarantee this task
        exists to preserve.
        """
        original_content = "def unused():\n    pass\n\n\ndef used():\n    return 1\n"
        file_path = tmp_path / "module.py"
        file_path.write_text(original_content, encoding="utf-8")

        issue = _issue(
            message="Unused function 'unused' at line 1 (90% confidence)",
            file_path=str(file_path),
            line_number=1,
        )

        def _corrupt_then_report_failure(path: object, content: str) -> bool:
            # Simulate a write that lands on disk but is then judged to
            # have failed (e.g. a downstream validation error) -- proving
            # that rollback recovers real corrupted content, not just a
            # no-op no-write scenario.
            Path(str(path)).write_text("CORRUPTED MID-EDIT", encoding="utf-8")
            return False

        monkeypatch.setattr(dead_code, "_write_file", _corrupt_then_report_failure)

        result = await dead_code.fix_dead_code_issue(issue)

        assert result.success is False
        assert file_path.read_text(encoding="utf-8") == original_content

        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        assert backup_path.exists()

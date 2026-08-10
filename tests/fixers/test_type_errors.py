"""Tests for crackerjack.fixers.type_errors.

Ported from tests/test_agents/test_type_error_specialist.py, keeping only
the cases that exercise real AST/regex-based type-error fixing logic.
Cases exercising SubAgent/coordinator dispatch (``can_handle``,
``get_supported_types``, ``TypeErrorSpecialistAgent.__init__``) were
dropped, since that machinery no longer exists -- see the module docstring
of ``crackerjack/fixers/type_errors.py`` for the full kept/dropped
rationale.

``TestStripNonErrorOutput`` from the original file (testing
``crackerjack.parsers.factory.strip_non_error_output``, an unrelated
module) was not ported -- it doesn't exercise anything in
``crackerjack.fixers.type_errors``. See this task's report for a flag to
the reviewer about that coverage.

New tests were added for ``fix_type_error_issue`` (the ported
``analyze_and_fix`` entry point) that write real files to ``tmp_path`` and
assert on actual on-disk content, replacing the original's
``AgentContext``-mock-based ``test_analyze_and_fix_no_file_path``/
``test_analyze_and_fix_file_not_found``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from crackerjack.fixers import type_errors
from crackerjack.models.issues import Issue, IssueType, Priority


def _issue(**kwargs: object) -> Issue:
    defaults: dict[str, object] = {
        "type": IssueType.TYPE_ERROR,
        "severity": Priority.MEDIUM,
        "message": "type error",
    }
    defaults.update(kwargs)
    return Issue(**defaults)  # type: ignore[arg-type]


class TestAddFutureAnnotations:
    def test_add_future_annotations(self) -> None:
        content = "import os\n\ndef foo():\n    pass\n"
        new_content, fixes = type_errors._add_future_annotations(content)
        assert "from __future__ import annotations" in new_content
        assert "Added __future__ annotations import" in fixes

    def test_add_future_annotations_already_present(self) -> None:
        content = "from __future__ import annotations\n\ndef foo():\n    pass\n"
        new_content, fixes = type_errors._add_future_annotations(content)
        assert new_content == content
        assert fixes == []


class TestFixMissingReturnTypes:
    def test_fix_missing_return_types(self) -> None:
        content = """
def foo(x, y):
    return x + y
"""
        issue = _issue(message="Missing return type annotation", line_number=2)
        new_content, _fixes = type_errors._fix_missing_return_types(content, issue)
        assert "-> None:" in new_content


class TestFixVarAnnotated:
    def test_fix_var_annotated_dict_pattern(self) -> None:
        """`data.get(k) or {}` from json.loads should get `dict[str, object]`."""
        content = (
            "import json\n"
            "def parse(out: str) -> list[str]:\n"
            "    data = json.loads(out)\n"
            "    entries = data.get('errors') or {}\n"
            "    for k, v in entries.items():\n"
            "        pass\n"
            "    return []\n"
        )
        issue = _issue(
            message='Need type annotation for "entries"  [var-annotated]',
            file_path="mod.py",
            line_number=4,
            stage="zuban",
        )
        new_content, fixes = type_errors._fix_var_annotated(content, issue)
        assert fixes, f"Expected a fix, got none. new_content:\n{new_content}"
        assert "dict[str, object]" in new_content, new_content
        assert new_content.count("entries") == content.count("entries")

    def test_fix_var_annotated_list_pattern(self) -> None:
        """`[...] or []` should get `list[object]`."""
        content = (
            "def f(x: object) -> None:\n"
            "    items = x.items() if hasattr(x, 'items') else []\n"
            "    for it in items:\n"
            "        pass\n"
        )
        issue = _issue(
            message='Need type annotation for "items"  [var-annotated]',
            file_path="mod.py",
            line_number=2,
            stage="zuban",
        )
        new_content, fixes = type_errors._fix_var_annotated(content, issue)
        assert fixes
        assert "list[object]" in new_content, new_content

    def test_fix_var_annotated_ignores_non_matching_messages(self) -> None:
        content = "x = 1\n"
        issue = _issue(
            message="Argument 1 has incompatible type",
            file_path="mod.py",
            line_number=1,
            stage="zuban",
        )
        new_content, fixes = type_errors._fix_var_annotated(content, issue)
        assert new_content == content
        assert fixes == []

    def test_fix_var_annotated_skips_when_line_out_of_range(self) -> None:
        content = "x = 1\n"
        issue = _issue(
            message='Need type annotation for "x"  [var-annotated]',
            file_path="mod.py",
            line_number=999,
            stage="zuban",
        )
        new_content, fixes = type_errors._fix_var_annotated(content, issue)
        assert new_content == content
        assert fixes == []


class TestAddTypingImports:
    def test_add_typing_imports_any(self) -> None:
        content = "import os\n"
        issue = _issue(message="Any is not defined")
        new_content, _fixes = type_errors._add_typing_imports(content, issue)
        assert "from typing import Any" in new_content

    def test_add_typing_imports_optional(self) -> None:
        content = "import os\n"
        issue = _issue(message="Optional is not defined")
        new_content, _fixes = type_errors._add_typing_imports(content, issue)
        assert "from typing import Optional" in new_content

    def test_add_typing_imports_union(self) -> None:
        content = "import os\n"
        issue = _issue(message="Union is not defined")
        new_content, _fixes = type_errors._add_typing_imports(content, issue)
        assert "from typing import Union" in new_content


class TestAddCommonImports:
    def test_add_common_imports_operator(self) -> None:
        content = "import os\n"
        issue = _issue(message="operator.add is not defined")
        new_content, _fixes = type_errors._add_common_imports(content, issue)
        assert "import operator" in new_content

    def test_add_common_imports_suppress(self) -> None:
        content = "import os\n"
        issue = _issue(message="suppress is not defined")
        new_content, _fixes = type_errors._add_common_imports(content, issue)
        assert "from contextlib import suppress" in new_content


class TestFixSuppressTupleArgType:
    def test_fix_suppress_tuple_arg_type(self) -> None:
        content = "with suppress((ValueError, TypeError)):\n    pass\n"
        issue = _issue(message="suppress")
        new_content, _fixes = type_errors._fix_suppress_tuple_arg_type(content, issue)
        assert "with suppress(ValueError, TypeError):" in new_content


class TestInferReturnTypes:
    def test_infer_and_add_return_types(self) -> None:
        content = """
def foo():
    return 42
"""
        issue = _issue(message="Missing return type", line_number=2)
        new_content, _fixes = type_errors._infer_and_add_return_types(content, issue)
        assert "-> int" in new_content

    def test_infer_return_type_from_body_int(self) -> None:
        content = """
def foo():
    return 42
"""
        tree = ast.parse(content)
        func = tree.body[0]
        result = type_errors._infer_return_type_from_body(func, content)
        assert result == "int"

    def test_infer_return_type_from_body_str(self) -> None:
        content = """
def foo():
    return "hello"
"""
        tree = ast.parse(content)
        func = tree.body[0]
        result = type_errors._infer_return_type_from_body(func, content)
        assert result == "str"

    def test_infer_return_type_from_body_bool(self) -> None:
        content = """
def foo():
    return True
"""
        tree = ast.parse(content)
        func = tree.body[0]
        result = type_errors._infer_return_type_from_body(func, content)
        assert result == "bool"

    def test_infer_return_type_from_body_none(self) -> None:
        content = """
def foo():
    pass
"""
        tree = ast.parse(content)
        func = tree.body[0]
        result = type_errors._infer_return_type_from_body(func, content)
        assert result == "None"

    def test_infer_type_from_constant(self) -> None:
        for value, expected in [
            (ast.Constant(value=42), "int"),
            (ast.Constant(value="str"), "str"),
            (ast.Constant(value=3.14), "float"),
            (ast.Constant(value=True), "bool"),
            (ast.Constant(value=None), "None"),
        ]:
            result = type_errors._infer_constant_type(value)
            assert result == expected

    def test_infer_type_from_list(self) -> None:
        node = ast.List(elts=[ast.Constant(value=1), ast.Constant(value=2)])
        result = type_errors._infer_list_type(node)
        assert result == "list[int]"

    def test_infer_type_from_dict(self) -> None:
        node = ast.Dict(
            keys=[ast.Constant(value="key")],
            values=[ast.Constant(value=1)],
        )
        result = type_errors._infer_dict_type(node)
        assert result == "dict[str, int]"


class TestFixComplexGenericTypes:
    def test_fix_complex_generic_types(self) -> None:
        content = """
from typing import List, Dict
x: List[int] = []
y: Dict[str, int] = {}
"""
        issue = _issue(message="Generic type arguments")
        new_content, _fixes = type_errors._fix_complex_generic_types(content, issue)
        assert "list[" in new_content or "List[" in new_content


class TestFixOptionalUnionTypes:
    def test_fix_optional_union_types(self) -> None:
        content = """
from __future__ import annotations
from typing import Optional, Union

def foo(x: Optional[int]) -> Union[str, None]:
    pass
"""
        issue = _issue(message="Optional or Union")
        new_content, fixes = type_errors._fix_optional_union_types(content, issue)
        assert (
            "int | None" in new_content
            or "Optional[int]" not in new_content
            or len(fixes) > 0
        )

    def test_split_union_types(self) -> None:
        result = type_errors._split_union_types("int, str")
        assert len(result) == 2

        result = type_errors._split_union_types("List[int], Dict[str, Any]")
        assert len(result) == 2


class TestDetectAndFixProtocolPatterns:
    def test_detect_and_fix_protocol_patterns(self) -> None:
        content = """
class Foo:
    def method1(self):
        pass

    def method2(self):
        pass
"""
        issue = _issue(message="Protocol structural typing")
        _new_content, fixes = type_errors._detect_and_fix_protocol_patterns(
            content, issue
        )
        assert len(fixes) > 0


class TestSelfTypeHelpers:
    def test_is_self_type_issue(self) -> None:
        assert type_errors._is_self_type_issue("return type of self") is True
        assert type_errors._is_self_type_issue("same type as self") is True
        assert type_errors._is_self_type_issue("some other issue") is False

    def test_collect_class_names(self) -> None:
        content = """
class Foo:
    pass

class Bar:
    pass
"""
        tree = ast.parse(content)
        names = type_errors._collect_class_names(tree)
        assert "Foo" in names
        assert "Bar" in names

    def test_should_skip_method_staticmethod(self) -> None:
        node = ast.FunctionDef(
            name="foo",
            args=ast.arguments(),
            body=[ast.Pass()],
            decorator_list=[ast.Name(id="staticmethod", ctx=ast.Load())],
        )
        assert type_errors._should_skip_method(node) is True

    def test_should_skip_method_dunder(self) -> None:
        node = ast.FunctionDef(
            name="_private",
            args=ast.arguments(),
            body=[ast.Pass()],
            decorator_list=[],
        )
        assert type_errors._should_skip_method(node) is True

    def test_should_not_skip_method_dunder_magic(self) -> None:
        node = ast.FunctionDef(
            name="__enter__",
            args=ast.arguments(),
            body=[ast.Pass()],
            decorator_list=[],
        )
        assert type_errors._should_skip_method(node) is False

    def test_add_self_type_for_methods_is_a_no_op_due_to_preexisting_regex_bug(
        self,
    ) -> None:
        """Pins a genuine pre-existing bug, not a new one from this port.

        ``_try_convert_to_self`` does
        ``re.sub(f"\\b-> {class_name}\\b", "-> Self", old_line)``. The
        leading ``\\b`` requires a word/non-word transition immediately
        before ``-``, but in any syntactically valid Python signature the
        character before ``-`` is always ``)`` or whitespace -- both
        non-word characters -- so that boundary can never be satisfied.
        This makes the "-> Self" conversion unreachable for any real
        function signature; ``_add_self_type_for_methods`` is effectively
        permanent dead code in the original agent (confirmed identical
        regex, verbatim, in
        ``crackerjack.agents.type_error_specialist.TypeErrorSpecialistAgent._try_convert_to_self``).
        Preserved verbatim per CLAUDE.md Rule 7, not "fixed" -- see the
        module docstring's "Preserved quirks" section, item 6.
        """
        content = (
            "from __future__ import annotations\n\n\n"
            "class Builder:\n"
            "    def with_name(self, name: str) -> Builder:\n"
            "        self.name = name\n"
            "        return self\n"
        )
        issue = _issue(message="return type could use Self (same type as instance)")
        new_content, fixes = type_errors._add_self_type_for_methods(content, issue)
        assert new_content == content
        assert fixes == []


class TestFixUp031PercentFormat:
    def test_fix_up031_percent_format(self) -> None:
        content = 'x = "value" % (a, b)\n'
        issue = _issue(message="UP031", line_number=1)
        new_content, _fixes = type_errors._fix_up031_percent_format(content, issue)
        assert "# noqa: UP031" in new_content


class TestPruneUnusedTypingImports:
    def test_prune_unused_typing_imports(self) -> None:
        content = """
from typing import Any, Optional, List

def foo():
    pass
"""
        new_content, fixes = type_errors._prune_unused_typing_imports(content)
        assert "Optional" in new_content or len(fixes) > 0


class TestFormatPythonFile:
    def test_format_python_file(self, mocker, tmp_path: Path) -> None:
        mock_run = mocker.patch("crackerjack.fixers.type_errors.subprocess.run")
        mock_run.return_value = mocker.MagicMock(returncode=0, stderr="")

        target = tmp_path / "file.py"
        type_errors._format_python_file(target, tmp_path)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ruff" in args
        assert "format" in args

    def test_format_python_file_pins_cwd_to_project_root(
        self, tmp_path: Path
    ) -> None:
        # Task 22a regression: exercise the real subprocess.run call (no
        # mocking) and capture the `cwd` kwarg to prove it is pinned to
        # `project_root`, matching the original `SubAgent.run_command`'s
        # `cwd=self.context.project_path` behavior for the project-wide
        # entry point (this function previously took no project-path
        # parameter at all).
        import subprocess

        target = tmp_path / "file.py"
        target.write_text("x=1\n")

        captured: dict[str, object] = {}
        real_run = subprocess.run

        def spying_run(*args: object, **kwargs: object):
            captured["cwd"] = kwargs.get("cwd")
            return real_run(*args, **kwargs)  # type: ignore[arg-type]

        import unittest.mock as mock

        with mock.patch(
            "crackerjack.fixers.type_errors.subprocess.run", side_effect=spying_run
        ):
            type_errors._format_python_file(target, tmp_path)

        assert captured["cwd"] == tmp_path


class TestFixLiteralMismatch:
    """Tests for ``_fix_literal_mismatch``.

    The fix widens a ``Literal[...]`` type on a dataclass field to admit
    a new value that is being passed at a call site. This unblocks the
    common case where a developer adds a new sentinel value (e.g.
    ``"invalid_metric"``) and the type definition needs to be updated
    in lockstep.
    """

    def _make_issue(self, message: str) -> Issue:
        return _issue(
            severity=Priority.HIGH,
            message=message,
            file_path="/tmp/example.py",
            line_number=42,
            stage="zuban",
        )

    def test_adds_new_value_to_literal(self) -> None:
        content = """\
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


@dataclass
class TrendAnalysis:
    trend: Literal["improving", "declining", "stable", "insufficient_data"]
    slope: float


def detect_trend() -> TrendAnalysis:
    return TrendAnalysis(
        trend="invalid_metric",
        slope=0.0,
    )
"""
        issue = self._make_issue(
            'Argument "trend" to "TrendAnalysis" has incompatible type '
            "\"Literal['invalid_metric']\"; expected "
            "\"Literal['improving', 'declining', 'stable', 'insufficient_data']\""
        )
        new_content, fixes = type_errors._fix_literal_mismatch(content, issue)
        assert "invalid_metric" in new_content
        assert any("invalid_metric" in fix for fix in fixes)
        for value in ("improving", "declining", "stable", "insufficient_data"):
            assert f'"{value}"' in new_content or f"'{value}'" in new_content

    def test_no_op_when_value_already_present(self) -> None:
        content = """\
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


@dataclass
class TrendAnalysis:
    trend: Literal["improving", "declining", "invalid_metric"]
    slope: float
"""
        issue = self._make_issue(
            'Argument "trend" to "TrendAnalysis" has incompatible type '
            "\"Literal['invalid_metric']\"; expected "
            "\"Literal['improving', 'declining', 'invalid_metric']\""
        )
        new_content, fixes = type_errors._fix_literal_mismatch(content, issue)
        assert new_content == content
        assert fixes == []

    def test_preserves_quote_style(self) -> None:
        content = """\
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal


@dataclass
class Status:
    code: Literal["ok", "error"]
"""
        issue = self._make_issue(
            'Argument "code" to "Status" has incompatible type '
            '\'Literal["pending"]\'; expected \'Literal["ok", "error"]\''
        )
        new_content, _fixes = type_errors._fix_literal_mismatch(content, issue)
        assert '"pending"' in new_content

    def test_no_op_for_unrelated_message(self) -> None:
        content = """\
from __future__ import annotations


def foo() -> int:
    return "not an int"
"""
        issue = self._make_issue(
            'Incompatible return value type (got "str", expected "int")'
        )
        new_content, fixes = type_errors._fix_literal_mismatch(content, issue)
        assert new_content == content
        assert fixes == []

    def test_no_op_when_class_not_in_file(self) -> None:
        content = """\
from __future__ import annotations
from somewhere_else import TrendAnalysis


def make_result() -> TrendAnalysis:
    return TrendAnalysis(
        trend="invalid_metric",
        slope=0.0,
    )
"""
        issue = self._make_issue(
            'Argument "trend" to "TrendAnalysis" has incompatible type '
            "\"Literal['invalid_metric']\"; expected "
            "\"Literal['improving']\""
        )
        new_content, fixes = type_errors._fix_literal_mismatch(content, issue)
        assert new_content == content
        assert fixes == []

    def test_no_op_when_field_not_a_literal(self) -> None:
        content = """\
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TrendAnalysis:
    trend: str
    slope: float
"""
        issue = self._make_issue(
            'Argument "trend" to "TrendAnalysis" has incompatible type '
            '"Literal[\'invalid_metric\']"; expected "str"'
        )
        new_content, fixes = type_errors._fix_literal_mismatch(content, issue)
        assert new_content == content
        assert fixes == []


class TestPhaseGTyHandlers:
    """Tests for Phase G ty-error-code-specific handlers."""

    def _issue(
        self, message: str, line_number: int, file_path: str = "crackerjack/foo.py"
    ) -> Issue:
        return _issue(
            message=message,
            file_path=file_path,
            line_number=line_number,
            stage="ty",
        )

    def test_paired_ty_ignore_appends_when_mypy_ignore_exists(self) -> None:
        content = "x = None  # type: ignore[assignment]\n"
        issue = self._issue(
            "crackerjack/foo.py:1:5: error[invalid-assignment] "
            "Object of type None is not assignable",
            1,
        )
        new_content, fixes = type_errors._fix_invalid_assignment_paired_ty_ignore(
            content, issue
        )
        assert "# ty: ignore[invalid-assignment]" in new_content
        assert "# type: ignore[assignment]" in new_content
        assert len(fixes) == 1

    def test_paired_ty_ignore_no_op_when_already_present(self) -> None:
        content = (
            "x = None  # type: ignore[assignment]  # ty: ignore[invalid-assignment]\n"
        )
        issue = self._issue(
            "crackerjack/foo.py:1:5: error[invalid-assignment] "
            "Object of type None is not assignable",
            1,
        )
        new_content, fixes = type_errors._fix_invalid_assignment_paired_ty_ignore(
            content, issue
        )
        assert new_content == content
        assert fixes == []

    def test_paired_ty_ignore_no_op_without_mypy_ignore(self) -> None:
        content = "x = None\n"
        issue = self._issue(
            "crackerjack/foo.py:1:5: error[invalid-assignment] "
            "Object of type None is not assignable",
            1,
        )
        new_content, fixes = type_errors._fix_invalid_assignment_paired_ty_ignore(
            content, issue
        )
        assert new_content == content
        assert fixes == []

    def test_paired_ty_ignore_skips_wrong_message(self) -> None:
        content = "x = None  # type: ignore[assignment]\n"
        issue = self._issue("Some other error", 1)
        new_content, fixes = type_errors._fix_invalid_assignment_paired_ty_ignore(
            content, issue
        )
        assert new_content == content
        assert fixes == []

    def test_typed_dict_subscript_wraps_in_cast(self) -> None:
        content = "predictor_name: str = config.get('predictor', 'moving_average')\n"
        issue = self._issue(
            "crackerjack/foo.py:1:31: error[invalid-assignment] "
            "Object of type int | float | str is not assignable to str",
            1,
        )
        new_content, fixes = type_errors._fix_invalid_typed_dict_subscript(
            content, issue
        )
        assert "cast(str, config.get" in new_content
        assert len(fixes) == 1

    def test_typed_dict_subscript_skips_when_already_has_cast(self) -> None:
        content = "predictor_name: str = cast(str, config.get('predictor'))\n"
        issue = self._issue(
            "crackerjack/foo.py:1:31: error[invalid-assignment] "
            "Object of type int | float | str is not assignable to str",
            1,
        )
        new_content, fixes = type_errors._fix_invalid_typed_dict_subscript(
            content, issue
        )
        assert new_content == content
        assert fixes == []

    def test_unresolved_import_adds_ty_ignore(self) -> None:
        content = "from crackerjack.foo import Bar\n"
        issue = self._issue(
            "crackerjack/foo.py:1:6: error[unresolved-import] "
            "No module named 'crackerjack.foo'",
            1,
            file_path="crackerjack/baz.py",
        )
        new_content, fixes = type_errors._fix_unresolved_import_with_ty_ignore(
            content, issue
        )
        assert "# ty: ignore[unresolved-import]" in new_content
        assert len(fixes) == 1

    def test_unresolved_import_no_op_when_ty_ignore_present(self) -> None:
        content = "from crackerjack.foo import Bar  # ty: ignore[unresolved-import]\n"
        issue = self._issue(
            "crackerjack/foo.py:1:6: error[unresolved-import] "
            "No module named 'crackerjack.foo'",
            1,
            file_path="crackerjack/baz.py",
        )
        new_content, fixes = type_errors._fix_unresolved_import_with_ty_ignore(
            content, issue
        )
        assert new_content == content
        assert fixes == []

    def test_unresolved_import_skips_workspace_tools(self) -> None:
        """workspace_tools.py has its own documented suppression; don't double-up."""
        content = "from crackerjack.mahavishnu.workspace import Manager\n"
        issue = self._issue(
            "crackerjack/mcp/tools/workspace_tools.py:10:6: error[unresolved-import] "
            "No module named 'crackerjack.mahavishnu.workspace'",
            1,
            file_path="crackerjack/mcp/tools/workspace_tools.py",
        )
        new_content, fixes = type_errors._fix_unresolved_import_with_ty_ignore(
            content, issue
        )
        assert new_content == content
        assert fixes == []


class TestFixTypeErrorIssue:
    """Real-file-I/O tests for the ``fix_type_error_issue`` entry point."""

    @pytest.mark.asyncio
    async def test_no_file_path(self, tmp_path: Path) -> None:
        issue = _issue(message="Missing return type", file_path=None)
        result = await type_errors.fix_type_error_issue(issue, tmp_path)
        assert result.success is False
        assert "No file path provided" in result.remaining_issues

    @pytest.mark.asyncio
    async def test_file_not_found(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.py"
        issue = _issue(message="Missing return type", file_path=str(missing))
        result = await type_errors.fix_type_error_issue(issue, tmp_path)
        assert result.success is False
        assert any("File not found" in msg for msg in result.remaining_issues)

    @pytest.mark.asyncio
    async def test_no_changes_applied(self, tmp_path: Path) -> None:
        target = tmp_path / "already_fine.py"
        target.write_text("from __future__ import annotations\n\nx = 1\n")
        issue = _issue(message="unrelated", file_path=str(target))
        result = await type_errors.fix_type_error_issue(issue, tmp_path)
        assert result.success is False
        assert "No changes applied" in result.remaining_issues
        # File must be untouched.
        assert target.read_text() == "from __future__ import annotations\n\nx = 1\n"

    @pytest.mark.asyncio
    async def test_applies_fix_and_writes_real_file(
        self, tmp_path: Path, mocker
    ) -> None:
        """End-to-end: a UP031 fix is applied and persisted to disk.

        Content already has ``from __future__ import annotations`` so that
        ``_add_future_annotations`` (unconditionally run early in the
        pipeline via ``_apply_common_fixes``) is a no-op and doesn't shift
        line numbers -- see ``test_up031_fix_missed_when_future_annotations_shifts_lines``
        below for what happens when it isn't a no-op.
        """
        # Avoid depending on a real `ruff` binary being on PATH in CI.
        mocker.patch(
            "crackerjack.fixers.type_errors.subprocess.run",
            return_value=mocker.MagicMock(returncode=0, stderr=""),
        )
        target = tmp_path / "mod.py"
        target.write_text(
            'from __future__ import annotations\n\nx = "value" % (a, b)\n'
        )
        issue = _issue(message="UP031", file_path=str(target), line_number=3)

        result = await type_errors.fix_type_error_issue(issue, tmp_path)

        assert result.success is True
        assert result.fixes_applied
        on_disk = target.read_text()
        assert "# noqa: UP031" in on_disk

    @pytest.mark.asyncio
    async def test_up031_fix_missed_when_future_annotations_shifts_lines(
        self, tmp_path: Path, mocker
    ) -> None:
        """Pins a genuine pre-existing pipeline-ordering bug.

        ``apply_type_fixes`` runs ``_apply_common_fixes`` (which
        unconditionally inserts ``from __future__ import annotations`` as
        a new line 1 if missing, regardless of the issue's actual type)
        *before* any of the line-number-based fixers
        (``_fix_up031_percent_format``, ``_fix_var_annotated``, the
        ``ty``-error-code handlers). ``issue.line_number`` is never
        adjusted for the shift, so for a file that doesn't already have
        ``from __future__ import annotations``, a UP031 fix targeting line
        1 silently misses -- it now points at the newly-inserted future
        import line instead of the original code line. The pipeline still
        reports ``success=True`` because *a* change was made (the future
        import), just not the intended one. Preserved verbatim -- see the
        module docstring's "Preserved quirks" section, item 7. This is the
        exact original ``_apply_type_fixes`` step order (unchanged by this
        port), not something introduced by flattening the class into
        functions.
        """
        mocker.patch(
            "crackerjack.fixers.type_errors.subprocess.run",
            return_value=mocker.MagicMock(returncode=0, stderr=""),
        )
        target = tmp_path / "mod.py"
        target.write_text('x = "value" % (a, b)\n')
        issue = _issue(message="UP031", file_path=str(target), line_number=1)

        result = await type_errors.fix_type_error_issue(issue, tmp_path)

        assert result.success is True
        assert result.fixes_applied == ["Added 'from __future__ import annotations'"]
        on_disk = target.read_text()
        assert "# noqa: UP031" not in on_disk
        assert on_disk == 'from __future__ import annotations\nx = "value" % (a, b)\n'

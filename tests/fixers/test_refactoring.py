"""Tests for crackerjack.fixers.refactoring.

Ported from tests/unit/agents/test_refactoring_agent.py and
test_refactoring_agent_branches.py, keeping only the cases that exercise
real AST/regex transform behavior. Cases exercising SubAgent/coordinator
dispatch (can_handle, analyze_and_fix, _handle_warning routing, and the
session-buddy semantic-enhancement helpers) were dropped, since that
machinery no longer exists.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.fixers import refactoring
from crackerjack.models.fix_plan import ChangeSpec, FixPlan, create_fix_plan
from crackerjack.models.issues import FixResult, Issue, IssueType, Priority

MODULE = "crackerjack.fixers.refactoring"


class TestReduceComplexity:
    async def test_no_file_path(self) -> None:
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Too complex",
            file_path=None,
        )

        result = await refactoring.reduce_complexity(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_file_not_exists(self, tmp_path: Path) -> None:
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Too complex",
            file_path=str(tmp_path / "nonexistent.py"),
        )

        result = await refactoring.reduce_complexity(issue)

        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    async def test_syntax_error(self, tmp_path: Path) -> None:
        test_file = tmp_path / "invalid.py"
        test_file.write_text("def broken(\n")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex function",
            file_path=str(test_file),
        )

        result = await refactoring.reduce_complexity(issue)

        assert result.success is False
        assert "Syntax error" in result.remaining_issues[0]


class TestRemoveDeadCode:
    async def test_no_file_path(self) -> None:
        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused code",
            file_path=None,
        )

        result = await refactoring.remove_dead_code(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_file_not_exists(self, tmp_path: Path) -> None:
        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused import",
            file_path=str(tmp_path / "nonexistent.py"),
        )

        result = await refactoring.remove_dead_code(issue)

        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    async def test_syntax_error(self, tmp_path: Path) -> None:
        test_file = tmp_path / "invalid.py"
        test_file.write_text("def broken(\n")

        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused code",
            file_path=str(test_file),
        )

        result = await refactoring.remove_dead_code(issue)

        assert result.success is False
        assert "Syntax error" in result.remaining_issues[0]

    async def test_general_exception_returns_error_result(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("import x\n")

        issue = Issue(
            id="dc-err-1",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="unused import",
            file_path=str(test_file),
        )

        with patch(f"{MODULE}._process_dead_code_removal") as mock_proc:
            mock_proc.side_effect = RuntimeError("boom")
            result = await refactoring.remove_dead_code(issue)

        assert result.success is False
        assert "Error processing" in result.remaining_issues[0]


class TestEstimateFunctionComplexity:
    def test_simple(self) -> None:
        function_body = """
    return x + y
"""
        complexity = refactoring._estimate_function_complexity(function_body)
        assert complexity >= 1

    def test_with_conditionals(self) -> None:
        function_body = """
    if x > 10:
        return True
    elif x < 5:
        return False
    else:
        return None
"""
        complexity = refactoring._estimate_function_complexity(function_body)
        assert complexity >= 3

    def test_with_loops(self) -> None:
        function_body = """
    for item in items:
        if item.valid:
            results.append(item)
"""
        complexity = refactoring._estimate_function_complexity(function_body)
        assert complexity >= 3

    def test_nested(self) -> None:
        function_body = """
    for item in items:
        for sub_item in item:
            if sub_item.valid:
                result.append(sub_item)
"""
        complexity = refactoring._estimate_function_complexity(function_body)
        assert complexity >= 4

    def test_empty(self) -> None:
        assert refactoring._estimate_function_complexity("") == 0


class TestShouldRemoveImportLine:
    def test_simple_import(self) -> None:
        unused_import = {"type": "import", "name": "os"}
        line = "import os"
        assert refactoring._should_remove_import_line(line, unused_import) is True

    def test_from_import(self) -> None:
        unused_import = {"type": "from_import", "name": "Path"}
        line = "from pathlib import Path"
        assert refactoring._should_remove_import_line(line, unused_import) is True

    def test_no_match(self) -> None:
        unused_import = {"type": "import", "name": "os"}
        line = "import sys"
        assert refactoring._should_remove_import_line(line, unused_import) is False

    def test_wrong_type(self) -> None:
        unused_import = {"type": "unknown", "name": "os"}
        line = "import os"
        assert refactoring._should_remove_import_line(line, unused_import) is False


class TestPatternDetection:
    def test_extract_nested_conditions_is_a_noop(self) -> None:
        content = """
def check():
    if x > 10 and y < 20 and z == 5 and a != 3 and b >= 7 and c <= 15 and d in items and e not in others:
        return True
"""
        result = refactoring._extract_nested_conditions(content)
        assert result == content

    def test_simplify_boolean_expressions_complex(self) -> None:
        content = """
def validate():
    if (x > 10 and y < 20) or (z == 5 and a != 3) or (b >= 7 and c <= 15) or (d in items and e not in others):
        return True
"""
        result = refactoring._simplify_boolean_expressions(content)
        assert "_validate_complex_condition" in result or result == content

    def test_is_empty_except_block(self) -> None:
        lines = ["try:", "    do_something()", "except:", "    pass"]
        assert refactoring._is_empty_except_block(lines, 2) is True

    def test_is_empty_except_block_with_named_exception(self) -> None:
        lines = [
            "try:",
            "    do_something()",
            "except Exception as e:",
            "    handle(e)",
        ]
        # Matches the `except ` prefix regardless of the handler body.
        assert refactoring._is_empty_except_block(lines, 2) is True


class TestValidation:
    def test_validate_complexity_issue_no_path(self) -> None:
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Too complex",
            file_path=None,
        )
        result = refactoring._validate_complexity_issue(issue)
        assert result is not None
        assert result.success is False

    def test_validate_complexity_issue_file_not_exists(self, tmp_path: Path) -> None:
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Too complex",
            file_path=str(tmp_path / "missing.py"),
        )
        result = refactoring._validate_complexity_issue(issue)
        assert result is not None
        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    def test_validate_complexity_issue_valid(self, tmp_path: Path) -> None:
        test_file = tmp_path / "valid.py"
        test_file.write_text("def foo(): pass")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Too complex",
            file_path=str(test_file),
        )
        assert refactoring._validate_complexity_issue(issue) is None

    def test_validate_dead_code_issue_no_path(self) -> None:
        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused code",
            file_path=None,
        )
        result = refactoring._validate_dead_code_issue(issue)
        assert result is not None
        assert result.success is False

    def test_validate_dead_code_issue_valid(self, tmp_path: Path) -> None:
        test_file = tmp_path / "valid.py"
        test_file.write_text("import unused_module")

        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused import",
            file_path=str(test_file),
        )
        assert refactoring._validate_dead_code_issue(issue) is None


class TestThreeTierFallback:
    def test_extract_function_name_from_simple_message(self) -> None:
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'my_function' has complexity 20",
        )
        assert refactoring._extract_function_name_from_issue(issue) == "my_function"

    def test_extract_function_name_from_class_method_format(self) -> None:
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'MyClass::complex_method' has complexity 25",
        )
        assert refactoring._extract_function_name_from_issue(issue) == "complex_method"

    def test_extract_function_name_from_details(self) -> None:
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complexity issue",
            details=["complexity: 20", "function: MyClass::process_data"],
        )
        assert refactoring._extract_function_name_from_issue(issue) == "process_data"

    def test_extract_function_name_no_match(self) -> None:
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Some complexity issue without function name",
        )
        assert refactoring._extract_function_name_from_issue(issue) is None

    def test_simple_dash_format(self) -> None:
        issue = Issue(
            id="e-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="my_func - has complexity 20",
        )
        assert refactoring._extract_function_name_from_issue(issue) == "my_func"

    def test_details_function_no_class_prefix(self) -> None:
        issue = Issue(
            id="e-2",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="no name here",
            details=["function: simple_func"],
        )
        assert refactoring._extract_function_name_from_issue(issue) == "simple_func"

    async def test_tier1_with_line_number(self, tmp_path: Path) -> None:
        test_file = tmp_path / "tier1.py"
        test_file.write_text(
            "\ndef complex_function():\n"
            "    if x > 10:\n"
            "        if y < 5:\n"
            "            return True\n"
            "    return False\n"
        )

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'complex_function' has complexity 20",
            file_path=str(test_file),
            line_number=3,
        )

        with patch(
            f"{MODULE}._process_complexity_reduction_with_line_number"
        ) as mock_tier1:
            mock_tier1.return_value = FixResult(
                success=True, confidence=0.9, fixes_applied=["Reduced complexity"]
            )

            result = await refactoring.reduce_complexity(issue)

            mock_tier1.assert_called_once()
            assert result.success is True

    async def test_tier2_by_function_name(self, tmp_path: Path) -> None:
        test_file = tmp_path / "tier2.py"
        test_file.write_text(
            "\ndef target_function():\n"
            "    if x > 10:\n"
            "        if y < 5:\n"
            "            return True\n"
            "    return False\n"
        )

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'target_function' has complexity 18",
            file_path=str(test_file),
            line_number=None,
        )

        with patch(
            f"{MODULE}._process_complexity_reduction_by_function_name"
        ) as mock_tier2:
            mock_tier2.return_value = FixResult(
                success=True, confidence=0.85, fixes_applied=["Reduced complexity"]
            )

            result = await refactoring.reduce_complexity(issue)

            mock_tier2.assert_called_once_with(
                Path(test_file), "target_function", issue=issue
            )
            assert result.success is True

    async def test_tier3_full_analysis(self, tmp_path: Path) -> None:
        test_file = tmp_path / "tier3.py"
        test_file.write_text(
            "\ndef complex_function():\n"
            "    if x > 10:\n"
            "        if y < 5:\n"
            "            return True\n"
            "    return False\n"
        )

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex function",
            file_path=str(test_file),
            line_number=None,
        )

        with patch(f"{MODULE}._process_complexity_reduction") as mock_tier3:
            mock_tier3.return_value = FixResult(
                success=True,
                confidence=0.8,
                fixes_applied=["Found and reduced complexity"],
            )

            result = await refactoring.reduce_complexity(issue)

            mock_tier3.assert_called_once()
            assert result.success is True

    async def test_three_tier_fallback_chain(self, tmp_path: Path) -> None:
        test_file = tmp_path / "fallback.py"
        test_file.write_text("def func(): pass")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'func' has complexity 20",
            file_path=str(test_file),
            line_number=None,
        )

        with (
            patch(
                f"{MODULE}._process_complexity_reduction_with_line_number"
            ) as mock_tier1,
            patch(
                f"{MODULE}._process_complexity_reduction_by_function_name"
            ) as mock_tier2,
            patch(f"{MODULE}._process_complexity_reduction") as mock_tier3,
        ):
            mock_tier2.return_value = FixResult(
                success=True, confidence=0.85, fixes_applied=["Fixed by name"]
            )

            result = await refactoring.reduce_complexity(issue)

            mock_tier1.assert_not_called()
            mock_tier2.assert_called_once()
            mock_tier3.assert_not_called()
            assert result.success is True

    async def test_three_tier_all_fail_returns_error(self, tmp_path: Path) -> None:
        test_file = tmp_path / "all_fail.py"
        test_file.write_text("def func(): pass")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'func' has complexity 20",
            file_path=str(test_file),
            line_number=None,
        )

        with (
            patch(f"{MODULE}._process_complexity_reduction_with_line_number"),
            patch(
                f"{MODULE}._process_complexity_reduction_by_function_name"
            ) as mock_tier2,
            patch(f"{MODULE}._process_complexity_reduction") as mock_tier3,
        ):
            mock_tier2.side_effect = Exception("Function not found")
            mock_tier3.return_value = FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=["No complex functions found"],
            )

            result = await refactoring.reduce_complexity(issue)

            mock_tier3.assert_called_once()
            assert result.success is False

    async def test_full_analysis_uses_ast_fallback(self, tmp_path: Path) -> None:
        test_file = tmp_path / "fallback_ast.py"
        test_file.write_text(
            """def load_settings():
    if config_file.exists():
        config = read_config()
        if config.get("enabled"):
            return config
    for path in search_paths:
        if path.exists():
            return path
    return None
"""
        )

        tree = ast.parse(test_file.read_text())
        func_node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "load_settings"
        )
        func_info = {
            "name": func_node.name,
            "line_start": func_node.lineno,
            "line_end": func_node.end_lineno or func_node.lineno,
            "node": func_node,
        }

        issue = Issue(
            id="comp-ast-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'load_settings' has complexity 20",
            file_path=str(test_file),
            line_number=None,
        )

        with patch(f"{MODULE}.find_complex_functions", return_value=[func_info]):
            result = await refactoring.reduce_complexity(issue)

        assert result.success is True
        written_content = test_file.read_text()
        assert "def _process_if_" in written_content
        ast.parse(written_content)

    async def test_apply_and_save_refactoring_uses_ast_fallback(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "ast_fallback.py"
        original_content = """
def target_function():
    if first:
        if second:
            if third:
                if fourth:
                    if fifth:
                        if sixth:
                            if seventh:
                                if eighth:
                                    if ninth:
                                        if tenth:
                                            if eleventh:
                                                if twelfth:
                                                    return True
    return False
"""
        test_file.write_text(original_content)

        transformed_content = """
def target_function():
    return _target_function_helper()


def _target_function_helper():
    if first:
        return True
    return False
"""

        tree = ast.parse(original_content)
        func_node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "target_function"
        )
        func_info = {
            "name": func_node.name,
            "line_start": func_node.lineno,
            "line_end": func_node.end_lineno or func_node.lineno,
            "complexity": 20,
            "node": func_node,
        }

        engine = Mock()
        engine.transform = AsyncMock(
            return_value=SimpleNamespace(transformed_content=transformed_content)
        )

        issue = Issue(
            id="comp-ast-002",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'target_function' has complexity 20",
            file_path=str(test_file),
            line_number=2,
        )

        with (
            patch(
                f"{MODULE}.refactor_complex_functions", return_value=original_content
            ),
            patch(f"{MODULE}.apply_enhanced_strategies", return_value=original_content),
            patch(f"{MODULE}._get_ast_transform_engine", return_value=engine),
        ):
            result = await refactoring._apply_and_save_refactoring(
                test_file,
                original_content,
                [func_info],
                issue=issue,
            )

        assert result.success is True
        written_content = test_file.read_text()
        assert written_content == transformed_content
        ast.parse(written_content)

    async def test_apply_and_save_refactoring_rejects_if_complexity_still_high(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "ast_fallback_fail.py"
        original_content = """
def target_function():
    if first:
        if second:
            if third:
                if fourth:
                    if fifth:
                        if sixth:
                            if seventh:
                                if eighth:
                                    if ninth:
                                        if tenth:
                                            if eleventh:
                                                if twelfth:
                                                    return True
    return False
"""
        test_file.write_text(original_content)

        too_complex_content = original_content

        tree = ast.parse(original_content)
        func_node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "target_function"
        )
        func_info = {
            "name": func_node.name,
            "line_start": func_node.lineno,
            "line_end": func_node.end_lineno or func_node.lineno,
            "complexity": 20,
            "node": func_node,
        }

        engine = Mock()
        engine.transform = AsyncMock(
            return_value=SimpleNamespace(transformed_content=too_complex_content)
        )

        with (
            patch(
                f"{MODULE}.refactor_complex_functions", return_value=original_content
            ),
            patch(f"{MODULE}.apply_enhanced_strategies", return_value=original_content),
            patch(f"{MODULE}._get_ast_transform_engine", return_value=engine),
        ):
            result = await refactoring._apply_and_save_refactoring(
                test_file,
                original_content,
                [func_info],
                issue=Issue(
                    id="comp-ast-003",
                    type=IssueType.COMPLEXITY,
                    severity=Priority.HIGH,
                    message="Function 'target_function' has complexity 20",
                    file_path=str(test_file),
                    line_number=2,
                ),
            )

        assert result.success is True
        written_content = test_file.read_text()
        assert "# noqa: C901" in written_content

    def test_complexity_noqa_fallback_appends_c901(self, tmp_path: Path) -> None:
        test_file = tmp_path / "noqa_fallback.py"
        test_file.write_text(
            "def target_function():\n"
            "    if first:\n"
            "        if second:\n"
            "            return True\n"
            "    return False\n",
            encoding="utf-8",
        )

        issue = Issue(
            id="comp-noqa-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'target_function' has complexity 20",
            file_path=str(test_file),
            line_number=1,
        )

        result = refactoring._apply_complexity_noqa_fallback(test_file, issue)

        assert result is not None
        assert result.success is True
        updated = test_file.read_text(encoding="utf-8")
        assert "def target_function(): # noqa: C901" in updated


class TestIsFixableTypeErrorClassifier:
    """Cover every confidence branch in `is_fixable_type_error`."""

    async def test_empty_message_returns_zero(self) -> None:
        issue = Issue(
            id="t-1", type=IssueType.TYPE_ERROR, severity=Priority.MEDIUM, message=""
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.0

    async def test_incompatible_types_returns_zero(self) -> None:
        issue = Issue(
            id="t-2",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="incompatible types in assignment",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.0

    async def test_type_mismatch_returns_zero(self) -> None:
        issue = Issue(
            id="t-3",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Type mismatch on attribute access",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.0

    async def test_cannot_assign_returns_zero(self) -> None:
        issue = Issue(
            id="t-4",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Cannot assign value of type 'str' to 'int'",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.0

    async def test_cannot_be_assigned_returns_zero(self) -> None:
        issue = Issue(
            id="t-5",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Value cannot be assigned to attribute",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.0

    async def test_needs_return_type_high_confidence(self) -> None:
        issue = Issue(
            id="t-6",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Function foo needs return type annotation",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.9

    async def test_return_arrow_none_branch(self) -> None:
        # Source bug preserved: the literal "-> None" / "-> Any" checks
        # compare against a lowercased message, so they never match. This
        # documents the observed fall-through, not the apparent intent.
        issue = Issue(
            id="t-7",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="signature is -> None",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.3

    async def test_return_arrow_any_branch(self) -> None:
        issue = Issue(
            id="t-8",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="return type is -> Any",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.0

    async def test_needs_annotation_branch(self) -> None:
        issue = Issue(
            id="t-9",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Variable needs annotation",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.8

    async def test_has_no_type_branch(self) -> None:
        issue = Issue(
            id="t-10",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Parameter has no type annotation",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.8

    async def test_parameter_with_type_annotation(self) -> None:
        issue = Issue(
            id="t-11",
            type=IssueType.TYPE_ERROR,
            severity=Priority.LOW,
            message="Parameter 'x' missing type annotation",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.7

    async def test_incompatible_return_type(self) -> None:
        issue = Issue(
            id="t-12",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="incompatible return type for function",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.6

    async def test_incompatible_type_branch(self) -> None:
        issue = Issue(
            id="t-13",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="incompatible type passed to call",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.6

    async def test_argument_of_type_branch(self) -> None:
        issue = Issue(
            id="t-14",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Argument of type 'str' not acceptable",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.6

    async def test_has_no_attribute_branch(self) -> None:
        issue = Issue(
            id="t-15",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Item has no attribute 'open'",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.6

    async def test_cannot_be_assigned_to_branch(self) -> None:
        issue = Issue(
            id="t-16",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Expression cannot be assigned to target",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.0

    async def test_assignment_branch(self) -> None:
        issue = Issue(
            id="t-17",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="invalid assignment expression",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.4

    async def test_invalid_type_branch(self) -> None:
        issue = Issue(
            id="t-18",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Invalid type used in expression",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.4

    async def test_undefined_name_branch(self) -> None:
        issue = Issue(
            id="t-19",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Undefined name 'foo'",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.4

    async def test_generic_type_error_branch(self) -> None:
        issue = Issue(
            id="t-20",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Generic type error in expression",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.3

    async def test_annotation_branch(self) -> None:
        issue = Issue(
            id="t-21",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Annotation is required for variable",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.3

    async def test_protocol_branch(self) -> None:
        issue = Issue(
            id="t-22",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Protocol mismatch detected",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.3

    async def test_signature_branch(self) -> None:
        issue = Issue(
            id="t-23",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Method signature incompatible",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.3

    async def test_unmatched_message_returns_zero(self) -> None:
        issue = Issue(
            id="t-24",
            type=IssueType.TYPE_ERROR,
            severity=Priority.LOW,
            message="nothing relevant in here",
        )
        assert await refactoring.is_fixable_type_error(issue) == 0.0


class TestFixTypeError:
    async def test_adds_return_type(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test_type_fix.py"
        test_file.write_text(
            "\ndef foo():\n    pass\n\ndef bar():  # No type annotation\n    return 42\n"
        )

        issue = Issue(
            id="type-006",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type",
            file_path=str(test_file),
            line_number=2,
        )

        result = await refactoring.fix_type_error(issue)

        assert result.success is True
        assert result.confidence > 0.8
        assert len(result.files_modified) == 1

        content = test_file.read_text()
        assert "def foo() -> None:" in content
        assert "def bar() -> None:" in content

    async def test_no_file_path(self) -> None:
        issue = Issue(
            id="type-008",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type",
            file_path=None,
            line_number=0,
        )

        result = await refactoring.fix_type_error(issue)

        assert result.success is False
        assert "No file path provided" in result.remaining_issues

    async def test_incompatible_message_skips_path(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def foo(): pass\n")

        issue = Issue(
            id="ft-1",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="incompatible types",
            file_path=str(test_file),
        )

        result = await refactoring.fix_type_error(issue)

        assert result.success is False
        assert "too complex" in result.remaining_issues[0].lower()

    async def test_empty_content_returns_error(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("")

        issue = Issue(
            id="ft-3",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type",
            file_path=str(test_file),
        )

        result = await refactoring.fix_type_error(issue)

        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    async def test_wraps_path_assignment_safely(self, tmp_path: Path) -> None:
        test_file = tmp_path / "path_assignment.py"
        test_file.write_text("repository_path=Path(repo_path_str)\n")

        issue = Issue(
            id="type-009",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Argument 1 to "open" has incompatible type "Path"; expected "str"',
            file_path=str(test_file),
            line_number=1,
        )

        result = await refactoring.fix_type_error(issue)

        assert result.success is True
        content = test_file.read_text()
        assert content == "repository_path=str(Path(repo_path_str))\n"
        assert "str(repository_path)" not in content

    async def test_flattens_suppress_tuple(self, tmp_path: Path) -> None:
        test_file = tmp_path / "suppress_tuple.py"
        test_file.write_text("with suppress((OSError, FileNotFoundError)):\n    pass\n")

        issue = Issue(
            id="type-010",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Argument 1 to "suppress" has incompatible type',
            file_path=str(test_file),
            line_number=1,
        )

        result = await refactoring.fix_type_error(issue)

        assert result.success is True
        content = test_file.read_text()
        assert "from contextlib import suppress" in content
        assert "with suppress(OSError, FileNotFoundError):" in content
        assert "suppress((" not in content

    async def test_wraps_open_target_with_path(self, tmp_path: Path) -> None:
        test_file = tmp_path / "open_target.py"
        test_file.write_text(
            'with output_path.open("w", encoding="utf-8") as f:\n    pass\n'
        )

        issue = Issue(
            id="type-011",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Item "str" of "str | Path" has no attribute "open"',
            file_path=str(test_file),
            line_number=1,
        )

        result = await refactoring.fix_type_error(issue)

        assert result.success is True
        content = test_file.read_text()
        assert 'Path(output_path).open("w", encoding="utf-8")' in content
        assert "output_path.open(" not in content


class TestApplyKnownComplexityFix:
    async def test_empty_content_returns_failure(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("")

        issue = Issue(
            id="k-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="detect_agent_needs too complex",
            file_path=str(test_file),
        )

        result = await refactoring._apply_known_complexity_fix(test_file, issue)
        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    async def test_pattern_does_not_change_content(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def detect_agent_needs(): pass\n")

        issue = Issue(
            id="k-2",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="detect_agent_needs too complex",
            file_path=str(test_file),
        )

        with patch(
            f"{MODULE}.refactor_detect_agent_needs_pattern",
            return_value="def detect_agent_needs(): pass\n",
        ):
            result = await refactoring._apply_known_complexity_fix(test_file, issue)

        assert result.success is False
        assert result.confidence == 0.3

    async def test_write_failure_after_transform(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def detect_agent_needs(): pass\n")

        issue = Issue(
            id="k-3",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="detect_agent_needs too complex",
            file_path=str(test_file),
        )

        with (
            patch(
                f"{MODULE}.refactor_detect_agent_needs_pattern",
                return_value="def detect_agent_needs(): return 1\n",
            ),
            patch(f"{MODULE}._write_file", return_value=False),
        ):
            result = await refactoring._apply_known_complexity_fix(test_file, issue)

        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]


class TestReduceComplexityDetectAgentNeedsBranch:
    async def test_detect_agent_needs_short_circuit(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def detect_agent_needs(): pass\n")

        issue = Issue(
            id="d-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="detect_agent_needs pattern is too complex",
            file_path=str(test_file),
        )

        with patch(
            f"{MODULE}.refactor_detect_agent_needs_pattern",
            return_value="def detect_agent_needs(): return None\n",
        ):
            result = await refactoring.reduce_complexity(issue)

        assert result.success is True
        assert "detect_agent_needs" in result.fixes_applied[0]


class TestFixPathStrPatterns:
    def test_no_matching_patterns_returns_none(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")
        result = refactoring._fix_path_str_patterns("x = 1\n", test_file)
        assert result is None

    def test_function_call_pattern_rewrites(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("open(Path(name))\n")

        result = refactoring._fix_path_str_patterns("open(Path(name))\n", test_file)
        assert result is not None
        assert result.success is True
        assert "str(Path(name))" in test_file.read_text()

    def test_write_failure_returns_none(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = Path(y)\n")

        with patch(f"{MODULE}._write_file", return_value=False):
            result = refactoring._fix_path_str_patterns("x = Path(y)\n", test_file)
        assert result is None


class TestTryFixPathStrTypeError:
    def test_no_indicator_returns_none(self, tmp_path: Path) -> None:
        issue = Issue(
            id="tp-1",
            type=IssueType.TYPE_ERROR,
            severity=Priority.LOW,
            message="random message",
        )
        result = refactoring._try_fix_path_str_type_error(
            issue, "x = 1\n", tmp_path / "x.py"
        )
        assert result is None

    def test_path_str_required_but_missing_returns_none(self, tmp_path: Path) -> None:
        issue = Issue(
            id="tp-2",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="arg-type mismatch",
        )
        result = refactoring._try_fix_path_str_type_error(
            issue, "x = 1\n", tmp_path / "x.py"
        )
        assert result is None


class TestEnsureContextlibSuppressImport:
    def test_already_imported_noop(self) -> None:
        content = "from contextlib import suppress\n"
        assert refactoring._ensure_contextlib_suppress_import(content) == content

    def test_import_contextlib_noop(self) -> None:
        content = "import contextlib\n"
        assert refactoring._ensure_contextlib_suppress_import(content) == content

    def test_injects_after_future(self) -> None:
        content = "from __future__ import annotations\nimport os\n\nx = 1\n"
        result = refactoring._ensure_contextlib_suppress_import(content)
        assert "from contextlib import suppress" in result
        lines = result.splitlines()
        assert lines[0] == "from __future__ import annotations"
        assert "from contextlib import suppress" in lines

    def test_injects_after_existing_imports(self) -> None:
        content = "import os\nimport sys\n\nx = 1\n"
        result = refactoring._ensure_contextlib_suppress_import(content)
        lines = result.splitlines()
        assert "from contextlib import suppress" in lines
        assert lines.index("from contextlib import suppress") > lines.index(
            "import sys"
        )

    def test_docstring_skipped_for_insertion(self) -> None:
        content = '"""Module docstring."""\nimport os\n\nx = 1\n'
        result = refactoring._ensure_contextlib_suppress_import(content)
        lines = result.splitlines()
        assert "from contextlib import suppress" in lines
        assert lines.index("from contextlib import suppress") > lines.index("import os")

    def test_no_imports_inserts_at_top(self) -> None:
        content = "x = 1\n"
        result = refactoring._ensure_contextlib_suppress_import(content)
        assert result.splitlines()[0] == "from contextlib import suppress"

    def test_skips_comment_lines(self) -> None:
        content = "# top comment\nimport os\n\nx = 1\n"
        result = refactoring._ensure_contextlib_suppress_import(content)
        lines = result.splitlines()
        assert "from contextlib import suppress" in lines


class TestFlattenSuppressTuple:
    def test_no_tuple_returns_none(self, tmp_path: Path) -> None:
        result = refactoring._flatten_suppress_tuple(
            "with suppress(OSError):\n    pass\n", tmp_path / "x.py"
        )
        assert result is None

    def test_write_failure_returns_none(self, tmp_path: Path) -> None:
        with patch(f"{MODULE}._write_file", return_value=False):
            result = refactoring._flatten_suppress_tuple(
                "with suppress((OSError,)):\n    pass\n", tmp_path / "x.py"
            )
        assert result is None


class TestApplyAndSaveRefactoringBranches:
    async def test_no_changes_no_fallback_returns_no_changes(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): return 1\n")

        engine = Mock()
        engine.transform = AsyncMock(return_value=None)

        func_info = {
            "name": "f",
            "line_start": 1,
            "line_end": 1,
            "complexity": 20,
            "node": None,
        }

        with (
            patch(
                f"{MODULE}.refactor_complex_functions",
                return_value="def f(): return 1\n",
            ),
            patch(
                f"{MODULE}.apply_enhanced_strategies",
                return_value="def f(): return 1\n",
            ),
            patch(f"{MODULE}._get_ast_transform_engine", return_value=engine),
        ):
            result = await refactoring._apply_and_save_refactoring(
                test_file, "def f(): return 1\n", [func_info], issue=None
            )

        assert result.success is False
        assert "Could not automatically" in result.remaining_issues[0]

    async def test_write_failure_for_refactored(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): return 1\n")

        func_info = {
            "name": "f",
            "line_start": 1,
            "line_end": 1,
            "complexity": 20,
            "node": None,
        }

        with (
            patch(
                f"{MODULE}.refactor_complex_functions",
                return_value="def f(): return 2\n",
            ),
            patch(f"{MODULE}._write_file", return_value=False),
        ):
            result = await refactoring._apply_and_save_refactoring(
                test_file, "def f(): return 1\n", [func_info], issue=None
            )

        assert result.success is False
        assert "Failed to write refactored" in result.remaining_issues[0]


class TestProcessComplexityReductionBranches:
    async def test_empty_content_returns_failure(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("")

        result = await refactoring._process_complexity_reduction(test_file)
        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    async def test_no_complex_functions_returns_failure(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f():\n    return 1\n")

        with patch(f"{MODULE}.find_complex_functions", return_value=[]):
            result = await refactoring._process_complexity_reduction(test_file)

        assert result.success is False
        assert "No overly complex" in result.remaining_issues[0]


class TestProcessDeadCodeRemovalBranches:
    async def test_empty_content_returns_failure(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("")

        result = await refactoring._process_dead_code_removal(test_file)
        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    async def test_no_removable_items_returns_success_with_recommendation(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")

        with patch(
            f"{MODULE}.analyze_dead_code",
            return_value={"removable_items": []},
        ):
            result = await refactoring._process_dead_code_removal(test_file)

        assert result.success is True
        assert result.confidence == 0.7
        assert "No obvious dead code" in result.recommendations[0]


class TestApplyAndSaveCleanup:
    def test_no_changes_returns_no_cleanup(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")

        with patch(f"{MODULE}._collect_all_removable_lines", return_value=set()):
            result = refactoring._apply_and_save_cleanup(
                test_file, "x = 1\n", {"removable_items": []}
            )

        assert result.success is False
        assert "Could not automatically remove" in result.remaining_issues[0]

    def test_write_failure_returns_failure(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")

        with (
            patch(f"{MODULE}._collect_all_removable_lines", return_value={0}),
            patch(f"{MODULE}._write_file", return_value=False),
        ):
            result = refactoring._apply_and_save_cleanup(
                test_file, "x = 1\n", {"removable_items": ["x"]}
            )

        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]

    def test_successful_removal(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")

        with patch(f"{MODULE}._collect_all_removable_lines", return_value={0}):
            result = refactoring._apply_and_save_cleanup(
                test_file, "x = 1\n", {"removable_items": ["x"]}
            )

        assert result.success is True
        assert "Removed 1" in result.fixes_applied[0]


class TestFindExtendedUnreachableLines:
    def test_no_unreachable_items_returns_empty(self) -> None:
        lines = ["def f():\n", "    return 1\n"]
        assert refactoring._find_extended_unreachable_lines(lines, {}) == set()

    def test_skips_to_next_function(self) -> None:
        lines = [
            "def outer():\n",
            "    return 1\n",
            "    unreachable = 2\n",
            "\n",
            "def another():\n",
            "    pass\n",
        ]
        analysis = {
            "unreachable_code": [
                {"type": "unreachable_after_return", "line": 3, "function": "outer"}
            ]
        }

        result = refactoring._find_extended_unreachable_lines(lines, analysis)
        assert 2 in result

    def test_find_function_indent(self) -> None:
        lines = ["def f():\n", "    pass\n"]
        assert refactoring._find_function_indent(lines, "f") == 0

    def test_find_function_indent_missing(self) -> None:
        lines = ["def other():\n", "    pass\n"]
        assert refactoring._find_function_indent(lines, "missing") is None


class TestLocateComplexityTargetLine:
    def test_returns_none_when_no_issue(self) -> None:
        assert (
            refactoring._locate_complexity_target_line("def f(): pass\n", None) is None
        )

    def test_finds_function_by_name(self) -> None:
        issue = Issue(
            id="l-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'target_func' - too complex",
        )
        result = refactoring._locate_complexity_target_line(
            "def target_func():\n    pass\n", issue
        )
        assert result == 0

    def test_finds_function_by_line_number(self) -> None:
        issue = Issue(
            id="l-2",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="complexity at line 1",
            line_number=1,
        )
        result = refactoring._locate_complexity_target_line(
            "def f():\n    return 1\n", issue
        )
        assert result == 0


class TestApplyComplexityNoqaFallback:
    def test_noqa_already_present_returns_none(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): pass  # noqa: C901\n")

        issue = Issue(
            id="n-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'f' too complex",
            line_number=1,
        )

        result = refactoring._apply_complexity_noqa_fallback(test_file, issue)
        assert result is None

    def test_existing_noqa_appends_c901(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): pass  # noqa: A001\n")

        issue = Issue(
            id="n-2",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'f' too complex",
            line_number=1,
        )

        result = refactoring._apply_complexity_noqa_fallback(test_file, issue)
        assert result is not None
        assert result.success is True

    def test_write_failure_returns_none(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): pass\n")

        issue = Issue(
            id="n-3",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'f' too complex",
            line_number=1,
        )

        with patch(f"{MODULE}._write_file", return_value=False):
            result = refactoring._apply_complexity_noqa_fallback(test_file, issue)
        assert result is None


class TestAstComplexityFallback:
    async def test_no_candidates_returns_none(self, tmp_path: Path) -> None:
        result = await refactoring._apply_ast_complexity_fallback(
            tmp_path / "x.py", "def f(): pass\n", [], issue=None
        )
        assert result is None

    async def test_transform_returns_none_continues(self, tmp_path: Path) -> None:
        engine = Mock()
        engine.transform = AsyncMock(return_value=None)

        candidate = {"name": "f", "line_start": 1, "line_end": 1, "complexity": 20}

        with patch(f"{MODULE}._get_ast_transform_engine", return_value=engine):
            result = await refactoring._apply_ast_complexity_fallback(
                tmp_path / "x.py", "def f(): pass\n", [candidate], issue=None
            )

        assert result is None

    async def test_write_failure_returns_error(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): pass\n")

        change_spec = SimpleNamespace(transformed_content="def f(): return 1\n")
        engine = Mock()
        engine.transform = AsyncMock(return_value=change_spec)

        candidate = {"name": "f", "line_start": 1, "line_end": 1, "complexity": 20}

        with (
            patch(f"{MODULE}._get_ast_transform_engine", return_value=engine),
            patch(f"{MODULE}._write_file", return_value=False),
        ):
            result = await refactoring._apply_ast_complexity_fallback(
                test_file,
                "def f(): pass\n",
                [candidate],
                issue=Issue(
                    id="ast-1",
                    type=IssueType.COMPLEXITY,
                    severity=Priority.HIGH,
                    message="complex",
                ),
            )

        assert result is not None
        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]

    def test_prioritize_complexity_candidates_empty(self) -> None:
        assert refactoring._prioritize_complexity_candidates([], None) == []

    def test_prioritize_complexity_candidates_orders_by_name(self) -> None:
        candidates = [
            {"name": "a", "line_start": 1, "line_end": 1},
            {"name": "b", "line_start": 1, "line_end": 1},
        ]
        issue = Issue(
            id="p-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'b' too complex",
        )
        ordered = refactoring._prioritize_complexity_candidates(candidates, issue)
        assert ordered[0]["name"] == "b"


class TestComplexityReducedHelpers:
    def test_reduced_below_threshold_syntax_error(self) -> None:
        candidate = {"name": "f", "line_start": 1, "line_end": 1}
        result = refactoring._complexity_reduced_below_threshold(
            "def broken(:\n", candidate
        )
        assert result is False

    def test_reduced_below_threshold_no_function(self) -> None:
        candidate = {"name": "missing", "line_start": 100, "line_end": 101}
        result = refactoring._complexity_reduced_below_threshold(
            "def f(): pass\n", candidate
        )
        assert result is False

    def test_reduced_for_targets_syntax_error(self) -> None:
        result = refactoring._complexity_reduced_for_targets(
            "def broken(:\n", [{"name": "f", "line_start": 1, "line_end": 1}]
        )
        assert result is False

    def test_reduced_for_targets_empty(self) -> None:
        assert (
            refactoring._complexity_reduced_for_targets("def f(): pass\n", []) is False
        )


class TestExecuteFixPlan:
    async def test_empty_changes_returns_error(self, tmp_path: Path) -> None:
        plan = create_fix_plan(
            file_path="x.py", issue_type="COMPLEXITY", changes=[], rationale="nothing"
        )

        result = await refactoring.execute_fix_plan(plan, tmp_path)
        assert result.success is False
        assert "no changes" in result.remaining_issues[0].lower()

    async def test_no_file_path_returns_error(self, tmp_path: Path) -> None:
        plan = FixPlan(
            file_path="",
            issue_type="COMPLEXITY",
            risk_level="low",
            validated_by="system",
            rationale="r",
            changes=[
                ChangeSpec(
                    line_range=(1, 1), old_code="", new_code="x = 1\n", reason="r"
                )
            ],
        )

        result = await refactoring.execute_fix_plan(plan, tmp_path)
        assert result.success is False
        assert "no file path" in result.remaining_issues[0].lower()

    async def test_read_failure_returns_error(self, tmp_path: Path) -> None:
        plan = create_fix_plan(
            file_path=str(tmp_path / "missing.py"),
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(line_range=(1, 1), old_code="x", new_code="y", reason="r")
            ],
            rationale="r",
        )

        result = await refactoring.execute_fix_plan(plan, tmp_path)
        assert result.success is False

    async def test_invalid_line_range_marks_change_failed(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")

        plan = create_fix_plan(
            file_path=str(test_file),
            issue_type="OTHER",
            changes=[
                ChangeSpec(
                    line_range=(0, 100),
                    old_code="",
                    new_code="x = 2\n",
                    reason="bogus range",
                )
            ],
            rationale="r",
        )

        result = await refactoring.execute_fix_plan(plan, tmp_path)
        assert result.success is False
        assert any("Invalid line range" in issue for issue in result.remaining_issues)

    async def test_non_complexity_plan_skips_fallback(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")

        plan = create_fix_plan(
            file_path=str(test_file),
            issue_type="DEAD_CODE",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="x = 1\n",
                    new_code="x = 2\n",
                    reason="change x",
                )
            ],
            rationale="r",
        )

        with (
            patch(f"{MODULE}._apply_ruff_formatting") as mock_ruff,
            patch(f"{MODULE}._handle_complexity_fallback") as mock_fallback,
        ):
            mock_fallback.return_value = (False, 0.0, [])
            result = await refactoring.execute_fix_plan(plan, tmp_path)

        assert result.success is False
        mock_ruff.assert_not_called()

    async def test_applies_ast_transform_as_full_file_replacement(
        self, tmp_path: Path
    ) -> None:
        content = """class ProviderSync:
    async def sync_provider_configs(
        self,
        source: str = "claude",
        destination: str = "qwen",
        sync_types: list[str] | None = None,
        skip_servers: list[str] | None = None,
    ) -> dict[str, str]:
        # prepare config
        config = {}
        if source != destination:
            config["source"] = source
        config["destination"] = destination
        config["sync_types"] = ",".join(sync_types or [])
        config["source_destination"] = f"{source}:{destination}"
        config["count"] = str(len(sync_types or []))
        # finalize sync
        if skip_servers:
            config["skip"] = ",".join(skip_servers)
        config["enabled"] = "true"
        config["mode"] = "sync"
        return config
"""
        file_path = tmp_path / "provider_sync.py"
        file_path.write_text(content)

        engine = refactoring._get_ast_transform_engine()
        result = await engine.transform(
            content, file_path, 2, len(content.splitlines())
        )
        assert result is not None

        plan = create_fix_plan(
            file_path=str(file_path),
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(
                    line_range=(2, 2),
                    old_code="    async def sync_provider_configs(...) -> dict[str, str]:",
                    new_code=result.transformed_content,
                    reason=(
                        "AST transform (extract_method): reduced complexity by "
                        f"{result.complexity_reduction}"
                    ),
                ),
            ],
            rationale="Reduce complexity with AST transform",
            risk_level="high",
            validated_by="PlanningAgent",
        )

        fix_result = await refactoring.execute_fix_plan(plan, tmp_path)

        assert fix_result.success is True
        written = file_path.read_text()
        module = ast.parse(written)
        assert any(
            isinstance(node, ast.AsyncFunctionDef)
            and node.name == "sync_provider_configs"
            for node in module.body
        )
        assert any(
            isinstance(node, ast.AsyncFunctionDef)
            and node.name != "sync_provider_configs"
            for node in module.body
        )

    async def test_reports_ast_transform_write_failure(self, tmp_path: Path) -> None:
        content = """class ProviderSync:
    async def sync_provider_configs(
        self,
        source: str = "claude",
        destination: str = "qwen",
        sync_types: list[str] | None = None,
        skip_servers: list[str] | None = None,
    ) -> dict[str, str]:
        # prepare config
        config = {}
        if source != destination:
            config["source"] = source
        config["destination"] = destination
        config["sync_types"] = ",".join(sync_types or [])
        config["source_destination"] = f"{source}:{destination}"
        config["count"] = str(len(sync_types or []))
        # finalize sync
        if skip_servers:
            config["skip"] = ",".join(skip_servers)
        config["enabled"] = "true"
        config["mode"] = "sync"
        return config
"""
        file_path = tmp_path / "provider_sync.py"
        file_path.write_text(content)

        engine = refactoring._get_ast_transform_engine()
        result = await engine.transform(
            content, file_path, 2, len(content.splitlines())
        )
        assert result is not None

        plan = create_fix_plan(
            file_path=str(file_path),
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(
                    line_range=(2, 2),
                    old_code="    async def sync_provider_configs(...) -> dict[str, str]:",
                    new_code=result.transformed_content,
                    reason=(
                        "AST transform (extract_method): reduced complexity by "
                        f"{result.complexity_reduction}"
                    ),
                ),
            ],
            rationale="Reduce complexity with AST transform",
            risk_level="high",
            validated_by="PlanningAgent",
        )

        with patch(f"{MODULE}._write_file", return_value=False):
            fix_result = await refactoring.execute_fix_plan(plan, tmp_path)

        assert fix_result.success is False
        assert any(
            "Failed to write AST transform" in issue
            for issue in fix_result.remaining_issues
        )

    async def test_adds_complexity_noqa_fallback(self, tmp_path: Path) -> None:
        content = """def target_function():
    if first:
        if second:
            if third:
                if fourth:
                    if fifth:
                        if sixth:
                            if seventh:
                                if eighth:
                                    if ninth:
                                        if tenth:
                                            if eleventh:
                                                if twelfth:
                                                    return True
    return False
"""
        file_path = tmp_path / "complexity_plan.py"
        file_path.write_text(content)

        plan = create_fix_plan(
            file_path=str(file_path),
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="def target_function():",
                    new_code="def target_function():",
                    reason=(
                        "Complexity fallback: preserve issue context for "
                        "RefactoringAgent when planner transform is unavailable"
                    ),
                ),
            ],
            rationale="Keep the plan but ensure complexity is addressed",
            risk_level="medium",
            validated_by="PlanningAgent",
            issue_message="Function 'target_function' has complexity 20",
            issue_details=["function: target_function"],
        )

        fix_result = await refactoring.execute_fix_plan(plan, tmp_path)

        assert fix_result.success is True
        written = file_path.read_text(encoding="utf-8")
        # Two spaces before the comment: execute_fix_plan runs `ruff format`
        # on success (_apply_ruff_formatting), which normalizes to PEP8's
        # "at least two spaces before an inline comment" after the noqa
        # fallback's own single-space append.
        assert "def target_function():  # noqa: C901" in written

    async def test_apply_ruff_formatting_pins_cwd_to_project_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Task 22a regression: `_apply_ruff_formatting` (called from
        # `execute_fix_plan` on a successful `.py` change) is a bare
        # `subprocess.run` with no `cwd=` before this fix. Exercise the real
        # subprocess call and capture the `cwd` kwarg to prove it is now
        # pinned to the `project_root` passed into `execute_fix_plan`.
        import subprocess

        test_file = tmp_path / "x.py"
        test_file.write_text("x=1\n")

        plan = create_fix_plan(
            file_path=str(test_file),
            issue_type="OTHER",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="x=1",
                    new_code="x=2",
                    reason="bump",
                )
            ],
            rationale="r",
        )

        captured: dict[str, object] = {}
        real_run = subprocess.run

        def spying_run(*args: object, **kwargs: object):
            if args and args[0][:1] == ["ruff"]:  # type: ignore[index]
                captured["cwd"] = kwargs.get("cwd")
            return real_run(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(subprocess, "run", spying_run)

        result = await refactoring.execute_fix_plan(plan, tmp_path)

        assert result is not None
        assert result.success is True
        assert captured["cwd"] == tmp_path


class TestApplyStandardFixChange:
    def test_invalid_line_range_logs_failure(self) -> None:
        applied: list[str] = []
        failed: list[str] = []
        change = ChangeSpec(
            line_range=(0, 1000), old_code="", new_code="x = 1\n", reason="bad"
        )
        plan = create_fix_plan(
            file_path="x.py", issue_type="X", changes=[change], rationale="r"
        )

        refactoring._apply_standard_fix_change(
            plan, "x = 1\n", change, 0, applied, failed
        )
        assert not applied
        assert any("Invalid line range" in f for f in failed)

    def test_successful_replacement(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")
        applied: list[str] = []
        failed: list[str] = []
        change = ChangeSpec(
            line_range=(1, 1), old_code="x = 1\n", new_code="x = 2\n", reason="rename"
        )
        plan = create_fix_plan(
            file_path=str(test_file), issue_type="X", changes=[change], rationale="r"
        )

        refactoring._apply_standard_fix_change(
            plan, "x = 1\n", change, 0, applied, failed
        )
        assert applied
        assert not failed

    def test_write_failure_marks_failed(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")
        applied: list[str] = []
        failed: list[str] = []
        change = ChangeSpec(
            line_range=(1, 1), old_code="x = 1\n", new_code="x = 2\n", reason="rename"
        )
        plan = create_fix_plan(
            file_path=str(test_file), issue_type="X", changes=[change], rationale="r"
        )

        with patch(f"{MODULE}._write_file", return_value=False):
            refactoring._apply_standard_fix_change(
                plan, "x = 1\n", change, 0, applied, failed
            )
        assert not applied
        assert failed


class TestApplyAstTransformChange:
    def test_non_ast_change_returns_false(self) -> None:
        change = ChangeSpec(
            line_range=(1, 1), old_code="", new_code="x", reason="standard change"
        )
        applied: list[str] = []
        failed: list[str] = []
        result = refactoring._apply_ast_transform_change(
            "x.py", change, 0, applied, failed
        )
        assert result is False
        assert not applied

    def test_ast_change_success(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="",
            new_code="x = 1\n",
            reason="AST transform: extract method",
        )
        applied: list[str] = []
        failed: list[str] = []

        result = refactoring._apply_ast_transform_change(
            str(test_file), change, 0, applied, failed
        )
        assert result is True
        assert applied

    def test_ast_change_write_failure(self) -> None:
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="",
            new_code="x = 1\n",
            reason="AST transform: extract method",
        )
        applied: list[str] = []
        failed: list[str] = []

        with patch(f"{MODULE}._write_file", return_value=False):
            result = refactoring._apply_ast_transform_change(
                "x.py", change, 0, applied, failed
            )
        assert result is True
        assert not applied
        assert failed


class TestComplexityStillExceedsThreshold:
    def test_none_line_number_returns_true(self) -> None:
        assert refactoring._complexity_still_exceeds_threshold("x.py", None) is True

    def test_empty_content_returns_true(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.py"
        assert refactoring._complexity_still_exceeds_threshold(str(missing), 1) is True

    def test_syntax_error_returns_true(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def broken(:\n")
        assert (
            refactoring._complexity_still_exceeds_threshold(str(test_file), 1) is True
        )

    def test_simple_function_returns_false(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f():\n    return 1\n")
        assert (
            refactoring._complexity_still_exceeds_threshold(str(test_file), 1) is False
        )

    def test_line_outside_function_returns_true(self, tmp_path: Path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f():\n    return 1\n")
        assert (
            refactoring._complexity_still_exceeds_threshold(str(test_file), 100) is True
        )


class TestHandleComplexityFallback:
    def test_non_complexity_returns_immediately(self) -> None:
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="DEAD_CODE",
            changes=[
                ChangeSpec(line_range=(1, 1), old_code="", new_code="", reason="r")
            ],
            rationale="r",
        )
        result = refactoring._handle_complexity_fallback(plan, "x.py", True, 0.5, [])
        assert result[0] is True
        assert result[1] == 0.5

    def test_complexity_below_threshold_returns_immediately(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f():\n    return 1\n")
        plan = create_fix_plan(
            file_path=str(test_file),
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(line_range=(1, 1), old_code="", new_code="", reason="r")
            ],
            rationale="r",
        )
        result = refactoring._handle_complexity_fallback(
            plan, str(test_file), True, 0.8, []
        )
        assert result[0] is True
        assert result[1] == 0.8

    def test_issue_from_fix_plan_no_changes(self) -> None:
        plan = create_fix_plan(
            file_path="x.py", issue_type="COMPLEXITY", changes=[], rationale="r"
        )
        assert refactoring._issue_from_fix_plan(plan) is None

    def test_issue_from_fix_plan_zero_line(self) -> None:
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(line_range=(0, 0), old_code="", new_code="", reason="r")
            ],
            rationale="r",
        )
        assert refactoring._issue_from_fix_plan(plan) is None

    def test_issue_from_fix_plan_with_issue_message(self) -> None:
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(line_range=(5, 5), old_code="", new_code="", reason="r")
            ],
            rationale="r",
            issue_message="from plan",
            issue_details=["function: f"],
            issue_stage="test",
        )
        issue = refactoring._issue_from_fix_plan(plan)
        assert issue is not None
        assert issue.message == "from plan"
        assert issue.line_number == 5
        assert issue.stage == "test"


class TestGetAstTransformEngine:
    def test_returns_cached_engine(self) -> None:
        refactoring._ast_transform_engine = None

        with patch(
            "crackerjack.fixers.ast_transform.ASTTransformEngine"
        ) as mock_engine_cls:
            mock_engine_cls.return_value = Mock()

            engine1 = refactoring._get_ast_transform_engine()
            engine2 = refactoring._get_ast_transform_engine()

        assert engine1 is engine2
        mock_engine_cls.assert_called_once()

        # Reset for other tests in this module.
        refactoring._ast_transform_engine = None

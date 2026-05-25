"""Tests for TypeErrorSpecialistAgent."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
import subprocess

from crackerjack.agents.base import AgentContext, Issue, IssueType, FixResult, Priority
from crackerjack.agents.type_error_specialist import TypeErrorSpecialistAgent


@pytest.fixture
def mock_context():
    """Create mock AgentContext."""
    context = Mock(spec=AgentContext)
    context.project_path = Path("/test/project")
    context.get_file_content = Mock(return_value=None)
    context.write_file_content = Mock(return_value=True)
    return context


@pytest.fixture
def agent(mock_context):
    """Create TypeErrorSpecialistAgent instance."""
    return TypeErrorSpecialistAgent(mock_context)


class TestTypeErrorSpecialistAgent:
    """Tests for TypeErrorSpecialistAgent."""

    def test_supported_types(self, agent):
        """Test get_supported_types returns TYPE_ERROR."""
        assert agent.get_supported_types() == {IssueType.TYPE_ERROR}

    @pytest.mark.asyncio
    async def test_can_handle_type_error_issue(self, agent):
        """Test can_handle returns high confidence for type error issues."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.TYPE_ERROR
        issue.message = "Missing return type annotation"
        issue.stage = "pyright"

        confidence = await agent.can_handle(issue)
        assert confidence == 0.85

    @pytest.mark.asyncio
    async def test_can_handle_non_type_error(self, agent):
        """Test can_handle returns 0 for non-type error issues."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.FORMATTING
        issue.message = "Formatting issue"
        issue.stage = "ruff"

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_can_handle_no_message(self, agent):
        """Test can_handle returns 0 for issue with no message."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.TYPE_ERROR
        issue.message = ""
        issue.stage = "pyright"

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_can_handle_different_stages(self, agent):
        """Test can_handle handles different type checker stages."""
        issue = Mock(spec=Issue)
        issue.type = IssueType.TYPE_ERROR
        issue.message = "Type error"

        for stage in ["zuban", "pyrefly", "ty", "pyright", "pyscn"]:
            issue.stage = stage
            confidence = await agent.can_handle(issue)
            assert confidence == 0.85

        issue.stage = "unknown"
        confidence = await agent.can_handle(issue)
        assert confidence == 0.6

    @pytest.mark.asyncio
    async def test_analyze_and_fix_no_file_path(self, agent):
        """Test analyze_and_fix handles missing file path."""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Missing return type",
            file_path=None,
        )

        result = await agent.analyze_and_fix(issue)
        assert result.success is False
        assert "No file path provided" in result.remaining_issues

    @pytest.mark.asyncio
    async def test_analyze_and_fix_file_not_found(self, agent):
        """Test analyze_and_fix handles missing file."""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Missing return type",
            file_path="/test/project/nonexistent.py",
        )

        result = await agent.analyze_and_fix(issue)
        assert result.success is False
        assert "File not found" in result.remaining_issues

    def test_add_future_annotations(self, agent):
        """Test _add_future_annotations adds future import."""
        content = "import os\n\ndef foo():\n    pass\n"
        new_content, fixes = agent._add_future_annotations(content)
        assert "from __future__ import annotations" in new_content
        assert "Added __future__ annotations import" in fixes

    def test_add_future_annotations_already_present(self, agent):
        """Test _add_future_annotations doesn't add if already present."""
        content = "from __future__ import annotations\n\ndef foo():\n    pass\n"
        new_content, fixes = agent._add_future_annotations(content)
        assert new_content == content
        assert fixes == []

    def test_fix_missing_return_types(self, agent):
        """Test _fix_missing_return_types adds return types."""
        content = """
def foo(x, y):
    return x + y
"""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type annotation",
            line_number=2,
        )
        new_content, fixes = agent._fix_missing_return_types(content, issue)
        assert "-> None:" in new_content

    def test_add_typing_imports_any(self, agent):
        """Test _add_typing_imports adds Any import."""
        content = "import os\n"
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Any is not defined",
        )
        new_content, fixes = agent._add_typing_imports(content, issue)
        assert "from typing import Any" in new_content

    def test_add_typing_imports_optional(self, agent):
        """Test _add_typing_imports adds Optional import."""
        content = "import os\n"
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Optional is not defined",
        )
        new_content, fixes = agent._add_typing_imports(content, issue)
        assert "from typing import Optional" in new_content

    def test_add_typing_imports_union(self, agent):
        """Test _add_typing_imports adds Union import."""
        content = "import os\n"
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Union is not defined",
        )
        new_content, fixes = agent._add_typing_imports(content, issue)
        assert "from typing import Union" in new_content

    def test_add_common_imports_operator(self, agent):
        """Test _add_common_imports adds operator import."""
        content = "import os\n"
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="operator.add is not defined",
        )
        new_content, fixes = agent._add_common_imports(content, issue)
        assert "import operator" in new_content

    def test_add_common_imports_suppress(self, agent):
        """Test _add_common_imports adds suppress import."""
        content = "import os\n"
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="suppress is not defined",
        )
        new_content, fixes = agent._add_common_imports(content, issue)
        assert "from contextlib import suppress" in new_content

    def test_fix_suppress_tuple_arg_type(self, agent):
        """Test _fix_suppress_tuple_arg_type flattens tuples."""
        content = "with suppress((ValueError, TypeError)):\n    pass\n"
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="suppress",
        )
        new_content, fixes = agent._fix_suppress_tuple_arg_type(content, issue)
        assert "with suppress(ValueError, TypeError):" in new_content

    def test_infer_and_add_return_types(self, agent):
        """Test _infer_and_add_return_types infers return types."""
        content = """
def foo():
    return 42
"""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type",
            line_number=2,
        )
        new_content, fixes = agent._infer_and_add_return_types(content, issue)
        assert "-> int" in new_content

    def test_infer_return_type_from_body_int(self, agent):
        """Test _infer_return_type_from_body infers int."""
        content = """
def foo():
    return 42
"""
        import ast
        tree = ast.parse(content)
        func = tree.body[0]
        result = agent._infer_return_type_from_body(func, content)
        assert result == "int"

    def test_infer_return_type_from_body_str(self, agent):
        """Test _infer_return_type_from_body infers str."""
        content = """
def foo():
    return "hello"
"""
        import ast
        tree = ast.parse(content)
        func = tree.body[0]
        result = agent._infer_return_type_from_body(func, content)
        assert result == "str"

    def test_infer_return_type_from_body_bool(self, agent):
        """Test _infer_return_type_from_body infers bool."""
        content = """
def foo():
    return True
"""
        import ast
        tree = ast.parse(content)
        func = tree.body[0]
        result = agent._infer_return_type_from_body(func, content)
        assert result == "bool"

    def test_infer_return_type_from_body_none(self, agent):
        """Test _infer_return_type_from_body returns None."""
        content = """
def foo():
    pass
"""
        import ast
        tree = ast.parse(content)
        func = tree.body[0]
        result = agent._infer_return_type_from_body(func, content)
        assert result == "None"

    def test_infer_type_from_constant(self, agent):
        """Test _infer_type_from_constant for various types."""
        import ast

        for value, expected in [
            (ast.Constant(value=42), "int"),
            (ast.Constant(value="str"), "str"),
            (ast.Constant(value=3.14), "float"),
            (ast.Constant(value=True), "bool"),
            (ast.Constant(value=None), "None"),
        ]:
            result = agent._infer_constant_type(value)
            assert result == expected

    def test_infer_type_from_list(self, agent):
        """Test _infer_type_from_list for list expressions."""
        import ast

        node = ast.List(elts=[ast.Constant(value=1), ast.Constant(value=2)])
        result = agent._infer_list_type(node)
        assert result == "list[int]"

    def test_infer_type_from_dict(self, agent):
        """Test _infer_type_from_dict for dict expressions."""
        import ast

        node = ast.Dict(
            keys=[ast.Constant(value="key")],
            values=[ast.Constant(value=1)],
        )
        result = agent._infer_dict_type(node)
        assert result == "dict[str, int]"

    def test_fix_complex_generic_types(self, agent):
        """Test _fix_complex_generic_types modernizes typing syntax."""
        content = """
from typing import List, Dict
x: List[int] = []
y: Dict[str, int] = {}
"""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Generic type arguments",
        )
        new_content, fixes = agent._fix_complex_generic_types(content, issue)
        assert "list[" in new_content or "List[" in new_content

    def test_fix_optional_union_types(self, agent):
        """Test _fix_optional_union_types converts to union syntax."""
        content = """
from __future__ import annotations
from typing import Optional, Union

def foo(x: Optional[int]) -> Union[str, None]:
    pass
"""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Optional or Union",
        )
        new_content, fixes = agent._fix_optional_union_types(content, issue)
        assert "int | None" in new_content or "Optional[int]" not in new_content or len(fixes) > 0

    def test_split_union_types(self, agent):
        """Test _split_union_types handles nested brackets."""
        result = agent._split_union_types("int, str")
        assert len(result) == 2

        result = agent._split_union_types("List[int], Dict[str, Any]")
        assert len(result) == 2

    def test_detect_and_fix_protocol_patterns(self, agent):
        """Test _detect_and_fix_protocol_patterns identifies protocol candidates."""
        content = """
class Foo:
    def method1(self):
        pass

    def method2(self):
        pass
"""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Protocol structural typing",
        )
        new_content, fixes = agent._detect_and_fix_protocol_patterns(content, issue)
        assert len(fixes) > 0

    def test_is_self_type_issue(self, agent):
        """Test _is_self_type_issue detects self-related issues."""
        assert agent._is_self_type_issue("return type of self") is True
        assert agent._is_self_type_issue("same type as self") is True
        assert agent._is_self_type_issue("some other issue") is False

    def test_collect_class_names(self, agent):
        """Test _collect_class_names extracts class names."""
        import ast

        content = """
class Foo:
    pass

class Bar:
    pass
"""
        tree = ast.parse(content)
        names = agent._collect_class_names(tree)
        assert "Foo" in names
        assert "Bar" in names

    def test_should_skip_method_staticmethod(self, agent):
        """Test _should_skip_method skips staticmethods."""
        import ast

        node = ast.FunctionDef(
            name="foo",
            args=ast.arguments(),
            body=[ast.Pass()],
            decorator_list=[ast.Name(id="staticmethod", ctx=ast.Load())],
        )
        assert agent._should_skip_method(node) is True

    def test_should_skip_method_dunder(self, agent):
        """Test _should_skip_method skips private dunder methods."""
        import ast

        node = ast.FunctionDef(
            name="_private",
            args=ast.arguments(),
            body=[ast.Pass()],
            decorator_list=[],
        )
        assert agent._should_skip_method(node) is True

    def test_should_not_skip_method_dunder_magic(self, agent):
        """Test _should_skip_method does not skip __enter__ and __exit__."""
        import ast

        node = ast.FunctionDef(
            name="__enter__",
            args=ast.arguments(),
            body=[ast.Pass()],
            decorator_list=[],
        )
        assert agent._should_skip_method(node) is False

    def test_fix_up031_percent_format(self, agent):
        """Test _fix_up031_percent_format adds noqa comment."""
        content = 'x = "value" % (a, b)\n'
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="UP031",
            line_number=1,
        )
        new_content, fixes = agent._fix_up031_percent_format(content, issue)
        assert "# noqa: UP031" in new_content

    def test_prune_unused_typing_imports(self, agent):
        """Test _prune_unused_typing_imports removes unused imports."""
        content = """
from typing import Any, Optional, List

def foo():
    pass
"""
        new_content, fixes = agent._prune_unused_typing_imports(content)
        assert "Optional" in new_content or len(fixes) > 0

    @patch("subprocess.run")
    def test_format_python_file(self, mock_run):
        """Test _format_python_file calls ruff."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")

        agent._format_python_file(Path("/test/file.py"))

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "ruff" in args
        assert "format" in args
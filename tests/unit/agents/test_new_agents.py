"""Tests for newly implemented agents and services.

This module tests:
- RefurbCodeTransformerAgent
- TypeErrorSpecialistAgent enhancements
- DeadCodeRemovalAgent enhancements
- AgentDelegator service
- PlanningAgent delegation
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
)
from crackerjack.agents.dead_code_removal_agent import (
    DeadCodeInfo,
    DeadCodeRemovalAgent,
)
from crackerjack.agents.refurb_agent import RefurbCodeTransformerAgent
from crackerjack.agents.type_error_specialist import TypeErrorSpecialistAgent


# Test Fixtures
@pytest.fixture
def mock_context():
    """Create a mock AgentContext for testing."""
    context = MagicMock(spec=AgentContext)
    context.project_path = Path("/tmp/test_project")
    context.get_file_content = MagicMock(return_value="")
    context.write_file_content = MagicMock(return_value=True)
    return context


@pytest.fixture
def type_error_issue():
    """Create a mock type error issue for testing."""
    return Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.HIGH,
        message="Function is missing return type annotation",
        file_path="/tmp/test_project/test_file.py",
        line_number=10,
    )


@pytest.fixture
def dead_code_issue():
    """Create a mock dead code issue for testing."""
    return Issue(
        type=IssueType.DEAD_CODE,
        severity=Priority.MEDIUM,
        message="Unused function 'old_helper' (line 15, 86% confidence)",
        file_path="/tmp/test_project/test_file.py",
        line_number=15,
    )


@pytest.fixture
def refurb_issue():
    """Create a mock refurb issue for testing."""
    return Issue(
        type=IssueType.REFURB,
        severity=Priority.LOW,
        message="FURB136: Replace if x: return True with return bool(x)",
        file_path="/tmp/test_project/test_file.py",
        line_number=20,
    )


# RefurbCodeTransformerAgent Tests
class TestRefurbCodeTransformerAgent:
    """Tests for RefurbCodeTransformerAgent."""

    def test_agent_initialization(self, mock_context):
        """Test agent initializes correctly."""
        agent = RefurbCodeTransformerAgent(mock_context)
        assert agent.name == "RefurbCodeTransformerAgent"
        assert IssueType.REFURB in agent.get_supported_types()

    @pytest.mark.asyncio
    async def test_can_handle_refurb_issue(self, mock_context, refurb_issue):
        """Test agent can handle refurb issues."""
        agent = RefurbCodeTransformerAgent(mock_context)
        confidence = await agent.can_handle(refurb_issue)
        assert confidence >= 0.7

    @pytest.mark.asyncio
    async def test_cannot_handle_other_issues(self, mock_context, type_error_issue):
        """Test agent rejects non-refurb issues."""
        agent = RefurbCodeTransformerAgent(mock_context)
        confidence = await agent.can_handle(type_error_issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_analyze_and_fix_converts_append_loop_to_list_comprehension(
        self, tmp_path
    ) -> None:
        """Test FURB138 append loops are rewritten to list comprehensions."""
        content = """from __future__ import annotations


def sync_provider_configs(self):
    plugin_names = []
    for plugin_id in enabled_plugins.keys():
        name = plugin_id.split("@")[0]
        plugin_names.append(name)
    return plugin_names
"""
        file_path = tmp_path / "llm_providers.py"
        file_path.write_text(content)

        context = MagicMock(spec=AgentContext)
        context.project_path = tmp_path
        context.get_file_content = MagicMock(return_value=content)
        context.write_file_content = MagicMock(
            side_effect=lambda path, new_content: Path(path).write_text(new_content)
            or True
        )

        agent = RefurbCodeTransformerAgent(context)
        issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.LOW,
            message="FURB138: Consider using list comprehension",
            file_path=str(file_path),
            line_number=8,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is True
        written = file_path.read_text()
        assert "plugin_names = [plugin_id.split(\"@\")[0] for plugin_id in enabled_plugins.keys()]" in written
        assert "plugin_names.append(name)" not in written

    def test_furb_transformations_dict_exists(self, mock_context):
        """Test FURB_TRANSFORMATIONS dictionary is populated."""
        from crackerjack.agents.refurb_agent import FURB_TRANSFORMATIONS

        # FURB_TRANSFORMATIONS is a module-level variable
        assert len(FURB_TRANSFORMATIONS) >= 10
        assert "FURB118" in FURB_TRANSFORMATIONS
        assert "FURB136" in FURB_TRANSFORMATIONS


# TypeErrorSpecialistAgent Tests
class TestTypeErrorSpecialistAgent:
    """Tests for TypeErrorSpecialistAgent enhancements."""

    def test_agent_initialization(self, mock_context):
        """Test agent initializes correctly."""
        agent = TypeErrorSpecialistAgent(mock_context)
        assert agent.name == "TypeErrorSpecialist"
        assert IssueType.TYPE_ERROR in agent.get_supported_types()

    @pytest.mark.asyncio
    async def test_can_handle_type_error(self, mock_context, type_error_issue):
        """Test agent can handle type errors."""
        agent = TypeErrorSpecialistAgent(mock_context)
        confidence = await agent.can_handle(type_error_issue)
        assert confidence >= 0.6

    def test_infer_type_from_constant(self, mock_context):
        """Test type inference from constant expressions."""
        import ast

        agent = TypeErrorSpecialistAgent(mock_context)

        # Test various constant types
        assert agent._infer_type_from_expr(ast.Constant(value=None)) == "None"
        assert agent._infer_type_from_expr(ast.Constant(value=True)) == "bool"
        assert agent._infer_type_from_expr(ast.Constant(value=42)) == "int"
        assert agent._infer_type_from_expr(ast.Constant(value=3.14)) == "float"
        assert agent._infer_type_from_expr(ast.Constant(value="hello")) == "str"

    def test_infer_type_from_list(self, mock_context):
        """Test type inference from list expressions."""
        import ast

        agent = TypeErrorSpecialistAgent(mock_context)

        # Empty list
        empty_list = ast.List(elts=[], ctx=ast.Load())
        assert agent._infer_type_from_expr(empty_list) == "list[Any]"

        # List of ints
        int_list = ast.List(
            elts=[ast.Constant(value=1), ast.Constant(value=2)],
            ctx=ast.Load(),
        )
        result = agent._infer_type_from_expr(int_list)
        assert "list[" in result

    def test_infer_type_from_dict(self, mock_context):
        """Test type inference from dict expressions."""
        import ast

        agent = TypeErrorSpecialistAgent(mock_context)

        # Dict with string keys and int values
        dict_expr = ast.Dict(
            keys=[ast.Constant(value="a"), ast.Constant(value="b")],
            values=[ast.Constant(value=1), ast.Constant(value=2)],
        )
        result = agent._infer_type_from_expr(dict_expr)
        assert "dict[" in result

    def test_infer_type_from_compare(self, mock_context):
        """Test that comparisons return bool."""
        import ast

        agent = TypeErrorSpecialistAgent(mock_context)

        compare = ast.Compare(
            left=ast.Constant(value=1),
            ops=[ast.Eq()],
            comparators=[ast.Constant(value=2)],
        )
        assert agent._infer_type_from_expr(compare) == "bool"

    def test_split_union_types(self, mock_context):
        """Test splitting union type arguments."""
        agent = TypeErrorSpecialistAgent(mock_context)

        # Simple types
        result = agent._split_union_types("int, str, bool")
        assert result == ["int", "str", "bool"]

        # Nested generics
        result = agent._split_union_types("list[int], dict[str, Any]")
        assert len(result) == 2

    def test_modernize_optional_syntax(self, mock_context):
        """Test converting Optional[X] to X | None."""
        agent = TypeErrorSpecialistAgent(mock_context)

        content = """from __future__ import annotations

def foo(x: Optional[str]) -> None:
    pass
"""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Optional type can be simplified",
            file_path="test.py",
            line_number=3,
        )

        new_content, fixes = agent._fix_optional_union_types(content, issue)
        assert "Optional" not in new_content or len(fixes) > 0

    @pytest.mark.asyncio
    async def test_analyze_and_fix_prunes_unused_typing_imports(
        self, tmp_path
    ) -> None:
        """Test that the agent does not leave behind unused typing imports."""
        file_path = tmp_path / "sample.py"
        content = """from __future__ import annotations


def build(values: list[str] | None):
    return []
"""
        file_path.write_text(content)

        context = MagicMock(spec=AgentContext)
        context.project_path = tmp_path
        context.get_file_content = MagicMock(return_value=content)

        agent = TypeErrorSpecialistAgent(context)
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Optional union list dict type annotation issue",
            file_path=str(file_path),
            line_number=4,
            stage="zuban",
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is True
        written = file_path.read_text()
        assert "from typing import" not in written
        assert "Optional" not in written
        assert "Union" not in written
        assert "List" not in written
        assert "Dict" not in written

    def test_add_typing_imports_includes_any(self, mock_context):
        """Test Any import is added for name-defined Any fixes."""
        agent = TypeErrorSpecialistAgent(mock_context)

        content = "def build(values):\n    return values\n"
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Name "Any" is not defined  [name-defined]',
            file_path="/tmp/test_project/test_file.py",
            line_number=1,
        )

        new_content, fixes = agent._add_typing_imports(content, issue)

        assert "from typing import Any" in new_content
        assert any("Any" in fix for fix in fixes)

    def test_add_common_imports_includes_operator(self, mock_context):
        """Test operator import is added for name-defined operator fixes."""
        agent = TypeErrorSpecialistAgent(mock_context)

        content = "def build(items):\n    return items\n"
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Name "operator" is not defined  [name-defined]',
            file_path="/tmp/test_project/test_file.py",
            line_number=1,
        )

        new_content, fixes = agent._add_common_imports(content, issue)

        assert "import operator" in new_content
        assert any("operator" in fix for fix in fixes)

    def test_add_common_imports_includes_suppress(self, mock_context):
        """Test suppress import is added for name-defined suppress fixes."""
        agent = TypeErrorSpecialistAgent(mock_context)

        content = "def build():\n    return True\n"
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Name "suppress" is not defined  [name-defined]',
            file_path="/tmp/test_project/test_file.py",
            line_number=1,
        )

        new_content, fixes = agent._add_common_imports(content, issue)

        assert "from contextlib import suppress" in new_content
        assert any("suppress" in fix for fix in fixes)

    def test_fix_suppress_tuple_arg_type(self, mock_context):
        """Test suppress tuple arg-type issues are normalized."""
        agent = TypeErrorSpecialistAgent(mock_context)

        content = "with suppress((OSError, FileNotFoundError)):\n    pass\n"
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Argument 1 to "suppress" has incompatible type',
            file_path="/tmp/test_project/test_file.py",
            line_number=1,
        )

        new_content, fixes = agent._fix_suppress_tuple_arg_type(content, issue)

        assert "with suppress(OSError, FileNotFoundError):" in new_content
        assert any("Flattened suppress" in fix for fix in fixes)


# DeadCodeRemovalAgent Tests
class TestDeadCodeRemovalAgent:
    """Tests for DeadCodeRemovalAgent enhancements."""

    def test_agent_initialization(self, mock_context):
        """Test agent initializes correctly."""
        agent = DeadCodeRemovalAgent(mock_context)
        assert agent.name == "DeadCodeRemovalAgent"
        assert IssueType.DEAD_CODE in agent.get_supported_types()
        assert agent.min_confidence_threshold == 0.70

    @pytest.mark.asyncio
    async def test_can_handle_dead_code(self, mock_context, dead_code_issue):
        """Test agent can handle dead code issues."""
        agent = DeadCodeRemovalAgent(mock_context)
        confidence = await agent.can_handle(dead_code_issue)
        assert confidence >= 0.7

    def test_extract_confidence_from_message(self, mock_context):
        """Test extracting confidence percentage from messages."""
        agent = DeadCodeRemovalAgent(mock_context)

        assert agent._extract_confidence("86% confidence") == 0.86
        assert agent._extract_confidence("definitely unused") == 0.95
        assert agent._extract_confidence("likely unused") == 0.75
        assert agent._extract_confidence("possibly unused") == 0.50
        assert agent._extract_confidence("some unused code") == 0.70

    def test_dead_code_info_dataclass(self):
        """Test DeadCodeInfo dataclass."""
        info = DeadCodeInfo(
            code_type="function",
            name="old_func",
            line_number=10,
            confidence=0.86,
            end_line=20,
            decorators=["@deprecated"],
        )
        assert info.code_type == "function"
        assert info.name == "old_func"
        assert info.line_number == 10
        assert info.confidence == 0.86
        assert info.end_line == 20
        assert info.decorators == ["@deprecated"]

    def test_parse_skylos_format(self, mock_context):
        """Test parsing skylos output format."""
        agent = DeadCodeRemovalAgent(mock_context)

        content = "def unused_func():\n    pass\n"
        issue = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused function 'unused_func' (line 1, 92% confidence)",
            file_path="test.py",
            line_number=1,
        )

        result = agent._parse_dead_code_issue_enhanced(issue, content)
        assert result is not None
        assert result.code_type == "function"
        assert result.name == "unused_func"
        assert result.line_number == 1
        assert result.confidence == 0.92

    def test_parse_vulture_format(self, mock_context):
        """Test parsing vulture output format."""
        agent = DeadCodeRemovalAgent(mock_context)

        content = "class OldClass:\n    pass\n"
        issue = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused class 'OldClass' at line 1 (60% confidence)",
            file_path="test.py",
            line_number=1,
        )

        result = agent._parse_dead_code_issue_enhanced(issue, content)
        assert result is not None
        assert result.code_type == "class"

    def test_find_block_end_by_indent(self, mock_context):
        """Test finding block end using indentation."""
        agent = DeadCodeRemovalAgent(mock_context)

        lines = [
            "def func():",
            "    x = 1",
            "    y = 2",
            "    return x + y",
            "",
            "def other():",
            "    pass",
        ]

        end = agent._find_block_end_by_indent(lines, 1)
        # Returns index of first line at base indent (empty lines skipped)
        assert end == 5  # "def other():" is at base indent

    def test_analyze_usage_dynamic_patterns(self, mock_context):
        """Test detecting dynamic usage patterns."""
        agent = DeadCodeRemovalAgent(mock_context)

        content = """
def old_func():
    pass

# Dynamic usage
result = getattr(obj, 'old_func')
"""
        dead_code = DeadCodeInfo(
            code_type="function",
            name="old_func",
            line_number=2,
            confidence=0.80,
        )

        usage = agent._analyze_usage(content, dead_code)
        assert usage["has_dynamic_usage"] is True

    def test_analyze_usage_string_references(self, mock_context):
        """Test detecting string references."""
        agent = DeadCodeRemovalAgent(mock_context)

        # Content with multiple string references to the function
        content = '''
def old_func():
    pass

# String references
name = "old_func"
alias = "old_func"
'''
        dead_code = DeadCodeInfo(
            code_type="function",
            name="old_func",
            line_number=2,
            confidence=0.80,
        )

        usage = agent._analyze_usage(content, dead_code)
        # Should detect at least 1 string reference (subtracts 1 for definition)
        # With 2 explicit string references, we get 2 - 1 = 1
        assert usage["string_references"] >= 1

    def test_protected_decorator_detection(self, mock_context):
        """Test that protected decorators are detected."""
        agent = DeadCodeRemovalAgent(mock_context)

        content = """
@pytest.fixture
def my_fixture():
    return {}
"""
        dead_code = DeadCodeInfo(
            code_type="function",
            name="my_fixture",
            line_number=3,
            confidence=0.90,
            decorators=["@pytest.fixture"],
        )

        result = agent._perform_safety_checks_enhanced(content, dead_code)
        assert result["safe_to_remove"] is False
        assert any("protected decorator" in r for r in result["reasons"])

    def test_is_test_file_detection(self, mock_context):
        """Test test file detection."""
        agent = DeadCodeRemovalAgent(mock_context)

        assert agent._is_test_file(str(Path("/project/tests/test_foo.py"))) is True
        assert agent._is_test_file(str(Path("/project/test_foo.py"))) is True
        assert agent._is_test_file(str(Path("/project/conftest.py"))) is True
        assert agent._is_test_file(str(Path("/project/foo_test.py"))) is True
        assert agent._is_test_file(str(Path("/project/src/module.py"))) is False

    @pytest.mark.asyncio
    async def test_analyze_and_fix_removes_undefined_exports(self, mock_context, tmp_path):
        """Test undefined __all__ entries are cleaned up instead of bouncing back."""
        file_path = tmp_path / "module.py"
        file_path.write_text('__all__ = ["foo", "bar"]\n\ndef foo():\n    return 1\n')
        mock_context.get_file_content.return_value = file_path.read_text()

        agent = DeadCodeRemovalAgent(mock_context)
        issue = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message='Undefined name "bar" in __all__',
            file_path=str(file_path),
            line_number=1,
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is True
        mock_context.write_file_content.assert_called_once()
        written_path, updated_content = mock_context.write_file_content.call_args[0]
        assert written_path == file_path
        assert '"bar"' not in updated_content
        assert '"foo"' in updated_content


# AgentDelegator Tests
class TestAgentDelegator:
    """Tests for AgentDelegator service."""

    def test_delegator_initialization(self, mock_context):
        """Test delegator initializes correctly."""
        from crackerjack.services.agent_delegator import AgentDelegator

        mock_coordinator = MagicMock()
        mock_coordinator.agents = []

        delegator = AgentDelegator(mock_coordinator)
        assert delegator.coordinator == mock_coordinator

    def test_delegation_stats(self, mock_context):
        """Test DelegationStats dataclass."""
        from crackerjack.services.agent_delegator import DelegationStats

        stats = DelegationStats()
        assert stats.total_delegations == 0
        assert stats.successful_delegations == 0

        stats.total_delegations = 10
        stats.successful_delegations = 8
        stats.total_latency_ms = 500.0

        assert stats.average_latency_ms == 50.0

    def test_create_cache_key(self, mock_context):
        """Test cache key creation."""
        from crackerjack.services.agent_delegator import AgentDelegator

        mock_coordinator = MagicMock()
        delegator = AgentDelegator(mock_coordinator)

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test error",
            file_path="test.py",
            line_number=10,
        )

        key1 = delegator._create_cache_key("TestAgent", issue, None)
        key2 = delegator._create_cache_key("TestAgent", issue, None)
        key3 = delegator._create_cache_key("OtherAgent", issue, None)

        assert key1 == key2  # Same inputs = same key
        assert key1 != key3  # Different agent = different key

    def test_get_delegation_metrics(self, mock_context):
        """Test getting delegation metrics."""
        from crackerjack.services.agent_delegator import AgentDelegator

        mock_coordinator = MagicMock()
        delegator = AgentDelegator(mock_coordinator)

        # Record some delegations
        delegator._record_delegation("TestAgent", success=True, latency_ms=100.0)
        delegator._record_delegation("TestAgent", success=False, latency_ms=50.0)

        metrics = delegator.get_delegation_metrics()
        assert metrics["total_delegations"] == 2
        assert metrics["successful_delegations"] == 1
        assert metrics["failed_delegations"] == 1
        assert "TestAgent" in metrics["agents_used"]


# PlanningAgent Delegation Tests
class TestPlanningAgentDelegation:
    """Tests for PlanningAgent delegation support."""

    def test_planning_agent_accepts_delegator(self):
        """Test PlanningAgent accepts optional delegator."""
        from crackerjack.agents.planning_agent import PlanningAgent

        # Without delegator
        agent1 = PlanningAgent("/tmp/test")
        assert agent1.delegator is None

        # With delegator
        mock_delegator = MagicMock()
        agent2 = PlanningAgent("/tmp/test", delegator=mock_delegator)
        assert agent2.delegator == mock_delegator

    def test_try_delegator_fix_without_delegator(self):
        """Test _try_delegator_fix returns None without delegator."""
        from crackerjack.agents.planning_agent import PlanningAgent

        agent = PlanningAgent("/tmp/test")
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test",
            file_path="test.py",
            line_number=1,
        )

        result = agent._try_delegator_fix(issue, {})
        assert result is None

    def test_furb_try_except_to_suppress_splits_exception_types(self):
        """Test FURB107 conversion keeps suppress arguments valid."""
        from crackerjack.agents.planning_agent import PlanningAgent
        from crackerjack.models.fix_plan import ChangeSpec

        agent = PlanningAgent("/tmp/test")
        lines = [
            "try:",
            "    do_something()",
            "except OSError, FileNotFoundError: pass",
        ]

        result = agent._furb_try_except_to_suppress(lines, 1, "FURB107")

        assert isinstance(result, ChangeSpec)
        assert "with suppress(OSError, FileNotFoundError):" in result.new_code
        assert "with suppress((OSError, FileNotFoundError))" not in result.new_code

    def test_fix_arg_type_error_wraps_path_call_safely(self):
        """Test Path -> str conversion only wraps the Path call itself."""
        from crackerjack.agents.planning_agent import PlanningAgent
        from crackerjack.models.fix_plan import ChangeSpec

        agent = PlanningAgent("/tmp/test")
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Argument 1 to `open` has incompatible type `Path`; expected `str`",
            file_path="test.py",
            line_number=1,
        )

        change = agent._fix_arg_type_error(
            issue,
            "repository_path=Path(repo_path_str)",
            {},
        )

        assert isinstance(change, ChangeSpec)
        assert change.new_code == "repository_path=str(Path(repo_path_str))"
        assert "str(repository_path)" not in change.new_code

    def test_fix_arg_type_error_flattens_suppress_tuple(self):
        """Test suppress(tuple(...)) is normalized to suppress(...)."""
        from crackerjack.agents.planning_agent import PlanningAgent
        from crackerjack.models.fix_plan import ChangeSpec

        agent = PlanningAgent("/tmp/test")
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Argument 1 to "suppress" has incompatible type',
            file_path="test.py",
            line_number=1,
        )

        change = agent._fix_arg_type_error(
            issue,
            "with suppress((OSError, FileNotFoundError)):",
            {},
        )

        assert isinstance(change, ChangeSpec)
        assert change.new_code == "with suppress(OSError, FileNotFoundError):"
        assert "suppress((" not in change.new_code

    def test_validate_change_spec_accepts_fragment_block_headers(self):
        """Test fragment validation accepts block headers used in line edits."""
        from crackerjack.agents.planning_agent import PlanningAgent
        from crackerjack.models.fix_plan import ChangeSpec

        agent = PlanningAgent("/tmp/test")
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="with suppress((OSError, FileNotFoundError)):",
            new_code="with suppress(OSError, FileNotFoundError):",
            reason="[arg-type] Flattened suppress() exception tuple",
        )

        validated = agent._validate_change_spec(change)

        assert isinstance(validated, ChangeSpec)
        assert validated.new_code == "with suppress(OSError, FileNotFoundError):"

    def test_validate_change_spec_rejects_broken_fragment(self):
        """Test malformed fragments are still rejected."""
        from crackerjack.agents.planning_agent import PlanningAgent
        from crackerjack.models.fix_plan import ChangeSpec

        agent = PlanningAgent("/tmp/test")
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="with suppress((OSError, FileNotFoundError)):",
            new_code="with suppress((OSError, FileNotFoundError):",
            reason="[arg-type] Broken suppress() change",
        )

        validated = agent._validate_change_spec(change)

        assert validated is None

    def test_validate_change_spec_accepts_comment_only_fragment_edits(self):
        """Test line-level comment edits on incomplete fragments are allowed."""
        from crackerjack.agents.planning_agent import PlanningAgent
        from crackerjack.models.fix_plan import ChangeSpec

        agent = PlanningAgent("/tmp/test")
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="base_url: str = Field(",
            new_code="base_url: str = Field(  # type: ignore[call-overload]",
            reason="[call-overload] Add ignore comment",
        )

        validated = agent._validate_change_spec(change)

        assert isinstance(validated, ChangeSpec)
        assert validated.new_code.endswith("# type: ignore[call-overload]")

    def test_fix_attr_defined_error_converts_path_startswith(self):
        """Test Path.startswith is rewritten instead of ignored."""
        from crackerjack.agents.planning_agent import PlanningAgent
        from crackerjack.models.fix_plan import ChangeSpec

        agent = PlanningAgent("/tmp/test")
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='"Path" has no attribute "startswith"  [attr-defined]',
            file_path="test.py",
            line_number=1,
        )

        change = agent._fix_attr_defined_error(
            issue,
            "if path.is_absolute() and not path.startswith(str(base_resolved)):",
            {},
        )

        assert isinstance(change, ChangeSpec)
        assert "str(path).startswith" in change.new_code
        assert "# type: ignore[attr-defined]" not in change.new_code

    @pytest.mark.asyncio
    async def test_ast_engine_accepts_register_wrapper_lift(self):
        """Test PlanningAgent AST engine accepts wrapper lift refactors."""
        from crackerjack.agents.context_agent import ContextAgent
        from crackerjack.agents.planning_agent import _get_ast_engine

        path = Path(
            "/Users/les/Projects/session-buddy/session_buddy/mcp/tools/code_analysis/tools.py"
        )
        issue = Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="C901 register_code_analysis_tools is too complex (20 > 15)",
            file_path=str(path),
            line_number=18,
        )
        context = await ContextAgent("/Users/les/Projects/session-buddy").extract_context(
            issue
        )

        engine = _get_ast_engine()
        result = await engine.transform(
            context["file_content"],
            path,
            line_start=issue.line_number or 1,
            line_end=issue.line_number or 1,
        )

        assert result is not None
        assert result.pattern_name == "extract_method"
        assert "def register_code_analysis_tools(" in result.transformed_content
        assert "def _code_ingest_file_impl(" in result.transformed_content
        assert "def _code_ingest_directory_impl(" in result.transformed_content
        assert "mcp.tool()(_code_ingest_file_impl)" in result.transformed_content
        assert "mcp.tool()(_code_ingest_directory_impl)" in result.transformed_content

    @pytest.mark.asyncio
    async def test_create_fix_plan_uses_debugger_for_unable_to_auto_fix(self):
        """Test planning failures are routed through the debug channel."""
        from crackerjack.agents.planning_agent import PlanningAgent

        mock_debugger = MagicMock()
        mock_debugger.enabled = True
        mock_debugger.log_agent_activity = MagicMock()

        agent = PlanningAgent("/tmp/test", debugger=mock_debugger)
        agent._dispatch_fix = MagicMock(return_value=None)

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Name "missing_value" is not defined  [name-defined]',
            file_path="/tmp/test/demo.py",
            line_number=7,
        )

        plan = await agent.create_fix_plan(issue, {"file_content": "value = 1\n"}, [])

        assert plan.changes == []
        mock_debugger.log_agent_activity.assert_called_once()
        call_kwargs = mock_debugger.log_agent_activity.call_args.kwargs
        assert call_kwargs["agent_name"] == "PlanningAgent"
        assert call_kwargs["activity"] == "unable_to_auto_fix"
        assert call_kwargs["issue_id"] == issue.id
        assert call_kwargs["metadata"]["issue_type"] == issue.type.value

    def test_dispatch_fix_strips_cautious_suffix_for_complexity(self):
        """Test cautious complexity approaches reuse the real refactor handler."""
        from crackerjack.agents.planning_agent import PlanningAgent

        agent = PlanningAgent("/tmp/test")
        agent._refactor_for_clarity = MagicMock(return_value="refactor-result")

        issue = Issue(
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="C901 demo is too complex (20 > 15)",
            file_path="/tmp/test/demo.py",
            line_number=7,
        )

        result = agent._dispatch_fix(
            "refactor_for_clarity_cautious",
            issue,
            "def demo():\n    return True\n",
        )

        assert result == "refactor-result"
        agent._refactor_for_clarity.assert_called_once()

    def test_fix_name_defined_error_adds_suppress_import(self):
        """Test missing suppress import is added for name-defined errors."""
        from crackerjack.agents.planning_agent import PlanningAgent

        agent = PlanningAgent("/tmp/test")
        content = (
            "from pathlib import Path\n\n"
            "def demo():\n"
            "    with suppress(OSError):\n"
            "        pass\n"
        )
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Name "suppress" is not defined  [name-defined]',
            file_path="/tmp/test/demo.py",
            line_number=4,
        )

        change = agent._fix_name_defined_error(issue, "with suppress(OSError):", {"file_content": content})

        assert change is not None
        assert change.line_range[0] == 1
        assert "from contextlib import suppress" in change.new_code

    def test_fix_name_defined_error_adds_operator_import(self):
        """Test missing operator import is added for name-defined errors."""
        from crackerjack.agents.planning_agent import PlanningAgent

        agent = PlanningAgent("/tmp/test")
        content = (
            "from pathlib import Path\n\n"
            "values = [1, 2, 3]\n"
            "key_fn = operator.itemgetter(0)\n"
        )
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Name "operator" is not defined  [name-defined]',
            file_path="/tmp/test/demo.py",
            line_number=4,
        )

        change = agent._fix_name_defined_error(issue, "key_fn = operator.itemgetter(0)", {"file_content": content})

        assert change is not None
        assert change.line_range[0] == 1
        assert "import operator" in change.new_code

    def test_apply_refurb_fix_adds_suppress_import_when_missing(self):
        """Test FURB107 inserts suppress import when needed."""
        from crackerjack.agents.planning_agent import PlanningAgent

        agent = PlanningAgent("/tmp/test")
        content = (
            "from pathlib import Path\n\n"
            "def demo():\n"
            "    try:\n"
            "        risky()\n"
            "    except OSError, FileNotFoundError: pass\n"
        )
        issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.LOW,
            message="FURB107: try/except can use suppress",
            file_path="/tmp/test/demo.py",
            line_number=6,
        )

        change = agent._apply_refurb_fix(issue, content)

        assert change is not None
        assert change.line_range[0] == 1
        assert "from contextlib import suppress" in change.new_code
        assert "with suppress(OSError, FileNotFoundError):" in change.new_code

    def test_apply_refurb_fix_adds_operator_import_when_missing(self):
        """Test FURB118 inserts operator import when needed."""
        from crackerjack.agents.planning_agent import PlanningAgent

        agent = PlanningAgent("/tmp/test")
        content = (
            "from pathlib import Path\n\n"
            "items = [1, 2, 3]\n"
            "key_fn = lambda x: x[0]\n"
        )
        issue = Issue(
            type=IssueType.REFURB,
            severity=Priority.LOW,
            message="FURB118: replace lambda with itemgetter",
            file_path="/tmp/test/demo.py",
            line_number=4,
        )

        change = agent._apply_refurb_fix(issue, content)

        assert change is not None
        assert change.line_range[0] == 1
        assert "import operator" in change.new_code
        assert "operator.itemgetter(0)" in change.new_code


# Integration Tests
class TestAgentIntegration:
    """Integration tests for agent interactions."""

    @pytest.mark.asyncio
    async def test_refurb_agent_analyze_and_fix(self, mock_context, refurb_issue):
        """Test RefurbCodeTransformerAgent analyze_and_fix method."""
        mock_context.get_file_content.return_value = """
def foo(x):
    if x:
        return True
    return False
"""
        agent = RefurbCodeTransformerAgent(mock_context)
        result = await agent.analyze_and_fix(refurb_issue)

        assert isinstance(result, FixResult)
        assert result.confidence >= 0.0

    @pytest.mark.asyncio
    async def test_type_error_agent_analyze_and_fix(
        self, mock_context, type_error_issue
    ):
        """Test TypeErrorSpecialistAgent analyze_and_fix method."""
        mock_context.get_file_content.return_value = """
def foo(x):
    return x + 1
"""
        agent = TypeErrorSpecialistAgent(mock_context)
        result = await agent.analyze_and_fix(type_error_issue)

        assert isinstance(result, FixResult)

    @pytest.mark.asyncio
    async def test_dead_code_agent_rejects_test_files(
        self, mock_context, dead_code_issue
    ):
        """Test DeadCodeRemovalAgent rejects test files."""
        dead_code_issue.file_path = "/tmp/test_project/tests/test_foo.py"
        agent = DeadCodeRemovalAgent(mock_context)
        result = await agent.analyze_and_fix(dead_code_issue)

        assert not result.success  # Falsy check
        assert any("test file" in r.lower() for r in result.remaining_issues)


# Edge Case Tests
class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_file_handling(self, mock_context):
        """Test agents handle empty files gracefully."""
        mock_context.get_file_content.return_value = ""

        agent = TypeErrorSpecialistAgent(mock_context)
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Error",
            file_path="empty.py",
            line_number=1,
        )

        # Should not crash
        new_content, fixes = agent._fix_missing_return_types("", issue)
        assert isinstance(new_content, str)

    def test_malformed_issue_handling(self, mock_context):
        """Test agents handle malformed issues gracefully."""
        agent = DeadCodeRemovalAgent(mock_context)

        # Issue with no file path
        issue = Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused code",
            file_path=None,
            line_number=None,
        )

        result = asyncio.run(agent.analyze_and_fix(issue))
        assert not result.success  # Falsy check

    def test_syntax_error_in_file(self, mock_context):
        """Test agents handle files with syntax errors."""
        agent = TypeErrorSpecialistAgent(mock_context)

        # Invalid Python code
        bad_code = "def foo(:\n    pass"

        # Should not crash when trying to parse
        try:
            compile(bad_code, "test.py", "exec")
        except SyntaxError:
            pass  # Expected

        # Agent should handle gracefully
        new_content, fixes = agent._infer_and_add_return_types(
            bad_code,
            Issue(
                type=IssueType.TYPE_ERROR,
                severity=Priority.MEDIUM,
                message="Error",
                file_path="test.py",
                line_number=1,
            ),
        )
        assert isinstance(new_content, str)


# PyCharmMCPAdapter Tests
class TestPyCharmMCPAdapter:
    """Tests for PyCharmMCPAdapter service."""

    def test_adapter_initialization(self):
        """Test adapter initializes correctly."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()
        assert adapter._timeout == 30.0
        assert adapter._max_results == 100

    def test_adapter_with_custom_settings(self):
        """Test adapter with custom settings."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter(timeout=60.0, max_results=50)
        assert adapter._timeout == 60.0
        assert adapter._max_results == 50

    def test_circuit_breaker_state(self):
        """Test CircuitBreakerState dataclass."""
        from crackerjack.services.pycharm_mcp_integration import (
            CircuitBreakerState,
        )

        cb = CircuitBreakerState()
        assert cb.failure_count == 0
        assert cb.is_open is False
        assert cb.can_execute() is True

        # Record failures to open circuit
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.is_open is True
        assert cb.can_execute() is False  # Circuit is open

        # Record success to close circuit
        cb.record_success()
        assert cb.is_open is False
        assert cb.failure_count == 0

    def test_sanitize_regex_valid(self):
        """Test sanitizing valid regex patterns."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Valid patterns
        assert adapter._sanitize_regex(r"# type: ignore") == r"# type: ignore"
        assert adapter._sanitize_regex(r"def\s+\w+") == r"def\s+\w+"
        assert adapter._sanitize_regex(r"TODO|FIXME") == r"TODO|FIXME"

    def test_sanitize_regex_invalid(self):
        """Test sanitizing invalid regex patterns."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Invalid patterns
        assert adapter._sanitize_regex("[invalid") == ""  # Unclosed bracket
        assert adapter._sanitize_regex("") == ""  # Empty is valid but returns empty
        assert adapter._sanitize_regex("x" * 600) == ""  # Too long

    def test_sanitize_regex_dangerous(self):
        """Test sanitizing dangerous ReDoS patterns."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Dangerous ReDoS patterns
        assert adapter._sanitize_regex(r"(.*)+") == ""
        assert adapter._sanitize_regex(r"(.+)+") == ""
        assert adapter._sanitize_regex(r"(.*)*") == ""

    def test_is_safe_path(self):
        """Test path safety validation."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Safe paths
        assert adapter._is_safe_path("src/module.py") is True
        assert adapter._is_safe_path("test_file.py") is True
        assert adapter._is_safe_path("/tmp/test.py") is True

        # Unsafe paths
        assert adapter._is_safe_path("../../../etc/passwd") is False  # Path traversal
        assert adapter._is_safe_path("") is False  # Empty
        assert adapter._is_safe_path("/etc/passwd") is False  # Outside project
        assert adapter._is_safe_path("file\x00.py") is False  # Null byte

    def test_search_result_dataclass(self):
        """Test SearchResult dataclass."""
        from crackerjack.services.pycharm_mcp_integration import SearchResult

        result = SearchResult(
            file_path="test.py",
            line_number=10,
            column=5,
            match_text="# type: ignore",
            context_before="def foo():",
            context_after="    pass",
        )
        assert result.file_path == "test.py"
        assert result.line_number == 10
        assert result.match_text == "# type: ignore"

    @pytest.mark.asyncio
    async def test_search_regex_no_mcp(self):
        """Test search when MCP is not available (uses fallback)."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter(mcp_client=None)

        # Should use fallback grep search
        results = await adapter.search_regex(r"def\s+\w+", file_pattern="*.py")
        # Results depend on current directory content
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_replace_text_unsafe_path(self):
        """Test replace rejects unsafe paths."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter(mcp_client=None)

        # Should reject path traversal
        result = await adapter.replace_text_in_file(
            "../../../etc/passwd",
            "old",
            "new",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_get_file_problems_unsafe_path(self):
        """Test get_file_problems rejects unsafe paths."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter(mcp_client=None)

        # Should reject path traversal
        problems = await adapter.get_file_problems("../../../etc/passwd")
        assert problems == []

    def test_cache_operations(self):
        """Test caching functionality."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Set and get cached
        adapter._set_cached("test_key", {"data": "value"}, ttl=60.0)
        result = adapter._get_cached("test_key")
        assert result == {"data": "value"}

        # Clear cache
        adapter.clear_cache()
        assert adapter._get_cached("test_key") is None

    def test_cache_expiry(self):
        """Test cache expiry."""
        import time

        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter()

        # Set with very short TTL
        adapter._set_cached("test_key", "value", ttl=0.01)
        time.sleep(0.02)

        # Should be expired
        result = adapter._get_cached("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check functionality."""
        from crackerjack.services.pycharm_mcp_integration import PyCharmMCPAdapter

        adapter = PyCharmMCPAdapter(mcp_client=None)
        health = await adapter.health_check()

        assert "mcp_available" in health
        assert "circuit_breaker_open" in health
        assert "failure_count" in health
        assert "cache_size" in health
        assert health["mcp_available"] is False


# Export Tests Summary
TEST_SUMMARY = """
Test Coverage Summary:
- RefurbCodeTransformerAgent: 4 tests
- TypeErrorSpecialistAgent: 8 tests
- DeadCodeRemovalAgent: 11 tests
- AgentDelegator: 4 tests
- PlanningAgent Delegation: 2 tests
- Integration Tests: 3 tests
- Edge Cases: 3 tests
- PyCharmMCPAdapter: 12 tests

Total: 47 tests covering all new features
"""

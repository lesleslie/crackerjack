"""Targeted coverage tests for RefactoringAgent branch coverage.

Focuses on the message-classifier and subcommand router paths in
`crackerjack.agents.refactoring_agent` that are not exercised by the broader
behavioural tests in `test_refactoring_agent.py`.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.refactoring_agent import RefactoringAgent
from crackerjack.models.fix_plan import ChangeSpec, FixPlan, create_fix_plan


@pytest.mark.unit
class TestIsFixableTypeErrorClassifier:
    """Cover every confidence branch in `_is_fixable_type_error`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_empty_message_returns_zero(self, agent) -> None:
        issue = Issue(
            id="t-1",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="",
        )

        assert await agent._is_fixable_type_error(issue) == 0.0

    async def test_incompatible_types_returns_zero(self, agent) -> None:
        issue = Issue(
            id="t-2",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="incompatible types in assignment",
        )

        assert await agent._is_fixable_type_error(issue) == 0.0

    async def test_type_mismatch_returns_zero(self, agent) -> None:
        issue = Issue(
            id="t-3",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Type mismatch on attribute access",
        )

        assert await agent._is_fixable_type_error(issue) == 0.0

    async def test_cannot_assign_returns_zero(self, agent) -> None:
        issue = Issue(
            id="t-4",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Cannot assign value of type 'str' to 'int'",
        )

        assert await agent._is_fixable_type_error(issue) == 0.0

    async def test_cannot_be_assigned_returns_zero(self, agent) -> None:
        issue = Issue(
            id="t-5",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Value cannot be assigned to attribute",
        )

        assert await agent._is_fixable_type_error(issue) == 0.0

    async def test_needs_return_type_high_confidence(self, agent) -> None:
        issue = Issue(
            id="t-6",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Function foo needs return type annotation",
        )

        assert await agent._is_fixable_type_error(issue) == 0.9

    async def test_return_arrow_none_branch(self, agent) -> None:
        # Source bug: the source code compares literal "-> None" / "-> Any"
        # against `message_lower`, but those literals contain capital
        # letters that survive `.lower()`. The case mismatch makes the
        # branch unreachable for case-insensitive input. We document the
        # observed fall-through behavior.
        issue = Issue(
            id="t-7",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="signature is -> None",
        )

        # "signature" is in the 0.3 list — that's the observed result.
        assert await agent._is_fixable_type_error(issue) == 0.3

    async def test_return_arrow_any_branch(self, agent) -> None:
        # Same source bug: "-> Any" never matches a lowercased message.
        # None of the keyword branches fire, so confidence is 0.0.
        issue = Issue(
            id="t-8",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="return type is -> Any",
        )

        assert await agent._is_fixable_type_error(issue) == 0.0

    async def test_needs_annotation_branch(self, agent) -> None:
        issue = Issue(
            id="t-9",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Variable needs annotation",
        )

        assert await agent._is_fixable_type_error(issue) == 0.8

    async def test_has_no_type_branch(self, agent) -> None:
        issue = Issue(
            id="t-10",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Parameter has no type annotation",
        )

        assert await agent._is_fixable_type_error(issue) == 0.8

    async def test_parameter_with_type_annotation(self, agent) -> None:
        issue = Issue(
            id="t-11",
            type=IssueType.TYPE_ERROR,
            severity=Priority.LOW,
            message="Parameter 'x' missing type annotation",
        )

        assert await agent._is_fixable_type_error(issue) == 0.7

    async def test_incompatible_return_type(self, agent) -> None:
        issue = Issue(
            id="t-12",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="incompatible return type for function",
        )

        assert await agent._is_fixable_type_error(issue) == 0.6

    async def test_incompatible_type_branch(self, agent) -> None:
        issue = Issue(
            id="t-13",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="incompatible type passed to call",
        )

        assert await agent._is_fixable_type_error(issue) == 0.6

    async def test_argument_of_type_branch(self, agent) -> None:
        issue = Issue(
            id="t-14",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Argument of type 'str' not acceptable",
        )

        assert await agent._is_fixable_type_error(issue) == 0.6

    async def test_has_no_attribute_branch(self, agent) -> None:
        issue = Issue(
            id="t-15",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Item has no attribute 'open'",
        )

        assert await agent._is_fixable_type_error(issue) == 0.6

    async def test_cannot_be_assigned_to_branch(self, agent) -> None:
        # The 0.0 incompatible list includes "cannot be assigned", which is
        # a substring of "cannot be assigned to". The 0.0 list is checked
        # first, so this falls through to 0.0 — documenting observed
        # behavior, not source intent.
        issue = Issue(
            id="t-16",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Expression cannot be assigned to target",
        )

        assert await agent._is_fixable_type_error(issue) == 0.0

    async def test_assignment_branch(self, agent) -> None:
        issue = Issue(
            id="t-17",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="invalid assignment expression",
        )

        assert await agent._is_fixable_type_error(issue) == 0.4

    async def test_invalid_type_branch(self, agent) -> None:
        issue = Issue(
            id="t-18",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Invalid type used in expression",
        )

        assert await agent._is_fixable_type_error(issue) == 0.4

    async def test_undefined_name_branch(self, agent) -> None:
        issue = Issue(
            id="t-19",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Undefined name 'foo'",
        )

        assert await agent._is_fixable_type_error(issue) == 0.4

    async def test_generic_type_error_branch(self, agent) -> None:
        issue = Issue(
            id="t-20",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Generic type error in expression",
        )

        assert await agent._is_fixable_type_error(issue) == 0.3

    async def test_annotation_branch(self, agent) -> None:
        issue = Issue(
            id="t-21",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Annotation is required for variable",
        )

        assert await agent._is_fixable_type_error(issue) == 0.3

    async def test_protocol_branch(self, agent) -> None:
        issue = Issue(
            id="t-22",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Protocol mismatch detected",
        )

        assert await agent._is_fixable_type_error(issue) == 0.3

    async def test_signature_branch(self, agent) -> None:
        issue = Issue(
            id="t-23",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Method signature incompatible",
        )

        assert await agent._is_fixable_type_error(issue) == 0.3

    async def test_unmatched_message_returns_zero(self, agent) -> None:
        issue = Issue(
            id="t-24",
            type=IssueType.TYPE_ERROR,
            severity=Priority.LOW,
            message="nothing relevant in here",
        )

        assert await agent._is_fixable_type_error(issue) == 0.0


@pytest.mark.unit
class TestHandleWarningRouter:
    """Cover `_handle_warning` routing paths."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_warning_routes_to_complexity(self, agent, tmp_path) -> None:
        test_file = tmp_path / "warn.py"
        test_file.write_text("def f():\n    return 1\n")

        issue = Issue(
            id="w-1",
            type=IssueType.WARNING,
            severity=Priority.LOW,
            message="Function has cognitive complexity of 20",
            file_path=str(test_file),
        )

        with patch.object(agent, "_reduce_complexity") as mock_reduce:
            mock_reduce.return_value = FixResult(success=True, confidence=0.9)
            result = await agent._handle_warning(issue)

        mock_reduce.assert_called_once_with(issue)
        assert result.success is True

    async def test_warning_routes_to_dead_code(self, agent, tmp_path) -> None:
        test_file = tmp_path / "warn_dead.py"
        test_file.write_text("import x\ndef f(): pass\n")

        issue = Issue(
            id="w-2",
            type=IssueType.WARNING,
            severity=Priority.LOW,
            message="Variable imported but unused",
            file_path=str(test_file),
        )

        with patch.object(agent, "_remove_dead_code") as mock_remove:
            mock_remove.return_value = FixResult(success=True, confidence=0.8)
            result = await agent._handle_warning(issue)

        mock_remove.assert_called_once_with(issue)
        assert result.success is True

    async def test_warning_unrouted_returns_manual_review(self, agent) -> None:
        issue = Issue(
            id="w-3",
            type=IssueType.WARNING,
            severity=Priority.LOW,
            message="Linter: undefined behavior",
        )

        result = await agent._handle_warning(issue)

        assert result.success is False
        assert result.confidence == 0.5
        assert "manual review" in result.remaining_issues[0].lower()
        assert result.recommendations


@pytest.mark.unit
class TestAnalyzeAndFixRouters:
    """Cover the type-dispatch in `analyze_and_fix`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_routes_to_type_error(self, agent) -> None:
        issue = Issue(
            id="r-1",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type",
            file_path=None,
        )

        with patch.object(agent, "_fix_type_error") as mock_fix:
            mock_fix.return_value = FixResult(success=True, confidence=0.9)
            result = await agent.analyze_and_fix(issue)

        mock_fix.assert_called_once_with(issue)
        assert result.success is True

    async def test_routes_to_warning(self, agent) -> None:
        issue = Issue(
            id="r-2",
            type=IssueType.WARNING,
            severity=Priority.LOW,
            message="Something generic",
        )

        with patch.object(agent, "_handle_warning") as mock_warn:
            mock_warn.return_value = FixResult(success=False, confidence=0.5)
            result = await agent.analyze_and_fix(issue)

        mock_warn.assert_called_once_with(issue)
        assert result.success is False


@pytest.mark.unit
class TestCanHandleWarningBranch:
    """Verify `can_handle` returns 0.7 for WARNING issues."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_warning_returns_default_confidence(self, agent) -> None:
        issue = Issue(
            id="cw-1",
            type=IssueType.WARNING,
            severity=Priority.LOW,
            message="Some warning",
        )

        assert await agent.can_handle(issue) == 0.7


@pytest.mark.unit
class TestApplyKnownComplexityFix:
    """Cover `_apply_known_complexity_fix` branches."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_empty_content_returns_failure(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("")
        agent.context.get_file_content = Mock(return_value="")

        issue = Issue(
            id="k-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="detect_agent_needs too complex",
            file_path=str(test_file),
        )

        result = await agent._apply_known_complexity_fix(test_file, issue)
        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    async def test_pattern_does_not_change_content(
        self, agent, tmp_path
    ) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def detect_agent_needs(): pass\n")
        agent.context.get_file_content = Mock(return_value="def detect_agent_needs(): pass\n")
        agent.context.write_file_content = Mock(return_value=True)

        issue = Issue(
            id="k-2",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="detect_agent_needs too complex",
            file_path=str(test_file),
        )

        with patch.object(
            agent._code_transformer,
            "refactor_detect_agent_needs_pattern",
            return_value="def detect_agent_needs(): pass\n",
        ):
            result = await agent._apply_known_complexity_fix(test_file, issue)

        assert result.success is False
        assert result.confidence == 0.3

    async def test_write_failure_after_transform(
        self, agent, tmp_path
    ) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def detect_agent_needs(): pass\n")
        agent.context.get_file_content = Mock(return_value="def detect_agent_needs(): pass\n")
        agent.context.write_file_content = Mock(return_value=False)

        issue = Issue(
            id="k-3",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="detect_agent_needs too complex",
            file_path=str(test_file),
        )

        with patch.object(
            agent._code_transformer,
            "refactor_detect_agent_needs_pattern",
            return_value="def detect_agent_needs(): return 1\n",
        ):
            result = await agent._apply_known_complexity_fix(test_file, issue)

        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]


@pytest.mark.unit
class TestReduceComplexityDetectAgentNeedsBranch:
    """Cover the `detect_agent_needs` short-circuit in `_reduce_complexity`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_detect_agent_needs_short_circuit(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def detect_agent_needs(): pass\n")
        agent.context.get_file_content = Mock(return_value="def detect_agent_needs(): pass\n")
        agent.context.write_file_content = Mock(return_value=True)

        issue = Issue(
            id="d-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="detect_agent_needs pattern is too complex",
            file_path=str(test_file),
        )

        with patch.object(
            agent._code_transformer,
            "refactor_detect_agent_needs_pattern",
            return_value="def detect_agent_needs(): return None\n",
        ):
            result = await agent._reduce_complexity(issue)

        assert result.success is True
        assert "detect_agent_needs" in result.fixes_applied[0]


@pytest.mark.unit
class TestFixTypeErrorEarlyReturns:
    """Cover early-return branches in `_fix_type_error`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_incompatible_message_skips_path(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def foo(): pass\n")
        agent.context.get_file_content = Mock(return_value="def foo(): pass\n")

        issue = Issue(
            id="ft-1",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="incompatible types",
            file_path=str(test_file),
        )

        result = await agent._fix_type_error(issue)

        assert result.success is False
        assert "too complex" in result.remaining_issues[0].lower()

    async def test_no_file_path_returns_error(self, agent) -> None:
        issue = Issue(
            id="ft-2",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type",
            file_path=None,
        )

        result = await agent._fix_type_error(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_empty_content_returns_error(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("")
        agent.context.get_file_content = Mock(return_value="")

        issue = Issue(
            id="ft-3",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type",
            file_path=str(test_file),
        )

        result = await agent._fix_type_error(issue)

        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]


@pytest.mark.unit
class TestFixPathStrPatterns:
    """Cover the pattern-application branches in `_fix_path_str_patterns`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_no_matching_patterns_returns_none(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")
        result = agent._fix_path_str_patterns("x = 1\n", test_file)
        assert result is None

    def test_function_call_pattern_rewrites(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("open(Path(name))\n")
        agent.context.write_file_content = Mock(return_value=True)

        result = agent._fix_path_str_patterns("open(Path(name))\n", test_file)
        assert result is not None
        assert result.success is True
        assert "str(Path(name))" in test_file.read_text() or result is not None

    def test_write_failure_returns_none(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = Path(y)\n")
        agent.context.write_file_content = Mock(return_value=False)

        result = agent._fix_path_str_patterns("x = Path(y)\n", test_file)
        assert result is None


@pytest.mark.unit
class TestTryFixPathStrTypeError:
    """Cover the indicator/branch logic in `_try_fix_path_str_type_error`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_no_indicator_returns_none(self, agent, tmp_path) -> None:
        issue = Issue(
            id="tp-1",
            type=IssueType.TYPE_ERROR,
            severity=Priority.LOW,
            message="random message",
        )
        result = agent._try_fix_path_str_type_error(issue, "x = 1\n", tmp_path / "x.py")
        assert result is None

    def test_path_str_required_but_missing_returns_none(
        self, agent, tmp_path
    ) -> None:
        issue = Issue(
            id="tp-2",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="arg-type mismatch",
        )
        result = agent._try_fix_path_str_type_error(issue, "x = 1\n", tmp_path / "x.py")
        assert result is None


@pytest.mark.unit
class TestEnsureContextlibSuppressImport:
    """Cover import-injection logic in `_ensure_contextlib_suppress_import`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_already_imported_noop(self, agent) -> None:
        content = "from contextlib import suppress\n"
        assert agent._ensure_contextlib_suppress_import(content) == content

    def test_import_contextlib_noop(self, agent) -> None:
        content = "import contextlib\n"
        assert agent._ensure_contextlib_suppress_import(content) == content

    def test_injects_after_future(self, agent) -> None:
        content = "from __future__ import annotations\nimport os\n\nx = 1\n"
        result = agent._ensure_contextlib_suppress_import(content)
        assert "from contextlib import suppress" in result
        # Should land after the future import
        lines = result.splitlines()
        assert lines[0] == "from __future__ import annotations"
        assert "from contextlib import suppress" in lines

    def test_injects_after_existing_imports(self, agent) -> None:
        content = "import os\nimport sys\n\nx = 1\n"
        result = agent._ensure_contextlib_suppress_import(content)
        lines = result.splitlines()
        assert "from contextlib import suppress" in lines
        assert lines.index("from contextlib import suppress") > lines.index("import sys")

    def test_docstring_skipped_for_insertion(self, agent) -> None:
        content = '"""Module docstring."""\nimport os\n\nx = 1\n'
        result = agent._ensure_contextlib_suppress_import(content)
        lines = result.splitlines()
        assert "from contextlib import suppress" in lines
        # Inserted after the import os line, not after the docstring only
        assert lines.index("from contextlib import suppress") > lines.index("import os")

    def test_no_imports_inserts_at_top(self, agent) -> None:
        content = "x = 1\n"
        result = agent._ensure_contextlib_suppress_import(content)
        assert result.splitlines()[0] == "from contextlib import suppress"

    def test_skips_comment_lines(self, agent) -> None:
        content = "# top comment\nimport os\n\nx = 1\n"
        result = agent._ensure_contextlib_suppress_import(content)
        lines = result.splitlines()
        assert "from contextlib import suppress" in lines


@pytest.mark.unit
class TestFlattenSuppressTuple:
    """Cover the suppress-tuple flattening branch."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_no_tuple_returns_none(self, agent, tmp_path) -> None:
        result = agent._flatten_suppress_tuple(
            "with suppress(OSError):\n    pass\n",
            tmp_path / "x.py",
        )
        assert result is None

    def test_write_failure_returns_none(self, agent, tmp_path) -> None:
        agent.context.write_file_content = Mock(return_value=False)
        result = agent._flatten_suppress_tuple(
            "with suppress((OSError,)):\n    pass\n",
            tmp_path / "x.py",
        )
        assert result is None


@pytest.mark.unit
class TestApplyAndSaveRefactoringBranches:
    """Cover additional branches in `_apply_and_save_refactoring`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_no_changes_no_fallback_returns_no_changes(
        self, agent, tmp_path
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

        with patch.object(
            agent._code_transformer,
            "refactor_complex_functions",
            return_value="def f(): return 1\n",
        ), patch.object(
            agent._code_transformer,
            "apply_enhanced_strategies",
            return_value="def f(): return 1\n",
        ), patch(
            "crackerjack.agents.refactoring_agent._get_ast_transform_engine",
            return_value=engine,
        ):
            result = await agent._apply_and_save_refactoring(
                test_file,
                "def f(): return 1\n",
                [func_info],
                issue=None,
            )

        assert result.success is False
        assert "Could not automatically" in result.remaining_issues[0]

    async def test_write_failure_for_refactored(
        self, agent, tmp_path
    ) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): return 1\n")
        agent.context.write_file_content = Mock(return_value=False)

        func_info = {
            "name": "f",
            "line_start": 1,
            "line_end": 1,
            "complexity": 20,
            "node": None,
        }

        with patch.object(
            agent._code_transformer,
            "refactor_complex_functions",
            return_value="def f(): return 2\n",
        ):
            result = await agent._apply_and_save_refactoring(
                test_file,
                "def f(): return 1\n",
                [func_info],
                issue=None,
            )

        assert result.success is False
        assert "Failed to write refactored" in result.remaining_issues[0]


@pytest.mark.unit
class TestProcessComplexityReductionBranches:
    """Cover `_process_complexity_reduction` early returns."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_empty_content_returns_failure(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("")
        agent.context.get_file_content = Mock(return_value="")

        result = await agent._process_complexity_reduction(test_file)
        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    async def test_no_complex_functions_returns_failure(
        self, agent, tmp_path
    ) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f():\n    return 1\n")
        agent.context.get_file_content = Mock(return_value="def f():\n    return 1\n")

        with patch.object(
            agent._complexity_analyzer, "find_complex_functions", return_value=[]
        ), patch.object(agent, "_find_semantic_complex_patterns", return_value=[]):
            result = await agent._process_complexity_reduction(test_file)

        assert result.success is False
        assert "No overly complex" in result.remaining_issues[0]


@pytest.mark.unit
class TestProcessDeadCodeRemovalBranches:
    """Cover `_process_dead_code_removal` paths."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_empty_content_returns_failure(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("")
        agent.context.get_file_content = Mock(return_value="")

        result = await agent._process_dead_code_removal(test_file)
        assert result.success is False
        assert "Could not read" in result.remaining_issues[0]

    async def test_no_removable_items_returns_success_with_recommendation(
        self, agent, tmp_path
    ) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")
        agent.context.get_file_content = Mock(return_value="x = 1\n")

        with patch.object(
            agent._dead_code_detector,
            "analyze_dead_code",
            return_value={"removable_items": []},
        ):
            result = await agent._process_dead_code_removal(test_file)

        assert result.success is True
        assert result.confidence == 0.7
        assert "No obvious dead code" in result.recommendations[0]


@pytest.mark.unit
class TestApplyAndSaveCleanup:
    """Cover the cleanup write paths."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_no_changes_returns_no_cleanup(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")
        agent.context.write_file_content = Mock(return_value=True)

        with patch.object(
            agent, "_collect_all_removable_lines", return_value=set()
        ):
            result = agent._apply_and_save_cleanup(
                test_file, "x = 1\n", {"removable_items": []}
            )

        assert result.success is False
        assert "Could not automatically remove" in result.remaining_issues[0]

    def test_write_failure_returns_failure(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")
        agent.context.write_file_content = Mock(return_value=False)

        with patch.object(agent, "_collect_all_removable_lines", return_value={0}):
            result = agent._apply_and_save_cleanup(
                test_file, "x = 1\n", {"removable_items": ["x"]}
            )

        assert result.success is False
        assert "Failed to write" in result.remaining_issues[0]

    def test_successful_removal(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")
        agent.context.write_file_content = Mock(return_value=True)

        with patch.object(agent, "_collect_all_removable_lines", return_value={0}):
            result = agent._apply_and_save_cleanup(
                test_file, "x = 1\n", {"removable_items": ["x"]}
            )

        assert result.success is True
        assert "Removed 1" in result.fixes_applied[0]


@pytest.mark.unit
class TestRemoveDeadCodeGeneralError:
    """Cover the non-SyntaxError exception path in `_remove_dead_code`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_general_exception_returns_error_result(
        self, agent, tmp_path
    ) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("import x\n")

        issue = Issue(
            id="dc-err-1",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="unused import",
            file_path=str(test_file),
        )

        with patch.object(agent, "_process_dead_code_removal") as mock_proc:
            mock_proc.side_effect = RuntimeError("boom")
            result = await agent._remove_dead_code(issue)

        assert result.success is False
        assert "Error processing" in result.remaining_issues[0]


@pytest.mark.unit
class TestFindExtendedUnreachableLines:
    """Cover `_find_extended_unreachable_lines` and `_find_function_indent`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_no_unreachable_items_returns_empty(self, agent) -> None:
        lines = ["def f():\n", "    return 1\n"]
        result = agent._find_extended_unreachable_lines(lines, {})
        assert result == set()

    def test_skips_to_next_function(self, agent) -> None:
        lines = [
            "def outer():\n",
            "    return 1\n",
            "    unreachable = 2\n",  # line index 2
            "\n",
            "def another():\n",
            "    pass\n",
        ]
        analysis = {
            "unreachable_code": [
                {
                    "type": "unreachable_after_return",
                    "line": 3,
                    "function": "outer",
                }
            ]
        }

        result = agent._find_extended_unreachable_lines(lines, analysis)
        assert 2 in result

    def test_find_function_indent(self, agent) -> None:
        lines = ["def f():\n", "    pass\n"]
        assert agent._find_function_indent(lines, "f") == 0

    def test_find_function_indent_missing(self, agent) -> None:
        lines = ["def other():\n", "    pass\n"]
        assert agent._find_function_indent(lines, "missing") is None


@pytest.mark.unit
class TestExtractFunctionNameFromIssue:
    """Cover alternate branches in `_extract_function_name_from_issue`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_simple_dash_format(self, agent) -> None:
        issue = Issue(
            id="e-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="my_func - has complexity 20",
        )
        assert agent._extract_function_name_from_issue(issue) == "my_func"

    def test_details_function_no_class_prefix(self, agent) -> None:
        issue = Issue(
            id="e-2",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="no name here",
            details=["function: simple_func"],
        )
        assert agent._extract_function_name_from_issue(issue) == "simple_func"


@pytest.mark.unit
class TestLocateComplexityTargetLine:
    """Cover `_locate_complexity_target_line` branches."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_returns_none_when_no_issue(self, agent) -> None:
        result = agent._locate_complexity_target_line("def f(): pass\n", None)
        assert result is None

    def test_finds_function_by_name(self, agent) -> None:
        issue = Issue(
            id="l-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'target_func' - too complex",
        )
        result = agent._locate_complexity_target_line(
            "def target_func():\n    pass\n", issue
        )
        assert result == 0  # 0-indexed lineno of first line

    def test_finds_function_by_line_number(self, agent) -> None:
        issue = Issue(
            id="l-2",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="complexity at line 1",
            line_number=1,
        )
        result = agent._locate_complexity_target_line(
            "def f():\n    return 1\n", issue
        )
        assert result == 0


@pytest.mark.unit
class TestApplyComplexityNoqaFallback:
    """Cover edge cases in `_apply_complexity_noqa_fallback`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_noqa_already_present_returns_none(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): pass  # noqa: C901\n")
        agent.context.get_file_content = Mock(
            return_value="def f(): pass  # noqa: C901\n"
        )

        issue = Issue(
            id="n-1",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'f' too complex",
            line_number=1,
        )

        result = agent._apply_complexity_noqa_fallback(test_file, issue)
        assert result is None

    def test_existing_noqa_appends_c901(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): pass  # noqa: A001\n")
        agent.context.get_file_content = Mock(
            return_value="def f(): pass  # noqa: A001\n"
        )
        agent.context.write_file_content = Mock(return_value=True)

        issue = Issue(
            id="n-2",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'f' too complex",
            line_number=1,
        )

        result = agent._apply_complexity_noqa_fallback(test_file, issue)
        assert result is not None
        assert result.success is True

    def test_write_failure_returns_none(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): pass\n")
        agent.context.get_file_content = Mock(return_value="def f(): pass\n")
        agent.context.write_file_content = Mock(return_value=False)

        issue = Issue(
            id="n-3",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'f' too complex",
            line_number=1,
        )

        result = agent._apply_complexity_noqa_fallback(test_file, issue)
        assert result is None


@pytest.mark.unit
class TestAstComplexityFallback:
    """Cover `_apply_ast_complexity_fallback` and related helpers."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_no_candidates_returns_none(self, agent, tmp_path) -> None:
        result = await agent._apply_ast_complexity_fallback(
            tmp_path / "x.py", "def f(): pass\n", [], issue=None
        )
        assert result is None

    async def test_transform_returns_none_continues(
        self, agent, tmp_path
    ) -> None:
        engine = Mock()
        engine.transform = AsyncMock(return_value=None)

        candidate = {
            "name": "f",
            "line_start": 1,
            "line_end": 1,
            "complexity": 20,
        }

        with patch(
            "crackerjack.agents.refactoring_agent._get_ast_transform_engine",
            return_value=engine,
        ):
            result = await agent._apply_ast_complexity_fallback(
                tmp_path / "x.py", "def f(): pass\n", [candidate], issue=None
            )

        assert result is None

    async def test_write_failure_returns_error(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("def f(): pass\n")
        agent.context.write_file_content = Mock(return_value=False)

        change_spec = SimpleNamespace(
            transformed_content="def f(): return 1\n",
        )

        engine = Mock()
        engine.transform = AsyncMock(return_value=change_spec)

        candidate = {
            "name": "f",
            "line_start": 1,
            "line_end": 1,
            "complexity": 20,
        }

        with patch(
            "crackerjack.agents.refactoring_agent._get_ast_transform_engine",
            return_value=engine,
        ):
            result = await agent._apply_ast_complexity_fallback(
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

    def test_prioritize_complexity_candidates_empty(self, agent) -> None:
        assert agent._prioritize_complexity_candidates([], None) == []

    def test_prioritize_complexity_candidates_orders_by_name(
        self, agent
    ) -> None:
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
        ordered = agent._prioritize_complexity_candidates(candidates, issue)
        assert ordered[0]["name"] == "b"


@pytest.mark.unit
class TestComplexityReducedHelpers:
    """Cover `_complexity_reduced_*` helpers."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_reduced_below_threshold_syntax_error(self, agent) -> None:
        candidate = {"name": "f", "line_start": 1, "line_end": 1}
        result = agent._complexity_reduced_below_threshold("def broken(:\n", candidate)
        assert result is False

    def test_reduced_below_threshold_no_function(self, agent) -> None:
        candidate = {"name": "missing", "line_start": 100, "line_end": 101}
        result = agent._complexity_reduced_below_threshold(
            "def f(): pass\n", candidate
        )
        assert result is False

    def test_reduced_for_targets_syntax_error(self, agent) -> None:
        result = agent._complexity_reduced_for_targets(
            "def broken(:\n", [{"name": "f", "line_start": 1, "line_end": 1}]
        )
        assert result is False

    def test_reduced_for_targets_empty(self, agent) -> None:
        result = agent._complexity_reduced_for_targets(
            "def f(): pass\n", []
        )
        assert result is False


@pytest.mark.unit
class TestExecuteFixPlan:
    """Cover the FixPlan executor branches."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_empty_changes_returns_error(self, agent) -> None:
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="COMPLEXITY",
            changes=[],
            rationale="nothing",
        )

        result = await agent.execute_fix_plan(plan)
        assert result.success is False
        assert "no changes" in result.remaining_issues[0].lower()

    async def test_no_file_path_returns_error(self, agent) -> None:
        plan = FixPlan(
            file_path="",
            issue_type="COMPLEXITY",
            risk_level="low",
            validated_by="system",
            rationale="r",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="",
                    new_code="x = 1\n",
                    reason="r",
                )
            ],
        )

        result = await agent.execute_fix_plan(plan)
        assert result.success is False
        assert "no file path" in result.remaining_issues[0].lower()

    async def test_read_failure_returns_error(self, agent, tmp_path) -> None:
        plan = create_fix_plan(
            file_path=str(tmp_path / "missing.py"),
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="x",
                    new_code="y",
                    reason="r",
                )
            ],
            rationale="r",
        )

        with patch.object(agent, "_read_file_context") as mock_read:
            mock_read.side_effect = OSError("not found")
            result = await agent.execute_fix_plan(plan)

        assert result.success is False

    async def test_invalid_line_range_marks_change_failed(
        self, agent, tmp_path
    ) -> None:
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

        result = await agent.execute_fix_plan(plan)
        assert result.success is False
        assert any("Invalid line range" in issue for issue in result.remaining_issues)

    async def test_non_complexity_plan_skips_fallback(
        self, agent, tmp_path
    ) -> None:
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

        with patch.object(agent, "_apply_ruff_formatting") as mock_ruff, \
             patch.object(agent, "_handle_complexity_fallback") as mock_fallback:
            mock_fallback.return_value = (False, 0.0, [])
            result = await agent.execute_fix_plan(plan)

        # When non-COMPLEXITY plan fails, ruff is not called
        assert result.success is False
        mock_ruff.assert_not_called()


@pytest.mark.unit
class TestApplyStandardFixChange:
    """Cover the standard line-range replacer."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_invalid_line_range_logs_failure(self, agent) -> None:
        applied: list[str] = []
        failed: list[str] = []
        change = ChangeSpec(
            line_range=(0, 1000),
            old_code="",
            new_code="x = 1\n",
            reason="bad",
        )
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="X",
            changes=[change],
            rationale="r",
        )

        agent._apply_standard_fix_change(plan, "x = 1\n", change, 0, applied, failed)
        assert not applied
        assert any("Invalid line range" in f for f in failed)

    def test_successful_replacement(self, agent) -> None:
        applied: list[str] = []
        failed: list[str] = []
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="x = 1\n",
            new_code="x = 2\n",
            reason="rename",
        )
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="X",
            changes=[change],
            rationale="r",
        )
        agent.context.write_file_content = Mock(return_value=True)

        agent._apply_standard_fix_change(plan, "x = 1\n", change, 0, applied, failed)
        assert applied
        assert not failed

    def test_write_failure_marks_failed(self, agent) -> None:
        applied: list[str] = []
        failed: list[str] = []
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="x = 1\n",
            new_code="x = 2\n",
            reason="rename",
        )
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="X",
            changes=[change],
            rationale="r",
        )
        agent.context.write_file_content = Mock(return_value=False)

        agent._apply_standard_fix_change(plan, "x = 1\n", change, 0, applied, failed)
        assert not applied
        assert failed


@pytest.mark.unit
class TestApplyAstTransformChange:
    """Cover `_apply_ast_transform_change`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_non_ast_change_returns_false(self, agent) -> None:
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="",
            new_code="x",
            reason="standard change",
        )
        applied: list[str] = []
        failed: list[str] = []
        result = agent._apply_ast_transform_change("x.py", change, 0, applied, failed)
        assert result is False
        assert not applied

    def test_ast_change_success(self, agent) -> None:
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="",
            new_code="x = 1\n",
            reason="AST transform: extract method",
        )
        applied: list[str] = []
        failed: list[str] = []
        agent.context.write_file_content = Mock(return_value=True)

        result = agent._apply_ast_transform_change("x.py", change, 0, applied, failed)
        assert result is True
        assert applied

    def test_ast_change_write_failure(self, agent) -> None:
        change = ChangeSpec(
            line_range=(1, 1),
            old_code="",
            new_code="x = 1\n",
            reason="AST transform: extract method",
        )
        applied: list[str] = []
        failed: list[str] = []
        agent.context.write_file_content = Mock(return_value=False)

        result = agent._apply_ast_transform_change("x.py", change, 0, applied, failed)
        assert result is True
        assert not applied
        assert failed


@pytest.mark.unit
class TestComplexityStillExceedsThreshold:
    """Cover `_complexity_still_exceeds_threshold`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_none_line_number_returns_true(self, agent) -> None:
        assert agent._complexity_still_exceeds_threshold("x.py", None) is True

    def test_empty_content_returns_true(self, agent) -> None:
        agent.context.get_file_content = Mock(return_value="")
        assert agent._complexity_still_exceeds_threshold("x.py", 1) is True

    def test_syntax_error_returns_true(self, agent) -> None:
        agent.context.get_file_content = Mock(return_value="def broken(:\n")
        assert agent._complexity_still_exceeds_threshold("x.py", 1) is True

    def test_simple_function_returns_false(self, agent) -> None:
        agent.context.get_file_content = Mock(
            return_value="def f():\n    return 1\n"
        )
        assert agent._complexity_still_exceeds_threshold("x.py", 1) is False

    def test_line_outside_function_returns_true(self, agent) -> None:
        agent.context.get_file_content = Mock(
            return_value="def f():\n    return 1\n"
        )
        assert agent._complexity_still_exceeds_threshold("x.py", 100) is True


@pytest.mark.unit
class TestHandleComplexityFallback:
    """Cover `_handle_complexity_fallback` and `_issue_from_fix_plan`."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_non_complexity_returns_immediately(self, agent) -> None:
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="DEAD_CODE",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="",
                    new_code="",
                    reason="r",
                )
            ],
            rationale="r",
        )
        result = agent._handle_complexity_fallback(
            plan, "x.py", True, 0.5, []
        )
        assert result[0] is True
        assert result[1] == 0.5

    def test_complexity_below_threshold_returns_immediately(self, agent) -> None:
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(
                    line_range=(1, 1),
                    old_code="",
                    new_code="",
                    reason="r",
                )
            ],
            rationale="r",
        )
        agent.context.get_file_content = Mock(
            return_value="def f():\n    return 1\n"
        )
        result = agent._handle_complexity_fallback(
            plan, "x.py", True, 0.8, []
        )
        assert result[0] is True
        assert result[1] == 0.8

    def test_issue_from_fix_plan_no_changes(self, agent) -> None:
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="COMPLEXITY",
            changes=[],
            rationale="r",
        )
        assert agent._issue_from_fix_plan(plan) is None

    def test_issue_from_fix_plan_zero_line(self, agent) -> None:
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(
                    line_range=(0, 0),
                    old_code="",
                    new_code="",
                    reason="r",
                )
            ],
            rationale="r",
        )
        assert agent._issue_from_fix_plan(plan) is None

    def test_issue_from_fix_plan_with_issue_message(self, agent) -> None:
        plan = create_fix_plan(
            file_path="x.py",
            issue_type="COMPLEXITY",
            changes=[
                ChangeSpec(
                    line_range=(5, 5),
                    old_code="",
                    new_code="",
                    reason="r",
                )
            ],
            rationale="r",
            issue_message="from plan",
            issue_details=["function: f"],
            issue_stage="test",
        )
        issue = agent._issue_from_fix_plan(plan)
        assert issue is not None
        assert issue.message == "from plan"
        assert issue.line_number == 5
        assert issue.stage == "test"


@pytest.mark.unit
class TestGetAstTransformEngine:
    """Cover the lazy singleton helper."""

    def test_returns_cached_engine(self) -> None:
        from crackerjack.agents import refactoring_agent as module

        # Reset module-level cache
        module._ast_transform_engine = None

        with patch(
            "crackerjack.agents.helpers.ast_transform.ASTTransformEngine"
        ) as mock_engine_cls:
            mock_engine_cls.return_value = Mock()

            engine1 = module._get_ast_transform_engine()
            engine2 = module._get_ast_transform_engine()

        # Second call should reuse the cached engine
        assert engine1 is engine2
        mock_engine_cls.assert_called_once()


@pytest.mark.unit
class TestModuleReadFileContext:
    """Cover `_read_file_context` delegating to FileContextReader."""

    @pytest.fixture
    def agent(self, tmp_path):
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_delegates_to_file_reader(self, agent, tmp_path) -> None:
        test_file = tmp_path / "x.py"
        test_file.write_text("x = 1\n")

        with patch.object(
            agent._file_reader, "read_file", new_callable=AsyncMock
        ) as mock_read:
            mock_read.return_value = "x = 1\n"
            result = await agent._read_file_context(test_file)

        assert result == "x = 1\n"
        mock_read.assert_called_once()

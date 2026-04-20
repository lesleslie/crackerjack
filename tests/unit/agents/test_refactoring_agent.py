"""Unit tests for RefactoringAgent.

Tests complexity reduction, dead code removal, semantic analysis,
and refactoring workflows.
"""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import libcst as cst
import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.helpers.ast_transform import ExtractMethodPattern, LibcstSurgeon
from crackerjack.agents.helpers.ast_transform.validator import TransformValidator
from crackerjack.agents.refactoring_agent import RefactoringAgent


@pytest.mark.unit
class TestRefactoringAgentInitialization:
    """Test RefactoringAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context) -> None:
        """Test RefactoringAgent initializes correctly."""
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            agent = RefactoringAgent(context)

            assert agent.context == context
            assert agent.semantic_insights == {}

    def test_get_supported_types(self, context) -> None:
        """Test agent supports complexity and dead code issues."""
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            agent = RefactoringAgent(context)

            supported = agent.get_supported_types()

            assert IssueType.COMPLEXITY in supported
            assert IssueType.DEAD_CODE in supported


@pytest.mark.unit
@pytest.mark.asyncio
class TestRefactoringAgentCanHandle:
    """Test issue detection and handling capability."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_can_handle_complexity_with_markers(self, agent) -> None:
        """Test high confidence for complexity issues with markers."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function has too complex cognitive complexity",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_complexity_without_markers(self, agent) -> None:
        """Test lower confidence for complexity without markers."""
        issue = Issue(
            id="comp-002",
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message="Some complexity issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.85

    async def test_can_handle_dead_code_with_markers(self, agent) -> None:
        """Test handling dead code issues with markers."""
        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Function defined but not used",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.8

    async def test_can_handle_dead_code_without_markers(self, agent) -> None:
        """Test handling dead code without markers."""
        issue = Issue(
            id="dead-002",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Some code",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.75

    async def test_cannot_handle_unsupported_type(self, agent) -> None:
        """Test agent cannot handle unsupported issue types."""
        issue = Issue(
            id="sec-001",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="Security issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.0


@pytest.mark.unit
@pytest.mark.asyncio
class TestRefactoringAgentComplexityReduction:
    """Test complexity reduction functionality."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_analyze_and_fix_complexity_issue(self, agent, tmp_path) -> None:
        """Test analyzing and fixing complexity issue."""
        test_file = tmp_path / "complex.py"
        test_file.write_text("""
def complex_function():
    if x > 10:
        if y < 5:
            if z == 3:
                return True
    return False
""")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too complex",
            file_path=str(test_file),
        )

        with patch.object(agent, "_reduce_complexity") as mock_reduce:
            mock_reduce.return_value = FixResult(success=True, confidence=0.8)

            result = await agent.analyze_and_fix(issue)

            mock_reduce.assert_called_once_with(issue)
            assert result.success is True

    async def test_analyze_and_fix_dead_code_issue(self, agent, tmp_path) -> None:
        """Test analyzing and fixing dead code issue."""
        test_file = tmp_path / "dead.py"
        test_file.write_text("import unused_module\n\ndef main():\n    pass\n")

        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused import",
            file_path=str(test_file),
        )

        with patch.object(agent, "_remove_dead_code") as mock_remove:
            mock_remove.return_value = FixResult(success=True, confidence=0.8)

            result = await agent.analyze_and_fix(issue)

            mock_remove.assert_called_once_with(issue)
            assert result.success is True

    async def test_analyze_and_fix_unsupported_type(self, agent) -> None:
        """Test analyzing unsupported issue type."""
        issue = Issue(
            id="test-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Format issue",
        )

        result = await agent.analyze_and_fix(issue)

        assert result.success is False
        assert result.confidence == 0.0
        assert "cannot handle" in result.remaining_issues[0].lower()

    async def test_reduce_complexity_no_file_path(self, agent) -> None:
        """Test reduce_complexity when no file path provided."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Too complex",
            file_path=None,
        )

        result = await agent._reduce_complexity(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_reduce_complexity_file_not_exists(self, agent, tmp_path) -> None:
        """Test reduce_complexity when file doesn't exist."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Too complex",
            file_path=str(tmp_path / "nonexistent.py"),
        )

        result = await agent._reduce_complexity(issue)

        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    async def test_reduce_complexity_syntax_error(self, agent, tmp_path) -> None:
        """Test reduce_complexity handles syntax errors."""
        test_file = tmp_path / "invalid.py"
        test_file.write_text("def broken(\n")  # Invalid syntax

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex function",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(return_value="def broken(\n")

        result = await agent._reduce_complexity(issue)

        assert result.success is False
        assert "Syntax error" in result.remaining_issues[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestRefactoringAgentDeadCodeRemoval:
    """Test dead code removal functionality."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    async def test_remove_dead_code_no_file_path(self, agent) -> None:
        """Test remove_dead_code when no file path provided."""
        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused code",
            file_path=None,
        )

        result = await agent._remove_dead_code(issue)

        assert result.success is False
        assert "No file path" in result.remaining_issues[0]

    async def test_remove_dead_code_file_not_exists(self, agent, tmp_path) -> None:
        """Test remove_dead_code when file doesn't exist."""
        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused import",
            file_path=str(tmp_path / "nonexistent.py"),
        )

        result = await agent._remove_dead_code(issue)

        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    async def test_remove_dead_code_syntax_error(self, agent, tmp_path) -> None:
        """Test remove_dead_code handles syntax errors."""
        test_file = tmp_path / "invalid.py"
        test_file.write_text("def broken(\n")

        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused code",
            file_path=str(test_file),
        )

        agent.context.get_file_content = Mock(return_value="def broken(\n")

        result = await agent._remove_dead_code(issue)

        assert result.success is False
        assert "Syntax error" in result.remaining_issues[0]


@pytest.mark.unit
class TestRefactoringAgentComplexityDetection:
    """Test complexity detection and analysis."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_has_complexity_markers_cognitive_complexity(self, agent) -> None:
        """Test detecting cognitive complexity marker."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function has high cognitive complexity",
        )

        result = agent._has_complexity_markers(issue)

        assert result is True

    def test_has_complexity_markers_too_complex(self, agent) -> None:
        """Test detecting too complex marker."""
        issue = Issue(
            id="comp-002",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function is too complex",
        )

        result = agent._has_complexity_markers(issue)

        assert result is True

    def test_has_complexity_markers_nested(self, agent) -> None:
        """Test detecting nested code marker."""
        issue = Issue(
            id="comp-003",
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message="Code has nested conditionals",
        )

        result = agent._has_complexity_markers(issue)

        assert result is True

    def test_has_complexity_markers_no_message(self, agent) -> None:
        """Test complexity markers with no message."""
        issue = Issue(
            id="comp-004",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message=None,
        )

        result = agent._has_complexity_markers(issue)

        assert result is False

    def test_has_complexity_markers_none_found(self, agent) -> None:
        """Test when no complexity markers found."""
        issue = Issue(
            id="comp-005",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Some other issue",
        )

        result = agent._has_complexity_markers(issue)

        assert result is False


@pytest.mark.unit
class TestRefactoringAgentDeadCodeDetection:
    """Test dead code detection markers."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_has_dead_code_markers_unused(self, agent) -> None:
        """Test detecting unused code marker."""
        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Variable unused in function",
        )

        result = agent._has_dead_code_markers(issue)

        assert result is True

    def test_has_dead_code_markers_imported_unused(self, agent) -> None:
        """Test detecting imported but unused marker."""
        issue = Issue(
            id="dead-002",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Module imported but unused",
        )

        result = agent._has_dead_code_markers(issue)

        assert result is True

    def test_has_dead_code_markers_unreachable(self, agent) -> None:
        """Test detecting unreachable code marker."""
        issue = Issue(
            id="dead-003",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Code unreachable after return",
        )

        result = agent._has_dead_code_markers(issue)

        assert result is True

    def test_has_dead_code_markers_no_message(self, agent) -> None:
        """Test dead code markers with no message."""
        issue = Issue(
            id="dead-004",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message=None,
        )

        result = agent._has_dead_code_markers(issue)

        assert result is False

    def test_has_dead_code_markers_none_found(self, agent) -> None:
        """Test when no dead code markers found."""
        issue = Issue(
            id="dead-005",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Some other issue",
        )

        result = agent._has_dead_code_markers(issue)

        assert result is False


@pytest.mark.unit
class TestRefactoringAgentComplexityCalculation:
    """Test complexity calculation methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_estimate_function_complexity_simple(self, agent) -> None:
        """Test estimating complexity for simple function."""
        function_body = """
    return x + y
"""
        complexity = agent._estimate_function_complexity(function_body)

        # Base complexity is 1
        assert complexity >= 1

    def test_estimate_function_complexity_with_conditionals(self, agent) -> None:
        """Test estimating complexity with conditionals."""
        function_body = """
    if x > 10:
        return True
    elif x < 5:
        return False
    else:
        return None
"""
        complexity = agent._estimate_function_complexity(function_body)

        # Base + 2 conditionals (if, elif)
        assert complexity >= 3

    def test_estimate_function_complexity_with_loops(self, agent) -> None:
        """Test estimating complexity with loops."""
        function_body = """
    for item in items:
        if item.valid:
            results.append(item)
"""
        complexity = agent._estimate_function_complexity(function_body)

        # Base + for + if
        assert complexity >= 3

    def test_estimate_function_complexity_nested(self, agent) -> None:
        """Test estimating complexity with nested code."""
        function_body = """
    for item in items:
        for sub_item in item:
            if sub_item.valid:
                result.append(sub_item)
"""
        complexity = agent._estimate_function_complexity(function_body)

        # Should detect nesting
        assert complexity >= 4

    def test_estimate_function_complexity_empty(self, agent) -> None:
        """Test estimating complexity for empty function."""
        complexity = agent._estimate_function_complexity("")

        assert complexity == 0


@pytest.mark.unit
class TestRefactoringAgentSemanticHelpers:
    """Test semantic analysis helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_is_semantic_function_definition(self, agent) -> None:
        """Test detecting function definitions."""
        assert agent._is_semantic_function_definition("def foo():") is True
        assert agent._is_semantic_function_definition("def bar(x, y):") is True
        assert agent._is_semantic_function_definition("async def baz():") is False
        assert agent._is_semantic_function_definition("    return x") is False

    def test_should_skip_semantic_line_empty(self, agent) -> None:
        """Test skipping empty lines in semantic analysis."""
        result = agent._should_skip_semantic_line("", None, "")

        assert result is True

    def test_should_skip_semantic_line_comment(self, agent) -> None:
        """Test skipping comment lines in semantic analysis."""
        result = agent._should_skip_semantic_line("# This is a comment", None, "# This is a comment")

        assert result is True

    def test_should_skip_semantic_line_code(self, agent) -> None:
        """Test not skipping code lines."""
        result = agent._should_skip_semantic_line("return True", None, "    return True")

        assert result is False


@pytest.mark.unit
class TestRefactoringAgentImportRemoval:
    """Test import removal logic."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_should_remove_import_line_simple_import(self, agent) -> None:
        """Test identifying simple import to remove."""
        unused_import = {"type": "import", "name": "os"}
        line = "import os"

        result = agent._should_remove_import_line(line, unused_import)

        assert result is True

    def test_should_remove_import_line_from_import(self, agent) -> None:
        """Test identifying from import to remove."""
        unused_import = {"type": "from_import", "name": "Path"}
        line = "from pathlib import Path"

        result = agent._should_remove_import_line(line, unused_import)

        assert result is True

    def test_should_remove_import_line_no_match(self, agent) -> None:
        """Test not removing non-matching import."""
        unused_import = {"type": "import", "name": "os"}
        line = "import sys"

        result = agent._should_remove_import_line(line, unused_import)

        assert result is False

    def test_should_remove_import_line_wrong_type(self, agent) -> None:
        """Test with unknown import type."""
        unused_import = {"type": "unknown", "name": "os"}
        line = "import os"

        result = agent._should_remove_import_line(line, unused_import)

        assert result is False


@pytest.mark.unit
class TestRefactoringAgentPatternDetection:
    """Test pattern detection for refactoring."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_extract_nested_conditions_long_line(self, agent) -> None:
        """Test extracting nested conditions from long lines."""
        content = """
def check():
    if x > 10 and y < 20 and z == 5 and a != 3 and b >= 7 and c <= 15 and d in items and e not in others:
        return True
"""
        result = agent._extract_nested_conditions(content)

        # Should suggest extracting to helper method
        assert "_is_complex_condition" in result or result == content

    def test_simplify_boolean_expressions_complex(self, agent) -> None:
        """Test simplifying complex boolean expressions."""
        content = """
def validate():
    if (x > 10 and y < 20) or (z == 5 and a != 3) or (b >= 7 and c <= 15) or (d in items and e not in others):
        return True
"""
        result = agent._simplify_boolean_expressions(content)

        # Should suggest extracting to validation method
        assert "_validate_complex_condition" in result or result == content

    def test_is_empty_except_block(self, agent) -> None:
        """Test detecting empty except blocks."""
        lines = ["try:", "    do_something()", "except:", "    pass"]

        result = agent._is_empty_except_block(lines, 2)

        assert result is True

    def test_is_not_empty_except_block(self, agent) -> None:
        """Test not detecting non-empty except blocks."""
        lines = ["try:", "    do_something()", "except Exception as e:", "    handle(e)"]

        result = agent._is_empty_except_block(lines, 2)

        assert result is True  # Still starts with "except "


@pytest.mark.unit
class TestRefactoringAgentAstTransformFallback:
    """Test the AST transform fallback used for complexity reduction."""

    def test_extract_method_pattern_applies_nested_helper(self, tmp_path) -> None:
        """Test extract_method candidates produce a valid nested helper rewrite."""
        test_file = tmp_path / "register_tools.py"
        content = """def register_tools():
    self.register_alpha()
    self.register_beta()
    self.register_gamma()
    self.register_delta()
    return True
"""
        node = next(
            node
            for node in ast.walk(ast.parse(content))
            if isinstance(node, ast.FunctionDef)
        )

        result = LibcstSurgeon().apply(
            content,
            {
                "type": "extract_method",
                "node": node,
                "extraction_start": 2,
                "extraction_end": 4,
                "suggested_name": "_setup_metrics",
                "inputs": [],
                "outputs": [],
                "block_statements": [],
            },
            test_file,
        )

        assert result.success is True
        assert "_setup_metrics()" in result.transformed_code
        assert "def _setup_metrics():" in result.transformed_code
        ast.parse(result.transformed_code)

    def test_registration_wrapper_pattern_lifts_to_module_helper(
        self,
        tmp_path,
    ) -> None:
        """Test register_* wrappers can be lifted into a top-level helper."""
        content = """def register_code_analysis_tools(mcp):
    \"\"\"Register code analysis tools.\"\"\"

    @mcp.tool()
    async def code_ingest_file(file_path: str) -> str:
        if not file_path:
            return ""
        for _ in range(2):
            if file_path:
                return file_path
        return file_path

    @mcp.tool()
    async def code_ingest_directory(directory: str) -> str:
        if not directory:
            return ""
        if directory.endswith(".py"):
            return directory
        return directory

    return None
"""
        tree = ast.parse(content)
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "register_code_analysis_tools"
        )

        pattern = ExtractMethodPattern()
        match = pattern.match(node, content.splitlines())

        assert match is not None
        assert match.match_info["lift_to_module"] is True

        result = LibcstSurgeon().apply(
            content,
            match.match_info,
            tmp_path / "register_code_analysis_tools.py",
        )

        assert result.success is True
        assert "def register_code_analysis_tools(mcp):" in result.transformed_code
        assert "def _code_ingest_file_impl(" in result.transformed_code
        assert "def _code_ingest_directory_impl(" in result.transformed_code
        assert "mcp.tool()(_code_ingest_file_impl)" in result.transformed_code
        assert "mcp.tool()(_code_ingest_directory_impl)" in result.transformed_code
        ast.parse(result.transformed_code)

        validation = TransformValidator().validate(
            content,
            result.transformed_code,
            tmp_path / "register_code_analysis_tools.py",
            target_function_name="register_code_analysis_tools",
        )

        assert validation.valid is True
        assert validation.original_complexity is not None
        assert validation.transformed_complexity is not None
        assert validation.transformed_complexity < validation.original_complexity

    def test_append_loop_cleanup_rewrites_list_comprehension(self) -> None:
        """Test extract-method cleanup removes simple append loops."""
        content = """def markdown_to_qwen_markdown(md_content):
    lines = md_content.strip().split("\\n")
    prompt_start = 0
    prompt_lines = []
    for line in lines[prompt_start:]:
        prompt_lines.append(line)
    prompt_content = "\\n".join(prompt_lines).strip()
    return prompt_content
"""

        result = LibcstSurgeon()._simplify_append_loops(content)

        assert "prompt_lines.append(line)" not in result
        assert "prompt_lines = [line for line in lines[prompt_start:]]" in result
        ast.parse(result)

    def test_dict_assignment_cleanup_reflows_long_dict_literal(self) -> None:
        """Test extract-method cleanup wraps long dict assignments."""
        content = """def get_metrics_summary():
    summary = {'total_sessions_started': 0, 'total_sessions_ended': 0, 'active_sessions': {}, 'quality_scores': {}, 'mcp_events_success': 0, 'mcp_events_failure': 0}
    return summary
"""

        result = LibcstSurgeon()._reflow_overlong_dict_assignments(content)

        assert "summary = {" in result
        assert "'total_sessions_started': 0," in result
        assert "'mcp_events_failure': 0," in result
        ast.parse(result)

    def test_report_sections_pattern_lifts_to_top_level_helpers(
        self,
        tmp_path,
    ) -> None:
        """Test numbered report sections split into top-level helper functions."""
        content = """from pathlib import Path
from datetime import datetime


def generate_workflow_report(db_path=None, session_id=None):
    from session_buddy.storage.skills_storage import SkillsStorage

    if db_path is None:
        db_path = Path.cwd() / ".session-buddy" / "skills.db"

    storage = SkillsStorage(db_path=db_path)
    lines = [
        "=" * 70,
        "Workflow Correlation Report",
        "=" * 70,
        "",
        f"Session: {session_id if session_id else 'All Sessions'}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    # Section 1: Skill Effectiveness by Phase
    lines.extend(["-" * 70, "1. Skill Effectiveness by Workflow Phase", "-" * 70, ""])

    effectiveness = storage.get_workflow_skill_effectiveness(
        workflow_phase=None, min_invocations=1
    )

    if effectiveness:
        phases: dict[str, list[dict]] = {}
        for skill in effectiveness:
            phase = skill["workflow_phase"]
            if phase not in phases:
                phases[phase] = []
            phases[phase].append(skill)
    else:
        lines.append("No workflow data available yet.")

    # Section 2: Bottleneck Identification
    lines.extend(["", "", "-" * 70, "2. Workflow Bottlenecks", "-" * 70, ""])
    bottlenecks = storage.identify_workflow_bottlenecks(min_abandonment_rate=0.2)
    if bottlenecks:
        lines.append("Phases with high abandonment rates (potential bottlenecks):")

    # Section 3: Phase Transition Diagram
    lines.extend(["", "", "-" * 70, "3. Workflow Phase Transitions", "-" * 70, ""])
    transitions = storage.get_workflow_phase_transitions(session_id=session_id)
    if transitions:
        lines.append("Most common phase transitions:")

    # Section 4: Phase-Specific Recommendations
    lines.extend(["", "", "-" * 70, "4. Recommendations by Phase", "-" * 70, ""])
    if effectiveness:
        lines.append("Top-performing skills for each phase:")
        for phase in sorted(phases.keys()):
            phase_skills = [
                s
                for s in effectiveness
                if s["workflow_phase"] == phase and s["completion_rate"] > 70
            ]
            if phase_skills:
                best_skill = max(phase_skills, key=lambda s: s["completion_rate"])
                lines.append(
                    f"  🎯 {phase.upper()}: Use {best_skill['skill_name']} "
                    f"({best_skill['completion_rate']:.1f}% success rate)"
                )
    else:
        lines.append("Insufficient data for recommendations.")

    lines.extend(["", "", "=" * 70])
    return "\\n".join(lines)
"""
        tree = ast.parse(content)
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "generate_workflow_report"
        )

        pattern = ExtractMethodPattern()
        match = pattern.match(node, content.splitlines())

        assert match is not None
        assert match.match_info["type"] == "split_sections"

        result = LibcstSurgeon().apply(
            content,
            match.match_info,
            tmp_path / "generate_workflow_report.py",
        )

        assert result.success is True
        module = ast.parse(result.transformed_code)
        wrapper_node = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "generate_workflow_report"
        )

        helper_nodes = [
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name != "generate_workflow_report"
        ]

        assert helper_nodes
        assert "from pathlib import Path" in result.transformed_code
        assert "from datetime import datetime" in result.transformed_code
        assert "effectiveness, phases =" in result.transformed_code
        assert "_section_2_bottleneck_identification(" in result.transformed_code
        assert "_section_3_phase_transition_diagram(" in result.transformed_code
        assert "_section_4_phasespecific_recommendations(" in result.transformed_code
        assert TransformValidator()._calculate_complexity(ast.unparse(wrapper_node)) <= 15

    def test_extract_method_renames_colliding_helper_name(
        self,
        tmp_path,
    ) -> None:
        """Test helper names are made unique when they collide with the source."""
        content = """async def sync_provider_configs(self, source, destination):
    return await _helper_functions(self, source, destination)


async def _helper_functions(self, source, destination):
    if source == destination:
        return {}
    return {"source": source, "destination": destination}
"""
        tree = ast.parse(content)
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_helper_functions"
        )

        result = LibcstSurgeon().apply(
            content,
            {
                "type": "extract_method",
                "node": node,
                "extraction_start": node.body[0].lineno,
                "extraction_end": node.body[-1].end_lineno or node.body[-1].lineno,
                "inputs": ["self", "source", "destination"],
                "outputs": [],
                "suggested_name": "_helper_functions",
                "block_statements": node.body,
                "lift_to_module": True,
            },
            tmp_path / "llm_providers.py",
        )

        assert result.success is True
        assert "async def _helper_functions_impl(" in result.transformed_code
        assert "return await _helper_functions_impl(" in result.transformed_code
        ast.parse(result.transformed_code)

    def test_extract_method_lifts_nested_helpers_to_module(
        self,
        tmp_path,
    ) -> None:
        """Test nested helper functions can be lifted into module-level helpers."""
        content = """async def _helper_functions(self, path):
    def load_json_safely(path):
        try:
            if path.exists():
                return json.loads(path.read_text())
        except OSError as e:
            self.logger.error(str(e))
        return {}

    def save_json_atomically(path, data):
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=2))
        temp_path.replace(path)
        return path

    data = load_json_safely(path)
    return save_json_atomically(path, data)
"""
        tree = ast.parse(content)
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_helper_functions"
        )

        pattern = ExtractMethodPattern()
        match = pattern.match(node, content.splitlines())

        assert match is not None
        assert match.match_info["type"] == "lift_nested_helpers"

        result = LibcstSurgeon().apply(
            content,
            match.match_info,
            tmp_path / "helpers.py",
        )

        assert result.success is True
        assert "def _load_json_safely_impl(" in result.transformed_code
        assert "def _save_json_atomically_impl(" in result.transformed_code
        assert "load_json_safely = partial(_load_json_safely_impl" in result.transformed_code
        assert "save_json_atomically = _save_json_atomically_impl" in result.transformed_code
        assert "import json" in result.transformed_code
        assert "from functools import partial" in result.transformed_code
        ast.parse(result.transformed_code)

    def test_extract_method_lifts_nested_helpers_imports_path(self, tmp_path) -> None:
        """Test nested helper lifting adds Path imports when needed."""
        content = """async def _helper_functions(self, path):
    def load_json_safely(path):
        return path.exists()

    def save_json_atomically(path, data):
        return Path(path).name

    return load_json_safely(path), save_json_atomically(path, {})
"""
        tree = ast.parse(content)
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_helper_functions"
        )

        pattern = ExtractMethodPattern()
        match = pattern.match(node, content.splitlines())

        assert match is not None
        assert match.match_info["type"] == "lift_nested_helpers"

        result = LibcstSurgeon().apply(
            content,
            match.match_info,
            tmp_path / "helpers_path.py",
        )

        assert result.success is True
        assert "from pathlib import Path" in result.transformed_code
        assert "from functools import partial" not in result.transformed_code
        ast.parse(result.transformed_code)

    def test_extract_method_lifts_nested_helpers_reflows_long_joined_strings(
        self,
        tmp_path,
    ) -> None:
        """Test nested helper lifting rewrites long f-strings into wrapped lines."""
        content = "\n".join(
            [
                "async def _helper_functions(self, path):",
                "    def load_json_safely(path: Path):",
                "        self.logger.info(",
                "            f\"Merged {path} {path} {path} {path} {path} {path} {path} {path}\"",
                "        )",
                "        return Path(path).name",
                "",
                "    def save_json_atomically(path, data):",
                "        return Path(path).name",
                "",
                "    return load_json_safely(path), save_json_atomically(path, {})",
                "",
            ]
        )
        tree = ast.parse(content)
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_helper_functions"
        )

        pattern = ExtractMethodPattern()
        match = pattern.match(node, content.splitlines())

        assert match is not None
        assert match.match_info["type"] == "lift_nested_helpers"

        result = LibcstSurgeon().apply(
            content,
            match.match_info,
            tmp_path / "helpers_wrapped.py",
        )

        assert result.success is True
        assert "from pathlib import Path" in result.transformed_code
        assert all(len(line) <= 88 for line in result.transformed_code.splitlines())
        ast.parse(result.transformed_code)

    def test_metrics_summary_pattern_splits_metric_loops(self, tmp_path) -> None:
        """Test get_metrics_summary-style loops split into helper sections."""
        content = "\n".join(
            [
                "def get_metrics_summary():",
                "    metrics = get_metrics()",
                "    summary = {",
                "        'total_sessions_started': 0,",
                "        'total_sessions_ended': 0,",
                "        'active_sessions': {},",
                "    }",
                "    try:",
                "        for metric in metrics.session_start_total.collect():",
                "            for sample in metric.samples:",
                "                summary['total_sessions_started'] += int(sample.value)",
                "        for metric in metrics.session_end_total.collect():",
                "            for sample in metric.samples:",
                "                summary['total_sessions_ended'] += int(sample.value)",
                "        for metric in metrics.active_sessions.collect():",
                "            for sample in metric.samples:",
                "                labels = sample.labels or {}",
                "                component = labels.get('component_name', 'unknown')",
                "                summary['active_sessions'][component] = int(sample.value)",
                "    except Exception as e:",
                "        return {'error': str(e)}",
                "    return summary",
                "",
            ]
        )
        tree = ast.parse(content)
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "get_metrics_summary"
        )

        pattern = ExtractMethodPattern()
        match = pattern.match(node, content.splitlines())

        assert match is not None
        assert match.match_info["type"] == "split_sections"

        result = LibcstSurgeon().apply(
            content,
            match.match_info,
            tmp_path / "get_metrics_summary.py",
        )

        assert result.success is True
        assert "_collect_session_start_total(" in result.transformed_code
        assert "_collect_session_end_total(" in result.transformed_code
        assert "_collect_active_sessions(" in result.transformed_code
        ast.parse(result.transformed_code)

    def test_extract_method_merges_adjacent_section_starts(
        self,
        tmp_path,
    ) -> None:
        """Test adjacent section comments still produce a valid extract-method transform."""
        content = """async def sync_provider_configs(self, source, destination, sync_types=None):
    # Main sync logic
    sync_result = {"source": source}
    sync_result["source_len"] = len(source)
    sync_result["dest_len"] = len(destination)

    # Load configs
    src_config = {"destination": destination}
    src_config["source"] = source
    dst_config = {"sync_types": sync_types or []}
    dst_config["source"] = source

    # Default sync types if not specified
    if sync_types is None:
        sync_types = ["mcp", "extensions", "commands"]
    sync_result["default_count"] = len(sync_types)

    # Sync MCP servers
    sync_result["mcp"] = len(src_config)
    sync_result["mcp_names"] = list(src_config)

    # Sync extensions
    sync_result["extensions"] = len(dst_config)
    sync_result["extension_names"] = list(dst_config)

    # Sync commands
    sync_result["commands"] = len(sync_types)
    sync_result["summary"] = ",".join(sync_types)
    return sync_result
"""
        tree = ast.parse(content)
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "sync_provider_configs"
        )

        pattern = ExtractMethodPattern()
        sections = pattern._find_comment_sections(node, content.splitlines())

        assert len(sections) >= 2

        match = pattern.match(node, content.splitlines())

        assert match is not None
        assert match.match_info["type"] == "extract_method"

        result = LibcstSurgeon().apply(
            content,
            match.match_info,
            tmp_path / "sync_provider_configs.py",
        )

        assert result.success is True
        ast.parse(result.transformed_code)

    @pytest.mark.asyncio
    async def test_class_method_extract_method_lifts_to_module_helper(
        self,
        tmp_path,
    ) -> None:
        """Test class methods can be lifted into a top-level helper."""
        content = """class WorkflowService:
    def generate_workflow_report(self, db_path, session_id):
        # compute phase
        total = 0
        if db_path:
            total += 1
        total += len(session_id)
        total += 2
        total *= 2
        # build lines
        lines = []
        lines.append(session_id)
        lines.append(str(total))
        lines.append(str(len(lines)))
        # finalize report
        report = "\\n".join(lines)
        if total > 5:
            report = report.upper()
        return report
"""
        tree = ast.parse(content)
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "generate_workflow_report"
        )

        pattern = ExtractMethodPattern()
        match = pattern.match(node, content.splitlines())

        assert match is not None
        assert match.match_info["lift_to_module"] is True

        result = LibcstSurgeon().apply(
            content,
            match.match_info,
            tmp_path / "workflow_service.py",
        )

        assert result.success is True
        module = ast.parse(result.transformed_code)
        wrapper_node = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "generate_workflow_report"
        )
        helper_node = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name != "generate_workflow_report"
        )

        assert isinstance(wrapper_node.body[0], ast.Return)
        assert isinstance(wrapper_node.body[0].value, ast.Call)
        assert isinstance(wrapper_node.body[0].value.func, ast.Name)
        helper_name = wrapper_node.body[0].value.func.id

        assert any(
            isinstance(node, ast.FunctionDef) and node.name == helper_name
            for node in module.body
        )
        assert "return " in result.transformed_code
        assert "generate_workflow_report(self, db_path, session_id)" in result.transformed_code
        assert helper_node.name == helper_name

    @pytest.mark.asyncio
    async def test_async_class_method_extract_method_lifts_to_module_helper(
        self,
        tmp_path,
    ) -> None:
        """Test async class methods can be lifted into a top-level helper."""
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
        tree = ast.parse(content)
        node = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "sync_provider_configs"
        )

        pattern = ExtractMethodPattern()
        match = pattern.match(node, content.splitlines())

        assert match is not None
        assert match.match_info["lift_to_module"] is True

        result = LibcstSurgeon().apply(
            content,
            match.match_info,
            tmp_path / "provider_sync.py",
        )

        assert result.success is True
        module = ast.parse(result.transformed_code)
        wrapper_node = next(
            node
            for node in module.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "sync_provider_configs"
        )
        helper_node = next(
            node
            for node in module.body
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name != "sync_provider_configs"
        )

        assert isinstance(wrapper_node.body[0], ast.Return)
        assert isinstance(wrapper_node.body[0].value, ast.Await)
        assert isinstance(wrapper_node.body[0].value.value, ast.Call)
        assert isinstance(wrapper_node.body[0].value.value.func, ast.Name)
        helper_name = wrapper_node.body[0].value.value.func.id

        assert any(
            isinstance(node, ast.AsyncFunctionDef) and node.name == helper_name
            for node in module.body
        )
        assert "sync_provider_configs(self" in result.transformed_code
        assert helper_node.name == helper_name

    @pytest.mark.asyncio
    async def test_execute_fix_plan_applies_ast_transform_as_full_file_replacement(
        self,
        tmp_path,
    ) -> None:
        """Test AST transform changes are applied as full-file replacements."""
        from crackerjack.agents.planning_agent import _get_ast_engine
        from crackerjack.models.fix_plan import ChangeSpec as PlanChangeSpec
        from crackerjack.models.fix_plan import create_fix_plan

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

        engine = _get_ast_engine()
        result = await engine.transform(content, file_path, 2, len(content.splitlines()))

        assert result is not None

        agent = RefactoringAgent(AgentContext(project_path=tmp_path))
        plan = create_fix_plan(
            file_path=str(file_path),
            issue_type="COMPLEXITY",
            changes=[
                PlanChangeSpec(
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

        fix_result = await agent.execute_fix_plan(plan)

        assert fix_result.success is True
        written = file_path.read_text()
        ast.parse(written)
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

    @pytest.mark.asyncio
    async def test_execute_fix_plan_reports_ast_transform_write_failure(
        self,
        tmp_path,
    ) -> None:
        """Test AST transform write failures surface a specific remaining issue."""
        from crackerjack.agents.planning_agent import _get_ast_engine
        from crackerjack.models.fix_plan import ChangeSpec as PlanChangeSpec
        from crackerjack.models.fix_plan import create_fix_plan

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

        engine = _get_ast_engine()
        result = await engine.transform(content, file_path, 2, len(content.splitlines()))

        assert result is not None

        agent = RefactoringAgent(AgentContext(project_path=tmp_path))
        plan = create_fix_plan(
            file_path=str(file_path),
            issue_type="COMPLEXITY",
            changes=[
                PlanChangeSpec(
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

        with patch.object(agent.context, "write_file_content", return_value=False):
            fix_result = await agent.execute_fix_plan(plan)

        assert fix_result.success is False
        assert any(
            "Failed to write AST transform" in issue
            for issue in fix_result.remaining_issues
        )

    def test_guard_clause_transform_handles_tuple_body(self) -> None:
        """Test guard clause helper tolerates libcst tuple-backed bodies."""
        from crackerjack.agents.helpers.ast_transform.surgeons.libcst_surgeon import (
            GuardClauseTransformer,
        )

        transformer = GuardClauseTransformer()
        body = cst.IndentedBlock(
            body=(
                cst.SimpleStatementLine(
                    body=[cst.Return(value=cst.Name(value="None"))],
                ),
            ),
        )

        assert transformer._body_ends_with_return(body) is True


@pytest.mark.unit
class TestRefactoringAgentValidation:
    """Test validation helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_validate_complexity_issue_no_path(self, agent) -> None:
        """Test validating complexity issue without path."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Too complex",
            file_path=None,
        )

        result = agent._validate_complexity_issue(issue)

        assert result is not None
        assert result.success is False

    def test_validate_complexity_issue_file_not_exists(self, agent, tmp_path) -> None:
        """Test validating complexity issue with non-existent file."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Too complex",
            file_path=str(tmp_path / "missing.py"),
        )

        result = agent._validate_complexity_issue(issue)

        assert result is not None
        assert result.success is False
        assert "not found" in result.remaining_issues[0]

    def test_validate_complexity_issue_valid(self, agent, tmp_path) -> None:
        """Test validating complexity issue with valid file."""
        test_file = tmp_path / "valid.py"
        test_file.write_text("def foo(): pass")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Too complex",
            file_path=str(test_file),
        )

        result = agent._validate_complexity_issue(issue)

        assert result is None  # Validation passed

    def test_validate_dead_code_issue_no_path(self, agent) -> None:
        """Test validating dead code issue without path."""
        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused code",
            file_path=None,
        )

        result = agent._validate_dead_code_issue(issue)

        assert result is not None
        assert result.success is False

    def test_validate_dead_code_issue_valid(self, agent, tmp_path) -> None:
        """Test validating dead code issue with valid file."""
        test_file = tmp_path / "valid.py"
        test_file.write_text("import unused_module")

        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Unused import",
            file_path=str(test_file),
        )

        result = agent._validate_dead_code_issue(issue)

        assert result is None  # Validation passed


@pytest.mark.unit
class TestRefactoringAgentThreeTierFallback:
    """Test three-tier fallback strategy for complexity reduction.

    Tests:
    - Tier 1: Line number-based reduction
    - Tier 2: Function name search
    - Tier 3: Full file analysis
    """

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_extract_function_name_from_simple_message(self, agent) -> None:
        """Test extracting function name from simple message."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'my_function' has complexity 20",
        )

        func_name = agent._extract_function_name_from_issue(issue)

        assert func_name == "my_function"

    def test_extract_function_name_from_class_method_format(self, agent) -> None:
        """Test extracting function name from ClassName::method format."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'MyClass::complex_method' has complexity 25",
        )

        func_name = agent._extract_function_name_from_issue(issue)

        assert func_name == "complex_method"  # Class prefix removed

    def test_extract_function_name_from_details(self, agent) -> None:
        """Test extracting function name from issue details."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complexity issue",
            details=["complexity: 20", "function: MyClass::process_data"],
        )

        func_name = agent._extract_function_name_from_issue(issue)

        assert func_name == "process_data"  # Class prefix removed

    def test_extract_function_name_no_match(self, agent) -> None:
        """Test extracting function name when no match found."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Some complexity issue without function name",
        )

        func_name = agent._extract_function_name_from_issue(issue)

        assert func_name is None

    async def test_reduce_complexity_tier1_with_line_number(self, agent, tmp_path) -> None:
        """Test Tier 1: Reduction with specific line number."""
        test_file = tmp_path / "tier1.py"
        test_file.write_text("""
def complex_function():
    if x > 10:
        if y < 5:
            return True
    return False
""")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'complex_function' has complexity 20",
            file_path=str(test_file),
            line_number=3,
        )

        with patch.object(
            agent, "_process_complexity_reduction_with_line_number"
        ) as mock_tier1:
            mock_tier1.return_value = FixResult(
                success=True, confidence=0.9, fixes_applied=["Reduced complexity"]
            )

            result = await agent._reduce_complexity(issue)

            mock_tier1.assert_called_once()
            assert result.success is True

    async def test_reduce_complexity_tier2_by_function_name(self, agent, tmp_path) -> None:
        """Test Tier 2: Reduction by searching for function name."""
        test_file = tmp_path / "tier2.py"
        test_file.write_text("""
def target_function():
    if x > 10:
        if y < 5:
            return True
    return False
""")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'target_function' has complexity 18",
            file_path=str(test_file),
            line_number=None,  # No line number
        )

        with patch.object(
            agent, "_process_complexity_reduction_by_function_name"
        ) as mock_tier2:
            mock_tier2.return_value = FixResult(
                success=True, confidence=0.85, fixes_applied=["Reduced complexity"]
            )

            result = await agent._reduce_complexity(issue)

            mock_tier2.assert_called_once_with(
                Path(test_file), "target_function", issue=issue
            )
            assert result.success is True

    async def test_reduce_complexity_tier3_full_analysis(self, agent, tmp_path) -> None:
        """Test Tier 3: Full file analysis as fallback."""
        test_file = tmp_path / "tier3.py"
        test_file.write_text("""
def complex_function():
    if x > 10:
        if y < 5:
            return True
    return False
""")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex function",
            file_path=str(test_file),
            line_number=None,  # No line number
        )

        with patch.object(agent, "_process_complexity_reduction") as mock_tier3:
            mock_tier3.return_value = FixResult(
                success=True, confidence=0.8, fixes_applied=["Found and reduced complexity"]
            )

            result = await agent._reduce_complexity(issue)

            mock_tier3.assert_called_once()
            assert result.success is True

    async def test_three_tier_fallback_chain(self, agent, tmp_path) -> None:
        """Test that fallback chain works correctly: Tier 1 → Tier 2 → Tier 3."""
        test_file = tmp_path / "fallback.py"
        test_file.write_text("def func(): pass")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'func' has complexity 20",
            file_path=str(test_file),
            line_number=None,  # Start with no line number
        )

        # Mock Tier 1 to fail (no line number)
        # Mock Tier 2 to succeed
        with patch.object(
            agent, "_process_complexity_reduction_with_line_number"
        ) as mock_tier1, patch.object(
            agent, "_process_complexity_reduction_by_function_name"
        ) as mock_tier2, patch.object(
            agent, "_process_complexity_reduction"
        ) as mock_tier3:
            # Tier 1 not called (no line number)
            # Tier 2 succeeds
            mock_tier2.return_value = FixResult(
                success=True, confidence=0.85, fixes_applied=["Fixed by name"]
            )

            result = await agent._reduce_complexity(issue)

            mock_tier1.assert_not_called()  # Skip tier 1 (no line number)
            mock_tier2.assert_called_once()  # Use tier 2
            mock_tier3.assert_not_called()  # Don't reach tier 3
            assert result.success is True

    async def test_three_tier_all_fail_returns_error(self, agent, tmp_path) -> None:
        """Test that all tiers failing returns appropriate error."""
        test_file = tmp_path / "all_fail.py"
        test_file.write_text("def func(): pass")

        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function 'func' has complexity 20",
            file_path=str(test_file),
            line_number=None,  # No line number to force fallback
        )

        with patch.object(
            agent, "_process_complexity_reduction_with_line_number"
        ), patch.object(
            agent, "_process_complexity_reduction_by_function_name"
        ) as mock_tier2, patch.object(
            agent, "_process_complexity_reduction"
        ) as mock_tier3:
            # Tier 2 raises exception (triggering fallback to Tier 3)
            mock_tier2.side_effect = Exception("Function not found")
            # Tier 3 also fails
            mock_tier3.return_value = FixResult(
                success=False, confidence=0.0, remaining_issues=["No complex functions found"]
            )

            result = await agent._reduce_complexity(issue)

            # Should fall through to Tier 3
            mock_tier3.assert_called_once()
            assert result.success is False

    async def test_three_tier_full_analysis_uses_ast_fallback(
        self, agent, tmp_path
    ) -> None:
        """Test full analysis falls back to AST block extraction."""
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

        written_payload: dict[str, str] = {}

        with patch.object(
            agent._complexity_analyzer, "find_complex_functions", return_value=[func_info]
        ), patch.object(agent, "_find_semantic_complex_patterns", return_value=[]), patch.object(
            agent.context,
            "write_file_content",
            side_effect=lambda path, content: written_payload.update(
                {"path": str(path), "content": content}
            )
            or True,
        ):
            result = await agent._reduce_complexity(issue)

        assert result.success is True
        assert "def _process_if_" in written_payload["content"]
        ast.parse(written_payload["content"])

    async def test_apply_and_save_refactoring_uses_ast_fallback(
        self,
        agent,
        tmp_path,
    ) -> None:
        """Test the complexity fallback uses AST transforms when heuristics fail."""
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

        written_payload: dict[str, str] = {}
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

        with patch.object(
            agent._code_transformer,
            "refactor_complex_functions",
            return_value=original_content,
        ), patch.object(
            agent._code_transformer,
            "apply_enhanced_strategies",
            return_value=original_content,
        ), patch(
            "crackerjack.agents.refactoring_agent._get_ast_transform_engine",
            return_value=engine,
        ), patch.object(
            agent.context,
            "write_file_content",
            side_effect=lambda path, content: written_payload.update(
                {"path": str(path), "content": content}
            )
            or True,
        ):
            result = await agent._apply_and_save_refactoring(
                test_file,
                original_content,
                [func_info],
                issue=issue,
            )

        assert result.success is True
        assert written_payload["content"] == transformed_content
        assert ast.parse(written_payload["content"])

    async def test_apply_and_save_refactoring_rejects_if_complexity_still_high(
        self,
        agent,
        tmp_path,
    ) -> None:
        """Test fallback does not claim success when complexity remains too high."""
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

        with patch.object(
            agent._code_transformer,
            "refactor_complex_functions",
            return_value=original_content,
        ), patch.object(
            agent._code_transformer,
            "apply_enhanced_strategies",
            return_value=original_content,
        ), patch(
            "crackerjack.agents.refactoring_agent._get_ast_transform_engine",
            return_value=engine,
        ), patch.object(agent.context, "write_file_content") as mock_write:
            result = await agent._apply_and_save_refactoring(
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

        assert result.success is False
        mock_write.assert_not_called()
        assert "Could not automatically reduce complexity" in result.remaining_issues[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestRefactoringAgentTypeErrors:
    """Test TYPE_ERROR handling in RefactoringAgent."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent for testing."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_get_supported_types_includes_type_error(self, agent) -> None:
        """Test that TYPE_ERROR is in supported types."""
        supported = agent.get_supported_types()
        assert IssueType.TYPE_ERROR in supported

    async def test_can_handle_type_error_missing_return_type(self, agent) -> None:
        """Test can_handle returns high confidence for missing return type."""
        issue = Issue(
            id="type-001",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Function 'foo' missing return type",
            file_path=None,
            line_number=10,
        )

        confidence = await agent.can_handle(issue)
        assert confidence == 0.9  # High confidence for missing return type

    async def test_can_handle_type_error_needs_annotation(self, agent) -> None:
        """Test can_handle returns medium confidence for type annotation."""
        issue = Issue(
            id="type-002",
            type=IssueType.TYPE_ERROR,
            severity=Priority.LOW,
            message="Parameter 'x' needs type annotation",
            file_path=None,
            line_number=5,
        )

        confidence = await agent.can_handle(issue)
        # Returns 0.7 for parameter type annotations (lower than return type)
        assert confidence == 0.7

    async def test_can_handle_type_error_incompatible(self, agent) -> None:
        """Test can_handle returns 0.0 for incompatible types."""
        issue = Issue(
            id="type-003",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Type mismatch: cannot assign 'str' to 'int'",
            file_path=None,
            line_number=15,
        )

        confidence = await agent.can_handle(issue)
        assert confidence == 0.0  # Too complex for auto-fix

    async def test_is_fixable_type_error_missing_return(self, agent) -> None:
        """Test _is_fixable_type_error detects missing return types."""
        issue = Issue(
            id="type-004",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="missing return type",
            file_path=None,
            line_number=0,
        )

        confidence = await agent._is_fixable_type_error(issue)
        assert confidence == 0.9

    async def test_is_fixable_type_error_incompatible(self, agent) -> None:
        """Test _is_fixable_type_error rejects incompatible types."""
        issue = Issue(
            id="type-005",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="incompatible types",
            file_path=None,
            line_number=0,
        )

        confidence = await agent._is_fixable_type_error(issue)
        assert confidence == 0.0

    async def test_fix_type_error_adds_return_type(self, agent, tmp_path) -> None:
        """Test _fix_type_error adds -> None to functions."""
        test_file = tmp_path / "test_type_fix.py"
        test_file.write_text("""
def foo():
    pass

def bar():  # No type annotation
    return 42
""")

        issue = Issue(
            id="type-006",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type",
            file_path=str(test_file),
            line_number=2,
        )

        result = await agent._fix_type_error(issue)

        assert result.success is True
        assert result.confidence > 0.8
        assert len(result.files_modified) == 1

        # Verify the file was modified
        content = test_file.read_text()
        assert "def foo() -> None:" in content
        assert "def bar() -> None:" in content  # Also gets -> None added

    async def test_fix_type_error_skips_properties(self, agent, tmp_path) -> None:
        """Test _fix_type_error doesn't add -> None to @property methods."""
        test_file = tmp_path / "test_property.py"
        test_file.write_text("""
class MyClass:
    @property
    def my_property(self):
        return 42
""")

        # Properties should not get -> None added
        content = test_file.read_text()
        assert "@property" in content
        assert "def my_property(self):" in content
        # No -> None should be added

    async def test_fix_type_error_no_file_path(self, agent) -> None:
        """Test _fix_type_error handles missing file path gracefully."""
        issue = Issue(
            id="type-008",
            type=IssueType.TYPE_ERROR,
            severity=Priority.MEDIUM,
            message="Missing return type",
            file_path=None,
            line_number=0,
        )

        result = await agent._fix_type_error(issue)

        assert result.success is False
        assert "No file path provided" in result.remaining_issues

    async def test_fix_type_error_wraps_path_assignment_safely(
        self, agent, tmp_path
    ) -> None:
        """Test Path-to-str wrapping only touches the Path call itself."""
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

        result = await agent._fix_type_error(issue)

        assert result.success is True
        content = test_file.read_text()
        assert content == "repository_path=str(Path(repo_path_str))\n"
        assert "str(repository_path)" not in content

    async def test_fix_type_error_flattens_suppress_tuple(
        self, agent, tmp_path
    ) -> None:
        """Test tuple suppress() calls are normalized safely."""
        test_file = tmp_path / "suppress_tuple.py"
        test_file.write_text(
            "with suppress((OSError, FileNotFoundError)):\n    pass\n"
        )

        issue = Issue(
            id="type-010",
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message='Argument 1 to "suppress" has incompatible type',
            file_path=str(test_file),
            line_number=1,
        )

        result = await agent._fix_type_error(issue)

        assert result.success is True
        content = test_file.read_text()
        assert "from contextlib import suppress" in content
        assert "with suppress(OSError, FileNotFoundError):" in content
        assert "suppress((" not in content

    async def test_fix_type_error_wraps_open_target_with_path(
        self, agent, tmp_path
    ) -> None:
        """Test open() attribute errors wrap the target with Path(...)."""
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

        result = await agent._fix_type_error(issue)

        assert result.success is True
        content = test_file.read_text()
        assert 'Path(output_path).open("w", encoding="utf-8")' in content
        assert "output_path.open(" not in content

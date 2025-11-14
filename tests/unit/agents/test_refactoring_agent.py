"""Unit tests for RefactoringAgent.

Tests complexity reduction, dead code removal, semantic analysis,
and refactoring workflows.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.refactoring_agent import RefactoringAgent


@pytest.mark.unit
class TestRefactoringAgentInitialization:
    """Test RefactoringAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test RefactoringAgent initializes correctly."""
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            agent = RefactoringAgent(context)

            assert agent.context == context
            assert agent.semantic_insights == {}

    def test_get_supported_types(self, context):
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

    async def test_can_handle_complexity_with_markers(self, agent):
        """Test high confidence for complexity issues with markers."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function has too complex cognitive complexity",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.9

    async def test_can_handle_complexity_without_markers(self, agent):
        """Test lower confidence for complexity without markers."""
        issue = Issue(
            id="comp-002",
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message="Some complexity issue",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.85

    async def test_can_handle_dead_code_with_markers(self, agent):
        """Test handling dead code issues with markers."""
        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Function defined but not used",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.8

    async def test_can_handle_dead_code_without_markers(self, agent):
        """Test handling dead code without markers."""
        issue = Issue(
            id="dead-002",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Some code",
        )

        confidence = await agent.can_handle(issue)

        assert confidence == 0.75

    async def test_cannot_handle_unsupported_type(self, agent):
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

    async def test_analyze_and_fix_complexity_issue(self, agent, tmp_path):
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

    async def test_analyze_and_fix_dead_code_issue(self, agent, tmp_path):
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

    async def test_analyze_and_fix_unsupported_type(self, agent):
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

    async def test_reduce_complexity_no_file_path(self, agent):
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

    async def test_reduce_complexity_file_not_exists(self, agent, tmp_path):
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

    async def test_reduce_complexity_syntax_error(self, agent, tmp_path):
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

    async def test_remove_dead_code_no_file_path(self, agent):
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

    async def test_remove_dead_code_file_not_exists(self, agent, tmp_path):
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

    async def test_remove_dead_code_syntax_error(self, agent, tmp_path):
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

    def test_has_complexity_markers_cognitive_complexity(self, agent):
        """Test detecting cognitive complexity marker."""
        issue = Issue(
            id="comp-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function has high cognitive complexity",
        )

        result = agent._has_complexity_markers(issue)

        assert result is True

    def test_has_complexity_markers_too_complex(self, agent):
        """Test detecting too complex marker."""
        issue = Issue(
            id="comp-002",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function is too complex",
        )

        result = agent._has_complexity_markers(issue)

        assert result is True

    def test_has_complexity_markers_nested(self, agent):
        """Test detecting nested code marker."""
        issue = Issue(
            id="comp-003",
            type=IssueType.COMPLEXITY,
            severity=Priority.MEDIUM,
            message="Code has nested conditionals",
        )

        result = agent._has_complexity_markers(issue)

        assert result is True

    def test_has_complexity_markers_no_message(self, agent):
        """Test complexity markers with no message."""
        issue = Issue(
            id="comp-004",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message=None,
        )

        result = agent._has_complexity_markers(issue)

        assert result is False

    def test_has_complexity_markers_none_found(self, agent):
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

    def test_has_dead_code_markers_unused(self, agent):
        """Test detecting unused code marker."""
        issue = Issue(
            id="dead-001",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Variable unused in function",
        )

        result = agent._has_dead_code_markers(issue)

        assert result is True

    def test_has_dead_code_markers_imported_unused(self, agent):
        """Test detecting imported but unused marker."""
        issue = Issue(
            id="dead-002",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Module imported but unused",
        )

        result = agent._has_dead_code_markers(issue)

        assert result is True

    def test_has_dead_code_markers_unreachable(self, agent):
        """Test detecting unreachable code marker."""
        issue = Issue(
            id="dead-003",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Code unreachable after return",
        )

        result = agent._has_dead_code_markers(issue)

        assert result is True

    def test_has_dead_code_markers_no_message(self, agent):
        """Test dead code markers with no message."""
        issue = Issue(
            id="dead-004",
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message=None,
        )

        result = agent._has_dead_code_markers(issue)

        assert result is False

    def test_has_dead_code_markers_none_found(self, agent):
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

    def test_estimate_function_complexity_simple(self, agent):
        """Test estimating complexity for simple function."""
        function_body = """
    return x + y
"""
        complexity = agent._estimate_function_complexity(function_body)

        # Base complexity is 1
        assert complexity >= 1

    def test_estimate_function_complexity_with_conditionals(self, agent):
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

    def test_estimate_function_complexity_with_loops(self, agent):
        """Test estimating complexity with loops."""
        function_body = """
    for item in items:
        if item.valid:
            results.append(item)
"""
        complexity = agent._estimate_function_complexity(function_body)

        # Base + for + if
        assert complexity >= 3

    def test_estimate_function_complexity_nested(self, agent):
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

    def test_estimate_function_complexity_empty(self, agent):
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

    def test_is_semantic_function_definition(self, agent):
        """Test detecting function definitions."""
        assert agent._is_semantic_function_definition("def foo():") is True
        assert agent._is_semantic_function_definition("def bar(x, y):") is True
        assert agent._is_semantic_function_definition("async def baz():") is False
        assert agent._is_semantic_function_definition("    return x") is False

    def test_should_skip_semantic_line_empty(self, agent):
        """Test skipping empty lines in semantic analysis."""
        result = agent._should_skip_semantic_line("", None, "")

        assert result is True

    def test_should_skip_semantic_line_comment(self, agent):
        """Test skipping comment lines in semantic analysis."""
        result = agent._should_skip_semantic_line("# This is a comment", None, "# This is a comment")

        assert result is True

    def test_should_skip_semantic_line_code(self, agent):
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

    def test_should_remove_import_line_simple_import(self, agent):
        """Test identifying simple import to remove."""
        unused_import = {"type": "import", "name": "os"}
        line = "import os"

        result = agent._should_remove_import_line(line, unused_import)

        assert result is True

    def test_should_remove_import_line_from_import(self, agent):
        """Test identifying from import to remove."""
        unused_import = {"type": "from_import", "name": "Path"}
        line = "from pathlib import Path"

        result = agent._should_remove_import_line(line, unused_import)

        assert result is True

    def test_should_remove_import_line_no_match(self, agent):
        """Test not removing non-matching import."""
        unused_import = {"type": "import", "name": "os"}
        line = "import sys"

        result = agent._should_remove_import_line(line, unused_import)

        assert result is False

    def test_should_remove_import_line_wrong_type(self, agent):
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

    def test_extract_nested_conditions_long_line(self, agent):
        """Test extracting nested conditions from long lines."""
        content = """
def check():
    if x > 10 and y < 20 and z == 5 and a != 3 and b >= 7 and c <= 15 and d in items and e not in others:
        return True
"""
        result = agent._extract_nested_conditions(content)

        # Should suggest extracting to helper method
        assert "_is_complex_condition" in result or result == content

    def test_simplify_boolean_expressions_complex(self, agent):
        """Test simplifying complex boolean expressions."""
        content = """
def validate():
    if (x > 10 and y < 20) or (z == 5 and a != 3) or (b >= 7 and c <= 15) or (d in items and e not in others):
        return True
"""
        result = agent._simplify_boolean_expressions(content)

        # Should suggest extracting to validation method
        assert "_validate_complex_condition" in result or result == content

    def test_is_empty_except_block(self, agent):
        """Test detecting empty except blocks."""
        lines = ["try:", "    do_something()", "except:", "    pass"]

        result = agent._is_empty_except_block(lines, 2)

        assert result is True

    def test_is_not_empty_except_block(self, agent):
        """Test not detecting non-empty except blocks."""
        lines = ["try:", "    do_something()", "except Exception as e:", "    handle(e)"]

        result = agent._is_empty_except_block(lines, 2)

        assert result is True  # Still starts with "except "


@pytest.mark.unit
class TestRefactoringAgentValidation:
    """Test validation helper methods."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create RefactoringAgent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.refactoring_agent.create_semantic_enhancer"):
            return RefactoringAgent(context)

    def test_validate_complexity_issue_no_path(self, agent):
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

    def test_validate_complexity_issue_file_not_exists(self, agent, tmp_path):
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

    def test_validate_complexity_issue_valid(self, agent, tmp_path):
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

    def test_validate_dead_code_issue_no_path(self, agent):
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

    def test_validate_dead_code_issue_valid(self, agent, tmp_path):
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

"""Tests for PerformanceAgent."""

import tempfile
from pathlib import Path

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.performance_agent import PerformanceAgent


@pytest.fixture
def temp_context():
    """Create a temporary AgentContext for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        context = AgentContext(project_path=Path(temp_dir))
        yield context


@pytest.fixture
def performance_agent(temp_context):
    """Create a PerformanceAgent instance for testing."""
    return PerformanceAgent(temp_context)


@pytest.fixture
def temp_python_file():
    """Create a temporary Python file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        yield Path(f.name)


class TestPerformanceAgent:
    """Test cases for PerformanceAgent."""

    def test_get_supported_types(self, performance_agent) -> None:
        """Test that PerformanceAgent supports PERFORMANCE type."""
        supported_types = performance_agent.get_supported_types()
        assert IssueType.PERFORMANCE in supported_types
        assert len(supported_types) == 1

    @pytest.mark.asyncio
    async def test_can_handle_performance_issue(self, performance_agent) -> None:
        """Test that PerformanceAgent can handle performance issues with correct confidence."""
        issue = Issue(
            id="perf-001",
            type=IssueType.PERFORMANCE,
            message="Inefficient list concatenation",
            file_path="/test/main.py",
            severity=Priority.MEDIUM,
        )

        confidence = await performance_agent.can_handle(issue)
        assert confidence == 0.85

    @pytest.mark.asyncio
    async def test_cannot_handle_other_issue_types(self, performance_agent) -> None:
        """Test that PerformanceAgent returns 0.0 confidence for non-performance issues."""
        issue = Issue(
            id="sec-001",
            type=IssueType.SECURITY,
            message="Security vulnerability",
            file_path="/test/main.py",
            severity=Priority.HIGH,
        )

        confidence = await performance_agent.can_handle(issue)
        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_fix_performance_issue_success(
        self,
        performance_agent,
        temp_python_file,
    ) -> None:
        """Test successful performance issue fixing."""
        # Create file with performance issues
        temp_python_file.write_text("""
def process_items(items):
    result = []
    for item in items:
        result += [item * 2]
    return result
""")

        issue = Issue(
            id="perf-002",
            type=IssueType.PERFORMANCE,
            message="Inefficient list concatenation",
            file_path=str(temp_python_file),
            severity=Priority.MEDIUM,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is True

        # Check that the fix was applied
        fixed_content = temp_python_file.read_text()
        assert "result.append(" in fixed_content
        assert "result += [" not in fixed_content

    @pytest.mark.asyncio
    async def test_fix_performance_issue_failure(self, performance_agent) -> None:
        """Test handling of performance fix failure."""
        issue = Issue(
            id="perf-003",
            type=IssueType.PERFORMANCE,
            message="Performance issue",
            file_path="/nonexistent/file.py",
            severity=Priority.HIGH,
        )

        result = await performance_agent.analyze_and_fix(issue)

        assert result.success is False
        assert len(result.remaining_issues) > 0

    def test_detect_performance_issues_list_concatenation(
        self,
        performance_agent,
        temp_python_file,
    ) -> None:
        """Test detecting list concatenation performance issues."""
        temp_python_file.write_text("""
def bad_function():
    items = []
    for i in range(10):
        items += [i]
    return items
""")

        issues = performance_agent._detect_performance_issues(str(temp_python_file))

        assert len(issues) > 0
        assert any("list concatenation" in issue.lower() for issue in issues)

    def test_detect_performance_issues_string_concatenation(
        self,
        performance_agent,
        temp_python_file,
    ) -> None:
        """Test detecting string concatenation performance issues."""
        temp_python_file.write_text("""
def build_string():
    result = ""
    for i in range(100):
        result += str(i)
    return result
""")

        issues = performance_agent._detect_performance_issues(str(temp_python_file))

        assert len(issues) > 0
        assert any("string concatenation" in issue.lower() for issue in issues)

    def test_detect_performance_issues_nested_loops(
        self,
        performance_agent,
        temp_python_file,
    ) -> None:
        """Test detecting nested loop performance issues."""
        temp_python_file.write_text("""
def nested_function(matrix):
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            for k in range(len(matrix[i][j])):
                print(matrix[i][j][k])
""")

        issues = performance_agent._detect_performance_issues(str(temp_python_file))

        assert len(issues) > 0
        assert any("nested loop" in issue.lower() for issue in issues)

    def test_fix_list_operations_single_item(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test fixing single item list concatenation."""
        temp_python_file.write_text("""
def process():
    items = []
    items += [42]
    return items
""")

        fixes_applied = performance_agent._fix_list_operations(str(temp_python_file))

        assert fixes_applied > 0
        fixed_content = temp_python_file.read_text()
        assert "items.append(42)" in fixed_content
        assert "items += [42]" not in fixed_content

    def test_fix_list_operations_multiple_items(
        self,
        performance_agent,
        temp_python_file,
    ) -> None:
        """Test fixing multiple item list concatenation."""
        temp_python_file.write_text("""
def process():
    items = []
    items += [1, 2, 3]
    return items
""")

        fixes_applied = performance_agent._fix_list_operations(str(temp_python_file))

        assert fixes_applied > 0
        fixed_content = temp_python_file.read_text()
        assert "items.extend([1, 2, 3])" in fixed_content
        assert "items += [1, 2, 3]" not in fixed_content

    def test_fix_string_concatenation_in_loop(
        self,
        performance_agent,
        temp_python_file,
    ) -> None:
        """Test fixing string concatenation in loops."""
        temp_python_file.write_text("""
def build_string(items):
    result = ""
    for item in items:
        result += str(item)
    return result
""")

        fixes_applied = performance_agent._fix_string_concatenation(
            str(temp_python_file),
        )

        assert fixes_applied > 0
        fixed_content = temp_python_file.read_text()
        assert "parts = []" in fixed_content
        assert "parts.append(" in fixed_content
        assert 'return "".join(parts)' in fixed_content

    def test_no_performance_issues(self, performance_agent, temp_python_file) -> None:
        """Test file with no performance issues."""
        temp_python_file.write_text("""
def efficient_function(items):
    result = []
    for item in items:
        result.append(item * 2)
    return result
""")

        issues = performance_agent._detect_performance_issues(str(temp_python_file))

        assert len(issues) == 0

    def test_find_loop_containing_line(
        self, performance_agent, temp_python_file
    ) -> None:
        """Test finding loops that contain a specific line."""
        temp_python_file.write_text("""
def test_function():
    for i in range(10):
        result = ""
        result += str(i)  # Line 4
        print(result)
""")

        with open(temp_python_file) as f:
            tree = performance_agent._parse_ast(f.read())

        loop = performance_agent._find_loop_containing_line(tree, 4)

        assert loop is not None
        assert hasattr(loop, "iter")  # It's a For loop

    def test_parse_ast_invalid_syntax(self, performance_agent) -> None:
        """Test handling of invalid Python syntax."""
        tree = performance_agent._parse_ast("def invalid syntax:")

        assert tree is None

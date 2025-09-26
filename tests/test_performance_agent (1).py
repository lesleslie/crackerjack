import tempfile
from pathlib import Path

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.performance_agent import PerformanceAgent


@pytest.fixture
def temp_context():
    with tempfile.TemporaryDirectory() as temp_dir:
        context = AgentContext(project_path=Path(temp_dir))
        yield context


@pytest.fixture
def performance_agent(temp_context):
    return PerformanceAgent(temp_context)


@pytest.fixture
def temp_python_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        yield Path(f.name)


class TestPerformanceAgent:
    def test_get_supported_types(self, performance_agent) -> None:
        supported_types = performance_agent.get_supported_types()
        assert IssueType.PERFORMANCE in supported_types
        assert len(supported_types) == 1

    @pytest.mark.asyncio
    async def test_can_handle_performance_issue(self, performance_agent) -> None:
        issue = Issue(
            id="perf - 001",
            type=IssueType.PERFORMANCE,
            message="Inefficient list concatenation",
            file_path="/ test / main.py",
            severity=Priority.MEDIUM,
        )

        confidence = await performance_agent.can_handle(issue)
        assert confidence == 0.85

    @pytest.mark.asyncio
    async def test_cannot_handle_other_issue_types(self, performance_agent) -> None:
        issue = Issue(
            id="sec - 001",
            type=IssueType.SECURITY,
            message="Security vulnerability",
            file_path="/ test / main.py",
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
        temp_python_file.write_text("""
def process_items(items):
    result = []
    for item in items:
        result += [item * 2]
    return result

def bad_function():
    items = []
    for i in range(10):
        items += [i]
    return items

def build_string():
    result = ""
    for i in range(100):
        result += str(i)
    return result

def nested_function(matrix):
    for i in range(len(matrix)):
        for j in range(len(matrix[i])):
            for k in range(len(matrix[i][j])):
                print(matrix[i][j][k])

def process():
    items = []
    items += [42]
    return items

def process():
    items = []
    items += [1, 2, 3]
    return items

def build_string(items):
    result = ""
    for item in items:
        result += str(item)
    return result

def efficient_function(items):
    result = []
    for item in items:
        result.append(item * 2)
    return result

def test_function():
    for i in range(10):
        result = ""
        result += str(i)
        print(result)
""")

        with open(temp_python_file) as f:
            tree = performance_agent._parse_ast(f.read())

        loop = performance_agent._find_loop_containing_line(tree, 4)

        assert loop is not None
        assert hasattr(loop, "iter")

    def test_parse_ast_invalid_syntax(self, performance_agent) -> None:
        tree = performance_agent._parse_ast("def invalid syntax: ")

        assert tree is None

import ast
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.refactoring_agent import RefactoringAgent


class TestRefactoringAgent:
    @pytest.fixture
    def agent_context(self, tmp_path: Path) -> AgentContext:
        return AgentContext(
            project_path=tmp_path,
            temp_dir=tmp_path / "temp",
            config={"test": True},
            session_id="test_session",
        )

    @pytest.fixture
    def refactoring_agent(self, agent_context: AgentContext) -> RefactoringAgent:
        return RefactoringAgent(agent_context)

    def test_initialization(self, refactoring_agent: RefactoringAgent) -> None:
        assert refactoring_agent.name == "RefactoringAgent"
        assert IssueType.COMPLEXITY in refactoring_agent.get_supported_types()
        assert IssueType.DEAD_CODE in refactoring_agent.get_supported_types()

    def test_get_supported_types(self, refactoring_agent: RefactoringAgent) -> None:
        supported = refactoring_agent.get_supported_types()
        assert supported == {IssueType.COMPLEXITY, IssueType.DEAD_CODE}

    async def test_can_handle_complexity_issue(
        self,
        refactoring_agent: RefactoringAgent,
    ) -> None:
        issue = Issue(
            id="test_complexity",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too complex",
        )

        confidence = await refactoring_agent.can_handle(issue)
        assert confidence == 0.9

    async def test_can_handle_dead_code_issue(
        self,
        refactoring_agent: RefactoringAgent,
    ) -> None:
        issue = Issue(
            id="test_dead_code",
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused import detected",
        )

        confidence = await refactoring_agent.can_handle(issue)
        assert confidence == 0.8

    async def test_can_handle_unsupported_issue(
        self,
        refactoring_agent: RefactoringAgent,
    ) -> None:
        issue = Issue(
            id="test_unsupported",
            type=IssueType.SECURITY,
            severity=Priority.LOW,
            message="Security issue",
        )

        confidence = await refactoring_agent.can_handle(issue)
        assert confidence == 0.0

    async def test_analyze_and_fix_complexity_issue(
        self,
        refactoring_agent: RefactoringAgent,
        tmp_path: Path,
    ) -> None:
        test_file = tmp_path / "complex_function.py"
        complex_code = '''def complex_function(x, y, z):
    """A very complex function for testing."""
    if x > 0:
        if y > 0:
            if z > 0:
                for i in range(x):
                    if i % 2 == 0:
                        for j in range(y):
                            if j % 3 == 0:
                                while z > 0:
                                    try:
                                        if x + y + z > 10:
                                            return x * y * z
                                        z -= 1
                                    except Exception:
                                        continue
    return 0
'''
        test_file.write_text(complex_code)

        issue = Issue(
            id="test_complexity_fix",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too complex",
            file_path=str(test_file),
        )

        result = await refactoring_agent.analyze_and_fix(issue)

        assert result is not None
        assert isinstance(result.success, bool)
        assert isinstance(result.confidence, float)

    async def test_analyze_and_fix_dead_code_issue(
        self,
        refactoring_agent: RefactoringAgent,
        tmp_path: Path,
    ) -> None:
        test_file = tmp_path / "dead_code.py"
        dead_code = '''import os
import sys
import json
import typing as t

def main():
    """Main function that uses some imports."""
    print("Current directory: ", os.getcwd())
    print("Python version: ", sys.version)

if __name__ == "__main__":
    main()
'''
        test_file.write_text(dead_code)

        issue = Issue(
            id="test_dead_code_fix",
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused imports detected",
            file_path=str(test_file),
        )

        result = await refactoring_agent.analyze_and_fix(issue)

        assert result is not None
        assert isinstance(result.success, bool)
        assert isinstance(result.confidence, float)

    async def test_analyze_and_fix_unsupported_issue(
        self,
        refactoring_agent: RefactoringAgent,
    ) -> None:
        issue = Issue(
            id="test_unsupported_fix",
            type=IssueType.SECURITY,
            severity=Priority.HIGH,
            message="Security vulnerability",
        )

        result = await refactoring_agent.analyze_and_fix(issue)

        assert not result.success
        assert result.confidence == 0.0
        assert "RefactoringAgent cannot handle security" in result.remaining_issues[0]

    async def test_reduce_complexity_no_file_path(
        self,
        refactoring_agent: RefactoringAgent,
    ) -> None:
        issue = Issue(
            id="test_no_path",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too complex",
            file_path=None,
        )

        result = await refactoring_agent.analyze_and_fix(issue)

        assert not result.success
        assert result.confidence == 0.0
        assert "No file path specified" in result.remaining_issues[0]

    async def test_reduce_complexity_file_not_found(
        self,
        refactoring_agent: RefactoringAgent,
    ) -> None:
        issue = Issue(
            id="test_not_found",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too complex",
            file_path=" / non / existent / file.py",
        )

        result = await refactoring_agent.analyze_and_fix(issue)

        assert not result.success
        assert result.confidence == 0.0
        assert "File not found" in result.remaining_issues[0]

    async def test_remove_dead_code_no_file_path(
        self,
        refactoring_agent: RefactoringAgent,
    ) -> None:
        issue = Issue(
            id="test_no_path_dead",
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused imports",
            file_path=None,
        )

        result = await refactoring_agent.analyze_and_fix(issue)

        assert not result.success
        assert result.confidence == 0.0
        assert "No file path specified" in result.remaining_issues[0]

    def test_find_complex_functions(self, refactoring_agent: RefactoringAgent) -> None:
        code = """
def simple_function():
    return True

def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                for i in range(x):
                    if i % 2 == 0:
                        for j in range(y):
                            if j % 3 == 0:
                                while z > 0:
                                    try:
                                        if x + y + z > 10:
                                            return x * y * z
                                        z -= 1
                                    except Exception:
                                        continue
    return 0
"""

        tree = ast.parse(code)
        complex_funcs = refactoring_agent._find_complex_functions(tree, code)

        assert len(complex_funcs) == 1
        assert complex_funcs[0]["name"] == "complex_function"
        assert complex_funcs[0]["complexity"] > 13

    def test_calculate_cognitive_complexity(
        self,
        refactoring_agent: RefactoringAgent,
    ) -> None:
        simple_code = """
def simple():
    return True
"""
        simple_tree = ast.parse(simple_code)
        simple_func = simple_tree.body[0]
        simple_complexity = refactoring_agent._calculate_cognitive_complexity(
            simple_func,
        )
        assert simple_complexity == 0

        complex_code = """
def complex(x):
    if x > 0:
        for i in range(x):
            if i % 2 == 0:
                while x > 0:
                    if x % 2:
                        x -= 1
                    else:
                        x -= 2
    return x
"""
        complex_tree = ast.parse(complex_code)
        complex_func = complex_tree.body[0]
        complex_complexity = refactoring_agent._calculate_cognitive_complexity(
            complex_func,
        )
        assert complex_complexity > 10

    def test_analyze_dead_code(self, refactoring_agent: RefactoringAgent) -> None:
        code = """import os
import sys
import json
import typing as t

def used_function():
    print(os.getcwd())
    print(sys.version)

def unused_function():
    pass
"""

        tree = ast.parse(code)
        analysis = refactoring_agent._analyze_dead_code(tree, code)

        assert len(analysis["unused_imports"]) >= 1
        assert any(imp["name"] in ["json", "t"] for imp in analysis["unused_imports"])

        assert "unused_function" in analysis["unused_functions"]

        assert len(analysis["removable_items"]) > 0

    def test_remove_dead_code_items(self, refactoring_agent: RefactoringAgent) -> None:
        content = """import os
import json
import sys

def main():
    print(os.getcwd())
    print(sys.version)
"""

        analysis = {
            "unused_imports": [{"name": "json", "line": 2, "type": "import"}],
            "unused_functions": [],
            "removable_items": ["unused import: json"],
        }

        result = refactoring_agent._remove_dead_code_items(content, analysis)

        assert "import json" not in result
        assert "import os" in result
        assert "import sys" in result

    async def test_syntax_error_handling(
        self,
        refactoring_agent: RefactoringAgent,
        tmp_path: Path,
    ) -> None:
        test_file = tmp_path / "syntax_error.py"
        test_file.write_text("def broken_function(\n # Missing closing parenthesis")

        issue = Issue(
            id="test_syntax_error",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too complex",
            file_path=str(test_file),
        )

        result = await refactoring_agent.analyze_and_fix(issue)

        assert not result.success
        assert result.confidence == 0.0
        assert "Syntax error" in result.remaining_issues[0]

    def test_extract_helper_methods(self, refactoring_agent: RefactoringAgent) -> None:
        func_lines = [
            "def complex_func(self, x, y): ",
            ' """Complex function."""',
            " if x > 0 and y > 0 and x + y > 10: ",
            " return True",
            " return False",
        ]

        func_info = {"name": "complex_func", "line_start": 1, "line_end": 5}

        extracted = refactoring_agent._extract_helper_methods(func_lines, func_info)

        assert len(extracted) >= 1
        assert any("def _is_complex_func_condition" in method for method in extracted)

    async def test_file_write_failure(
        self,
        refactoring_agent: RefactoringAgent,
        tmp_path: Path,
    ) -> None:
        test_file = tmp_path / "test_file.py"
        test_file.write_text("import unused_module\n\ndef main(): pass")

        with patch.object(
            refactoring_agent.context,
            "write_file_content",
            return_value=False,
        ):
            issue = Issue(
                id="test_write_fail",
                type=IssueType.DEAD_CODE,
                severity=Priority.MEDIUM,
                message="Unused imports",
                file_path=str(test_file),
            )

            result = await refactoring_agent.analyze_and_fix(issue)

            assert not result.success
            assert result.confidence == 0.0
            assert "Failed to write" in result.remaining_issues[0]

    async def test_no_complex_functions_found(
        self,
        refactoring_agent: RefactoringAgent,
        tmp_path: Path,
    ) -> None:
        test_file = tmp_path / "simple_file.py"
        simple_code = '''def simple_function():
    """A simple function."""
    return True

def another_simple_function(x):
    """Another simple function."""
    return x * 2
'''
        test_file.write_text(simple_code)

        issue = Issue(
            id="test_no_complex",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Function too complex",
            file_path=str(test_file),
        )

        result = await refactoring_agent.analyze_and_fix(issue)

        assert result.success
        assert result.confidence == 0.7
        assert "No overly complex functions found" in result.recommendations[0]

    async def test_no_dead_code_found(
        self,
        refactoring_agent: RefactoringAgent,
        tmp_path: Path,
    ) -> None:
        test_file = tmp_path / "clean_file.py"
        clean_code = '''import os

def main():
    """Main function using all imports."""
    print(os.getcwd())

if __name__ == "__main__":
    main()
'''
        test_file.write_text(clean_code)

        issue = Issue(
            id="test_no_dead_code",
            type=IssueType.DEAD_CODE,
            severity=Priority.MEDIUM,
            message="Unused code",
            file_path=str(test_file),
        )

        result = await refactoring_agent.analyze_and_fix(issue)

        assert result.success
        assert result.confidence == 0.7
        assert "No obvious dead code found" in result.recommendations[0]

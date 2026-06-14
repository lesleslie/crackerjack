from __future__ import annotations

import ast
from pathlib import Path

import pytest

from crackerjack.agents.base import AgentContext
from crackerjack.agents.helpers.refactoring.complexity_analyzer import (
    ComplexityAnalyzer,
    ComplexityCalculator,
)


@pytest.fixture
def context(tmp_path: Path) -> AgentContext:
    return AgentContext(project_path=tmp_path)


@pytest.fixture
def analyzer(context: AgentContext) -> ComplexityAnalyzer:
    return ComplexityAnalyzer(context)


# ---------------------------------------------------------------------------
# ComplexityCalculator (AST visitor)


class TestComplexityCalculator:
    def _calc(self, src: str) -> int:
        tree = ast.parse(src)
        calc = ComplexityCalculator()
        calc.visit(tree)
        return calc.complexity

    def test_empty_function_has_zero_complexity(self) -> None:
        src = "def f(): pass"
        assert self._calc(src) == 0

    def test_if_increments_complexity(self) -> None:
        src = "if x:\n    pass"
        assert self._calc(src) == 1

    def test_for_loop_increments_complexity(self) -> None:
        src = "for i in range(10):\n    pass"
        assert self._calc(src) == 1

    def test_while_increments_complexity(self) -> None:
        src = "while True:\n    break"
        assert self._calc(src) == 1

    def test_except_handler_increments_complexity(self) -> None:
        src = "try:\n    pass\nexcept ValueError:\n    pass"
        assert self._calc(src) == 1

    def test_with_statement_increments_complexity(self) -> None:
        src = "with open('f') as fh:\n    pass"
        assert self._calc(src) == 1

    def test_bool_op_with_more_than_two_values(self) -> None:
        src = "x = a and b and c"
        assert self._calc(src) == 1

    def test_bool_op_with_two_values_no_increment(self) -> None:
        src = "x = a and b"
        assert self._calc(src) == 0

    def test_lambda_increments_complexity(self) -> None:
        src = "f = lambda x: x + 1"
        assert self._calc(src) == 1

    def test_function_def_does_not_increment(self) -> None:
        src = "def foo(): pass"
        assert self._calc(src) == 0

    def test_async_function_def_does_not_increment(self) -> None:
        src = "async def foo(): pass"
        assert self._calc(src) == 0

    def test_class_def_does_not_increment(self) -> None:
        src = "class Foo: pass"
        assert self._calc(src) == 0

    def test_multiple_constructs_accumulate(self) -> None:
        src = """
def foo(x, y):
    if x:
        for i in range(y):
            while i > 0:
                i -= 1
"""
        assert self._calc(src) == 3


# ---------------------------------------------------------------------------
# ComplexityAnalyzer._calculate_cognitive_complexity


class TestCalculateCognitiveComplexity:
    def test_simple_function_returns_low_complexity(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        src = "def f(x):\n    return x + 1"
        tree = ast.parse(src)
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = analyzer._calculate_cognitive_complexity(func)
        assert result == 0

    def test_nested_loops_yield_higher_complexity(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        src = """
def heavy(data):
    for row in data:
        for col in row:
            if col > 0:
                pass
"""
        tree = ast.parse(src)
        func = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        result = analyzer._calculate_cognitive_complexity(func)
        assert result >= 3

    def test_async_function_complexity(self, analyzer: ComplexityAnalyzer) -> None:
        src = """
async def fetch(items):
    for item in items:
        if item:
            pass
"""
        tree = ast.parse(src)
        func = next(
            n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)
        )
        result = analyzer._calculate_cognitive_complexity(func)
        assert result >= 2


# ---------------------------------------------------------------------------
# ComplexityAnalyzer.find_complex_functions


class TestFindComplexFunctions:
    def test_returns_empty_for_simple_function(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        src = "def f():\n    return 1"
        tree = ast.parse(src)
        result = analyzer.find_complex_functions(tree, src)
        assert result == []

    def test_detects_highly_complex_function(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        # Build a function with >15 complexity score
        branches = "\n".join(
            f"    if x == {i}:\n        return {i}" for i in range(18)
        )
        src = f"def heavy(x):\n{branches}\n    return -1"
        tree = ast.parse(src)
        result = analyzer.find_complex_functions(tree, src)
        assert len(result) == 1
        assert result[0]["name"] == "heavy"
        assert result[0]["complexity"] > 15

    def test_result_contains_expected_keys(self, analyzer: ComplexityAnalyzer) -> None:
        branches = "\n".join(
            f"    if x == {i}:\n        return {i}" for i in range(18)
        )
        src = f"def heavy(x):\n{branches}\n    return -1"
        tree = ast.parse(src)
        result = analyzer.find_complex_functions(tree, src)
        assert len(result) == 1
        item = result[0]
        assert "name" in item
        assert "line_start" in item
        assert "line_end" in item
        assert "complexity" in item
        assert "node" in item

    def test_detects_complex_async_function(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        branches = "\n".join(
            f"    if x == {i}:\n        return {i}" for i in range(18)
        )
        src = f"async def heavy(x):\n{branches}\n    return -1"
        tree = ast.parse(src)
        result = analyzer.find_complex_functions(tree, src)
        assert len(result) == 1
        assert result[0]["name"] == "heavy"

    def test_skips_moderately_complex_function(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        src = """
def moderate(x):
    if x > 0:
        return x
    return -x
"""
        tree = ast.parse(src)
        result = analyzer.find_complex_functions(tree, src)
        assert result == []


# ---------------------------------------------------------------------------
# ComplexityAnalyzer._estimate_function_complexity


class TestEstimateFunctionComplexity:
    def test_empty_body_returns_zero(self) -> None:
        assert ComplexityAnalyzer._estimate_function_complexity("") == 0

    def test_simple_body_returns_one(self) -> None:
        assert ComplexityAnalyzer._estimate_function_complexity("    return 1\n") == 1

    def test_if_adds_to_score(self) -> None:
        body = "    if x:\n        return x\n"
        score = ComplexityAnalyzer._estimate_function_complexity(body)
        assert score >= 2

    def test_deeply_indented_line_adds_to_score(self) -> None:
        body = "         " * 2 + "x = 1\n"  # 18 spaces indent
        score = ComplexityAnalyzer._estimate_function_complexity(body)
        assert score >= 2

    def test_and_or_adds_to_score(self) -> None:
        body = "    if a and b:\n        pass\n"
        score = ComplexityAnalyzer._estimate_function_complexity(body)
        assert score >= 3


# ---------------------------------------------------------------------------
# ComplexityAnalyzer._should_skip_line


class TestShouldSkipLine:
    def test_empty_line_with_no_function(self) -> None:
        assert ComplexityAnalyzer._should_skip_line("", None, "")

    def test_comment_line_with_no_function(self) -> None:
        assert ComplexityAnalyzer._should_skip_line("# comment", None, "# comment")

    def test_empty_line_appends_to_function_body(self) -> None:
        func = {"body": ""}
        result = ComplexityAnalyzer._should_skip_line("", func, "")
        assert result
        assert "\n" in func["body"]

    def test_non_empty_non_comment_returns_false(self) -> None:
        assert not ComplexityAnalyzer._should_skip_line("x = 1", None, "x = 1")


# ---------------------------------------------------------------------------
# ComplexityAnalyzer._is_function_definition


class TestIsFunctionDefinition:
    def test_def_with_parens(self) -> None:
        assert ComplexityAnalyzer._is_function_definition("def foo():")

    def test_def_without_parens_returns_false(self) -> None:
        assert not ComplexityAnalyzer._is_function_definition("define_something")

    def test_class_not_function(self) -> None:
        assert not ComplexityAnalyzer._is_function_definition("class Foo:")


# ---------------------------------------------------------------------------
# ComplexityAnalyzer._handle_function_definition


class TestHandleFunctionDefinition:
    def test_saves_previous_function_and_starts_new(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        functions: list = []
        prev = {
            "body": "    return 1\n",
            "name": "prev",
            "type": "function",
            "signature": "def prev():",
            "start_line": 1,
            "indent_level": 0,
        }
        new = analyzer._handle_function_definition(
            functions, prev, "def new():", 0, 5
        )
        assert len(functions) == 1
        assert functions[0]["name"] == "prev"
        assert "end_line" in functions[0]
        assert new["name"] == "new"

    def test_creates_new_function_dict_when_no_previous(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        functions: list = []
        new = analyzer._handle_function_definition(
            functions, None, "def fresh():", 0, 0
        )
        assert not functions
        assert new["name"] == "fresh"
        assert new["body"] == ""
        assert new["indent_level"] == 0


# ---------------------------------------------------------------------------
# ComplexityAnalyzer._is_line_inside_function


class TestIsLineInsideFunction:
    def test_deeper_indent_is_inside(self) -> None:
        func = {"indent_level": 0}
        assert ComplexityAnalyzer._is_line_inside_function(func, 4, "return x")

    def test_same_indent_string_start_is_inside(self) -> None:
        func = {"indent_level": 4}
        assert ComplexityAnalyzer._is_line_inside_function(func, 4, '"docstring"')

    def test_same_indent_decorator_is_inside(self) -> None:
        func = {"indent_level": 0}
        assert ComplexityAnalyzer._is_line_inside_function(func, 0, "@decorator")

    def test_same_indent_normal_code_is_outside(self) -> None:
        func = {"indent_level": 0}
        assert not ComplexityAnalyzer._is_line_inside_function(func, 0, "x = 1")


# ---------------------------------------------------------------------------
# ComplexityAnalyzer._handle_function_body_line


class TestHandleFunctionBodyLine:
    def test_appends_body_when_inside_function(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        functions: list = []
        func = {
            "name": "f",
            "body": "",
            "indent_level": 0,
            "type": "function",
            "signature": "def f():",
            "start_line": 1,
        }
        result = analyzer._handle_function_body_line(
            functions, func, "    return 1", "return 1", 4, 2
        )
        assert result is not None
        assert "return 1" in result["body"]
        assert not functions

    def test_closes_function_when_outside_indent(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        functions: list = []
        func = {
            "name": "f",
            "body": "    return 1\n",
            "indent_level": 4,
            "type": "function",
            "signature": "    def f():",
            "start_line": 2,
        }
        result = analyzer._handle_function_body_line(
            functions, func, "x = 1", "x = 1", 0, 5
        )
        assert result is None
        assert len(functions) == 1
        assert functions[0]["name"] == "f"


# ---------------------------------------------------------------------------
# ComplexityAnalyzer.extract_code_functions_for_semantic_analysis (integration)


class TestExtractCodeFunctionsForSemanticAnalysis:
    def test_extracts_single_function(self, analyzer: ComplexityAnalyzer) -> None:
        src = "def greet(name):\n    return f'Hello {name}'\n"
        result = analyzer.extract_code_functions_for_semantic_analysis(src)
        assert len(result) == 1
        assert result[0]["name"] == "greet"

    def test_extracts_multiple_functions(self, analyzer: ComplexityAnalyzer) -> None:
        src = "def foo():\n    pass\n\ndef bar():\n    return 1\n"
        result = analyzer.extract_code_functions_for_semantic_analysis(src)
        names = [f["name"] for f in result]
        assert "foo" in names
        assert "bar" in names

    def test_result_has_expected_keys(self, analyzer: ComplexityAnalyzer) -> None:
        src = "def example():\n    x = 1\n    return x\n"
        result = analyzer.extract_code_functions_for_semantic_analysis(src)
        assert result
        item = result[0]
        assert "name" in item
        assert "body" in item
        assert "start_line" in item
        assert "estimated_complexity" in item

    def test_returns_empty_for_no_functions(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        src = "x = 1\ny = 2\n"
        result = analyzer.extract_code_functions_for_semantic_analysis(src)
        assert result == []

    def test_comment_lines_are_skipped(self, analyzer: ComplexityAnalyzer) -> None:
        src = "# module comment\ndef documented():\n    # inner comment\n    pass\n"
        result = analyzer.extract_code_functions_for_semantic_analysis(src)
        assert len(result) == 1
        assert result[0]["name"] == "documented"

    def test_trailing_function_appended_at_eof(
        self, analyzer: ComplexityAnalyzer
    ) -> None:
        src = "def last():\n    return 42"
        result = analyzer.extract_code_functions_for_semantic_analysis(src)
        assert result
        assert result[-1]["name"] == "last"

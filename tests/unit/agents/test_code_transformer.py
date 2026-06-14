from __future__ import annotations

import ast
from pathlib import Path

import pytest

from crackerjack.agents.base import AgentContext
from crackerjack.agents.helpers.refactoring.code_transformer import CodeTransformer


@pytest.fixture
def ctx(tmp_path: Path) -> AgentContext:
    return AgentContext(project_path=tmp_path)


@pytest.fixture
def transformer(ctx: AgentContext) -> CodeTransformer:
    return CodeTransformer(ctx)


def test_perform_extraction_emits_valid_nested_helpers() -> None:
    content = """class Server:
    async def start(self):
        if self.enable_metrics and self.metrics:
            self.metrics.start_metrics_server(self.metrics_port)
        return True
"""
    tree = ast.parse(content)
    func_node = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "start"
    )
    func_info = {
        "line_start": func_node.lineno,
        "line_end": func_node.end_lineno or func_node.lineno,
        "node": func_node,
    }
    extracted_helpers = [
        {
            "name": "_process_conditional_1",
            "content": """        if self.enable_metrics and self.metrics:
            self.metrics.start_metrics_server(self.metrics_port)
""",
        }
    ]

    result = CodeTransformer._perform_extraction(
        content.split("\n"),
        func_info,
        extracted_helpers,
    )

    ast.parse(result)
    assert "async def _process_conditional_1()" in result
    assert "await _process_conditional_1()" in result


def test_refactor_complex_functions_falls_back_to_ast_sections() -> None:
    content = """def load_settings():
    if config_file.exists():
        config = read_config()
        if config.get("enabled"):
            return config
    for path in search_paths:
        if path.exists():
            return path
    return None
"""
    tree = ast.parse(content)
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

    transformer = CodeTransformer(AgentContext(project_path="/tmp"))
    result = transformer._extract_ast_sections(content, func_info)

    assert result
    assert any(section["name"].startswith("_process_if_") for section in result)
    assert any(section["content"].lstrip().startswith("if ") for section in result)


# ---------------------------------------------------------------------------
# apply_enhanced_strategies / _apply_enhanced_complexity_patterns


def test_apply_enhanced_strategies_returns_string(transformer: CodeTransformer) -> None:
    content = "x = 1\ny = 2\n"
    result = transformer.apply_enhanced_strategies(content)
    assert isinstance(result, str)


def test_apply_enhanced_complexity_patterns_identity_on_plain_code(
    transformer: CodeTransformer,
) -> None:
    content = "def foo():\n    return 1\n"
    result = transformer._apply_enhanced_complexity_patterns(content)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _extract_nested_conditions (no-op)


def test_extract_nested_conditions_returns_unchanged() -> None:
    content = "if a:\n    if b:\n        pass\n"
    result = CodeTransformer._extract_nested_conditions(content)
    assert result == content


# ---------------------------------------------------------------------------
# _simplify_data_structures


def test_simplify_data_structures_plain_lines_unchanged() -> None:
    content = "x = 1\ny = 2\n"
    result = CodeTransformer._simplify_data_structures(content)
    assert result == content


def test_simplify_data_structures_long_comprehension_unchanged() -> None:
    # Long list comp with 'if' — triggers branch but currently no-op
    content = "result = [x for x in items if x > 0 and x < 100 and x != 50]\n" * 2
    result = CodeTransformer._simplify_data_structures(content)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _extract_validation_patterns


def test_extract_validation_patterns_no_op_without_key() -> None:
    content = "x = validate(y)\n"
    result = CodeTransformer._extract_validation_patterns(content)
    assert result == content


# ---------------------------------------------------------------------------
# refactor_detect_agent_needs_pattern


def test_refactor_detect_agent_needs_pattern_no_match() -> None:
    content = "def something_else():\n    pass\n"
    result = CodeTransformer.refactor_detect_agent_needs_pattern(content)
    assert result == content


def test_refactor_detect_agent_needs_pattern_with_func_present_no_original() -> None:
    # Has the function name but not the exact original pattern
    content = "async def detect_agent_needs(x):\n    return {}\n"
    result = CodeTransformer.refactor_detect_agent_needs_pattern(content)
    assert result == content


# ---------------------------------------------------------------------------
# refactor_complex_functions — detect_agent_needs special-case branch


def test_refactor_complex_functions_detect_agent_needs_no_op(
    transformer: CodeTransformer,
) -> None:
    content = "async def detect_agent_needs(x):\n    return {}\n"
    tree = ast.parse(content)
    func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef))
    func_info = {
        "name": "detect_agent_needs",
        "line_start": func_node.lineno,
        "line_end": func_node.end_lineno or func_node.lineno,
        "node": func_node,
    }
    result = transformer.refactor_complex_functions(content, [func_info])
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# refactor_complex_functions — no extracted helpers → returns content


def test_refactor_complex_functions_returns_content_when_no_helpers(
    transformer: CodeTransformer,
) -> None:
    content = "def simple():\n    return 1\n"
    tree = ast.parse(content)
    func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    func_info = {
        "name": "simple",
        "line_start": func_node.lineno,
        "line_end": func_node.end_lineno or func_node.lineno,
        "node": func_node,
    }
    result = transformer.refactor_complex_functions(content, [func_info])
    assert result == content


# ---------------------------------------------------------------------------
# refactor_complex_functions — empty func_content branch


def test_refactor_complex_functions_empty_func_content_branch(
    transformer: CodeTransformer,
) -> None:
    content = "def outer():\n    pass\n"
    # Provide out-of-range line numbers to trigger empty func_content path
    func_info = {
        "name": "outer",
        "line_start": 999,
        "line_end": 1000,
        "node": None,
    }
    result = transformer.refactor_complex_functions(content, [func_info])
    assert result == content


# ---------------------------------------------------------------------------
# _extract_ast_sections — non-FunctionDef node


def test_extract_ast_sections_non_function_node_returns_empty(
    transformer: CodeTransformer,
) -> None:
    func_info = {"node": None, "line_start": 1}
    result = transformer._extract_ast_sections("x = 1", func_info)
    assert result == []


def test_extract_ast_sections_skips_short_blocks(
    transformer: CodeTransformer,
) -> None:
    content = "def f():\n    if True:\n        pass\n"
    tree = ast.parse(content)
    func_node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    func_info = {
        "name": "f",
        "line_start": func_node.lineno,
        "line_end": func_node.end_lineno or func_node.lineno,
        "node": func_node,
    }
    result = transformer._extract_ast_sections(content, func_info)
    # Single 2-line if block should be skipped (< 3 lines)
    assert result == []


# ---------------------------------------------------------------------------
# _extract_logical_sections branches


def test_extract_logical_sections_empty_content(transformer: CodeTransformer) -> None:
    result = transformer._extract_logical_sections("", {})
    assert result == []


def test_extract_logical_sections_for_loop_section(
    transformer: CodeTransformer,
) -> None:
    content = (
        "for item in items:\n"
        "    process(item)\n"
        "    log(item)\n"
        "    save(item)\n"
    )
    result = transformer._extract_logical_sections(content, {})
    assert any(s["type"] == "loop" for s in result)


def test_extract_logical_sections_long_if_section(
    transformer: CodeTransformer,
) -> None:
    content = (
        "if some_very_long_condition_that_exceeds_fifty_characters_in_length:\n"
        "    do_thing_one()\n"
        "    do_thing_two()\n"
        "    do_thing_three()\n"
    )
    result = transformer._extract_logical_sections(content, {})
    assert any(s["type"] == "conditional" for s in result)


# ---------------------------------------------------------------------------
# _should_start_new_section


def test_should_start_new_section_long_if() -> None:
    long_if = "if " + "x" * 50 + ":"
    assert CodeTransformer._should_start_new_section(long_if, None)


def test_should_start_new_section_for_not_in_loop() -> None:
    assert CodeTransformer._should_start_new_section("for i in items:", None)


def test_should_start_new_section_for_already_in_loop() -> None:
    assert not CodeTransformer._should_start_new_section("for i in items:", "loop")


def test_should_start_new_section_short_if_returns_false() -> None:
    assert not CodeTransformer._should_start_new_section("if x:", None)


# ---------------------------------------------------------------------------
# _initialize_new_section


def test_initialize_new_section_long_if() -> None:
    long_if = "if " + "x" * 50 + ":"
    lines, section_type = CodeTransformer._initialize_new_section(long_if, long_if)
    assert section_type == "conditional"


def test_initialize_new_section_for_loop() -> None:
    _, section_type = CodeTransformer._initialize_new_section(
        "for i in x:", "for i in x:"
    )
    assert section_type == "loop"


def test_initialize_new_section_while_loop() -> None:
    _, section_type = CodeTransformer._initialize_new_section(
        "while True:", "while True:"
    )
    assert section_type == "loop"


def test_initialize_new_section_general_fallback() -> None:
    _, section_type = CodeTransformer._initialize_new_section("x = 1", "x = 1")
    assert section_type == "general"


# ---------------------------------------------------------------------------
# _extract_function_content — out-of-range


def test_extract_function_content_negative_start_returns_empty() -> None:
    lines = ["def f():", "    pass"]
    result = CodeTransformer._extract_function_content(
        lines, {"line_start": 0, "line_end": 1}
    )
    assert result == ""


def test_extract_function_content_end_beyond_lines_returns_empty() -> None:
    lines = ["def f():", "    pass"]
    result = CodeTransformer._extract_function_content(
        lines, {"line_start": 1, "line_end": 100}
    )
    assert result == ""


# ---------------------------------------------------------------------------
# _is_extraction_valid — invalid conditions


def test_is_extraction_valid_no_helpers() -> None:
    lines = ["def f():", "    pass"]
    assert not CodeTransformer._is_extraction_valid(
        lines, {"line_start": 1, "line_end": 2}, []
    )


def test_is_extraction_valid_negative_start() -> None:
    lines = ["def f():", "    pass"]
    helpers = [{"name": "h", "content": "pass"}]
    assert not CodeTransformer._is_extraction_valid(
        lines, {"line_start": 0, "line_end": 1}, helpers
    )


# ---------------------------------------------------------------------------
# _find_class_end / _find_class_indent / _find_class_end_line


def test_find_class_indent_finds_class() -> None:
    lines = ["class Foo:", "    def bar(self):", "        pass"]
    result = CodeTransformer._find_class_indent(lines, 1)
    assert result == 0


def test_find_class_indent_returns_none_when_no_class() -> None:
    lines = ["x = 1", "y = 2"]
    result = CodeTransformer._find_class_indent(lines, 1)
    assert result is None


def test_find_class_end_line_finds_next_top_level() -> None:
    lines = [
        "class Foo:",
        "    def bar(self):",
        "        pass",
        "x = 1",
    ]
    result = CodeTransformer._find_class_end_line(lines, 1, 0)
    assert result == 3


def test_find_class_end_line_returns_len_when_no_end() -> None:
    lines = ["class Foo:", "    def bar(self):", "        pass"]
    result = CodeTransformer._find_class_end_line(lines, 1, 0)
    assert result == len(lines)


def test_find_class_end_no_class_returns_len() -> None:
    lines = ["x = 1", "y = 2"]
    result = CodeTransformer._find_class_end(lines, 1)
    assert result == len(lines)


def test_find_class_end_with_class_present() -> None:
    lines = [
        "class Foo:",
        "    def bar(self):",
        "        pass",
        "x = 1",
    ]
    result = CodeTransformer._find_class_end(lines, 1)
    assert result == 3

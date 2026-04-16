from __future__ import annotations

import ast

from crackerjack.agents.base import AgentContext
from crackerjack.agents.helpers.refactoring.code_transformer import CodeTransformer


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

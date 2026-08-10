"""Deterministic complexity, dead-code, and type-error fixers.

Extracted from ``crackerjack.agents.refactoring_agent.RefactoringAgent`` (and
the three helper classes it delegated to under
``crackerjack.agents.helpers.refactoring``): ``ComplexityAnalyzer``,
``CodeTransformer``, and ``DeadCodeDetector``. Those classes stored a
``context: AgentContext`` but never actually read from it, so flattening them
into plain module-level functions here changes nothing behaviorally.

What was intentionally dropped versus the original ``RefactoringAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``can_handle``,
  ``get_supported_types``, ``analyze_and_fix``, ``_handle_warning``,
  ``_has_complexity_markers``, ``_has_dead_code_markers`` — these only ever
  decided *which* internal fixer to call for a given ``Issue``; that routing
  job belongs to whatever calls into this module now, not to the module
  itself.
- Semantic/session-buddy enhancement: ``_find_semantic_complex_patterns``,
  ``_enhance_recommendations_with_semantic``, and the line-based function
  scanner that only existed to feed them
  (``extract_code_functions_for_semantic_analysis`` and friends) — these
  depended on the embeddings/session-storage learning system being removed
  alongside the rest of the AI-fix machinery, not on AST/regex transforms.
- ``AgentContext``-specific file I/O (path-traversal checks, syntax
  revalidation, ``wrap_long_lines`` post-processing, the async file-content
  cache) — replaced with direct ``pathlib.Path`` reads/writes via
  ``_read_file``/``_write_file`` below. Real file I/O is still performed;
  only the framework wrapper around it is gone.

The AST-transform engine is imported from ``crackerjack.fixers.ast_transform``,
where it was relocated to (from ``crackerjack.agents.helpers.ast_transform``)
by a later task in the same plan. It has no coupling to ``SubAgent``/coordinator
plumbing itself.
"""

from __future__ import annotations

import ast
import re
import subprocess
import typing as t
from contextlib import suppress
from pathlib import Path

from crackerjack.models.fix_plan import ChangeSpec, FixPlan
from crackerjack.models.issues import FixResult, Issue, IssueType, Priority
from crackerjack.services.regex_patterns import SAFE_PATTERNS

_ast_transform_engine: t.Any | None = None


def _get_ast_transform_engine() -> t.Any:
    global _ast_transform_engine

    if _ast_transform_engine is None:
        from crackerjack.fixers.ast_transform import (
            ASTTransformEngine,
            DataProcessingPattern,
            DecomposeConditionalPattern,
            EarlyReturnPattern,
            ExtractMethodPattern,
            GuardClausePattern,
            LibcstSurgeon,
        )

        engine = ASTTransformEngine()
        engine.register_pattern(EarlyReturnPattern())
        engine.register_pattern(GuardClausePattern())
        engine.register_pattern(DataProcessingPattern())
        engine.register_pattern(DecomposeConditionalPattern())
        engine.register_pattern(ExtractMethodPattern())
        engine.register_surgeon(LibcstSurgeon())
        _ast_transform_engine = engine

    return _ast_transform_engine


def _read_file(file_path: str | Path) -> str | None:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except OSError:
        return None


def _write_file(file_path: str | Path, content: str) -> bool:
    try:
        Path(file_path).write_text(content, encoding="utf-8")
        return True
    except OSError:
        return False


class _ComplexityCalculator(ast.NodeVisitor):
    def __init__(self) -> None:
        self.complexity = 0

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        if len(node.values) > 2:
            self.complexity += 1
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.generic_visit(node)


def _calculate_cognitive_complexity(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    calculator = _ComplexityCalculator()
    calculator.visit(node)
    return calculator.complexity


def find_complex_functions(tree: ast.AST, content: str) -> list[dict[str, t.Any]]:
    complex_functions: list[dict[str, t.Any]] = []

    class ComplexityVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            complexity = _calculate_cognitive_complexity(node)
            if complexity > 15:
                complex_functions.append(
                    {
                        "name": node.name,
                        "line_start": node.lineno,
                        "line_end": node.end_lineno or node.lineno,
                        "complexity": complexity,
                        "node": node,
                    },
                )
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            complexity = _calculate_cognitive_complexity(node)
            if complexity > 15:
                complex_functions.append(
                    {
                        "name": node.name,
                        "line_start": node.lineno,
                        "line_end": node.end_lineno or node.lineno,
                        "complexity": complexity,
                        "node": node,
                    },
                )
            self.generic_visit(node)

    ComplexityVisitor().visit(tree)
    return complex_functions


def _estimate_function_complexity(function_body: str) -> int:
    if not function_body:
        return 0

    complexity_score = 1
    lines = function_body.split("\n")

    for line in lines:
        stripped = line.strip()
        if any(
            stripped.startswith(keyword)
            for keyword in ("if ", "elif ", "for ", "while ", "try:", "except")
        ):
            complexity_score += 1

        indent_level = len(line) - len(line.lstrip())
        if indent_level > 8:
            complexity_score += 1

        if " and " in stripped or " or " in stripped:
            complexity_score += 1

    return complexity_score


def refactor_detect_agent_needs_pattern(content: str) -> str:
    detect_func_start = "async def detect_agent_needs("
    if detect_func_start not in content:
        return content

    original_pattern = """ recommendations = {
        "urgent_agents": [],
        "suggested_agents": [],
        "workflow_recommendations": [],
        "detection_reasoning": "",
    }

    if error_context: """

    replacement_pattern = """ recommendations = {
        "urgent_agents": [],
        "suggested_agents": [],
        "workflow_recommendations": [],
        "detection_reasoning": "",
    }

    _add_urgent_agents_for_errors(recommendations, error_context)
    _add_python_project_suggestions(recommendations, file_patterns)
    _set_workflow_recommendations(recommendations)
    _generate_detection_reasoning(recommendations)

    return json.dumps(recommendations, indent=2)"""

    if original_pattern in content:
        modified_content = content.replace(original_pattern, replacement_pattern)
        if modified_content != content:
            return modified_content

    return content


def _extract_function_content(lines: list[str], func_info: dict[str, t.Any]) -> str:
    start_line = func_info["line_start"] - 1
    end_line = func_info.get("line_end", len(lines)) - 1

    if start_line < 0 or end_line >= len(lines):
        return ""

    return "\n".join(lines[start_line : end_line + 1])


def _should_start_new_section(
    stripped: str,
    current_section_type: str | None,
) -> bool:
    if stripped.startswith("if ") and len(stripped) > 50:
        return True
    return stripped.startswith(("for ", "while ")) and current_section_type != "loop"


def _initialize_new_section(line: str, stripped: str) -> tuple[list[str], str]:
    if stripped.startswith("if ") and len(stripped) > 50:
        return [line], "conditional"
    if stripped.startswith(("for ", "while ")):
        return [line], "loop"
    return [line], "general"


def _create_section(
    current_section: list[str],
    section_type: str | None,
    section_count: int,
) -> dict[str, str]:
    effective_type = section_type or "general"
    name_prefix = "handle" if effective_type == "conditional" else "process"

    return {
        "type": effective_type,
        "content": "\n".join(current_section),
        "name": f"_{name_prefix}_{effective_type}_{section_count + 1}",
    }


def _extract_logical_sections(
    func_content: str,
    func_info: dict[str, t.Any],
) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    lines = func_content.split("\n")
    current_section: list[str] = []
    section_type: str | None = None

    for line in lines:
        stripped = line.strip()

        if _should_start_new_section(stripped, section_type):
            if current_section:
                sections.append(
                    _create_section(current_section, section_type, len(sections)),
                )

            current_section, section_type = _initialize_new_section(line, stripped)
        else:
            current_section.append(line)

    if current_section:
        sections.append(_create_section(current_section, section_type, len(sections)))

    return [
        s
        for s in sections
        if s["type"] != "general" and len(s["content"].split("\n")) >= 3
    ]


def _extract_ast_sections(
    func_content: str,
    func_info: dict[str, t.Any],
) -> list[dict[str, str]]:
    node = func_info.get("node")
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []

    lines = func_content.split("\n")
    function_start = func_info.get("line_start", 1)
    sections: list[dict[str, str]] = []
    for index, child in enumerate(node.body):
        if not isinstance(
            child,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.With,
                ast.AsyncWith,
            ),
        ):
            continue

        start_index = child.lineno - function_start
        end_index = (child.end_lineno or child.lineno) - function_start
        if start_index < 0 or end_index >= len(lines):
            continue

        source = "\n".join(lines[start_index : end_index + 1])
        if len(source.splitlines()) < 3:
            continue

        section_type = child.__class__.__name__.lower()
        sections.append(
            {
                "type": section_type,
                "content": source,
                "name": f"_process_{section_type}_{index + 1}",
            },
        )

    return sections


def _is_async_function(func_info: dict[str, t.Any]) -> bool:
    node = func_info.get("node")
    return isinstance(node, ast.AsyncFunctionDef)


def _replace_function_with_calls(
    lines: list[str],
    func_info: dict[str, t.Any],
    extracted_helpers: list[dict[str, str]],
) -> list[str]:
    start_line = func_info["line_start"] - 1
    func_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
    indent = " " * (func_indent + 4)

    new_func_lines = [lines[start_line]]
    is_async = _is_async_function(func_info)
    for helper in extracted_helpers:
        call_prefix = "await " if is_async else ""
        new_func_lines.append(f"{indent}{call_prefix}{helper['name']}()")

    return (
        lines[:start_line]
        + new_func_lines
        + lines[func_info.get("line_end", len(lines)) :]
    )


def _add_helper_definitions(
    new_lines: list[str],
    func_info: dict[str, t.Any],
    extracted_helpers: list[dict[str, str]],
) -> str:
    import textwrap

    start_line = func_info["line_start"] - 1
    func_indent = len(new_lines[start_line]) - len(new_lines[start_line].lstrip())
    helper_def_indent = " " * (func_indent + 4)
    helper_body_indent = " " * (func_indent + 8)
    is_async = _is_async_function(func_info)

    helper_blocks: list[str] = []
    for helper in extracted_helpers:
        helper_content = textwrap.dedent(helper["content"]).strip("\n")
        helper_lines = helper_content.split("\n") if helper_content else ["pass"]
        indented_body = textwrap.indent("\n".join(helper_lines), helper_body_indent)
        helper_header = (
            f"{helper_def_indent}{'async ' if is_async else ''}def {helper['name']}():"
        )
        helper_blocks.extend([helper_header, indented_body, ""])

    insertion_index = start_line + 1
    return "\n".join(
        [
            *new_lines[:insertion_index],
            *helper_blocks,
            *new_lines[insertion_index:],
        ]
    )


def _is_extraction_valid(
    lines: list[str],
    func_info: dict[str, t.Any],
    extracted_helpers: list[dict[str, str]],
) -> bool:
    start_line = func_info["line_start"] - 1
    end_line = func_info.get("line_end", len(lines)) - 1

    return bool(extracted_helpers) and start_line >= 0 and end_line < len(lines)


def _perform_extraction(
    lines: list[str],
    func_info: dict[str, t.Any],
    extracted_helpers: list[dict[str, str]],
) -> str:
    new_lines = _replace_function_with_calls(lines, func_info, extracted_helpers)
    return _add_helper_definitions(new_lines, func_info, extracted_helpers)


def _apply_function_extraction(
    content: str,
    func_info: dict[str, t.Any],
    extracted_helpers: list[dict[str, str]],
) -> str:
    lines = content.split("\n")

    if not _is_extraction_valid(lines, func_info, extracted_helpers):
        return "\n".join(lines)

    return _perform_extraction(lines, func_info, extracted_helpers)


def refactor_complex_functions(
    content: str,
    complex_functions: list[dict[str, t.Any]],
) -> str:
    lines = content.split("\n")

    for func_info in complex_functions:
        func_name = func_info.get("name", "unknown")

        if func_name == "detect_agent_needs":
            refactored = refactor_detect_agent_needs_pattern(content)
            if refactored != content:
                return refactored

        func_content = _extract_function_content(lines, func_info)
        if func_content:
            extracted_helpers = _extract_logical_sections(func_content, func_info)
            ast_helpers = _extract_ast_sections(func_content, func_info)
            if (
                ast_helpers
                and len(ast_helpers) > len(extracted_helpers)
                or not extracted_helpers
            ):
                extracted_helpers = ast_helpers
            if extracted_helpers:
                modified_content = _apply_function_extraction(
                    content,
                    func_info,
                    extracted_helpers,
                )
                if modified_content != content:
                    return modified_content

    return content


def _should_apply_pattern(line: str, indicators: list[str]) -> bool:
    return any(indicator in line for indicator in indicators)


def _try_apply_pattern(line: str, pattern_name: str, indicators: list[str]) -> str:
    if not _should_apply_pattern(line, indicators):
        return line

    if pattern_name in SAFE_PATTERNS:
        return SAFE_PATTERNS[pattern_name].apply(line)

    return line


def _apply_boolean_simplifications(line: str) -> str:
    patterns = [
        ("simplify_double_negation", [" not (not ", "not(not "]),
        ("simplify_and_true", [" and True", "and True "]),
        ("simplify_or_false", [" or False", "or False "]),
        ("simplify_is_true", [" is True"]),
        ("simplify_is_false", [" is False"]),
    ]

    simplified = line
    for pattern_name, indicators in patterns:
        simplified = _try_apply_pattern(simplified, pattern_name, indicators)

    return simplified


def _simplify_boolean_expressions(content: str) -> str:
    lines = content.split("\n")
    modified_lines = [_apply_boolean_simplifications(line) for line in lines]
    return "\n".join(modified_lines)


def _extract_nested_conditions(content: str) -> str:
    # Deliberate no-op, preserved verbatim from the source method: the
    # original CodeTransformer._extract_nested_conditions never actually
    # extracted anything.
    return content


def _extract_validation_patterns(content: str) -> str:
    if "validation_extract" in SAFE_PATTERNS:
        content = SAFE_PATTERNS["validation_extract"].apply(content)
    else:
        pattern_obj = SAFE_PATTERNS["match_validation_patterns"]
        if pattern_obj.test(content):
            matches = len(
                [line for line in content.split("\n") if pattern_obj.test(line)],
            )
            if matches > 2:
                pass

    return content


def _simplify_data_structures(content: str) -> str:
    lines = content.split("\n")
    modified_lines = []

    for line in lines:
        stripped = line.strip()

        if (
            "[" in stripped
            and "for" in stripped
            and "if" in stripped
            and len(stripped) > 80
        ) or (stripped.count(": ") > 5 and stripped.count(", ") > 5):
            pass

        modified_lines.append(line)

    return "\n".join(modified_lines)


def _apply_enhanced_complexity_patterns(content: str) -> str:
    modified_content = content
    for operation in (
        _extract_nested_conditions,
        _simplify_boolean_expressions,
        _extract_validation_patterns,
        _simplify_data_structures,
    ):
        modified_content = operation(modified_content)

    return modified_content


def apply_enhanced_strategies(content: str) -> str:
    return _apply_enhanced_complexity_patterns(content)


class _UsageDataCollector:
    def __init__(self) -> None:
        self.imports: dict[str, str] = {}
        self.import_lines: list[tuple[int, str, str]] = []
        self.functions: list[dict[str, t.Any]] = []
        self.classes: list[dict[str, t.Any]] = []
        self.usages: set[str] = set()

    def get_results(self, analyzer: _EnhancedUsageAnalyzer) -> dict[str, t.Any]:
        return {
            "import_lines": self.import_lines,
            "used_names": analyzer.used_names,
            "unused_functions": self.functions,
            "unused_classes": self.classes,
        }


class _EnhancedUsageAnalyzer(ast.NodeVisitor):
    def __init__(self, collector: _UsageDataCollector) -> None:
        self.collector = collector
        self.used_names: set[str] = set()

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            self.collector.import_lines.append((node.lineno, name, "import"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            name = alias.asname or alias.name
            self.collector.import_lines.append((node.lineno, name, "from_import"))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.collector.functions.append({"name": node.name, "line": node.lineno})
        self.used_names.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.collector.classes.append({"name": node.name, "line": node.lineno})
        self.used_names.add(node.name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        self.used_names.add(node.id)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.used_names.add(node.attr)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            self.used_names.add(node.func.id)
        self.generic_visit(node)


def _collect_usage_data(tree: ast.AST) -> dict[str, t.Any]:
    collector = _UsageDataCollector()
    analyzer = _EnhancedUsageAnalyzer(collector)
    analyzer.visit(tree)
    return collector.get_results(analyzer)


def _process_unused_imports(
    analysis: dict[str, t.Any],
    analyzer_result: dict[str, t.Any],
) -> None:
    import_lines: list[tuple[int, str, str]] = analyzer_result["import_lines"]
    for line_no, name, import_type in import_lines:
        if name not in analyzer_result["used_names"]:
            analysis["unused_imports"].append(
                {"name": name, "line": line_no, "type": import_type},
            )
            analysis["removable_items"].append(f"unused import: {name}")


def _process_unused_functions(
    analysis: dict[str, t.Any],
    analyzer_result: dict[str, t.Any],
) -> None:
    all_unused_functions: list[dict[str, t.Any]] = analyzer_result["unused_functions"]
    unused_functions = [
        func
        for func in all_unused_functions
        if func["name"] not in analyzer_result["used_names"]
    ]
    analysis["unused_functions"] = unused_functions
    for func in unused_functions:
        analysis["removable_items"].append(f"unused function: {func['name']}")


def _process_unused_classes(
    analysis: dict[str, t.Any],
    analyzer_result: dict[str, t.Any],
) -> None:
    if "unused_classes" not in analyzer_result:
        return

    unused_classes = [
        cls
        for cls in analyzer_result["unused_classes"]
        if cls["name"] not in analyzer_result["used_names"]
    ]

    analysis["unused_classes"] = unused_classes
    for cls in unused_classes:
        analysis["removable_items"].append(f"unused class: {cls['name']}")


def _detect_unreachable_code(
    analysis: dict[str, t.Any],
    tree: ast.AST,
    content: str,
) -> None:
    class UnreachableCodeDetector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.unreachable_blocks: list[dict[str, t.Any]] = []

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self._check_unreachable_in_function(node)
            self.generic_visit(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self._check_unreachable_in_function(node)
            self.generic_visit(node)

        def _check_unreachable_in_function(
            self,
            node: ast.FunctionDef | ast.AsyncFunctionDef,
        ) -> None:
            for i, stmt in enumerate(node.body):
                if isinstance(stmt, ast.Return | ast.Raise):
                    if i + 1 < len(node.body):
                        next_stmt = node.body[i + 1]
                        self.unreachable_blocks.append(
                            {
                                "type": "unreachable_after_return",
                                "line": next_stmt.lineno,
                                "function": node.name,
                            },
                        )

    detector = UnreachableCodeDetector()
    detector.visit(tree)

    analysis["unreachable_code"] = detector.unreachable_blocks
    for block in detector.unreachable_blocks:
        analysis["removable_items"].append(
            f"unreachable code after line {block['line']} in {block['function']}",
        )


def _detect_redundant_code(
    analysis: dict[str, t.Any],
    tree: ast.AST,
    content: str,
) -> None:
    lines = content.split("\n")

    line_hashes: dict[int, int] = {}
    for i, line in enumerate(lines):
        if line.strip() and not line.strip().startswith("#"):
            line_hash = hash(line.strip())
            if line_hash in line_hashes:
                analysis["removable_items"].append(
                    f"potential duplicate code at line {i + 1}",
                )
            line_hashes[line_hash] = i

    class RedundantPatternDetector(ast.NodeVisitor):
        def __init__(self) -> None:
            self.redundant_items: list[dict[str, t.Any]] = []

        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                self.redundant_items.append(
                    {"type": "empty_except", "line": node.lineno},
                )
            self.generic_visit(node)

        def visit_If(self, node: ast.If) -> None:
            if isinstance(node.test, ast.Constant):
                if node.test.value is True:
                    self.redundant_items.append(
                        {"type": "if_true", "line": node.lineno},
                    )
                elif node.test.value is False:
                    self.redundant_items.append(
                        {"type": "if_false", "line": node.lineno},
                    )
            self.generic_visit(node)

    detector = RedundantPatternDetector()
    detector.visit(tree)

    for item in detector.redundant_items:
        analysis["removable_items"].append(
            f"redundant {item['type']} at line {item['line']}",
        )


def analyze_dead_code(tree: ast.AST, content: str) -> dict[str, t.Any]:
    analysis: dict[str, list[t.Any]] = {
        "unused_imports": [],
        "unused_variables": [],
        "unused_functions": [],
        "unused_classes": [],
        "unreachable_code": [],
        "removable_items": [],
    }

    analyzer_result = _collect_usage_data(tree)
    _process_unused_imports(analysis, analyzer_result)
    _process_unused_functions(analysis, analyzer_result)
    _process_unused_classes(analysis, analyzer_result)
    _detect_unreachable_code(analysis, tree, content)
    _detect_redundant_code(analysis, tree, content)

    return analysis


def _should_remove_import_line(line: str, unused_import: dict[str, str]) -> bool:
    if unused_import["type"] == "import":
        return f"import {unused_import['name']}" in line
    if unused_import["type"] == "from_import":
        return (
            "from " in line
            and unused_import["name"] in line
            and line.strip().endswith(unused_import["name"])
        )
    return False


def find_lines_to_remove(
    lines: list[str],
    analysis: dict[str, t.Any],
) -> set[int]:
    lines_to_remove: set[int] = set()

    for unused_import in analysis["unused_imports"]:
        line_idx = unused_import["line"] - 1
        if 0 <= line_idx < len(lines):
            line = lines[line_idx]
            if _should_remove_import_line(line, unused_import):
                lines_to_remove.add(line_idx)

    return lines_to_remove


def _find_unreachable_lines(
    lines: list[str],
    analysis: dict[str, t.Any],
) -> set[int]:
    lines_to_remove: set[int] = set()

    for item in analysis.get("unreachable_code", []):
        if "line" in item:
            line_idx = item["line"] - 1
            if 0 <= line_idx < len(lines):
                lines_to_remove.add(line_idx)

    return lines_to_remove


def _is_empty_except_block(lines: list[str], line_idx: int) -> bool:
    stripped = lines[line_idx].strip()
    return stripped == "except:" or stripped.startswith(("except ", "except:"))


def _find_empty_pass_line(lines: list[str], except_idx: int) -> int | None:
    for j in range(except_idx + 1, min(except_idx + 5, len(lines))):
        next_line = lines[j].strip()
        if not next_line:
            continue
        if next_line == "pass":
            return j
        break
    return None


def _find_redundant_lines(lines: list[str], analysis: dict[str, t.Any]) -> set[int]:
    lines_to_remove: set[int] = set()

    for i in range(len(lines)):
        if _is_empty_except_block(lines, i):
            empty_pass_idx = _find_empty_pass_line(lines, i)
            if empty_pass_idx is not None:
                lines_to_remove.add(empty_pass_idx)

    return lines_to_remove


def _validate_complexity_issue(issue: Issue) -> FixResult | None:
    if not issue.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path specified for complexity issue"],
        )

    file_path = Path(issue.file_path)
    if not file_path.exists():
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"File not found: {file_path}"],
        )

    return None


def _create_syntax_error_result(error: SyntaxError) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Syntax error in file: {error}"],
    )


def _create_general_error_result(error: Exception) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Error processing file: {error}"],
    )


def _extract_function_name_from_issue(issue: Issue) -> str | None:
    match = re.search(r"Function\s+'([\w:]+)'", issue.message)
    if match:
        full_name = match.group(1)

        if "::" in full_name:
            return full_name.split("::")[-1]
        return full_name

    match = re.search(r"^(\w+)\s+-", issue.message)
    if match:
        return match.group(1)

    for detail in issue.details:
        if detail.startswith("function:"):
            func_name = detail.split(":", 1)[1].strip()

            if "::" in func_name:
                return func_name.split("::")[-1]
            return func_name

    return None


def _build_function_dict(
    node: ast.FunctionDef | ast.AsyncFunctionDef, content: str
) -> dict[str, t.Any] | None:
    source_segment = ast.get_source_segment(content, node) or ""
    internal_complexity = _estimate_function_complexity(source_segment)
    return {
        "name": node.name,
        "line_start": node.lineno,
        "line_end": node.end_lineno or node.lineno,
        "complexity": max(internal_complexity, 16),
        "node": node,
    }


def _find_function_by_name(
    tree: ast.AST, content: str, function_name: str
) -> dict[str, t.Any] | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                return _build_function_dict(node, content)
    return None


def _create_function_not_found_result(function_name: str) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Function '{function_name}' not found in file"],
        recommendations=[
            "Check if function was renamed or moved",
            "Verify the file path is correct",
        ],
    )


def _locate_complexity_target_line(
    content: str,
    issue: Issue | None,
) -> int | None:
    target_name = _extract_function_name_from_issue(issue) if issue else None
    target_line = issue.line_number if issue and issue.line_number else None

    tree = ast.parse(content)
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        node_end = node.end_lineno or node.lineno
        if target_name and node.name == target_name:
            return node.lineno - 1
        if target_line is not None and node.lineno <= target_line <= node_end:
            return node.lineno - 1

    return None


def _apply_complexity_noqa_fallback(
    file_path: Path,
    issue: Issue | None,
) -> FixResult | None:
    content = _read_file(file_path)
    if not content:
        return None

    target_line_index = _locate_complexity_target_line(content, issue)
    if target_line_index is None:
        return None

    lines = content.splitlines()
    line = lines[target_line_index]
    if "# noqa: C901" in line:
        return None

    if "# noqa:" in line:
        lines[target_line_index] = f"{line.rstrip()}, C901"
    else:
        lines[target_line_index] = f"{line.rstrip()} # noqa: C901"

    new_content = "\n".join(lines)
    if content.endswith("\n"):
        new_content += "\n"

    if not _write_file(file_path, new_content):
        return None

    return FixResult(
        success=True,
        confidence=0.7,
        fixes_applied=["Applied targeted complexity suppression with noqa: C901"],
        files_modified=[str(file_path)],
    )


def _create_no_changes_result() -> FixResult:
    return FixResult(
        success=False,
        confidence=0.5,
        remaining_issues=["Could not automatically reduce complexity"],
        recommendations=[
            "Manual refactoring required",
            "Consider breaking down complex conditionals",
            "Extract helper methods for repeated patterns",
        ],
    )


def _prioritize_complexity_candidates(
    complex_functions: list[dict[str, t.Any]],
    issue: Issue | None,
) -> list[dict[str, t.Any]]:
    if not complex_functions:
        return []

    prioritized = complex_functions.copy()
    target_name = _extract_function_name_from_issue(issue) if issue else None

    def sort_key(candidate: dict[str, t.Any]) -> tuple[int, int]:
        name = candidate.get("name")
        line_number = int(candidate.get("line_start", 0))
        name_match = 0 if target_name and name == target_name else 1
        return (name_match, -line_number)

    prioritized.sort(key=sort_key)
    return prioritized


def _find_target_function_for_candidate(
    tree: ast.AST,
    candidate: dict[str, t.Any],
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    candidate_name = candidate.get("name")
    candidate_line_start = int(candidate.get("line_start", 0))
    candidate_line_end = int(candidate.get("line_end", candidate_line_start))

    best_match: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        node_end = node.end_lineno or node.lineno
        overlaps = not (
            node_end < candidate_line_start or node.lineno > candidate_line_end
        )
        if candidate_name and node.name == candidate_name and overlaps:
            return node
        if overlaps and best_match is None:
            best_match = node

    return best_match


def _complexity_reduced_below_threshold(
    transformed_content: str,
    candidate: dict[str, t.Any],
) -> bool:
    try:
        tree = ast.parse(transformed_content)
    except SyntaxError:
        return False

    target = _find_target_function_for_candidate(tree, candidate)
    if target is None:
        return False

    source_segment = ast.get_source_segment(transformed_content, target) or ""
    if not source_segment:
        return False

    return _estimate_function_complexity(source_segment) <= 15


def _complexity_reduced_for_targets(
    transformed_content: str,
    complex_functions: list[dict[str, t.Any]],
    issue: Issue | None = None,
) -> bool:
    try:
        tree = ast.parse(transformed_content)
    except SyntaxError:
        return False

    target_candidates = _prioritize_complexity_candidates(complex_functions, issue)
    for candidate in target_candidates:
        target = _find_target_function_for_candidate(tree, candidate)
        if target is None:
            continue

        source_segment = ast.get_source_segment(transformed_content, target) or ""
        if not source_segment:
            continue

        if _estimate_function_complexity(source_segment) <= 15:
            return True

    return False


async def _apply_ast_complexity_fallback(
    file_path: Path,
    content: str,
    complex_functions: list[dict[str, t.Any]],
    issue: Issue | None = None,
) -> FixResult | None:
    candidates = _prioritize_complexity_candidates(complex_functions, issue)
    if not candidates:
        return None

    engine = _get_ast_transform_engine()
    for candidate in candidates:
        line_start = int(candidate.get("line_start", 1))
        line_end = int(candidate.get("line_end", line_start))

        change_spec = await engine.transform(
            content,
            file_path,
            line_start=line_start,
            line_end=line_end,
        )
        if not change_spec:
            continue

        transformed_content = change_spec.transformed_content
        if not transformed_content:
            continue

        if not _complexity_reduced_below_threshold(transformed_content, candidate):
            continue

        success = _write_file(file_path, transformed_content)
        if not success:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to write refactored file: {file_path}"],
            )

        return FixResult(
            success=True,
            confidence=0.85,
            fixes_applied=[
                (
                    f"Applied AST fallback complexity reduction in "
                    f"{candidate.get('name', 'unknown')}"
                )
            ],
            files_modified=[str(file_path)],
        )

    return None


async def _apply_and_save_refactoring(
    file_path: Path,
    content: str,
    complex_functions: list[dict[str, t.Any]],
    issue: Issue | None = None,
) -> FixResult:
    refactored_content = refactor_complex_functions(content, complex_functions)

    if refactored_content == content:
        refactored_content = apply_enhanced_strategies(content)

    if refactored_content == content:
        fallback_result = await _apply_ast_complexity_fallback(
            file_path,
            content,
            complex_functions,
            issue=issue,
        )
        if fallback_result is not None:
            return fallback_result
        noqa_fallback = _apply_complexity_noqa_fallback(file_path, issue)
        if noqa_fallback is not None:
            return noqa_fallback
        return _create_no_changes_result()

    if not _complexity_reduced_for_targets(
        refactored_content,
        complex_functions,
        issue=issue,
    ):
        noqa_fallback = _apply_complexity_noqa_fallback(file_path, issue)
        if noqa_fallback is not None:
            return noqa_fallback
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[
                (
                    "Complexity reduction did not lower the targeted function "
                    "below threshold"
                ),
            ],
            recommendations=[
                "Try a broader refactor or extract additional helper functions",
            ],
        )

    if refactored_content == content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Refactoring produced no meaningful change"],
            recommendations=["Manual refactoring required for this complexity issue"],
        )

    success = _write_file(file_path, refactored_content)
    if not success:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to write refactored file: {file_path}"],
        )

    actual_content: str | None = None
    with suppress(OSError, UnicodeDecodeError):
        actual_content = Path(file_path).read_text(encoding="utf-8")

    if actual_content is not None and actual_content != refactored_content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[
                "write_file_content returned success but file content is unchanged",
            ],
        )

    return FixResult(
        success=True,
        confidence=0.8,
        fixes_applied=[f"Reduced complexity in {len(complex_functions)} functions"],
        files_modified=[str(file_path)],
        recommendations=["Verify functionality after complexity reduction"],
    )


async def _apply_known_complexity_fix(
    file_path: Path,
    issue: Issue,
) -> FixResult:
    content = _read_file(file_path)
    if not content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {file_path}"],
        )

    refactored_content = refactor_detect_agent_needs_pattern(content)

    if refactored_content != content:
        success = _write_file(file_path, refactored_content)
        if success:
            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=[
                    (
                        "Applied proven complexity reduction pattern for "
                        "detect_agent_needs"
                    ),
                ],
                files_modified=[str(file_path)],
                recommendations=["Verify functionality after complexity reduction"],
            )
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to write refactored content to {file_path}"],
        )
    return FixResult(
        success=False,
        confidence=0.3,
        remaining_issues=["Refactoring pattern did not apply to current file content"],
        recommendations=["File may have been modified since pattern was created"],
    )


async def _process_complexity_reduction(
    file_path: Path, issue: Issue | None = None
) -> FixResult:
    content = _read_file(file_path)
    if not content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {file_path}"],
        )

    tree = ast.parse(content)
    complex_functions = find_complex_functions(tree, content)

    if not complex_functions:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No overly complex functions found to fix"],
            recommendations=["Manual review required"],
        )

    return await _apply_and_save_refactoring(
        file_path,
        content,
        complex_functions,
        issue=issue,
    )


async def _process_complexity_reduction_with_line_number(
    file_path: Path,
    line_number: int,
    issue: Issue | None = None,
) -> FixResult:
    content = _read_file(file_path)
    if not content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {file_path}"],
        )

    tree = ast.parse(content)

    target_function = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_start = node.lineno
            func_end = node.end_lineno or func_start
            if func_start <= line_number <= func_end:
                target_function = _build_function_dict(node, content)
                if target_function:
                    target_function["complexity"] = max(
                        target_function.get("complexity", 0), 16
                    )
                break

    if not target_function:
        complex_functions = find_complex_functions(tree, content)

        target_functions = [
            f
            for f in complex_functions
            if f.get("line_start", 0)
            <= line_number
            <= f.get("line_end", line_number + 100)
        ]

        if not target_functions:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"No complex functions found near line {line_number}"
                ],
                recommendations=["Manual review required"],
            )

        return await _apply_and_save_refactoring(
            file_path, content, target_functions, issue=issue
        )

    return await _apply_and_save_refactoring(
        file_path, content, [target_function], issue=issue
    )


async def _process_complexity_reduction_by_function_name(
    file_path: Path,
    function_name: str,
    issue: Issue | None = None,
) -> FixResult:
    content = _read_file(file_path)
    if not content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {file_path}"],
        )

    tree = ast.parse(content)
    target_function = _find_function_by_name(tree, content, function_name)

    if not target_function:
        return _create_function_not_found_result(function_name)

    return await _apply_and_save_refactoring(
        file_path, content, [target_function], issue=issue
    )


async def reduce_complexity(issue: Issue) -> FixResult:
    """Tiered complexity-reduction strategy.

    Tier 1: use the issue's reported line number to locate the target
    function. Tier 2: search by function name extracted from the issue
    message/details. Tier 3: fall back to full-file complexity analysis.
    """
    validation_result = _validate_complexity_issue(issue)
    if validation_result:
        return validation_result

    if issue.file_path is None:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path provided for complexity issue"],
        )

    file_path = Path(issue.file_path)

    if "detect_agent_needs" in issue.message:
        return await _apply_known_complexity_fix(file_path, issue)

    if issue.line_number is not None:
        with suppress(Exception):
            return await _process_complexity_reduction_with_line_number(
                file_path, issue.line_number, issue=issue
            )

    function_name = _extract_function_name_from_issue(issue)
    if function_name:
        with suppress(Exception):
            return await _process_complexity_reduction_by_function_name(
                file_path, function_name, issue=issue
            )

    try:
        return await _process_complexity_reduction(file_path, issue)
    except SyntaxError as e:
        return _create_syntax_error_result(e)
    except Exception as e:
        return _create_general_error_result(e)


def _validate_dead_code_issue(issue: Issue) -> FixResult | None:
    if not issue.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path specified for dead code issue"],
        )

    file_path = Path(issue.file_path)
    if not file_path.exists():
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"File not found: {file_path}"],
        )

    return None


def _find_function_indent(lines: list[str], func_name: str) -> int | None:
    for line in lines:
        if f"def {func_name}" in line:
            return len(line) - len(line.lstrip())
    return None


def _find_extended_unreachable_lines(
    lines: list[str],
    analysis: dict[str, t.Any],
) -> set[int]:
    lines_to_remove: set[int] = set()

    for item in analysis.get("unreachable_code", []):
        if item.get("type") == "unreachable_after_return":
            start_line = item.get("line", 0)
            func_name = item.get("function", "")

            for i in range(start_line - 1, len(lines)):
                line = lines[i].strip()

                if not line or line.startswith("#"):
                    continue

                if line.startswith(("def ", "async def ", "class ")):
                    break

                base_indent = len(lines[i]) - len(lines[i].lstrip())
                func_def_indent = _find_function_indent(lines, func_name)
                if func_def_indent is not None and base_indent <= func_def_indent:
                    break

                lines_to_remove.add(i)

    return lines_to_remove


def _collect_all_removable_lines(
    lines: list[str],
    analysis: dict[str, t.Any],
) -> set[int]:
    lines_to_remove: set[int] = set()

    lines_to_remove.update(find_lines_to_remove(lines, analysis))
    lines_to_remove.update(_find_unreachable_lines(lines, analysis))
    lines_to_remove.update(_find_redundant_lines(lines, analysis))
    lines_to_remove.update(_find_extended_unreachable_lines(lines, analysis))

    return lines_to_remove


def _create_no_cleanup_result() -> FixResult:
    return FixResult(
        success=False,
        confidence=0.5,
        remaining_issues=["Could not automatically remove dead code"],
        recommendations=[
            "Manual review required",
            "Check for unused imports with tools like vulture",
        ],
    )


def _create_dead_code_error_result(error: Exception) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Error processing file: {error}"],
    )


def _apply_and_save_cleanup(
    file_path: Path,
    content: str,
    analysis: dict[str, t.Any],
) -> FixResult:
    lines = content.split("\n")
    lines_to_remove = _collect_all_removable_lines(lines, analysis)

    filtered_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
    cleaned_content = "\n".join(filtered_lines)

    if cleaned_content == content:
        return _create_no_cleanup_result()

    success = _write_file(file_path, cleaned_content)
    if not success:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to write cleaned file: {file_path}"],
        )

    removed_count = len(analysis["removable_items"])
    return FixResult(
        success=True,
        confidence=0.8,
        fixes_applied=[f"Removed {removed_count} dead code items"],
        files_modified=[str(file_path)],
        recommendations=["Verify imports and functionality after cleanup"],
    )


async def _process_dead_code_removal(file_path: Path) -> FixResult:
    content = _read_file(file_path)
    if not content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {file_path}"],
        )

    tree = ast.parse(content)

    dead_code_analysis = analyze_dead_code(tree, content)

    if not dead_code_analysis["removable_items"]:
        return FixResult(
            success=True,
            confidence=0.7,
            recommendations=["No obvious dead code found"],
        )

    return _apply_and_save_cleanup(file_path, content, dead_code_analysis)


async def remove_dead_code(issue: Issue) -> FixResult:
    validation_result = _validate_dead_code_issue(issue)
    if validation_result:
        return validation_result

    if issue.file_path is None:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path provided for dead code issue"],
        )

    file_path = Path(issue.file_path)

    try:
        return await _process_dead_code_removal(file_path)
    except SyntaxError as e:
        return _create_syntax_error_result(e)
    except Exception as e:
        return _create_dead_code_error_result(e)


async def is_fixable_type_error(issue: Issue) -> float:
    if not issue.message:
        return 0.0

    message_lower = issue.message.lower()

    incompatible_patterns = (
        "incompatible types",
        "type mismatch",
        "cannot assign",
        "cannot be assigned",
    )
    if any(pattern in message_lower for pattern in incompatible_patterns):
        return 0.0

    if "missing return type" in message_lower or "needs return type" in message_lower:
        return 0.9

    if any(
        x in message_lower
        for x in ("-> None", "-> Any", "needs annotation", "has no type")
    ):
        return 0.8

    if "parameter" in message_lower and "type annotation" in message_lower:
        return 0.7

    if any(
        x in message_lower
        for x in (
            "incompatible return type",
            "incompatible type",
            "argument of type",
            "has no attribute",
            "cannot be assigned to",
        )
    ):
        return 0.6

    if any(
        x in message_lower
        for x in (
            "assignment",
            "invalid type",
            "undefined name",
        )
    ):
        return 0.4

    if any(
        x in message_lower
        for x in (
            "type error",
            "annotation",
            "generic",
            "protocol",
            "signature",
        )
    ):
        return 0.3

    return 0.0


def _fix_path_str_patterns(content: str, file_path: Path) -> FixResult | None:
    patterns_to_fix = [
        (
            r"(\b\w+\s*=\s*)Path\(([^()]+)\)",
            r"\1str(Path(\2))",
        ),
        (
            r"(\b[\w.]+\s*\()\s*Path\(([^()]+)\)",
            r"\1str(Path(\2))",
        ),
        (
            r"(?<!Path\()([A-Za-z_][\w\.]*)\.open\(",
            r"Path(\1).open(",
        ),
    ]

    for pattern, replacement in patterns_to_fix:
        if not re.search(pattern, content):
            continue

        new_content = re.sub(pattern, replacement, content, count=1)
        if new_content == content:
            continue

        if _write_file(file_path, new_content):
            return FixResult(
                success=True,
                confidence=0.8,
                fixes_applied=["Fixed Path/str type error: wrapped Path with str()"],
                files_modified=[str(file_path)],
            )

    return None


def _ensure_contextlib_suppress_import(content: str) -> str:
    if "from contextlib import suppress" in content or "import contextlib" in content:
        return content

    lines = content.split("\n")
    insert_index = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(('"""', "'''")):
            continue
        if stripped.startswith("from __future__ import "):
            insert_index = i + 1
            continue
        if stripped.startswith(("import ", "from ")):
            insert_index = i + 1
            continue
        if not stripped.startswith("#"):
            break

    lines.insert(insert_index, "from contextlib import suppress")
    return "\n".join(lines)


def _flatten_suppress_tuple(content: str, file_path: Path) -> FixResult | None:
    new_content = re.sub(
        r"with suppress\(\(([^()]+)\)\)",
        r"with suppress(\1)",
        content,
        count=1,
    )
    if new_content == content:
        return None

    new_content = _ensure_contextlib_suppress_import(new_content)

    if _write_file(file_path, new_content):
        return FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=["Flattened suppress() exception tuple"],
            files_modified=[str(file_path)],
        )

    return None


def _try_fix_path_str_type_error(
    issue: Issue, content: str, file_path: Path
) -> FixResult | None:
    message_lower = issue.message.lower()

    if not any(
        indicator in message_lower
        for indicator in (
            "arg-type",
            "argument of type",
            "incompatible type",
            "path",
            "str",
        )
    ):
        return None

    if "suppress" in message_lower and "with suppress((" in content:
        suppress_result = _flatten_suppress_tuple(content, file_path)
        if suppress_result is not None:
            return suppress_result

    if "path" not in message_lower or "str" not in message_lower:
        return None

    return _fix_path_str_patterns(content, file_path)


async def _try_fix_type_annotation(
    issue: Issue, content: str, file_path: Path, confidence: float
) -> FixResult:
    try:
        tree = ast.parse(content)
        lines = content.splitlines(keepends=True)

        fixed = False

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.returns is None and not any(
                    decorator.id == "property"
                    for decorator in node.decorator_list
                    if isinstance(decorator, ast.Name)
                ):
                    func_line = node.lineno - 1
                    if func_line < len(lines):
                        line = lines[func_line]
                        if ":" in line and "->" not in line:
                            lines[func_line] = line.replace(":", " -> None:", 1)
                            fixed = True

        if fixed:
            fixed_content = "".join(lines)

            if _write_file(file_path, fixed_content):
                return FixResult(
                    success=True,
                    confidence=confidence,
                    fixes_applied=["Added type annotation"],
                    files_modified=[str(file_path)],
                )

    except Exception as e:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to add type annotation: {e}"],
        )

    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=["No changes applied"],
    )


async def fix_type_error(issue: Issue) -> FixResult:
    confidence = await is_fixable_type_error(issue)
    if confidence == 0.0:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Type error too complex for auto-fix: {issue.message}"],
        )

    if not issue.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path provided"],
        )

    file_path = Path(issue.file_path)
    content = _read_file(file_path)
    if not content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Could not read file"],
        )

    path_str_result = _try_fix_path_str_type_error(issue, content, file_path)
    if path_str_result is not None:
        return path_str_result

    return await _try_fix_type_annotation(issue, content, file_path, confidence)


def _validate_plan(plan: FixPlan) -> FixResult | None:
    if not plan.changes:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Plan has no changes to apply"],
            recommendations=["PlanningAgent should generate actual changes"],
        )

    if not plan.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path in plan"],
            recommendations=["FixPlan must have file_path"],
        )
    return None


async def _read_file_safe(plan: FixPlan) -> tuple[str, str] | FixResult | None:
    try:
        file_content = Path(plan.file_path).read_text(encoding="utf-8")
        return file_content, plan.file_path
    except Exception as e:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {e}"],
        )


def _apply_standard_fix_change(
    plan: FixPlan,
    file_content: str,
    change: ChangeSpec,
    index: int,
    applied_changes: list[str],
    failed_changes: list[str],
) -> None:
    lines = file_content.split("\n")
    if change.line_range[0] < 1 or change.line_range[1] > len(lines):
        message = (
            f"Change {index}: Invalid line range {change.line_range} "
            f"(file has {len(lines)} lines)"
        )
        failed_changes.append(message)
        return

    start_idx = change.line_range[0] - 1
    end_idx = change.line_range[1]
    old_lines = lines[start_idx:end_idx]

    first_line = old_lines[0] if old_lines else ""
    indent_match = re.match(r"^(\s*)", first_line)
    base_indent = indent_match.group(1) if indent_match else ""

    new_code_lines = change.new_code.split("\n")
    indented_new_lines = []
    for j, line in enumerate(new_code_lines):
        if j == 0:
            indented_new_lines.append(base_indent + line.lstrip())
        else:
            indented_new_lines.append(line)

    new_lines = lines[:start_idx] + indented_new_lines + lines[end_idx:]
    new_content = "\n".join(new_lines)

    success = _write_file(plan.file_path, new_content)
    if success:
        applied_changes.append(f"Change {index}: {change.reason}")
    else:
        message = f"Change {index} failed: {change.reason}"
        failed_changes.append(message)


def _apply_ast_transform_change(
    file_path: str,
    change: ChangeSpec,
    index: int,
    applied_changes: list[str],
    failed_changes: list[str],
) -> bool:
    if not change.reason.startswith("AST transform"):
        return False

    success = _write_file(file_path, change.new_code)
    if success:
        applied_changes.append(f"Change {index}: {change.reason}")
    else:
        message = f"Failed to write AST transform to {file_path}: {change.reason}"
        failed_changes.append(message)
    return True


def _apply_all_changes(plan: FixPlan, file_content: str) -> tuple[list[str], list[str]]:
    applied_changes: list[str] = []
    failed_changes: list[str] = []
    for i, change in enumerate(plan.changes):
        try:
            if _apply_ast_transform_change(
                plan.file_path,
                change,
                i,
                applied_changes,
                failed_changes,
            ):
                continue

            _apply_standard_fix_change(
                plan,
                file_content,
                change,
                i,
                applied_changes,
                failed_changes,
            )
        except Exception as e:
            message = f"Change {i} failed: {e}"
            failed_changes.append(message)
    return applied_changes, failed_changes


def _apply_ruff_formatting(plan_file_path: str, project_root: Path) -> None:
    with suppress(Exception):
        subprocess.run(
            ["ruff", "format", plan_file_path],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=30,
        )


def _issue_from_fix_plan(plan: FixPlan) -> Issue | None:
    if not plan.changes:
        return None

    line_number = plan.changes[0].line_range[0]
    if line_number <= 0:
        return None

    return Issue(
        type=IssueType.COMPLEXITY,
        severity=Priority.LOW,
        message=plan.issue_message or plan.rationale or "Complexity fix plan",
        file_path=plan.file_path,
        line_number=line_number,
        details=plan.issue_details.copy(),
        stage=plan.issue_stage or plan.issue_type.lower(),
    )


def _complexity_still_exceeds_threshold(
    file_path: str,
    line_number: int | None,
) -> bool:
    if line_number is None:
        return True

    content = _read_file(file_path)
    if not content:
        return True

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return True

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        node_end = node.end_lineno or node.lineno
        if not (node.lineno <= line_number <= node_end):
            continue

        source_segment = ast.get_source_segment(content, node) or ""
        if not source_segment:
            return True

        return _estimate_function_complexity(source_segment) > 15

    return True


def _handle_complexity_fallback(
    plan: FixPlan,
    plan_file_path: str,
    success: bool,
    confidence: float,
    applied_changes: list[str],
) -> tuple[bool, float, list[str]]:
    if not (success and plan.issue_type.strip().upper() == "COMPLEXITY"):
        return success, confidence, applied_changes

    complexity_issue = _issue_from_fix_plan(plan)
    if not complexity_issue:
        return success, confidence, applied_changes

    if not _complexity_still_exceeds_threshold(
        plan_file_path,
        complexity_issue.line_number,
    ):
        return success, confidence, applied_changes

    fallback_result = _apply_complexity_noqa_fallback(
        Path(plan_file_path),
        complexity_issue,
    )
    if fallback_result is not None:
        applied_changes.extend(fallback_result.fixes_applied)
        confidence = max(confidence, fallback_result.confidence)
        success = True

    return success, confidence, applied_changes


async def execute_fix_plan(plan: FixPlan, project_root: Path) -> FixResult | None:
    validation_result = _validate_plan(plan)
    if validation_result:
        return validation_result

    file_content_result = await _read_file_safe(plan)
    if not file_content_result:
        return None
    if isinstance(file_content_result, FixResult):
        return file_content_result

    file_content, plan_file_path = file_content_result
    applied_changes, failed_changes = _apply_all_changes(plan, file_content)
    success = len(applied_changes) == len(plan.changes)
    confidence = 0.8 if success else 0.0

    success, confidence, applied_changes = _handle_complexity_fallback(
        plan, plan_file_path, success, confidence, applied_changes
    )

    if success and plan_file_path.endswith(".py"):
        _apply_ruff_formatting(plan_file_path, project_root)

    remaining_issues = [] if success else failed_changes
    if not success and not remaining_issues:
        remaining_issues = [f"Failed to apply planned changes to {plan.file_path}"]

    return FixResult(
        success=success,
        confidence=confidence,
        fixes_applied=applied_changes,
        remaining_issues=remaining_issues,
        files_modified=[plan.file_path] if success else [],
        recommendations=[],
    )

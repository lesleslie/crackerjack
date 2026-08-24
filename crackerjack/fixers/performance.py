"""Deterministic performance hot-spot detection and optimization fixer.

Extracted from ``crackerjack.agents.performance_agent.PerformanceAgent`` (and
the three helper classes it delegated to under
``crackerjack.agents.helpers.performance``): ``PerformanceASTAnalyzer``,
``PerformancePatternDetector``, and ``PerformanceRecommender``. Two of those
three (``PerformanceASTAnalyzer`` and ``PerformancePatternDetector``) stored a
``context: AgentContext`` but never actually read from it (verified via
grep), so flattening them into plain module-level functions here changes
nothing behaviorally. The third (``PerformanceRecommender``) only ever used
``self.context`` for an optional ``self.context.log(...)`` call, which is a
no-op ``pass`` on the ``SubAgent`` base class; that hook is dropped along
with the rest of the coordinator plumbing.

What was intentionally dropped versus the original ``PerformanceAgent``:

- ``SubAgent``/coordinator dispatch plumbing: ``can_handle`` and
  ``get_supported_types`` — these only ever decided *whether* and *how
  confidently* this fixer should run for a given ``Issue``; that routing job
  belongs to whatever calls into this module now, not to the module itself.
- Semantic/session-buddy enhancement: ``_detect_semantic_performance_issues``
  (which combined ``PerformanceASTAnalyzer.extract_performance_critical_functions``
  with ``semantic_enhancer.find_similar_patterns``, an embeddings/session-storage
  lookup), ``PerformanceASTAnalyzer.analyze_performance_patterns`` (which only
  ever consumed the semantic-search result produced by the method above), and
  the ``get_session_enhanced_recommendations``/``semantic_enhancer`` calls
  inside ``_generate_enhanced_recommendations`` — these depended on the
  embeddings/session-storage learning system being removed alongside the
  rest of the AI-fix machinery. ``extract_performance_critical_functions``
  itself (the real, dependency-free AST hot-spot finder) is ported below as
  ``extract_performance_critical_functions``; only its semantic-search caller
  is gone.
- ``PerformanceASTAnalyzer.analyze_code_metrics`` — dead code with no callers
  anywhere in the original source (verified via grep); it was never wired
  into the performance-issue detection/fix pipeline.
- Cross-file, cross-call session bookkeeping: ``PerformanceAgent.performance_metrics``
  and ``PerformanceAgent._generate_optimization_summary`` accumulated
  wall-clock timing and fix counts across every ``analyze_and_fix`` call made
  to one long-lived agent instance during a coordinator "session" — that
  session concept doesn't exist once there's no persistent coordinator-managed
  agent instance.

Disclosed behavior change (not a drop, a statefulness change to logic that
*is* kept): in the original, ``PerformanceAgent.__init__`` constructs exactly
one ``PerformanceRecommender`` and reuses it for the agent's entire
lifetime. Its ``optimization_stats`` dict is initialized once in
``PerformanceRecommender.__init__`` and only ever mutated via ``+=`` —
never reset — so ``PerformanceRecommender.generate_optimization_summary()``
in the original is cross-call cumulative over that agent instance's
lifetime, the same category of statefulness as ``performance_metrics``
above, not a "reports what changed in this call only" summary. Below,
``generate_optimization_summary`` is kept but made deliberately per-call:
``_apply_and_save_optimizations`` calls ``create_optimization_stats()``
fresh on every invocation of ``optimize_performance``, so the summary
embedded in each returned ``FixResult.fixes_applied`` reflects only that
call's transforms. This is an intentional, disclosed behavior change
(cumulative-across-session → reset-per-call), made for the same reason
``performance_metrics`` was dropped rather than ported as-is: there is no
persistent agent instance left to accumulate state across calls, and a
per-call summary is arguably more correct/less leaky than the original's
cross-file accumulation. No currently-known caller depends on the old
cumulative behavior.
- ``AgentContext``-specific file I/O (path-traversal checks, the no-op
  ``context.log`` hook, and ``write_file_content``'s ``wrap_long_lines``
  post-processing which itself imports from the to-be-removed ``ai_fix``
  package) — replaced with direct ``pathlib.Path`` reads/writes via
  ``_read_file``/``_write_file`` below. Real file I/O is still performed;
  only the framework wrapper around it is gone.

Renames worth noting for anyone diffing against the original: the
``SubAgent.analyze_and_fix`` entry point becomes ``optimize_performance``
below (same validate/read/detect/apply/save flow, minus the ``self``/
``AgentContext`` plumbing); ``_generate_enhanced_recommendations`` becomes
``_generate_recommendations`` (same "benchmark + per-issue suggestion"
recommendation list, minus the semantic/session-buddy additions described
above).
"""

from __future__ import annotations

import ast
import operator
import re
import typing as t
from dataclasses import dataclass
from pathlib import Path

from crackerjack.models.issues import FixResult, Issue
from crackerjack.services.regex_patterns import SAFE_PATTERNS


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


def extract_performance_critical_functions(content: str) -> list[dict[str, t.Any]]:
    functions: list[dict[str, t.Any]] = []
    lines = content.split("\n")
    current_function = None

    for i, line in enumerate(lines):
        stripped = line.strip()

        if _is_empty_or_comment_line(stripped):
            if current_function:
                current_function["body"] += line + "\n"
            continue

        indent = len(line) - len(line.lstrip())

        if _is_function_definition(stripped):
            current_function = _handle_function_definition(
                current_function,
                functions,
                stripped,
                indent,
                i,
            )
        elif current_function:
            current_function = _handle_function_body_line(
                current_function,
                functions,
                line,
                stripped,
                indent,
                i,
            )

    _handle_last_function(current_function, functions, len(lines))
    return functions


def _is_empty_or_comment_line(stripped: str) -> bool:
    return not stripped or stripped.startswith("#")


def _is_function_definition(stripped: str) -> bool:
    return stripped.startswith("def ") and "(" in stripped


def _handle_function_definition(
    current_function: dict[str, t.Any] | None,
    functions: list[dict[str, t.Any]],
    stripped: str,
    indent: int,
    line_number: int,
) -> dict[str, t.Any]:
    if current_function and _is_performance_critical(current_function):
        _finalize_function(current_function, functions, line_number)

    func_name = stripped.split("(")[0].replace("def ", "").strip()
    return {
        "name": func_name,
        "signature": stripped,
        "start_line": line_number + 1,
        "body": "",
        "indent_level": indent,
    }


def _handle_function_body_line(
    current_function: dict[str, t.Any],
    functions: list[dict[str, t.Any]],
    line: str,
    stripped: str,
    indent: int,
    line_number: int,
) -> dict[str, t.Any] | None:
    if _is_still_in_function(current_function, indent, stripped):
        current_function["body"] += line + "\n"
        return current_function
    if _is_performance_critical(current_function):
        _finalize_function(current_function, functions, line_number)
    return None


def _is_still_in_function(
    current_function: dict[str, t.Any],
    indent: int,
    stripped: str,
) -> bool:
    return indent > current_function["indent_level"] or (
        indent == current_function["indent_level"]
        and stripped.startswith(('"', "'", "@"))
    )


def _finalize_function(
    function: dict[str, t.Any],
    functions: list[dict[str, t.Any]],
    end_line: int,
) -> None:
    function["end_line"] = end_line
    function["body_sample"] = function["body"][:300]
    function["estimated_complexity"] = _estimate_complexity(function["body"])
    functions.append(function)


def _handle_last_function(
    current_function: dict[str, t.Any] | None,
    functions: list[dict[str, t.Any]],
    total_lines: int,
) -> None:
    if current_function and _is_performance_critical(current_function):
        _finalize_function(current_function, functions, total_lines)


def _is_performance_critical(function_info: dict[str, t.Any]) -> bool:
    body = function_info.get("body", "")
    name = function_info.get("name", "")

    performance_indicators = [
        "for " in body
        and len([line for line in body.split("\n") if "for " in line]) > 1,
        "while " in body,
        body.count("for ") > 0 and len(body) > 200,
        any(pattern in body for pattern in (".append(", "+=", ".extend(", "len(")),
        any(
            pattern in name
            for pattern in (
                "process",
                "analyze",
                "compute",
                "calculate",
                "optimize",
            )
        ),
        "range(" in body and ("1000" in body or "len(" in body),
    ]

    return any(performance_indicators)


def _estimate_complexity(body: str) -> int:
    complexity = 1

    nested_for_loops = 0
    for_depth = 0
    lines = body.split("\n")

    for line in lines:
        stripped = line.strip()
        if "for " in stripped:
            for_depth += 1
            nested_for_loops = max(nested_for_loops, for_depth)
        elif (
            stripped
            and not stripped.startswith("#")
            and len(line) - len(line.lstrip()) == 0
        ):
            for_depth = 0

    complexity = max(complexity, nested_for_loops)

    if ".sort(" in body or "sorted(" in body:
        complexity += 1
    if body.count("len(") > 5:
        complexity += 1
    if ".index(" in body or ".find(" in body:
        complexity += 1

    return complexity


def detect_performance_issues(content: str, file_path: t.Any) -> list[dict[str, t.Any]]:
    issues: list[dict[str, t.Any]] = []

    try:
        tree = ast.parse(content)
    except SyntaxError:
        return issues

    nested_issues = _detect_nested_loops_enhanced(tree)
    issues.extend(nested_issues)

    list_issues = _detect_inefficient_list_ops_enhanced(content, tree)
    issues.extend(list_issues)

    repeated_issues = _detect_repeated_operations_enhanced(content, tree)
    issues.extend(repeated_issues)

    string_issues = _detect_string_inefficiencies_enhanced(content)
    issues.extend(string_issues)

    comprehension_issues = _detect_list_comprehension_opportunities(tree)
    issues.extend(comprehension_issues)

    builtin_issues = _detect_inefficient_builtin_usage(tree, content)
    issues.extend(builtin_issues)

    return issues


def _detect_nested_loops_enhanced(tree: ast.AST) -> list[dict[str, t.Any]]:
    analyzer = NestedLoopAnalyzer()
    analyzer.visit(tree)
    return _build_nested_loop_issues(analyzer)


def _build_nested_loop_issues(analyzer: NestedLoopAnalyzer) -> list[dict[str, t.Any]]:
    if not analyzer.nested_loops:
        return []

    return [
        {
            "type": "nested_loops_enhanced",
            "instances": analyzer.nested_loops,
            "hotspots": analyzer.complexity_hotspots,
            "total_count": len(analyzer.nested_loops),
            "high_priority_count": _count_high_priority_loops(analyzer.nested_loops),
            "suggestion": _generate_nested_loop_suggestions(analyzer.nested_loops),
        },
    ]


def _count_high_priority_loops(nested_loops: list[dict[str, t.Any]]) -> int:
    return len([n for n in nested_loops if n["priority"] in ("high", "critical")])


def _generate_nested_loop_suggestions(nested_loops: list[dict[str, t.Any]]) -> str:
    suggestions = []

    critical_count = len([n for n in nested_loops if n.get("priority") == "critical"])
    high_count = len([n for n in nested_loops if n.get("priority") == "high"])

    if critical_count > 0:
        suggestions.append(
            f"CRITICAL: {critical_count} O(n⁴+) loops need immediate algorithmic redesign",
        )
    if high_count > 0:
        suggestions.append(
            f"HIGH: {high_count} O(n³) loops should use memoization/caching",
        )

    suggestions.extend(
        [
            "Consider: 1) Hash tables for lookups 2) List comprehensions 3) NumPy for numerical operations",
            "Profile: Use timeit or cProfile to measure actual performance impact",
        ],
    )

    return "; ".join(suggestions)


def _detect_inefficient_list_ops_enhanced(
    content: str,
    tree: ast.AST,
) -> list[dict[str, t.Any]]:
    analyzer = ListOpAnalyzer()
    analyzer.visit(tree)

    if not analyzer.list_ops:
        return []

    return _build_list_ops_issues(analyzer)


def _build_list_ops_issues(analyzer: ListOpAnalyzer) -> list[dict[str, t.Any]]:
    total_impact = sum(int(op["impact_factor"]) for op in analyzer.list_ops)
    high_impact_ops = [op for op in analyzer.list_ops if int(op["impact_factor"]) >= 10]

    return [
        {
            "type": "inefficient_list_operations_enhanced",
            "instances": analyzer.list_ops,
            "total_impact": total_impact,
            "high_impact_count": len(high_impact_ops),
            "suggestion": _generate_list_op_suggestions(analyzer.list_ops),
        },
    ]


def _generate_list_op_suggestions(list_ops: list[dict[str, t.Any]]) -> str:
    suggestions = []

    high_impact_count = len([op for op in list_ops if int(op["impact_factor"]) >= 10])
    if high_impact_count > 0:
        suggestions.append(
            f"HIGH IMPACT: {high_impact_count} list[t.Any] operations in hot loops",
        )

    append_count = len([op for op in list_ops if op["optimization"] == "append"])
    extend_count = len([op for op in list_ops if op["optimization"] == "extend"])

    if append_count > 0:
        suggestions.append(f"Replace {append_count} += [item] with .append(item)")
    if extend_count > 0:
        suggestions.append(f"Replace {extend_count} += multiple_items with .extend()")

    suggestions.append("Expected performance gains: 2-50x depending on loop context")

    return "; ".join(suggestions)


def _detect_repeated_operations_enhanced(
    content: str,
    tree: ast.AST,
) -> list[dict[str, t.Any]]:
    lines = content.split("\n")
    repeated_calls = _find_expensive_operations_in_loops(lines)

    return _create_repeated_operations_issues(repeated_calls)


def _find_expensive_operations_in_loops(lines: list[str]) -> list[dict[str, t.Any]]:
    repeated_calls: list[dict[str, t.Any]] = []
    expensive_patterns = _get_expensive_operation_patterns()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if _contains_expensive_operation(stripped, expensive_patterns) and (
            _is_in_loop_context(lines, i)
        ):
            repeated_calls.append(_create_operation_record(i, stripped))

    return repeated_calls


def _get_expensive_operation_patterns() -> tuple[str, ...]:
    return (
        ".exists()",
        ".read_text()",
        ".glob(",
        ".rglob(",
        "Path(",
        "len(",
        ".get(",
    )


def _contains_expensive_operation(line: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in line for pattern in patterns)


def _is_in_loop_context(lines: list[str], line_index: int) -> bool:
    context_start = max(0, line_index - 5)
    context_lines = lines[context_start : line_index + 1]

    loop_keywords = ("for ", "while ")
    return any(
        any(keyword in ctx_line for keyword in loop_keywords)
        for ctx_line in context_lines
    )


def _create_operation_record(line_index: int, content: str) -> dict[str, t.Any]:
    return {
        "line_number": line_index + 1,
        "content": content,
        "type": "expensive_operation_in_loop",
    }


def _create_repeated_operations_issues(
    repeated_calls: list[dict[str, t.Any]],
) -> list[dict[str, t.Any]]:
    if len(repeated_calls) >= 2:
        return [
            {
                "type": "repeated_expensive_operations",
                "instances": repeated_calls,
                "suggestion": "Cache expensive operations outside loops",
            },
        ]
    return []


def _detect_string_inefficiencies_enhanced(content: str) -> list[dict[str, t.Any]]:
    issues: list[dict[str, t.Any]] = []
    lines = content.split("\n")

    string_concat_patterns = []
    inefficient_joins = []
    repeated_format_calls = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        if "+=" in stripped and any(quote in stripped for quote in ('"', "'")):
            if _is_in_loop_context_enhanced(lines, i):
                context_info = _analyze_string_context(lines, i)
                string_concat_patterns.append(
                    {
                        "line_number": i + 1,
                        "content": stripped,
                        "context": context_info,
                        "estimated_impact": int(
                            context_info.get("impact_factor", "1"),
                        ),
                    },
                )

        if ".join([])" in stripped:
            inefficient_joins.append(
                {
                    "line_number": i + 1,
                    "content": stripped,
                    "optimization": "Use empty string literal instead",
                    "performance_gain": "2x",
                },
            )

        if any(pattern in stripped for pattern in ('f"', ".format(", "% ")) and (
            _is_in_loop_context_enhanced(lines, i)
        ):
            repeated_format_calls.append(
                {
                    "line_number": i + 1,
                    "content": stripped,
                    "optimization": "Move formatting outside loop if static",
                },
            )

    total_issues = (
        len(string_concat_patterns)
        + len(inefficient_joins)
        + len(repeated_format_calls)
    )

    if total_issues > 0:
        issues.append(
            {
                "type": "string_inefficiencies_enhanced",
                "string_concat_patterns": string_concat_patterns,
                "inefficient_joins": inefficient_joins,
                "repeated_formatting": repeated_format_calls,
                "total_count": total_issues,
                "suggestion": _generate_string_suggestions(
                    string_concat_patterns,
                    inefficient_joins,
                    repeated_format_calls,
                ),
            },
        )

    return issues


def _analyze_string_context(lines: list[str], line_idx: int) -> dict[str, t.Any]:
    context = _create_default_string_context()
    loop_context = _find_loop_context_in_lines(lines, line_idx)

    if loop_context:
        context.update(loop_context)

    return context


def _create_default_string_context() -> dict[str, t.Any]:
    return {
        "loop_type": "unknown",
        "loop_depth": 1,
        "impact_factor": "1",
    }


def _find_loop_context_in_lines(
    lines: list[str],
    line_idx: int,
) -> dict[str, t.Any] | None:
    for i in range(max(0, line_idx - 10), line_idx):
        line = lines[i].strip()
        loop_context = _analyze_single_line_for_loop_context(line)
        if loop_context:
            return loop_context
    return None


def _analyze_single_line_for_loop_context(line: str) -> dict[str, t.Any] | None:
    if "for " in line and " in " in line:
        return _analyze_for_loop_context(line)
    if "while " in line:
        return _analyze_while_loop_context()
    return None


def _analyze_for_loop_context(line: str) -> dict[str, t.Any]:
    context = {"loop_type": "for"}

    if "range(" in line:
        impact_factor = _estimate_range_impact_factor(line)
        context["impact_factor"] = str(impact_factor)
    else:
        context["impact_factor"] = "2"

    return context


def _analyze_while_loop_context() -> dict[str, t.Any]:
    return {
        "loop_type": "while",
        "impact_factor": "3",
    }


def _estimate_range_impact_factor(line: str) -> int:
    try:
        pattern_obj = SAFE_PATTERNS["extract_range_size"]
        if not pattern_obj.test(line):
            return 2

        range_str = pattern_obj.apply(line)
        range_size = _extract_range_size_from_string(range_str)

        return _calculate_impact_from_range_size(range_size)
    except ValueError, AttributeError:
        return 2


def _extract_range_size_from_string(range_str: str) -> int:
    number_match = re.search(r"\d+", range_str)
    if number_match:
        return int(number_match.group())
    return 0


def _calculate_impact_from_range_size(range_size: int) -> int:
    if range_size > 1000:
        return 10
    if range_size > 100:
        return 5
    return 2


def _is_in_loop_context_enhanced(lines: list[str], line_index: int) -> bool:
    context_start = max(0, line_index - 8)
    context_lines = lines[context_start : line_index + 1]

    for ctx_line in context_lines:
        pattern_obj = SAFE_PATTERNS["match_loop_patterns"]
        candidate = ctx_line.split("#", 1)[0]
        if pattern_obj.test(candidate):
            return True
        stripped = candidate.strip()
        if stripped.startswith(("for ", "while ")) and stripped.endswith(":"):
            return True

    return False


def _generate_string_suggestions(
    concat_patterns: list[dict[str, t.Any]],
    inefficient_joins: list[dict[str, t.Any]],
    repeated_formatting: list[dict[str, t.Any]],
) -> str:
    suggestions = []

    if concat_patterns:
        high_impact = len(
            [p for p in concat_patterns if p.get("estimated_impact", 1) >= 5],
        )
        suggestions.append(
            f"String concatenation: {len(concat_patterns)} instances "
            f"({high_impact} high-impact) - use list[t.Any].append + join",
        )

    if inefficient_joins:
        suggestions.append(
            f"Empty joins: {len(inefficient_joins)} - use empty string literal",
        )

    if repeated_formatting:
        suggestions.append(
            f"Repeated formatting: {len(repeated_formatting)} - cache format strings",
        )

    suggestions.append("Expected gains: 3-50x for string building in loops")
    return "; ".join(suggestions)


def _detect_list_comprehension_opportunities(tree: ast.AST) -> list[dict[str, t.Any]]:
    issues: list[dict[str, t.Any]] = []

    class ComprehensionAnalyzer(ast.NodeVisitor):
        def __init__(self) -> None:
            self.opportunities: list[dict[str, t.Any]] = []

        def visit_For(self, node: ast.For) -> None:
            if (
                len(node.body) == 1
                and isinstance(node.body[0], ast.Expr)
                and isinstance(
                    node.body[0].value,
                    ast.Call,
                )
                and isinstance(
                    node.body[0].value.func,
                    ast.Attribute,
                )
                and node.body[0].value.func.attr == "append"
            ):
                self.opportunities.append(
                    {
                        "line_number": node.lineno,
                        "type": "append_loop_to_comprehension",
                        "optimization": "list_comprehension",
                        "performance_gain": "20-30% faster",
                        "readability": "improved",
                    },
                )

            self.generic_visit(node)

    analyzer = ComprehensionAnalyzer()
    analyzer.visit(tree)

    if analyzer.opportunities:
        issues.append(
            {
                "type": "list_comprehension_opportunities",
                "instances": analyzer.opportunities,
                "total_count": len(analyzer.opportunities),
                "suggestion": f"Convert {len(analyzer.opportunities)} append loops"
                f" to list[t.Any] comprehensions for better performance "
                f"and readability",
            },
        )

    return issues


def _detect_inefficient_builtin_usage(
    tree: ast.AST,
    content: str,
) -> list[dict[str, t.Any]]:
    issues: list[dict[str, t.Any]] = []

    class BuiltinAnalyzer(ast.NodeVisitor):
        def __init__(self) -> None:
            self.inefficient_calls: list[dict[str, t.Any]] = []
            self.in_loop = False

        def visit_For(self, node: ast.For) -> None:
            old_in_loop = self.in_loop
            self.in_loop = True
            self.generic_visit(node)
            self.in_loop = old_in_loop

        def visit_While(self, node: ast.While) -> None:
            old_in_loop = self.in_loop
            self.in_loop = True
            self.generic_visit(node)
            self.in_loop = old_in_loop

        def visit_Call(self, node: ast.Call) -> None:
            if self.in_loop and isinstance(node.func, ast.Name):
                func_name = node.func.id

                if func_name in ("len", "sum", "max", "min", "sorted") and (
                    node.args and isinstance(node.args[0], ast.Name)
                ):
                    self.inefficient_calls.append(
                        {
                            "line_number": node.lineno,
                            "function": func_name,
                            "type": "repeated_builtin_in_loop",
                            "optimization": f"Cache {func_name}() result outside loop",
                            "performance_gain": "2-10x depending on data size",
                        },
                    )

            self.generic_visit(node)

    analyzer = BuiltinAnalyzer()
    analyzer.visit(tree)

    if analyzer.inefficient_calls:
        issues.append(
            {
                "type": "inefficient_builtin_usage",
                "instances": analyzer.inefficient_calls,
                "total_count": len(analyzer.inefficient_calls),
                "suggestion": f"Cache {len(analyzer.inefficient_calls)} "
                f"repeated builtin calls outside loops",
            },
        )

    return issues


class NestedLoopAnalyzer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.nested_loops: list[dict[str, t.Any]] = []
        self.complexity_hotspots: list[dict[str, t.Any]] = []
        self._loop_stack: list[tuple[int, str]] = []

    def visit_For(self, node: ast.For) -> None:
        self._handle_loop_node(node, "for")
        self.generic_visit(node)
        self._loop_stack.pop()

    def visit_While(self, node: ast.While) -> None:
        self._handle_loop_node(node, "while")
        self.generic_visit(node)
        self._loop_stack.pop()

    def _handle_loop_node(self, node: ast.For | ast.While, loop_type: str) -> None:
        self._loop_stack.append((node.lineno, loop_type))

        if len(self._loop_stack) > 1:
            depth = len(self._loop_stack)
            complexity = self._calculate_loop_complexity(depth)
            priority = self._determine_priority(depth)

            self.nested_loops.append(
                {
                    "line_number": node.lineno,
                    "depth": depth,
                    "complexity": complexity,
                    "priority": priority,
                    "type": loop_type,
                },
            )

    @staticmethod
    def _calculate_loop_complexity(depth: int) -> str:
        if depth == 2:
            return "O(n²)"
        if depth == 3:
            return "O(n³)"
        if depth >= 4:
            return "O(n⁴+)"
        return "O(n)"

    @staticmethod
    def _determine_priority(depth: int) -> str:
        if depth >= 4:
            return "critical"
        if depth in {3, 2}:
            return "high"
        return "medium"


class ListOpAnalyzer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.list_ops: list[dict[str, t.Any]] = []
        self._in_loop = False

    def visit_For(self, node: ast.For) -> None:
        old_in_loop = self._in_loop
        self._in_loop = True
        self.generic_visit(node)
        self._in_loop = old_in_loop

    def visit_While(self, node: ast.While) -> None:
        old_in_loop = self._in_loop
        self._in_loop = True
        self.generic_visit(node)
        self._in_loop = old_in_loop

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if (
            self._in_loop
            and isinstance(node.op, ast.Add)
            and isinstance(node.value, ast.List)
        ):
            impact = len(node.value.elts) if node.value.elts else 1
            self.list_ops.append(
                {
                    "line_number": node.lineno,
                    "type": "inefficient_list_concat",
                    "optimization": "append" if len(node.value.elts) == 1 else "extend",
                    "impact_factor": impact,
                    "performance_gain": f"{max(2, min(50, impact * 5))}x",
                },
            )

        self.generic_visit(node)


@dataclass
class OptimizationResult:
    lines: list[str]
    modified: bool
    optimization_description: str | None = None


def create_optimization_stats() -> dict[str, int]:
    return {
        "nested_loops_optimized": 0,
        "list_ops_optimized": 0,
        "string_concat_optimized": 0,
        "repeated_ops_cached": 0,
        "comprehensions_applied": 0,
    }


def apply_performance_optimizations(
    content: str,
    issues: list[dict[str, t.Any]],
    stats: dict[str, int],
) -> str:
    lines = content.split("\n")
    modified = False

    for issue in issues:
        result = _process_single_issue(lines, issue, stats)
        if result.modified:
            lines = result.lines
            modified = True

    return "\n".join(lines) if modified else content


def _process_single_issue(
    lines: list[str],
    issue: dict[str, t.Any],
    stats: dict[str, int],
) -> OptimizationResult:
    issue_type = issue["type"]

    if issue_type in (
        "inefficient_list_operations",
        "inefficient_list_operations_enhanced",
    ):
        return _handle_list_operations_issue(lines, issue, stats)
    if issue_type in (
        "string_concatenation_in_loop",
        "string_inefficiencies_enhanced",
    ):
        return _handle_string_operations_issue(lines, issue, stats)
    if issue_type == "repeated_expensive_operations":
        return _handle_repeated_operations_issue(lines, issue, stats)
    if issue_type in ("nested_loops", "nested_loops_enhanced"):
        return _handle_nested_loops_issue(lines, issue, stats)
    if issue_type == "list_comprehension_opportunities":
        return _handle_comprehension_opportunities_issue(lines, issue, stats)
    if issue_type == "inefficient_builtin_usage":
        return _handle_builtin_usage_issue(lines, issue)
    return _create_no_change_result(lines)


def _handle_list_operations_issue(
    lines: list[str],
    issue: dict[str, t.Any],
    stats: dict[str, int],
) -> OptimizationResult:
    new_lines, changed = _fix_list_operations_enhanced(lines, issue)
    description = None

    if changed:
        instance_count = len(issue.get("instances", []))
        stats["list_ops_optimized"] += instance_count
        description = f"List operations: {instance_count}"

    return _create_optimization_result(new_lines, changed, description)


def _handle_string_operations_issue(
    lines: list[str],
    issue: dict[str, t.Any],
    stats: dict[str, int],
) -> OptimizationResult:
    new_lines, changed = _fix_string_operations_enhanced(lines, issue)
    description = None

    if changed:
        total_string_fixes = (
            len(issue.get("string_concat_patterns", []))
            + len(issue.get("inefficient_joins", []))
            + len(issue.get("repeated_formatting", []))
        )
        stats["string_concat_optimized"] += total_string_fixes
        description = f"String operations: {total_string_fixes}"

    return _create_optimization_result(new_lines, changed, description)


def _handle_repeated_operations_issue(
    lines: list[str],
    issue: dict[str, t.Any],
    stats: dict[str, int],
) -> OptimizationResult:
    new_lines, changed = _fix_repeated_operations(lines, issue)

    if changed:
        stats["repeated_ops_cached"] += len(issue.get("instances", []))

    return _create_optimization_result(new_lines, changed)


def _handle_nested_loops_issue(
    lines: list[str],
    issue: dict[str, t.Any],
    stats: dict[str, int],
) -> OptimizationResult:
    new_lines, changed = _add_nested_loop_comments(lines, issue)

    if changed:
        stats["nested_loops_optimized"] += len(issue.get("instances", []))

    return _create_optimization_result(new_lines, changed)


def _handle_comprehension_opportunities_issue(
    lines: list[str],
    issue: dict[str, t.Any],
    stats: dict[str, int],
) -> OptimizationResult:
    new_lines, changed = _apply_list_comprehension_optimizations(lines, issue)

    if changed:
        stats["comprehensions_applied"] += len(issue.get("instances", []))

    return _create_optimization_result(new_lines, changed)


def _handle_builtin_usage_issue(
    lines: list[str],
    issue: dict[str, t.Any],
) -> OptimizationResult:
    new_lines, changed = _add_builtin_caching_comments(lines, issue)
    return _create_optimization_result(new_lines, changed)


def _create_optimization_result(
    lines: list[str],
    modified: bool,
    description: str | None = None,
) -> OptimizationResult:
    return OptimizationResult(
        lines=lines,
        modified=modified,
        optimization_description=description,
    )


def _create_no_change_result(lines: list[str]) -> OptimizationResult:
    return OptimizationResult(
        lines=lines,
        modified=False,
        optimization_description=None,
    )


def _fix_list_operations_enhanced(
    lines: list[str],
    issue: dict[str, t.Any],
) -> tuple[list[str], bool]:
    modified = False

    instances = sorted(
        issue["instances"],
        key=operator.itemgetter("line_number"),
        reverse=True,
    )

    for raw_instance in instances:
        instance = t.cast(dict[str, t.Any], raw_instance)
        line_idx = instance["line_number"] - 1
        if line_idx < len(lines):
            original_line = lines[line_idx]

            optimization_type = instance.get("optimization", "append")

            if optimization_type == "append":
                modified |= _handle_append_optimization(
                    lines,
                    instance,
                    line_idx,
                    original_line,
                )

            elif optimization_type == "extend":
                modified |= _handle_extend_optimization(
                    lines,
                    instance,
                    line_idx,
                    original_line,
                )

    return lines, modified


def _handle_append_optimization(
    lines: list[str],
    instance: dict[str, t.Any],
    line_idx: int,
    original_line: str,
) -> bool:
    list_pattern = SAFE_PATTERNS["list_append_inefficiency_pattern"]
    target_idx = line_idx
    current_line = original_line

    if not list_pattern.test(current_line):
        for candidate_idx in range(
            max(0, line_idx - 2),
            min(len(lines), line_idx + 3),
        ):
            if list_pattern.test(lines[candidate_idx]):
                target_idx = candidate_idx
                current_line = lines[candidate_idx]
                break

    if list_pattern.test(current_line):
        optimized_line = list_pattern.apply(current_line)
        lines[target_idx] = optimized_line

        indent = current_line[: len(current_line) - len(current_line.lstrip())]
        performance_gain = instance.get("performance_gain", "2x")
        comment = (
            f"{indent}# Performance: {performance_gain} improvement (append vs +=)"
        )
        lines.insert(target_idx, comment)
        return True

    return False


def _handle_extend_optimization(
    lines: list[str],
    instance: dict[str, t.Any],
    line_idx: int,
    original_line: str,
) -> bool:
    extend_pattern = SAFE_PATTERNS["list_extend_optimization_pattern"]
    target_idx = line_idx
    current_line = original_line

    if not extend_pattern.test(current_line):
        for candidate_idx in range(
            max(0, line_idx - 2),
            min(len(lines), line_idx + 3),
        ):
            if extend_pattern.test(lines[candidate_idx]):
                target_idx = candidate_idx
                current_line = lines[candidate_idx]
                break

    if extend_pattern.test(current_line):
        optimized_line = extend_pattern.apply(current_line)
        lines[target_idx] = optimized_line

        indent = current_line[: len(current_line) - len(current_line.lstrip())]
        performance_gain = instance.get("performance_gain", "x")
        impact_factor = int(instance.get("impact_factor", "1"))
        comment = (
            f"{indent}# Performance: {performance_gain} "
            f"improvement, impact factor: {impact_factor}"
        )
        lines.insert(target_idx, comment)
        return True

    return False


def _fix_string_operations_enhanced(
    lines: list[str],
    issue: dict[str, t.Any],
) -> tuple[list[str], bool]:
    modified = False

    concat_patterns = issue.get("string_concat_patterns", [])
    if concat_patterns:
        lines, concat_modified = _fix_string_concatenation(
            lines,
            {"instances": concat_patterns},
        )
        modified = modified or concat_modified

    inefficient_joins = issue.get("inefficient_joins", [])
    for join_issue in inefficient_joins:
        line_idx = join_issue["line_number"] - 1
        if line_idx < len(lines):
            original_line = lines[line_idx]
            join_pattern = SAFE_PATTERNS["inefficient_string_join_pattern"]
            if join_pattern.test(original_line):
                lines[line_idx] = join_pattern.apply(original_line)
                modified = True

    repeated_formatting = issue.get("repeated_formatting", [])
    for format_issue in repeated_formatting:
        line_idx = format_issue["line_number"] - 1
        if line_idx < len(lines):
            original_line = lines[line_idx]
            indent = original_line[: len(original_line) - len(original_line.lstrip())]
            comment = (
                f"{indent}# Performance: Consider caching format string outside loop"
            )
            lines.insert(line_idx, comment)
            modified = True

    return lines, modified


def _add_nested_loop_comments(
    lines: list[str],
    issue: dict[str, t.Any],
) -> tuple[list[str], bool]:
    modified = False

    instances: list[dict[str, t.Any]] = issue.get("instances", [])
    for instance in sorted(
        instances,
        key=operator.itemgetter("line_number"),
        reverse=True,
    ):
        line_idx = instance["line_number"] - 1
        if line_idx < len(lines):
            original_line = lines[line_idx]
            indent = original_line[: len(original_line) - len(original_line.lstrip())]

            complexity = _normalize_complexity_notation(
                instance.get("complexity", "O(n^2)"),
            )
            priority = instance.get("priority", "medium")
            priority_label = (
                priority.upper() if isinstance(priority, str) else str(priority)
            )

            comment_lines = [
                f"{indent}# Performance: {complexity} nested loop detected - {priority_label} priority",
            ]

            comment_lines.extend(_get_priority_specific_comments(indent, priority))

            for i, comment in enumerate(comment_lines):
                lines.insert(line_idx + i, comment)

            modified = True

    return lines, modified


def _normalize_complexity_notation(complexity: str) -> str:
    if isinstance(complexity, str):
        return complexity.replace("²", "^2").replace("³", "^3").replace("⁴", "^4")
    return complexity


def _get_priority_specific_comments(indent: str, priority: str) -> list[str]:
    comment_lines = []

    if priority in ("high", "critical"):
        if priority == "critical":
            comment_lines.append(
                f"{indent}# CRITICAL: Consider algorithmic redesign or"
                f" data structure changes",
            )
        else:
            comment_lines.append(
                f"{indent}# Suggestion: Consider memoization, caching,  or hash tables",
            )

    return comment_lines


def _apply_list_comprehension_optimizations(
    lines: list[str],
    issue: dict[str, t.Any],
) -> tuple[list[str], bool]:
    modified = False

    instances = issue.get("instances", [])
    for instance in sorted(
        instances,
        key=operator.itemgetter("line_number"),
        reverse=True,
    ):
        line_idx = instance["line_number"] - 1
        if line_idx < len(lines):
            original_line = lines[line_idx]
            indent = original_line[: len(original_line) - len(original_line.lstrip())]

            comment = (
                f"{indent}# Performance: Consider list[t.Any] comprehension for "
                f"20-30% improvement"
            )
            lines.insert(line_idx, comment)
            modified = True

    return lines, modified


def _add_builtin_caching_comments(
    lines: list[str],
    issue: dict[str, t.Any],
) -> tuple[list[str], bool]:
    modified = False

    instances: list[dict[str, t.Any]] = issue.get("instances", [])
    for instance in sorted(
        instances,
        key=operator.itemgetter("line_number"),
        reverse=True,
    ):
        line_idx = instance["line_number"] - 1
        if line_idx < len(lines):
            original_line = lines[line_idx]
            indent = original_line[: len(original_line) - len(original_line.lstrip())]

            func_name = instance.get("function", "builtin")
            performance_gain = instance.get("performance_gain", "2-10x")

            comment = (
                f"{indent}# Performance: Cache {func_name}() result outside"
                f" loop for {performance_gain} improvement"
            )
            lines.insert(line_idx, comment)
            modified = True

    return lines, modified


def _fix_string_concatenation(
    lines: list[str],
    issue: dict[str, t.Any],
) -> tuple[list[str], bool]:
    modified = False
    instances = issue.get("instances", [])

    if not instances:
        return lines, modified

    for raw_instance in sorted(
        instances,
        key=operator.itemgetter("line_number"),
        reverse=True,
    ):
        instance = t.cast(dict[str, t.Any], raw_instance)
        modified |= _process_single_concatenation_instance(lines, instance)

    return lines, modified


def _process_single_concatenation_instance(
    lines: list[str],
    instance: dict[str, t.Any],
) -> bool:
    original_idx = instance.get("line_number", 1) - 1
    target_content = instance.get("content", "").strip()
    candidate_indices: list[int] = _find_candidate_indices(
        lines,
        original_idx,
        target_content,
    )

    if not candidate_indices:
        return False

    line_idx = min(candidate_indices, key=lambda idx: abs(idx - original_idx))
    original_line = lines[line_idx]

    if "+=" not in original_line:
        return False

    return _fix_line_at_index(lines, line_idx, original_line)


def _find_candidate_indices(
    lines: list[str],
    original_idx: int,
    target_content: str,
) -> list[int]:
    if _is_valid_original_index(lines, original_idx, target_content):
        return [original_idx]

    if target_content:
        exact_matches = _find_exact_content_matches(lines, target_content)
        if exact_matches:
            return exact_matches

    return _find_pattern_matches(lines)


def _is_valid_original_index(
    lines: list[str],
    original_idx: int,
    target_content: str,
) -> bool:
    if not (0 <= original_idx < len(lines)):
        return False

    original_line = lines[original_idx]
    has_concat = "+=" in original_line
    matches_target = not target_content or original_line.strip() == target_content

    return has_concat and matches_target


def _find_exact_content_matches(lines: list[str], target_content: str) -> list[int]:
    return [idx for idx, line in enumerate(lines) if line.strip() == target_content]


def _find_pattern_matches(lines: list[str]) -> list[int]:
    return [idx for idx, line in enumerate(lines) if _is_concatenation_pattern(line)]


def _is_concatenation_pattern(line: str) -> bool:
    stripped = line.strip()
    has_concat = "+=" in stripped
    has_quotes = any(quote in stripped for quote in ('"', "'"))
    not_append = ".append(" not in stripped

    return has_concat and has_quotes and not_append


def _fix_line_at_index(lines: list[str], line_idx: int, original_line: str) -> bool:
    modified = False
    line_body, _sep, comment = original_line.partition("#")
    left, _, right = line_body.partition("+=")
    if not left.strip() or not right.strip():
        return False

    target = left.strip()
    expr = right.strip()

    current_indent = len(original_line) - len(original_line.lstrip())
    body_indent_str = " " * current_indent

    loop_start_idx = _find_loop_start_idx(lines, line_idx, current_indent)

    _parent_indent, parent_indent_str = _get_parent_indent_info(
        lines,
        loop_start_idx,
        current_indent,
    )

    parts_name = f"{target}_parts"
    line_idx += _ensure_parts_initialized(
        lines,
        loop_start_idx,
        line_idx,
        parts_name,
        parent_indent_str,
    )

    new_line = f"{body_indent_str}{parts_name}.append({expr})"
    if comment:
        new_line = f"{new_line} #{comment.strip()}"
    lines[line_idx] = new_line
    modified = True

    modified |= _add_join_statement(
        lines,
        loop_start_idx,
        line_idx,
        target,
        parts_name,
        parent_indent_str,
    )

    return modified


def _find_loop_start_idx(
    lines: list[str],
    line_idx: int,
    current_indent: int,
) -> int | None:
    for i in range(line_idx - 1, -1, -1):
        candidate = lines[i]
        stripped = candidate.lstrip()
        if not stripped:
            continue
        indent = len(candidate) - len(candidate.lstrip())
        if indent < current_indent and stripped.startswith(("for ", "while ")):
            return i
    return None


def _get_parent_indent_info(
    lines: list[str],
    loop_start_idx: int | None,
    current_indent: int,
) -> tuple[int, str]:
    parent_indent = (
        len(lines[loop_start_idx]) - len(lines[loop_start_idx].lstrip())
        if loop_start_idx is not None
        else current_indent
    )
    parent_indent_str = " " * parent_indent
    return parent_indent, parent_indent_str


def _ensure_parts_initialized(
    lines: list[str],
    loop_start_idx: int | None,
    line_idx: int,
    parts_name: str,
    parent_indent_str: str,
) -> int:
    has_parts_init = any(
        parts_name in line and line.strip().endswith("= []") for line in lines
    )
    if not has_parts_init:
        insert_at = loop_start_idx if loop_start_idx is not None else line_idx
        lines.insert(
            insert_at,
            f"{parent_indent_str}# Performance: build strings with list join",
        )
        lines.insert(insert_at + 1, f"{parent_indent_str}{parts_name} = []")
        if insert_at <= line_idx:
            return 2
        return 0
    return 0


def _add_join_statement(
    lines: list[str],
    loop_start_idx: int | None,
    line_idx: int,
    target: str,
    parts_name: str,
    parent_indent_str: str,
) -> bool:
    join_line = f"{parent_indent_str}{target} = ''.join({parts_name})"

    if join_line in lines:
        return False

    if loop_start_idx is not None:
        return _add_join_in_loop(lines, line_idx, join_line)
    return _add_join_after_line(lines, line_idx, join_line)


def _add_join_in_loop(lines: list[str], line_idx: int, join_line: str) -> bool:
    current_indent = len(lines[line_idx]) - len(lines[line_idx].lstrip())
    loop_body_indent = current_indent

    insert_at = _find_loop_end_insertion_point(lines, line_idx, loop_body_indent)

    lines.insert(insert_at, join_line)
    return True


def _find_loop_end_insertion_point(
    lines: list[str],
    line_idx: int,
    loop_body_indent: int,
) -> int:
    for j in range(line_idx + 1, len(lines)):
        candidate = lines[j]
        stripped = candidate.lstrip()
        if not stripped:
            continue
        indent = len(candidate) - len(candidate.lstrip())
        if indent < loop_body_indent:
            return j
    return len(lines)


def _add_join_after_line(lines: list[str], line_idx: int, join_line: str) -> bool:
    lines.insert(line_idx + 1, join_line)
    return True


def _fix_repeated_operations(
    lines: list[str],
    issue: dict[str, t.Any],
) -> tuple[list[str], bool]:
    modified = False

    for instance in issue["instances"]:
        line_idx = instance["line_number"] - 1
        if line_idx < len(lines):
            original_line = lines[line_idx]
            indent_level = len(original_line) - len(original_line.lstrip())
            indent_str = " " * indent_level

            comment = (
                f"{indent_str}# Performance: Consider caching this expensive"
                f" operation outside the loop"
            )
            lines.insert(line_idx, comment)
            modified = True

    return lines, modified


def generate_optimization_summary(stats: dict[str, int]) -> str:
    total_optimizations = sum(stats.values())
    if total_optimizations == 0:
        return "No optimizations applied in this session"

    summary_parts = [
        f"{opt_type}: {count}" for opt_type, count in stats.items() if count > 0
    ]

    return (
        f"Optimization Summary - {', '.join(summary_parts)} "
        f"(Total: {total_optimizations})"
    )


def _validate_performance_issue(issue: Issue) -> FixResult | None:
    if not issue.file_path:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path specified for performance issue"],
        )

    file_path = Path(issue.file_path)
    if not file_path.exists():
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"File not found: {file_path}"],
        )

    return None


def _create_no_optimization_result() -> FixResult:
    return FixResult(
        success=False,
        confidence=0.6,
        remaining_issues=["Could not automatically optimize performance"],
        recommendations=[
            "Manual optimization required",
            "Consider algorithm complexity improvements",
            "Review data structure choices",
            "Profile code execution for bottlenecks",
        ],
    )


def _create_performance_error_result(error: Exception) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[f"Error processing file: {error}"],
    )


def _generate_recommendations(issues: list[dict[str, t.Any]]) -> list[str]:
    recommendations = ["Test performance improvements with benchmarks"]
    for issue in issues:
        suggestion = issue.get("suggestion")
        if suggestion:
            recommendations.append(str(suggestion))

    return recommendations


def _apply_and_save_optimizations(
    file_path: Path,
    content: str,
    issues: list[dict[str, t.Any]],
) -> FixResult:
    stats = create_optimization_stats()
    optimized_content = apply_performance_optimizations(content, issues, stats)

    if optimized_content == content:
        return _create_no_optimization_result()

    success = _write_file(file_path, optimized_content)
    if not success:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Failed to write optimized file: {file_path}"],
        )

    stats_summary = generate_optimization_summary(stats)

    return FixResult(
        success=True,
        confidence=0.8,
        fixes_applied=[
            f"Optimized {len(issues)} performance issues",
            "Applied algorithmic improvements",
            stats_summary,
        ],
        files_modified=[str(file_path)],
        recommendations=_generate_recommendations(issues),
    )


def _process_performance_optimization(file_path: Path) -> FixResult:
    content = _read_file(file_path)
    if not content:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Could not read file: {file_path}"],
        )

    performance_issues = detect_performance_issues(content, file_path)

    if not performance_issues:
        return FixResult(
            success=True,
            confidence=0.7,
            recommendations=["No performance issues detected"],
        )

    return _apply_and_save_optimizations(file_path, content, performance_issues)


async def optimize_performance(issue: Issue) -> FixResult:
    validation_result = _validate_performance_issue(issue)
    if validation_result:
        return validation_result

    if issue.file_path is None:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["No file path provided for performance issue"],
        )

    file_path = Path(issue.file_path)

    try:
        return _process_performance_optimization(file_path)
    except Exception as e:
        return _create_performance_error_result(e)

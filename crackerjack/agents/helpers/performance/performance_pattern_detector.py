"""Pattern detection for performance anti-patterns in Python code."""

import ast
import operator
import typing as t
from contextlib import suppress

from ...base import AgentContext
from ...services.regex_patterns import SAFE_PATTERNS


class PerformancePatternDetector:
    """Detects performance anti-patterns in Python code using AST and pattern matching."""

    def __init__(self, context: AgentContext) -> None:
        """Initialize detector with agent context.

        Args:
            context: AgentContext for file operations and logging
        """
        self.context = context

    def detect_performance_issues(
        self,
        content: str,
        file_path: t.Any,
    ) -> list[dict[str, t.Any]]:
        """Detect all performance issues in content using pattern matching.

        Args:
            content: File content to analyze
            file_path: Path to the file

        Returns:
            List of detected performance issues
        """
        issues: list[dict[str, t.Any]] = []

        with suppress(SyntaxError):
            tree = ast.parse(content)

            nested_issues = self._detect_nested_loops_enhanced(tree)
            issues.extend(nested_issues)

            list_issues = self._detect_inefficient_list_ops_enhanced(content, tree)
            issues.extend(list_issues)

            repeated_issues = self._detect_repeated_operations_enhanced(content, tree)
            issues.extend(repeated_issues)

            string_issues = self._detect_string_inefficiencies_enhanced(content)
            issues.extend(string_issues)

            comprehension_issues = self._detect_list_comprehension_opportunities(tree)
            issues.extend(comprehension_issues)

            builtin_issues = self._detect_inefficient_builtin_usage(tree, content)
            issues.extend(builtin_issues)

        return issues

    def _detect_nested_loops_enhanced(self, tree: ast.AST) -> list[dict[str, t.Any]]:
        """Detect nested loops with complexity analysis.

        Args:
            tree: AST tree to analyze

        Returns:
            List of nested loop issues
        """
        analyzer = self._create_nested_loop_analyzer()
        analyzer.visit(tree)
        return self._build_nested_loop_issues(analyzer)

    @staticmethod
    def _create_nested_loop_analyzer() -> "NestedLoopAnalyzer":
        """Create AST analyzer for nested loops.

        Returns:
            NestedLoopAnalyzer instance
        """
        return NestedLoopAnalyzer()

    def _build_nested_loop_issues(
        self, analyzer: "NestedLoopAnalyzer"
    ) -> list[dict[str, t.Any]]:
        """Build issue data from nested loop analysis.

        Args:
            analyzer: NestedLoopAnalyzer instance

        Returns:
            List of issues
        """
        if not analyzer.nested_loops:
            return []

        return [
            {
                "type": "nested_loops_enhanced",
                "instances": analyzer.nested_loops,
                "hotspots": analyzer.complexity_hotspots,
                "total_count": len(analyzer.nested_loops),
                "high_priority_count": self._count_high_priority_loops(
                    analyzer.nested_loops
                ),
                "suggestion": self._generate_nested_loop_suggestions(
                    analyzer.nested_loops
                ),
            }
        ]

    @staticmethod
    def _count_high_priority_loops(nested_loops: list[dict[str, t.Any]]) -> int:
        """Count high priority nested loops.

        Args:
            nested_loops: List of nested loop instances

        Returns:
            Count of high priority loops
        """
        return len([n for n in nested_loops if n["priority"] in ("high", "critical")])

    @staticmethod
    def _generate_nested_loop_suggestions(nested_loops: list[dict[str, t.Any]]) -> str:
        """Generate optimization suggestions for nested loops.

        Args:
            nested_loops: List of nested loop instances

        Returns:
            Suggestion string
        """
        suggestions = []

        critical_count = len(
            [n for n in nested_loops if n.get("priority") == "critical"]
        )
        high_count = len([n for n in nested_loops if n.get("priority") == "high"])

        if critical_count > 0:
            suggestions.append(
                f"CRITICAL: {critical_count} O(n⁴+) loops need immediate algorithmic redesign"
            )
        if high_count > 0:
            suggestions.append(
                f"HIGH: {high_count} O(n³) loops should use memoization/caching"
            )

        suggestions.extend(
            [
                "Consider: 1) Hash tables for lookups 2) List comprehensions 3) NumPy for numerical operations",
                "Profile: Use timeit or cProfile to measure actual performance impact",
            ]
        )

        return "; ".join(suggestions)

    def _detect_inefficient_list_ops_enhanced(
        self,
        content: str,
        tree: ast.AST,
    ) -> list[dict[str, t.Any]]:
        """Detect inefficient list operations in loops.

        Args:
            content: File content
            tree: AST tree

        Returns:
            List of inefficient list operation issues
        """
        analyzer = self._create_enhanced_list_op_analyzer()
        analyzer.visit(tree)

        if not analyzer.list_ops:
            return []

        return self._build_list_ops_issues(analyzer)

    @staticmethod
    def _create_enhanced_list_op_analyzer() -> "ListOpAnalyzer":
        """Create AST analyzer for list operations.

        Returns:
            ListOpAnalyzer instance
        """
        return ListOpAnalyzer()

    def _build_list_ops_issues(
        self, analyzer: "ListOpAnalyzer"
    ) -> list[dict[str, t.Any]]:
        """Build issue data from list operation analysis.

        Args:
            analyzer: ListOpAnalyzer instance

        Returns:
            List of issues
        """
        total_impact = sum(int(op["impact_factor"]) for op in analyzer.list_ops)
        high_impact_ops = [
            op for op in analyzer.list_ops if int(op["impact_factor"]) >= 10
        ]

        return [
            {
                "type": "inefficient_list_operations_enhanced",
                "instances": analyzer.list_ops,
                "total_impact": total_impact,
                "high_impact_count": len(high_impact_ops),
                "suggestion": self._generate_list_op_suggestions(analyzer.list_ops),
            }
        ]

    @staticmethod
    def _generate_list_op_suggestions(list_ops: list[dict[str, t.Any]]) -> str:
        """Generate optimization suggestions for list operations.

        Args:
            list_ops: List of inefficient operations

        Returns:
            Suggestion string
        """
        suggestions = []

        high_impact_count = len(
            [op for op in list_ops if int(op["impact_factor"]) >= 10]
        )
        if high_impact_count > 0:
            suggestions.append(
                f"HIGH IMPACT: {high_impact_count} list[t.Any] operations in hot loops"
            )

        append_count = len([op for op in list_ops if op["optimization"] == "append"])
        extend_count = len([op for op in list_ops if op["optimization"] == "extend"])

        if append_count > 0:
            suggestions.append(f"Replace {append_count} += [item] with .append(item)")
        if extend_count > 0:
            suggestions.append(
                f"Replace {extend_count} += multiple_items with .extend()"
            )

        suggestions.append(
            "Expected performance gains: 2-50x depending on loop context"
        )

        return "; ".join(suggestions)

    def _detect_repeated_operations_enhanced(
        self,
        content: str,
        tree: ast.AST,
    ) -> list[dict[str, t.Any]]:
        """Detect repeated expensive operations in loops.

        Args:
            content: File content
            tree: AST tree

        Returns:
            List of repeated operation issues
        """
        lines = content.split("\n")
        repeated_calls = self._find_expensive_operations_in_loops(lines)

        return self._create_repeated_operations_issues(repeated_calls)

    def _find_expensive_operations_in_loops(
        self,
        lines: list[str],
    ) -> list[dict[str, t.Any]]:
        """Find expensive operations inside loops.

        Args:
            lines: File lines

        Returns:
            List of repeated operation records
        """
        repeated_calls: list[dict[str, t.Any]] = []
        expensive_patterns = self._get_expensive_operation_patterns()

        for i, line in enumerate(lines):
            stripped = line.strip()
            if self._contains_expensive_operation(stripped, expensive_patterns):
                if self._is_in_loop_context(lines, i):
                    repeated_calls.append(self._create_operation_record(i, stripped))

        return repeated_calls

    @staticmethod
    def _get_expensive_operation_patterns() -> tuple[str, ...]:
        """Get patterns for expensive operations.

        Returns:
            Tuple of pattern strings
        """
        return (
            ".exists()",
            ".read_text()",
            ".glob(",
            ".rglob(",
            "Path(",
            "len(",
            ".get(",
        )

    @staticmethod
    def _contains_expensive_operation(
        line: str,
        patterns: tuple[str, ...],
    ) -> bool:
        """Check if line contains expensive operations.

        Args:
            line: Code line
            patterns: Patterns to match

        Returns:
            True if expensive operation found
        """
        return any(pattern in line for pattern in patterns)

    @staticmethod
    def _is_in_loop_context(lines: list[str], line_index: int) -> bool:
        """Check if line is inside a loop.

        Args:
            lines: File lines
            line_index: Index of line to check

        Returns:
            True if inside loop context
        """
        context_start = max(0, line_index - 5)
        context_lines = lines[context_start : line_index + 1]

        loop_keywords = ("for ", "while ")
        return any(
            any(keyword in ctx_line for keyword in loop_keywords)
            for ctx_line in context_lines
        )

    @staticmethod
    def _create_operation_record(
        line_index: int,
        content: str,
    ) -> dict[str, t.Any]:
        """Create record for operation.

        Args:
            line_index: Line number
            content: Line content

        Returns:
            Operation record
        """
        return {
            "line_number": line_index + 1,
            "content": content,
            "type": "expensive_operation_in_loop",
        }

    @staticmethod
    def _create_repeated_operations_issues(
        repeated_calls: list[dict[str, t.Any]],
    ) -> list[dict[str, t.Any]]:
        """Create issues from repeated operations.

        Args:
            repeated_calls: List of repeated operation records

        Returns:
            List of issues
        """
        if len(repeated_calls) >= 2:
            return [
                {
                    "type": "repeated_expensive_operations",
                    "instances": repeated_calls,
                    "suggestion": "Cache expensive operations outside loops",
                },
            ]
        return []

    def _detect_string_inefficiencies_enhanced(
        self, content: str
    ) -> list[dict[str, t.Any]]:
        """Detect string building inefficiencies.

        Args:
            content: File content

        Returns:
            List of string inefficiency issues
        """
        issues: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        string_concat_patterns = []
        inefficient_joins = []
        repeated_format_calls = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            if "+=" in stripped and any(quote in stripped for quote in ('"', "'")):
                if self._is_in_loop_context_enhanced(lines, i):
                    context_info = self._analyze_string_context(lines, i)
                    string_concat_patterns.append(
                        {
                            "line_number": i + 1,
                            "content": stripped,
                            "context": context_info,
                            "estimated_impact": int(
                                context_info.get("impact_factor", "1")
                            ),
                        }
                    )

            if ".join([])" in stripped:
                inefficient_joins.append(
                    {
                        "line_number": i + 1,
                        "content": stripped,
                        "optimization": "Use empty string literal instead",
                        "performance_gain": "2x",
                    }
                )

            if any(pattern in stripped for pattern in ('f"', ".format(", "% ")):
                if self._is_in_loop_context_enhanced(lines, i):
                    repeated_format_calls.append(
                        {
                            "line_number": i + 1,
                            "content": stripped,
                            "optimization": "Move formatting outside loop if static",
                        }
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
                    "suggestion": self._generate_string_suggestions(
                        string_concat_patterns, inefficient_joins, repeated_format_calls
                    ),
                }
            )

        return issues

    def _analyze_string_context(
        self, lines: list[str], line_idx: int
    ) -> dict[str, t.Any]:
        """Analyze string building context.

        Args:
            lines: File lines
            line_idx: Line index

        Returns:
            Context information
        """
        context = self._create_default_string_context()
        loop_context = self._find_loop_context_in_lines(lines, line_idx)

        if loop_context:
            context.update(loop_context)

        return context

    @staticmethod
    def _create_default_string_context() -> dict[str, t.Any]:
        """Create default string context.

        Returns:
            Default context dict
        """
        return {
            "loop_type": "unknown",
            "loop_depth": 1,
            "impact_factor": "1",
        }

    def _find_loop_context_in_lines(
        self, lines: list[str], line_idx: int
    ) -> dict[str, t.Any] | None:
        """Find loop context for a line.

        Args:
            lines: File lines
            line_idx: Line index

        Returns:
            Loop context or None
        """
        for i in range(max(0, line_idx - 10), line_idx):
            line = lines[i].strip()
            loop_context = self._analyze_single_line_for_loop_context(line)
            if loop_context:
                return loop_context
        return None

    def _analyze_single_line_for_loop_context(
        self, line: str
    ) -> dict[str, t.Any] | None:
        """Analyze a single line for loop context.

        Args:
            line: Code line

        Returns:
            Loop context or None
        """
        if "for " in line and " in " in line:
            return self._analyze_for_loop_context(line)
        elif "while " in line:
            return self._analyze_while_loop_context()
        return None

    def _analyze_for_loop_context(self, line: str) -> dict[str, t.Any]:
        """Analyze for loop for impact factor.

        Args:
            line: For loop line

        Returns:
            Context dict
        """
        context = {"loop_type": "for"}

        if "range(" in line:
            impact_factor = self._estimate_range_impact_factor(line)
            context["impact_factor"] = str(impact_factor)
        else:
            context["impact_factor"] = "2"

        return context

    @staticmethod
    def _analyze_while_loop_context() -> dict[str, t.Any]:
        """Analyze while loop context.

        Returns:
            Context dict
        """
        return {
            "loop_type": "while",
            "impact_factor": "3",
        }

    def _estimate_range_impact_factor(self, line: str) -> int:
        """Estimate impact factor for range size.

        Args:
            line: Code line

        Returns:
            Impact factor
        """
        try:
            pattern_obj = SAFE_PATTERNS["extract_range_size"]
            if not pattern_obj.test(line):
                return 2

            range_str = pattern_obj.apply(line)
            range_size = self._extract_range_size_from_string(range_str)

            return self._calculate_impact_from_range_size(range_size)
        except (ValueError, AttributeError):
            return 2

    @staticmethod
    def _extract_range_size_from_string(range_str: str) -> int:
        """Extract range size from string.

        Args:
            range_str: Range string

        Returns:
            Range size
        """
        import re

        number_match = re.search(r"\d+", range_str)
        if number_match:
            return int(number_match.group())
        return 0

    @staticmethod
    def _calculate_impact_from_range_size(range_size: int) -> int:
        """Calculate impact factor from range size.

        Args:
            range_size: Size of range

        Returns:
            Impact factor
        """
        if range_size > 1000:
            return 10
        elif range_size > 100:
            return 5
        return 2

    @staticmethod
    def _is_in_loop_context_enhanced(lines: list[str], line_index: int) -> bool:
        """Check if line is in enhanced loop context.

        Args:
            lines: File lines
            line_index: Line index

        Returns:
            True if in loop
        """
        context_start = max(0, line_index - 8)
        context_lines = lines[context_start : line_index + 1]

        for ctx_line in context_lines:
            pattern_obj = SAFE_PATTERNS["match_loop_patterns"]
            if pattern_obj.test(ctx_line):
                return True

        return False

    @staticmethod
    def _generate_string_suggestions(
        concat_patterns: list[dict[str, t.Any]],
        inefficient_joins: list[dict[str, t.Any]],
        repeated_formatting: list[dict[str, t.Any]],
    ) -> str:
        """Generate string optimization suggestions.

        Args:
            concat_patterns: String concatenation patterns
            inefficient_joins: Inefficient join patterns
            repeated_formatting: Repeated formatting patterns

        Returns:
            Suggestion string
        """
        suggestions = []

        if concat_patterns:
            high_impact = len(
                [p for p in concat_patterns if p.get("estimated_impact", 1) >= 5]
            )
            suggestions.append(
                f"String concatenation: {len(concat_patterns)} instances "
                f"({high_impact} high-impact) - use list[t.Any].append + join"
            )

        if inefficient_joins:
            suggestions.append(
                f"Empty joins: {len(inefficient_joins)} - use empty string literal"
            )

        if repeated_formatting:
            suggestions.append(
                f"Repeated formatting: {len(repeated_formatting)} - cache format strings"
            )

        suggestions.append("Expected gains: 3-50x for string building in loops")
        return "; ".join(suggestions)

    def _detect_list_comprehension_opportunities(
        self, tree: ast.AST
    ) -> list[dict[str, t.Any]]:
        """Detect opportunities to use list comprehensions.

        Args:
            tree: AST tree

        Returns:
            List of comprehension opportunities
        """
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
                        }
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
                }
            )

        return issues

    def _detect_inefficient_builtin_usage(
        self, tree: ast.AST, content: str
    ) -> list[dict[str, t.Any]]:
        """Detect inefficient builtin function usage in loops.

        Args:
            tree: AST tree
            content: File content

        Returns:
            List of inefficient builtin issues
        """
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

                    if func_name in ("len", "sum", "max", "min", "sorted"):
                        if node.args and isinstance(node.args[0], ast.Name):
                            self.inefficient_calls.append(
                                {
                                    "line_number": node.lineno,
                                    "function": func_name,
                                    "type": "repeated_builtin_in_loop",
                                    "optimization": f"Cache {func_name}() "
                                    f"result outside loop",
                                    "performance_gain": "2-10x depending on data size",
                                }
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
                }
            )

        return issues


class NestedLoopAnalyzer(ast.NodeVisitor):
    """AST visitor for detecting nested loops."""

    def __init__(self) -> None:
        """Initialize analyzer."""
        self.nested_loops: list[dict[str, t.Any]] = []
        self.complexity_hotspots: list[dict[str, t.Any]] = []
        self._loop_stack: list[tuple[int, str]] = []

    def visit_For(self, node: ast.For) -> None:
        """Visit for loop node."""
        self._handle_loop_node(node, "for")
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        """Visit while loop node."""
        self._handle_loop_node(node, "while")
        self.generic_visit(node)

    def _handle_loop_node(self, node: ast.For | ast.While, loop_type: str) -> None:
        """Handle loop node detection."""
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
                }
            )

        self._loop_stack.pop()

    @staticmethod
    def _calculate_loop_complexity(depth: int) -> str:
        """Calculate complexity string from depth."""
        if depth == 2:
            return "O(n²)"
        elif depth == 3:
            return "O(n³)"
        elif depth >= 4:
            return "O(n⁴+)"
        return "O(n)"

    @staticmethod
    def _determine_priority(depth: int) -> str:
        """Determine priority from depth."""
        if depth >= 4:
            return "critical"
        elif depth == 3:
            return "high"
        return "medium"


class ListOpAnalyzer(ast.NodeVisitor):
    """AST visitor for detecting inefficient list operations."""

    def __init__(self) -> None:
        """Initialize analyzer."""
        self.list_ops: list[dict[str, t.Any]] = []
        self._in_loop = False

    def visit_For(self, node: ast.For) -> None:
        """Visit for loop."""
        old_in_loop = self._in_loop
        self._in_loop = True
        self.generic_visit(node)
        self._in_loop = old_in_loop

    def visit_While(self, node: ast.While) -> None:
        """Visit while loop."""
        old_in_loop = self._in_loop
        self._in_loop = True
        self.generic_visit(node)
        self._in_loop = old_in_loop

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Visit augmented assignment."""
        if self._in_loop and isinstance(node.op, operator.Add):
            if isinstance(node.value, ast.List):
                impact = len(node.value.elts) if node.value.elts else 1
                self.list_ops.append(
                    {
                        "line_number": node.lineno,
                        "type": "inefficient_list_concat",
                        "optimization": "append"
                        if len(node.value.elts) == 1
                        else "extend",
                        "impact_factor": impact,
                        "performance_gain": f"{max(2, min(50, impact * 5))}x",
                    }
                )

        self.generic_visit(node)

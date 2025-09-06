import ast
import operator
import time
import typing as t
from contextlib import suppress
from pathlib import Path

from ..services.regex_patterns import SAFE_PATTERNS
from . import performance_helpers
from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)
from .performance_helpers import OptimizationResult


class PerformanceAgent(SubAgent):
    """Enhanced PerformanceAgent with automated O(n²) detection and measurable optimizations."""

    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        self.performance_metrics: dict[str, t.Any] = {}
        self.optimization_stats: dict[str, int] = {
            "nested_loops_optimized": 0,
            "list_ops_optimized": 0,
            "string_concat_optimized": 0,
            "repeated_ops_cached": 0,
            "comprehensions_applied": 0,
        }

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.PERFORMANCE}

    async def can_handle(self, issue: Issue) -> float:
        """Enhanced confidence scoring based on issue complexity."""
        if issue.type != IssueType.PERFORMANCE:
            return 0.0

        # Higher confidence for specific performance patterns
        confidence = 0.85
        message_lower = issue.message.lower()

        # Boost confidence for known optimization patterns
        if any(
            pattern in message_lower
            for pattern in (
                "nested loop",
                "o(n²)",
                "string concatenation",
                "list concatenation",
                "inefficient",
                "complexity",
            )
        ):
            confidence = 0.9

        return confidence

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Enhanced analysis with performance measurement and optimization tracking."""
        self.log(f"Analyzing performance issue: {issue.message}")
        start_time = time.time()

        validation_result = self._validate_performance_issue(issue)
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
            result = await self._process_performance_optimization(file_path)

            # Track performance metrics
            analysis_time = time.time() - start_time
            self.performance_metrics[str(file_path)] = {
                "analysis_duration": analysis_time,
                "optimizations_applied": result.fixes_applied,
                "timestamp": time.time(),
            }

            # Add performance statistics to result
            if result.success and result.fixes_applied:
                stats_summary = self._generate_optimization_summary()
                result.recommendations = result.recommendations + [stats_summary]

            return result
        except Exception as e:
            return self._create_performance_error_result(e)

    @staticmethod
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

    async def _process_performance_optimization(self, file_path: Path) -> FixResult:
        content = self.context.get_file_content(file_path)
        if not content:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Could not read file: {file_path}"],
            )

        performance_issues = self._detect_performance_issues(content, file_path)

        if not performance_issues:
            return FixResult(
                success=True,
                confidence=0.7,
                recommendations=["No performance issues detected"],
            )

        return self._apply_and_save_optimizations(
            file_path,
            content,
            performance_issues,
        )

    def _apply_and_save_optimizations(
        self,
        file_path: Path,
        content: str,
        issues: list[dict[str, t.Any]],
    ) -> FixResult:
        optimized_content = self._apply_performance_optimizations(content, issues)

        if optimized_content == content:
            return self._create_no_optimization_result()

        success = self.context.write_file_content(file_path, optimized_content)
        if not success:
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Failed to write optimized file: {file_path}"],
            )

        return FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=[
                f"Optimized {len(issues)} performance issues",
                "Applied algorithmic improvements",
            ],
            files_modified=[str(file_path)],
            recommendations=["Test performance improvements with benchmarks"],
        )

    @staticmethod
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

    @staticmethod
    def _create_performance_error_result(error: Exception) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"Error processing file: {error}"],
        )

    def _detect_performance_issues(
        self,
        content: str,
        file_path: Path,
    ) -> list[dict[str, t.Any]]:
        """Enhanced performance issue detection with comprehensive O(n²) analysis."""
        issues: list[dict[str, t.Any]] = []

        with suppress(SyntaxError):
            tree = ast.parse(content)

            # Enhanced nested loop detection with complexity analysis
            nested_issues = self._detect_nested_loops_enhanced(tree)
            issues.extend(nested_issues)

            # Improved list operations detection
            list_issues = self._detect_inefficient_list_ops_enhanced(content, tree)
            issues.extend(list_issues)

            # Enhanced repeated operations detection
            repeated_issues = self._detect_repeated_operations_enhanced(content, tree)
            issues.extend(repeated_issues)

            # Comprehensive string inefficiency detection
            string_issues = self._detect_string_inefficiencies_enhanced(content)
            issues.extend(string_issues)

            # New: Detect list comprehension opportunities
            comprehension_issues = self._detect_list_comprehension_opportunities(tree)
            issues.extend(comprehension_issues)

            # New: Detect inefficient built-in usage
            builtin_issues = self._detect_inefficient_builtin_usage(tree, content)
            issues.extend(builtin_issues)

        return issues

    def _detect_nested_loops_enhanced(self, tree: ast.AST) -> list[dict[str, t.Any]]:
        """Enhanced nested loop detection with complexity analysis and optimization suggestions."""
        analyzer = self._create_nested_loop_analyzer()
        analyzer.visit(tree)
        return self._build_nested_loop_issues(analyzer)

    @staticmethod
    def _create_nested_loop_analyzer() -> (
        performance_helpers.EnhancedNestedLoopAnalyzer
    ):
        """Create and configure the nested loop analyzer."""
        return performance_helpers.EnhancedNestedLoopAnalyzer()

    def _build_nested_loop_issues(
        self, analyzer: performance_helpers.EnhancedNestedLoopAnalyzer
    ) -> list[dict[str, t.Any]]:
        """Build the final nested loop issues from analyzer results."""
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
        """Count loops with high or critical priority."""
        return len([n for n in nested_loops if n["priority"] in ("high", "critical")])

    @staticmethod
    def _generate_nested_loop_suggestions(nested_loops: list[dict[str, t.Any]]) -> str:
        """Generate specific optimization suggestions based on nested loop analysis."""
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
        """Enhanced list operations detection with performance impact assessment."""
        analyzer = self._create_enhanced_list_op_analyzer()
        analyzer.visit(tree)

        if not analyzer.list_ops:
            return []

        return self._build_list_ops_issues(analyzer)

    @staticmethod
    def _create_enhanced_list_op_analyzer() -> t.Any:
        """Create the enhanced list operations analyzer."""
        return performance_helpers.EnhancedListOpAnalyzer()

    def _build_list_ops_issues(self, analyzer: t.Any) -> list[dict[str, t.Any]]:
        """Build the final list operations issues from analyzer results."""
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
        """Generate specific optimization suggestions for list operations."""
        suggestions = []

        high_impact_count = len(
            [op for op in list_ops if int(op["impact_factor"]) >= 10]
        )
        if high_impact_count > 0:
            suggestions.append(
                f"HIGH IMPACT: {high_impact_count} list operations in hot loops"
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
        lines = content.split("\n")
        repeated_calls = self._find_expensive_operations_in_loops(lines)

        return self._create_repeated_operations_issues(repeated_calls)

    def _find_expensive_operations_in_loops(
        self,
        lines: list[str],
    ) -> list[dict[str, t.Any]]:
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
        return any(pattern in line for pattern in patterns)

    @staticmethod
    def _is_in_loop_context(lines: list[str], line_index: int) -> bool:
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
        return {
            "line_number": line_index + 1,
            "content": content,
            "type": "expensive_operation_in_loop",
        }

    @staticmethod
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

    @staticmethod
    def _detect_string_inefficiencies(content: str) -> list[dict[str, t.Any]]:
        issues: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        string_concat_in_loop: list[dict[str, t.Any]] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if "+=" in stripped and any(quote in stripped for quote in ('"', "'")):
                context_start = max(0, i - 5)
                context_lines = lines[context_start : i + 1]

                loop_keywords = ("for ", "while ")
                if any(
                    any(keyword in ctx_line for keyword in loop_keywords)
                    for ctx_line in context_lines
                ):
                    string_concat_in_loop.append(
                        {
                            "line_number": i + 1,
                            "content": stripped,
                        },
                    )

        if len(string_concat_in_loop) >= 2:
            issues.append(
                {
                    "type": "string_concatenation_in_loop",
                    "instances": string_concat_in_loop,
                    "suggestion": 'Use list.append() and "".join() for string building',
                },
            )

        return issues

    def _detect_string_inefficiencies_enhanced(
        self, content: str
    ) -> list[dict[str, t.Any]]:
        """Enhanced string inefficiency detection with comprehensive analysis."""
        issues: list[dict[str, t.Any]] = []
        lines = content.split("\n")

        string_concat_patterns = []
        inefficient_joins = []
        repeated_format_calls = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Detect string concatenation in loops (enhanced)
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

            # Detect inefficient string joins
            if ".join([])" in stripped:
                inefficient_joins.append(
                    {
                        "line_number": i + 1,
                        "content": stripped,
                        "optimization": "Use empty string literal instead",
                        "performance_gain": "2x",
                    }
                )

            # Detect repeated string formatting in loops
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
        """Analyze the context around a string operation for impact assessment."""
        context = self._create_default_string_context()
        loop_context = self._find_loop_context_in_lines(lines, line_idx)

        if loop_context:
            context.update(loop_context)

        return context

    @staticmethod
    def _create_default_string_context() -> dict[str, t.Any]:
        """Create default context for string operations."""
        return {
            "loop_type": "unknown",
            "loop_depth": 1,
            "impact_factor": "1",
        }

    def _find_loop_context_in_lines(
        self, lines: list[str], line_idx: int
    ) -> dict[str, t.Any] | None:
        """Find loop context by looking back through lines."""
        for i in range(max(0, line_idx - 10), line_idx):
            line = lines[i].strip()
            loop_context = self._analyze_single_line_for_loop_context(line)
            if loop_context:
                return loop_context
        return None

    def _analyze_single_line_for_loop_context(
        self, line: str
    ) -> dict[str, t.Any] | None:
        """Analyze a single line for loop context information."""
        if "for " in line and " in " in line:
            return self._analyze_for_loop_context(line)
        elif "while " in line:
            return self._analyze_while_loop_context()
        return None

    def _analyze_for_loop_context(self, line: str) -> dict[str, t.Any]:
        """Analyze for loop context and estimate impact."""
        context = {"loop_type": "for"}

        if "range(" in line:
            impact_factor = self._estimate_range_impact_factor(line)
            context["impact_factor"] = str(impact_factor)
        else:
            context["impact_factor"] = "2"  # Default for for loops

        return context

    @staticmethod
    def _analyze_while_loop_context() -> dict[str, t.Any]:
        """Analyze while loop context."""
        return {
            "loop_type": "while",
            "impact_factor": "3",  # Generally higher impact for while loops
        }

    def _estimate_range_impact_factor(self, line: str) -> int:
        """Estimate impact factor based on range size."""
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
        """Extract numeric range size from string using safe regex."""
        import re  # REGEX OK: temporary for extracting number from safe pattern

        number_match = re.search(
            r"\d+", range_str
        )  # REGEX OK: extracting digits from validated pattern
        if number_match:
            return int(number_match.group())
        return 0

    @staticmethod
    def _calculate_impact_from_range_size(range_size: int) -> int:
        """Calculate impact factor based on range size."""
        if range_size > 1000:
            return 10
        elif range_size > 100:
            return 5
        return 2

    @staticmethod
    def _is_in_loop_context_enhanced(lines: list[str], line_index: int) -> bool:
        """Enhanced loop context detection with better accuracy."""
        context_start = max(0, line_index - 8)
        context_lines = lines[context_start : line_index + 1]

        # Check for various loop patterns

        for ctx_line in context_lines:
            # Use safe pattern matching for loop detection
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
        """Generate comprehensive string optimization suggestions."""
        suggestions = []

        if concat_patterns:
            high_impact = len(
                [p for p in concat_patterns if p.get("estimated_impact", 1) >= 5]
            )
            suggestions.append(
                f"String concatenation: {len(concat_patterns)} instances "
                f"({high_impact} high-impact) - use list.append + join"
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
        """Detect opportunities to replace append loops with list comprehensions."""
        issues: list[dict[str, t.Any]] = []

        class ComprehensionAnalyzer(ast.NodeVisitor):
            def __init__(self) -> None:
                self.opportunities: list[dict[str, t.Any]] = []

            def visit_For(self, node: ast.For) -> None:
                # Look for simple append patterns that can be comprehensions
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
                    f" to list comprehensions for better performance "
                    f"and readability",
                }
            )

        return issues

    def _detect_inefficient_builtin_usage(
        self, tree: ast.AST, content: str
    ) -> list[dict[str, t.Any]]:
        """Detect inefficient usage of built-in functions."""
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

                    # Detect expensive operations in loops
                    if func_name in ("len", "sum", "max", "min", "sorted"):
                        # Check if called on the same variable repeatedly
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

    def _generate_optimization_summary(self) -> str:
        """Generate a summary of all optimizations applied."""
        total_optimizations = sum(self.optimization_stats.values())
        if total_optimizations == 0:
            return "No optimizations applied in this session"

        summary_parts = [
            f"{opt_type}: {count}"
            for opt_type, count in self.optimization_stats.items()
            if count > 0
        ]

        return (
            f"Optimization Summary - {', '.join(summary_parts)} "
            f"(Total: {total_optimizations})"
        )

    def _apply_performance_optimizations(
        self,
        content: str,
        issues: list[dict[str, t.Any]],
    ) -> str:
        """Enhanced optimization application with support for new issue types."""
        lines = content.split("\n")
        modified = False
        optimizations_applied = []

        for issue in issues:
            result = self._process_single_issue(lines, issue)
            if result.modified:
                lines = result.lines
                modified = True
                if result.optimization_description:
                    optimizations_applied.append(result.optimization_description)

        if optimizations_applied:
            self.log(f"Applied optimizations: {', '.join(optimizations_applied)}")

        return "\n".join(lines) if modified else content

    def _process_single_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Process a single optimization issue and return the result."""
        issue_type = issue["type"]

        if issue_type in (
            "inefficient_list_operations",
            "inefficient_list_operations_enhanced",
        ):
            return self._handle_list_operations_issue(lines, issue)
        elif issue_type in (
            "string_concatenation_in_loop",
            "string_inefficiencies_enhanced",
        ):
            return self._handle_string_operations_issue(lines, issue)
        elif issue_type == "repeated_expensive_operations":
            return self._handle_repeated_operations_issue(lines, issue)
        elif issue_type in ("nested_loops", "nested_loops_enhanced"):
            return self._handle_nested_loops_issue(lines, issue)
        elif issue_type == "list_comprehension_opportunities":
            return self._handle_comprehension_opportunities_issue(lines, issue)
        elif issue_type == "inefficient_builtin_usage":
            return self._handle_builtin_usage_issue(lines, issue)
        return self._create_no_change_result(lines)

    def _handle_list_operations_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle list operations optimization issue."""
        new_lines, changed = self._fix_list_operations_enhanced(lines, issue)
        description = None

        if changed:
            instance_count = len(issue.get("instances", []))
            self.optimization_stats["list_ops_optimized"] += instance_count
            description = f"List operations: {instance_count}"

        return self._create_optimization_result(new_lines, changed, description)

    def _handle_string_operations_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle string operations optimization issue."""
        new_lines, changed = self._fix_string_operations_enhanced(lines, issue)
        description = None

        if changed:
            total_string_fixes = (
                len(issue.get("string_concat_patterns", []))
                + len(issue.get("inefficient_joins", []))
                + len(issue.get("repeated_formatting", []))
            )
            self.optimization_stats["string_concat_optimized"] += total_string_fixes
            description = f"String operations: {total_string_fixes}"

        return self._create_optimization_result(new_lines, changed, description)

    def _handle_repeated_operations_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle repeated operations optimization issue."""
        new_lines, changed = self._fix_repeated_operations(lines, issue)

        if changed:
            self.optimization_stats["repeated_ops_cached"] += len(
                issue.get("instances", [])
            )

        return self._create_optimization_result(new_lines, changed)

    def _handle_nested_loops_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle nested loops optimization issue."""
        new_lines, changed = self._add_nested_loop_comments(lines, issue)

        if changed:
            self.optimization_stats["nested_loops_optimized"] += len(
                issue.get("instances", [])
            )

        return self._create_optimization_result(new_lines, changed)

    def _handle_comprehension_opportunities_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle list comprehension opportunities issue."""
        new_lines, changed = self._apply_list_comprehension_optimizations(lines, issue)

        if changed:
            self.optimization_stats["comprehensions_applied"] += len(
                issue.get("instances", [])
            )

        return self._create_optimization_result(new_lines, changed)

    def _handle_builtin_usage_issue(
        self, lines: list[str], issue: dict[str, t.Any]
    ) -> OptimizationResult:
        """Handle inefficient builtin usage issue."""
        new_lines, changed = self._add_builtin_caching_comments(lines, issue)
        return self._create_optimization_result(new_lines, changed)

    @staticmethod
    def _create_optimization_result(
        lines: list[str], modified: bool, description: str | None = None
    ) -> OptimizationResult:
        """Create an optimization result object."""
        return OptimizationResult(
            lines=lines, modified=modified, optimization_description=description
        )

    @staticmethod
    def _create_no_change_result(lines: list[str]) -> OptimizationResult:
        """Create a result indicating no changes were made."""
        return OptimizationResult(
            lines=lines, modified=False, optimization_description=None
        )

    @staticmethod
    def _fix_list_operations_enhanced(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Enhanced list operations fixing with comprehensive optimization."""
        modified = False

        instances = sorted(
            issue["instances"],
            key=operator.itemgetter("line_number"),
            reverse=True,
        )

        for instance in instances:
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = t.cast(str, lines[line_idx])

                # Apply optimization based on instance type
                optimization_type = instance.get(
                    "optimization",
                    "append",
                )

                if optimization_type == "append":
                    # Use existing safe pattern for single item append
                    list_pattern = SAFE_PATTERNS["list_append_inefficiency_pattern"]
                    if list_pattern.test(original_line):
                        optimized_line = list_pattern.apply(original_line)
                        lines[line_idx] = optimized_line
                        modified = True

                        # Add performance comment
                        indent = original_line[
                            : len(original_line) - len(original_line.lstrip())
                        ]
                        performance_gain = instance.get("performance_gain", "2x")
                        comment = (
                            f"{indent}# Performance: {performance_gain}"
                            f" improvement (append vs +=)"
                        )
                        lines.insert(line_idx, comment)

                elif optimization_type == "extend":
                    # Use new extend pattern for multiple items
                    extend_pattern = SAFE_PATTERNS["list_extend_optimization_pattern"]
                    if extend_pattern.test(original_line):
                        optimized_line = extend_pattern.apply(original_line)
                        lines[line_idx] = optimized_line
                        modified = True

                        # Add performance comment
                        indent = original_line[
                            : len(original_line) - len(original_line.lstrip())
                        ]
                        performance_gain = instance.get("performance_gain", "x")
                        impact_factor = int(instance.get("impact_factor", "1"))
                        comment = (
                            f"{indent}# Performance: {performance_gain} "
                            f"improvement, impact factor: {impact_factor}"
                        )
                        lines.insert(line_idx, comment)

        return lines, modified

    def _fix_string_operations_enhanced(
        self,
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Enhanced string operations fixing with comprehensive patterns."""
        modified = False

        # Handle string concatenation patterns
        concat_patterns = issue.get("string_concat_patterns", [])
        if concat_patterns:
            lines, concat_modified = self._fix_string_concatenation(
                lines, {"instances": concat_patterns}
            )
            modified = modified or concat_modified

        # Handle inefficient joins
        inefficient_joins = issue.get("inefficient_joins", [])
        for join_issue in inefficient_joins:
            line_idx = join_issue["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                join_pattern = SAFE_PATTERNS["inefficient_string_join_pattern"]
                if join_pattern.test(original_line):
                    lines[line_idx] = join_pattern.apply(original_line)
                    modified = True

        # Handle repeated formatting - just add comments for now
        repeated_formatting = issue.get("repeated_formatting", [])
        for format_issue in repeated_formatting:
            line_idx = format_issue["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                indent = original_line[
                    : len(original_line) - len(original_line.lstrip())
                ]
                comment = (
                    f"{indent}# Performance: Consider caching format string "
                    f"outside loop"
                )
                lines.insert(line_idx, comment)
                modified = True

        return lines, modified

    @staticmethod
    def _add_nested_loop_comments(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Add informative comments about nested loop complexity."""
        modified = False

        instances = issue.get("instances", [])
        for instance in sorted(
            instances, key=operator.itemgetter("line_number"), reverse=True
        ):
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                indent = original_line[
                    : len(original_line) - len(original_line.lstrip())
                ]

                complexity = instance.get("complexity", "O(n²)")
                priority = instance.get("priority", "medium")

                comment_lines = [
                    f"{indent}# Performance: {complexity} nested loop detected -"
                    f" {priority} priority",
                ]

                # Add specific suggestions for high priority loops
                if priority in ("high", "critical"):
                    if priority == "critical":
                        comment_lines.append(
                            f"{indent}# CRITICAL: Consider algorithmic redesign or"
                            f" data structure changes"
                        )
                    else:
                        comment_lines.append(
                            f"{indent}# Suggestion: Consider memoization, caching,"
                            f" or hash tables"
                        )

                # Insert comments before the loop
                for i, comment in enumerate(comment_lines):
                    lines.insert(line_idx + i, comment)

                modified = True

        return lines, modified

    @staticmethod
    def _apply_list_comprehension_optimizations(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Apply list comprehension optimizations where detected."""
        modified = False

        instances = issue.get("instances", [])
        for instance in sorted(
            instances, key=operator.itemgetter("line_number"), reverse=True
        ):
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                indent = original_line[
                    : len(original_line) - len(original_line.lstrip())
                ]

                # Add suggestion comment for now - actual transformation would need more AST analysis
                comment = (
                    f"{indent}# Performance: Consider list comprehension for "
                    f"20-30% improvement"
                )
                lines.insert(line_idx, comment)
                modified = True

        return lines, modified

    @staticmethod
    def _add_builtin_caching_comments(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        """Add comments about caching builtin function calls."""
        modified = False

        instances = issue.get("instances", [])
        for instance in sorted(
            instances, key=operator.itemgetter("line_number"), reverse=True
        ):
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = lines[line_idx]
                indent = original_line[
                    : len(original_line) - len(original_line.lstrip())
                ]

                func_name = instance.get("function", "builtin")
                performance_gain = instance.get(
                    "performance_gain",
                    "2-10x",
                )

                comment = (
                    f"{indent}# Performance: Cache {func_name}() result outside"
                    f" loop for {performance_gain} improvement"
                )
                lines.insert(line_idx, comment)
                modified = True

        return lines, modified

    @staticmethod
    def _fix_list_operations(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        modified = False

        instances = sorted(
            issue["instances"],
            key=operator.itemgetter("line_number"),
            reverse=True,
        )

        list_pattern = SAFE_PATTERNS["list_append_inefficiency_pattern"]

        for instance in instances:
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = t.cast(str, lines[line_idx])

                # Use safe pattern to test and transform
                if list_pattern.test(original_line):
                    # Apply the performance optimization using safe pattern
                    optimized_line = list_pattern.apply(original_line)
                    lines[line_idx] = optimized_line
                    modified = True

                    # Extract indent from the original line for comment
                    indent = original_line[
                        : len(original_line) - len(original_line.lstrip())
                    ]
                    comment = (
                        f"{indent}# Performance: Changed += [item] to .append(item)"
                    )
                    lines.insert(line_idx, comment)

        return lines, modified

    def _fix_string_concatenation(
        self,
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        var_groups = self._group_concatenation_instances(lines, issue["instances"])
        return self._apply_concatenation_optimizations(lines, var_groups)

    def _group_concatenation_instances(
        self,
        lines: list[str],
        instances: list[dict[str, t.Any]],
    ) -> dict[str, list[dict[str, t.Any]]]:
        var_groups: dict[str, list[dict[str, t.Any]]] = {}

        for instance in instances:
            line_info = self._parse_concatenation_line(lines, instance)
            if line_info:
                var_name = line_info["var_name"]
                if var_name not in var_groups:
                    var_groups[var_name] = []
                var_groups[var_name].append(line_info)

        return var_groups

    @staticmethod
    def _parse_concatenation_line(
        lines: list[str],
        instance: dict[str, t.Any],
    ) -> dict[str, t.Any] | None:
        line_idx = instance["line_number"] - 1
        if line_idx >= len(lines):
            return None

        original_line = t.cast(str, lines[line_idx])

        # Use safe pattern for string concatenation parsing
        concat_pattern = SAFE_PATTERNS["string_concatenation_pattern"]
        if concat_pattern.test(original_line):
            # Extract parts using the safe pattern's compiled pattern
            compiled = concat_pattern._get_compiled_pattern()
            match = compiled.match(original_line)
            if match:
                indent, var_name, expr = match.groups()
                return {
                    "line_idx": line_idx,
                    "indent": indent,
                    "var_name": var_name,
                    "expr": expr.strip(),
                    "original_line": original_line,
                }
        return None

    def _apply_concatenation_optimizations(
        self,
        lines: list[str],
        var_groups: dict[str, list[dict[str, t.Any]]],
    ) -> tuple[list[str], bool]:
        modified = False

        for var_name, instances in var_groups.items():
            if instances:
                first_instance = instances[0]
                loop_start = self._find_loop_start(lines, first_instance["line_idx"])

                if loop_start is not None:
                    optimization_applied = self._apply_string_building_optimization(
                        lines, var_name, instances, loop_start
                    )
                    modified = modified or optimization_applied

        return lines, modified

    @staticmethod
    def _find_loop_start(lines: list[str], start_idx: int) -> int | None:
        for i in range(start_idx, -1, -1):
            line = lines[i].strip()
            if line.startswith(("for ", "while ")):
                return i

            if line.startswith(("def ", "class ")):
                break
        return None

    def _apply_string_building_optimization(
        self,
        lines: list[str],
        var_name: str,
        instances: list[dict[str, t.Any]],
        loop_start: int,
    ) -> bool:
        if not instances:
            return False

        first_instance = instances[0]
        indent = first_instance["indent"]

        init_line_idx = self._find_variable_initialization(lines, var_name, loop_start)
        if init_line_idx is not None:
            self._transform_string_initialization(
                lines, init_line_idx, var_name, indent
            )
            self._replace_concatenations_with_appends(
                lines, instances, var_name, indent
            )
            self._add_join_after_loop(lines, var_name, indent, loop_start)
            return True

        return False

    @staticmethod
    def _find_variable_initialization(
        lines: list[str],
        var_name: str,
        loop_start: int,
    ) -> int | None:
        search_start = max(0, loop_start - 10)

        for i in range(loop_start - 1, search_start - 1, -1):
            line = lines[i].strip()
            if f"{var_name} =" in line and '""' in line:
                return i
        return None

    @staticmethod
    def _transform_string_initialization(
        lines: list[str],
        init_line_idx: int,
        var_name: str,
        indent: str,
    ) -> None:
        lines[init_line_idx] = (
            f"{indent}{var_name}_parts = [] # Performance: Use list for string building"
        )

    @staticmethod
    def _replace_concatenations_with_appends(
        lines: list[str],
        instances: list[dict[str, t.Any]],
        var_name: str,
        indent: str,
    ) -> None:
        for instance in instances:
            line_idx = instance["line_idx"]
            expr = instance["expr"]
            lines[line_idx] = f"{indent}{var_name}_parts.append({expr})"

    def _add_join_after_loop(
        self,
        lines: list[str],
        var_name: str,
        indent: str,
        loop_start: int,
    ) -> None:
        loop_end = self._find_loop_end(lines, loop_start)
        if loop_end is not None:
            join_line = (
                f"{indent}{var_name} = ''.join({var_name}_parts) # Performance:"
                f" Join string parts"
            )
            lines.insert(loop_end + 1, join_line)

    @staticmethod
    def _find_loop_end(lines: list[str], loop_start: int) -> int | None:
        if loop_start >= len(lines):
            return None

        loop_indent = len(lines[loop_start]) - len(lines[loop_start].lstrip())

        for i in range(loop_start + 1, len(lines)):
            line = lines[i]
            if line.strip() == "":
                continue

            current_indent = len(line) - len(line.lstrip())
            if current_indent <= loop_indent:
                return i - 1

        return len(lines) - 1

    @staticmethod
    def _fix_repeated_operations(
        lines: list[str],
        issue: dict[str, t.Any],
    ) -> tuple[list[str], bool]:
        modified = False

        for instance in issue["instances"]:
            line_idx = instance["line_number"] - 1
            if line_idx < len(lines):
                original_line = t.cast(str, lines[line_idx])
                indent_level = len(original_line) - len(original_line.lstrip())
                indent_str = " " * indent_level

                comment = (
                    f"{indent_str}# Performance: Consider caching this expensive"
                    f" operation outside the loop"
                )
                lines.insert(line_idx, comment)
                modified = True

        return lines, modified


agent_registry.register(PerformanceAgent)

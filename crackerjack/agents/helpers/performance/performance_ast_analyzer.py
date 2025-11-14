"""AST analysis for performance complexity detection."""

import ast
import typing as t

from ...base import AgentContext


class PerformanceASTAnalyzer:
    """Analyzes Python AST for performance-related complexity issues."""

    def __init__(self, context: AgentContext) -> None:
        """Initialize analyzer with agent context.

        Args:
            context: AgentContext for logging and operations
        """
        self.context = context

    def extract_performance_critical_functions(
        self, content: str
    ) -> list[dict[str, t.Any]]:
        """Extract functions likely to have performance issues.

        Args:
            content: File content

        Returns:
            List of performance-critical functions
        """
        functions: list[dict[str, t.Any]] = []
        lines = content.split("\n")
        current_function = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            if self._is_empty_or_comment_line(stripped):
                if current_function:
                    current_function["body"] += line + "\n"
                continue

            indent = len(line) - len(line.lstrip())

            if self._is_function_definition(stripped):
                current_function = self._handle_function_definition(
                    current_function, functions, stripped, indent, i
                )
            elif current_function:
                current_function = self._handle_function_body_line(
                    current_function, functions, line, stripped, indent, i
                )

        self._handle_last_function(current_function, functions, len(lines))
        return functions

    @staticmethod
    def _is_empty_or_comment_line(stripped: str) -> bool:
        """Check if line is empty or comment.

        Args:
            stripped: Stripped line

        Returns:
            True if empty or comment
        """
        return not stripped or stripped.startswith("#")

    @staticmethod
    def _is_function_definition(stripped: str) -> bool:
        """Check if line is function definition.

        Args:
            stripped: Stripped line

        Returns:
            True if function definition
        """
        return stripped.startswith("def ") and "(" in stripped

    def _handle_function_definition(
        self,
        current_function: dict[str, t.Any] | None,
        functions: list[dict[str, t.Any]],
        stripped: str,
        indent: int,
        line_number: int,
    ) -> dict[str, t.Any]:
        """Handle function definition line.

        Args:
            current_function: Current function being parsed
            functions: List of functions
            stripped: Stripped line
            indent: Indentation level
            line_number: Line number

        Returns:
            New function dict
        """
        if current_function and self._is_performance_critical(current_function):
            self._finalize_function(current_function, functions, line_number)

        func_name = stripped.split("(")[0].replace("def ", "").strip()
        return {
            "name": func_name,
            "signature": stripped,
            "start_line": line_number + 1,
            "body": "",
            "indent_level": indent,
        }

    def _handle_function_body_line(
        self,
        current_function: dict[str, t.Any],
        functions: list[dict[str, t.Any]],
        line: str,
        stripped: str,
        indent: int,
        line_number: int,
    ) -> dict[str, t.Any] | None:
        """Handle line within function body.

        Args:
            current_function: Current function
            functions: Functions list
            line: Full line
            stripped: Stripped line
            indent: Indent level
            line_number: Line number

        Returns:
            Updated current function or None
        """
        if self._is_still_in_function(current_function, indent, stripped):
            current_function["body"] += line + "\n"
            return current_function
        else:
            if self._is_performance_critical(current_function):
                self._finalize_function(current_function, functions, line_number)
            return None

    @staticmethod
    def _is_still_in_function(
        current_function: dict[str, t.Any], indent: int, stripped: str
    ) -> bool:
        """Check if still inside function.

        Args:
            current_function: Current function
            indent: Indent level
            stripped: Stripped line

        Returns:
            True if still inside
        """
        return indent > current_function["indent_level"] or (
            indent == current_function["indent_level"]
            and stripped.startswith(('"', "'", "@"))
        )

    def _finalize_function(
        self,
        function: dict[str, t.Any],
        functions: list[dict[str, t.Any]],
        end_line: int,
    ) -> None:
        """Finalize function and add to results.

        Args:
            function: Function to finalize
            functions: Functions list
            end_line: End line number
        """
        function["end_line"] = end_line
        function["body_sample"] = function["body"][:300]
        function["estimated_complexity"] = self._estimate_complexity(function["body"])
        functions.append(function)

    def _handle_last_function(
        self,
        current_function: dict[str, t.Any] | None,
        functions: list[dict[str, t.Any]],
        total_lines: int,
    ) -> None:
        """Handle last function in file.

        Args:
            current_function: Last function
            functions: Functions list
            total_lines: Total lines
        """
        if current_function and self._is_performance_critical(current_function):
            self._finalize_function(current_function, functions, total_lines)

    @staticmethod
    def _is_performance_critical(function_info: dict[str, t.Any]) -> bool:
        """Determine if function is performance-critical.

        Args:
            function_info: Function info

        Returns:
            True if performance-critical
        """
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

    @staticmethod
    def _estimate_complexity(body: str) -> int:
        """Estimate computational complexity of function.

        Args:
            body: Function body

        Returns:
            Complexity score
        """
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

    def analyze_performance_patterns(
        self, semantic_insight: t.Any, current_func: dict[str, t.Any]
    ) -> dict[str, t.Any]:
        """Analyze semantic patterns for performance insights.

        Args:
            semantic_insight: Semantic insight from analysis
            current_func: Current function

        Returns:
            Analysis dict
        """
        analysis: dict[str, t.Any] = {
            "issues_found": False,
            "optimization_suggestion": "Consider reviewing similar implementations for consistency",
            "pattern_insights": [],
        }

        if semantic_insight.high_confidence_matches > 0:
            analysis["issues_found"] = True
            analysis["pattern_insights"].append(
                f"Found {semantic_insight.high_confidence_matches} highly similar implementations"
            )

            performance_concerns = []
            for pattern in semantic_insight.related_patterns:
                content = pattern.get("content", "").lower()
                if any(
                    concern in content for concern in ("for", "while", "+=", "append")
                ):
                    performance_concerns.append(pattern["file_path"])

            if performance_concerns:
                analysis["optimization_suggestion"] = (
                    f"Performance review needed: {len(performance_concerns)} similar functions "
                    f"may benefit from the same optimization approach"
                )
                analysis["pattern_insights"].append(
                    f"Similar performance patterns found in: {', '.join(list(set(performance_concerns))[:3])}"
                )

        return analysis

    def analyze_code_metrics(self, tree: ast.AST) -> dict[str, t.Any]:
        """Analyze code metrics from AST.

        Args:
            tree: AST tree

        Returns:
            Metrics dict
        """
        metrics: dict[str, t.Any] = {
            "total_functions": 0,
            "total_classes": 0,
            "average_function_length": 0,
            "max_nesting_depth": 0,
            "high_complexity_functions": [],
        }

        class MetricsCollector(ast.NodeVisitor):
            def __init__(self) -> None:
                self.function_count = 0
                self.class_count = 0
                self.function_lengths: list[int] = []
                self.max_depth = 0

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                self.function_count += 1
                length = (node.end_lineno or node.lineno) - node.lineno
                self.function_lengths.append(length)
                self.generic_visit(node)

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                self.class_count += 1
                self.generic_visit(node)

        collector = MetricsCollector()
        collector.visit(tree)

        metrics["total_functions"] = collector.function_count
        metrics["total_classes"] = collector.class_count

        if collector.function_lengths:
            metrics["average_function_length"] = sum(collector.function_lengths) / len(
                collector.function_lengths
            )

        return metrics

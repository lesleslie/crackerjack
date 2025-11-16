"""Complexity detection and analysis for refactoring."""

import ast
import typing as t

from ...base import AgentContext


class ComplexityAnalyzer:
    """Analyzes code complexity and identifies complex functions."""

    def __init__(self, context: AgentContext) -> None:
        """Initialize analyzer with agent context.

        Args:
            context: AgentContext for logging
        """
        self.context = context

    def find_complex_functions(
        self,
        tree: ast.AST,
        content: str,
    ) -> list[dict[str, t.Any]]:
        """Find functions with complexity > 15.

        Args:
            tree: AST tree
            content: File content

        Returns:
            List of complex functions
        """
        complex_functions: list[dict[str, t.Any]] = []

        class ComplexityVisitor(ast.NodeVisitor):
            def __init__(
                self,
                calc_complexity: t.Callable[
                    [ast.FunctionDef | ast.AsyncFunctionDef], int
                ],
            ) -> None:
                self.calc_complexity = calc_complexity

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                complexity = self.calc_complexity(node)
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
                complexity = self.calc_complexity(node)
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

        visitor = ComplexityVisitor(self._calculate_cognitive_complexity)
        visitor.visit(tree)

        return complex_functions

    def _calculate_cognitive_complexity(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> int:
        """Calculate cognitive complexity of function.

        Args:
            node: Function node

        Returns:
            Complexity score
        """
        calculator = ComplexityCalculator()
        calculator.visit(node)
        return calculator.complexity

    def extract_code_functions_for_semantic_analysis(
        self, content: str
    ) -> list[dict[str, t.Any]]:
        """Extract functions with complexity for semantic analysis.

        Args:
            content: File content

        Returns:
            List of functions
        """
        functions: list[dict[str, t.Any]] = []
        lines = content.split("\n")
        current_function = None

        for i, line in enumerate(lines):
            stripped = line.strip()

            if self._should_skip_line(stripped, current_function, line):
                continue

            indent = len(line) - len(line.lstrip())

            if self._is_function_definition(stripped):
                current_function = self._handle_function_definition(
                    functions, current_function, stripped, indent, i
                )
            elif current_function:
                current_function = self._handle_function_body_line(
                    functions, current_function, line, stripped, indent, i
                )

        if current_function:
            current_function["end_line"] = len(lines)
            current_function["estimated_complexity"] = (
                self._estimate_function_complexity(current_function["body"])
            )
            functions.append(current_function)

        return functions

    @staticmethod
    def _should_skip_line(
        stripped: str, current_function: dict[str, t.Any] | None, line: str
    ) -> bool:
        """Check if line should be skipped.

        Args:
            stripped: Stripped line
            current_function: Current function
            line: Full line

        Returns:
            True if should skip
        """
        if not stripped or stripped.startswith("#"):
            if current_function:
                current_function["body"] += line + "\n"
            return True
        return False

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
        functions: list[dict[str, t.Any]],
        current_function: dict[str, t.Any] | None,
        stripped: str,
        indent: int,
        line_index: int,
    ) -> dict[str, t.Any]:
        """Handle function definition.

        Args:
            functions: Functions list
            current_function: Current function
            stripped: Stripped line
            indent: Indent level
            line_index: Line index

        Returns:
            New function dict
        """
        if current_function:
            current_function["end_line"] = line_index
            current_function["estimated_complexity"] = (
                self._estimate_function_complexity(current_function["body"])
            )
            functions.append(current_function)

        func_name = stripped.split("(")[0].replace("def ", "").strip()
        return {
            "type": "function",
            "name": func_name,
            "signature": stripped,
            "start_line": line_index + 1,
            "body": "",
            "indent_level": indent,
        }

    def _handle_function_body_line(
        self,
        functions: list[dict[str, t.Any]],
        current_function: dict[str, t.Any],
        line: str,
        stripped: str,
        indent: int,
        line_index: int,
    ) -> dict[str, t.Any] | None:
        """Handle line in function body.

        Args:
            functions: Functions list
            current_function: Current function
            line: Full line
            stripped: Stripped line
            indent: Indent level
            line_index: Line index

        Returns:
            Updated current function or None
        """
        if self._is_line_inside_function(current_function, indent, stripped):
            current_function["body"] += line + "\n"
            return current_function
        else:
            current_function["end_line"] = line_index
            current_function["estimated_complexity"] = (
                self._estimate_function_complexity(current_function["body"])
            )
            functions.append(current_function)
            return None

    @staticmethod
    def _is_line_inside_function(
        current_function: dict[str, t.Any], indent: int, stripped: str
    ) -> bool:
        """Check if line is inside function.

        Args:
            current_function: Current function
            indent: Indent level
            stripped: Stripped line

        Returns:
            True if inside
        """
        return indent > current_function["indent_level"] or (
            indent == current_function["indent_level"]
            and stripped.startswith(('"', "'", "@"))
        )

    @staticmethod
    def _estimate_function_complexity(function_body: str) -> int:
        """Estimate function complexity from body.

        Args:
            function_body: Function body

        Returns:
            Complexity score
        """
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


class ComplexityCalculator(ast.NodeVisitor):
    """Calculates cognitive complexity of code."""

    def __init__(self) -> None:
        """Initialize calculator."""
        self.complexity = 0

    def visit_If(self, node: ast.If) -> None:
        """Visit if statement."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Visit for loop."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        """Visit while loop."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Visit exception handler."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        """Visit with statement."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        """Visit boolean operation."""
        # Count boolean operators for higher complexity
        if len(node.values) > 2:
            self.complexity += 1
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        """Visit lambda."""
        self.complexity += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Don't count nested functions separately."""
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Don't count nested async functions separately."""
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Don't count nested classes separately."""
        self.generic_visit(node)

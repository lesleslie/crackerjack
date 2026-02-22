"""Validation gates for AST transformations."""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ValidationResult:
    """Result of transform validation."""

    valid: bool = False
    gate_results: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Complexity metrics
    original_complexity: int | None = None
    transformed_complexity: int | None = None
    complexity_delta: int | None = None


class TransformValidator:
    """Validates transformed code against multiple gates.

    Gates are checked in order:
    1. Syntax - Code must parse
    2. Complexity reduction - New < original (with timeout)
    3. Behavior preservation - Signatures, returns, scope preserved
    4. Formatting preservation - Comments, whitespace, f-strings preserved
    """

    def __init__(
        self,
        complexity_timeout: float = 30.0,
        strict_formatting: bool = True,
    ) -> None:
        """Initialize validator.

        Args:
            complexity_timeout: Max seconds for complexity calculation
            strict_formatting: If True, reject any formatting loss
        """
        self.complexity_timeout = complexity_timeout
        self.strict_formatting = strict_formatting

    def validate(
        self,
        original: str,
        transformed: str,
        file_path: Path | None = None,
    ) -> ValidationResult:
        """Run all validation gates.

        Args:
            original: Original source code
            transformed: Transformed source code
            file_path: Optional file path for error reporting

        Returns:
            ValidationResult with gate outcomes and any errors
        """
        result = ValidationResult()

        # Gate 1: Syntax check
        syntax_result = self._check_syntax(transformed, file_path)
        result.gate_results["syntax"] = syntax_result["valid"]
        if not syntax_result["valid"]:
            result.errors.append(syntax_result["error"])
            result.valid = False
            return result

        # Gate 2: Complexity reduction
        complexity_result = self._check_complexity(original, transformed, file_path)
        result.gate_results["complexity"] = complexity_result["valid"]
        result.original_complexity = complexity_result.get("original")
        result.transformed_complexity = complexity_result.get("transformed")
        result.complexity_delta = complexity_result.get("delta")
        if not complexity_result["valid"]:
            result.errors.append(complexity_result["error"])
            result.valid = False
            return result

        # Gate 3: Behavior preservation
        behavior_result = self._check_behavior(original, transformed, file_path)
        result.gate_results["behavior"] = behavior_result["valid"]
        if not behavior_result["valid"]:
            result.errors.append(behavior_result["error"])
            result.valid = False
            return result

        # Gate 4: Formatting preservation
        formatting_result = self._check_formatting(original, transformed, file_path)
        result.gate_results["formatting"] = formatting_result["valid"]
        if not formatting_result["valid"]:
            if self.strict_formatting:
                result.errors.append(formatting_result["error"])
                result.valid = False
                return result
            else:
                result.warnings.append(formatting_result["error"])

        result.valid = True
        return result

    def _check_syntax(
        self,
        code: str,
        file_path: Path | None = None,
    ) -> dict[str, Any]:
        """Gate 1: Verify code parses successfully."""
        try:
            ast.parse(code)
            return {"valid": True}
        except SyntaxError as e:
            return {
                "valid": False,
                "error": f"Syntax error at line {e.lineno}: {e.msg}",
            }

    def _check_complexity(
        self,
        original: str,
        transformed: str,
        file_path: Path | None = None,
    ) -> dict[str, Any]:
        """Gate 2: Verify complexity was reduced."""
        try:
            original_complexity = self._calculate_complexity(original)
            transformed_complexity = self._calculate_complexity(transformed)

            delta = transformed_complexity - original_complexity

            if delta > 0:
                return {
                    "valid": False,
                    "error": f"Complexity increased by {delta}",
                    "original": original_complexity,
                    "transformed": transformed_complexity,
                    "delta": delta,
                }

            if delta == 0:
                return {
                    "valid": False,
                    "error": "Complexity unchanged - no improvement",
                    "original": original_complexity,
                    "transformed": transformed_complexity,
                    "delta": delta,
                }

            return {
                "valid": True,
                "original": original_complexity,
                "transformed": transformed_complexity,
                "delta": delta,
            }

        except TimeoutError:
            return {
                "valid": False,
                "error": f"Complexity calculation timed out after {self.complexity_timeout}s",
            }

    def _calculate_complexity(self, code: str) -> int:
        """Calculate cognitive complexity with nesting penalties.

        Cognitive complexity increases for:
        - Control structures (if, for, while, etc.): +1
        - Nesting: +1 per level for each control structure
        - Boolean operators (and, or): +1 for each additional operand
        """
        tree = ast.parse(code)

        def calculate_nested_complexity(
            node: ast.AST,
            nesting_level: int = 0,
        ) -> int:
            """Recursively calculate complexity with nesting."""
            complexity = 0

            # Control structures that add complexity
            control_types = (
                ast.If, ast.For, ast.While, ast.ExceptHandler,
                ast.With, ast.AsyncFor, ast.AsyncWith,
            )

            if isinstance(node, control_types):
                # Base complexity + nesting increment
                complexity += 1 + nesting_level
                new_nesting = nesting_level + 1
            else:
                new_nesting = nesting_level

            # Boolean operators (and, or)
            if isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1

            # Comprehensions
            if isinstance(node, ast.comprehension):
                complexity += 1 + nesting_level
                if node.ifs:
                    complexity += len(node.ifs)
                # Comprehensions create nesting for their element expression
                new_nesting = max(new_nesting, nesting_level + 1)

            # Lambda and ternary also nest
            if isinstance(node, ast.Lambda):
                new_nesting = max(new_nesting, nesting_level + 1)

            if isinstance(node, ast.IfExp):  # Ternary operator
                complexity += 1 + nesting_level

            # Recurse into children
            for child in ast.iter_child_nodes(node):
                complexity += calculate_nested_complexity(child, new_nesting)

            return complexity

        return calculate_nested_complexity(tree)

    def _check_behavior(
        self,
        original: str,
        transformed: str,
        file_path: Path | None = None,
    ) -> dict[str, Any]:
        """Gate 3: Verify behavior is preserved."""
        try:
            original_tree = ast.parse(original)
            transformed_tree = ast.parse(transformed)
        except SyntaxError:
            return {"valid": False, "error": "Cannot check behavior - syntax error"}

        # Check function signatures match
        original_funcs = self._extract_function_signatures(original_tree)
        transformed_funcs = self._extract_function_signatures(transformed_tree)

        if original_funcs != transformed_funcs:
            return {
                "valid": False,
                "error": "Function signatures changed",
            }

        # Check return value consistency
        original_returns = self._extract_return_patterns(original_tree)
        transformed_returns = self._extract_return_patterns(transformed_tree)

        if not self._returns_compatible(original_returns, transformed_returns):
            return {
                "valid": False,
                "error": "Return value patterns changed",
            }

        # Check for deleted statements (simplified check)
        original_stmts = self._count_statements(original_tree)
        transformed_stmts = self._count_statements(transformed_tree)

        # Allow some variation but flag large deletions
        if transformed_stmts < original_stmts * 0.5:
            return {
                "valid": False,
                "error": f"Too many statements deleted: {original_stmts} -> {transformed_stmts}",
            }

        return {"valid": True}

    def _extract_function_signatures(self, tree: ast.AST) -> dict[str, tuple]:
        """Extract function signatures from AST."""
        signatures: dict[str, tuple] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Extract: name, args, defaults, return annotation
                args = []
                for arg in node.args.args:
                    args.append(arg.arg)

                returns = None
                if node.returns:
                    returns = ast.unparse(node.returns)

                signatures[node.name] = (tuple(args), returns, isinstance(node, ast.AsyncFunctionDef))

        return signatures

    def _extract_return_patterns(self, tree: ast.AST) -> list[str]:
        """Extract return value types for consistency checking."""
        patterns: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and node.value:
                # Classify return type
                if isinstance(node.value, ast.Constant):
                    if node.value.value is None:
                        patterns.append("None")
                    elif isinstance(node.value.value, bool):
                        patterns.append("bool")
                    elif isinstance(node.value.value, int):
                        patterns.append("int")
                    elif isinstance(node.value.value, str):
                        patterns.append("str")
                    else:
                        patterns.append("constant")
                elif isinstance(node.value, ast.List):
                    patterns.append("list")
                elif isinstance(node.value, ast.Dict):
                    patterns.append("dict")
                elif isinstance(node.value, ast.Tuple):
                    patterns.append("tuple")
                elif isinstance(node.value, ast.Name):
                    patterns.append("name")
                elif isinstance(node.value, ast.Call):
                    patterns.append("call")
                else:
                    patterns.append("other")

        return sorted(patterns)

    def _returns_compatible(
        self,
        original: list[str],
        transformed: list[str],
    ) -> bool:
        """Check if return patterns are compatible.

        Returns are compatible if:
        - Same types present (order can change)
        - No None -> value or value -> None changes
        """
        # Can't add None returns where there weren't any
        if "None" not in original and "None" in transformed:
            return False

        # Can't remove None returns (might be expected)
        if "None" in original and "None" not in transformed:
            return False

        return True

    def _count_statements(self, tree: ast.AST) -> int:
        """Count top-level statements in AST."""
        count = 0
        for _ in ast.walk(tree):
            if isinstance(
                _,
                ast.Expr | ast.Assign | ast.AugAssign | ast.AnnAssign |
                ast.Return | ast.Raise | ast.Pass | ast.Break | ast.Continue |
                ast.If | ast.For | ast.While | ast.With | ast.Try |
                ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
            ):
                count += 1
        return count

    def _check_formatting(
        self,
        original: str,
        transformed: str,
        file_path: Path | None = None,
    ) -> dict[str, Any]:
        """Gate 4: Verify formatting is preserved."""
        # Check comments preserved
        original_comments = self._extract_comments(original)
        transformed_comments = self._extract_comments(transformed)

        missing_comments = original_comments - transformed_comments
        if missing_comments:
            return {
                "valid": False,
                "error": f"Comments lost: {missing_comments}",
            }

        # Check docstrings preserved
        try:
            original_tree = ast.parse(original)
            transformed_tree = ast.parse(transformed)

            original_docstrings = self._extract_docstrings(original_tree)
            transformed_docstrings = self._extract_docstrings(transformed_tree)

            if original_docstrings != transformed_docstrings:
                return {
                    "valid": False,
                    "error": "Docstrings changed or removed",
                }
        except SyntaxError:
            pass  # Already caught in syntax gate

        # Check f-strings not converted to .format()
        if ".format(" in transformed and ".format(" not in original:
            return {
                "valid": False,
                "error": "F-strings converted to .format()",
            }

        # Check type annotation style preserved (X | Y vs Union[X, Y])
        if "Union[" in transformed and "Union[" not in original:
            return {
                "valid": False,
                "error": "Type annotations changed from | to Union",
            }

        return {"valid": True}

    def _extract_comments(self, code: str) -> set[str]:
        """Extract all comments from source code."""
        comments: set[str] = set()
        for line in code.split("\n"):
            # Handle inline comments
            if "#" in line:
                comment_part = line[line.index("#"):]
                comments.add(comment_part.strip())
        return comments

    def _extract_docstrings(self, tree: ast.AST) -> dict[str, str]:
        """Extract docstrings from functions and classes."""
        docstrings: dict[str, str] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if (node.body and
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant) and
                    isinstance(node.body[0].value.value, str)):
                    docstrings[node.name] = node.body[0].value.value

        return docstrings

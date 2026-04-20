import ast
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ValidationResult:
    valid: bool = False
    gate_results: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    original_complexity: int | None = None
    transformed_complexity: int | None = None
    complexity_delta: int | None = None


class TransformValidator:
    def __init__(
        self,
        complexity_timeout: float = 30.0,
        strict_formatting: bool = True,
    ) -> None:
        self.complexity_timeout = complexity_timeout
        self.strict_formatting = strict_formatting

    def validate(
        self,
        original: str,
        transformed: str,
        file_path: Path | None = None,
        target_function_name: str | None = None,
    ) -> ValidationResult:
        result = ValidationResult()

        syntax_result = self._check_syntax(transformed, file_path)
        result.gate_results["syntax"] = syntax_result["valid"]
        if not syntax_result["valid"]:
            result.errors.append(syntax_result["error"])
            result.valid = False
            return result

        complexity_result = self._check_complexity(
            original,
            transformed,
            file_path,
            target_function_name=target_function_name,
        )
        result.gate_results["complexity"] = complexity_result["valid"]
        result.original_complexity = complexity_result.get("original")
        result.transformed_complexity = complexity_result.get("transformed")
        result.complexity_delta = complexity_result.get("delta")
        if not complexity_result["valid"]:
            result.errors.append(complexity_result["error"])
            result.valid = False
            return result

        behavior_result = self._check_behavior(
            original,
            transformed,
            file_path,
            target_function_name=target_function_name,
        )
        result.gate_results["behavior"] = behavior_result["valid"]
        if not behavior_result["valid"]:
            result.errors.append(behavior_result["error"])
            result.valid = False
            return result

        formatting_result = self._check_formatting(
            original,
            transformed,
            file_path,
            target_function_name=target_function_name,
        )
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
        target_function_name: str | None = None,
    ) -> dict[str, Any]:
        try:
            if target_function_name:
                original_complexity = self._calculate_target_function_complexity(
                    original,
                    target_function_name,
                )
                transformed_complexity = self._calculate_target_function_complexity(
                    transformed,
                    target_function_name,
                )
            else:
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

    def _calculate_target_function_complexity(
        self,
        code: str,
        target_function_name: str,
    ) -> int:
        tree = ast.parse(code)

        target_functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == target_function_name
        ]
        if not target_functions:
            return self._calculate_complexity(code)

        return max(
            self._calculate_complexity(ast.unparse(func)) for func in target_functions
        )

    def _calculate_complexity(self, code: str) -> int:
        tree = ast.parse(code)

        def calculate_nested_complexity(
            node: ast.AST,
            nesting_level: int = 0,
        ) -> int:
            complexity = 0

            control_types = (
                ast.If,
                ast.For,
                ast.While,
                ast.ExceptHandler,
                ast.With,
                ast.AsyncFor,
                ast.AsyncWith,
            )

            if isinstance(node, control_types):
                complexity += 1 + nesting_level
                new_nesting = nesting_level + 1
            else:
                new_nesting = nesting_level

            if isinstance(node, ast.BoolOp):
                complexity += len(node.values) - 1

            if isinstance(node, ast.comprehension):
                complexity += 1 + nesting_level
                if node.ifs:
                    complexity += len(node.ifs)

                new_nesting = max(new_nesting, nesting_level + 1)

            if isinstance(node, ast.Lambda):
                new_nesting = max(new_nesting, nesting_level + 1)

            if isinstance(node, ast.IfExp):
                complexity += 1 + nesting_level

            for child in ast.iter_child_nodes(node):
                complexity += calculate_nested_complexity(child, new_nesting)

            return complexity

        return calculate_nested_complexity(tree)

    def _check_behavior(
        self,
        original: str,
        transformed: str,
        file_path: Path | None = None,
        target_function_name: str | None = None,
    ) -> dict[str, Any]:
        try:
            original_tree = ast.parse(original)
            transformed_tree = ast.parse(transformed)
        except SyntaxError:
            return {"valid": False, "error": "Cannot check behavior - syntax error"}

        if target_function_name:
            original_func = self._find_function_by_name(
                original_tree, target_function_name
            )
            transformed_func = self._find_function_by_name(
                transformed_tree,
                target_function_name,
            )
            if original_func is None or transformed_func is None:
                return {
                    "valid": False,
                    "error": f"Target function {target_function_name} missing after transform",
                }

            original_funcs = {
                target_function_name: self._extract_function_signature(original_func)
            }
            transformed_funcs = {
                target_function_name: self._extract_function_signature(transformed_func)
            }
            original_returns = self._extract_return_patterns(original_func)
            transformed_returns = self._extract_return_patterns(transformed_func)
        else:
            original_funcs = self._extract_function_signatures(original_tree)
            transformed_funcs = self._extract_function_signatures(transformed_tree)
            original_returns = self._extract_return_patterns(original_tree)
            transformed_returns = self._extract_return_patterns(transformed_tree)

        if original_funcs != transformed_funcs:
            return {
                "valid": False,
                "error": "Function signatures changed",
            }

        if not self._returns_compatible(original_returns, transformed_returns):
            return {
                "valid": False,
                "error": "Return value patterns changed",
            }

        original_stmts = self._count_statements(original_tree)
        transformed_stmts = self._count_statements(transformed_tree)

        if transformed_stmts < original_stmts * 0.5:
            return {
                "valid": False,
                "error": f"Too many statements deleted: {original_stmts} -> {transformed_stmts}",
            }

        return {"valid": True}

    def _extract_function_signatures(self, tree: ast.AST) -> dict[str, tuple]:
        signatures: dict[str, tuple] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                signatures[node.name] = self._extract_function_signature(node)

        return signatures

    def _extract_function_signature(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> tuple:
        args = [arg.arg for arg in node.args.args]

        returns = None
        if node.returns:
            returns = ast.unparse(node.returns)

        return (
            tuple(args),
            returns,
            isinstance(node, ast.AsyncFunctionDef),
        )

    def _find_function_by_name(
        self,
        tree: ast.AST,
        target_function_name: str,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and node.name == target_function_name
            ):
                return node
        return None

    def _extract_return_patterns(self, tree: ast.AST) -> list[str]:
        patterns: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Return) and node.value:
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

        if "None" not in original and "None" in transformed:
            return False

        if "None" in original and "None" not in transformed:
            return False

        return True

    def _count_statements(self, tree: ast.AST) -> int:
        count = 0
        for _ in ast.walk(tree):
            if isinstance(
                _,
                ast.Expr
                | ast.Assign
                | ast.AugAssign
                | ast.AnnAssign
                | ast.Return
                | ast.Raise
                | ast.Pass
                | ast.Break
                | ast.Continue
                | ast.If
                | ast.For
                | ast.While
                | ast.With
                | ast.Try
                | ast.FunctionDef
                | ast.AsyncFunctionDef
                | ast.ClassDef,
            ):
                count += 1
        return count

    def _check_formatting(
        self,
        original: str,
        transformed: str,
        file_path: Path | None = None,
        target_function_name: str | None = None,
    ) -> dict[str, Any]:
        with suppress(SyntaxError):
            original_tree = ast.parse(original)
            transformed_tree = ast.parse(transformed)

            if target_function_name:
                original_func = self._find_function_by_name(
                    original_tree,
                    target_function_name,
                )
                transformed_func = self._find_function_by_name(
                    transformed_tree,
                    target_function_name,
                )
                if original_func and transformed_func:
                    original_docstrings = {
                        target_function_name: ast.get_docstring(original_func)
                    }
                    transformed_docstrings = {
                        target_function_name: ast.get_docstring(transformed_func)
                    }
                else:
                    original_docstrings = self._extract_docstrings(original_tree)
                    transformed_docstrings = self._extract_docstrings(transformed_tree)
            else:
                original_docstrings = self._extract_docstrings(original_tree)
                transformed_docstrings = self._extract_docstrings(transformed_tree)

            if original_docstrings != transformed_docstrings:
                return {
                    "valid": False,
                    "error": "Docstrings changed or removed",
                }

        if ".format(" in transformed and ".format(" not in original:
            return {
                "valid": False,
                "error": "F-strings converted to .format()",
            }

        if "Union[" in transformed and "Union[" not in original:
            return {
                "valid": False,
                "error": "Type annotations changed from | to Union",
            }

        return {"valid": True}

    def _extract_comments(self, code: str) -> set[str]:
        comments: set[str] = set()
        for line in code.split("\n"):
            if "#" in line:
                comment_part = line[line.index("#") :]
                comments.add(comment_part.strip())
        return comments

    def _extract_docstrings(self, tree: ast.AST) -> dict[str, str]:
        docstrings: dict[str, str] = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    docstrings[node.name] = node.body[0].value.value

        return docstrings

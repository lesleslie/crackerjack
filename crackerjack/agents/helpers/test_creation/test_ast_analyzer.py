
import ast
from pathlib import Path
from typing import Any

from crackerjack.agents.base import AgentContext


class TestASTAnalyzer:

    def __init__(self, context: AgentContext) -> None:
        self.context = context

    async def extract_functions_from_file(
        self,
        file_path: Path,
    ) -> list[dict[str, Any]]:
        functions: list[dict[str, Any]] = []

        try:
            content = self.context.get_file_content(file_path)
            if not content:
                return functions

            tree = ast.parse(content)
            functions = self._parse_function_nodes(tree)

        except Exception as e:
            self._log(f"Error parsing file {file_path}: {e}", "WARN")

        return functions

    def _parse_function_nodes(self, tree: ast.AST) -> list[dict[str, Any]]:
        functions: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(
                node, ast.FunctionDef | ast.AsyncFunctionDef
            ) and self._is_valid_function_node(node):
                function_info = self._create_function_info(node)

                function_info["is_async"] = isinstance(node, ast.AsyncFunctionDef)
                functions.append(function_info)

        return functions

    def _is_valid_function_node(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> bool:
        return not node.name.startswith(("_", "test_"))

    def _create_function_info(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> dict[str, Any]:
        return {
            "name": node.name,
            "line": node.lineno,
            "signature": self._get_function_signature(node),
            "args": [arg.arg for arg in node.args.args],
            "returns": self._get_return_annotation(node),
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "docstring": ast.get_docstring(node) or "",
        }

    async def extract_classes_from_file(self, file_path: Path) -> list[dict[str, Any]]:
        classes: list[dict[str, Any]] = []

        try:
            content = self.context.get_file_content(file_path)
            if not content:
                return classes

            tree = ast.parse(content)
            classes = self._process_ast_nodes_for_classes(tree)

        except Exception as e:
            self._log(f"Error parsing classes from {file_path}: {e}", "WARN")

        return classes

    def _process_ast_nodes_for_classes(self, tree: ast.AST) -> list[dict[str, Any]]:
        classes: list[dict[str, Any]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and self._should_include_class(node):
                class_info = self._create_class_info(node)
                classes.append(class_info)

        return classes

    def _should_include_class(self, node: ast.ClassDef) -> bool:
        return not node.name.startswith("_")

    def _create_class_info(self, node: ast.ClassDef) -> dict[str, Any]:
        methods = self._extract_public_methods_from_class(node)
        return {"name": node.name, "line": node.lineno, "methods": methods}

    def _extract_public_methods_from_class(self, node: ast.ClassDef) -> list[str]:
        return [
            item.name
            for item in node.body
            if isinstance(item, ast.FunctionDef) and not item.name.startswith("_")
        ]

    def _get_function_signature(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str:
        args = [arg.arg for arg in node.args.args]
        prefix = "async " if isinstance(node, ast.AsyncFunctionDef) else ""
        return f"{prefix}{node.name}({', '.join(args)})"

    def _get_return_annotation(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> str:
        if node.returns:
            return ast.unparse(node.returns) if (hasattr(ast, "unparse")) else "Any"
        return "Any"

    async def function_has_test(
        self,
        func_info: dict[str, Any],
        file_path: Path,
    ) -> bool:
        test_file_path = await self.generate_test_file_path(file_path)

        if not test_file_path.exists():
            return False

        test_content = self.context.get_file_content(test_file_path)
        if not test_content:
            return False

        test_patterns = [
            f"test_{func_info['name']}",
            f"test_{func_info['name']}_",
            f"def test_{func_info['name']}",
        ]

        return any(pattern in test_content for pattern in test_patterns)

    async def generate_test_file_path(self, source_file: Path) -> Path:
        tests_dir = self.context.project_path / "tests"
        tests_dir.mkdir(exist_ok=True)

        relative_path = source_file.relative_to(
            self.context.project_path / "crackerjack",
        )
        test_name = f"test_{relative_path.stem}.py"

        return tests_dir / test_name

    def get_module_import_path(self, file_path: Path) -> str:
        try:
            relative_path = file_path.relative_to(self.context.project_path)
            parts = (*relative_path.parts[:-1], relative_path.stem)
            return ".".join(parts)
        except ValueError:
            return file_path.stem

    def should_skip_module_for_coverage(self, py_file: Path) -> bool:
        return py_file.name.startswith("test_") or py_file.name == "__init__.py"

    def should_skip_file_for_testing(self, py_file: Path) -> bool:
        return py_file.name.startswith("test_")

    def has_corresponding_test(self, file_path: str) -> bool:
        path = Path(file_path)

        test_patterns = [
            f"test_{path.stem}.py",
            f"{path.stem}_test.py",
            f"test_{path.stem}_*.py",
        ]

        tests_dir = self.context.project_path / "tests"
        if tests_dir.exists():
            for pattern in test_patterns:
                if list(tests_dir.glob(pattern)):
                    return True

        return False

    def get_relative_module_path(self, py_file: Path) -> str:
        return str(py_file.relative_to(self.context.project_path))

    def _log(self, message: str, level: str = "INFO") -> None:

        pass

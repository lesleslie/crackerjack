import ast
import logging
import re
from typing import Any

from ..agents.base import Issue
from .file_context import FileContextReader

logger = logging.getLogger(__name__)


class ContextAgent:
    def __init__(self, project_path: str) -> None:
        self.project_path = project_path
        self.file_reader = FileContextReader()

    async def extract_context(self, issue: Issue) -> dict[str, Any]:
        if not issue.file_path:
            logger.warning(f"No file path for issue {issue.id}")
            return {}

        try:
            file_content = await self.file_reader.read_file(issue.file_path)
        except Exception as e:
            logger.error(f"Failed to read file {issue.file_path}: {e}")
            return {}

        context = {
            "file_content": file_content,
            "file_path": issue.file_path,
            "line_number": issue.line_number,
        }

        context["relevant_code"] = self._extract_relevant_code(
            file_content, issue.line_number or 0
        )

        context["imports"] = self._extract_imports_ast(file_content)  # type: ignore[untyped]

        functions, classes = self._extract_definitions(file_content)
        context["functions"] = functions  # type: ignore[untyped]
        context["classes"] = classes  # type: ignore

        logger.info(
            f"Extracted context for {issue.file_path}:{issue.line_number}: "
            f"{len(context['imports'])} imports, "  # type: ignore
            f"{len(context['functions'])} functions, "  # type: ignore
            f"{len(context['classes'])} classes"  # type: ignore
        )

        return context

    def _extract_relevant_code(self, content: str, line_number: int) -> str:
        lines = content.split("\n")
        context_window = 20

        start = max(0, line_number - context_window - 1)
        end = min(len(lines), line_number + context_window)

        relevant_lines = lines[start: end]
        return "\n".join(relevant_lines)

    def _extract_imports_ast(self, content: str) -> list[str]:
        imports = []

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.append(ast.get_source_segment(content, node))

        except SyntaxError:
            imports = self._extract_imports_regex(content)

        return imports

    def _extract_imports_regex(self, content: str) -> list[str]:
        import_pattern = r"^(?:import\s+[^\n]+|from\s+[^\n]+(?:import\s+[^\n]+)?)"
        matches = re.findall(import_pattern, content, re.MULTILINE)

        logger.info(f"Extracted {len(matches)} imports via regex fallback")
        return matches

    def _extract_definitions(self, content: str) -> tuple[list[str], list[str]]:
        functions = []
        classes = []

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(f"def {node.name}")
                elif isinstance(node, ast.AsyncFunctionDef):
                    functions.append(f"async def {node.name}")
                elif isinstance(node, ast.ClassDef):
                    classes.append(f"class {node.name}")

        except SyntaxError:
            logger.debug("Syntax error in file, skipping definition extraction")

        return functions, classes

    async def can_handle(self, issue: Issue) -> float:
        return 0.9

    def get_supported_types(self) -> set:
        from ..agents.base import IssueType

        return set(IssueType)

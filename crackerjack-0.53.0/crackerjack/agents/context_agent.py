"""
Context extraction agent for AI fix planning.

Extracts relevant context around issues to inform fix generation.
"""

import ast
import logging
import re
from typing import Any

from ..agents.base import Issue
from .file_context import FileContextReader

logger = logging.getLogger(__name__)


class ContextAgent:
    """
    Extract context around code issues to inform fix generation.

    Provides:
    - Function/class context (surrounding code)
    - Import statements
    - Related code patterns
    """

    def __init__(self, project_path: str) -> None:
        """
        Initialize context agent.

        Args:
            project_path: Root path for file operations
        """
        self.project_path = project_path
        self.file_reader = FileContextReader()

    async def extract_context(self, issue: Issue) -> dict[str, Any]:
        """
        Extract context for the given issue.

        Args:
            issue: Issue to extract context for

        Returns:
            Dictionary with extracted context:
            - file_content: Full file content
            - relevant_code: Code around issue location
            - imports: List of import statements
            - functions: List of function definitions
            - classes: List of class definitions
        """
        if not issue.file_path:
            logger.warning(f"No file path for issue {issue.id}")
            return {}

        # Read full file content
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

        # Extract relevant code around issue
        context["relevant_code"] = self._extract_relevant_code(
            file_content, issue.line_number or 0
        )

        # Extract imports
        context["imports"] = self._extract_imports_ast(file_content)

        # Extract function and class definitions
        functions, classes = self._extract_definitions(file_content)
        context["functions"] = functions
        context["classes"] = classes

        logger.info(
            f"Extracted context for {issue.file_path}:{issue.line_number}: "
            f"{len(context['imports'])} imports, "
            f"{len(context['functions'])} functions, "
            f"{len(context['classes'])} classes"
        )

        return context

    def _extract_relevant_code(self, content: str, line_number: int) -> str:
        """
        Extract code around the issue location.

        Args:
            content: Full file content
            line_number: Line number of issue

        Returns:
            Relevant code snippet (context window)
        """
        lines = content.split("\n")
        context_window = 20  # 20 lines before and after

        start = max(0, line_number - context_window - 1)
        end = min(len(lines), line_number + context_window)

        relevant_lines = lines[start:end]
        return "\n".join(relevant_lines)

    def _extract_imports_ast(self, content: str) -> list[str]:
        """
        Extract import statements using AST parsing.

        Args:
            content: File content

        Returns:
            List of import statements
        """
        imports = []

        try:
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imports.append(ast.get_source_segment(content, node))

        except SyntaxError:
            # Fallback to regex if AST parsing fails
            imports = self._extract_imports_regex(content)

        return imports

    def _extract_imports_regex(self, content: str) -> list[str]:
        """
        Extract import statements using regex (fallback method).

        Args:
            content: File content

        Returns:
            List of import statements
        """
        import_pattern = r"^(?:import\s+[^\n]+|from\s+[^\n]+(?:import\s+[^\n]+)?)"
        matches = re.findall(import_pattern, content, re.MULTILINE)

        logger.info(f"Extracted {len(matches)} imports via regex fallback")
        return matches

    def _extract_definitions(self, content: str) -> tuple[list[str], list[str]]:
        """
        Extract function and class definitions.

        Args:
            content: File content

        Returns:
            Tuple of (functions, classes)
        """
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
            logger.warning("Syntax error in file, skipping definition extraction")

        return functions, classes

    async def can_handle(self, issue: Issue) -> float:
        """Context agent can handle any issue type."""
        return 0.9  # High confidence for context extraction

    def get_supported_types(self) -> set:
        """Context agent works with all issue types."""
        from ..agents.base import IssueType

        return set(IssueType)

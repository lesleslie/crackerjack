"""
Anti-pattern detection agent for AI fix planning.

Identifies common code anti-patterns to warn fix generation.
"""

import ast
import logging
from typing import Any

from .file_context import FileContextReader

logger = logging.getLogger(__name__)


class AntiPatternAgent:
    """
    Detect anti-patterns in code to inform fix generation.

    Identifies:
    - Duplicate definitions
    - Unclosed brackets/parentheses
    - Misplaced imports
    - Future imports issues
    """

    def __init__(self, project_path: str) -> None:
        """
        Initialize anti-pattern agent.

        Args:
            project_path: Root path for file operations
        """
        self.project_path = project_path
        self.file_reader = FileContextReader()

    async def identify_anti_patterns(self, context: dict[str, Any]) -> list[str]:
        """
        Identify anti-patterns in the given code context.

        Args:
            context: Context dict from ContextAgent

        Returns:
            List of anti-pattern warnings
        """
        warnings = []

        # Check for code content (support multiple key names for compatibility)
        code = (
            context.get("code")
            or context.get("relevant_code")
            or context.get("file_content")
        )
        if not code:
            warnings.append("No code content in context")
            return warnings

        # Check for duplicate definitions
        duplicate_defs = self._check_duplicate_definitions(code)
        if duplicate_defs:
            warnings.extend(duplicate_defs)

        # Check for unclosed brackets
        unclosed = self._check_unclosed_brackets(code)
        if unclosed:
            warnings.append(unclosed)

        # Check for misplaced imports
        misplaced = self._check_import_placement(code)
        if misplaced:
            warnings.append(misplaced)

        # Check for future imports
        future_issues = self._check_future_imports(code)
        if future_issues:
            warnings.extend(future_issues)

        logger.info(f"Found {len(warnings)} anti-pattern warnings")
        return warnings

    def _check_duplicate_definitions(self, code: str) -> list[str]:
        """Check for duplicate function/class definitions."""
        try:
            tree = ast.parse(code)
            definitions = {}

            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    name = node.name
                    if name in definitions:
                        return [f"Duplicate definition of '{name}' detected"]
                    definitions[name] = node.lineno

            return []
        except Exception as e:
            logger.debug(f"Duplicate definition check failed: {e}")
            return []

    def _check_unclosed_brackets(self, code: str) -> str | None:
        """Check for unclosed brackets/parentheses."""
        open_brackets = {"(": ")", "[": "]", "{": "}"}
        stack = []

        for i, char in enumerate(code):
            if char in open_brackets:
                stack.append((char, i))
            elif char in open_brackets.values():
                if not stack:
                    return f"Unmatched closing '{char}' at position {i}"
                expected_closing = open_brackets[stack[-1][0]]
                if char != expected_closing:
                    return f"Mismatched brackets: expected '{expected_closing}' but got '{char}' at position {i}"
                stack.pop()

        if stack:
            open_char, pos = stack[-1]
            return f"Unclosed '{open_char}' at position {pos}"

        return None

    def _check_import_placement(self, code: str) -> str | None:
        """Check for misplaced import statements."""
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                # Check if import is in the middle of code (not at top)
                if i > 10 and not any(
                    x in lines[:i]
                    for x in ["'''", '"""', "class ", "def ", "async def "]
                ):
                    return f"Import statement at line {i} appears mid-file"

        return None

    def _check_future_imports(self, code: str) -> list[str]:
        """Check for problematic __future__ imports."""
        warnings = []

        # Check for future imports after other code
        lines = code.split("\n")
        future_found = False
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("__future__"):
                if future_found:
                    warnings.append(f"Multiple __future__ imports detected (line {i})")
                future_found = True
            elif stripped and not stripped.startswith("#") and future_found:
                # Non-comment, non-future code after future import
                if any(
                    stripped.startswith(x)
# TODO: Refactor for x in ["import ", "from ", "class ", "def ", "async def "]
                    for x in ["import ", "from ", "class ", "def ", "async def "]
                ):
                    warnings.append(
                        f"Code after __future__ import (line {i}) - "
                        "move __future__ to top of file"
                    )

        return warnings

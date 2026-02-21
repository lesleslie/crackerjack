"""
from typing import List
Logic validation for AI-generated fixes.

Checks for logical errors, duplicate definitions, and common pitfalls.
"""

import ast
import logging
import re

logger = logging.getLogger(__name__)

from .syntax_validator import ValidationResult


class LogicValidator:
    """
    Validator for logical correctness of generated code.

    Checks for:
    - Duplicate function/class definitions
    - Misplaced imports
    - Incomplete code blocks
    """

    async def validate(self, code: str) -> ValidationResult:
        """
        Validate code logic and structure.

        Args:
            code: Python code to validate

        Returns:
            ValidationResult with any logic errors found
        """
        errors = []

        # Check for duplicate definitions
        duplicate_errors = self._check_duplicate_definitions(code)
        errors.extend(duplicate_errors)

        # Check import placement
        import_errors = self._check_import_placement(code)
        errors.extend(import_errors)

        # Check for incomplete blocks
        block_errors = self._check_complete_blocks(code)
        errors.extend(block_errors)

        # Check for common anti-patterns
        pattern_errors = self._check_anti_patterns(code)
        errors.extend(pattern_errors)

        is_valid = len(errors) == 0

        if is_valid:
            logger.debug("✅ Logic validation passed")
        else:
            logger.error(f"❌ Logic validation found {len(errors)} errors")

        return ValidationResult(valid=is_valid, errors=errors)

    def _check_duplicate_definitions(self, code: str) -> list[str]:
        """Check for duplicate function/class definitions."""
        errors = []

        try:
            tree = ast.parse(code)
            definitions: dict[str, list[int]] = {}

            for node in ast.walk(tree):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    name = node.name
                    lineno = node.lineno

                    if name not in definitions:
                        definitions[name] = []

                    definitions[name].append(lineno)

            # Check for duplicates
            for name, linenos in definitions.items():
                if len(linenos) > 1:
                    locations = ", ".join(str(lineno) for lineno in linenos)
                    errors.append(f"Duplicate definition '{name}' at lines {locations}")

        except SyntaxError:
            # If code has syntax errors, skip this check
            pass

        return errors

    def _check_import_placement(self, code: str) -> list[str]:
        """Check for misplaced imports (should be at top)."""
        errors = []

        lines = code.split("\n")

        # Find all import statements
        import_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                import_lines.append(i)

        if not import_lines:
            return errors

        # Check if there are non-import/non-docstring lines before first import
        first_import = min(import_lines)

        for i in range(first_import):
            line = lines[i].strip()

            # Skip blank lines, comments, and docstrings
            if (
                not line
                or line.startswith("#")
                or line.startswith('"""')
                or line.startswith("'''")
            ):
                continue

            # Found code before imports
            errors.append(
                f"Import statement at line {first_import + 1} "
                f"should be before code at line {i + 1}"
            )
            break

        # Check for imports after function/class definitions
        code_started = False
        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith(("def ", "async def ", "class ")):
                code_started = True
            elif code_started and stripped.startswith(("import ", "from ")):
                errors.append(
                    f"Import statement at line {i + 1} appears after code definitions"
                )

        return errors

    def _check_complete_blocks(self, code: str) -> list[str]:
        """Check for incomplete code blocks."""
        errors = []

        # Check for unclosed blocks (missing indentation)
        lines = code.split("\n")
        block_stack = []

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Track block openings
            if any(
                stripped.startswith(kw)
                for kw in (
                    "def ",
                    "async def ",
                    "class ",
                    "if ",
                    "for ",
                    "while ",
                    "try:",
                    "with ",
                )
            ):
                if stripped.endswith(":"):
                    block_stack.append((i + 1, stripped))

            # Check for empty blocks (just pass or ...)
            if stripped in ("pass", "...") and block_stack:
                start_lineno, start_line = block_stack[-1]
                if i == start_lineno + 1:  # Immediately after block start
                    errors.append(
                        f"Empty block at line {i + 1} "
                        f"(block started at line {start_lineno} with '{start_line}')"
                    )
                    block_stack.pop()

        return errors

    def _check_anti_patterns(self, code: str) -> list[str]:
        """Check for common anti-patterns that indicate bad fixes."""
        errors = []

        # Check for future imports at top (should be first)
        lines = code.split("\n")
        non_future_before_future = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            if stripped.startswith("from __future__ import"):
                # After future import, only other future imports or docstrings
                continue
            elif (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith(('"""', "'''"))
            ):
                if not any(
                    kw in stripped for kw in ("import ", "from ", "def ", "class ")
                ):
                    # Found non-import, non-comment line before future import
                    if not non_future_before_future:
                        # Only warn once
                        non_future_before_future = True

        # Check for TODO/FIXME comments (indicates incomplete fix)
        for i, line in enumerate(lines):
            if "todo" in line.lower() or "fixme" in line.lower():
                errors.append(
                    f"Line {i + 1} contains TODO/FIXME - fix may be incomplete"
                )

        # Check for hardcoded paths
        path_pattern = r'["/][/][a-zA-Z0-9_/]+'
        if re.search(path_pattern, code):
            errors.append("Code contains hardcoded absolute paths")

        return errors

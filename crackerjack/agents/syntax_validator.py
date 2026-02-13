"""
AST-based syntax validation for AI-generated fixes.

Provides fast, reliable syntax checking before applying fixes.
"""

import ast
import dataclasses
import logging

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ValidationResult:
    """Result of validation check."""

    valid: bool
    errors: list[str]

    def __bool__(self) -> bool:
        return self.valid

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        """Merge two validation results."""
        return ValidationResult(
            valid=self.valid and other.valid, errors=self.errors + other.errors
        )


class SyntaxValidator:
    """
    AST-based syntax validator for Python code.

    Catches syntax errors that would break execution.
    """

    async def validate(self, code: str) -> ValidationResult:
        """
        Validate Python code syntax using AST parsing.

        Args:
            code: Python code to validate

        Returns:
            ValidationResult with validity status and any errors
        """
        errors = []

        try:
            ast.parse(code)
            logger.debug("✅ Syntax validation passed")
            return ValidationResult(valid=True, errors=[])
        except SyntaxError as e:
            error_msg = (
                f"Syntax error at line {e.lineno}: {e.msg}\n"
                f"  {e.text if e.text else '(no context)'}"
            )
            errors.append(error_msg)
            logger.error(f"❌ Syntax validation failed: {error_msg}")
            return ValidationResult(valid=False, errors=errors)
        except Exception as e:
            errors.append(f"Unexpected error during syntax validation: {e}")
            logger.error(f"❌ Syntax validation error: {e}")
            return ValidationResult(valid=False, errors=errors)

    def validate_incomplete_code(self, code: str) -> list[str]:
        """
        Check for common incomplete code patterns.

        Args:
            code: Code to check

        Returns:
            List of warning messages
        """
        warnings = []

        # Check for unclosed brackets/parens
        open_brackets = code.count("(") - code.count(")")
        open_braces = code.count("{") - code.count("}")
        open_brackets_sq = code.count("[") - code.count("]")

        if open_brackets > 0:
            warnings.append(f"{open_brackets} unclosed parenthesis")
        if open_braces > 0:
            warnings.append(f"{open_braces} unclosed braces")
        if open_brackets_sq > 0:
            warnings.append(f"{open_brackets_sq} unclosed square brackets")

        # Check for incomplete statements
        lines = code.split("\n")
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.endswith((":", "\\")) and not any(
                stripped.startswith(kw)
                for kw in (
                    "if",
                    "else",
                    "elif",
                    "for",
                    "while",
                    "try",
                    "except",
                    "finally",
                    "with",
                    "def",
                    "class",
                )
            ):
                warnings.append(f"Possible incomplete statement at line {i}")

        return warnings

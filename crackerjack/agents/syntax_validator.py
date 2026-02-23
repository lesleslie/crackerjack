import ast
import dataclasses
import logging

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ValidationResult:
    valid: bool
    errors: list[str]

    def __bool__(self) -> bool:
        return self.valid

    def merge(self, other: "ValidationResult") -> "ValidationResult":
        return ValidationResult(
            valid=self.valid and other.valid, errors=self.errors + other.errors
        )


class SyntaxValidator:
    async def validate(self, code: str) -> ValidationResult:
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
        warnings = []

        open_brackets = code.count("(") - code.count(")")
        open_braces = code.count("{") - code.count("}")
        open_brackets_sq = code.count("[") - code.count("]")

        if open_brackets > 0:
            warnings.append(f"{open_brackets} unclosed parenthesis")
        if open_braces > 0:
            warnings.append(f"{open_braces} unclosed braces")
        if open_brackets_sq > 0:
            warnings.append(f"{open_brackets_sq} unclosed square brackets")

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

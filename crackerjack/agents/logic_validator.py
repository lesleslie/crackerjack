import ast
import logging
import re

logger = logging.getLogger(__name__)
from .syntax_validator import ValidationResult


class LogicValidator:
    async def validate(self, code: str) -> ValidationResult:
        errors: list[Any] = []  # type: ignore
        duplicate_errors = self._check_duplicate_definitions(code)
        errors.extend(duplicate_errors)
        import_errors = self._check_import_placement(code)
        errors.extend(import_errors)
        block_errors = self._check_complete_blocks(code)
        errors.extend(block_errors)
        pattern_errors = self._check_anti_patterns(code)
        errors.extend(pattern_errors)
        is_valid = not errors
        if is_valid:
            logger.debug("✅ Logic validation passed")
        else:
            logger.debug(f"❌ Logic validation found {len(errors)} errors")
        return ValidationResult(valid=is_valid, errors=errors)

    def _check_duplicate_definitions(self, code: str) -> list[str]:
        errors: list[Any] = []  # type: ignore
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
            for name, linenos in definitions.items():
                if len(linenos) > 1:
                    locations = ", ".join(str(lineno) for lineno in linenos)
                    errors.append(f"Duplicate definition '{name}' at lines {locations}")
        except SyntaxError:
            pass
        return errors

    def _check_import_placement(self, code: str) -> list[str]:
        errors: list[Any] = []  # type: ignore
        lines = code.split("\n")
        import_lines = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                import_lines.append(i)
        if not import_lines:
            return errors
        first_import = min(import_lines)
        for i in range(first_import):
            line = lines[i].strip()
            if not line or line.startswith(("#", '"""', "'''")):
                continue
            errors.append(
                f"Import statement at line {first_import + 1} should be before code at line {i + 1}"
            )
            break
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
        errors: list[Any] = []  # type: ignore
        lines = code.split("\n")
        block_stack = []
        for i, line in enumerate(lines):
            stripped = line.strip()
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
            if stripped in ("pass", "...") and block_stack:
                start_lineno, start_line = block_stack[-1]
                if i == start_lineno + 1:
                    errors.append(
                        f"Empty block at line {i + 1} (block started at line {start_lineno} with '{start_line}')"
                    )
                    block_stack.pop()
        return errors

    def _check_anti_patterns(self, code: str) -> list[str]:
        errors: list[Any] = []  # type: ignore
        lines = code.split("\n")
        non_future_before_future = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("from __future__ import"):
                continue
            elif (
                stripped
                and (not stripped.startswith("#"))
                and (not stripped.startswith(('"""', "'''")))
            ):
                if not any(
                    kw in stripped for kw in ("import ", "from ", "def ", "class ")
                ):
                    if not non_future_before_future:
                        non_future_before_future = True
        for i, line in enumerate(lines):
            if "todo" in line.lower() or "fixme" in line.lower():
                errors.append(
                    f"Line {i + 1} contains TODO/FIXME - fix may be incomplete"
                )
        path_pattern = '["/][/][a-zA-Z0-9_/]+'
        if re.search(path_pattern, code):
            errors.append("Code contains hardcoded absolute paths")
        return errors

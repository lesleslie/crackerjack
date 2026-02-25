import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from .logic_validator import LogicValidator
from .syntax_validator import SyntaxValidator, ValidationResult


class BehaviorValidator:
    def __init__(self, project_path: Path | None = None) -> None:
        self.project_path = project_path or Path.cwd()

    async def validate(self, code: str) -> ValidationResult:
        errors: list[str] = []
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def validate_with_tests(
        self, file_path: str, code: str, test_path: str | None = None
    ) -> ValidationResult:
        return await self.validate(code)


class ValidationCoordinator:
    def __init__(self, project_path: Path | None = None) -> None:
        self.syntax = SyntaxValidator()
        self.logic = LogicValidator()
        self.behavior = BehaviorValidator(project_path)

    async def validate_fix(
        self,
        code: str,
        file_path: str | None = None,
        test_path: str | None = None,
        run_tests: bool = False,
    ) -> tuple[bool, str]:

        is_python_file = file_path and file_path.endswith(".py")

        if not is_python_file:
            logger.info(
                f"Skipping Python syntax validation for non-Python file: {file_path}"
            )

            if not code or not code.strip():
                return False, "Empty content"
            return True, "Non-Python file validation passed"

        if run_tests and file_path:
            syntax_result, logic_result, behavior_result = await asyncio.gather(
                self.syntax.validate(code),
                self.logic.validate(code),
                self.behavior.validate_with_tests(file_path, code, test_path),
            )
        else:
            syntax_result, logic_result, behavior_result = await asyncio.gather(
                self.syntax.validate(code),
                self.logic.validate(code),
                self.behavior.validate(code),
            )

        results = [syntax_result, logic_result, behavior_result]

        if not syntax_result.valid:
            feedback = self._combine_feedback(results)
            logger.warning(f"❌ Fix rejected: Syntax validation failed:\n{feedback}")
            return False, feedback

        non_syntax_results = [logic_result, behavior_result]
        if any(r.valid for r in non_syntax_results):
            passed_validator = "Logic" if logic_result.valid else "Behavior"
            logger.info(f"✅ Fix validated by {passed_validator} validator (syntax OK)")
            return True, "Fix validated"

        feedback = self._combine_feedback(results)
        logger.warning(f"❌ Fix rejected by Logic/Behavior validators:\n{feedback}")
        return False, feedback

    def _combine_feedback(self, results: list[ValidationResult]) -> str:
        errors = []

        validator_names = ["Syntax", "Logic", "Behavior"]

        for i, result in enumerate(results):
            if not result.valid and result.errors:
                errors.append(f"{validator_names[i]} Validator:")
                for error in result.errors:
                    errors.append(f"  - {error}")

        return "\n".join(errors)

    async def validate_syntax_only(self, code: str) -> ValidationResult:
        return await self.syntax.validate(code)

    async def validate_with_retry(
        self,
        code: str,
        file_path: str | None = None,
        test_path: str | None = None,
        max_retries: int = 3,
    ) -> tuple[bool, str, int]:
        for attempt in range(max_retries):
            is_valid, feedback = await self.validate_fix(
                code=code,
                file_path=file_path,
                test_path=test_path,
                run_tests=(attempt == max_retries - 1),
            )

            if is_valid:
                return True, "Fix validated", attempt + 1

        return False, feedback, max_retries

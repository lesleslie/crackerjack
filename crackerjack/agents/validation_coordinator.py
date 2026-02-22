"""
Coordination of parallel validation for AI-generated fixes.

Runs multiple validators concurrently with permissive logic (apply if ANY passes).
"""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from .logic_validator import LogicValidator
from .syntax_validator import SyntaxValidator, ValidationResult


class BehaviorValidator:
    """
    Placeholder behavior validator for basic checks.

    TODO: Implement full behavior validation with test execution.
    """

    def __init__(self, project_path: Path | None = None) -> None:
        self.project_path = project_path or Path.cwd()

    async def validate(self, code: str) -> ValidationResult:
        """Basic validation without test execution."""
        errors = []
        return ValidationResult(valid=len(errors) == 0, errors=errors)

    async def validate_with_tests(
        self, file_path: str, code: str, test_path: str | None = None
    ) -> ValidationResult:
        """Placeholder for test validation."""
        return await self.validate(code)


class ValidationCoordinator:
    """
    Coordinate parallel validation using multiple validators.

    Validation strategy:
    1. Syntax validation is MANDATORY - must pass for fix to be applied
    2. Logic and Behavior validation use permissive logic (apply if EITHER passes)

    This ensures we never apply broken code while allowing flexibility on
    logic/style issues.
    """

    def __init__(self, project_path: Path | None = None) -> None:
        """
        Initialize validation coordinator.

        Args:
            project_path: Path to project root
        """
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
        """
        Validate fix using all three validators in parallel.

        Args:
            code: Generated code to validate
            file_path: Path to file being modified (for tests)
            test_path: Specific test to run (optional)
            run_tests: Whether to execute tests

        Returns:
            Tuple of (is_valid, feedback_message)
        """
        # Check if this is a Python file - only Python files need syntax validation
        is_python_file = file_path and file_path.endswith(".py")

        # For non-Python files, skip syntax validation and use basic validation
        if not is_python_file:
            logger.info(
                f"Skipping Python syntax validation for non-Python file: {file_path}"
            )
            # Basic validation for non-Python files (check content is not empty)
            if not code or not code.strip():
                return False, "Empty content"
            return True, "Non-Python file validation passed"

        # Run all validators in parallel for Python files
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

        # MANDATORY: Syntax must pass first - this is non-negotiable
        if not syntax_result.valid:
            feedback = self._combine_feedback(results)
            logger.warning(f"❌ Fix rejected: Syntax validation failed:\n{feedback}")
            return False, feedback

        # For logic and behavior: use permissive validation (apply if EITHER passes)
        non_syntax_results = [logic_result, behavior_result]
        if any(r.valid for r in non_syntax_results):
            passed_validator = "Logic" if logic_result.valid else "Behavior"
            logger.info(f"✅ Fix validated by {passed_validator} validator (syntax OK)")
            return True, "Fix validated"

        # Logic and behavior both failed: combine feedback
        feedback = self._combine_feedback(results)
        logger.warning(f"❌ Fix rejected by Logic/Behavior validators:\n{feedback}")
        return False, feedback

    def _combine_feedback(self, results: list[ValidationResult]) -> str:
        """
        Combine error messages from all validators.

        Args:
            results: List of validation results

        Returns:
            Combined error message
        """
        errors = []

        validator_names = ["Syntax", "Logic", "Behavior"]

        for i, result in enumerate(results):
            if not result.valid and result.errors:
                errors.append(f"{validator_names[i]} Validator:")
                for error in result.errors:
                    errors.append(f"  - {error}")

        return "\n".join(errors)

    async def validate_syntax_only(self, code: str) -> ValidationResult:
        """
        Quick syntax-only validation.

        Args:
            code: Code to validate

        Returns:
            Syntax validation result
        """
        return await self.syntax.validate(code)

    async def validate_with_retry(
        self,
        code: str,
        file_path: str | None = None,
        test_path: str | None = None,
        max_retries: int = 3,
    ) -> tuple[bool, str, int]:
        """
        Validate with retry logic.

        Args:
            code: Generated code to validate
            file_path: Path to file being modified
            test_path: Specific test to run
            max_retries: Maximum retry attempts

        Returns:
            Tuple of (is_valid, feedback_message, attempts_made)
        """
        for attempt in range(max_retries):
            is_valid, feedback = await self.validate_fix(
                code=code,
                file_path=file_path,
                test_path=test_path,
                run_tests=(
                    attempt == max_retries - 1
                ),  # Only run tests on last attempt
            )

            if is_valid:
                return True, "Fix validated", attempt + 1

        return False, feedback, max_retries

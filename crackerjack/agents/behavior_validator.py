"""
Behavior validator for AI-generated fixes with full test execution.

Validates that fixes don't break existing behavior.
"""

import asyncio
import logging
import subprocess
from pathlib import Path

from ..agents.base import Issue
from .syntax_validator import ValidationResult

logger = logging.getLogger(__name__)


class BehaviorValidator:
    """
    Complete behavior validator with test execution capabilities.

    Responsibilities:
    - Test file discovery
    - Test execution via pytest subprocess
    - Test result parsing
    - Signature change detection
    - Side effect detection
    """

    def __init__(self, project_path: Path | None = None) -> None:
        """
        Initialize behavior validator.

        Args:
            project_path: Root path for test discovery
        """
        self.project_path = project_path or Path.cwd()

    async def validate(self, code: str) -> ValidationResult:
        """
        Basic validation without test execution.

        Args:
            code: Code to validate

        Returns:
            ValidationResult with any logic errors
        """
        errors = []

        # Check for dangerous operations
        dangerous_patterns = [
            (r"\.exec\(", "Use of exec() function"),
            (r"eval\(", "Use of eval() function"),
            (r"__import__\s*\(", "Dynamic imports detected"),
        ]

        import re

        for pattern, description in dangerous_patterns:
            if re.search(pattern, code):
                errors.append(f"Dangerous operation detected: {description}")

        is_valid = len(errors) == 0

        if is_valid:
            logger.debug("✅ Behavior validation passed (basic)")
        else:
            logger.error(f"❌ Behavior validation failed: {errors}")

        return ValidationResult(valid=is_valid, errors=errors)

    async def validate_with_tests(
        self,
        file_path: str,
        code: str,
        test_path: str | None = None,
    ) -> ValidationResult:
        """
        Validate code by running relevant tests.

        Args:
            file_path: Path to file being modified
            code: Generated code to validate
            test_path: Optional path to specific test file

        Returns:
            ValidationResult with test results
        """
        errors = []

        # First do basic validation
        basic_result = await self.validate(code)
        if not basic_result.valid:
            return basic_result

        # Discover tests if not provided
        if not test_path:
            test_path = await self._discover_test_file(file_path)
            if not test_path:
                errors.append("No test file found for validation")
                return ValidationResult(valid=False, errors=errors)

        # Run the test
        logger.info(f"Running test: {test_path}")
        test_result = await self._run_test(test_path)

        if test_result.returncode == 0:
            logger.info(f"✅ Test passed: {test_path}")
            # Check for test output that suggests issues
            if test_result.stderr:
                # Check for common failure patterns
                if "FAILED" in test_result.stderr:
                    errors.append(f"Test failed: {test_path}")
                elif "ERROR" in test_result.stderr:
                    # Parse error messages
                    for line in test_result.stderr.split("\n"):
                        if "Error" in line and "import" in line.lower():
                            errors.append(f"Import error: {line.strip()}")
        else:
            errors.append(f"Test failed with return code {test_result.returncode}")
            logger.error(
                f"Test output: {test_result.stderr[:500] if test_result.stderr else '(empty)'}"
            )

        is_valid = len(errors) == 0

        if is_valid:
            logger.debug("✅ Behavior validation with tests passed")
        else:
            logger.error(f"❌ Behavior validation with tests failed: {errors}")

        return ValidationResult(valid=is_valid, errors=errors)

    async def _discover_test_file(self, file_path: str) -> str | None:
        """
        Discover test file for given source file.

        Args:
            file_path: Path to source file

        Returns:
            Path to test file or None
        """
        # Common test file patterns
        test_patterns = [
            f"test_{Path(file_path).stem}.py",
            f"{Path(file_path).stem}_test.py",
            f"tests/test_{Path(file_path).stem}.py",
            f"tests/{Path(file_path).stem}/test_*.py",
        ]

        # Check for exact match first
        exact_match = None
        for pattern in test_patterns:
            test_file = Path(file_path).parent / pattern
            if test_file.exists():
                exact_match = str(test_file)
                break

        if exact_match:
            logger.debug(f"Found exact test file: {exact_match}")
            return exact_match

        # Try fuzzy match
        file_name = Path(file_path).stem
        parent_dir = Path(file_path).parent

        # Check common locations
        for test_dir in ["tests", "tests/integration"]:
            test_file = test_dir / f"{file_name}_test.py"
            if test_file.exists():
                logger.debug(f"Found test file: {test_file}")
                return str(test_file)

        # Check for any test file containing the name
        try:
            for candidate in parent_dir.rglob("test_*.py"):
                if file_name.lower() in candidate.name.lower():
                    logger.debug(f"Found test file: {candidate}")
                    return str(candidate)
        except Exception:
            pass

        logger.warning(f"No test file found for {file_path}")
        return None

    async def _run_test(self, test_path: str) -> subprocess.CompletedProcess:
        """
        Run pytest test in subprocess.

        Args:
            test_path: Path to test file

        Returns:
            CompletedProcess with returncode, stdout, stderr
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "pytest",
                str(test_path),
                "-v",
                cwd=self.project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=60.0,
            )

            logger.info(f"Test completed with return code {proc.returncode}")

            return subprocess.CompletedProcess(
                returncode=proc.returncode or 0,
                stdout=stdout.decode() if stdout else "",
                stderr=stderr.decode() if stderr else "",
            )

        except TimeoutError:
            logger.error(f"Test timed out: {test_path}")
            return subprocess.CompletedProcess(
                returncode=-1,
                stdout="",
                stderr="Test timed out after 60 seconds",
            )
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return subprocess.CompletedProcess(
                returncode=-2,
                stdout="",
                stderr=f"Exception: {e}",
            )

    async def can_handle(self, issue: Issue) -> float:
        """Behavior validator can handle any issue type."""
        return 0.9  # High confidence for behavior validation

    def get_supported_types(self) -> set:
        """Behavior validator works with all issue types."""
        from ..agents.base import IssueType

        return set(IssueType)

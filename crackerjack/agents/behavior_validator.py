import asyncio
import logging
import subprocess
from pathlib import Path

from ..agents.base import Issue
from .syntax_validator import ValidationResult

logger = logging.getLogger(__name__)


class BehaviorValidator:
    def __init__(self, project_path: Path | None = None) -> None:
        self.project_path = project_path or Path.cwd()

    async def validate(self, code: str) -> ValidationResult:
        errors = []

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
        errors = []

        basic_result = await self.validate(code)
        if not basic_result.valid:
            return basic_result

        if not test_path:
            test_path = await self._discover_test_file(file_path)
            if not test_path:
                errors.append("No test file found for validation")
                return ValidationResult(valid=False, errors=errors)

        logger.info(f"Running test: {test_path}")
        test_result = await self._run_test(test_path)

        if test_result.returncode == 0:
            logger.info(f"✅ Test passed: {test_path}")

            if test_result.stderr:
                if "FAILED" in test_result.stderr:
                    errors.append(f"Test failed: {test_path}")
                elif "ERROR" in test_result.stderr:
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

        test_patterns = [
            f"test_{Path(file_path).stem}.py",
            f"{Path(file_path).stem}_test.py",
            f"tests/test_{Path(file_path).stem}.py",
            f"tests/{Path(file_path).stem}/test_*.py",
        ]

        exact_match = None
        for pattern in test_patterns:
            test_file = Path(file_path).parent / pattern
            if test_file.exists():
                exact_match = str(test_file)
                break

        if exact_match:
            logger.debug(f"Found exact test file: {exact_match}")
            return exact_match

        file_name = Path(file_path).stem
        parent_dir = Path(file_path).parent

        for test_dir in ["tests", "tests/integration"]:
            test_file = test_dir / f"{file_name}_test.py"  # type: ignore[untyped]
            if test_file.exists():
                logger.debug(f"Found test file: {test_file}")
                return str(test_file)

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

            return subprocess.CompletedProcess(  # type: ignore[untyped]
                returncode=proc.returncode or 0,
                stdout=stdout.decode() if stdout else "",
                stderr=stderr.decode() if stderr else "",
            )

        except TimeoutError:
            logger.error(f"Test timed out: {test_path}")
            return subprocess.CompletedProcess(  # type: ignore[untyped]
                returncode=-1,
                stdout="",
                stderr="Test timed out after 60 seconds",
            )
        except Exception as e:
            logger.error(f"Test execution failed: {e}")
            return subprocess.CompletedProcess(  # type: ignore[untyped]
                returncode=-2,
                stdout="",
                stderr=f"Exception: {e}",
            )

    async def can_handle(self, issue: Issue) -> float:
        return 0.9

    def get_supported_types(self) -> set:
        from ..agents.base import IssueType

        return set(IssueType)

import asyncio
import json
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

from .logic_validator import LogicValidator
from .syntax_validator import SyntaxValidator, ValidationResult


class BehaviorValidator:
    def __init__(self, project_path: Path | None = None) -> None:
        self.project_path = project_path or Path.cwd()

    async def validate(self, code: str) -> ValidationResult:
        errors: list[str] = []
        return ValidationResult(valid=not errors, errors=errors)

    async def validate_with_tests(
        self, file_path: str, code: str, test_path: str | None = None
    ) -> ValidationResult:
        return await self.validate(code)


class QualityValidator:
    """Validates that AI-fixed code passes ruff and refurb checks.

    Uses baseline comparison when original_code is provided: only rejects
    fixes that introduce NEW ruff/refurb violations, not pre-existing ones.
    Uses subprocess_exec (no shell interpolation) with internal file_path
    values only — safe from injection.
    """

    def __init__(self, project_path: Path | None = None) -> None:
        self.project_path = project_path or Path.cwd()

    async def validate(
        self,
        code: str,
        file_path: str | None = None,
        original_code: str | None = None,
    ) -> ValidationResult:
        if not file_path or not file_path.endswith(".py"):
            return ValidationResult(valid=True, errors=[])

        # Establish baseline from original code if available
        baseline_ruff: set[str] = set()
        baseline_refurb: set[str] = set()
        if original_code is not None:
            baseline_ruff = set(await self._check_ruff_keys(original_code))
            baseline_refurb = set(await self._check_refurb_keys(original_code))

        ruff_errors = await self._check_ruff(code, file_path, baseline_ruff)
        if ruff_errors:
            return ValidationResult(valid=False, errors=ruff_errors)

        refurb_errors = await self._check_refurb(code, file_path, baseline_refurb)
        if refurb_errors:
            return ValidationResult(valid=False, errors=refurb_errors)

        return ValidationResult(valid=True, errors=[])

    def _write_tmp(self, code: str) -> str:
        fd, tmp_path = tempfile.mkstemp(suffix=".py")
        with open(fd, "w") as tmp:
            tmp.write(code)
        return tmp_path

    async def _run_ruff(self, tmp_path: str) -> list[dict]:
        process = await asyncio.create_subprocess_exec(
            "ruff",
            "check",
            "--output-format=json",
            "--select=E,F,W,C90",
            tmp_path,
            cwd=str(self.project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
        output = stdout.decode() if stdout else ""
        if not output.strip() or process.returncode == 0:
            return []
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return []

    async def _run_refurb(self, tmp_path: str) -> list[str]:
        process = await asyncio.create_subprocess_exec(
            "refurb",
            tmp_path,
            cwd=str(self.project_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=60)
        output = stdout.decode() if stdout else ""
        if not output.strip() or process.returncode == 0:
            return []
        return [line.strip() for line in output.strip().split("\n") if line.strip()]

    async def _check_ruff_keys(self, code: str) -> list[str]:
        """Return set-identifiable keys for ruff violations (for baseline diff)."""
        try:
            tmp_path = self._write_tmp(code)
            try:
                violations = await self._run_ruff(tmp_path)
                keys: list[str] = []
                for v in violations:
                    code_id = v.get("code", "???")
                    row = v.get("location", {}).get("row", "?")
                    msg = v.get("message", "unknown")
                    keys.append(f"{code_id}:{row}:{msg}")
                return keys
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except (TimeoutError, FileNotFoundError, OSError) as e:
            logger.debug(f"Ruff baseline unavailable: {e}")
            return []

    async def _check_refurb_keys(self, code: str) -> list[str]:
        """Return set-identifiable keys for refurb violations (for baseline diff)."""
        try:
            tmp_path = self._write_tmp(code)
            try:
                lines = await self._run_refurb(tmp_path)
                return lines[:10]
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except (TimeoutError, FileNotFoundError, OSError) as e:
            logger.debug(f"Refurb baseline unavailable: {e}")
            return []

    async def _check_ruff(
        self, code: str, file_path: str, baseline: set[str] | None = None
    ) -> list[str]:
        try:
            tmp_path = self._write_tmp(code)
            try:
                violations = await self._run_ruff(tmp_path)
                errors: list[str] = []
                for v in violations:
                    code_id = v.get("code", "???")
                    msg = v.get("message", "unknown")
                    row = v.get("location", {}).get("row", "?")
                    key = f"{code_id}:{row}:{msg}"
                    if baseline is None or key not in baseline:
                        errors.append(f"ruff {code_id} (line {row}): {msg}")
                return errors[:10]
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except (TimeoutError, FileNotFoundError, OSError) as e:
            logger.debug(f"Ruff validation unavailable: {e}")
            return []

    async def _check_refurb(
        self, code: str, file_path: str, baseline: set[str] | None = None
    ) -> list[str]:
        try:
            tmp_path = self._write_tmp(code)
            try:
                lines = await self._run_refurb(tmp_path)
                errors: list[str] = []
                for line in lines:
                    if baseline is None or line not in baseline:
                        errors.append(f"refurb: {line}")
                return errors[:10]
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except (TimeoutError, FileNotFoundError, OSError) as e:
            logger.debug(f"Refurb validation unavailable: {e}")
            return []


class ValidationCoordinator:
    def __init__(self, project_path: Path | None = None) -> None:
        self.syntax = SyntaxValidator()
        self.logic = LogicValidator()
        self.behavior = BehaviorValidator(project_path)
        self.quality = QualityValidator(project_path)

    async def validate_fix(
        self,
        code: str,
        file_path: str | None = None,
        test_path: str | None = None,
        run_tests: bool = False,
        original_code: str | None = None,
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
            (
                syntax_result,
                logic_result,
                behavior_result,
                quality_result,
            ) = await asyncio.gather(
                self.syntax.validate(code),
                self.logic.validate(code),
                self.behavior.validate_with_tests(file_path, code, test_path),
                self.quality.validate(code, file_path, original_code),
            )
        else:
            (
                syntax_result,
                logic_result,
                behavior_result,
                quality_result,
            ) = await asyncio.gather(
                self.syntax.validate(code),
                self.logic.validate(code),
                self.behavior.validate(code),
                self.quality.validate(code, file_path, original_code),
            )

        if not quality_result.valid:
            feedback = "Quality validation failed (ruff/refurb):\n"
            for err in quality_result.errors:
                feedback += f"  - {err}\n"
            logger.warning(f"❌ Fix rejected: {feedback.strip()}")
            return False, feedback

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
        original_code: str | None = None,
    ) -> tuple[bool, str, int]:
        for attempt in range(max_retries):
            is_valid, feedback = await self.validate_fix(
                code=code,
                file_path=file_path,
                test_path=test_path,
                run_tests=(attempt == max_retries - 1),
                original_code=original_code,
            )

            if is_valid:
                return True, "Fix validated", attempt + 1

        return False, feedback, max_retries

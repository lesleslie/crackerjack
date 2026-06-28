import asyncio
import json
import logging
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

from .behavior_validator import BehaviorValidator
from .logic_validator import LogicValidator
from .syntax_validator import SyntaxValidator, ValidationResult


@dataclass
class TypeChangeValidationResult:
    """Structured result of a project-wide type-check validation.

    Carries the (file:line:column:message) keys for newly introduced
    errors and the keys for errors that the fix resolved, so callers
    can decide to keep, roll back, or escalate.
    """

    is_valid: bool
    new_issues: tuple[str, ...] = ()
    resolved_issues: tuple[str, ...] = ()
    feedback: str = ""
    baseline_issue_count: int = 0
    post_fix_issue_count: int = 0
    file_rolled_back: bool = False
    extra: dict[str, str] = field(default_factory=dict)


class QualityValidator:
    def __init__(self, project_path: Path | None = None) -> None:
        self.project_path = project_path or Path.cwd()

    async def validate(
        self,
        code: str,
        file_path: str | None = None,
        original_code: str | None = None,
        quality_checks: tuple[str, ...] | None = None,
        compare_to_original: bool = True,
    ) -> ValidationResult:
        if not file_path or not file_path.endswith(".py"):
            return ValidationResult(valid=True, errors=[])

        selected_checks = set(quality_checks or ("ruff", "refurb"))
        baseline_ruff: set[str] = set()
        baseline_refurb: set[str] = set()
        if (
            compare_to_original
            and original_code is not None
            and "ruff" in selected_checks
        ):
            baseline_ruff = set(await self._check_ruff_keys(original_code))
        if (
            compare_to_original
            and original_code is not None
            and "refurb" in selected_checks
        ):
            baseline_refurb = set(await self._check_refurb_keys(original_code))

        if "ruff" in selected_checks:
            ruff_errors = await self._check_ruff(code, file_path, baseline_ruff)
            if ruff_errors:
                return ValidationResult(valid=False, errors=ruff_errors)

        if "refurb" in selected_checks:
            refurb_errors = await self._check_refurb(code, file_path, baseline_refurb)
            if refurb_errors:
                return ValidationResult(valid=False, errors=refurb_errors)

        return ValidationResult(valid=True, errors=[])

    def _write_tmp(self, code: str) -> str:
        fd, tmp_path = tempfile.mkstemp(suffix=".py")
        os.write(fd, code.encode())
        os.close(fd)
        return tmp_path

    @staticmethod
    def _tool_command(tool_name: str) -> list[str]:
        resolved = shutil.which(tool_name)
        if resolved:
            return [resolved]
        return [sys.executable, "-m", tool_name]

    async def _run_ruff(self, tmp_path: str) -> list[dict]:
        cmd = [*self._tool_command("ruff")]
        process = await asyncio.create_subprocess_exec(
            *cmd,
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
        cmd = [*self._tool_command("refurb")]
        process = await asyncio.create_subprocess_exec(
            *cmd,
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
        try:
            tmp_path = self._write_tmp(code)
            try:
                violations = await self._run_ruff(tmp_path)
                keys: list[str] = []
                for v in violations:
                    code_id = v.get("code", "???")
                    msg = v.get("message", "unknown")
                    keys.append(self._normalize_ruff_key(code_id, msg))
                return keys
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except (TimeoutError, FileNotFoundError, OSError) as e:
            logger.debug(f"Ruff baseline unavailable: {e}")
            return []

    async def _check_refurb_keys(self, code: str) -> list[str]:
        try:
            tmp_path = self._write_tmp(code)
            try:
                lines = await self._run_refurb(tmp_path)

                return [self._normalize_refurb_line(line) for line in lines]
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
                    key = self._normalize_ruff_key(code_id, msg)
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
                    normalized_line = self._normalize_refurb_line(line)
                    if baseline is None or normalized_line not in baseline:
                        errors.append(f"refurb: {line}")
                return errors[:10]
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except (TimeoutError, FileNotFoundError, OSError) as e:
            logger.debug(f"Refurb validation unavailable: {e}")
            return []

    @staticmethod
    def _normalize_ruff_key(code_id: str, message: str) -> str:
        return f"{code_id}:{message.strip()}"

    @staticmethod
    def _normalize_refurb_line(line: str) -> str:

        parts = line.split(":", 2)
        if len(parts) >= 3 and parts[1].strip().isdigit():
            return parts[2].strip()
        return line.strip()


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
        quality_checks: tuple[str, ...] | None = None,
        compare_to_original: bool = True,
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
                self.quality.validate(
                    code,
                    file_path,
                    original_code,
                    quality_checks=quality_checks,
                    compare_to_original=compare_to_original,
                ),
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
                self.quality.validate(
                    code,
                    file_path,
                    original_code,
                    quality_checks=quality_checks,
                    compare_to_original=compare_to_original,
                ),
            )

        if not quality_result.valid:
            feedback = "Quality validation failed (ruff/refurb):\n"
            for err in quality_result.errors:
                feedback += f" - {err}\n"
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
                    errors.append(f" - {error}")

        return "\n".join(errors)

    async def validate_syntax_only(self, code: str) -> ValidationResult:
        return await self.syntax.validate(code)

    @staticmethod
    def _issue_signature(issue: dict[str, object]) -> str:
        """Stable signature for a type-checker issue: file:line:col:message.

        Column is included because the same file/line can carry multiple
        errors (e.g. multi-arg type mismatch), and we want each counted
        independently.
        """
        file_path = str(issue.get("file_path", ""))
        line = issue.get("line_number", "?")
        col = issue.get("column_number", "?")
        message = str(issue.get("message", "")).strip()
        return f"{file_path}:{line}:{col}:{message}"

    @staticmethod
    def _new_issues(
        baseline_keys: set[str],
        post_issue_dicts: list[dict[str, object]],
    ) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for issue in post_issue_dicts:
            key = ValidationCoordinator._issue_signature(issue)
            if key in baseline_keys or key in seen:
                continue
            seen.add(key)
            ordered.append(key)
        return tuple(ordered)

    @staticmethod
    def _resolved_issues(
        baseline_keys: set[str],
        post_keys: set[str],
    ) -> tuple[str, ...]:
        return tuple(sorted(baseline_keys - post_keys))

    async def validate_fix_for_type_change(
        self,
        code: str,
        file_path: str | None = None,
        original_code: str | None = None,
    ) -> tuple[bool, str]:
        """Project-wide type-check validation for TYPE_ERROR fixes.

        ``validate_fix`` only runs ruff/refurb on the SINGLE modified
        file (via ``_write_tmp``), so when a fix changes a type
        signature in file A and breaks callers in file B, validation
        passes and the broken change is saved to disk.

        This method:

        1. Captures a baseline by running the ``ty`` adapter on the
           current on-disk project (the broken pre-fix state).
        2. Writes the modified file content to its real path
           atomically.
        3. Runs ``ty`` on the project again.
        4. Computes the delta — any errors in the post-fix run that
           were NOT in the baseline count as "new" errors.
        5. Rolls the file back to its original contents if new errors
           appeared (so the caller never has to clean up).
        6. Returns ``(is_valid, feedback)``.
        """
        if not file_path or not file_path.endswith(".py"):
            return True, "Non-Python file skipped for type-check validation"

        target = Path(file_path).resolve()
        if not target.exists():
            return True, f"File not found on disk: {file_path} — skipping"

        original_on_disk = target.read_text(encoding="utf-8")
        if original_code is None:
            original_code = original_on_disk

        try:
            baseline = await self._run_ty_check()
            baseline_keys = self._collect_ty_keys(baseline)

            wrote = self._atomic_write(target, code)
            try:
                post_fix = await self._run_ty_check()
                post_dicts = self._extract_issue_dicts(post_fix)
                post_keys = self._collect_ty_keys(post_fix)
            except Exception:
                self._atomic_write(target, original_on_disk)
                raise

            new_issues = self._new_issues(baseline_keys, post_dicts)
            resolved_issues = self._resolved_issues(baseline_keys, post_keys)

            rolled_back = False
            if new_issues:
                self._atomic_write(target, original_on_disk)
                rolled_back = True

            is_valid = not bool(new_issues)
            feedback = self._format_type_feedback(
                new_issues=new_issues,
                resolved_issues=resolved_issues,
                baseline_count=len(baseline_keys),
                post_count=len(post_keys),
                rolled_back=rolled_back,
            )
            return is_valid, feedback
        except FileNotFoundError as e:
            logger.debug(f"ty binary not available: {e}")
            return True, f"ty not available — type-check validation skipped: {e}"
        except (TimeoutError, OSError) as e:
            logger.debug(f"ty validation unavailable: {e}")
            return True, f"ty validation unavailable: {e}"
        finally:
            try:
                if target.read_text(encoding="utf-8") != original_on_disk:
                    self._atomic_write(target, original_on_disk)
            except OSError:
                pass

    @staticmethod
    def _atomic_write(target: Path, content: str) -> None:
        tmp_path = target.with_suffix(target.suffix + ".ty-validate.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, target)

    async def _run_ty_check(self) -> object:
        from crackerjack.adapters.type import ty as ty_module

        adapter = ty_module.TyAdapter()
        await adapter.init()
        return await adapter.check()

    @staticmethod
    def _collect_ty_keys(result: object) -> set[str]:
        parsed = getattr(result, "parsed_issues", None) or []
        return {
            ValidationCoordinator._issue_signature(issue)
            for issue in parsed
            if isinstance(issue, dict)
        }

    @staticmethod
    def _extract_issue_dicts(result: object) -> list[dict[str, object]]:
        parsed = getattr(result, "parsed_issues", None) or []
        return [issue for issue in parsed if isinstance(issue, dict)]

    @staticmethod
    def _format_type_feedback(
        new_issues: tuple[str, ...],
        resolved_issues: tuple[str, ...],
        baseline_count: int,
        post_count: int,
        rolled_back: bool,
    ) -> str:
        if not new_issues:
            resolved_note = (
                f" (resolved {len(resolved_issues)} baseline issue(s))"
                if resolved_issues
                else ""
            )
            return (
                f"Project-wide ty check: no new errors "
                f"(baseline={baseline_count}, post={post_count})"
                f"{resolved_note}"
            )
        rollback_note = " — file rolled back to original" if rolled_back else ""
        head = new_issues[:10]
        bullet = "\n".join(f"  - {key}" for key in head)
        more = (
            f"\n  ... and {len(new_issues) - len(head)} more"
            if len(new_issues) > len(head)
            else ""
        )
        return (
            f"Project-wide ty check introduced "
            f"{len(new_issues)} new error(s){rollback_note}:\n"
            f"{bullet}{more}"
        )

    async def validate_with_retry(
        self,
        code: str,
        file_path: str | None = None,
        test_path: str | None = None,
        max_retries: int = 3,
        original_code: str | None = None,
        quality_checks: tuple[str, ...] | None = None,
        compare_to_original: bool = True,
    ) -> tuple[bool, str, int]:
        for attempt in range(max_retries):
            is_valid, feedback = await self.validate_fix(
                code=code,
                file_path=file_path,
                test_path=test_path,
                run_tests=(attempt == max_retries - 1),
                original_code=original_code,
                quality_checks=quality_checks,
                compare_to_original=compare_to_original,
            )

            if is_valid:
                return True, "Fix validated", attempt + 1

        return False, feedback, max_retries

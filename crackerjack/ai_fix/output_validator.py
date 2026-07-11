from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


IMPORT_CHECK_TIMEOUT_S: int = 30


RUFF_CHECK_TIMEOUT_S: int = 30


RUFF_RUNTIME_RULES: tuple[str, ...] = ("E9", "F63", "F7", "F82")


_IMPORT_DRIVER = """\
import importlib.util
import sys
import traceback

try:
    spec = importlib.util.spec_from_file_location("_crackerjack_check", {path!r})
    if spec is None or spec.loader is None:
        print("IMPORT_FAILED: could not build spec", file=sys.stderr)
        sys.exit(2)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
except Exception as exc:
    print(type(exc).__name__ + ": " + str(exc), file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
sys.exit(0)
"""


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    reason: str = ""
    skipped: bool = False
    details: list[str] | None = None


def _is_python(path: Path) -> bool:
    return path.suffix == ".py"


def syntax_check(file_path: Path) -> ValidationResult:
    if not _is_python(file_path):
        return ValidationResult(passed=True, skipped=True)

    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationResult(passed=False, reason=f"could not read: {exc}")

    try:
        compile(source, str(file_path), "exec")
    except SyntaxError as exc:
        return ValidationResult(
            passed=False,
            reason=f"syntax error at line {exc.lineno}: {exc.msg}",
        )
    return ValidationResult(passed=True)


def import_check(file_path: Path) -> ValidationResult:
    if not _is_python(file_path):
        return ValidationResult(passed=True, skipped=True)

    driver = _IMPORT_DRIVER.format(path=str(file_path))
    try:
        proc = subprocess.run(
            [sys.executable, "-c", driver],
            capture_output=True,
            text=True,
            timeout=IMPORT_CHECK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(
            passed=False,
            reason=f"import timed out after {IMPORT_CHECK_TIMEOUT_S}s",
        )
    except OSError as exc:
        return ValidationResult(passed=False, reason=f"subprocess failed: {exc}")

    if proc.returncode == 0:
        return ValidationResult(passed=True)

    stderr_text = proc.stderr or proc.stdout or ""
    err_lines = stderr_text.strip().splitlines()
    reason = err_lines[-1] if err_lines else f"import exit {proc.returncode}"
    details: list[str] | None = (
    stderr_text.splitlines() if stderr_text else None
)
    return ValidationResult(passed=False, reason=reason, details=details)


def ruff_sanity_check(file_path: Path) -> ValidationResult:
    if not _is_python(file_path):
        return ValidationResult(passed=True, skipped=True)

    if shutil.which("ruff") is None:
        return ValidationResult(passed=True, skipped=True)

    try:
        proc = subprocess.run(
            [
                "ruff",
                "check",
                "--no-fix",
                "--select",
                ",".join(RUFF_RUNTIME_RULES),
                "--output-format",
                "concise",
                str(file_path),
            ],
            capture_output=True,
            text=True,
            timeout=RUFF_CHECK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(
            passed=False, reason=f"ruff timed out after {RUFF_CHECK_TIMEOUT_S}s"
        )
    except OSError as exc:
        return ValidationResult(passed=False, reason=f"ruff failed: {exc}")

    if proc.returncode == 0:
        return ValidationResult(passed=True)

    summary = (proc.stdout or proc.stderr).strip().splitlines()
    reason = "; ".join(summary[:3]) if summary else f"ruff exit {proc.returncode}"
    return ValidationResult(passed=False, reason=reason)


class OutputValidator:
    def validate(self, file_path: Path) -> ValidationResult:
        for check in (syntax_check, import_check, ruff_sanity_check):
            result = check(file_path)
            if not result.passed:
                logger.warning(
                    f"OutputValidator: {check.__name__} failed for "
                    f"{file_path}: {result.reason}"
                )
                return result
        return ValidationResult(passed=True)


__all__ = [
    "IMPORT_CHECK_TIMEOUT_S",
    "OutputValidator",
    "RUFF_CHECK_TIMEOUT_S",
    "RUFF_RUNTIME_RULES",
    "ValidationResult",
    "import_check",
    "ruff_sanity_check",
    "syntax_check",
]

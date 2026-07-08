"""Post-fix output validation: syntax, import, ruff sanity.

The validator is the gatekeeper between an AI-generated fix and the
working tree. After a fixer reports ``success=True``, the coordinator
runs the modified file through these checks; the first failure
short-circuits and the caller rolls back the working tree.

The three checks in order:

1. **syntax_check** — ``compile()`` rejects broken Python. Cheap,
   deterministic, runs first because a syntax error makes every
   downstream check fail for the wrong reason.
2. **import_check** — runs ``importlib.util.spec_from_file_location``
   in a subprocess to catch ``ImportError`` / ``NameError`` /
   ``SyntaxError`` that ``compile()`` missed (forward refs, runtime
   imports, etc.). Subprocess so a broken fix can't hang the
   coordinator.
3. **ruff_sanity_check** — ``ruff check --select=E9,F63,F7,F82`` for
   runtime / undefined-name issues the import check can miss.
   Skipped (not failed) if ruff isn't installed — the import check
   already covers the common cases.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


# ``import_check`` timeout: a healthy import takes <1s; 30s is
# generous and stops a hung interpreter from blocking the run.
IMPORT_CHECK_TIMEOUT_S: int = 30

# ``ruff check`` timeout: same logic.
RUFF_CHECK_TIMEOUT_S: int = 30

# Rule codes for ruff. These are the subset that catches "the file
# is broken in a way that compile() missed":
#   E9   = runtime errors (e.g. ``TypeError`` at module load)
#   F63  = import-related issues (e.g. ``from x import y`` for missing y)
#   F7   = logic bugs that surface as runtime errors
#   F82  = undefined name (F821 specifically)
RUFF_RUNTIME_RULES: tuple[str, ...] = ("E9", "F63", "F7", "F82")


# Driver script that imports a file by absolute path using
# ``importlib.util``. Runs in a subprocess so a hung import (e.g. an
# infinite loop at module top level) cannot block the coordinator.
#
# We can't simply do ``python -c "import <module>"`` because the
# module name would have to be a valid dotted Python identifier,
# which a filesystem path is not.
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
    """Outcome of a single output check (or the combined chain).

    Attributes:
        passed: True if the check passed (or was skipped). False on
            a real failure.
        reason: Human-readable description of the failure. Empty
            string when passed.
        skipped: True if the check was deliberately bypassed
            (e.g. non-Python file, or ruff not installed). A
            skipped check is still ``passed=True`` because we
            don't want to fail the run on a non-issue.
    """

    passed: bool
    reason: str = ""
    skipped: bool = False


def _is_python(path: Path) -> bool:
    """True for files we should run the Python-specific checks on."""
    return path.suffix == ".py"


def syntax_check(file_path: Path) -> ValidationResult:
    """Validate Python syntax via ``compile()``.

    Non-Python files are skipped (not failed) — the validator
    should not error on ``README.md`` or ``pyproject.toml``.
    """
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
    """Import the file in a subprocess to catch runtime-load errors.

    This catches ``ImportError`` / ``NameError`` / ``SyntaxError``
    that ``compile()`` cannot, e.g. forward references resolved at
    import time, missing third-party modules, or top-level code that
    references an undefined name. The subprocess is bounded by
    :data:`IMPORT_CHECK_TIMEOUT_S` so a hung import cannot block
    the coordinator.
    """
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

    # Last line of stderr is usually the actual exception message
    # (``ImportError: cannot import name 'foo'``); the traceback
    # above it is more verbose than we want for a single-line reason.
    err_lines = (proc.stderr or proc.stdout).strip().splitlines()
    reason = err_lines[-1] if err_lines else f"import exit {proc.returncode}"
    return ValidationResult(passed=False, reason=reason)


def ruff_sanity_check(file_path: Path) -> ValidationResult:
    """Run ``ruff check`` on the file with runtime-failure rules.

    Skipped (not failed) if ruff is not installed. The rule subset
    is E9 / F63 / F7 / F82 — these catch issues that survive
    ``compile()`` and the import check (e.g. undefined names used
    only inside functions, not at module load time).
    """
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
        # ``shutil.which`` already verified ruff is on PATH, so a
        # permission / spawn failure here is a real problem.
        return ValidationResult(passed=False, reason=f"ruff failed: {exc}")

    if proc.returncode == 0:
        return ValidationResult(passed=True)

    # ``ruff check`` returns non-zero when violations are found.
    # The concise output format puts violations on stdout, one per line.
    summary = (proc.stdout or proc.stderr).strip().splitlines()
    reason = "; ".join(summary[:3]) if summary else f"ruff exit {proc.returncode}"
    return ValidationResult(passed=False, reason=reason)


class OutputValidator:
    """Combined validator: runs all three checks, returns first failure.

    The order is fixed (syntax → import → ruff) and is short-circuit:
    a syntax error makes the import check fail for the wrong reason
    (the import would fail on the broken line), so we want to catch
    the syntax error first.

    Construction is parameterless because the checks take only
    ``file_path``. We could add configurability later (custom rule
    sets, custom subprocess timeouts) but YAGNI for now.
    """

    def validate(self, file_path: Path) -> ValidationResult:
        """Run all checks in order; return the first failure (or success)."""
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
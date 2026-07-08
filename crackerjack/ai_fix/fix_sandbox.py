from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from crackerjack.ai_fix.output_validator import OutputValidator

logger = logging.getLogger(__name__)


DEFAULT_SANDBOX_TIMEOUT_S: int = 300


_SANDBOX_ENV_PASSTHROUGH: frozenset[str] = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LC_MESSAGES",
        "TZ",
        "TMPDIR",
        "PYTHONPATH",
        "CRACKERJACK_PROJECT_ROOT",
    }
)


def _build_clean_env() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if key in _SANDBOX_ENV_PASSTHROUGH
    }


@dataclass(frozen=True)
class SandboxResult:
    passed: bool
    modified_content: str | None = None
    reason: str = ""
    duration_s: float = 0.0
    is_validation_failure: bool = False


class FixSandbox:
    def __init__(self, validator: OutputValidator | None = None) -> None:
        self._validator = validator or OutputValidator()

    def run_command(
        self,
        *,
        command: list[str],
        file_path: Path,
        timeout: int = DEFAULT_SANDBOX_TIMEOUT_S,
    ) -> SandboxResult:
        import time

        if not file_path.is_file():
            return SandboxResult(
                passed=False, reason=f"file does not exist: {file_path}"
            )

        try:
            original_content = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            return SandboxResult(passed=False, reason=f"could not read: {exc}")

        with tempfile.TemporaryDirectory(prefix="crackerjack-fix-sandbox-") as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "out.py"
            try:
                target.write_text(original_content, encoding="utf-8")
            except OSError as exc:
                return SandboxResult(passed=False, reason=f"could not seed: {exc}")

            t0 = time.monotonic()
            try:
                proc = subprocess.run(
                    command,
                    cwd=str(tmp_path),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=_build_clean_env(),
                )
            except subprocess.TimeoutExpired:
                return SandboxResult(
                    passed=False,
                    reason=f"subprocess timeout after {timeout}s",
                    duration_s=time.monotonic() - t0,
                )
            except OSError as exc:
                return SandboxResult(
                    passed=False,
                    reason=f"subprocess failed: {exc}",
                    duration_s=time.monotonic() - t0,
                )

            duration = time.monotonic() - t0

            if proc.returncode != 0:
                last_err = (proc.stderr or proc.stdout).strip().splitlines()
                reason = last_err[-1] if last_err else f"exit code {proc.returncode}"
                return SandboxResult(
                    passed=False,
                    reason=f"subprocess {reason}",
                    duration_s=duration,
                )

            if not target.exists():
                return SandboxResult(
                    passed=False,
                    reason="subprocess deleted the target file",
                    duration_s=duration,
                )

            validation = self._validator.validate(target)
            if not validation.passed:
                return SandboxResult(
                    passed=False,
                    reason=validation.reason,
                    duration_s=duration,
                    is_validation_failure=True,
                )

            try:
                modified = target.read_text(encoding="utf-8")
            except OSError as exc:
                return SandboxResult(
                    passed=False,
                    reason=f"could not read result: {exc}",
                    duration_s=duration,
                )

            return SandboxResult(
                passed=True,
                modified_content=modified,
                duration_s=duration,
            )


__all__ = [
    "DEFAULT_SANDBOX_TIMEOUT_S",
    "FixSandbox",
    "SandboxResult",
]

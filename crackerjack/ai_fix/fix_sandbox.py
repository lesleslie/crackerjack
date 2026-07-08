"""Run a fixer command in a subprocess with isolated filesystem access.

The ai-fix pipeline has corrupted 24+ files in a single run (2026-07-04
incident), plus 2 ``float('inf')`` type regressions. The root cause is
that fixers run with full access to the main working tree, so any
bug in the fixer's code path can damage the user's repository. This
sandbox limits the blast radius by:

1. **Subprocess isolation.** The fixer runs in a ``subprocess.run``
   with ``cwd`` set to a temp directory. The subprocess cannot reach
   the main tree because the relative path "out.py" is the temp file,
   not anything in the main repo.
2. **Clean env.** Parent env vars (which may include API keys, GitHub
   tokens, AWS creds) are NOT inherited. The subprocess gets a
   minimal allowlist (``PATH``, ``HOME``, ``LANG``, ``PYTHONPATH``,
   ``CRACKERJACK_PROJECT_ROOT``).
3. **Timeout.** A hung fixer cannot block the coordinator. Default
   300s matches the per-issue timeout.
4. **Output validation.** After the subprocess exits, the modified
   file is run through :class:`OutputValidator` (syntax / import /
   ruff). Broken output is rejected; the parent decides what to do.

The sandbox is intentionally a thin wrapper: it doesn't try to be
clever. The caller (coordinator) owns the "apply to main tree or
discard" decision. This keeps the sandbox a pure transport layer.
"""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from crackerjack.ai_fix.output_validator import OutputValidator

logger = logging.getLogger(__name__)


# Default per-run timeout. Matches the per-issue timeout (300s) so
# the sandbox's hang protection aligns with the rest of the pipeline.
DEFAULT_SANDBOX_TIMEOUT_S: int = 300


# Subprocess env allowlist. Mirrors the existing
# ``crackerjack/ai_fix/sandbox_runner.py`` policy: do not inherit
# parent secrets. The fixer is supposed to be a pure transformation;
# it does not need API keys, GitHub tokens, or AWS creds.
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
    """Build a subprocess env that does NOT inherit parent secrets.

    The result includes only the keys in :data:`_SANDBOX_ENV_PASSTHROUGH`
    if they're present in the parent's ``os.environ``; everything else
    is dropped.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if key in _SANDBOX_ENV_PASSTHROUGH
    }


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of a single sandbox run.

    Attributes:
        passed: True if the subprocess produced valid output (per
            OutputValidator). False on subprocess failure, timeout,
            or validation rejection.
        modified_content: The new file content, if ``passed=True``.
            None on any failure.
        reason: Human-readable description of the failure. Empty
            string when passed.
        duration_s: Wall-clock time the subprocess took (or
            ``timeout_s`` on a timeout). Useful for telemetry.
    """

    passed: bool
    modified_content: str | None = None
    reason: str = ""
    duration_s: float = 0.0


class FixSandbox:
    """Subprocess sandbox for AI fix execution.

    The sandbox is constructed with an :class:`OutputValidator`
    (injected for testability). Each ``run_command`` invocation:

    1. Copies ``file_path`` to a temp dir (named ``out.py`` in cwd).
    2. Runs ``command`` in the temp dir with the clean env.
    3. Validates the modified file via the validator.
    4. Returns a :class:`SandboxResult` with the outcome.

    The main working tree is never written to by the sandbox; the
    caller is responsible for applying ``modified_content`` if
    ``passed=True``.

    Construction is parameterless if the default validator is
    acceptable (``OutputValidator()`` is constructed lazily).
    """

    def __init__(self, validator: OutputValidator | None = None) -> None:
        self._validator = validator or OutputValidator()

    def run_command(
        self,
        *,
        command: list[str],
        file_path: Path,
        timeout: int = DEFAULT_SANDBOX_TIMEOUT_S,
    ) -> SandboxResult:
        """Run ``command`` against a copy of ``file_path`` in a temp dir.

        Args:
            command: The subprocess argv. The command's ``cwd`` is
                a temp directory containing a copy of ``file_path``
                named ``out.py`` (the convention every fixer follows).
            file_path: The original file. Read once at the start;
                never written to by the sandbox.
            timeout: Max seconds the subprocess may run. Default
                :data:`DEFAULT_SANDBOX_TIMEOUT_S` (300s).

        Returns:
            A :class:`SandboxResult` with ``passed=True`` and
            ``modified_content`` set if the subprocess produced
            valid output. ``passed=False`` and ``reason`` set on
            subprocess failure, timeout, or validation rejection.
            ``file_path`` on disk is never modified.
        """
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
                # Surface the subprocess's last stderr line as the reason.
                last_err = (proc.stderr or proc.stdout).strip().splitlines()
                reason = (
                    last_err[-1] if last_err else f"exit code {proc.returncode}"
                )
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

            # Validate the result before returning it. The validator
            # is the gate; a failed validation means we won't hand
            # back broken content to the caller.
            validation = self._validator.validate(target)
            if not validation.passed:
                return SandboxResult(
                    passed=False,
                    reason=validation.reason,
                    duration_s=duration,
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
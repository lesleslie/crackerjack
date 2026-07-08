
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from crackerjack.ai_fix.promotion_pipeline import SandboxResult

logger = logging.getLogger(__name__)


DEFAULT_SANDBOX_TIMEOUT_S: int = 60


SAFE_ENV_PASSTHROUGH: frozenset[str] = frozenset(
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


def _build_clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    safe: dict[str, str] = {
        key: value for key, value in os.environ.items() if key in SAFE_ENV_PASSTHROUGH
    }
    if extra:
        safe.update(extra)
    return safe


def _build_test_driver(signature: str, test_script: str | None) -> str:
    default_test_script = (
        "# Default test: the fixer must define an apply() function.\n"
        'fixer = __import__("crackerjack_ai_fix_fixer")\n'
        "assert callable(getattr(fixer, 'apply', None)), (\n"
        ' "fixer module must define apply()"\n'
        ")\n"
        "# Smoke-call apply with a placeholder; the fixer's own\n"
        "# argument validation should reject this without crashing.\n"
        "try:\n"
        " fixer.apply(signature=__SIGNATURE__, issue=None)\n"
        "except (TypeError, ValueError, AttributeError):\n"
        " pass # expected: the fixer is allowed to reject unknown input\n"
    )
    body = test_script if test_script is not None else default_test_script


    return (
        "import sys\n"
        "import os\n"
        "sys.path.insert(0, os.getcwd())\n"
        f"__SIGNATURE__ = {signature!r}\n"
        f"{body}"
        'print("SANDBOX_OK")\n'
    )


class SubprocessSandboxRunner:

    def __init__(
        self,
        *,
        timeout_s: int = DEFAULT_SANDBOX_TIMEOUT_S,
        python_executable: str | None = None,
    ) -> None:
        self._timeout_s = timeout_s
        self._python = python_executable or sys.executable

    def run_tests(
        self,
        *,
        fixer_source: str,
        signature: str,
        project_root: Path,
        test_script: str | None = None,
    ) -> SandboxResult:
        import time

        driver_source = _build_test_driver(signature, test_script)
        with tempfile.TemporaryDirectory(prefix="crackerjack-sandbox-") as tmp:
            tmp_path = Path(tmp)
            fixer_path = tmp_path / "crackerjack_ai_fix_fixer.py"
            driver_path = tmp_path / "_driver.py"
            fixer_path.write_text(fixer_source, encoding="utf-8")
            driver_path.write_text(driver_source, encoding="utf-8")

            t0 = time.monotonic()
            try:
                proc = subprocess.run(
                    [self._python, str(driver_path), str(fixer_path)],
                    cwd=str(project_root),
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_s,
                    env=_build_clean_env({"PYTHONPATH": str(tmp_path)}),
                )
            except subprocess.TimeoutExpired as exc:
                return SandboxResult(
                    passed=False,
                    stdout=exc.stdout or "",
                    stderr=f"timeout after {self._timeout_s}s",
                    duration_s=time.monotonic() - t0,
                )
            except OSError as exc:
                return SandboxResult(
                    passed=False,
                    stdout="",
                    stderr=f"subprocess failed: {exc}",
                    duration_s=time.monotonic() - t0,
                )

            passed = proc.returncode == 0 and "SANDBOX_OK" in proc.stdout
            return SandboxResult(
                passed=passed,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_s=time.monotonic() - t0,
            )


__all__ = ["DEFAULT_SANDBOX_TIMEOUT_S", "SubprocessSandboxRunner"]

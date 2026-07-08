"""Real :class:`SandboxRunner` implementation: subprocess + pytest.

The sandbox runs the generated fixer against the skill's recorded
test cases. We use a subprocess for two reasons:

1. **Isolation.** A generated fixer that imports a broken module
   can't take down the parent crackerjack process. A timeout or
   a segfault in the fixer is contained.
2. **Clean state.** Each run starts with a fresh Python process;
   the fixer's import side effects don't leak between attempts.

The contract is "the fixer reproduces the skill's behaviour on the
recorded test cases." For the ai-fix promotion flow, the test
cases are a small pytest-style script that imports the fixer,
invokes its main function with the skill's recorded input, and
asserts the recorded output.

The runner is intentionally simple — it doesn't try to be clever
about the test cases. It just runs them and reports pass/fail.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from crackerjack.ai_fix.promotion_pipeline import SandboxResult

logger = logging.getLogger(__name__)


# Default per-run timeout for the sandbox. 60s is generous for a
# single Python import + small test script; longer than that and
# the generated fixer is almost certainly stuck in a loop.
DEFAULT_SANDBOX_TIMEOUT_S: int = 60


def _build_test_driver(signature: str, test_script: str | None) -> str:
    """Build a Python script that loads the fixer and runs the tests.

    The driver is a tiny bootstrap. The real test logic lives in
    ``test_script`` (a string the caller provides) or, if absent,
    in a default that just imports the fixer and asserts the
    ``apply`` symbol exists. The signature is exposed as a constant
    so the test_script can reference it.
    """
    default_test_script = (
        "# Default test: the fixer must define an apply() function.\n"
        'fixer = __import__("crackerjack_ai_fix_fixer")\n'
        "assert callable(getattr(fixer, 'apply', None)), (\n"
        '    "fixer module must define apply()"\n'
        ")\n"
        "# Smoke-call apply with a placeholder; the fixer's own\n"
        "# argument validation should reject this without crashing.\n"
        "try:\n"
        "    fixer.apply(signature=__SIGNATURE__, issue=None)\n"
        "except (TypeError, ValueError, AttributeError):\n"
        "    pass  # expected: the fixer is allowed to reject unknown input\n"
    )
    body = test_script if test_script is not None else default_test_script
    # NOTE: do not use a triple-quoted indented template here. Any
    # leading whitespace on the source lines would become a Python
    # IndentationError once the string is written to a file and
    # executed. Build the driver as a single concatenated string with
    # no leading whitespace on any line.
    return (
        "import sys\n"
        "import os\n"
        "sys.path.insert(0, os.getcwd())\n"
        f"__SIGNATURE__ = {signature!r}\n"
        f"{body}"
        'print("SANDBOX_OK")\n'
    )


class SubprocessSandboxRunner:
    """Run the generated fixer in a subprocess; report pass/fail.

    The runner is a real implementation of the :class:`SandboxRunner`
    protocol. It writes the fixer's source to a temp file, the test
    driver to another, then runs ``python test_driver.py fixer.py``
    in a subprocess. Pass = exit 0 + "SANDBOX_OK" in stdout.
    """

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
                    env={**os.environ, "PYTHONPATH": str(tmp_path)},
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

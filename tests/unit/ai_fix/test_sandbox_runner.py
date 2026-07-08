"""Tests for :class:`SubprocessSandboxRunner` (PR 8 of 2026-07-07 ai-fix design).

The runner is real: it spawns a Python subprocess, imports the
generated fixer, and runs a test driver. Tests in this file spawn
real subprocesses, so the suite requires the crackerjack venv to
have a working Python (which is true in any normal environment).
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from crackerjack.ai_fix.promotion_pipeline import SandboxResult
from crackerjack.ai_fix.sandbox_runner import (
    DEFAULT_SANDBOX_TIMEOUT_S,
    SubprocessSandboxRunner,
    _build_test_driver,
)


# ---------------------------------------------------------------------------
# 1. Pure helper: _build_test_driver
# ---------------------------------------------------------------------------


class TestBuildTestDriver:
    """The driver is a string; tests assert on its shape, not its execution."""

    def test_includes_signature_constant(self) -> None:
        driver = _build_test_driver("abc123", test_script=None)
        assert "__SIGNATURE__ = 'abc123'" in driver

    def test_default_test_script_asserts_apply_exists(self) -> None:
        driver = _build_test_driver("sig", test_script=None)
        # The default script imports the fixer and asserts apply() exists.
        assert "def apply" in driver or "callable(getattr" in driver
        assert "SANDBOX_OK" in driver

    def test_custom_test_script_is_included_verbatim(self) -> None:
        script = "print('custom test ran')\nassert 1 + 1 == 2\n"
        driver = _build_test_driver("sig", test_script=script)
        assert "custom test ran" in driver
        assert "1 + 1 == 2" in driver

    def test_signature_is_escaped(self) -> None:
        """A signature with single quotes doesn't break the driver."""
        driver = _build_test_driver("o'malley", test_script=None)
        # Python's repr() escapes single quotes safely.
        assert "__SIGNATURE__ = \"o'malley\"" in driver or "__SIGNATURE__ = 'o\\'malley'" in driver


# ---------------------------------------------------------------------------
# 2. Real subprocess: success path
# ---------------------------------------------------------------------------


class TestSubprocessSuccess:
    """A fixer that defines ``apply()`` and survives a smoke call passes."""

    def test_passing_fixer(self, tmp_path: Path) -> None:
        runner = SubprocessSandboxRunner(timeout_s=10)
        fixer_source = textwrap.dedent(
            """
            def apply(signature, issue):
                return {"success": True, "files_modified": []}
            """
        )
        result = runner.run_tests(
            fixer_source=fixer_source,
            signature="abc123",
            project_root=tmp_path,
        )
        assert isinstance(result, SandboxResult)
        assert result.passed is True
        assert "SANDBOX_OK" in result.stdout


# ---------------------------------------------------------------------------
# 3. Real subprocess: failure path
# ---------------------------------------------------------------------------


class TestSubprocessFailure:
    """A fixer that crashes or lacks ``apply()`` fails the sandbox."""

    def test_fixer_with_syntax_error(self, tmp_path: Path) -> None:
        runner = SubprocessSandboxRunner(timeout_s=10)
        # Intentionally broken Python: missing colon.
        fixer_source = "def apply(signature, issue)\n    return {}\n"
        result = runner.run_tests(
            fixer_source=fixer_source,
            signature="abc123",
            project_root=tmp_path,
        )
        assert result.passed is False
        # SyntaxError should appear in stderr.
        assert "SyntaxError" in result.stderr or "SANDBOX_OK" not in result.stdout

    def test_fixer_missing_apply(self, tmp_path: Path) -> None:
        runner = SubprocessSandboxRunner(timeout_s=10)
        fixer_source = "x = 1\n"  # No apply() defined
        result = runner.run_tests(
            fixer_source=fixer_source,
            signature="abc123",
            project_root=tmp_path,
        )
        assert result.passed is False


# ---------------------------------------------------------------------------
# 4. Timeout
# ---------------------------------------------------------------------------


class TestSubprocessTimeout:
    """A fixer that loops forever is killed by the timeout."""

    @pytest.mark.skipif(
        sys.platform == "win32", reason="timeout semantics differ on Windows"
    )
    def test_timeout_kills_long_running_fixer(self, tmp_path: Path) -> None:
        # timeout_s=1 is enough to kill an infinite loop.
        runner = SubprocessSandboxRunner(timeout_s=1)
        fixer_source = textwrap.dedent(
            """
            import time
            def apply(signature, issue):
                time.sleep(60)
                return {}
            """
        )
        result = runner.run_tests(
            fixer_source=fixer_source,
            signature="abc123",
            project_root=tmp_path,
        )
        assert result.passed is False
        assert "timeout" in result.stderr.lower()


# ---------------------------------------------------------------------------
# 5. Default timeout constant
# ---------------------------------------------------------------------------


class TestDefaults:
    """The default timeout is the design value (60s)."""

    def test_default_timeout_s_is_60(self) -> None:
        assert DEFAULT_SANDBOX_TIMEOUT_S == 60

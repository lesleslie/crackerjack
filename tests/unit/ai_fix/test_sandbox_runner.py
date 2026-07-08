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


# ---------------------------------------------------------------------------
# 6. Env isolation (defense against secret leak from parent process)
# ---------------------------------------------------------------------------


class TestEnvIsolation:
    """The sandbox must NOT inherit the parent env (no secret leak)."""

    def test_clean_env_does_not_inherit_secrets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A secret set in the parent must not appear in the subprocess env."""
        from crackerjack.ai_fix.sandbox_runner import _build_clean_env

        monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret_should_not_leak")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws_secret_should_not_leak")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk_secret_should_not_leak")
        monkeypatch.setenv("PATH", "/usr/bin:/bin")  # this one IS allowed
        monkeypatch.setenv("HOME", "/home/user")  # this one IS allowed

        env = _build_clean_env()

        # None of the secret-style vars should be in the clean env.
        assert "GITHUB_TOKEN" not in env
        assert "AWS_SECRET_ACCESS_KEY" not in env
        assert "ANTHROPIC_API_KEY" not in env

        # The allowlisted vars should be passed through.
        assert env.get("PATH") == "/usr/bin:/bin"
        assert env.get("HOME") == "/home/user"

    def test_extra_overrides_allowlist(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The ``extra`` arg overrides any existing values."""
        from crackerjack.ai_fix.sandbox_runner import _build_clean_env

        monkeypatch.setenv("PATH", "/usr/bin")
        env = _build_clean_env({"PATH": "/custom/bin"})
        assert env["PATH"] == "/custom/bin"

    def test_extra_can_add_arbitrary_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``extra`` can pass keys that aren't on the allowlist (caller's choice)."""
        from crackerjack.ai_fix.sandbox_runner import _build_clean_env

        env = _build_clean_env({"TMPDIR": "/scratch"})
        assert env["TMPDIR"] == "/scratch"

    def test_safe_env_passthrough_does_not_include_secrets(self) -> None:
        """The allowlist itself must not include any secret-named vars."""
        from crackerjack.ai_fix.sandbox_runner import SAFE_ENV_PASSTHROUGH

        # Defensive: even if someone adds to the allowlist, secrets
        # like GITHUB_TOKEN, AWS_*, ANTHROPIC_* must never appear.
        for key in SAFE_ENV_PASSTHROUGH:
            upper = key.upper()
            assert "SECRET" not in upper, f"allowlist contains SECRET: {key}"
            assert "TOKEN" not in upper, f"allowlist contains TOKEN: {key}"
            assert "KEY" not in upper or "PATH" in upper, f"allowlist contains KEY: {key}"

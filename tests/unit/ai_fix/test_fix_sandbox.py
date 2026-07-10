"""Tests for the FixSandbox — subprocess-with-restricted-FS layer.

The sandbox runs a fixer command in a temp directory with a copy of
the target file. The subprocess cannot reach the main working tree
because its ``cwd`` is the temp dir. After the subprocess exits,
the sandbox validates the modified file via ``OutputValidator`` and
returns the result + the new content. The parent (coordinator)
decides whether to apply the result to the main tree.

Why a subprocess rather than a Python callback? Two reasons:

1. **Filesystem isolation.** The subprocess's ``cwd`` is a temp dir;
   even if the subprocess tries to write to ``/Users/.../crackerjack/``,
   the path doesn't exist (or is the temp dir). A Python callback would
   have full filesystem access by design.
2. **Hang protection.** A subprocess can be killed by ``timeout=``;
   a hung Python callback inside the coordinator would block the
   entire run.
"""

from __future__ import annotations

import os
import sys
import textwrap
from pathlib import Path

from crackerjack.ai_fix.fix_sandbox import (
    DEFAULT_SANDBOX_TIMEOUT_S,
    FixSandbox,
    SandboxResult,
)
from crackerjack.ai_fix.output_validator import OutputValidator


def _echo_command(content: str) -> list[str]:
    """A trivial subprocess that writes ``content`` to a file in cwd.

    Used by tests to drive the sandbox without depending on the real
    AI fix pipeline. The script writes to ``out.py`` (the convention
    the sandbox expects) and exits 0.
    """
    return [
        sys.executable,
        "-c",
        textwrap.dedent(
            f"""
            import sys
            with open("out.py", "w", encoding="utf-8") as f:
                f.write({content!r})
            sys.exit(0)
            """
        ),
    ]


def _broken_python_command() -> list[str]:
    """A subprocess that writes syntactically-broken Python to out.py."""
    return [
        sys.executable,
        "-c",
        "open('out.py', 'w').write('def x(:\\n')",
    ]


def _exit_nonzero_command() -> list[str]:
    return [sys.executable, "-c", "import sys; sys.exit(1)"]


def _sleep_command(seconds: int) -> list[str]:
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


class TestFixSandbox:
    def test_default_timeout_is_300(self) -> None:
        """The default timeout is 300s, matching the per-issue timeout."""
        assert DEFAULT_SANDBOX_TIMEOUT_S == 300

    def test_sandbox_passes_when_subprocess_produces_valid_python(
        self, tmp_path: Path
    ) -> None:
        """Subprocess writes valid Python to out.py → passed=True."""
        original = tmp_path / "out.py"
        original.write_text("x = 1\n", encoding="utf-8")
        sandbox = FixSandbox(validator=OutputValidator())

        result = sandbox.run_command(
            command=_echo_command("x = 42\n"),
            file_path=original,
            timeout=30,
        )

        assert isinstance(result, SandboxResult)
        assert result.passed is True
        assert result.modified_content == "x = 42\n"
        assert result.reason == ""

    def test_sandbox_rejects_broken_python(self, tmp_path: Path) -> None:
        """Subprocess writes broken Python → passed=False with reason."""
        original = tmp_path / "out.py"
        original.write_text("x = 1\n", encoding="utf-8")
        sandbox = FixSandbox(validator=OutputValidator())

        result = sandbox.run_command(
            command=_broken_python_command(),
            file_path=original,
            timeout=30,
        )

        assert result.passed is False
        assert "syntax" in result.reason.lower()

    def test_sandbox_rejects_nonzero_exit(self, tmp_path: Path) -> None:
        original = tmp_path / "out.py"
        original.write_text("x = 1\n", encoding="utf-8")
        sandbox = FixSandbox(validator=OutputValidator())

        result = sandbox.run_command(
            command=_exit_nonzero_command(),
            file_path=original,
            timeout=30,
        )

        assert result.passed is False
        assert "exit" in result.reason.lower() or "failed" in result.reason.lower()

    def test_sandbox_times_out_on_hang(self, tmp_path: Path) -> None:
        original = tmp_path / "out.py"
        original.write_text("x = 1\n", encoding="utf-8")
        sandbox = FixSandbox(validator=OutputValidator())

        result = sandbox.run_command(
            command=_sleep_command(5),
            file_path=original,
            timeout=1,
        )

        assert result.passed is False
        assert "timeout" in result.reason.lower()

    def test_sandbox_does_not_modify_main_tree_on_failure(
        self, tmp_path: Path
    ) -> None:
        """When the subprocess produces broken code, the original file is untouched."""
        original = tmp_path / "out.py"
        original_content = "x = 1\n"
        original.write_text(original_content, encoding="utf-8")
        sandbox = FixSandbox(validator=OutputValidator())

        sandbox.run_command(
            command=_broken_python_command(),
            file_path=original,
            timeout=30,
        )

        # The main file is still the original content.
        assert original.read_text(encoding="utf-8") == original_content

    def test_sandbox_returns_modified_content_on_success(
        self, tmp_path: Path
    ) -> None:
        """The ``modified_content`` field carries the subprocess's output."""
        original = tmp_path / "out.py"
        original.write_text("x = 1\n", encoding="utf-8")
        sandbox = FixSandbox(validator=OutputValidator())

        result = sandbox.run_command(
            command=_echo_command("# ai-fixed\n"),
            file_path=original,
            timeout=30,
        )

        assert result.passed is True
        assert result.modified_content == "# ai-fixed\n"

    def test_sandbox_uses_clean_env(self, tmp_path: Path) -> None:
        """Parent env vars are NOT in the subprocess env (secrets stay safe).

        We set a fake "secret" in the parent env, then have the subprocess
        assert it's NOT present.
        """
        original = tmp_path / "out.py"
        original.write_text("x = 1\n", encoding="utf-8")
        sandbox = FixSandbox(validator=OutputValidator())

        secret_var = "CRACKERJACK_TEST_SECRET_DO_NOT_USE"
        os.environ[secret_var] = "should-not-leak"
        try:
            # The subprocess writes its observed env to out.py.
            cmd = [
                sys.executable,
                "-c",
                (
                    "import os, json\n"
                    f"observed = os.environ.get({secret_var!r})\n"
                    "with open('out.py', 'w') as f:\n"
                    "    f.write('observed=' + repr(observed) + '\\n')\n"
                ),
            ]
            result = sandbox.run_command(
                command=cmd,
                file_path=original,
                timeout=30,
            )
            assert result.passed is True
            # The subprocess should NOT have seen the secret.
            assert "observed=None" in (result.modified_content or "")
        finally:
            del os.environ[secret_var]

    def test_sandbox_constructor_takes_validator(self) -> None:
        """The constructor accepts an OutputValidator (DI for testability)."""
        sandbox = FixSandbox(validator=OutputValidator())
        assert sandbox is not None

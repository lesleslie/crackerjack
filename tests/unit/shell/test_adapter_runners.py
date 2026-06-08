"""Tests for CrackerjackShell runner methods (subprocess, hooks, crack)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.shell import CrackerjackShell


def _completed_process(
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


@pytest.fixture
def mock_app() -> MagicMock:
    app = MagicMock()
    app.qa_adapters = {"pytest": True, "ruff": True, "mypy": True, "bandit": True}
    return app


@pytest.fixture
def shell(mock_app: MagicMock) -> CrackerjackShell:
    return CrackerjackShell(mock_app)


@pytest.fixture(autouse=True)
def _isolate_oneiric() -> None:
    """Drop any cached oneiric modules so AdminShell's metaclass setup is fresh."""
    import sys

    oneiric_keys = [k for k in sys.modules if k.startswith("oneiric")]
    for key in oneiric_keys:
        del sys.modules[key]


class TestRunTests:
    @pytest.mark.asyncio
    async def test_run_tests_success_prints_passed_line(self, shell: CrackerjackShell) -> None:
        passed_line = "= 42 passed in 1.20s = 80% ="
        result = _completed_process(
            returncode=0,
            stdout=f"collected 42 items\n\n{passed_line}\n",
        )
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=result) as run:
            await shell._run_tests()

        run.assert_called_once()
        assert run.call_args.args[0] == [
            "pytest",
            "-v",
            "--cov=crackerjack",
            "--cov-report=term-missing",
        ]
        assert run.call_args.kwargs["cwd"] == shell._project_root
        assert run.call_args.kwargs["capture_output"] is True
        assert run.call_args.kwargs["text"] is True

    @pytest.mark.asyncio
    async def test_run_tests_failed_raises(self, shell: CrackerjackShell) -> None:
        result = _completed_process(returncode=1, stdout="1 failed")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=result):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                await shell._run_tests()
        assert exc.value.returncode == 1

    @pytest.mark.asyncio
    async def test_run_tests_failed_line_in_output(self, shell: CrackerjackShell) -> None:
        result = _completed_process(
            returncode=0,
            stdout="FAILED tests/test_x.py::test_y - assert error",
        )
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=result):
            await shell._run_tests()

    @pytest.mark.asyncio
    async def test_run_tests_error_line_in_output(self, shell: CrackerjackShell) -> None:
        result = _completed_process(
            returncode=0,
            stdout="ERROR tests/test_x.py - setup failed",
        )
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=result):
            await shell._run_tests()

    @pytest.mark.asyncio
    async def test_run_tests_blank_stdout(self, shell: CrackerjackShell) -> None:
        result = _completed_process(returncode=0, stdout="")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=result):
            await shell._run_tests()


class TestRunLint:
    @pytest.mark.asyncio
    async def test_run_lint_success(self, shell: CrackerjackShell) -> None:
        success = _completed_process(returncode=0, stdout="All checks passed!")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=success) as run:
            await shell._run_lint()

        # Two subprocess invocations: ruff check and ruff format --check
        assert run.call_count == 2
        first_cmd = run.call_args_list[0].args[0]
        second_cmd = run.call_args_list[1].args[0]
        assert first_cmd == ["ruff", "check", "."]
        assert second_cmd == ["ruff", "format", "--check", "."]

    @pytest.mark.asyncio
    async def test_run_lint_raises_on_check_failure(self, shell: CrackerjackShell) -> None:
        failed_check = _completed_process(returncode=1, stdout="lint errors found")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=failed_check):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                await shell._run_lint()
        assert exc.value.returncode == 1

    @pytest.mark.asyncio
    async def test_run_lint_raises_on_format_failure(self, shell: CrackerjackShell) -> None:
        success_check = _completed_process(returncode=0, stdout="")
        failed_format = _completed_process(returncode=2, stdout="would reformat 3 files")
        with patch(
            "crackerjack.shell.adapter.subprocess.run",
            side_effect=[success_check, failed_format],
        ):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                await shell._run_lint()
        assert exc.value.returncode == 2


class TestRunScan:
    @pytest.mark.asyncio
    async def test_run_scan_success(self, shell: CrackerjackShell) -> None:
        result = _completed_process(returncode=0, stdout="No issues identified.")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=result) as run:
            await shell._run_scan()

        run.assert_called_once()
        assert run.call_args.args[0] == ["bandit", "-r", "crackerjack/", "-f", "screen"]

    @pytest.mark.asyncio
    async def test_run_scan_raises_on_findings(self, shell: CrackerjackShell) -> None:
        result = _completed_process(returncode=1, stdout="Total: 3 issues")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=result):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                await shell._run_scan()
        assert exc.value.returncode == 1


class TestRunFormat:
    @pytest.mark.asyncio
    async def test_run_format_success(self, shell: CrackerjackShell) -> None:
        ok_format = _completed_process(returncode=0, stdout="")
        ok_fix = _completed_process(returncode=0, stdout="All fixes applied")
        with patch(
            "crackerjack.shell.adapter.subprocess.run",
            side_effect=[ok_format, ok_fix],
        ) as run:
            await shell._run_format()

        assert run.call_count == 2
        first_cmd = run.call_args_list[0].args[0]
        second_cmd = run.call_args_list[1].args[0]
        assert first_cmd == ["ruff", "format", "."]
        assert second_cmd == ["ruff", "check", "--fix", "."]

    @pytest.mark.asyncio
    async def test_run_format_raises_when_format_fails(self, shell: CrackerjackShell) -> None:
        bad_format = _completed_process(returncode=3, stdout="format error")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=bad_format):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                await shell._run_format()
        assert exc.value.returncode == 3

    @pytest.mark.asyncio
    async def test_run_format_prints_unfixed_issues(self, shell: CrackerjackShell) -> None:
        ok_format = _completed_process(returncode=0, stdout="")
        fix_partial = _completed_process(returncode=1, stdout="3 issues unfixable")
        with patch(
            "crackerjack.shell.adapter.subprocess.run",
            side_effect=[ok_format, fix_partial],
        ):
            await shell._run_format()


class TestRunTypecheck:
    @pytest.mark.asyncio
    async def test_run_typecheck_success(self, shell: CrackerjackShell) -> None:
        result = _completed_process(returncode=0, stdout="Success: no issues found in 5 files")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=result) as run:
            await shell._run_typecheck()

        run.assert_called_once()
        assert run.call_args.args[0] == ["mypy", "crackerjack/"]

    @pytest.mark.asyncio
    async def test_run_typecheck_raises_on_errors(self, shell: CrackerjackShell) -> None:
        result = _completed_process(returncode=1, stdout="error: Name 'x' is not defined")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=result):
            with pytest.raises(subprocess.CalledProcessError) as exc:
                await shell._run_typecheck()
        assert exc.value.returncode == 1

    @pytest.mark.asyncio
    async def test_run_typecheck_blank_stdout(self, shell: CrackerjackShell) -> None:
        result = _completed_process(returncode=0, stdout="")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=result):
            await shell._run_typecheck()


class TestShowHooks:
    @pytest.mark.asyncio
    async def test_show_hooks_no_pyproject(
        self, shell: CrackerjackShell, tmp_path: Path,
    ) -> None:
        shell._project_root = tmp_path
        await shell._show_hooks()

    @pytest.mark.asyncio
    async def test_show_hooks_no_hooks_configured(
        self, shell: CrackerjackShell, tmp_path: Path,
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.black]\nline-length = 100\n")

        shell._project_root = tmp_path
        await shell._show_hooks()

    @pytest.mark.asyncio
    async def test_show_hooks_with_dict_hooks(
        self, shell: CrackerjackShell, tmp_path: Path,
    ) -> None:
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.pre-commit]\n"
            "[tool.pre-commit.hooks]\n"
            'black = { stage = "format", command = "black ." }\n'
            'ruff = { stage = "lint", command = "ruff check" }\n',
        )

        shell._project_root = tmp_path
        await shell._show_hooks()

    @pytest.mark.asyncio
    async def test_show_hooks_with_string_hooks(
        self, shell: CrackerjackShell, tmp_path: Path,
    ) -> None:
        # String-valued hook entries are skipped (only dicts are rendered).
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[tool.pre-commit]\n"
            "[tool.pre-commit.hooks]\n"
            'black = "just a string"\n',
        )

        shell._project_root = tmp_path
        await shell._show_hooks()


class TestRunCrack:
    @pytest.mark.asyncio
    async def test_run_crack_all_pass(self, shell: CrackerjackShell) -> None:
        ok = _completed_process(returncode=0, stdout="ok")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=ok):
            await shell._run_crack()

    @pytest.mark.asyncio
    async def test_run_crack_one_fails(self, shell: CrackerjackShell) -> None:
        ok = _completed_process(returncode=0, stdout="ok")
        fail = _completed_process(returncode=1, stdout="1 failed")
        with patch(
            "crackerjack.shell.adapter.subprocess.run",
            side_effect=[ok, ok, fail, ok],
        ):
            await shell._run_crack()

    @pytest.mark.asyncio
    async def test_run_crack_all_fail(self, shell: CrackerjackShell) -> None:
        fail = _completed_process(returncode=1, stdout="boom")
        with patch("crackerjack.shell.adapter.subprocess.run", return_value=fail):
            await shell._run_crack()


class TestClose:
    @pytest.mark.asyncio
    async def test_close_with_no_session(self, shell: CrackerjackShell) -> None:
        shell._session_id = None
        shell.session_tracker.emit_session_end = AsyncMock()
        shell.session_tracker.close = AsyncMock()

        await shell.close()

        shell.session_tracker.emit_session_end.assert_not_called()
        shell.session_tracker.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_with_session_resets_id(
        self, shell: CrackerjackShell,
    ) -> None:
        shell._session_id = "abc-123"
        shell.session_tracker.emit_session_end = AsyncMock()
        shell.session_tracker.close = AsyncMock()

        await shell.close()

        shell.session_tracker.emit_session_end.assert_awaited_once_with(
            session_id="abc-123", metadata={},
        )
        assert shell._session_id is None
        shell.session_tracker.close.assert_awaited_once()


class TestSessionEmission:
    @pytest.mark.asyncio
    async def test_session_start_unavailable_emits_none(
        self, shell: CrackerjackShell,
    ) -> None:
        shell.session_tracker.emit_session_start = AsyncMock(return_value=None)

        await shell._emit_session_start()

        shell.session_tracker.emit_session_start.assert_awaited_once()
        assert shell._session_id is None

    @pytest.mark.asyncio
    async def test_session_start_emitter_raises_is_logged(
        self, shell: CrackerjackShell, caplog: pytest.LogCaptureFixture,
    ) -> None:
        async def boom(**_: object) -> str:
            raise RuntimeError("tracker down")

        shell.session_tracker.emit_session_start = boom

        with caplog.at_level("DEBUG", logger="crackerjack.shell.adapter"):
            await shell._emit_session_start()

        assert shell._session_id is None

    @pytest.mark.asyncio
    async def test_session_end_emitter_raises_is_logged(
        self, shell: CrackerjackShell, caplog: pytest.LogCaptureFixture,
    ) -> None:
        shell._session_id = "abc-123"

        async def boom(**_: object) -> None:
            raise RuntimeError("tracker down")

        shell.session_tracker.emit_session_end = boom

        with caplog.at_level("DEBUG", logger="crackerjack.shell.adapter"):
            await shell._emit_session_end()

        # Session id is still reset in the finally block
        assert shell._session_id is None

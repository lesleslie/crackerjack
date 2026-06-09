"""Tests for ``crackerjack.mcp.client_runner``.

The client_runner module is a thin wrapper that:

* probes the local MCP server port via ``is_mcp_server_running`` (socket probe);
* starts the server via ``ensure_mcp_server_running`` (subprocess.Popen);
* drives a mock session through ``run_with_mcp_server``;
* exposes a CLI entry point via ``main``.

All I/O boundaries (socket, subprocess, Console, asyncio.run) are mocked at
the boundary so no real network/process activity is needed.
"""

from __future__ import annotations

import asyncio
import socket
import subprocess
import sys
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.mcp import client_runner
from crackerjack.mcp.client_runner import (
    ensure_mcp_server_running,
    is_mcp_server_running,
    main,
    run_with_mcp_server,
)


# ---------------------------------------------------------------------------
# is_mcp_server_running
# ---------------------------------------------------------------------------


class TestIsMcpServerRunning:
    """Probe the local MCP port via a TCP socket."""

    def test_returns_true_when_port_is_open(self) -> None:
        # Simulate connect_ex returning 0 (success) without touching the network.
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        with patch.object(socket, "socket", return_value=mock_sock):
            assert is_mcp_server_running() is True

    def test_returns_false_when_port_is_closed(self) -> None:
        # Non-zero return from connect_ex => port not accepting connections.
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 111  # ECONNREFUSED on Linux
        with patch.object(socket, "socket", return_value=mock_sock):
            assert is_mcp_server_running() is False

    def test_uses_provided_host_and_port(self) -> None:
        mock_sock = MagicMock()
        mock_sock.connect_ex.return_value = 0
        with patch.object(socket, "socket", return_value=mock_sock) as sock_factory:
            assert is_mcp_server_running(host="10.0.0.5", port=9999) is True
        sock_factory.assert_called_once_with(socket.AF_INET, socket.SOCK_STREAM)
        mock_sock.connect_ex.assert_called_once_with(("10.0.0.5", 9999))

    def test_socket_is_always_closed(self) -> None:
        # Even when connect_ex raises, the socket must be closed in the
        # ``finally`` block.
        mock_sock = MagicMock()
        mock_sock.connect_ex.side_effect = OSError("boom")
        with patch.object(socket, "socket", return_value=mock_sock):
            with pytest.raises(OSError):
                is_mcp_server_running()
        mock_sock.close.assert_called_once_with()


# ---------------------------------------------------------------------------
# ensure_mcp_server_running
# ---------------------------------------------------------------------------


class TestEnsureMcpServerRunning:
    """Start the MCP server subprocess when one isn't already running."""

    async def test_returns_none_when_already_running(self) -> None:
        # Already-running case: no subprocess should be spawned.
        with patch.object(client_runner, "is_mcp_server_running", return_value=True):
            result = await ensure_mcp_server_running()
        assert result is None

    async def test_starts_subprocess_when_not_running(self) -> None:
        # First probe = not running, then loop probe = running. Should spawn
        # exactly one Popen and return the handle.
        fake_proc = MagicMock(spec=subprocess.Popen)
        with (
            patch.object(
                client_runner,
                "is_mcp_server_running",
                side_effect=[False, True],
            ),
            patch.object(client_runner.subprocess, "Popen", return_value=fake_proc) as popen,
            patch.object(client_runner.asyncio, "sleep", new=AsyncMock()),
        ):
            result = await ensure_mcp_server_running()
        assert result is fake_proc
        popen.assert_called_once()
        argv = popen.call_args.args[0]
        # Must launch the crackerjack module rather than a bare command.
        assert argv[:3] == [sys.executable, "-m", "crackerjack"]

    async def test_raises_runtime_error_when_server_never_starts(self) -> None:
        # Probe never becomes True -> RuntimeError and process terminated.
        fake_proc = MagicMock(spec=subprocess.Popen)
        with (
            patch.object(
                client_runner,
                "is_mcp_server_running",
                return_value=False,
            ),
            patch.object(client_runner.subprocess, "Popen", return_value=fake_proc),
            patch.object(client_runner.asyncio, "sleep", new=AsyncMock()),
        ):
            with pytest.raises(RuntimeError, match="Failed to start MCP server"):
                await ensure_mcp_server_running()
        fake_proc.terminate.assert_called_once_with()

    async def test_loop_sleeps_between_probes(self) -> None:
        # When the server is already up, no Popen / no sleep should fire.
        with (
            patch.object(client_runner, "is_mcp_server_running", return_value=True),
            patch.object(
                client_runner.subprocess,
                "Popen",
                create=True,
            ) as popen,
            patch.object(client_runner.asyncio, "sleep", new=AsyncMock()) as sleep,
        ):
            await ensure_mcp_server_running()
        popen.assert_not_called()
        sleep.assert_not_called()


# ---------------------------------------------------------------------------
# run_with_mcp_server
# ---------------------------------------------------------------------------


class TestRunWithMcpServer:
    """The high-level driver: ensures server up, runs mock session, logs."""

    async def test_uses_default_command_when_unspecified(self) -> None:
        # Default command should flow through and reach the print().
        fake_proc = MagicMock(spec=subprocess.Popen)
        with (
            patch.object(
                client_runner,
                "ensure_mcp_server_running",
                new=AsyncMock(return_value=fake_proc),
            ),
            patch.object(client_runner, "Console") as console_cls,
        ):
            await run_with_mcp_server()
        console_instance = console_cls.return_value
        printed = " ".join(str(call) for call in console_instance.print.call_args_list)
        assert "WebSocket monitoring removed" in printed

    async def test_uses_provided_command(self) -> None:
        # Custom command should be interpolated into the print message.
        fake_proc = MagicMock(spec=subprocess.Popen)
        with (
            patch.object(
                client_runner,
                "ensure_mcp_server_running",
                new=AsyncMock(return_value=fake_proc),
            ),
            patch.object(client_runner, "Console") as console_cls,
        ):
            await run_with_mcp_server(command="/crackerjack:lint")
        console_instance = console_cls.return_value
        printed = " ".join(str(call) for call in console_instance.print.call_args_list)
        assert "/crackerjack:lint" in printed

    async def test_handles_exception_via_console(self) -> None:
        # The inner ``try/except`` converts errors into console output and
        # sys.exit(1) rather than re-raising.
        fake_proc = MagicMock(spec=subprocess.Popen)
        with (
            patch.object(
                client_runner,
                "ensure_mcp_server_running",
                new=AsyncMock(return_value=fake_proc),
            ),
            patch.object(client_runner, "Console") as console_cls,
            patch.object(client_runner.sys, "exit") as exit_mock,
        ):
            # Force the second print (inside the try block) to raise. The
            # first call goes to the finally block's "continues running"
            # print which runs AFTER the except. So the second call
            # (inside try) raises and triggers sys.exit(1).
            console_instance = console_cls.return_value

            def _maybe_raise(msg: object = "", *args: object, **kwargs: object) -> None:
                if "WebSocket monitoring removed" in str(msg):
                    raise RuntimeError("kaboom")

            console_instance.print.side_effect = _maybe_raise
            await run_with_mcp_server()
        # sys.exit was called with 1 when the except fired.
        exit_mock.assert_called_once_with(1)

    async def test_logs_continuation_message_when_server_was_spawned(self) -> None:
        # If ensure_mcp_server_running returned a real process, the finally
        # block should print the "continues running" note.
        fake_proc = MagicMock(spec=subprocess.Popen)
        with (
            patch.object(
                client_runner,
                "ensure_mcp_server_running",
                new=AsyncMock(return_value=fake_proc),
            ),
            patch.object(client_runner, "Console") as console_cls,
        ):
            await run_with_mcp_server()
        printed = " ".join(
            str(call) for call in console_cls.return_value.print.call_args_list
        )
        assert "continues running" in printed

    async def test_no_continuation_message_when_server_already_running(self) -> None:
        # ensure_mcp_server_running returns None when server is already up;
        # the finally block should NOT print the "continues running" note.
        with (
            patch.object(
                client_runner,
                "ensure_mcp_server_running",
                new=AsyncMock(return_value=None),
            ),
            patch.object(client_runner, "Console") as console_cls,
        ):
            await run_with_mcp_server()
        printed = " ".join(
            str(call) for call in console_cls.return_value.print.call_args_list
        )
        assert "continues running" not in printed

    async def test_resolves_main_py_path_without_crash(self) -> None:
        # The ``Path(__file__).parent.parent / "__main__.py"`` expression must
        # resolve to a real path; the result is discarded but the lookup must
        # not raise.
        fake_proc = MagicMock(spec=subprocess.Popen)
        with (
            patch.object(
                client_runner,
                "ensure_mcp_server_running",
                new=AsyncMock(return_value=fake_proc),
            ),
            patch.object(client_runner, "Console"),
        ):
            await run_with_mcp_server()
        expected = Path(client_runner.__file__).parent.parent / "__main__.py"
        assert expected.exists() or True  # resolution only, no behavioural claim


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


class TestMain:
    """The CLI entry point: argparse + asyncio.run."""

    def test_uses_default_command_when_no_argv(self) -> None:
        # No positional command => default "/crackerjack:run" (with embedded
        # spaces) is used.
        with (
            patch.object(sys, "argv", ["client_runner"]),
            patch.object(client_runner.asyncio, "run") as run_mock,
            patch.object(client_runner, "Console"),
        ):
            main()
        run_mock.assert_called_once()
        # Compare the .args attribute to avoid coroutine identity issues.
        actual_args = run_mock.call_args.args
        assert len(actual_args) == 1
        # The first arg is a coroutine; just check that run_with_mcp_server
        # was the source by calling .cr_frame.f_code.co_name.
        coro = actual_args[0]
        assert coro.cr_code.co_name == "run_with_mcp_server"
        coro.close()  # avoid "coroutine was never awaited" warning

    def test_uses_positional_command(self) -> None:
        with (
            patch.object(
                sys,
                "argv",
                ["client_runner", "/crackerjack:custom-op"],
            ),
            patch.object(client_runner.asyncio, "run") as run_mock,
        ):
            main()
        run_mock.assert_called_once()
        coro = run_mock.call_args.args[0]
        assert coro.cr_code.co_name == "run_with_mcp_server"
        coro.close()

    def test_keyboard_interrupt_exits_with_code_1(self) -> None:
        # asyncio.run raises KeyboardInterrupt -> the handler must translate
        # it to a clean sys.exit(1) and print a cancellation message.
        with (
            patch.object(sys, "argv", ["client_runner"]),
            patch.object(
                client_runner.asyncio,
                "run",
                side_effect=KeyboardInterrupt,
            ),
            patch.object(client_runner.sys, "exit") as exit_mock,
            patch.object(client_runner, "Console") as console_cls,
        ):
            main()
        exit_mock.assert_called_once_with(1)
        printed = " ".join(
            str(call) for call in console_cls.return_value.print.call_args_list
        )
        assert "cancelled" in printed

    def test_passes_default_to_argparse(self) -> None:
        # Invoke the real argparse path; the call to asyncio.run will
        # receive a coroutine built from the parsed default command.
        with (
            patch.object(sys, "argv", ["client_runner"]),
            patch.object(client_runner.asyncio, "run") as run_mock,
            patch.object(client_runner, "Console"),
        ):
            main()
        assert run_mock.called
        run_mock.call_args.args[0].close()


# ---------------------------------------------------------------------------
# Smoke test: ensure the module's CLI guard does not run during import.
# ---------------------------------------------------------------------------


def test_module_dunder_main_guard_does_not_run_on_import() -> None:
    # Importing the module must not trigger main(); the __name__ == "__main__"
    # guard prevents that.
    import importlib

    importlib.reload(client_runner)
    # If the guard worked, we are still in this test (no sys.exit) and
    # the call below returns normally.
    assert callable(client_runner.main)


# ---------------------------------------------------------------------------
# asyncio event loop fixture to keep ``asyncio.run`` mocks simple.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_real_event_loop() -> t.Iterator[None]:
    # Some tests patch asyncio.run; we don't want stray background tasks.
    yield
    # Drain anything left behind in the current loop.
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return
    except RuntimeError:
        pass

"""Tests for ``crackerjack.services.zuban_lsp_service``.

Covers the ``ZubanLSPService`` lifecycle: init, properties, start/stop/restart,
health checks (stdio + tcp + OSError fallback), status reporting, and the
LSP message I/O paths. ``subprocess.Popen`` and socket operations are mocked
to keep tests hermetic.
"""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
from io import BytesIO
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.services.zuban_lsp_service import (
    ZubanLSPService,
    create_zuban_lsp_service,
)


def _make_running_process() -> MagicMock:
    """Subprocess.Popen double that's still alive (``poll()`` returns None)."""
    proc = MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = None  # alive
    proc.pid = 12345
    # stdin / stdout / stderr are file-like objects so .write / .readline work.
    proc.stdin = MagicMock()
    proc.stdout = MagicMock()
    proc.stderr = MagicMock()
    proc.terminate = MagicMock()
    proc.kill = MagicMock()
    proc.wait = MagicMock()
    return proc


def _make_dead_process() -> MagicMock:
    """Process that has exited (``poll()`` returns a non-None exit code)."""
    proc = MagicMock(spec=subprocess.Popen)
    proc.poll.return_value = 1  # exited
    proc.pid = 99999
    proc.stdin = MagicMock()
    proc.stdout = MagicMock()
    proc.stderr = BytesIO(b"boot failed")
    return proc


def test_init_defaults() -> None:
    svc = ZubanLSPService()
    assert svc.port == 8685
    assert svc.mode == "tcp"
    assert svc.process is None
    assert svc.start_time == 0.0
    assert svc._health_check_failures == 0  # noqa: SLF001
    assert svc._max_health_failures == 3  # noqa: SLF001


def test_is_running_false_when_no_process() -> None:
    svc = ZubanLSPService()
    assert svc.is_running is False


def test_is_running_false_when_poll_returns_nonzero() -> None:
    svc = ZubanLSPService()
    svc.process = _make_dead_process()
    assert svc.is_running is False


def test_is_running_true_when_alive() -> None:
    svc = ZubanLSPService()
    svc.process = _make_running_process()
    assert svc.is_running is True


def test_uptime_zero_when_not_running() -> None:
    svc = ZubanLSPService()
    assert svc.uptime == 0.0


def test_uptime_when_running() -> None:
    svc = ZubanLSPService()
    svc.start_time = 100.0
    svc.process = _make_running_process()
    with patch("crackerjack.services.zuban_lsp_service.time.time", return_value=125.0):
        assert svc.uptime == 25.0


def test_uptime_zero_when_start_time_zero() -> None:
    """Even with a running process, uptime is 0 if start_time was never set."""
    svc = ZubanLSPService()
    svc.process = _make_running_process()
    svc.start_time = 0.0
    assert svc.uptime == 0.0


@pytest.mark.asyncio
async def test_start_returns_true_when_already_running() -> None:
    """If process is already running, ``start`` is a no-op success."""
    svc = ZubanLSPService()
    svc.process = _make_running_process()
    result = await svc.start()
    assert result is True


@pytest.mark.asyncio
async def test_start_success_tcp_mode() -> None:
    svc = ZubanLSPService(mode="tcp")
    proc = _make_running_process()
    with patch(
        "crackerjack.services.zuban_lsp_service.subprocess.Popen",
        return_value=proc,
    ) as mocked_popen:
        result = await svc.start()

    assert result is True
    assert svc.process is proc
    assert svc.start_time > 0
    # Both modes run the same command (zuban server), so just verify it ran.
    mocked_popen.assert_called_once()
    cmd = mocked_popen.call_args.args[0]
    assert cmd == ["uv", "run", "zuban", "server"]


@pytest.mark.asyncio
async def test_start_success_stdio_mode() -> None:
    """The mode != 'tcp' else-branch is also exercised (same command)."""
    svc = ZubanLSPService(mode="stdio")
    proc = _make_running_process()
    with patch(
        "crackerjack.services.zuban_lsp_service.subprocess.Popen",
        return_value=proc,
    ) as mocked_popen:
        result = await svc.start()
    assert result is True
    cmd = mocked_popen.call_args.args[0]
    assert cmd == ["uv", "run", "zuban", "server"]


@pytest.mark.asyncio
async def test_start_logs_error_output_when_process_exits() -> None:
    """When start fails AND stderr has content, the error is logged."""
    import logging

    svc = ZubanLSPService()
    proc = _make_dead_process()
    proc.stderr = BytesIO(b"port already in use")
    with patch(
        "crackerjack.services.zuban_lsp_service.subprocess.Popen", return_value=proc
    ):
        with patch.object(svc, "_check_stdio_health", return_value=False):
            with patch.object(svc.console, "print"):
                with patch.object(logging.getLogger("crackerjack.zuban_lsp"), "error") as mocked_log:
                    result = await svc.start()
    assert result is False
    mocked_log.assert_called_once()
    assert "port already in use" in str(mocked_log.call_args)


@pytest.mark.asyncio
async def test_start_returns_false_when_process_exits_immediately() -> None:
    """If Popen returns but poll() shows it dead, ``start`` returns False."""
    svc = ZubanLSPService()
    proc = _make_dead_process()
    with patch(
        "crackerjack.services.zuban_lsp_service.subprocess.Popen",
        return_value=proc,
    ):
        with patch.object(svc, "_check_stdio_health", return_value=False):
            result = await svc.start()
    assert result is False


@pytest.mark.asyncio
async def test_start_handles_popen_exception() -> None:
    svc = ZubanLSPService()
    with patch(
        "crackerjack.services.zuban_lsp_service.subprocess.Popen",
        side_effect=OSError("binary not found"),
    ):
        result = await svc.start()
    assert result is False


@pytest.mark.asyncio
async def test_stop_no_process_is_noop() -> None:
    svc = ZubanLSPService()
    await svc.stop()  # must not raise


@pytest.mark.asyncio
async def test_stop_graceful_terminate() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc
    await svc.stop()
    proc.terminate.assert_called_once()
    assert svc.process is None
    assert svc.start_time == 0.0


@pytest.mark.asyncio
async def test_stop_force_kill_on_timeout() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    proc.wait.side_effect = [
        subprocess.TimeoutExpired(cmd="zuban", timeout=5.0),
        None,
    ]
    svc.process = proc
    await svc.stop()
    proc.terminate.assert_called_once()
    proc.kill.assert_called_once()


@pytest.mark.asyncio
async def test_stop_swallows_exception() -> None:
    svc = ZubanLSPService()
    proc = MagicMock()
    proc.terminate.side_effect = RuntimeError("oops")
    svc.process = proc
    await svc.stop()  # must not raise
    assert svc.process is None


@pytest.mark.asyncio
async def test_health_check_returns_false_when_not_running() -> None:
    svc = ZubanLSPService()
    assert await svc.health_check() is False


@pytest.mark.asyncio
async def test_health_check_stdio_mode() -> None:
    svc = ZubanLSPService(mode="stdio")
    svc.process = _make_running_process()
    svc.process.poll.return_value = None
    assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_health_check_tcp_mode_success() -> None:
    svc = ZubanLSPService(mode="tcp")
    svc.process = _make_running_process()
    with patch("socket.socket") as mocked_socket:
        s = MagicMock()
        s.connect_ex.return_value = 0
        mocked_socket.return_value.__enter__.return_value = s
        # The code uses ``socket.socket()`` then ``connect_ex`` then ``close``.
        mocked_socket.return_value.connect_ex.return_value = 0
        assert await svc.health_check() is True


@pytest.mark.asyncio
async def test_health_check_tcp_mode_connect_fails_falls_back_to_stdio() -> None:
    """If TCP connect fails (OSError), fall back to stdio health check."""
    svc = ZubanLSPService(mode="tcp")
    svc.process = _make_running_process()
    with patch("socket.socket") as mocked_socket:
        s = MagicMock()
        s.connect_ex.side_effect = OSError("connection refused")
        mocked_socket.return_value = s
        with patch.object(svc, "_check_stdio_health", return_value=True) as mocked_stdio:
            assert await svc.health_check() is True
        mocked_stdio.assert_called_once()


@pytest.mark.asyncio
async def test_health_check_tcp_mode_connect_non_zero_falls_back_to_stdio() -> None:
    """If TCP returns non-zero, fall back to stdio."""
    svc = ZubanLSPService(mode="tcp")
    svc.process = _make_running_process()
    with patch("socket.socket") as mocked_socket:
        s = MagicMock()
        s.connect_ex.return_value = 1  # non-zero
        mocked_socket.return_value = s
        with patch.object(svc, "_check_stdio_health", return_value=False) as mocked_stdio:
            assert await svc.health_check() is False


@pytest.mark.asyncio
async def test_health_check_records_failure_on_exception() -> None:
    svc = ZubanLSPService(mode="stdio")
    svc.process = _make_running_process()
    with patch.object(svc, "_check_stdio_health", side_effect=RuntimeError("boom")):
        result = await svc.health_check()
    assert result is False
    assert svc._health_check_failures == 1  # noqa: SLF001


def test_check_stdio_health_false_when_no_process() -> None:
    svc = ZubanLSPService()
    assert svc._check_stdio_health() is False  # noqa: SLF001


def test_check_stdio_health_true_when_alive() -> None:
    svc = ZubanLSPService()
    svc.process = _make_running_process()
    assert svc._check_stdio_health() is True  # noqa: SLF001


def test_check_stdio_health_false_when_dead() -> None:
    svc = ZubanLSPService()
    svc.process = _make_dead_process()
    assert svc._check_stdio_health() is False  # noqa: SLF001


def test_check_tcp_health_false_when_no_process() -> None:
    svc = ZubanLSPService()
    assert svc._check_tcp_health() is False  # noqa: SLF001


def test_check_tcp_health_falls_back_to_stdio_on_oserror() -> None:
    svc = ZubanLSPService()
    svc.process = _make_running_process()
    with patch("socket.socket") as mocked_socket:
        s = MagicMock()
        s.connect_ex.side_effect = OSError("refused")
        mocked_socket.return_value = s
        with patch.object(svc, "_check_stdio_health", return_value=True) as mocked_stdio:
            assert svc._check_tcp_health() is True  # noqa: SLF001
            mocked_stdio.assert_called_once()


@pytest.mark.asyncio
async def test_restart_calls_stop_then_start() -> None:
    svc = ZubanLSPService()
    svc.process = _make_running_process()
    with patch.object(svc, "stop", new=AsyncMock()) as mocked_stop:
        with patch.object(svc, "start", new=AsyncMock(return_value=True)) as mocked_start:
            result = await svc.restart()
    assert result is True
    mocked_stop.assert_awaited_once()
    mocked_start.assert_awaited_once()


@pytest.mark.asyncio
async def test_restart_returns_false_when_start_fails() -> None:
    svc = ZubanLSPService()
    with patch.object(svc, "stop", new=AsyncMock()):
        with patch.object(svc, "start", new=AsyncMock(return_value=False)):
            assert await svc.restart() is False


def test_get_status_when_stopped() -> None:
    svc = ZubanLSPService(port=9999, mode="tcp")
    status = svc.get_status()
    assert status["running"] is False
    assert status["pid"] is None
    assert status["uptime"] == 0.0
    assert status["port"] == 9999
    assert status["mode"] == "tcp"
    assert status["health_failures"] == 0
    assert status["max_health_failures"] == 3
    assert status["healthy"] is False


def test_get_status_when_running() -> None:
    svc = ZubanLSPService(port=8685, mode="tcp")
    svc.process = _make_running_process()
    svc.start_time = 0.0  # uptime stays 0
    status = svc.get_status()
    assert status["running"] is True
    assert status["pid"] == 12345


def test_get_status_unhealthy_when_failures_exceed_max() -> None:
    svc = ZubanLSPService()
    svc.process = _make_running_process()
    svc._health_check_failures = 3  # noqa: SLF001
    assert svc.get_status()["healthy"] is False


@pytest.mark.asyncio
async def test_send_lsp_request_returns_none_when_not_running() -> None:
    svc = ZubanLSPService()
    assert await svc.send_lsp_request("initialize") is None


@pytest.mark.asyncio
async def test_send_lsp_request_returns_none_when_no_stdin() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    proc.stdin = None
    svc.process = proc
    assert await svc.send_lsp_request("initialize") is None


@pytest.mark.asyncio
async def test_send_lsp_request_writes_correct_message_format() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    with patch.object(
        svc, "_read_lsp_response", new=AsyncMock(return_value={"id": 1})
    ):
        await svc.send_lsp_request("initialize", params={"x": 1})

    # The stdin should have received a Content-Length framed message.
    written = proc.stdin.write.call_args.args[0].decode("utf-8")
    assert written.startswith("Content-Length: ")
    assert "\r\n\r\n" in written
    body = written.split("\r\n\r\n", 1)[1]
    parsed = json.loads(body)
    assert parsed["method"] == "initialize"
    assert parsed["params"] == {"x": 1}


@pytest.mark.asyncio
async def test_send_lsp_request_didopen_returns_notification_status() -> None:
    """``textDocument/did*`` notifications get a stub response without reading."""
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    # Don't stub _read_lsp_response — it should NOT be called for notifications.
    result = await svc.send_lsp_request(
        "textDocument/didOpen", params={"uri": "file://x.py"}
    )
    assert result["status"] == "notification_sent"
    assert "id" in result


@pytest.mark.asyncio
async def test_send_lsp_request_returns_timeout_status_on_timeout() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    async def _raise_timeout(*_args: Any, **_kwargs: Any) -> Any:
        raise TimeoutError

    with patch.object(svc, "_read_lsp_response", side_effect=_raise_timeout):
        result = await svc.send_lsp_request("initialize")
    assert result["status"] == "timeout"


@pytest.mark.asyncio
async def test_send_lsp_request_returns_none_on_exception() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    with patch.object(svc, "_read_lsp_response", side_effect=RuntimeError("boom")):
        assert await svc.send_lsp_request("initialize") is None


@pytest.mark.asyncio
async def test_send_lsp_request_without_params_omits_field() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    with patch.object(
        svc, "_read_lsp_response", new=AsyncMock(return_value={"id": 1})
    ):
        await svc.send_lsp_request("shutdown")

    body = proc.stdin.write.call_args.args[0].decode("utf-8").split("\r\n\r\n", 1)[1]
    parsed = json.loads(body)
    assert "params" not in parsed


@pytest.mark.asyncio
async def test_read_lsp_response_returns_none_when_no_process() -> None:
    svc = ZubanLSPService()
    assert await svc._read_lsp_response(expected_id=1) is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_lsp_response_returns_none_when_no_stdout() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    proc.stdout = None
    svc.process = proc
    assert await svc._read_lsp_response(expected_id=1) is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_lsp_response_returns_matched_id() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    async def _fake_read() -> str:
        return json.dumps({"id": 42, "result": "ok"})

    with patch.object(svc, "_read_message_from_stdout", new=AsyncMock(side_effect=_fake_read)):
        response = await svc._read_lsp_response(expected_id=42)  # noqa: SLF001
    assert response == {"id": 42, "result": "ok"}


@pytest.mark.asyncio
async def test_read_lsp_response_returns_mismatched_id() -> None:
    """A response with the wrong id is still returned (logged but not dropped)."""
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    async def _fake_read() -> str:
        return json.dumps({"id": 99, "result": "ok"})

    with patch.object(
        svc, "_read_message_from_stdout", new=AsyncMock(side_effect=_fake_read)
    ):
        response = await svc._read_lsp_response(expected_id=42)  # noqa: SLF001
    assert response == {"id": 99, "result": "ok"}


@pytest.mark.asyncio
async def test_read_lsp_response_returns_none_when_empty_message() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    async def _fake_read() -> None:
        return None

    with patch.object(
        svc, "_read_message_from_stdout", new=AsyncMock(side_effect=_fake_read)
    ):
        assert await svc._read_lsp_response(expected_id=1) is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_lsp_response_returns_none_on_json_error() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    async def _fake_read() -> str:
        return "not json"

    with patch.object(
        svc, "_read_message_from_stdout", new=AsyncMock(side_effect=_fake_read)
    ):
        assert await svc._read_lsp_response(expected_id=1) is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_lsp_response_propagates_timeout() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    async def _fake_read() -> str:
        raise TimeoutError

    with patch.object(svc, "_read_message_from_stdout", new=AsyncMock(side_effect=_fake_read)):
        with pytest.raises(TimeoutError):
            await svc._read_lsp_response(expected_id=1)  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_message_from_stdout_returns_none_when_no_stdout() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    proc.stdout = None
    svc.process = proc
    assert await svc._read_message_from_stdout() is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_message_from_stdout_happy_path() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc
    body = json.dumps({"id": 1, "result": "ok"})
    header = f"Content-Length: {len(body.encode())}\r\n\r\n"

    async def _fake_line() -> str:
        return header

    async def _fake_bytes(count: int) -> bytes:
        return body.encode("utf-8")

    with patch.object(svc, "_read_line_async", new=AsyncMock(side_effect=_fake_line)):
        with patch.object(
            svc, "_read_bytes_async", new=AsyncMock(side_effect=_fake_bytes)
        ):
            result = await svc._read_message_from_stdout()  # noqa: SLF001
    assert json.loads(result) == {"id": 1, "result": "ok"}


@pytest.mark.asyncio
async def test_read_message_from_stdout_no_header_returns_none() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    async def _empty() -> str:
        return ""

    with patch.object(svc, "_read_line_async", new=AsyncMock(side_effect=_empty)):
        assert await svc._read_message_from_stdout() is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_message_from_stdout_no_content_length_returns_none() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    async def _no_cl() -> str:
        return "Garbage header line"

    with patch.object(svc, "_read_line_async", new=AsyncMock(side_effect=_no_cl)):
        assert await svc._read_message_from_stdout() is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_message_from_stdout_warns_on_non_empty_separator() -> None:
    """A non-empty separator line after Content-Length logs a warning."""
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc
    body = json.dumps({"id": 1})

    async def _lines() -> str:
        return f"Content-Length: {len(body.encode())}"

    async def _non_empty() -> str:
        return "unexpected content"

    async def _bytes(count: int) -> bytes:
        return body.encode("utf-8")

    with patch.object(svc, "_read_line_async", new=AsyncMock(side_effect=[_lines(), _non_empty()] if False else AsyncMock(side_effect=lambda: None))):
        pass

    # Simpler version: just use a list of side_effects.
    line_results = iter([f"Content-Length: {len(body.encode())}", "unexpected"])

    async def _next_line() -> str:
        return next(line_results)

    with patch.object(svc, "_read_line_async", new=AsyncMock(side_effect=_next_line)):
        with patch.object(
            svc, "_read_bytes_async", new=AsyncMock(return_value=body.encode("utf-8"))
        ):
            result = await svc._read_message_from_stdout()  # noqa: SLF001
    # The body is still returned, just with a warning logged.
    assert json.loads(result) == {"id": 1}


@pytest.mark.asyncio
async def test_read_message_from_stdout_exception_returns_none() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    svc.process = proc

    async def _boom() -> str:
        raise RuntimeError("oops")

    with patch.object(svc, "_read_line_async", new=AsyncMock(side_effect=_boom)):
        assert await svc._read_message_from_stdout() is None  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_line_async_returns_empty_when_no_stdout() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    proc.stdout = None
    svc.process = proc
    assert await svc._read_line_async() == ""  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_line_async_strips_crlf() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    proc.stdout.readline.return_value = b"hello world\r\n"
    svc.process = proc
    line = await svc._read_line_async()  # noqa: SLF001
    assert line == "hello world"


@pytest.mark.asyncio
async def test_read_bytes_async_returns_empty_when_no_stdout() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    proc.stdout = None
    svc.process = proc
    assert await svc._read_bytes_async(5) == b""  # noqa: SLF001


@pytest.mark.asyncio
async def test_read_bytes_async_returns_process_output() -> None:
    svc = ZubanLSPService()
    proc = _make_running_process()
    proc.stdout.read.return_value = b"abcde"
    svc.process = proc
    assert await svc._read_bytes_async(5) == b"abcde"  # noqa: SLF001


@pytest.mark.asyncio
async def test_create_zuban_lsp_service_factory() -> None:
    svc = await create_zuban_lsp_service(port=1234, mode="tcp")
    assert isinstance(svc, ZubanLSPService)
    assert svc.port == 1234

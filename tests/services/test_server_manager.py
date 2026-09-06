"""Tests for ``crackerjack.services.server_manager``.

This module wraps ``ps aux`` parsing to identify crackerjack MCP server
processes and Zuban LSP server processes, then stops/restarts them. The
``execute_secure_subprocess`` and ``subprocess.Popen`` boundaries are
patched at the module level so we exercise the parsing logic, the kill
escalation logic in ``stop_process``, and the orchestration in
``stop_mcp_server``/``stop_zuban_lsp``/``restart_*`` without spawning
real processes.

The ``_extract_process_info`` expection list is positional ``parts[1]`` is
PID, ``parts[0]`` is user, ``parts[2..3]`` are CPU/mem percentages; the
command-start index defaults to 10 (BSD/macOS ``ps aux``) but adjusts when
the command contains ``python``/``Python`` (Linux style).
"""

from __future__ import annotations

import os
import signal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from crackerjack.services import server_manager
from crackerjack.services.server_manager import (
    _extract_process_info,
    _find_command_start_index,
    _is_mcp_server_process,
    _is_zuban_lsp_process,
    _parse_mcp_processes,
    _parse_zuban_lsp_processes,
    find_mcp_server_processes,
    find_zuban_lsp_processes,
    list_server_status,
    restart_mcp_server,
    restart_zuban_lsp,
    stop_all_servers,
    stop_mcp_server,
    stop_process,
    stop_zuban_lsp,
)


# Fixed pid values used throughout the tests.
_PID_RUNNING = 4242
_PID_DEAD = 9999


def _ps_line(
    pid: int = _PID_RUNNING,
    user: str = "les",
    cpu: str = "1.0",
    mem: str = "0.5",
    command: str = "python -m crackerjack --start-mcp-server",
) -> str:
    """Build a fake ``ps aux`` line with the standard 10 metadata fields
    followed by the command — matching ``ps aux`` output:

        USER PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
    """
    # 10 metadata fields + command = 11+ parts.
    meta = ["?"] * 6  # VSZ RSS TTY STAT START TIME
    return f"{user} {pid} {cpu} {mem} {' '.join(meta)} {command}"


# ---------------------------------------------------------------------------
# _is_mcp_server_process / _is_zuban_lsp_process
# ---------------------------------------------------------------------------


def test_is_mcp_server_process_matches_all_three() -> None:
    line = "les 100 1.0 0.5 python -m crackerjack --start-mcp-server"
    assert _is_mcp_server_process(line) is True


def test_is_mcp_server_process_rejects_missing_cake() -> None:
    # Has python + crackerjack, but no --start-mcp-server flag.
    assert _is_mcp_server_process("les 100 1.0 0.5 python crackerjack") is False
    # Has crackerjack + --start-mcp-server, but no python.
    assert _is_mcp_server_process("les 100 1.0 0.5 crackerjack --start-mcp-server") is False
    # Has python + --start-mcp-server, but no crackerjack.
    assert _is_mcp_server_process("les 100 1.0 0.5 python --start-mcp-server") is False


def test_is_zuban_lsp_process_matches() -> None:
    assert _is_zuban_lsp_process("les 100 1.0 0.5 uv run zuban server") is True
    assert _is_zuban_lsp_process("les 100 1.0 0.5 python zuban_server.py") is True


def test_is_zuban_lsp_process_rejects_non_server() -> None:
    assert _is_zuban_lsp_process("les 100 1.0 0.5 python foo") is False
    assert _is_zuban_lsp_process("les 100 1.0 0.5 uv run something") is False


# ---------------------------------------------------------------------------
# _extract_process_info / _find_command_start_index
# ---------------------------------------------------------------------------


def test_extract_process_info_basic() -> None:
    line = _ps_line(command="python -m crackerjack --start-mcp-server")
    info = _extract_process_info(line)
    assert info is not None
    assert info["pid"] == _PID_RUNNING
    assert info["user"] == "les"
    assert info["cpu"] == "1.0"
    assert info["mem"] == "0.5"
    assert "crackerjack --start-mcp-server" in info["command"]


def test_extract_process_info_short_line_returns_none() -> None:
    line = "les 100 1.0 0.5 python -m foo"
    assert _extract_process_info(line) is None


def test_extract_process_info_invalid_pid_returns_none() -> None:
    line = f"les notanumber 1.0 0.5 {' '.join(['?'] * 6)} python -m crackerjack --start-mcp-server"
    assert _extract_process_info(line) is None


def test_find_command_start_index_default_when_no_python() -> None:
    """If no ``python`` token is present, the index defaults to 10."""
    parts = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"]
    assert _find_command_start_index(parts) == 10


def test_find_command_start_index_finds_python_token() -> None:
    parts = ["a", "b", "c", "d", "e", "python", "crackerjack"]
    assert _find_command_start_index(parts) == 5


def test_find_command_start_index_finds_Python_capitalized() -> None:
    parts = ["a", "b", "c", "d", "e", "f", "g", "Python", "crackerjack"]
    assert _find_command_start_index(parts) == 7


def test_find_command_start_index_uses_endswith_python() -> None:
    parts = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "/usr/bin/python"]
    assert _find_command_start_index(parts) == 10


# ---------------------------------------------------------------------------
# _parse_mcp_processes / _parse_zuban_lsp_processes
# ---------------------------------------------------------------------------


def test_parse_mcp_processes_extracts_one() -> None:
    line = _ps_line()
    processes = _parse_mcp_processes(line)
    assert len(processes) == 1
    assert processes[0]["pid"] == _PID_RUNNING


def test_parse_mcp_processes_skips_non_mcp_lines() -> None:
    noise = "les 100 1.0 0.5 bash\n"
    mcp = _ps_line(pid=200)
    out = _parse_mcp_processes(noise + mcp)
    assert len(out) == 1
    assert out[0]["pid"] == 200


def test_parse_zuban_lsp_processes_extracts_one() -> None:
    line = _ps_line(command="uv run zuban server")
    processes = _parse_zuban_lsp_processes(line)
    assert len(processes) == 1


def test_parse_zuban_lsp_processes_skips_non_zuban_lines() -> None:
    noise = "les 100 1.0 0.5 python foo\n"
    zuban = _ps_line(pid=300, command="uv run zuban server")
    out = _parse_zuban_lsp_processes(noise + zuban)
    assert len(out) == 1


# ---------------------------------------------------------------------------
# find_mcp_server_processes / find_zuban_lsp_processes — ps boundary
# ---------------------------------------------------------------------------


def test_find_mcp_server_processes_returns_parsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = SimpleNamespace(stdout=_ps_line())
    monkeypatch.setattr(
        server_manager, "execute_secure_subprocess", lambda **kw: fake
    )
    assert find_mcp_server_processes() == [
        _extract_process_info(_ps_line())
    ]


def test_find_mcp_server_processes_logs_and_returns_empty_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(**kw: object) -> object:
        raise RuntimeError("ps unavailable")

    monkeypatch.setattr(server_manager, "execute_secure_subprocess", _raise)
    assert find_mcp_server_processes() == []


def test_find_zuban_lsp_processes_returns_parsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = SimpleNamespace(stdout=_ps_line(command="uv run zuban server"))
    monkeypatch.setattr(
        server_manager, "execute_secure_subprocess", lambda **kw: fake
    )
    assert find_zuban_lsp_processes() == [
        _extract_process_info(_ps_line(command="uv run zuban server"))
    ]


def test_find_zuban_lsp_processes_logs_and_returns_empty_on_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise(**kw: object) -> object:
        raise RuntimeError("ps unavailable")

    monkeypatch.setattr(server_manager, "execute_secure_subprocess", _raise)
    assert find_zuban_lsp_processes() == []


# ---------------------------------------------------------------------------
# stop_process — escalation logic
# ---------------------------------------------------------------------------


def test_stop_process_terminates_gracefully(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SIGTERM sent first; if process exits, return True (no SIGKILL)."""
    kill_calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    monkeypatch.setattr(os, "kill", fake_kill)

    # First kill (SIGTERM, sent by stop_process). Second call (the os.kill
    # probe at line 141) raises OSError → process exited → return True.
    def _kill_or_raise(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))
        if (pid, sig) in {(pid, signal.SIGTERM)}:
            # First SIGTERM probe: process still running, no exception.
            if len(kill_calls) == 2:
                return
        # Second probe (after sleep) — process is gone.
        raise OSError("No such process")

    monkeypatch.setattr(os, "kill", _kill_or_raise)
    # Avoid the real sleep.
    monkeypatch.setattr(server_manager.time, "sleep", lambda s: None)
    assert stop_process(_PID_RUNNING) is True
    # Both SIGTERM and SIGTERM-probe (kill(pid, 0)) were attempted.
    assert any(call[1] == signal.SIGTERM for call in kill_calls)


def test_stop_process_force_uses_sigkill(monkeypatch: pytest.MonkeyPatch) -> None:
    """``force=True`` sends SIGKILL first."""
    kill_calls: list[tuple[int, int]] = []

    def _kill_or_raise(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))
        # Raise on probe to short-circuit the wait loop.
        if sig == 0:
            raise OSError("process gone")

    monkeypatch.setattr(os, "kill", _kill_or_raise)
    monkeypatch.setattr(server_manager.time, "sleep", lambda s: None)
    assert stop_process(_PID_RUNNING, force=True) is True
    assert kill_calls[0] == (_PID_RUNNING, signal.SIGKILL)


def test_stop_process_escalates_to_sigkill_when_sigterm_does_not_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After 10 SIGTERM-probes never raise, escalate to SIGKILL."""
    kill_calls: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        kill_calls.append((pid, sig))

    monkeypatch.setattr(os, "kill", fake_kill)
    monkeypatch.setattr(server_manager.time, "sleep", lambda s: None)
    assert stop_process(_PID_RUNNING, force=False) is True
    # 1 initial SIGTERM (line 137), 10 probes with sig=0 (line 141),
    # 1 escalation SIGKILL (line 147).
    sigterm_count = sum(1 for _p, sig in kill_calls if sig == signal.SIGTERM)
    sigkill_count = sum(1 for _p, sig in kill_calls if sig == signal.SIGKILL)
    probe_count = sum(1 for _p, sig in kill_calls if sig == 0)
    assert sigterm_count == 1  # the initial SIGTERM
    assert probe_count == 10  # 10 ``os.kill(pid, 0)`` probes
    assert sigkill_count == 1  # escalation SIGKILL


def test_stop_process_returns_true_when_process_already_dead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If ``os.kill`` raises ``OSError`` on the first call, return ``True``."""

    def _always_raise(pid: int, sig: int) -> None:
        raise OSError("No such process")

    monkeypatch.setattr(os, "kill", _always_raise)
    assert stop_process(_PID_DEAD) is True


# ---------------------------------------------------------------------------
# stop_mcp_server / stop_zuban_lsp
# ---------------------------------------------------------------------------


def test_stop_mcp_server_no_processes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty process list prints a warning and returns True."""
    monkeypatch.setattr(server_manager, "find_mcp_server_processes", lambda: [])
    assert stop_mcp_server() is True


def test_stop_mcp_server_stops_each_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    procs = [{"pid": 1, "command": "x", "user": "u", "cpu": "1", "mem": "2"}]
    monkeypatch.setattr(server_manager, "find_mcp_server_processes", lambda: procs)
    monkeypatch.setattr(server_manager, "stop_process", lambda pid, force=False: True)
    assert stop_mcp_server() is True


def test_stop_mcp_server_records_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    procs = [{"pid": 1, "command": "x", "user": "u", "cpu": "1", "mem": "2"}]
    monkeypatch.setattr(server_manager, "find_mcp_server_processes", lambda: procs)
    monkeypatch.setattr(server_manager, "stop_process", lambda pid, force=False: False)
    assert stop_mcp_server() is False


def test_stop_zuban_lsp_no_processes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(server_manager, "find_zuban_lsp_processes", lambda: [])
    assert stop_zuban_lsp() is True


def test_stop_zuban_lsp_stops_each_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    procs = [{"pid": 1, "command": "x", "user": "u", "cpu": "1", "mem": "2"}]
    monkeypatch.setattr(server_manager, "find_zuban_lsp_processes", lambda: procs)
    monkeypatch.setattr(server_manager, "stop_process", lambda pid, force=False: True)
    assert stop_zuban_lsp() is True


def test_stop_zuban_lsp_records_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    procs = [{"pid": 1, "command": "x", "user": "u", "cpu": "1", "mem": "2"}]
    monkeypatch.setattr(server_manager, "find_zuban_lsp_processes", lambda: procs)
    monkeypatch.setattr(server_manager, "stop_process", lambda pid, force=False: False)
    assert stop_zuban_lsp() is False


def test_stop_all_servers_both_succeed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server_manager, "stop_mcp_server", lambda: True)
    monkeypatch.setattr(server_manager, "stop_zuban_lsp", lambda: True)
    assert stop_all_servers() is True


def test_stop_all_servers_zuban_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server_manager, "stop_mcp_server", lambda: True)
    monkeypatch.setattr(server_manager, "stop_zuban_lsp", lambda: False)
    assert stop_all_servers() is False


# ---------------------------------------------------------------------------
# restart_mcp_server / restart_zuban_lsp — Popen boundary
# ---------------------------------------------------------------------------


def test_restart_mcp_server_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """restart_mcp_server calls ServerPanels, sleep, Popen, then ServerPanels.

    The function does ``import subprocess`` inside its body, so we patch
    ``subprocess.Popen`` directly (it's the same module the function ends
    up importing).
    """
    import subprocess

    monkeypatch.setattr(server_manager, "stop_mcp_server", lambda: True)
    monkeypatch.setattr(server_manager.time, "sleep", lambda s: None)

    fake_proc = SimpleNamespace(pid=12345)

    class _FakePopen:
        def __init__(self, *a: object, **kw: object) -> None:
            self.pid = fake_proc.pid

    monkeypatch.setattr(subprocess, "Popen", _FakePopen)
    assert restart_mcp_server() is True


def test_restart_mcp_server_handles_popen_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    monkeypatch.setattr(server_manager, "stop_mcp_server", lambda: True)
    monkeypatch.setattr(server_manager.time, "sleep", lambda s: None)

    def _raise(*a: object, **kw: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "Popen", _raise)
    assert restart_mcp_server() is False


def test_restart_zuban_lsp_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    monkeypatch.setattr(server_manager, "stop_zuban_lsp", lambda: True)
    monkeypatch.setattr(server_manager.time, "sleep", lambda s: None)

    class _FakePopen:
        def __init__(self, *a: object, **kw: object) -> None:
            self.pid = 99999

    monkeypatch.setattr(subprocess, "Popen", _FakePopen)
    assert restart_zuban_lsp() is True


def test_restart_zuban_lsp_handles_popen_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    monkeypatch.setattr(server_manager, "stop_zuban_lsp", lambda: True)
    monkeypatch.setattr(server_manager.time, "sleep", lambda s: None)

    def _raise(*a: object, **kw: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(subprocess, "Popen", _raise)
    assert restart_zuban_lsp() is False


# ---------------------------------------------------------------------------
# list_server_status
# ---------------------------------------------------------------------------


def test_list_server_status_no_processes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No processes → all three 'no servers' branches fire."""
    monkeypatch.setattr(server_manager, "find_mcp_server_processes", lambda: [])
    monkeypatch.setattr(server_manager, "find_zuban_lsp_processes", lambda: [])
    list_server_status()  # must not raise


def test_list_server_status_with_processes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    procs = [{"pid": 1, "command": "x", "user": "u", "cpu": "1.0", "mem": "0.5"}]
    monkeypatch.setattr(server_manager, "find_mcp_server_processes", lambda: procs)
    monkeypatch.setattr(server_manager, "find_zuban_lsp_processes", lambda: procs)
    list_server_status()  # must not raise

"""Tests for ``crackerjack.cli.lifecycle_handlers``.

Covers three CLI handlers:
- ``start_handler`` — boots the MCP server via ``mcp_main``
- ``stop_handler`` — graceful SIGTERM → SIGKILL escalation
- ``health_probe_handler`` — reads + validates runtime health snapshot

Tests mock at the OS/process boundary (``os.kill``, ``time.sleep``) and
the runtime health boundary (``read_runtime_health``) so the orchestration
logic is exercised without spawning real processes.
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.cli import lifecycle_handlers
from crackerjack.cli.lifecycle_handlers import (
    health_probe_handler,
    start_handler,
    stop_handler,
)


# ---------------------------------------------------------------------------
# start_handler
# ---------------------------------------------------------------------------


def test_start_handler_calls_mcp_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """start_handler invokes ``crackerjack.mcp.server_core.main``."""
    import sys

    called: dict[str, object] = {}

    def fake_mcp_main(cwd: str, http_mode: bool, http_port: int | None) -> None:
        called["cwd"] = cwd
        called["http_mode"] = http_mode
        called["http_port"] = http_port

    # Patch the import target inside the function body.
    fake_module = MagicMock()
    fake_module.main = fake_mcp_main
    monkeypatch.setitem(sys.modules, "crackerjack.mcp.server_core", fake_module)
    start_handler()
    assert called == {"cwd": ".", "http_mode": False, "http_port": None}


# ---------------------------------------------------------------------------
# stop_handler
# ---------------------------------------------------------------------------


def test_stop_handler_uses_default_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no console is provided, the handler instantiates one."""
    # Process not found immediately → returns after one os.kill probe.
    def fake_kill(pid: int, sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr(os, "kill", fake_kill)
    # Should NOT raise despite no console arg.
    stop_handler(9999)


def test_stop_handler_process_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    """If ``os.kill(pid, 0)`` raises ProcessLookupError, log + return."""
    console = MagicMock()
    monkeypatch.setattr(os, "kill", MagicMock(side_effect=ProcessLookupError))
    stop_handler(9999, console=console)
    console.print.assert_any_call("[yellow]Process 9999 not found[/yellow]")


def test_stop_handler_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    """Process exits after SIGTERM (second probe raises ProcessLookupError)."""
    console = MagicMock()
    call_count = [0]

    def fake_kill(pid: int, sig: int) -> None:
        call_count[0] += 1
        # First call (probe) returns ok. Second call (SIGTERM) returns ok.
        # Third call (probe after SIGTERM) raises → process exited.
        if call_count[0] >= 3:
            raise ProcessLookupError

    monkeypatch.setattr(os, "kill", fake_kill)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    stop_handler(1234, console=console)
    console.print.assert_any_call("[green]Server stopped gracefully[/green]")


def test_stop_handler_escalates_to_sigkill(monkeypatch: pytest.MonkeyPatch) -> None:
    """Process never exits → SIGKILL after 100 probes."""
    console = MagicMock()
    sigs: list[int] = []

    def fake_kill(pid: int, sig: int) -> None:
        sigs.append(sig)

    monkeypatch.setattr(os, "kill", fake_kill)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    stop_handler(1234, console=console)
    # Expect: 1 probe (0), 1 SIGTERM, 100 SIGTERM-probes (0), 1 SIGKILL.
    assert signal.SIGTERM in sigs
    assert signal.SIGKILL in sigs
    assert sigs.count(0) == 101  # 1 initial probe + 100 probes
    console.print.assert_any_call("[red]Process 1234 did not stop gracefully, sending SIGKILL...[/red]")


def test_stop_handler_sigkill_process_disappears(monkeypatch: pytest.MonkeyPatch) -> None:
    """SIGKILL raises ProcessLookupError → print 'Server stopped'."""
    console = MagicMock()

    def fake_kill(pid: int, sig: int) -> None:
        # All probes succeed; SIGKILL itself raises.
        if sig == signal.SIGKILL:
            raise ProcessLookupError

    monkeypatch.setattr(os, "kill", fake_kill)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    stop_handler(1234, console=console)
    console.print.assert_any_call("[green]Server stopped[/green]")


def test_stop_handler_sigkill_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """SIGKILL succeeds → 'Server forcefully stopped'."""
    console = MagicMock()
    monkeypatch.setattr(os, "kill", MagicMock())
    monkeypatch.setattr(time, "sleep", lambda s: None)
    stop_handler(1234, console=console)
    console.print.assert_any_call("[yellow]Server forcefully stopped[/yellow]")


# ---------------------------------------------------------------------------
# health_probe_handler
# ---------------------------------------------------------------------------


def test_health_probe_handler_missing_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Snapshot file doesn't exist → RuntimeError."""
    fake_settings = MagicMock()
    fake_settings.health_snapshot_path.return_value = tmp_path / "missing.json"
    fake_settings.health_ttl_seconds = 60
    monkeypatch.setattr(
        lifecycle_handlers, "CrackerjackMCPSettings", MagicMock(load_for_crackerjack=lambda: fake_settings)
    )
    with pytest.raises(RuntimeError, match="Health snapshot not found"):
        health_probe_handler()


def test_health_probe_handler_invalid_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``read_runtime_health`` returns None → RuntimeError 'Invalid'."""
    p = tmp_path / "h.json"
    p.write_text("{}")
    fake_settings = MagicMock()
    fake_settings.health_snapshot_path.return_value = p
    fake_settings.health_ttl_seconds = 60
    monkeypatch.setattr(
        lifecycle_handlers, "CrackerjackMCPSettings", MagicMock(load_for_crackerjack=lambda: fake_settings)
    )
    monkeypatch.setattr(lifecycle_handlers, "read_runtime_health", lambda path: None)
    with pytest.raises(RuntimeError, match="Invalid health snapshot"):
        health_probe_handler()


def test_health_probe_handler_stale_snapshot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Snapshot mtime > TTL seconds old → RuntimeError 'stale'."""
    p = tmp_path / "h.json"
    p.write_text("{}")
    # Force mtime to 1 hour ago.
    old_time = time.time() - 3600
    os.utime(p, (old_time, old_time))

    fake_settings = MagicMock()
    fake_settings.health_snapshot_path.return_value = p
    fake_settings.health_ttl_seconds = 60  # 1-minute TTL
    monkeypatch.setattr(
        lifecycle_handlers, "CrackerjackMCPSettings", MagicMock(load_for_crackerjack=lambda: fake_settings)
    )

    snap = MagicMock(orchestrator_pid=1234, watchers_running=2, lifecycle_state="running")
    monkeypatch.setattr(lifecycle_handlers, "read_runtime_health", lambda path: snap)

    with pytest.raises(RuntimeError, match="stale"):
        health_probe_handler()


def test_health_probe_handler_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Valid fresh snapshot → returns MCPRuntimeHealthSnapshot."""
    p = tmp_path / "h.json"
    p.write_text("{}")

    fake_settings = MagicMock()
    fake_settings.health_snapshot_path.return_value = p
    fake_settings.health_ttl_seconds = 60
    monkeypatch.setattr(
        lifecycle_handlers, "CrackerjackMCPSettings", MagicMock(load_for_crackerjack=lambda: fake_settings)
    )

    snap = MagicMock(orchestrator_pid=1234, watchers_running=2, lifecycle_state="running")
    monkeypatch.setattr(lifecycle_handlers, "read_runtime_health", lambda path: snap)

    out = health_probe_handler()
    assert out.orchestrator_pid == 1234
    assert out.watchers_running == 2
    assert out.lifecycle_state == "running"


# ---------------------------------------------------------------------------
# __all__ surface
# ---------------------------------------------------------------------------


def test_module_dunder_all() -> None:
    assert lifecycle_handlers.__all__ == [
        "health_probe_handler",
        "start_handler",
        "stop_handler",
    ]

from __future__ import annotations

import logging
import os
import signal
import time

from mcp_common.cli.health import RuntimeHealthSnapshot as MCPRuntimeHealthSnapshot
from rich.console import Console

from crackerjack.config.mcp_settings_adapter import CrackerjackMCPSettings
from crackerjack.runtime import (
    read_runtime_health,
)

logger = logging.getLogger(__name__)
console = Console()


def start_handler() -> None:
    from crackerjack.mcp.server_core import main as mcp_main

    mcp_main(".", http_mode=False, http_port=None)


def stop_handler(pid: int) -> None:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        console.print(f"[yellow]Process {pid} not found[/yellow]")
        return

    console.print(f"[yellow]Sending SIGTERM to process {pid}...[/yellow]")
    os.kill(pid, signal.SIGTERM)

    for _ in range(100):
        try:
            os.kill(pid, 0)
            time.sleep(0.1)
        except ProcessLookupError:
            console.print("[green]Server stopped gracefully[/green]")
            return

    console.print(
        f"[red]Process {pid} did not stop gracefully, sending SIGKILL...[/red]"
    )
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
        console.print("[yellow]Server forcefully stopped[/yellow]")
    except ProcessLookupError:
        console.print("[green]Server stopped[/green]")


def health_probe_handler() -> MCPRuntimeHealthSnapshot:
    settings = CrackerjackMCPSettings.load_for_crackerjack()
    health_path = settings.health_snapshot_path()

    if not health_path.exists():
        msg = f"Health snapshot not found: {health_path} (server may not be running)"
        raise RuntimeError(msg)

    snapshot = read_runtime_health(health_path)
    if snapshot is None:
        msg = f"Invalid health snapshot: {health_path}"
        raise RuntimeError(msg)

    if health_path.stat().st_mtime < time.time() - settings.health_ttl_seconds:
        msg = f"Health snapshot is stale (>{settings.health_ttl_seconds}s old)"
        raise RuntimeError(msg)

    return MCPRuntimeHealthSnapshot(
        orchestrator_pid=snapshot.orchestrator_pid,
        watchers_running=snapshot.watchers_running,
        lifecycle_state=snapshot.lifecycle_state,
    )


__all__ = ["start_handler", "stop_handler", "health_probe_handler"]

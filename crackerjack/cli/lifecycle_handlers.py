"""MCP Server lifecycle handlers for Crackerjack.

Implements start/stop/health handlers for integration with mcp-common's
MCPServerCLIFactory. These handlers bridge Crackerjack's server implementation
to the Oneiric CLI lifecycle management pattern.
"""

from __future__ import annotations

import logging
import os
import signal
import time

from rich.console import Console

from crackerjack.config.mcp_settings_adapter import CrackerjackMCPSettings
from crackerjack.runtime import (
    RuntimeHealthSnapshot,
    read_runtime_health,
)

logger = logging.getLogger(__name__)
console = Console()


def start_handler() -> None:
    """Start Crackerjack MCP server with Oneiric lifecycle management.

    This handler:
    1. Loads CrackerjackSettings (ACB-based app config)
    2. Starts the actual MCP server with mcp-common integration

    Example:
        >>> start_handler()
    """
    # Start the actual MCP server with mcp-common and Oneiric integration
    from crackerjack.mcp.server_core import main as mcp_main

    mcp_main(".", http_mode=False, http_port=None)


def stop_handler(pid: int) -> None:
    """Stop Crackerjack MCP server using PID.

    This handler:
    1. Sends SIGTERM to the process
    2. Waits for graceful shutdown (up to 10 seconds)
    3. Falls back to SIGKILL if needed

    Args:
        pid: Process ID to stop

    Raises:
        RuntimeError: If process not found

    Example:
        >>> stop_handler(12345)
    """
    try:
        # Check if process exists
        os.kill(pid, 0)
    except ProcessLookupError:
        console.print(f"[yellow]Process {pid} not found[/yellow]")
        return

    # Send SIGTERM for graceful shutdown
    console.print(f"[yellow]Sending SIGTERM to process {pid}...[/yellow]")
    os.kill(pid, signal.SIGTERM)

    # Wait for process to exit (up to 10 seconds)
    for _ in range(100):  # 100 * 0.1s = 10 seconds
        try:
            os.kill(pid, 0)  # Check if process still exists
            time.sleep(0.1)
        except ProcessLookupError:
            console.print("[green]Server stopped gracefully[/green]")
            return

    # If still running after 10 seconds, force kill
    console.print(
        f"[red]Process {pid} did not stop gracefully, sending SIGKILL...[/red]"
    )
    try:
        os.kill(pid, signal.SIGKILL)
        time.sleep(0.5)
        console.print("[yellow]Server forcefully stopped[/yellow]")
    except ProcessLookupError:
        # Process exited between checks
        console.print("[green]Server stopped[/green]")


def health_probe_handler() -> RuntimeHealthSnapshot:
    """Get health snapshot from running Crackerjack MCP server.

    This handler reads the health snapshot JSON file written by the running
    server. Used for liveness/readiness probes.

    Returns:
        RuntimeHealthSnapshot from running server

    Raises:
        RuntimeError: If health snapshot not found or stale

    Example:
        >>> snapshot = health_probe_handler()
        >>> print(snapshot.orchestrator_pid)
        12345
    """
    # Load settings to get health snapshot path
    settings = CrackerjackMCPSettings.load_for_crackerjack()
    health_path = settings.health_snapshot_path()

    if not health_path.exists():
        msg = f"Health snapshot not found: {health_path} (server may not be running)"
        raise RuntimeError(msg)

    snapshot = read_runtime_health(health_path)
    if snapshot is None:
        msg = f"Invalid health snapshot: {health_path}"
        raise RuntimeError(msg)

    # Check snapshot freshness (TTL from settings)
    if health_path.stat().st_mtime < time.time() - settings.health_ttl_seconds:
        msg = f"Health snapshot is stale (>{settings.health_ttl_seconds}s old)"
        raise RuntimeError(msg)

    return snapshot


__all__ = ["start_handler", "stop_handler", "health_probe_handler"]

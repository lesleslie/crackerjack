"""CLI handlers for monitoring, server, and LSP commands.

This module contains command coordinators for:
- Monitoring modes (monitor, enhanced_monitor, dashboard, watchdog)
- WebSocket server lifecycle (start, stop, restart)
- MCP server lifecycle (start, stop, restart)
- Zuban LSP lifecycle (start, stop, restart)
"""

import asyncio
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends


@depends.inject  # type: ignore[misc]
def handle_mcp_server(
    websocket_port: int | None = None, console: Inject[Console] = None
) -> None:
    from crackerjack.mcp.server import main as start_mcp_main

    project_path = str(Path.cwd())

    if websocket_port:
        start_mcp_main(project_path, websocket_port)
    else:
        start_mcp_main(project_path)


@depends.inject  # type: ignore[misc]
def handle_monitor_mode(
    dev_mode: bool = False, console: Inject[Console] = None
) -> None:
    from crackerjack.mcp.progress_monitor import run_progress_monitor

    console.print("[bold cyan]🌟 Starting Multi-Project Progress Monitor[/ bold cyan]")
    console.print(
        "[bold yellow]🐕 With integrated Service Watchdog and WebSocket polling[/ bold yellow]",
    )

    try:
        asyncio.run(run_progress_monitor(dev_mode=dev_mode))
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Monitor stopped[/ yellow]")


@depends.inject  # type: ignore[misc]
def handle_enhanced_monitor_mode(
    dev_mode: bool = False, console: Inject[Console] = None
) -> None:
    from crackerjack.mcp.enhanced_progress_monitor import run_enhanced_progress_monitor

    console.print("[bold magenta]✨ Starting Enhanced Progress Monitor[/ bold magenta]")
    console.print(
        "[bold cyan]📊 With advanced MetricCard widgets and modern web UI patterns[/ bold cyan]",
    )

    try:
        asyncio.run(run_enhanced_progress_monitor(dev_mode=dev_mode))
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Enhanced Monitor stopped[/ yellow]")


@depends.inject  # type: ignore[misc]
def handle_dashboard_mode(
    dev_mode: bool = False, console: Inject[Console] = None
) -> None:
    from crackerjack.mcp.dashboard import run_dashboard

    console.print("[bold green]🎯 Starting Comprehensive Dashboard[/ bold green]")
    console.print(
        "[bold cyan]📈 With system metrics, job tracking, and performance monitoring[/ bold cyan]",
    )

    try:
        run_dashboard()
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Dashboard stopped[/ yellow]")


@depends.inject  # type: ignore[misc]
def handle_unified_dashboard_mode(
    port: int = 8675, dev_mode: bool = False, console: Inject[Console] = None
) -> None:
    from crackerjack.monitoring.websocket_server import CrackerjackMonitoringServer

    console.print("[bold green]🚀 Starting Unified Monitoring Dashboard[/bold green]")
    console.print(
        f"[bold cyan]🌐 WebSocket server on port {port} with real-time streaming and web UI[/bold cyan]",
    )

    try:
        server = CrackerjackMonitoringServer()
        asyncio.run(server.start_monitoring(port))
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Unified Dashboard stopped[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Unified Dashboard failed: {e}[/red]")


@depends.inject  # type: ignore[misc]
def handle_watchdog_mode(console: Inject[Console] = None) -> None:
    from crackerjack.mcp.service_watchdog import main as start_watchdog

    try:
        asyncio.run(start_watchdog())
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Watchdog stopped[/ yellow]")


def handle_start_websocket_server(port: int = 8675) -> None:
    from crackerjack.mcp.websocket.server import handle_websocket_server_command

    handle_websocket_server_command(start=True, port=port)


def handle_stop_websocket_server() -> None:
    from crackerjack.mcp.websocket.server import handle_websocket_server_command

    handle_websocket_server_command(stop=True)


def handle_restart_websocket_server(port: int = 8675) -> None:
    from crackerjack.mcp.websocket.server import handle_websocket_server_command

    handle_websocket_server_command(restart=True, port=port)


@depends.inject  # type: ignore[misc]
def handle_stop_mcp_server(console: Inject[Console] = None) -> None:
    from crackerjack.services.server_manager import (
        list_server_status,
        stop_all_servers,
    )

    console.print("[bold red]🛑 Stopping MCP Servers[/ bold red]")

    list_server_status(console)

    if stop_all_servers(console):
        console.print("\n[bold green]✅ All servers stopped successfully[/ bold green]")
    else:
        console.print("\n[bold red]❌ Some servers failed to stop[/ bold red]")
        raise SystemExit(1)


@depends.inject  # type: ignore[misc]
def handle_restart_mcp_server(
    websocket_port: int | None = None, console: Inject[Console] = None
) -> None:
    from crackerjack.services.server_manager import restart_mcp_server

    if restart_mcp_server(websocket_port, console):
        console.print("\n[bold green]✅ MCP server restart completed[/ bold green]")
    else:
        console.print("\n[bold red]❌ MCP server restart failed[/ bold red]")
        raise SystemExit(1)


@depends.inject  # type: ignore[misc]
def handle_start_zuban_lsp(
    port: int = 8677, mode: str = "tcp", console: Inject[Console] = None
) -> None:
    """Start Zuban LSP server."""
    from crackerjack.services.zuban_lsp_service import (
        create_zuban_lsp_service,
    )

    console.print("[bold cyan]🚀 Starting Zuban LSP Server[/bold cyan]")

    async def _start() -> None:
        lsp_service = await create_zuban_lsp_service(
            port=port, mode=mode, console=console
        )
        if await lsp_service.start():
            console.print(
                f"[bold green]✅ Zuban LSP server started on port {port} ({mode} mode)[/bold green]"
            )
        else:
            console.print("[bold red]❌ Failed to start Zuban LSP server[/bold red]")
            raise SystemExit(1)

    try:
        asyncio.run(_start())
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Zuban LSP startup interrupted[/yellow]")


@depends.inject  # type: ignore[misc]
def handle_stop_zuban_lsp(console: Inject[Console] = None) -> None:
    """Stop Zuban LSP server."""
    from crackerjack.services.server_manager import stop_zuban_lsp

    console.print("[bold red]🛑 Stopping Zuban LSP Server[/bold red]")

    if stop_zuban_lsp(console):
        console.print(
            "\n[bold green]✅ Zuban LSP server stopped successfully[/bold green]"
        )
    else:
        console.print("\n[bold red]❌ Failed to stop Zuban LSP server[/bold red]")
        raise SystemExit(1)


@depends.inject  # type: ignore[misc]
def handle_restart_zuban_lsp(
    port: int = 8677, mode: str = "tcp", console: Inject[Console] = None
) -> None:
    """Restart Zuban LSP server."""
    from crackerjack.services.server_manager import restart_zuban_lsp

    if restart_zuban_lsp(console):
        console.print(
            "\n[bold green]✅ Zuban LSP server restart completed[/bold green]"
        )
    else:
        console.print("\n[bold red]❌ Zuban LSP server restart failed[/bold red]")
        raise SystemExit(1)


def handle_monitoring_commands(
    monitor: bool,
    enhanced_monitor: bool,
    dashboard: bool,
    unified_dashboard: bool,
    unified_dashboard_port: int | None,
    watchdog: bool,
    dev: bool,
) -> bool:
    """Route monitoring and dashboard commands to appropriate handlers."""
    if monitor:
        handle_monitor_mode(dev_mode=dev)
        return True
    if enhanced_monitor:
        handle_enhanced_monitor_mode(dev_mode=dev)
        return True
    if dashboard:
        handle_dashboard_mode(dev_mode=dev)
        return True
    if unified_dashboard:
        port = unified_dashboard_port or 8675
        handle_unified_dashboard_mode(port=port, dev_mode=dev)
        return True
    if watchdog:
        handle_watchdog_mode()
        return True
    return False


def handle_websocket_commands(
    start_websocket_server: bool,
    stop_websocket_server: bool,
    restart_websocket_server: bool,
    websocket_port: int | None,
) -> bool:
    """Route WebSocket server lifecycle commands to appropriate handlers."""
    if start_websocket_server:
        port = websocket_port or 8675
        handle_start_websocket_server(port)
        return True
    if stop_websocket_server:
        handle_stop_websocket_server()
        return True
    if restart_websocket_server:
        port = websocket_port or 8675
        handle_restart_websocket_server(port)
        return True
    return False


def handle_mcp_commands(
    start_mcp_server: bool,
    stop_mcp_server: bool,
    restart_mcp_server: bool,
    websocket_port: int | None,
) -> bool:
    """Route MCP server lifecycle commands to appropriate handlers."""
    if start_mcp_server:
        handle_mcp_server(websocket_port)
        return True
    if stop_mcp_server:
        handle_stop_mcp_server()
        return True
    if restart_mcp_server:
        handle_restart_mcp_server(websocket_port)
        return True
    return False


def handle_zuban_lsp_commands(
    start_zuban_lsp: bool,
    stop_zuban_lsp: bool,
    restart_zuban_lsp: bool,
    zuban_lsp_port: int,
    zuban_lsp_mode: str,
) -> bool:
    """Route Zuban LSP lifecycle commands to appropriate handlers."""
    if start_zuban_lsp:
        handle_start_zuban_lsp(port=zuban_lsp_port, mode=zuban_lsp_mode)
        return True
    if stop_zuban_lsp:
        handle_stop_zuban_lsp()
        return True
    if restart_zuban_lsp:
        handle_restart_zuban_lsp(port=zuban_lsp_port, mode=zuban_lsp_mode)
        return True
    return False


def handle_server_commands(
    monitor: bool,
    enhanced_monitor: bool,
    dashboard: bool,
    unified_dashboard: bool,
    unified_dashboard_port: int | None,
    watchdog: bool,
    start_websocket_server: bool,
    stop_websocket_server: bool,
    restart_websocket_server: bool,
    start_mcp_server: bool,
    stop_mcp_server: bool,
    restart_mcp_server: bool,
    websocket_port: int | None,
    start_zuban_lsp: bool,
    stop_zuban_lsp: bool,
    restart_zuban_lsp: bool,
    zuban_lsp_port: int,
    zuban_lsp_mode: str,
    dev: bool,
) -> bool:
    """Master coordinator for all server-related commands.

    Routes to:
    - handle_monitoring_commands (monitor, dashboard, watchdog)
    - handle_websocket_commands (WebSocket server lifecycle)
    - handle_mcp_commands (MCP server lifecycle)
    - handle_zuban_lsp_commands (LSP server lifecycle)

    Returns True if any server command was handled.
    """
    return (
        handle_monitoring_commands(
            monitor,
            enhanced_monitor,
            dashboard,
            unified_dashboard,
            unified_dashboard_port,
            watchdog,
            dev,
        )
        or handle_websocket_commands(
            start_websocket_server,
            stop_websocket_server,
            restart_websocket_server,
            websocket_port,
        )
        or handle_mcp_commands(
            start_mcp_server,
            stop_mcp_server,
            restart_mcp_server,
            websocket_port,
        )
        or handle_zuban_lsp_commands(
            start_zuban_lsp,
            stop_zuban_lsp,
            restart_zuban_lsp,
            zuban_lsp_port,
            zuban_lsp_mode,
        )
    )

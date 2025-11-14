"""CLI handlers for monitoring, server, and LSP commands.

This module contains command coordinators for:
- Monitoring modes (monitor, enhanced_monitor, dashboard, watchdog)
- WebSocket server lifecycle (start, stop, restart)
- MCP server lifecycle (start, stop, restart)
- Zuban LSP lifecycle (start, stop, restart)
"""

from ..handlers import (
    handle_dashboard_mode,
    handle_enhanced_monitor_mode,
    handle_mcp_server,
    handle_monitor_mode,
    handle_restart_mcp_server,
    handle_restart_websocket_server,
    handle_restart_zuban_lsp,
    handle_start_websocket_server,
    handle_start_zuban_lsp,
    handle_stop_mcp_server,
    handle_stop_websocket_server,
    handle_stop_zuban_lsp,
    handle_unified_dashboard_mode,
    handle_watchdog_mode,
)


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

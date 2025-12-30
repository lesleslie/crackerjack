import os
import signal
import sys
import time
import typing as t
from pathlib import Path

from mcp_common.ui import ServerPanels

from .secure_subprocess import execute_secure_subprocess
from .security_logger import get_security_logger


def find_mcp_server_processes() -> list[dict[str, t.Any]]:
    security_logger = get_security_logger()

    try:
        result = execute_secure_subprocess(
            command=["ps", "aux"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10.0,
        )

        return _parse_mcp_processes(result.stdout)

    except Exception as e:
        security_logger.log_subprocess_failure(
            command=["ps", "aux"],
            exit_code=-1,
            error_output=str(e),
        )
        return []


def _parse_mcp_processes(stdout: str) -> list[dict[str, t.Any]]:
    processes: list[dict[str, t.Any]] = []
    str(Path.cwd())

    for line in stdout.splitlines():
        if _is_mcp_server_process(line):
            process_info = _extract_process_info(line)
            if process_info:
                processes.append(process_info)

    return processes


def _is_mcp_server_process(line: str) -> bool:
    return (
        "crackerjack" in line
        and "--start-mcp-server" in line
        and "python" in line.lower()
    )


def _is_zuban_lsp_process(line: str) -> bool:
    return (
        "zuban" in line
        and "server" in line
        and ("uv" in line.lower() or "python" in line.lower())
    )


def _extract_process_info(line: str) -> dict[str, t.Any] | None:
    parts = line.split()
    if len(parts) < 11:
        return None

    try:
        pid = int(parts[1])

        command_start_index = _find_command_start_index(parts)

        return {
            "pid": pid,
            "command": " ".join(parts[command_start_index:]),
            "user": parts[0],
            "cpu": parts[2],
            "mem": parts[3],
        }
    except (ValueError, IndexError):
        return None


def _find_command_start_index(parts: list[str]) -> int:
    command_start_index = 10
    for i, part in enumerate(parts):
        if part.endswith("python") or "Python" in part:
            command_start_index = i
            break
    return command_start_index


# Phase 1: find_websocket_server_processes() removed (WebSocket stack deleted)


def find_zuban_lsp_processes() -> list[dict[str, t.Any]]:
    """Find running zuban LSP server processes."""
    security_logger = get_security_logger()

    try:
        result = execute_secure_subprocess(
            command=["ps", "aux"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10.0,
        )

        return _parse_zuban_lsp_processes(result.stdout)

    except Exception as e:
        security_logger.log_subprocess_failure(
            command=["ps", "aux"],
            exit_code=-1,
            error_output=str(e),
        )
        return []


def _parse_zuban_lsp_processes(stdout: str) -> list[dict[str, t.Any]]:
    """Parse zuban LSP processes from ps output."""
    processes: list[dict[str, t.Any]] = []

    for line in stdout.splitlines():
        if _is_zuban_lsp_process(line):
            process_info = _extract_process_info(line)
            if process_info:
                processes.append(process_info)

    return processes


def stop_process(pid: int, force: bool = False) -> bool:
    try:
        if force:
            os.kill(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGTERM)

        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                return True

        if not force:
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)

        return True

    except (OSError, ProcessLookupError):
        return True


def stop_mcp_server() -> bool:
    processes = find_mcp_server_processes()

    if not processes:
        console.print("[yellow]⚠️ No MCP server processes found[/ yellow]")
        return True

    ServerPanels.info(
        title="MCP Server", message=f"Stopping {len(processes)} process(es)"
    )

    success = True
    for proc in processes:
        console.print(f"Stopping process {proc['pid']}...")
        if stop_process(proc["pid"]):
            console.print(f"✅ Process {proc['pid']} terminated gracefully")
        else:
            console.print(f"❌ Failed to stop process {proc['pid']}")
            success = False

    if success:
        ServerPanels.info(
            title="MCP Server",
            message=f"Successfully stopped {len(processes)} process(es)",
        )

    return success


# Phase 1: stop_websocket_server() removed (WebSocket stack deleted)
def stop_zuban_lsp() -> bool:
    """Stop running zuban LSP server processes."""
    processes = find_zuban_lsp_processes()

    if not processes:
        console.print("[yellow]⚠️ No Zuban LSP server processes found[/ yellow]")
        return True

    success = True
    for proc in processes:
        console.print(f"🛑 Stopping Zuban LSP server process {proc['pid']}")
        if stop_process(proc["pid"]):
            console.print(f"✅ Stopped process {proc['pid']}")
        else:
            console.print(f"❌ Failed to stop process {proc['pid']}")
            success = False

    return success


def stop_all_servers() -> bool:
    # Phase 1: stop_websocket_server() call removed (WebSocket stack deleted)
    mcp_success = stop_mcp_server()
    zuban_lsp_success = stop_zuban_lsp()

    return mcp_success and zuban_lsp_success


def restart_mcp_server() -> bool:
    ServerPanels.info(
        title="MCP Server", message="Restarting Crackerjack MCP Server..."
    )

    stop_mcp_server()

    ServerPanels.simple_message("⏳ Waiting for cleanup...", style="dim")
    time.sleep(2)

    ServerPanels.simple_message("🚀 Starting new server instance...", style="green")
    try:
        cmd = [sys.executable, "-m", "crackerjack", "--start-mcp-server"]

        import subprocess

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        security_logger = get_security_logger()
        security_logger.log_subprocess_execution(
            command=cmd,
            purpose="mcp_server_restart",
        )

        # Give the server a moment to start
        time.sleep(1)

        # Display success panel with server details
        http_endpoint = "http://127.0.0.1:8676/mcp"

        ServerPanels.startup_success(
            server_name="Crackerjack MCP",
            endpoint=http_endpoint,
            process_id=process.pid,
        )
        return True

    except Exception as e:
        ServerPanels.error(title="MCP Restart Error", message=str(e))
        return False


def restart_zuban_lsp() -> bool:
    """Restart zuban LSP server."""
    console.print("[bold cyan]🔄 Restarting Zuban LSP server...[/ bold cyan]")

    stop_zuban_lsp()

    console.print("⏳ Waiting for cleanup")
    time.sleep(2)

    console.print("🚀 Starting new Zuban LSP server")
    try:
        cmd = [sys.executable, "-m", "crackerjack", "--start-zuban-lsp"]

        import subprocess

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        security_logger = get_security_logger()
        security_logger.log_subprocess_execution(
            command=cmd,
            purpose="zuban_lsp_restart",
        )

        console.print("✅ Zuban LSP server restart initiated")
        return True

    except Exception as e:
        console.print(f"❌ Failed to restart Zuban LSP server: {e}")
        return False


def list_server_status() -> None:
    console.print("[bold cyan]📊 Crackerjack Server Status[/ bold cyan]")

    mcp_processes = find_mcp_server_processes()
    # Phase 1: find_websocket_server_processes() call removed (WebSocket stack deleted)
    zuban_lsp_processes = find_zuban_lsp_processes()

    if mcp_processes:
        console.print("\n[bold green]MCP Servers: [/ bold green]")
        for proc in mcp_processes:
            console.print(
                f" • PID {proc['pid']} - CPU: {proc['cpu']}%-Memory: {proc['mem']}%",
            )
            console.print(f" Command: {proc['command']}")
    else:
        console.print("\n[yellow]MCP Servers: None running[/ yellow]")

    # Phase 1: WebSocket server status display removed (WebSocket stack deleted)

    if zuban_lsp_processes:
        console.print("\n[bold green]Zuban LSP Servers: [/ bold green]")
        for proc in zuban_lsp_processes:
            console.print(
                f" • PID {proc['pid']} - CPU: {proc['cpu']}%-Memory: {proc['mem']}%",
            )
            console.print(f" Command: {proc['command']}")
    else:
        console.print("\n[yellow]Zuban LSP Servers: None running[/ yellow]")

    # Phase 1: Removed websocket_processes from empty server check (WebSocket stack deleted)
    if not mcp_processes and not zuban_lsp_processes:
        console.print("\n[dim]No crackerjack servers currently running[/ dim]")

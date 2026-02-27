
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from crackerjack.config.mcp_settings_adapter import CrackerjackMCPSettings

console = Console()


PID_FILE_PATH = Path("/tmp/crackerjack-mcp.pid")


DEFAULT_HEALTH_ENDPOINT = "http://localhost: 8676/health"


class ExitCode:

    SUCCESS = 0
    GENERAL_ERROR = 1
    SERVER_NOT_RUNNING = 2
    SERVER_ALREADY_RUNNING = 3
    HEALTH_CHECK_FAILED = 4
    TIMEOUT = 7
    STALE_PID = 8


def _get_settings() -> CrackerjackMCPSettings:
    return CrackerjackMCPSettings.load_for_crackerjack()


def _read_pid() -> int | None:
    if not PID_FILE_PATH.exists():
        return None
    try:
        return int(PID_FILE_PATH.read_text().strip())
    except (ValueError, OSError):
        return None


def _write_pid(pid: int) -> None:
    PID_FILE_PATH.write_text(str(pid))


def _remove_pid() -> None:
    PID_FILE_PATH.unlink(missing_ok=True)


def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _wait_for_shutdown(pid: int, timeout: int = 10) -> bool:
    for _ in range(timeout * 10):
        if not _is_process_alive(pid):
            return True
        time.sleep(0.1)
    return False


def _check_http_health(endpoint: str, timeout: float = 5.0) -> dict[str, Any]:
    try:
        url = f"{endpoint}/health"
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")

        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
            return {"status": "healthy", "data": data}
    except urllib.error.HTTPError as e:
        return {"status": "unhealthy", "error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"status": "unreachable", "error": str(e.reason)}
    except json.JSONDecodeError as e:
        return {"status": "invalid_response", "error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


app = typer.Typer(
    name="mcp",
    help="MCP server lifecycle management commands.",
    add_completion=False,
)


@app.command()
def start(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force start (remove stale PID file if exists)",
    ),
    detach: bool = typer.Option(
        True,
        "--detach/--no-detach",
        help="Run server in background (default: True)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output JSON instead of text",
    ),
) -> None:
    existing_pid = _read_pid()

    if existing_pid is not None:
        if _is_process_alive(existing_pid):
            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "status": "error",
                            "error": "already_running",
                            "pid": existing_pid,
                            "message": f"Server already running (PID {existing_pid})",
                        }
                    )
                )
            else:
                console.print(
                    f"[yellow]Server already running (PID {existing_pid})[/yellow]"
                )
            sys.exit(ExitCode.SERVER_ALREADY_RUNNING)

        if not force:
            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "status": "error",
                            "error": "stale_pid",
                            "pid": existing_pid,
                            "message": "Stale PID file found. Use --force to remove.",
                        }
                    )
                )
            else:
                console.print(
                    f"[yellow]Stale PID file found (PID {existing_pid}). "
                    "Use --force to remove.[/yellow]"
                )
            sys.exit(ExitCode.STALE_PID)

        _remove_pid()


    cmd = [sys.executable, "-m", "crackerjack.mcp.server"]

    try:
        if detach:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            _write_pid(process.pid)

            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "status": "started",
                            "pid": process.pid,
                            "message": "Server started in background",
                        }
                    )
                )
            else:
                console.print(f"[green]Server started (PID {process.pid})[/green]")
        else:

            _write_pid(os.getpid())
            try:
                subprocess.run(cmd, check=True)
            except KeyboardInterrupt:
                console.print("\n[yellow]Server stopped by user[/yellow]")
            finally:
                _remove_pid()

    except Exception as e:
        _remove_pid()
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "error",
                        "error": "start_failed",
                        "message": str(e),
                    }
                )
            )
        else:
            console.print(f"[red]Failed to start server: {e}[/red]")
        sys.exit(ExitCode.GENERAL_ERROR)


@app.command()
def stop(
    timeout: int = typer.Option(
        10,
        "--timeout",
        "-t",
        help="Seconds to wait for graceful shutdown",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force kill (SIGKILL) if graceful shutdown fails",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output JSON instead of text",
    ),
) -> None:
    pid = _read_pid()

    if pid is None:
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "not_running",
                        "message": "Server not running (no PID file)",
                    }
                )
            )
        else:
            console.print("[yellow]Server not running (no PID file)[/yellow]")
        sys.exit(ExitCode.SUCCESS)

    if not _is_process_alive(pid):
        _remove_pid()
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "not_running",
                        "message": f"Process {pid} not found, removed stale PID file",
                    }
                )
            )
        else:
            console.print(
                f"[yellow]Process {pid} not found, removed stale PID file[/yellow]"
            )
        sys.exit(ExitCode.SUCCESS)


    if json_output:
        typer.echo(
            json.dumps(
                {
                    "status": "stopping",
                    "pid": pid,
                    "message": f"Sending SIGTERM to process {pid}",
                }
            )
        )
    else:
        console.print(f"[yellow]Stopping server (PID {pid})...[/yellow]")

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _remove_pid()
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "not_running",
                        "message": "Process not found",
                    }
                )
            )
        else:
            console.print("[yellow]Process not found[/yellow]")
        sys.exit(ExitCode.SUCCESS)


    if _wait_for_shutdown(pid, timeout):
        _remove_pid()
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "stopped",
                        "message": "Server stopped gracefully",
                    }
                )
            )
        else:
            console.print("[green]Server stopped gracefully[/green]")
        sys.exit(ExitCode.SUCCESS)


    if force:
        try:
            os.kill(pid, signal.SIGKILL)
            _remove_pid()
            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "status": "killed",
                            "message": "Server forcefully killed",
                        }
                    )
                )
            else:
                console.print("[red]Server forcefully killed[/red]")
            sys.exit(ExitCode.SUCCESS)
        except ProcessLookupError:
            _remove_pid()
            sys.exit(ExitCode.SUCCESS)
    else:
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "timeout",
                        "message": "Shutdown timed out. Use --force to kill.",
                    }
                )
            )
        else:
            console.print("[red]Shutdown timed out. Use --force to kill.[/red]")
        sys.exit(ExitCode.TIMEOUT)


@app.command()
def status(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output JSON instead of text",
    ),
) -> None:
    pid = _read_pid()

    if pid is None:
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "not_running",
                        "message": "Server not running (no PID file)",
                    }
                )
            )
        else:
            console.print("[yellow]Server not running (no PID file)[/yellow]")
        sys.exit(ExitCode.SERVER_NOT_RUNNING)

    if not _is_process_alive(pid):
        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "stale_pid",
                        "pid": pid,
                        "message": f"Stale PID file (process {pid} not found)",
                    }
                )
            )
        else:
            console.print(f"[yellow]Stale PID file (process {pid} not found)[/yellow]")
        sys.exit(ExitCode.STALE_PID)


    if json_output:
        typer.echo(
            json.dumps(
                {
                    "status": "running",
                    "pid": pid,
                    "message": f"Server running (PID {pid})",
                }
            )
        )
    else:
        console.print(f"[green]Server running (PID {pid})[/green]")
    sys.exit(ExitCode.SUCCESS)


@app.command()
def restart(
    timeout: int = typer.Option(
        10,
        "--timeout",
        "-t",
        help="Seconds to wait for graceful shutdown",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force restart even if server not running",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output JSON instead of text",
    ),
) -> None:

    pid = _read_pid()

    if pid is None or not _is_process_alive(pid):
        if not force:
            if json_output:
                typer.echo(
                    json.dumps(
                        {
                            "status": "error",
                            "error": "not_running",
                            "message": "Server not running. Use --force to start anyway.",
                        }
                    )
                )
            else:
                console.print(
                    "[yellow]Server not running. Use --force to start anyway.[/yellow]"
                )
            sys.exit(ExitCode.SERVER_NOT_RUNNING)

        _remove_pid()
    else:

        if json_output:
            typer.echo(
                json.dumps(
                    {
                        "status": "stopping",
                        "pid": pid,
                        "message": f"Stopping server (PID {pid})...",
                    }
                )
            )
        else:
            console.print(f"[yellow]Stopping server (PID {pid})...[/yellow]")

        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            _remove_pid()


        if not _wait_for_shutdown(pid, timeout):
            if force:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                if json_output:
                    typer.echo(
                        json.dumps(
                            {
                                "status": "error",
                                "error": "timeout",
                                "message": "Shutdown timed out. Use --force.",
                            }
                        )
                    )
                else:
                    console.print("[red]Shutdown timed out. Use --force.[/red]")
                sys.exit(ExitCode.TIMEOUT)

        _remove_pid()


        time.sleep(1)


    if json_output:
        typer.echo(json.dumps({"status": "starting", "message": "Starting server..."}))
    else:
        console.print("[cyan]Starting server...[/cyan]")


    start(force=True, detach=True, json_output=json_output)


@app.command()
def health(
    probe: bool = typer.Option(
        False,
        "--probe",
        "-p",
        help="Run live HTTP health probe",
    ),
    endpoint: str = typer.Option(
        DEFAULT_HEALTH_ENDPOINT,
        "--endpoint",
        "-e",
        help="Health check endpoint URL",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output JSON instead of text",
    ),
) -> None:
    pid = _read_pid()


    health_data: dict[str, Any] = {
        "pid": pid,
        "pid_file": str(PID_FILE_PATH),
        "process_alive": False,
    }

    if pid is not None:
        health_data["process_alive"] = _is_process_alive(pid)


    settings = _get_settings()
    snapshot_path = settings.health_snapshot_path()

    if snapshot_path.exists():
        try:
            from crackerjack.runtime import read_runtime_health

            snapshot = read_runtime_health(snapshot_path)
            if snapshot is not None:
                health_data["snapshot"] = {
                    "orchestrator_pid": snapshot.orchestrator_pid,
                    "watchers_running": snapshot.watchers_running,
                    "lifecycle_state": snapshot.lifecycle_state,
                }


                if (
                    snapshot_path.stat().st_mtime
                    < time.time() - settings.health_ttl_seconds
                ):
                    health_data["snapshot_fresh"] = False
                else:
                    health_data["snapshot_fresh"] = True
        except Exception as e:
            health_data["snapshot_error"] = str(e)
    else:
        health_data["snapshot"] = None
        health_data["snapshot_fresh"] = False


    if probe:
        http_health = _check_http_health(endpoint)
        health_data["http_probe"] = http_health


    is_healthy = health_data.get("process_alive", False) and health_data.get(
        "snapshot_fresh", False
    )

    if probe and health_data.get("http_probe", {}).get("status") != "healthy":
        is_healthy = False

    health_data["status"] = "healthy" if is_healthy else "unhealthy"

    if json_output:
        typer.echo(json.dumps(health_data, indent=2))
    else:
        console.print("\n[bold]Crackerjack MCP Server Health[/bold]")
        console.print(f"  PID: {pid or 'N/A'}")
        console.print(
            f"  Process: {'[green]alive[/green]' if health_data['process_alive'] else '[red]dead[/red]'}"
        )

        if "snapshot" in health_data and health_data["snapshot"]:
            snapshot = health_data["snapshot"]
            console.print(
                f"  Watchers: {'[green]running[/green]' if snapshot.get('watchers_running') else '[red]stopped[/red]'}"
            )
            console.print(
                f"  Snapshot: {'[green]fresh[/green]' if health_data.get('snapshot_fresh') else '[red]stale[/red]'}"
            )
        else:
            console.print("  Snapshot: [yellow]not available[/yellow]")

        if probe:
            http_status = health_data.get("http_probe", {}).get("status", "unknown")
            console.print(
                f"  HTTP Probe: {'[green]' + http_status + '[/green]' if http_status == 'healthy' else '[red]' + http_status + '[/red]'}"
            )

        console.print(
            f"\n  Overall: {'[bold green]HEALTHY[/bold green]' if is_healthy else '[bold red]UNHEALTHY[/bold red]'}"
        )

    sys.exit(ExitCode.SUCCESS if is_healthy else ExitCode.HEALTH_CHECK_FAILED)


__all__ = ["app"]

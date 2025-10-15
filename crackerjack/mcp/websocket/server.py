import asyncio
import contextlib
import signal
import subprocess
import tempfile
import time
import typing as t
from pathlib import Path

import uvicorn
from acb import console

from crackerjack.core.timeout_manager import get_timeout_manager

from .app import create_websocket_app
from .jobs import JobManager


class WebSocketServer:
    def __init__(self, port: int = 8675) -> None:
        self.port = port
        self.progress_dir = Path(tempfile.gettempdir()) / "crackerjack-mcp-progress"
        self.is_running = True
        self.job_manager: JobManager | None = None
        self.app: t.Any = None
        self.timeout_manager = get_timeout_manager()
        self.server_task: asyncio.Task[t.Any] | None = None

    def setup(self) -> None:
        self.progress_dir.mkdir(exist_ok=True)

        self.job_manager = JobManager(self.progress_dir)

        self.app = create_websocket_app(self.job_manager, self.progress_dir)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, _signum: int, _frame: t.Any) -> None:
        console.print("\n[yellow]Shutting down WebSocket server...[/yellow]")
        self.is_running = False

        if self.server_task and not self.server_task.done():
            self.server_task.cancel()

        if self.job_manager:
            with contextlib.suppress(Exception):
                asyncio.create_task(self._graceful_shutdown())

    async def _graceful_shutdown(self) -> None:
        if self.job_manager:
            try:
                await asyncio.sleep(2.0)

                console.print(
                    "[yellow]Forcing remaining WebSocket connections to close[/yellow]"
                )
            except Exception as e:
                console.print(f"[red]Error during graceful shutdown: {e}[/red]")

    def run(self) -> None:
        try:
            self.setup()
            console.print(
                f"[green]Starting WebSocket server on port {self.port}[/green]",
            )
            console.print(f"Progress directory: {self.progress_dir}")
            console.print("Press Ctrl+C to stop")

            config = uvicorn.Config(
                app=self.app,
                port=self.port,
                host="127.0.0.1",
                log_level="info",
                timeout_keep_alive=30,
                timeout_graceful_shutdown=30,
            )

            server = uvicorn.Server(config)

            try:
                asyncio.run(self._run_with_timeout(server))
            except KeyboardInterrupt:
                console.print("\n[yellow]Server interrupted by user[/yellow]")

        except KeyboardInterrupt:
            console.print("\n[yellow]Server stopped by user[/yellow]")
        except Exception as e:
            console.print(f"[red]Server error: {e}[/red]")
        finally:
            console.print("[green]WebSocket server shutdown complete[/green]")

    async def _run_with_timeout(self, server: uvicorn.Server) -> None:
        try:
            self.server_task = asyncio.create_task(server.serve())

            while self.is_running and not self.server_task.done():
                try:
                    await asyncio.sleep(5.0)

                except asyncio.CancelledError:
                    console.print("[yellow]Server monitoring cancelled[/yellow]")
                    break
                except Exception as e:
                    console.print(f"[red]Server monitoring error: {e}[/red]")
                    break

            if self.server_task and not self.server_task.done():
                try:
                    await asyncio.wait_for(self.server_task, timeout=30.0)
                except TimeoutError:
                    console.print(
                        "[yellow]Server shutdown timeout, forcing termination[/yellow]"
                    )
                    self.server_task.cancel()
                    try:
                        await self.server_task
                    except asyncio.CancelledError:
                        pass

        except Exception as e:
            console.print(f"[red]Server runtime error: {e}[/red]")


def handle_websocket_server_command(
    start: bool = False,
    stop: bool = False,
    restart: bool = False,
    port: int = 8675,
) -> None:
    if stop or restart:
        console.print("[yellow]Stopping WebSocket servers...[/yellow]")

        try:
            result = subprocess.run(
                ["pkill", "-f", f"uvicorn.*: {port}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                console.print("[green]✅ WebSocket servers stopped[/green]")
            else:
                console.print("[dim]No WebSocket servers were running[/dim]")
        except subprocess.TimeoutExpired:
            console.print("[red]Timeout stopping WebSocket servers[/red]")
        except Exception as e:
            console.print(f"[red]Error stopping WebSocket servers: {e}[/red]")

        if stop:
            return

        time.sleep(2)

    if start or restart:
        console.print(f"[green]Starting WebSocket server on port {port}...[/green]")
        try:
            server = WebSocketServer(port)
            server.run()
        except Exception as e:
            console.print(f"[red]Failed to start WebSocket server: {e}[/red]")


def main(port: int = 8675) -> None:
    server = WebSocketServer(port)
    server.run()


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8675
    main(port)

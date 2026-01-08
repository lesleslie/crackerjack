import asyncio
import json
import logging
import subprocess
import time
import typing as t
from contextlib import suppress
from pathlib import Path

from rich.console import Console

from .security_logger import get_security_logger

logger = logging.getLogger("crackerjack.zuban_lsp")


class ZubanLSPService:
    def __init__(
        self,
        port: int = 8677,
        mode: str = "tcp",
        console: Console | None = None,
    ) -> None:
        self.port = port
        self.mode = mode
        self.console = console or Console()
        self.process: subprocess.Popen[bytes] | None = None
        self.start_time: float = 0.0
        self.security_logger = get_security_logger()
        self._health_check_failures = 0
        self._max_health_failures = 3

    @property
    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def uptime(self) -> float:
        if self.is_running and self.start_time > 0:
            return time.time() - self.start_time
        return 0.0

    async def start(self) -> bool:
        if self.is_running:
            logger.info("Zuban LSP server already running")
            return True

        try:
            self.console.print("[cyan]🚀 Starting Zuban LSP server...[/cyan]")

            if self.mode == "tcp":
                cmd = ["uv", "run", "zuban", "server"]
            else:
                cmd = ["uv", "run", "zuban", "server"]

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path.cwd(),
                start_new_session=True,
            )

            self.start_time = time.time()
            self._health_check_failures = 0

            self.security_logger.log_subprocess_execution(
                command=cmd,
                purpose="zuban_lsp_server_start",
            )

            await asyncio.sleep(1.0)

            if not self.is_running:
                error_output = ""
                if self.process and self.process.stderr:
                    with suppress(Exception):
                        error_output = self.process.stderr.read().decode()

                self.console.print("[red]❌ Failed to start Zuban LSP server[/red]")
                if error_output:
                    logger.error(f"Zuban LSP startup error: {error_output}")
                return False

            self.console.print(
                f"[green]✅ Zuban LSP server started (PID: {self.process.pid})[/green]"
            )
            logger.info(f"Zuban LSP server started with PID {self.process.pid}")
            return True

        except Exception as e:
            self.console.print(f"[red]❌ Error starting Zuban LSP server: {e}[/red]")
            logger.error(f"Failed to start Zuban LSP server: {e}")
            return False

    async def stop(self) -> None:
        if not self.process:
            return

        self.console.print("[yellow]🛑 Stopping Zuban LSP server...[/yellow]")

        try:
            self.process.terminate()

            try:
                self.process.wait(timeout=5.0)
                self.console.print(
                    "[green]✅ Zuban LSP server stopped gracefully[/green]"
                )
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2.0)
                self.console.print("[yellow]⚠️ Zuban LSP server force stopped[/yellow]")

        except Exception as e:
            logger.error(f"Error stopping Zuban LSP server: {e}")

        finally:
            self.process = None
            self.start_time = 0.0
            self._health_check_failures = 0

    async def health_check(self) -> bool:
        if not self.is_running:
            return False

        try:
            if self.mode == "stdio":
                return self._check_stdio_health()
            else:
                return self._check_tcp_health()

        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            self._health_check_failures += 1
            return False

    def _check_stdio_health(self) -> bool:
        if not self.process:
            return False

        return self.process.poll() is None

    def _check_tcp_health(self) -> bool:
        # TODO: Implement TCP health check when zuban supports TCP mode

        return self._check_stdio_health()

    async def restart(self) -> bool:
        self.console.print("[cyan]🔄 Restarting Zuban LSP server...[/cyan]")

        await self.stop()
        await asyncio.sleep(2.0)

        success = await self.start()
        if success:
            self.console.print(
                "[green]✅ Zuban LSP server restarted successfully[/green]"
            )
        else:
            self.console.print("[red]❌ Failed to restart Zuban LSP server[/red]")

        return success

    def get_status(self) -> dict[str, t.Any]:
        return {
            "running": self.is_running,
            "pid": self.process.pid if self.process else None,
            "uptime": self.uptime,
            "port": self.port,
            "mode": self.mode,
            "health_failures": self._health_check_failures,
            "max_health_failures": self._max_health_failures,
            "healthy": self.is_running
            and self._health_check_failures < self._max_health_failures,
        }

    async def send_lsp_request(
        self, method: str, params: dict[str, t.Any] | None = None
    ) -> dict[str, t.Any] | None:
        if not self.is_running or not self.process or not self.process.stdin:
            return None

        try:
            request_id = int(time.time() * 1000)
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
            }

            if params is not None:
                request["params"] = params

            request_json = json.dumps(request)
            content_length = len(request_json.encode())

            message = f"Content-Length: {content_length}\r\n\r\n{request_json}"

            self.process.stdin.write(message.encode())
            self.process.stdin.flush()

            if method.startswith("textDocument/did"):
                return {"status": "notification_sent", "id": request_id}

            try:
                response = await self._read_lsp_response(request_id, timeout=5.0)
                return response
            except TimeoutError:
                logger.warning(f"LSP request {method} timed out")
                return {"status": "timeout", "id": request_id}

        except Exception as e:
            logger.error(f"Failed to send LSP request: {e}")
            return None

    async def _read_lsp_response(
        self, expected_id: int, timeout: float = 5.0
    ) -> dict[str, t.Any] | None:
        if not self.process or not self.process.stdout:
            return None

        try:
            response_data = await asyncio.wait_for(
                self._read_message_from_stdout(), timeout=timeout
            )

            if not response_data:
                return None

            response = json.loads(response_data)
            typed_response = t.cast(dict[str, t.Any], response)

            if typed_response.get("id") == expected_id:
                return typed_response

            logger.debug(
                f"Received response for ID {typed_response.get('id')}, expected {expected_id}"
            )
            return typed_response

        except TimeoutError:
            raise
        except Exception as e:
            logger.error(f"Failed to read LSP response: {e}")
            return None

    async def _read_message_from_stdout(self) -> str | None:
        if not self.process or not self.process.stdout:
            return None

        try:
            header_line = await self._read_line_async()
            if not header_line or not header_line.startswith("Content-Length:"):
                return None

            content_length = int(header_line.split(":", 1)[1].strip())

            empty_line = await self._read_line_async()
            if empty_line.strip():
                logger.warning("Expected empty line after Content-Length header")

            content_bytes = await self._read_bytes_async(content_length)
            return content_bytes.decode("utf-8")

        except Exception as e:
            logger.error(f"Failed to read LSP message: {e}")
            return None

    async def _read_line_async(self) -> str:
        if not self.process or not self.process.stdout:
            return ""

        loop = asyncio.get_event_loop()
        line = await loop.run_in_executor(None, self.process.stdout.readline)  # type: ignore[call-arg]
        return line.decode("utf-8").rstrip("\r\n")

    async def _read_bytes_async(self, count: int) -> bytes:
        if not self.process or not self.process.stdout:
            return b""

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, self.process.stdout.read, count)  # type: ignore[call-arg]
        return data


async def create_zuban_lsp_service(
    port: int = 8677,
    mode: str = "tcp",
    console: Console | None = None,
) -> ZubanLSPService:
    service = ZubanLSPService(port=port, mode=mode, console=console)
    return service

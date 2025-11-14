"""Zuban Language Server Protocol (LSP) service for real-time type checking."""

import asyncio
import json
import logging
import subprocess
import time
import typing as t
from contextlib import suppress
from pathlib import Path

from acb.console import Console
from acb.depends import depends

from .security_logger import get_security_logger

logger = logging.getLogger("crackerjack.zuban_lsp")


class ZubanLSPService:
    """Manages zuban language server lifecycle and communication."""

    def __init__(
        self,
        port: int = 8677,
        mode: str = "tcp",
        console: Console | None = None,
    ) -> None:
        """Initialize Zuban LSP service.

        Args:
            port: TCP port for server (default: 8677)
            mode: Transport mode, "tcp" or "stdio" (default: "tcp")
            console: Rich console for output (optional)
        """
        self.port = port
        self.mode = mode
        self.console = console or depends.get_sync(Console)
        self.process: subprocess.Popen[bytes] | None = None
        self.start_time: float = 0.0
        self.security_logger = get_security_logger()
        self._health_check_failures = 0
        self._max_health_failures = 3

    @property
    def is_running(self) -> bool:
        """Check if LSP server process is running."""
        return self.process is not None and self.process.poll() is None

    @property
    def uptime(self) -> float:
        """Get server uptime in seconds."""
        if self.is_running and self.start_time > 0:
            return time.time() - self.start_time
        return 0.0

    async def start(self) -> bool:
        """Start the zuban LSP server.

        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            logger.info("Zuban LSP server already running")
            return True

        try:
            self.console.print("[cyan]🚀 Starting Zuban LSP server...[/cyan]")

            # Build command based on transport mode
            if self.mode == "tcp":
                # For TCP mode, we'll need to configure zuban to listen on port
                # Currently zuban server only supports stdio, so we use stdio mode
                cmd = ["uv", "run", "zuban", "server"]
            else:
                cmd = ["uv", "run", "zuban", "server"]

            # Start the process
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

            # Log the startup
            self.security_logger.log_subprocess_execution(
                command=cmd,
                purpose="zuban_lsp_server_start",
            )

            # Wait a moment for startup
            await asyncio.sleep(1.0)

            # Verify it started successfully
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
        """Gracefully stop the LSP server."""
        if not self.process:
            return

        self.console.print("[yellow]🛑 Stopping Zuban LSP server...[/yellow]")

        try:
            # Try graceful shutdown first
            self.process.terminate()

            # Wait for graceful shutdown
            try:
                self.process.wait(timeout=5.0)
                self.console.print(
                    "[green]✅ Zuban LSP server stopped gracefully[/green]"
                )
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
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
        """Check if LSP server is responsive.

        Returns:
            True if server is healthy, False otherwise
        """
        if not self.is_running:
            return False

        try:
            # For stdio mode, we check if process is alive and responsive
            if self.mode == "stdio":
                return self._check_stdio_health()
            else:
                # For TCP mode, we would check port connectivity
                return self._check_tcp_health()

        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            self._health_check_failures += 1
            return False

    def _check_stdio_health(self) -> bool:
        """Check health for stdio mode server."""
        if not self.process:
            return False

        # Simple check - is process still alive?
        return self.process.poll() is None

    def _check_tcp_health(self) -> bool:
        """Check health for TCP mode server."""
        # TODO: Implement TCP health check when zuban supports TCP mode
        # For now, fall back to process check
        return self._check_stdio_health()

    async def restart(self) -> bool:
        """Restart the LSP server.

        Returns:
            True if restarted successfully, False otherwise
        """
        self.console.print("[cyan]🔄 Restarting Zuban LSP server...[/cyan]")

        await self.stop()
        await asyncio.sleep(2.0)  # Brief pause between stop and start

        success = await self.start()
        if success:
            self.console.print(
                "[green]✅ Zuban LSP server restarted successfully[/green]"
            )
        else:
            self.console.print("[red]❌ Failed to restart Zuban LSP server[/red]")

        return success

    def get_status(self) -> dict[str, t.Any]:
        """Get current status of the LSP server.

        Returns:
            Dictionary with server status information
        """
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
        """Send an LSP request to the server.

        Args:
            method: LSP method name (e.g., "initialize", "textDocument/didOpen")
            params: Request parameters (optional)

        Returns:
            LSP response or None if failed
        """
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

            # LSP protocol: Content-Length header + \r\n\r\n + JSON
            message = f"Content-Length: {content_length}\r\n\r\n{request_json}"

            self.process.stdin.write(message.encode())
            self.process.stdin.flush()

            # For notifications (no response expected), return success
            if method.startswith("textDocument/did"):
                return {"status": "notification_sent", "id": request_id}

            # For requests that expect responses, attempt to read response
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
        """Read LSP response from server with timeout.

        Args:
            expected_id: Expected request ID for the response
            timeout: Timeout in seconds

        Returns:
            LSP response dictionary or None if failed
        """
        if not self.process or not self.process.stdout:
            return None

        try:
            # Read with timeout
            response_data = await asyncio.wait_for(
                self._read_message_from_stdout(), timeout=timeout
            )

            if not response_data:
                return None

            response = json.loads(response_data)
            typed_response = t.cast(dict[str, t.Any], response)

            # Check if this is the response we're looking for
            if typed_response.get("id") == expected_id:
                return typed_response

            # Log if we got a different response
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
        """Read a complete LSP message from stdout.

        Returns:
            Message content as string, or None if failed
        """
        if not self.process or not self.process.stdout:
            return None

        try:
            # Read the Content-Length header
            header_line = await self._read_line_async()
            if not header_line or not header_line.startswith("Content-Length:"):
                return None

            # Extract content length
            content_length = int(header_line.split(":", 1)[1].strip())

            # Read the empty line separator
            empty_line = await self._read_line_async()
            if empty_line.strip():  # Should be empty
                logger.warning("Expected empty line after Content-Length header")

            # Read the JSON content
            content_bytes = await self._read_bytes_async(content_length)
            return content_bytes.decode("utf-8")

        except Exception as e:
            logger.error(f"Failed to read LSP message: {e}")
            return None

    async def _read_line_async(self) -> str:
        """Read a line from stdout asynchronously."""
        if not self.process or not self.process.stdout:
            return ""

        # This is a simplified implementation
        # In a production system, you'd want to use proper async I/O
        loop = asyncio.get_event_loop()
        line = await loop.run_in_executor(None, self.process.stdout.readline)  # type: ignore[call-arg]
        return line.decode("utf-8").rstrip("\r\n")

    async def _read_bytes_async(self, count: int) -> bytes:
        """Read specified number of bytes from stdout asynchronously."""
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
    """Factory function to create and optionally start Zuban LSP service.

    Args:
        port: TCP port for server (default: 8677)
        mode: Transport mode, "tcp" or "stdio" (default: "tcp")
        console: Rich console for output (optional)

    Returns:
        Configured ZubanLSPService instance
    """
    service = ZubanLSPService(port=port, mode=mode, console=console)
    return service

import asyncio
import typing as t
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from acb import console
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from crackerjack.core.timeout_manager import TimeoutStrategy, get_timeout_manager

from .jobs import JobManager

# console imported from acb


# Phase 9.4: WebSocket Security Configuration
@dataclass
class WebSocketSecurityConfig:
    """Security configuration for WebSocket connections.

    Phase 9.4: Enhanced security hardening for MCP WebSocket server.
    """

    # Message limits
    max_message_size: int = 1024 * 1024  # 1MB max message size
    max_messages_per_connection: int = 10000  # Max messages before forcing reconnect
    max_concurrent_connections: int = 100  # Limit concurrent WebSocket connections

    # Origin validation (localhost only for MCP)
    allowed_origins: set[str] | None = None  # None = allow all (default for local dev)

    # Rate limiting
    messages_per_second: int = 100  # Max messages per second per connection

    def __post_init__(self) -> None:
        """Initialize allowed origins with secure defaults."""
        if self.allowed_origins is None:
            # Default: only allow localhost connections
            self.allowed_origins = {
                "http://localhost",
                "http://127.0.0.1",
                "https://localhost",
                "https://127.0.0.1",
            }

    def validate_origin(self, origin: str | None) -> bool:
        """Validate WebSocket origin header.

        Args:
            origin: Origin header value

        Returns:
            True if origin is allowed, False otherwise
        """
        if not origin:
            # Allow connections without origin (local tools)
            return True

        # Check against allowed origins
        for allowed in self.allowed_origins or set():
            if origin.startswith(allowed):
                return True

        console.print(
            f"[red]Rejected WebSocket connection from unauthorized origin: {origin}[/red]"
        )
        return False


class WebSocketHandler:
    def __init__(
        self,
        job_manager: JobManager,
        progress_dir: Path,
        security_config: WebSocketSecurityConfig | None = None,
        event_bridge: t.Any | None = None,  # EventBusWebSocketBridge from DI
    ) -> None:
        self.job_manager = job_manager
        self.progress_dir = progress_dir
        self.timeout_manager = get_timeout_manager()
        self.security_config = security_config or WebSocketSecurityConfig()
        self.event_bridge = event_bridge
        self._connection_count = 0

    async def handle_connection(self, websocket: WebSocket, job_id: str) -> None:
        # Phase 9.4: Security validations
        if not self.job_manager.validate_job_id(job_id):
            await websocket.close(code=1008, reason="Invalid job ID")
            return

        # Check origin header
        origin = websocket.headers.get("origin")
        if not self.security_config.validate_origin(origin):
            await websocket.close(code=1008, reason="Unauthorized origin")
            return

        # Check connection limit
        if self._connection_count >= self.security_config.max_concurrent_connections:
            await websocket.close(code=1008, reason="Connection limit reached")
            console.print(
                f"[yellow]Connection limit reached: {self._connection_count}[/yellow]"
            )
            return

        try:
            async with self.timeout_manager.timeout_context(
                "websocket_connection",
                timeout=3600.0,
                strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
            ):
                await self._establish_connection(websocket, job_id)
                await self._send_initial_progress(websocket, job_id)
                await self._handle_message_loop(websocket, job_id)

        except TimeoutError:
            await self._handle_timeout_error(websocket, job_id)
        except WebSocketDisconnect:
            console.print(f"[yellow]WebSocket disconnected for job: {job_id}[/yellow]")
        except Exception as e:
            await self._handle_connection_error(websocket, job_id, e)
        finally:
            await self._cleanup_connection(job_id, websocket)

    async def _establish_connection(self, websocket: WebSocket, job_id: str) -> None:
        await websocket.accept()
        self._connection_count += 1  # Phase 9.4: Track concurrent connections
        self.job_manager.add_connection(job_id, websocket)

        # Phase 7.3: Register client with event bridge for real-time updates
        if self.event_bridge:
            await self.event_bridge.register_client(job_id, websocket)

        console.print(
            f"[green]WebSocket connected for job: {job_id} (connections: {self._connection_count})[/green]"
        )

    async def _send_initial_progress(self, websocket: WebSocket, job_id: str) -> None:
        try:
            async with self.timeout_manager.timeout_context(
                "websocket_broadcast",
                timeout=5.0,
                strategy=TimeoutStrategy.FAIL_FAST,
            ):
                initial_progress = self.job_manager.get_job_progress(job_id)
                if initial_progress:
                    await websocket.send_json(initial_progress)
                else:
                    await websocket.send_json(
                        self._create_initial_progress_message(job_id)
                    )
        except Exception as e:
            console.print(
                f"[red]Failed to send initial progress for {job_id}: {e}[/red]"
            )

    def _create_initial_progress_message(self, job_id: str) -> dict[str, t.Any]:
        return {
            "job_id": job_id,
            "status": "waiting",
            "message": "Waiting for job to start...",
            "overall_progress": 0,
            "iteration": 0,
            "max_iterations": 10,
            "current_stage": "Initializing",
        }

    async def _handle_message_loop(self, websocket: WebSocket, job_id: str) -> None:
        message_count = 0
        max_messages = (
            self.security_config.max_messages_per_connection
        )  # Phase 9.4: Use config

        while message_count < max_messages:
            try:
                should_continue = await self._process_single_message(
                    websocket, job_id, message_count + 1
                )
                if not should_continue:
                    break
                message_count += 1
            except (TimeoutError, WebSocketDisconnect, Exception):
                break

        if message_count >= max_messages:
            console.print(
                f"[yellow]WebSocket connection limit reached for {job_id}: {max_messages} messages[/yellow]"
            )

    async def _process_single_message(
        self, websocket: WebSocket, job_id: str, message_count: int
    ) -> bool:
        try:
            async with self.timeout_manager.timeout_context(
                "websocket_message",
                timeout=30.0,
                strategy=TimeoutStrategy.FAIL_FAST,
            ):
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=25.0,
                )

                console.print(
                    f"[blue]Received message {message_count} for {job_id}: {data[:100]}...[/blue]",
                )

                await asyncio.wait_for(
                    websocket.send_json(
                        {
                            "type": "echo",
                            "message": f"Received: {data}",
                            "job_id": job_id,
                            "message_count": message_count,
                        }
                    ),
                    timeout=5.0,
                )

                return True

        except TimeoutError:
            console.print(
                f"[yellow]Message timeout for {job_id} after {message_count} messages[/yellow]"
            )
            return False
        except WebSocketDisconnect:
            console.print(f"[yellow]WebSocket disconnected for job: {job_id}[/yellow]")
            return False
        except Exception as e:
            console.print(f"[red]WebSocket message error for job {job_id}: {e}[/red]")
            return False

    async def _handle_timeout_error(self, websocket: WebSocket, job_id: str) -> None:
        console.print(
            f"[yellow]WebSocket connection timeout for job: {job_id}[/yellow]"
        )
        with suppress(Exception):
            await websocket.close(code=1001, reason="Connection timeout")

    async def _handle_connection_error(
        self, websocket: WebSocket, job_id: str, error: Exception
    ) -> None:
        console.print(f"[red]WebSocket error for job {job_id}: {error}[/red]")
        with suppress(Exception):
            await websocket.close(code=1011, reason="Internal error")

    async def _cleanup_connection(self, job_id: str, websocket: WebSocket) -> None:
        try:
            self.job_manager.remove_connection(job_id, websocket)

            # Phase 7.3: Unregister client from event bridge
            if self.event_bridge:
                await self.event_bridge.unregister_client(job_id, websocket)

            self._connection_count = max(
                0, self._connection_count - 1
            )  # Phase 9.4: Decrement count
            console.print(
                f"[yellow]WebSocket disconnected for job: {job_id} (connections: {self._connection_count})[/yellow]"
            )
        except Exception as e:
            console.print(f"[red]Error removing connection for {job_id}: {e}[/red]")


def register_websocket_routes(
    app: FastAPI,
    job_manager: JobManager,
    progress_dir: Path,
    event_bridge: t.Any | None = None,  # EventBusWebSocketBridge from DI
) -> None:
    handler = WebSocketHandler(job_manager, progress_dir, event_bridge=event_bridge)

    @app.websocket("/ws/progress/{job_id}")
    async def websocket_progress_endpoint(websocket: WebSocket, job_id: str) -> None:
        await handler.handle_connection(websocket, job_id)

import asyncio
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from rich.console import Console

from crackerjack.core.timeout_manager import TimeoutStrategy, get_timeout_manager

from .jobs import JobManager

console = Console()


class WebSocketHandler:
    def __init__(self, job_manager: JobManager, progress_dir: Path) -> None:
        self.job_manager = job_manager
        self.progress_dir = progress_dir
        self.timeout_manager = get_timeout_manager()

    async def handle_connection(self, websocket: WebSocket, job_id: str) -> None:
        if not self.job_manager.validate_job_id(job_id):
            await websocket.close(code=1008, reason="Invalid job ID")
            return

        try:
            # Add timeout to the entire connection handling
            async with self.timeout_manager.timeout_context(
                "websocket_connection",
                timeout=3600.0,  # 1 hour max connection time
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
        """Establish WebSocket connection and add to job manager."""
        await websocket.accept()
        self.job_manager.add_connection(job_id, websocket)
        console.print(f"[green]WebSocket connected for job: {job_id}[/green]")

    async def _send_initial_progress(self, websocket: WebSocket, job_id: str) -> None:
        """Send initial progress data to the connected WebSocket."""
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

    def _create_initial_progress_message(self, job_id: str) -> dict:
        """Create initial progress message for new jobs."""
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
        """Handle the main message processing loop."""
        message_count = 0
        max_messages = 10000  # Prevent infinite message loops

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
        """Process a single WebSocket message. Returns False to break the loop."""
        try:
            # Add timeout to individual message operations
            async with self.timeout_manager.timeout_context(
                "websocket_message",
                timeout=30.0,  # 30 second timeout per message
                strategy=TimeoutStrategy.FAIL_FAST,
            ):
                # Use asyncio.wait_for for additional protection
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=25.0,  # Slightly less than timeout context
                )

                console.print(
                    f"[blue]Received message {message_count} for {job_id}: {data[:100]}...[/blue]",
                )

                # Respond with timeout protection
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
        """Handle timeout errors during connection."""
        console.print(
            f"[yellow]WebSocket connection timeout for job: {job_id}[/yellow]"
        )
        with suppress(Exception):
            await websocket.close(code=1001, reason="Connection timeout")

    async def _handle_connection_error(
        self, websocket: WebSocket, job_id: str, error: Exception
    ) -> None:
        """Handle connection errors."""
        console.print(f"[red]WebSocket error for job {job_id}: {error}[/red]")
        with suppress(Exception):
            await websocket.close(code=1011, reason="Internal error")

    async def _cleanup_connection(self, job_id: str, websocket: WebSocket) -> None:
        """Clean up the connection."""
        try:
            self.job_manager.remove_connection(job_id, websocket)
        except Exception as e:
            console.print(f"[red]Error removing connection for {job_id}: {e}[/red]")


def register_websocket_routes(
    app: FastAPI,
    job_manager: JobManager,
    progress_dir: Path,
) -> None:
    handler = WebSocketHandler(job_manager, progress_dir)

    @app.websocket("/ws/progress/{job_id}")
    async def websocket_progress_endpoint(websocket: WebSocket, job_id: str) -> None:
        await handler.handle_connection(websocket, job_id)

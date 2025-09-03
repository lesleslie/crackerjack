import asyncio
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
                await websocket.accept()
                self.job_manager.add_connection(job_id, websocket)

                console.print(f"[green]WebSocket connected for job: {job_id}[/green]")

                # Send initial progress with timeout
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
                                {
                                    "job_id": job_id,
                                    "status": "waiting",
                                    "message": "Waiting for job to start...",
                                    "overall_progress": 0,
                                    "iteration": 0,
                                    "max_iterations": 10,
                                    "current_stage": "Initializing",
                                },
                            )
                except Exception as e:
                    console.print(
                        f"[red]Failed to send initial progress for {job_id}: {e}[/red]"
                    )

                # Message handling loop with timeout protection
                message_count = 0
                max_messages = 10000  # Prevent infinite message loops

                while message_count < max_messages:
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

                            message_count += 1
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
                                    },
                                ),
                                timeout=5.0,
                            )

                    except TimeoutError:
                        console.print(
                            f"[yellow]Message timeout for {job_id} after {message_count} messages[/yellow]"
                        )
                        break
                    except WebSocketDisconnect:
                        console.print(
                            f"[yellow]WebSocket disconnected for job: {job_id}[/yellow]"
                        )
                        break
                    except Exception as e:
                        console.print(
                            f"[red]WebSocket message error for job {job_id}: {e}[/red]"
                        )
                        break

                if message_count >= max_messages:
                    console.print(
                        f"[yellow]WebSocket connection limit reached for {job_id}: {max_messages} messages[/yellow]"
                    )

        except TimeoutError:
            console.print(
                f"[yellow]WebSocket connection timeout for job: {job_id}[/yellow]"
            )
            try:
                await websocket.close(code=1001, reason="Connection timeout")
            except Exception:
                pass
        except WebSocketDisconnect:
            console.print(f"[yellow]WebSocket disconnected for job: {job_id}[/yellow]")
        except Exception as e:
            console.print(f"[red]WebSocket error for job {job_id}: {e}[/red]")
            try:
                await websocket.close(code=1011, reason="Internal error")
            except Exception:
                pass
        finally:
            # Always clean up connection
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

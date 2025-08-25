from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from rich.console import Console

from .jobs import JobManager

console = Console()


class WebSocketHandler:
    def __init__(self, job_manager: JobManager, progress_dir: Path) -> None:
        self.job_manager = job_manager
        self.progress_dir = progress_dir

    async def handle_connection(self, websocket: WebSocket, job_id: str) -> None:
        if not self.job_manager.validate_job_id(job_id):
            await websocket.close(code=1008, reason="Invalid job ID")
            return

        await websocket.accept()
        self.job_manager.add_connection(job_id, websocket)

        console.print(f"[green]WebSocket connected for job: {job_id}[/green]")

        try:
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

            while True:
                try:
                    data = await websocket.receive_text()
                    console.print(
                        f"[blue]Received message for {job_id}: {data[:100]}...[/blue]",
                    )

                    await websocket.send_json(
                        {
                            "type": "echo",
                            "message": f"Received: {data}",
                            "job_id": job_id,
                        },
                    )

                except WebSocketDisconnect:
                    break

        except WebSocketDisconnect:
            console.print(f"[yellow]WebSocket disconnected for job: {job_id}[/yellow]")
        except Exception as e:
            console.print(f"[red]WebSocket error for job {job_id}: {e}[/red]")
        finally:
            self.job_manager.remove_connection(job_id, websocket)


def register_websocket_routes(
    app: FastAPI,
    job_manager: JobManager,
    progress_dir: Path,
) -> None:
    handler = WebSocketHandler(job_manager, progress_dir)

    @app.websocket(" / ws / progress / {job_id}")
    async def websocket_progress_endpoint(websocket: WebSocket, job_id: str) -> None:
        await handler.handle_connection(websocket, job_id)

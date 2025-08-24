import asyncio
from pathlib import Path

from fastapi import FastAPI

from .endpoints import register_endpoints
from .jobs import JobManager
from .websocket_handler import register_websocket_routes


def create_websocket_app(job_manager: JobManager, progress_dir: Path) -> FastAPI:
    app = FastAPI(
        title="Crackerjack WebSocket Server",
        description="Real-time progress monitoring for Crackerjack workflows",
        version="1.0.0",
    )

    # Store job_manager in app state for startup/shutdown events
    app.state.job_manager = job_manager

    @app.on_event("startup")
    async def startup_event() -> None:
        """Start background tasks."""
        if job_manager:
            asyncio.create_task(job_manager.monitor_progress_files())
            asyncio.create_task(job_manager.cleanup_old_jobs())
            asyncio.create_task(job_manager.timeout_stuck_jobs())

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        """Cleanup on shutdown."""
        if job_manager:
            job_manager.cleanup()

    register_endpoints(app, job_manager, progress_dir)

    register_websocket_routes(app, job_manager, progress_dir)

    return app

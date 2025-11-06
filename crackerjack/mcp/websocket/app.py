import asyncio
from pathlib import Path

from acb.depends import depends
from fastapi import FastAPI

from .endpoints import register_endpoints
from .jobs import JobManager
from .monitoring_endpoints import (
    MonitoringWebSocketManager,
    create_monitoring_endpoints,
)
from .websocket_handler import register_websocket_routes


def create_websocket_app(job_manager: JobManager, progress_dir: Path) -> FastAPI:
    app = FastAPI(
        title="Crackerjack WebSocket Server",
        description="Real-time progress monitoring for Crackerjack workflows",
        version="1.0.0",
    )

    app.state.job_manager = job_manager

    @app.on_event("startup")
    async def startup_event() -> None:
        if job_manager:
            asyncio.create_task(job_manager.monitor_progress_files())
            asyncio.create_task(job_manager.cleanup_old_jobs())
            asyncio.create_task(job_manager.timeout_stuck_jobs())

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        if job_manager:
            job_manager.cleanup()

    register_endpoints(app, job_manager, progress_dir)

    # Phase 7.3: Get EventBusWebSocketBridge from DI and pass to WebSocket routes
    try:
        from crackerjack.mcp.websocket.event_bridge import EventBusWebSocketBridge

        event_bridge = depends.get_sync(EventBusWebSocketBridge)
    except Exception:
        # Event bridge not available (DI not initialized)
        event_bridge = None

    register_websocket_routes(app, job_manager, progress_dir, event_bridge=event_bridge)

    # Register monitoring endpoints
    monitoring_ws_manager = MonitoringWebSocketManager()
    create_monitoring_endpoints(app, job_manager, progress_dir, monitoring_ws_manager)

    return app

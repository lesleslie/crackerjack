"""Unified WebSocket server for real-time monitoring dashboard."""

import asyncio
import json
import logging
import typing as t
from contextlib import suppress
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from crackerjack.mcp.websocket.monitoring_endpoints import MonitoringWebSocketManager
from crackerjack.monitoring.ai_agent_watchdog import AIAgentWatchdog
from crackerjack.monitoring.metrics_collector import (
    MetricsCollector,
    UnifiedDashboardMetrics,
)
from crackerjack.services.acb_cache_adapter import CrackerjackCache
from crackerjack.ui.dashboard_renderer import render_monitoring_dashboard

logger = logging.getLogger(__name__)


class CrackerjackMonitoringServer:
    """
    Unified monitoring server for Crackerjack with real-time WebSocket streaming.

    Provides comprehensive monitoring capabilities:
    - Real-time metrics via WebSocket
    - Historical data storage and retrieval
    - AI agent performance tracking
    - System health monitoring
    - Interactive dashboard interface
    """

    def __init__(self, port: int = 8675, host: str = "localhost"):
        self.port = port
        self.host = host

        # Core services
        self.app = FastAPI(title="Crackerjack Monitoring", version="1.0.0")
        self.cache = CrackerjackCache()
        self.metrics_collector = MetricsCollector(self.cache)
        self.websocket_manager = MonitoringWebSocketManager()
        self.ai_watchdog = AIAgentWatchdog()

        # Server state
        self.is_running = False
        self.server_task: asyncio.Task[None] | None = None

        # WebSocket connections
        self.active_connections: dict[str, WebSocket] = {}
        self.metrics_subscribers: set[WebSocket] = set()
        self.alerts_subscribers: set[WebSocket] = set()

        self._setup_routes()
        self._setup_websocket_endpoints()

    def _setup_routes(self) -> None:
        """Setup HTTP API routes."""

        @self.app.get("/")
        async def dashboard() -> HTMLResponse:
            """Main dashboard interface."""
            return HTMLResponse(content=self._get_dashboard_html())

        @self.app.get("/api/status")
        async def status() -> JSONResponse:
            """Get server status."""
            return JSONResponse(
                {
                    "status": "running" if self.is_running else "stopped",
                    "timestamp": datetime.now().isoformat(),
                    "host": self.host,
                    "port": self.port,
                    "metrics_collecting": self.metrics_collector.is_collecting,
                    "active_connections": len(self.active_connections),
                }
            )

        @self.app.get("/api/metrics")
        async def current_metrics() -> JSONResponse:
            """Get current metrics snapshot."""
            return JSONResponse(self.metrics_collector.get_current_metrics().to_dict())

        @self.app.get("/api/metrics/summary")
        async def metrics_summary() -> JSONResponse:
            """Get metrics summary for quick display."""
            return JSONResponse(self.metrics_collector.get_metrics_summary())

        @self.app.get("/api/metrics/history")
        async def metrics_history(hours: int = 1) -> JSONResponse:
            """Get metrics history."""
            history = self.metrics_collector.get_metrics_history(hours)
            return JSONResponse([m.to_dict() for m in history])

        @self.app.get("/api/agents/status")
        async def agents_status() -> JSONResponse:
            """Get AI agent status and performance."""
            return JSONResponse(
                {
                    "agents": {
                        name: {
                            "total_handled": metrics.total_issues_handled,
                            "success_rate": metrics.successful_fixes
                            / max(1, metrics.total_issues_handled),
                            "avg_confidence": metrics.average_confidence,
                            "avg_execution_time": metrics.average_execution_time,
                            "recent_failures": len(metrics.recent_failures),
                        }
                        for name, metrics in self.ai_watchdog.performance_metrics.items()
                    },
                    "alerts": [
                        {
                            "level": alert.level,
                            "message": alert.message,
                            "agent": alert.agent_name,
                            "timestamp": alert.timestamp.isoformat(),
                        }
                        for alert in self.ai_watchdog.get_recent_alerts(hours=1)
                    ],
                }
            )

        @self.app.post("/api/metrics/record")
        async def record_metrics(data: dict[str, Any]) -> JSONResponse:
            """Record metrics from external sources."""
            try:
                if "job_start" in data:
                    self.metrics_collector.record_job_start(data["job_start"]["job_id"])

                if "job_completion" in data:
                    completion = data["job_completion"]
                    self.metrics_collector.record_job_completion(
                        completion["job_id"], completion.get("success", True)
                    )

                if "quality_data" in data:
                    quality = data["quality_data"]
                    self.metrics_collector.record_quality_data(
                        quality.get("issues_found", 0),
                        quality.get("issues_fixed", 0),
                        quality.get("coverage", 0.0),
                        quality.get("success_rate", 0.0),
                    )

                return JSONResponse({"status": "recorded"})
            except Exception as e:
                logger.error(f"Error recording metrics: {e}")
                return JSONResponse({"error": str(e)}, status_code=400)

    def _setup_websocket_endpoints(self) -> None:
        """Setup WebSocket endpoints for real-time communication."""
        self.app.websocket("/ws/metrics")(self._handle_metrics_websocket)
        self.app.websocket("/ws/alerts")(self._handle_alerts_websocket)

    async def _handle_metrics_websocket(self, websocket: WebSocket) -> None:
        """Handle metrics WebSocket connection."""
        client_id = f"metrics_{datetime.now().timestamp()}"
        await websocket.accept()

        try:
            await self._setup_metrics_connection(websocket, client_id)
            await self._send_initial_metrics(websocket)
            await self._handle_metrics_messages(websocket)
        finally:
            self._cleanup_connection(websocket, client_id)

    async def _handle_alerts_websocket(self, websocket: WebSocket) -> None:
        """Handle alerts WebSocket connection."""
        client_id = f"alerts_{datetime.now().timestamp()}"
        await websocket.accept()

        try:
            await self._setup_alerts_connection(websocket, client_id)
            await self._send_initial_alerts(websocket)
            await self._handle_alerts_messages(websocket)
        finally:
            self._cleanup_connection(websocket, client_id)

    async def _setup_metrics_connection(
        self, websocket: WebSocket, client_id: str
    ) -> None:
        """Setup metrics websocket connection."""
        self.active_connections[client_id] = websocket
        self.metrics_subscribers.add(websocket)

    async def _setup_alerts_connection(
        self, websocket: WebSocket, client_id: str
    ) -> None:
        """Setup alerts websocket connection."""
        self.active_connections[client_id] = websocket
        self.alerts_subscribers.add(websocket)

    async def _send_initial_metrics(self, websocket: WebSocket) -> None:
        """Send initial metrics to websocket client."""
        current_metrics = self.metrics_collector.get_current_metrics()
        await websocket.send_text(
            json.dumps(
                {
                    "type": "initial_metrics",
                    "data": current_metrics.to_dict(),
                }
            )
        )

    async def _send_initial_alerts(self, websocket: WebSocket) -> None:
        """Send initial alerts to websocket client."""
        recent_alerts = self.ai_watchdog.get_recent_alerts(hours=24)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "initial_alerts",
                    "data": [
                        {
                            "level": alert.level,
                            "message": alert.message,
                            "agent": alert.agent_name,
                            "timestamp": alert.timestamp.isoformat(),
                        }
                        for alert in recent_alerts
                    ],
                }
            )
        )

    async def _handle_metrics_messages(self, websocket: WebSocket) -> None:
        """Handle incoming metrics websocket messages."""
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                await self._process_websocket_message(websocket, data)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    async def _handle_alerts_messages(self, websocket: WebSocket) -> None:
        """Handle incoming alerts websocket messages."""
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                await self._process_websocket_message(websocket, data)
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    async def _process_websocket_message(
        self, websocket: WebSocket, data: dict[str, Any]
    ) -> None:
        """Process incoming websocket message."""
        if data.get("type") == "ping":
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )

    def _cleanup_connection(self, websocket: WebSocket, client_id: str) -> None:
        """Clean up a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        self.metrics_subscribers.discard(websocket)
        self.alerts_subscribers.discard(websocket)

    async def start_monitoring(self, port: int | None = None) -> None:
        """Start the monitoring server with real-time updates."""
        if self.is_running:
            logger.warning("Monitoring server already running")
            return

        server_port = port or self.port

        try:
            # Start metrics collection
            await self.metrics_collector.start_collection()

            # Setup metrics listener for WebSocket broadcasting
            self.metrics_collector.add_metrics_listener(self._broadcast_metrics)

            # Start the web server
            config = uvicorn.Config(
                self.app,
                host=self.host,
                port=server_port,
                log_level="info",
            )
            server = uvicorn.Server(config)

            self.server_task = asyncio.create_task(server.serve())
            self.is_running = True

            logger.info(
                f"🚀 Crackerjack Monitoring Server started on http://{self.host}:{server_port}"
            )
            logger.info(f"📊 Dashboard available at http://{self.host}:{server_port}/")
            logger.info("🔗 WebSocket endpoints:")
            logger.info(f"   - Metrics: ws://{self.host}:{server_port}/ws/metrics")
            logger.info(f"   - Alerts: ws://{self.host}:{server_port}/ws/alerts")

            # Wait for server to complete
            await self.server_task

        except Exception as e:
            logger.error(f"Error starting monitoring server: {e}")
            await self.stop_monitoring()
            raise

    async def stop_monitoring(self) -> None:
        """Stop the monitoring server."""
        if not self.is_running:
            return

        self.is_running = False

        try:
            # Stop metrics collection
            await self.metrics_collector.stop_collection()

            # Close all WebSocket connections
            for websocket in list[t.Any](self.active_connections.values()):
                with suppress(Exception):
                    await websocket.close()
            self.active_connections.clear()
            self.metrics_subscribers.clear()
            self.alerts_subscribers.clear()

            # Stop server task
            if self.server_task and not self.server_task.done():
                self.server_task.cancel()
                try:
                    await self.server_task
                except asyncio.CancelledError:
                    pass

            logger.info("🔻 Crackerjack Monitoring Server stopped")

        except Exception as e:
            logger.error(f"Error stopping monitoring server: {e}")

    def _broadcast_metrics(self, metrics: UnifiedDashboardMetrics) -> None:
        """Broadcast metrics to all connected WebSocket clients."""
        if not self.metrics_subscribers:
            return

        message = {
            "type": "metrics_update",
            "data": metrics.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }

        # Use asyncio to broadcast to all subscribers
        asyncio.create_task(self._async_broadcast_metrics(message))

    async def _async_broadcast_metrics(self, message: dict[str, Any]) -> None:
        """Async broadcast helper."""
        disconnected = []
        for websocket in self.metrics_subscribers:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected clients
        self.metrics_subscribers.difference_update(disconnected)

    def _get_dashboard_html(self) -> str:
        """Generate the dashboard HTML interface."""
        return render_monitoring_dashboard()


# Convenience function for quick server startup
async def start_crackerjack_monitoring_server(
    port: int = 8675, host: str = "localhost"
) -> CrackerjackMonitoringServer:
    """Start a Crackerjack monitoring server."""
    server = CrackerjackMonitoringServer(port=port, host=host)
    await server.start_monitoring()
    return server


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8675

    async def main() -> None:
        server = CrackerjackMonitoringServer(port=port)
        try:
            await server.start_monitoring()
        except KeyboardInterrupt:
            logger.info("Shutting down monitoring server")
            await server.stop_monitoring()

    asyncio.run(main())

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
from crackerjack.services.cache import CrackerjackCache

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
        html_template = self._get_html_template()
        css_styles = self._get_dashboard_css()
        javascript_code = self._get_dashboard_javascript()

        return html_template.format(
            css_styles=css_styles, javascript_code=javascript_code
        )

    def _get_html_template(self) -> str:
        """Get the HTML template structure."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crackerjack Monitoring Dashboard</title>
    <style>{css_styles}</style>
</head>
<body>
    <div class="connection-status disconnected" id="connection-status">Connecting...</div>

    <div class="header">
        <h1>🔧 Crackerjack Monitoring Dashboard</h1>
        <p>Real-time project monitoring and analytics</p>
    </div>

    <div class="dashboard">
        <div class="card">
            <h3>System Health</h3>
            <div class="metric">
                <span class="metric-label">CPU Usage</span>
                <span class="metric-value" id="cpu">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Memory</span>
                <span class="metric-value" id="memory">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Uptime</span>
                <span class="metric-value" id="uptime">--</span>
            </div>
        </div>

        <div class="card">
            <h3>Quality Metrics</h3>
            <div class="metric">
                <span class="metric-label">Success Rate</span>
                <span class="metric-value" id="success-rate">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Issues Fixed</span>
                <span class="metric-value" id="issues-fixed">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Test Coverage</span>
                <span class="metric-value" id="coverage">--</span>
            </div>
        </div>

        <div class="card">
            <h3>Workflow Status</h3>
            <div class="metric">
                <span class="metric-label">Jobs Completed</span>
                <span class="metric-value" id="jobs-completed">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Avg Duration</span>
                <span class="metric-value" id="avg-duration">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Throughput</span>
                <span class="metric-value" id="throughput">--</span>
            </div>
        </div>

        <div class="card">
            <h3>AI Agents</h3>
            <div class="metric">
                <span class="metric-label">Active Agents</span>
                <span class="metric-value" id="active-agents">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Total Fixes</span>
                <span class="metric-value" id="total-fixes">--</span>
            </div>
            <div class="metric">
                <span class="metric-label">Cache Hit Rate</span>
                <span class="metric-value" id="cache-hit-rate">--</span>
            </div>
        </div>

        <div class="card" style="grid-column: 1/-1;">
            <h3>Activity Log</h3>
            <div id="logs"></div>
        </div>
    </div>

    <script>{javascript_code}</script>
</body>
</html>"""

    def _get_dashboard_css(self) -> str:
        """Get the CSS styles for the dashboard."""
        return """
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #1a1a1a; color: #fff; }
        .dashboard { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .card { background: #2d2d2d; border-radius: 8px; padding: 20px; border: 1px solid #404040; }
        .metric { display: flex; justify-content: space-between; margin: 10px 0; }
        .metric-label { color: #aaa; }
        .metric-value { color: #fff; font-weight: bold; }
        .status-good { color: #4ade80; }
        .status-warning { color: #fbbf24; }
        .status-error { color: #ef4444; }
        .header { text-align: center; margin-bottom: 30px; }
        .connection-status { position: fixed; top: 20px; right: 20px; padding: 10px; border-radius: 4px; }
        .connected { background: #16a34a; }
        .disconnected { background: #dc2626; }
        #logs { height: 200px; overflow-y: auto; background: #000; padding: 10px; border-radius: 4px; font-family: monospace; font-size: 12px; }
        """

    def _get_dashboard_javascript(self) -> str:
        """Get the JavaScript code for the dashboard."""
        js_variables = self._get_js_variables()
        js_websocket_handlers = self._get_js_websocket_handlers()
        js_dashboard_functions = self._get_js_dashboard_functions()
        js_initialization = self._get_js_initialization()

        return f"""
        {js_variables}
        {js_websocket_handlers}
        {js_dashboard_functions}
        {js_initialization}
        """

    def _get_js_variables(self) -> str:
        """Get JavaScript variable declarations."""
        return """
        const wsUrl = `ws://${window.location.host}/ws/metrics`;
        let ws = null;
        let reconnectInterval = 5000;
        """

    def _get_js_websocket_handlers(self) -> str:
        """Get JavaScript WebSocket connection handlers."""
        return """
        function connect() {
            ws = new WebSocket(wsUrl);
            ws.onopen = handleWebSocketOpen;
            ws.onmessage = handleWebSocketMessage;
            ws.onclose = handleWebSocketClose;
            ws.onerror = handleWebSocketError;
        }

        function handleWebSocketOpen() {
            document.getElementById('connection-status').textContent = 'Connected';
            document.getElementById('connection-status').className = 'connection-status connected';
            log('Connected to monitoring server');
        }

        function handleWebSocketMessage(event) {
            const message = JSON.parse(event.data);
            if (message.type === 'metrics_update' || message.type === 'initial_metrics') {
                updateDashboard(message.data);
            }
        }

        function handleWebSocketClose() {
            document.getElementById('connection-status').textContent = 'Disconnected';
            document.getElementById('connection-status').className = 'connection-status disconnected';
            log('Disconnected from monitoring server');
            setTimeout(connect, reconnectInterval);
        }

        function handleWebSocketError(error) {
            log(`WebSocket error: ${error}`);
        }
        """

    def _get_js_dashboard_functions(self) -> str:
        """Get JavaScript dashboard utility functions."""
        return """
        function updateDashboard(data) {
            updateSystemMetrics(data.system);
            updateQualityMetrics(data.quality);
            updateWorkflowMetrics(data.workflow);
            updateAgentMetrics(data.agents);
        }

        function updateSystemMetrics(system) {
            document.getElementById('cpu').textContent = system.cpu_usage.toFixed(1) + '%';
            document.getElementById('memory').textContent = (system.memory_usage_mb / 1024).toFixed(1) + 'GB';
            document.getElementById('uptime').textContent = formatUptime(system.uptime_seconds);
        }

        function updateQualityMetrics(quality) {
            document.getElementById('success-rate').textContent = (quality.success_rate * 100).toFixed(1) + '%';
            document.getElementById('issues-fixed').textContent = quality.issues_fixed;
            document.getElementById('coverage').textContent = (quality.test_coverage * 100).toFixed(1) + '%';
        }

        function updateWorkflowMetrics(workflow) {
            document.getElementById('jobs-completed').textContent = workflow.jobs_completed;
            document.getElementById('avg-duration').textContent = workflow.average_job_duration.toFixed(1) + 's';
            document.getElementById('throughput').textContent = workflow.throughput_per_hour.toFixed(1) + '/h';
        }

        function updateAgentMetrics(agents) {
            document.getElementById('active-agents').textContent = agents.active_agents;
            document.getElementById('total-fixes').textContent = agents.total_fixes_applied;
            document.getElementById('cache-hit-rate').textContent = (agents.cache_hit_rate * 100).toFixed(1) + '%';
        }

        function formatUptime(seconds) {
            if (seconds < 3600) return Math.floor(seconds/60) + 'm';
            if (seconds < 86400) return Math.floor(seconds/3600) + 'h';
            return Math.floor(seconds/86400) + 'd';
        }

        function log(message) {
            const logs = document.getElementById('logs');
            const timestamp = new Date().toLocaleTimeString();
            logs.innerHTML += `<div>[${timestamp}] ${message}</div>`;
            logs.scrollTop = logs.scrollHeight;
        }
        """

    def _get_js_initialization(self) -> str:
        """Get JavaScript initialization code."""
        return """
        // Start connection
        connect();

        // Periodic ping to keep connection alive
        setInterval(() => {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({type: 'ping'}));
            }
        }, 30000);
        """


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
            logger.info("Shutting down monitoring server...")
            await server.stop_monitoring()

    asyncio.run(main())

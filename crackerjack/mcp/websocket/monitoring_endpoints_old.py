"""Enhanced WebSocket endpoints for unified monitoring dashboard."""

import asyncio
import json
import typing as t
from datetime import datetime
from pathlib import Path

from acb.depends import depends
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from crackerjack.events import WorkflowEventTelemetry
from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.dependency_analyzer import (
    DependencyAnalyzer,
    DependencyGraph,
)
from crackerjack.services.monitoring.error_pattern_analyzer import (
    ErrorPatternAnalyzer,
)
from crackerjack.services.quality.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,
    QualityAlert,
    SystemHealthStatus,
    TrendDirection,
    UnifiedMetrics,
)
from crackerjack.services.quality.quality_intelligence import (
    QualityIntelligenceService,
)
from crackerjack.ui.dashboard_renderer import render_monitoring_dashboard


class TelemetryEventModel(BaseModel):
    event_type: str
    timestamp: datetime
    source: str | None = None
    payload: t.Any = None

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "TelemetryEventModel":
        return cls(
            event_type=data.get("event_type", ""),
            timestamp=datetime.fromisoformat(data.get("timestamp")),
            source=data.get("source"),
            payload=data.get("payload"),
        )


class TelemetrySnapshotModel(BaseModel):
    counts: dict[str, int]
    recent_events: list[TelemetryEventModel]
    last_error: TelemetryEventModel | None = None

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, t.Any]) -> "TelemetrySnapshotModel":
        events = [
            TelemetryEventModel.from_dict(event)
            for event in snapshot.get("recent_events", [])
        ]
        last_error = snapshot.get("last_error")
        return cls(
            counts=snapshot.get("counts", {}),
            recent_events=events,
            last_error=(
                TelemetryEventModel.from_dict(last_error)
                if last_error is not None
                else None
            ),
        )


class TelemetryResponseModel(BaseModel):
    status: str
    data: TelemetrySnapshotModel
    timestamp: datetime


class UnifiedMetricsModel(BaseModel):
    timestamp: datetime
    quality_score: int
    test_coverage: float
    hook_duration: float
    active_jobs: int
    error_count: int
    trend_direction: TrendDirection
    predictions: dict[str, t.Any] = {}

    @classmethod
    def from_domain(cls, metrics: UnifiedMetrics) -> "UnifiedMetricsModel":
        return cls(
            timestamp=metrics.timestamp,
            quality_score=metrics.quality_score,
            test_coverage=metrics.test_coverage,
            hook_duration=metrics.hook_duration,
            active_jobs=metrics.active_jobs,
            error_count=metrics.error_count,
            trend_direction=metrics.trend_direction,
            predictions=metrics.predictions,
        )


class HealthResponseModel(BaseModel):
    status: str
    data: UnifiedMetricsModel
    timestamp: datetime


from .jobs import JobManager


class MonitoringWebSocketManager:
    """Manages WebSocket connections for real-time monitoring."""

    def __init__(self) -> None:
        self.active_connections: dict[str, WebSocket] = {}
        self.metrics_subscribers: set[WebSocket] = set()
        self.alerts_subscribers: set[WebSocket] = set()

    async def connect_metrics(self, websocket: WebSocket, client_id: str) -> None:
        """Connect a client for metrics streaming."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.metrics_subscribers.add(websocket)

    async def connect_alerts(self, websocket: WebSocket, client_id: str) -> None:
        """Connect a client for alert notifications."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.alerts_subscribers.add(websocket)

    def disconnect(self, websocket: WebSocket, client_id: str) -> None:
        """Disconnect a client."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        self.metrics_subscribers.discard(websocket)
        self.alerts_subscribers.discard(websocket)

    async def broadcast_metrics(self, metrics: UnifiedMetrics) -> None:
        """Broadcast metrics to all connected metrics subscribers."""
        message = {
            "type": "metrics_update",
            "data": metrics.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }

        disconnected = []
        for websocket in self.metrics_subscribers:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected clients
        self.metrics_subscribers.difference_update(disconnected)

    async def broadcast_alert(self, alert: QualityAlert) -> None:
        """Broadcast alert to all connected alert subscribers."""
        message = {
            "type": "alert",
            "data": alert.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }

        disconnected = []
        for websocket in self.alerts_subscribers:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                disconnected.append(websocket)

        # Clean up disconnected clients
        self.alerts_subscribers.difference_update(disconnected)


def create_monitoring_endpoints(
    app: FastAPI,
    job_manager: JobManager,
    progress_dir: Path,
    ws_manager: MonitoringWebSocketManager,
) -> None:
    """Add monitoring endpoints to the FastAPI app."""
    services = _initialize_monitoring_services(progress_dir)

    _register_websocket_endpoints(app, job_manager, ws_manager, services)
    _register_rest_api_endpoints(app, job_manager, services)
    _register_dashboard_endpoint(app)


def _initialize_monitoring_services(progress_dir: Path) -> dict[str, t.Any]:
    """Initialize all monitoring services."""
    cache = CrackerjackCache()
    quality_service = EnhancedQualityBaselineService(cache=cache)
    intelligence_service = QualityIntelligenceService(quality_service)
    dependency_analyzer = DependencyAnalyzer(progress_dir.parent)
    error_analyzer = ErrorPatternAnalyzer(progress_dir.parent)
    try:
        telemetry = depends.get_sync(WorkflowEventTelemetry)
    except Exception:
        telemetry = WorkflowEventTelemetry()

    return {
        "cache": cache,
        "quality_service": quality_service,
        "intelligence_service": intelligence_service,
        "dependency_analyzer": dependency_analyzer,
        "error_analyzer": error_analyzer,
        "telemetry": telemetry,
    }


def _register_websocket_endpoints(
    app: FastAPI,
    job_manager: JobManager,
    ws_manager: MonitoringWebSocketManager,
    services: dict[str, t.Any],
) -> None:
    """Register all WebSocket endpoints."""
    _register_metrics_websockets(app, job_manager, ws_manager, services)
    _register_intelligence_websockets(app, ws_manager, services)
    _register_dependency_websockets(app, ws_manager, services)
    _register_heatmap_websockets(app, ws_manager, services)


def _register_metrics_websockets(
    app: FastAPI,
    job_manager: JobManager,
    ws_manager: MonitoringWebSocketManager,
    services: dict[str, t.Any],
) -> None:
    """Register metrics-related WebSocket endpoints."""
    quality_service = services["quality_service"]

    @app.websocket("/ws/metrics/live")
    async def websocket_metrics_live(websocket: WebSocket) -> None:
        """WebSocket endpoint for live metrics streaming."""
        await _handle_live_metrics_websocket(
            websocket, ws_manager, quality_service, job_manager
        )

    @app.websocket("/ws/metrics/historical/{days}")
    async def websocket_metrics_historical(websocket: WebSocket, days: int) -> None:
        """WebSocket endpoint for historical metrics data."""
        await _handle_historical_metrics_websocket(
            websocket, ws_manager, quality_service, days
        )

    @app.websocket("/ws/alerts/subscribe")
    async def websocket_alerts_subscribe(websocket: WebSocket) -> None:
        """WebSocket endpoint for alert subscriptions."""
        await _handle_alerts_websocket(websocket, ws_manager)

    @app.websocket("/ws/dashboard/overview")
    async def websocket_dashboard_overview(websocket: WebSocket) -> None:
        """WebSocket endpoint for comprehensive dashboard data."""
        await _handle_dashboard_websocket(
            websocket, ws_manager, quality_service, job_manager
        )


async def _handle_live_metrics_websocket(
    websocket: WebSocket,
    ws_manager: MonitoringWebSocketManager,
    quality_service: EnhancedQualityBaselineService,
    job_manager: JobManager,
) -> None:
    """Handle live metrics WebSocket connection."""
    client_id = f"metrics_{datetime.now().timestamp()}"
    await ws_manager.connect_metrics(websocket, client_id)

    try:
        # Send initial metrics
        current_metrics = await get_current_metrics(quality_service, job_manager)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "initial_metrics",
                    "data": current_metrics.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Keep connection alive and handle client messages
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                data = json.loads(message)

                if data.get("type") == "request_update":
                    metrics = await get_current_metrics(quality_service, job_manager)
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "metrics_update",
                                "data": metrics.to_dict(),
                                "timestamp": datetime.now().isoformat(),
                            }
                        )
                    )

            except TimeoutError:
                metrics = await get_current_metrics(quality_service, job_manager)
                await ws_manager.broadcast_metrics(metrics)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, client_id)


async def _handle_historical_metrics_websocket(
    websocket: WebSocket,
    ws_manager: MonitoringWebSocketManager,
    quality_service: EnhancedQualityBaselineService,
    days: int,
) -> None:
    """Handle historical metrics WebSocket connection."""
    if days > 365:
        await websocket.close(code=1008, reason="Days parameter too large")
        return

    client_id = f"historical_{datetime.now().timestamp()}"
    await ws_manager.connect_metrics(websocket, client_id)

    try:
        baselines = await quality_service.aget_recent_baselines(limit=days)
        historical_data = _convert_baselines_to_metrics(baselines)

        await _send_historical_data_chunks(websocket, historical_data)

        # Keep connection open for updates
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, client_id)


def _convert_baselines_to_metrics(
    baselines: list[t.Any],
) -> list[UnifiedMetrics]:
    """Convert quality baselines to UnifiedMetrics objects."""
    return [
        UnifiedMetrics(
            timestamp=baseline.timestamp,
            quality_score=baseline.quality_score,
            test_coverage=baseline.coverage_percent,
            hook_duration=0.0,
            active_jobs=0,
            error_count=baseline.hook_failures
            + baseline.security_issues
            + baseline.type_errors
            + baseline.linting_issues,
            trend_direction=TrendDirection.STABLE,
            predictions={},
        )
        for baseline in baselines
    ]


async def _send_historical_data_chunks(
    websocket: WebSocket, historical_data: list[UnifiedMetrics]
) -> None:
    """Send historical data in chunks to avoid overwhelming the client."""
    chunk_size = 100

    for i in range(0, len(historical_data), chunk_size):
        chunk = historical_data[i : i + chunk_size]
        await websocket.send_text(
            json.dumps(
                {
                    "type": "historical_chunk",
                    "data": [m.to_dict() for m in chunk],
                    "chunk_index": i // chunk_size,
                    "total_chunks": (len(historical_data) + chunk_size - 1)
                    // chunk_size,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )
        await asyncio.sleep(0.1)

    # Send completion signal
    await websocket.send_text(
        json.dumps(
            {
                "type": "historical_complete",
                "total_records": len(historical_data),
                "timestamp": datetime.now().isoformat(),
            }
        )
    )


async def _handle_alerts_websocket(
    websocket: WebSocket, ws_manager: MonitoringWebSocketManager
) -> None:
    """Handle alerts WebSocket connection."""
    client_id = f"alerts_{datetime.now().timestamp()}"
    await ws_manager.connect_alerts(websocket, client_id)

    try:
        # Send current active alerts - would need to track these separately
        active_alerts = []  # For now, empty list
        await websocket.send_text(
            json.dumps(
                {
                    "type": "active_alerts",
                    "data": [alert.to_dict() for alert in active_alerts],
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Keep connection alive
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, client_id)


async def _handle_dashboard_websocket(
    websocket: WebSocket,
    ws_manager: MonitoringWebSocketManager,
    quality_service: EnhancedQualityBaselineService,
    job_manager: JobManager,
) -> None:
    """Handle dashboard overview WebSocket connection."""
    client_id = f"dashboard_{datetime.now().timestamp()}"
    await ws_manager.connect_metrics(websocket, client_id)

    try:
        telemetry: WorkflowEventTelemetry | None
        try:
            telemetry = depends.get(WorkflowEventTelemetry)
        except Exception:
            telemetry = None

        while True:
            current_metrics = await get_current_metrics(quality_service, job_manager)

            metrics_dict = _create_dashboard_metrics_dict(current_metrics)

            dashboard_state = await asyncio.to_thread(
                quality_service.create_dashboard_state,
                metrics_dict,
                len(job_manager.active_connections),
                7,
            )

            telemetry_snapshot: dict[str, t.Any] | None = None
            if telemetry is not None:
                telemetry_snapshot = await telemetry.snapshot()

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "dashboard_update",
                        "data": dashboard_state.to_dict(),
                        "telemetry": telemetry_snapshot,
                        "timestamp": datetime.now().isoformat(),
                    }
                )
            )

            await asyncio.sleep(10)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, client_id)


def _create_dashboard_metrics_dict(current_metrics: UnifiedMetrics) -> dict[str, t.Any]:
    """Create basic metrics dict for dashboard state."""
    return {
        "coverage_percent": current_metrics.test_coverage,
        "test_count": 0,
        "test_pass_rate": 100.0,
        "hook_failures": 0,
        "complexity_violations": 0,
        "security_issues": 0,
        "type_errors": 0,
        "linting_issues": 0,
    }


def _register_intelligence_websockets(
    app: FastAPI,
    ws_manager: MonitoringWebSocketManager,
    services: dict[str, t.Any],
) -> None:
    """Register intelligence-related WebSocket endpoints."""
    intelligence_service = services["intelligence_service"]

    @app.websocket("/ws/intelligence/anomalies")
    async def websocket_anomaly_detection(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time anomaly detection."""
        await _handle_anomaly_detection_websocket(
            websocket, ws_manager, intelligence_service
        )

    @app.websocket("/ws/intelligence/predictions")
    async def websocket_predictions(websocket: WebSocket) -> None:
        """WebSocket endpoint for quality predictions."""
        await _handle_predictions_websocket(websocket, ws_manager, intelligence_service)

    @app.websocket("/ws/intelligence/patterns")
    async def websocket_pattern_analysis(websocket: WebSocket) -> None:
        """WebSocket endpoint for pattern recognition and correlation analysis."""
        await _handle_pattern_analysis_websocket(
            websocket, ws_manager, intelligence_service
        )


async def _handle_anomaly_detection_websocket(
    websocket: WebSocket,
    ws_manager: MonitoringWebSocketManager,
    intelligence_service: QualityIntelligenceService,
) -> None:
    """Handle anomaly detection WebSocket connection."""
    client_id = f"anomalies_{datetime.now().timestamp()}"
    await ws_manager.connect_metrics(websocket, client_id)

    try:
        # Send initial anomaly analysis
        anomalies = intelligence_service.detect_anomalies(days=7)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "anomalies_initial",
                    "data": [anomaly.to_dict() for anomaly in anomalies],
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Stream ongoing anomaly detection
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                data = json.loads(message)

                if data.get("type") == "request_analysis":
                    await _handle_anomaly_request(websocket, intelligence_service, data)

            except TimeoutError:
                await _send_periodic_anomaly_check(websocket, intelligence_service)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, client_id)


async def _handle_anomaly_request(
    websocket: WebSocket,
    intelligence_service: QualityIntelligenceService,
    data: dict[str, t.Any],
) -> None:
    """Handle anomaly analysis request."""
    days = data.get("days", 7)
    metrics_filter = data.get("metrics")

    anomalies = intelligence_service.detect_anomalies(days=days, metrics=metrics_filter)
    await websocket.send_text(
        json.dumps(
            {
                "type": "anomalies_update",
                "data": [anomaly.to_dict() for anomaly in anomalies],
                "timestamp": datetime.now().isoformat(),
            }
        )
    )


async def _send_periodic_anomaly_check(
    websocket: WebSocket, intelligence_service: QualityIntelligenceService
) -> None:
    """Send periodic anomaly check."""
    anomalies = intelligence_service.detect_anomalies(days=1)
    if anomalies:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "anomalies_alert",
                    "data": [anomaly.to_dict() for anomaly in anomalies],
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )


async def _handle_predictions_websocket(
    websocket: WebSocket,
    ws_manager: MonitoringWebSocketManager,
    intelligence_service: QualityIntelligenceService,
) -> None:
    """Handle predictions WebSocket connection."""
    client_id = f"predictions_{datetime.now().timestamp()}"
    await ws_manager.connect_metrics(websocket, client_id)

    try:
        # Send initial predictions
        insights = intelligence_service.generate_comprehensive_insights(days=30)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "predictions_initial",
                    "data": insights.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Stream prediction updates
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(), timeout=300.0
                )
                data = json.loads(message)

                if data.get("type") == "request_predictions":
                    await _handle_prediction_request(
                        websocket, intelligence_service, data
                    )

            except TimeoutError:
                await _send_periodic_prediction_update(websocket, intelligence_service)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, client_id)


async def _handle_prediction_request(
    websocket: WebSocket,
    intelligence_service: QualityIntelligenceService,
    data: dict[str, t.Any],
) -> None:
    """Handle prediction request."""
    days = data.get("days", 30)
    horizon = data.get("horizon", 7)

    insights = intelligence_service.generate_comprehensive_insights(days=days)

    # Generate specific predictions for requested horizon
    predictions = {}
    all_predictions = intelligence_service.generate_advanced_predictions(
        horizon_days=horizon
    )
    for metric in ("quality_score", "test_coverage", "hook_duration"):
        # Find the prediction for this specific metric
        pred = next((p for p in all_predictions if p.metric_name == metric), None)
        if pred:
            predictions[metric] = pred.to_dict()

    await websocket.send_text(
        json.dumps(
            {
                "type": "predictions_update",
                "data": {
                    "insights": insights.to_dict(),
                    "predictions": predictions,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )
    )


async def _send_periodic_prediction_update(
    websocket: WebSocket, intelligence_service: QualityIntelligenceService
) -> None:
    """Send periodic predictions update."""
    insights = intelligence_service.generate_comprehensive_insights(days=7)
    await websocket.send_text(
        json.dumps(
            {
                "type": "predictions_periodic",
                "data": insights.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    )


async def _handle_pattern_analysis_websocket(
    websocket: WebSocket,
    ws_manager: MonitoringWebSocketManager,
    intelligence_service: QualityIntelligenceService,
) -> None:
    """Handle pattern analysis WebSocket connection."""
    client_id = f"patterns_{datetime.now().timestamp()}"
    await ws_manager.connect_metrics(websocket, client_id)

    try:
        # Send initial pattern analysis
        patterns = intelligence_service.identify_patterns(days=30)
        await websocket.send_text(
            json.dumps(
                {
                    "type": "patterns_initial",
                    "data": patterns,
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Stream pattern updates
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(), timeout=180.0
                )
                data = json.loads(message)

                if data.get("type") == "request_patterns":
                    await _handle_pattern_request(websocket, intelligence_service, data)

            except TimeoutError:
                await _send_periodic_pattern_update(websocket, intelligence_service)

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, client_id)


async def _handle_pattern_request(
    websocket: WebSocket,
    intelligence_service: QualityIntelligenceService,
    data: dict[str, t.Any],
) -> None:
    """Handle pattern analysis request."""
    days = data.get("days", 30)
    patterns = intelligence_service.identify_patterns(days=days)

    await websocket.send_text(
        json.dumps(
            {
                "type": "patterns_update",
                "data": patterns,
                "timestamp": datetime.now().isoformat(),
            }
        )
    )


async def _send_periodic_pattern_update(
    websocket: WebSocket, intelligence_service: QualityIntelligenceService
) -> None:
    """Send periodic pattern analysis update."""
    patterns = intelligence_service.identify_patterns(days=7)
    await websocket.send_text(
        json.dumps(
            {
                "type": "patterns_periodic",
                "data": patterns,
                "timestamp": datetime.now().isoformat(),
            }
        )
    )


def _register_dependency_websockets(
    app: FastAPI,
    ws_manager: MonitoringWebSocketManager,
    services: dict[str, t.Any],
) -> None:
    """Register dependency-related WebSocket endpoints."""
    dependency_analyzer = services["dependency_analyzer"]

    @app.websocket("/ws/dependencies/graph")
    async def websocket_dependency_graph(websocket: WebSocket) -> None:
        """WebSocket endpoint for dependency graph data."""
        await _handle_dependency_graph_websocket(
            websocket, ws_manager, dependency_analyzer
        )


async def _handle_dependency_graph_websocket(
    websocket: WebSocket,
    ws_manager: MonitoringWebSocketManager,
    dependency_analyzer: DependencyAnalyzer,
) -> None:
    """Handle dependency graph WebSocket connection."""
    client_id = f"dependencies_{datetime.now().timestamp()}"
    await ws_manager.connect_metrics(websocket, client_id)

    try:
        # Send initial message
        await websocket.send_text(
            json.dumps(
                {
                    "type": "analysis_started",
                    "message": "Starting dependency analysis...",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Generate dependency graph
        graph = dependency_analyzer.analyze_project()

        # Send the complete graph data
        await websocket.send_text(
            json.dumps(
                {
                    "type": "graph_data",
                    "data": graph.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

        # Listen for client requests
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                data = json.loads(message)

                await _handle_dependency_request(
                    websocket, dependency_analyzer, graph, data
                )

            except TimeoutError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "keepalive",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                )

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, client_id)


async def _handle_dependency_request(
    websocket: WebSocket,
    dependency_analyzer: DependencyAnalyzer,
    graph: DependencyGraph,
    data: dict[str, t.Any],
) -> None:
    """Handle dependency graph request."""
    if data.get("type") == "filter_request":
        filtered_graph = await _apply_graph_filters(graph, data.get("filters", {}))
        await websocket.send_text(
            json.dumps(
                {
                    "type": "filtered_graph",
                    "data": filtered_graph.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )

    elif data.get("type") == "refresh_request":
        fresh_graph = dependency_analyzer.analyze_project()
        await websocket.send_text(
            json.dumps(
                {
                    "type": "graph_data",
                    "data": fresh_graph.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )


def _register_rest_api_endpoints(
    app: FastAPI, job_manager: JobManager, services: dict[str, t.Any]
) -> None:
    """Register all REST API endpoints."""
    _register_metrics_api_endpoints(app, job_manager, services)
    _register_intelligence_api_endpoints(app, services)
    _register_dependency_api_endpoints(app, services)
    _register_heatmap_api_endpoints(app, services)
    _register_telemetry_api_endpoints(app, job_manager, services)


def _register_telemetry_api_endpoints(
    app: FastAPI, job_manager: JobManager, services: dict[str, t.Any]
) -> None:
    """Register telemetry and dashboard REST endpoints."""
    telemetry: WorkflowEventTelemetry = services["telemetry"]
    quality_service = services["quality_service"]

    @app.get(
        "/monitoring/events",
        response_model=TelemetryResponseModel,
        summary="Get workflow telemetry snapshot",
    )
    async def get_monitoring_events() -> TelemetryResponseModel:
        snapshot = await telemetry.snapshot()
        return TelemetryResponseModel(
            status="success",
            data=TelemetrySnapshotModel.from_snapshot(snapshot),
            timestamp=datetime.now(),
        )

    @app.post(
        "/monitoring/events/reset",
        response_model=TelemetryResponseModel,
        summary="Reset workflow telemetry history",
    )
    async def reset_monitoring_events() -> TelemetryResponseModel:
        await telemetry.reset()
        snapshot = await telemetry.snapshot()
        return TelemetryResponseModel(
            status="success",
            data=TelemetrySnapshotModel.from_snapshot(snapshot),
            timestamp=datetime.now(),
        )

    @app.get(
        "/monitoring/health",
        response_model=HealthResponseModel,
        summary="Retrieve aggregated monitoring health metrics",
    )
    async def get_monitoring_health() -> HealthResponseModel:
        unified_metrics = await get_current_metrics(quality_service, job_manager)
        return HealthResponseModel(
            status=_derive_health_status(unified_metrics),
            data=UnifiedMetricsModel.from_domain(unified_metrics),
            timestamp=datetime.now(),
        )


def _register_metrics_api_endpoints(
    app: FastAPI, job_manager: JobManager, services: dict[str, t.Any]
) -> None:
    """Register metrics-related REST API endpoints."""
    quality_service = services["quality_service"]

    @app.get("/api/metrics/summary")
    async def get_metrics_summary() -> None:
        """Get current system summary."""
        try:
            current_metrics = await get_current_metrics(quality_service, job_manager)
            return JSONResponse(
                {
                    "status": "success",
                    "data": current_metrics.to_dict(),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/trends/quality")
    async def get_quality_trends(days: int = 30) -> None:
        """Get quality trend analysis."""
        return await _handle_quality_trends_request(quality_service, days)

    @app.get("/api/alerts/configure")
    async def get_alert_configuration() -> None:
        """Get current alert configuration."""
        return await _handle_get_alert_configuration(quality_service)

    @app.post("/api/alerts/configure")
    async def update_alert_configuration(config: dict) -> None:
        """Update alert configuration."""
        return await _handle_update_alert_configuration(quality_service, config)

    @app.get("/api/export/data")
    async def export_data(days: int = 30, format: str = "json") -> None:
        """Export historical data for external analysis."""
        return await _handle_export_data_request(quality_service, days, format)


def _derive_health_status(metrics: UnifiedMetrics) -> str:
    """Derive a coarse health status string from unified metrics."""
    if metrics.error_count > 5 or metrics.quality_score < 40:
        return "critical"
    if metrics.error_count > 0 or metrics.quality_score < 60:
        return "warning"
    return "healthy"


async def _handle_quality_trends_request(
    quality_service: EnhancedQualityBaselineService, days: int
) -> JSONResponse:
    """Handle quality trends API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        trends = await asyncio.to_thread(
            quality_service.analyze_quality_trend,
            days,
        )
        return JSONResponse(
            {
                "status": "success",
                "data": trends.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_get_alert_configuration(
    quality_service: EnhancedQualityBaselineService,
) -> JSONResponse:
    """Handle get alert configuration API request."""
    try:
        config = quality_service.get_alert_thresholds()
        return JSONResponse(
            {
                "status": "success",
                "data": config,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_update_alert_configuration(
    quality_service: EnhancedQualityBaselineService, config: dict
) -> JSONResponse:
    """Handle update alert configuration API request."""
    try:
        # Update individual thresholds
        for metric, threshold in config.items():
            quality_service.set_alert_threshold(metric, threshold)
        return JSONResponse(
            {
                "status": "success",
                "message": "Alert configuration updated",
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_export_data_request(
    quality_service: EnhancedQualityBaselineService, days: int, format_type: str
) -> JSONResponse | t.Any:
    """Handle export data API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        if format_type not in ("json", "csv"):
            raise HTTPException(
                status_code=400, detail="Format must be 'json' or 'csv'"
            )

        historical_baselines = await quality_service.aget_recent_baselines(limit=days)

        if format_type == "csv":
            return _export_csv_data(historical_baselines, days)
        else:
            data = [baseline.to_dict() for baseline in historical_baselines]
            return JSONResponse(
                {
                    "status": "success",
                    "data": data,
                    "timestamp": datetime.now().isoformat(),
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _export_csv_data(historical_baselines: list[t.Any], days: int) -> t.Any:
    """Export data in CSV format."""
    import csv
    from io import StringIO

    from fastapi.responses import Response

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow(
        [
            "timestamp",
            "git_hash",
            "quality_score",
            "coverage_percent",
            "test_count",
            "test_pass_rate",
            "hook_failures",
            "complexity_violations",
            "security_issues",
            "type_errors",
            "linting_issues",
        ]
    )

    # Write data
    for baseline in historical_baselines:
        writer.writerow(
            [
                baseline.timestamp.isoformat(),
                baseline.git_hash,
                baseline.quality_score,
                baseline.coverage_percent,
                baseline.test_count,
                baseline.test_pass_rate,
                baseline.hook_failures,
                baseline.complexity_violations,
                baseline.security_issues,
                baseline.type_errors,
                baseline.linting_issues,
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f"attachment; filename=crackerjack_metrics_{days}d.csv"
            )
        },
    )


def _register_intelligence_api_endpoints(
    app: FastAPI, services: dict[str, t.Any]
) -> None:
    """Register intelligence-related REST API endpoints."""
    intelligence_service = services["intelligence_service"]

    @app.get("/api/intelligence/anomalies")
    async def get_anomalies(days: int = 7, metrics: str = None) -> None:
        """Get anomaly detection results."""
        return await _handle_anomalies_request(intelligence_service, days, metrics)

    @app.get("/api/intelligence/predictions/{metric}")
    async def get_metric_prediction(metric: str, horizon_days: int = 7) -> None:
        """Get prediction for a specific metric."""
        return await _handle_metric_prediction_request(
            intelligence_service, metric, horizon_days
        )

    @app.get("/api/intelligence/insights")
    async def get_quality_insights(days: int = 30) -> None:
        """Get comprehensive quality insights."""
        return await _handle_quality_insights_request(intelligence_service, days)

    @app.get("/api/intelligence/patterns")
    async def get_pattern_analysis(days: int = 30) -> None:
        """Get pattern recognition analysis."""
        return await _handle_pattern_analysis_request(intelligence_service, days)

    @app.post("/api/intelligence/analyze")
    async def run_comprehensive_analysis(request: dict) -> None:
        """Run comprehensive intelligence analysis."""
        return await _handle_comprehensive_analysis_request(
            intelligence_service, request
        )


async def _handle_anomalies_request(
    intelligence_service: QualityIntelligenceService, days: int, metrics: str | None
) -> JSONResponse:
    """Handle anomalies API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        metrics_list = metrics.split(",") if metrics else None
        anomalies = intelligence_service.detect_anomalies(
            days=days, metrics=metrics_list
        )

        return JSONResponse(
            {
                "status": "success",
                "data": [anomaly.to_dict() for anomaly in anomalies],
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_metric_prediction_request(
    intelligence_service: QualityIntelligenceService, metric: str, horizon_days: int
) -> JSONResponse:
    """Handle metric prediction API request."""
    try:
        if horizon_days > 30:
            raise HTTPException(status_code=400, detail="Horizon too far in the future")

        all_predictions = intelligence_service.generate_advanced_predictions(
            horizon_days
        )
        prediction = next((p for p in all_predictions if p.metric_name == metric), None)
        if not prediction:
            raise HTTPException(status_code=404, detail="Prediction not available")

        return JSONResponse(
            {
                "status": "success",
                "data": prediction.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_quality_insights_request(
    intelligence_service: QualityIntelligenceService, days: int
) -> JSONResponse:
    """Handle quality insights API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        insights = intelligence_service.generate_comprehensive_insights(days=days)

        return JSONResponse(
            {
                "status": "success",
                "data": insights.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_pattern_analysis_request(
    intelligence_service: QualityIntelligenceService, days: int
) -> JSONResponse:
    """Handle pattern analysis API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        patterns = intelligence_service.identify_patterns(days=days)

        return JSONResponse(
            {
                "status": "success",
                "data": patterns,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_comprehensive_analysis_request(
    intelligence_service: QualityIntelligenceService, request: dict
) -> JSONResponse:
    """Handle comprehensive analysis API request."""
    try:
        days = request.get("days", 30)

        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        results = await _build_comprehensive_analysis_results(
            intelligence_service, request, days
        )

        return JSONResponse(
            {
                "status": "success",
                "data": results,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _build_comprehensive_analysis_results(
    intelligence_service: QualityIntelligenceService, request: dict, days: int
) -> dict[str, t.Any]:
    """Build comprehensive analysis results based on request parameters."""
    results = {}

    if request.get("include_anomalies", True):
        results["anomalies"] = [
            anomaly.to_dict()
            for anomaly in intelligence_service.detect_anomalies(days=days)
        ]

    if request.get("include_predictions", True):
        insights = intelligence_service.generate_comprehensive_insights(days=days)
        results["insights"] = insights.to_dict()

        # Generate specific predictions
        predictions = {}
        for metric in ("quality_score", "test_coverage", "hook_duration"):
            pred = intelligence_service.generate_advanced_predictions(
                metric, horizon_days=7
            )
            if pred:
                predictions[metric] = pred.to_dict()
        results["predictions"] = predictions

    if request.get("include_patterns", True):
        results["patterns"] = intelligence_service.identify_patterns(days=days)

    return results


def _register_dependency_api_endpoints(
    app: FastAPI, services: dict[str, t.Any]
) -> None:
    """Register dependency-related REST API endpoints."""
    dependency_analyzer = services["dependency_analyzer"]

    @app.get("/api/dependencies/graph")
    async def get_dependency_graph(
        filter_type: str = None,
        max_nodes: int = 1000,
        include_external: bool = False,
    ) -> None:
        """Get dependency graph data."""
        return await _handle_dependency_graph_request(
            dependency_analyzer, filter_type, max_nodes, include_external
        )

    @app.get("/api/dependencies/metrics")
    async def get_dependency_metrics() -> None:
        """Get dependency graph metrics."""
        return await _handle_dependency_metrics_request(dependency_analyzer)

    @app.get("/api/dependencies/clusters")
    async def get_dependency_clusters() -> None:
        """Get dependency graph clusters."""
        return await _handle_dependency_clusters_request(dependency_analyzer)

    @app.post("/api/dependencies/analyze")
    async def trigger_dependency_analysis(request: dict) -> None:
        """Trigger fresh dependency analysis."""
        return await _handle_dependency_analysis_request(dependency_analyzer, request)


async def _handle_dependency_graph_request(
    dependency_analyzer: DependencyAnalyzer,
    filter_type: str | None,
    max_nodes: int,
    include_external: bool,
) -> JSONResponse:
    """Handle dependency graph API request."""
    try:
        graph = dependency_analyzer.analyze_project()

        # Apply filters if requested
        if filter_type or max_nodes < len(graph.nodes):
            filters = {
                "type": filter_type,
                "max_nodes": max_nodes,
                "include_external": include_external,
            }
            graph = await _apply_graph_filters(graph, filters)

        return JSONResponse(
            {
                "status": "success",
                "data": graph.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_dependency_metrics_request(
    dependency_analyzer: DependencyAnalyzer,
) -> JSONResponse:
    """Handle dependency metrics API request."""
    try:
        graph = dependency_analyzer.analyze_project()

        return JSONResponse(
            {
                "status": "success",
                "data": graph.metrics,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_dependency_clusters_request(
    dependency_analyzer: DependencyAnalyzer,
) -> JSONResponse:
    """Handle dependency clusters API request."""
    try:
        graph = dependency_analyzer.analyze_project()

        return JSONResponse(
            {
                "status": "success",
                "data": graph.clusters,
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_dependency_analysis_request(
    dependency_analyzer: DependencyAnalyzer, request: dict
) -> JSONResponse:
    """Handle dependency analysis trigger API request."""
    try:
        # Reset analyzer for fresh analysis
        dependency_analyzer.dependency_graph = DependencyGraph()
        graph = dependency_analyzer.analyze_project()

        return JSONResponse(
            {
                "status": "success",
                "message": "Dependency analysis completed",
                "data": {
                    "nodes": len(graph.nodes),
                    "edges": len(graph.edges),
                    "clusters": len(graph.clusters),
                    "metrics": graph.metrics,
                },
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _register_heatmap_websockets(
    app: FastAPI,
    ws_manager: MonitoringWebSocketManager,
    services: dict[str, t.Any],
) -> None:
    """Register heatmap-related WebSocket endpoints."""
    error_analyzer = services["error_analyzer"]

    @app.websocket("/ws/heatmap/errors")
    async def websocket_error_heatmap(websocket: WebSocket) -> None:
        """WebSocket endpoint for real-time error heat map streaming."""
        await _handle_error_heatmap_websocket(websocket, error_analyzer)


async def _handle_error_heatmap_websocket(
    websocket: WebSocket, error_analyzer: ErrorPatternAnalyzer
) -> None:
    """Handle error heatmap WebSocket connection."""
    await websocket.accept()

    try:
        # Analyze error patterns and send initial data
        error_patterns = error_analyzer.analyze_error_patterns(days=30)
        await _send_initial_heatmap_data(websocket, error_analyzer, error_patterns)

        # Handle client messages
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                data = json.loads(message)

                await _handle_heatmap_request(websocket, error_analyzer, data)

            except TimeoutError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "heartbeat",
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
                )

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )


async def _send_initial_heatmap_data(
    websocket: WebSocket,
    error_analyzer: ErrorPatternAnalyzer,
    error_patterns: list[t.Any],
) -> None:
    """Send initial heatmap data to client."""
    # Send file-based heat map
    file_heatmap = error_analyzer.generate_file_error_heatmap()
    await websocket.send_text(
        json.dumps(
            {
                "type": "file_heatmap",
                "data": file_heatmap.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    )

    # Send temporal heat map
    temporal_heatmap = error_analyzer.generate_temporal_heatmap()
    await websocket.send_text(
        json.dumps(
            {
                "type": "temporal_heatmap",
                "data": temporal_heatmap.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    )

    # Send function-based heat map
    function_heatmap = error_analyzer.generate_function_error_heatmap()
    await websocket.send_text(
        json.dumps(
            {
                "type": "function_heatmap",
                "data": function_heatmap.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    )

    # Send error patterns summary
    patterns_data = [pattern.to_dict() for pattern in error_patterns]
    await websocket.send_text(
        json.dumps(
            {
                "type": "error_patterns",
                "data": patterns_data,
                "timestamp": datetime.now().isoformat(),
            }
        )
    )


async def _handle_heatmap_request(
    websocket: WebSocket,
    error_analyzer: ErrorPatternAnalyzer,
    data: dict[str, t.Any],
) -> None:
    """Handle heatmap request from client."""
    if data.get("type") == "refresh_heatmap":
        await _handle_heatmap_refresh(websocket, error_analyzer, data)
    elif data.get("type") == "keepalive":
        await websocket.send_text(
            json.dumps(
                {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        )


async def _handle_heatmap_refresh(
    websocket: WebSocket,
    error_analyzer: ErrorPatternAnalyzer,
    data: dict[str, t.Any],
) -> None:
    """Handle heatmap refresh request."""
    error_analyzer.analyze_error_patterns(days=data.get("days", 30))

    heatmap_type = data.get("heatmap_type", "file")

    if heatmap_type == "file":
        heatmap = error_analyzer.generate_file_error_heatmap()
    elif heatmap_type == "temporal":
        heatmap = error_analyzer.generate_temporal_heatmap(
            time_buckets=data.get("time_buckets", 24)
        )
    elif heatmap_type == "function":
        heatmap = error_analyzer.generate_function_error_heatmap()
    else:
        return

    await websocket.send_text(
        json.dumps(
            {
                "type": f"{heatmap_type}_heatmap_refresh",
                "data": heatmap.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    )


def _register_heatmap_api_endpoints(app: FastAPI, services: dict[str, t.Any]) -> None:
    """Register heatmap-related REST API endpoints."""
    error_analyzer = services["error_analyzer"]
    cache = services["cache"]

    @app.get("/api/heatmap/file_errors")
    async def get_file_error_heatmap() -> None:
        """Get error heat map by file."""
        return await _handle_file_error_heatmap_request(error_analyzer)

    @app.get("/api/heatmap/temporal_errors")
    async def get_temporal_error_heatmap(time_buckets: int = 24) -> None:
        """Get error heat map over time."""
        return await _handle_temporal_error_heatmap_request(
            error_analyzer, time_buckets
        )

    @app.get("/api/heatmap/function_errors")
    async def get_function_error_heatmap() -> None:
        """Get error heat map by function."""
        return await _handle_function_error_heatmap_request(error_analyzer)

    @app.get("/api/error_patterns")
    async def get_error_patterns(
        days: int = 30, min_occurrences: int = 2, severity: str | None = None
    ) -> None:
        """Get analyzed error patterns."""
        return await _handle_error_patterns_request(
            error_analyzer, days, min_occurrences, severity
        )

    @app.post("/api/trigger_error_analysis")
    async def trigger_error_analysis(request: dict) -> None:
        """Trigger fresh error pattern analysis."""
        return await _handle_trigger_error_analysis_request(
            error_analyzer, cache, request
        )


async def _handle_file_error_heatmap_request(
    error_analyzer: ErrorPatternAnalyzer,
) -> JSONResponse:
    """Handle file error heatmap API request."""
    try:
        error_analyzer.analyze_error_patterns(days=30)
        heatmap = error_analyzer.generate_file_error_heatmap()
        return JSONResponse(heatmap.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_temporal_error_heatmap_request(
    error_analyzer: ErrorPatternAnalyzer, time_buckets: int
) -> JSONResponse:
    """Handle temporal error heatmap API request."""
    try:
        error_analyzer.analyze_error_patterns(days=30)
        heatmap = error_analyzer.generate_temporal_heatmap(time_buckets=time_buckets)
        return JSONResponse(heatmap.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_function_error_heatmap_request(
    error_analyzer: ErrorPatternAnalyzer,
) -> JSONResponse:
    """Handle function error heatmap API request."""
    try:
        error_analyzer.analyze_error_patterns(days=30)
        heatmap = error_analyzer.generate_function_error_heatmap()
        return JSONResponse(heatmap.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_error_patterns_request(
    error_analyzer: ErrorPatternAnalyzer,
    days: int,
    min_occurrences: int,
    severity: str | None,
) -> JSONResponse:
    """Handle error patterns API request."""
    try:
        patterns = error_analyzer.analyze_error_patterns(
            days=days, min_occurrences=min_occurrences
        )

        # Filter by severity if specified
        if severity:
            patterns = [p for p in patterns if p.severity == severity]

        return JSONResponse(
            {
                "patterns": [pattern.to_dict() for pattern in patterns],
                "total_count": len(patterns),
                "analysis_period_days": days,
                "generated_at": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _handle_trigger_error_analysis_request(
    error_analyzer: ErrorPatternAnalyzer, cache: CrackerjackCache, request: dict
) -> JSONResponse:
    """Handle trigger error analysis API request."""
    try:
        days = request.get("days", 30)
        min_occurrences = request.get("min_occurrences", 2)

        # Perform fresh analysis
        patterns = error_analyzer.analyze_error_patterns(
            days=days, min_occurrences=min_occurrences
        )

        # Store results in cache
        cache_key = f"error_patterns_{days}d"
        cache.set(cache_key, [p.to_dict() for p in patterns], ttl_seconds=1800)

        severity_breakdown = {
            severity: len([p for p in patterns if p.severity == severity])
            for severity in ("low", "medium", "high", "critical")
        }

        return JSONResponse(
            {
                "status": "success",
                "message": "Error pattern analysis completed",
                "patterns_found": len(patterns),
                "analysis_period_days": days,
                "severity_breakdown": severity_breakdown,
                "generated_at": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _register_dashboard_endpoint(app: FastAPI) -> None:
    """Register the dashboard HTML endpoint."""

    @app.get("/dashboard")
    async def get_dashboard_html() -> None:
        """Serve the monitoring dashboard HTML."""
        return HTMLResponse(_get_dashboard_html())


async def get_current_metrics(
    quality_service: EnhancedQualityBaselineService, job_manager: JobManager
) -> UnifiedMetrics:
    """Get current unified metrics."""
    try:
        # Get baseline from quality service
        baseline = await quality_service.aget_baseline()
        if not baseline:
            # Return default metrics if no baseline exists
            return UnifiedMetrics(
                timestamp=datetime.now(),
                quality_score=0,
                test_coverage=0.0,
                hook_duration=0.0,
                active_jobs=len(job_manager.active_connections),
                error_count=0,
                trend_direction=TrendDirection.STABLE,
                predictions={},
            )

        # Create metrics dict from baseline
        current_metrics = {
            "coverage_percent": baseline.coverage_percent,
            "test_count": baseline.test_count,
            "test_pass_rate": baseline.test_pass_rate,
            "hook_failures": baseline.hook_failures,
            "complexity_violations": baseline.complexity_violations,
            "security_issues": baseline.security_issues,
            "type_errors": baseline.type_errors,
            "linting_issues": baseline.linting_issues,
            "hook_duration": 0.0,  # Would need to be tracked separately
        }

        unified = await asyncio.to_thread(
            quality_service.create_unified_metrics,
            current_metrics,
            len(job_manager.active_connections),
        )
        return unified
    except Exception:
        # Fallback to basic metrics if service fails
        return UnifiedMetrics(
            timestamp=datetime.now(),
            quality_score=0,
            test_coverage=0.0,
            hook_duration=0.0,
            active_jobs=len(job_manager.active_connections),
            error_count=0,
            trend_direction=TrendDirection.STABLE,
            predictions={},
        )


async def get_system_health_status(
    quality_service: EnhancedQualityBaselineService,
) -> SystemHealthStatus:
    """Get system health status."""
    return await asyncio.to_thread(quality_service.get_system_health)


async def _apply_graph_filters(
    graph: DependencyGraph, filters: dict[str, t.Any]
) -> DependencyGraph:
    """Apply filters to dependency graph."""
    filtered_graph = DependencyGraph(
        generated_at=graph.generated_at,
        metrics=graph.metrics.copy(),
        clusters=graph.clusters.copy(),
    )

    # Filter nodes by type
    filter_type = filters.get("type")
    max_nodes = filters.get("max_nodes", 1000)
    include_external = filters.get("include_external", False)

    # Start with all nodes
    candidate_nodes = list(graph.nodes.values())

    # Filter by type if specified
    if filter_type:
        candidate_nodes = [node for node in candidate_nodes if node.type == filter_type]

    # Filter external dependencies if not included
    if not include_external:
        project_nodes = [
            node
            for node in candidate_nodes
            if not node.file_path or "site-packages" not in node.file_path
        ]
        candidate_nodes = project_nodes

    # Limit number of nodes
    if len(candidate_nodes) > max_nodes:
        # Prioritize by complexity and connectivity
        def node_priority(node: t.Any) -> int:
            # Count edges involving this node
            edge_count = sum(
                1 for edge in graph.edges if node.id in (edge.source, edge.target)
            )
            return int(node.complexity * edge_count)

        candidate_nodes.sort(key=node_priority, reverse=True)
        candidate_nodes = candidate_nodes[:max_nodes]

    # Add filtered nodes to graph
    node_ids = {node.id for node in candidate_nodes}
    for node in candidate_nodes:
        filtered_graph.nodes[node.id] = node

    # Add edges between filtered nodes
    for edge in graph.edges:
        if edge.source in node_ids and edge.target in node_ids:
            filtered_graph.edges.append(edge)

    # Update clusters to only include filtered nodes
    filtered_clusters = {}
    for cluster_name, cluster_nodes in graph.clusters.items():
        filtered_cluster_nodes = [
            node_id for node_id in cluster_nodes if node_id in node_ids
        ]
        if filtered_cluster_nodes:
            filtered_clusters[cluster_name] = filtered_cluster_nodes

    filtered_graph.clusters = filtered_clusters

    return filtered_graph


def _get_dashboard_html() -> str:
    """Generate the monitoring dashboard HTML."""
    return render_monitoring_dashboard()

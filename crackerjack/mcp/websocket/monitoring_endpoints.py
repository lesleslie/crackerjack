"""Enhanced WebSocket endpoints for unified monitoring dashboard."""

import asyncio
import json
import typing as t
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.dependency_analyzer import (
    DependencyAnalyzer,
    DependencyGraph,
)
from crackerjack.services.error_pattern_analyzer import (
    ErrorPatternAnalyzer,
)
from crackerjack.services.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,
    QualityAlert,
    SystemHealthStatus,
    TrendDirection,
    UnifiedMetrics,
)
from crackerjack.services.quality_intelligence import (
    QualityIntelligenceService,
)

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

    return {
        "cache": cache,
        "quality_service": quality_service,
        "intelligence_service": intelligence_service,
        "dependency_analyzer": dependency_analyzer,
        "error_analyzer": error_analyzer,
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
        historical_data = _convert_baselines_to_metrics(
            quality_service.get_recent_baselines(limit=days)
        )

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
        while True:
            current_metrics = await get_current_metrics(quality_service, job_manager)

            metrics_dict = _create_dashboard_metrics_dict(current_metrics)

            dashboard_state = quality_service.create_dashboard_state(
                current_metrics=metrics_dict,
                active_job_count=len(job_manager.active_connections),
                historical_days=7,
            )

            await websocket.send_text(
                json.dumps(
                    {
                        "type": "dashboard_update",
                        "data": dashboard_state.to_dict(),
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


async def _handle_quality_trends_request(
    quality_service: EnhancedQualityBaselineService, days: int
) -> JSONResponse:
    """Handle quality trends API request."""
    try:
        if days > 365:
            raise HTTPException(status_code=400, detail="Days parameter too large")

        trends = quality_service.analyze_quality_trend(days=days)
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

        historical_baselines = quality_service.get_recent_baselines(limit=days)

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
        baseline = quality_service.get_baseline()
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

        return quality_service.create_unified_metrics(
            current_metrics, active_job_count=len(job_manager.active_connections)
        )
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
    return quality_service.get_system_health()


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
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Crackerjack Monitoring Dashboard</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://unpkg.com/react@18/umd/react.development.js"></script>
    <script src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
                         'Roboto', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .dashboard-container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        .metric-card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: inline-block;
            min-width: 200px;
        }}
        .metric-value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        .metric-label {{
            color: #666;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .trend-indicator {{
            font-size: 0.8em;
            padding: 2px 8px;
            border-radius: 12px;
            margin-left: 10px;
        }}
        .trend-improving {{ background-color: #d4edda; color: #155724; }}
        .trend-declining {{ background-color: #f8d7da; color: #721c24; }}
        .trend-stable {{ background-color: #d1ecf1; color: #0c5460; }}
        .chart-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        .status-healthy {{ background-color: #28a745; }}
        .status-warning {{ background-color: #ffc107; }}
        .status-error {{ background-color: #dc3545; }}
        #connection-status {{
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 15px;
            border-radius: 5px;
            color: white;
            font-weight: bold;
        }}
        .connected {{ background-color: #28a745; }}
        .disconnected {{ background-color: #dc3545; }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <div id="connection-status" class="disconnected">Connecting...</div>

        <h1>🚀 Crackerjack Monitoring Dashboard</h1>

        <div id="metrics-cards"></div>

        <div class="chart-container">
            <h3>Quality Score Trend (7 Days)</h3>
            <div id="quality-chart"></div>
        </div>

        <div class="chart-container">
            <h3>Test Coverage & Performance</h3>
            <div id="coverage-chart"></div>
        </div>

        <div class="chart-container">
            <h3>System Health</h3>
            <div id="health-chart"></div>
        </div>

        <div class="chart-container">
            <h3>Active Alerts</h3>
            <div id="alerts-panel"></div>
        </div>

        <div class="chart-container">
            <h3>🧠 ML Anomaly Detection</h3>
            <div id="anomalies-panel"></div>
        </div>

        <div class="chart-container">
            <h3>🔮 Quality Predictions</h3>
            <div id="predictions-panel"></div>
        </div>

        <div class="chart-container">
            <h3>📊 Pattern Analysis</h3>
            <div id="patterns-panel"></div>
        </div>

        <div class="chart-container">
            <h3>🕸️ Code Dependencies Network</h3>
            <div style="margin-bottom: 10px;">
                <button id="load-dependency-graph" onclick="loadDependencyGraph()">
                    Load Dependency Graph
                </button>
                <button id="refresh-graph" onclick="refreshDependencyGraph()" disabled>
                    Refresh
                </button>
                <select id="graph-filter" onchange="applyGraphFilter()" disabled>
                    <option value="">All Types</option>
                    <option value="module">Modules Only</option>
                    <option value="class">Classes Only</option>
                    <option value="function">Functions Only</option>
                </select>
                <label>
                    <input type="checkbox" id="include-external"
                           onchange="applyGraphFilter()" disabled>
                    Include External Dependencies
                </label>
            </div>
            <div id="dependency-graph"
                 style="width: 100%; height: 600px; border: 1px solid #ddd;">
            </div>
        </div>
    </div>

    <!-- Error Pattern Heat Map Section -->
    <div class="section">
        <h2>Error Pattern Heat Maps</h2>
        <div class="controls">
            <label>Heat Map Type:</label>
            <select id="heatmap-type" onchange="updateHeatMap()">
                <option value="file">By File</option>
                <option value="temporal">Over Time</option>
                <option value="function">By Function</option>
            </select>
            <button id="load-heatmap" onclick="loadErrorHeatMap()">
                Load Heat Map
            </button>
            <label>
                <input type="number" id="analysis-days" value="30" min="1" max="365"
                       onchange="updateHeatMap()">
                Analysis Days
            </label>
            <label>
                <input type="number" id="time-buckets" value="24" min="6" max="48"
                       onchange="updateTemporalHeatMap()" disabled>
                Time Buckets
            </label>
        </div>
        <div class="tab-container">
            <div class="tab-buttons">
                <button class="tab-button active" onclick="showHeatMapTab('heatmap')">
                    Heat Map
                </button>
                <button class="tab-button" onclick="showHeatMapTab('patterns')">
                    Error Patterns
                </button>
                <button class="tab-button" onclick="showHeatMapTab('severity')">
                    Severity Analysis
                </button>
            </div>
            <div id="heatmap-tab" class="tab-content active">
                <div id="error-heatmap" style="width: 100%; height: 600px; border: 1px solid #ddd; overflow: auto;"></div>
            </div>
            <div id="patterns-tab" class="tab-content">
                <div id="error-patterns-list" style="max-height: 600px; overflow-y: auto;"></div>
            </div>
            <div id="severity-tab" class="tab-content">
                <div id="severity-breakdown" style="max-height: 600px; overflow-y: auto;"></div>
            </div>
        </div>
    </div>

    <script>
        // WebSocket connection management
        let ws = null;
        let reconnectInterval = 5000;
        let isConnected = false;

        // Dashboard state
        let currentMetrics = {{}};
        let historicalData = [];
        let activeAlerts = [];
        let anomalies = [];
        let predictions = {{}};
        let patterns = {{}};
        let dependencyGraph = null;
        let dependencyWs = null;

        // Intelligence WebSocket connections
        let anomaliesWs = null;
        let predictionsWs = null;
        let patternsWs = null;

        // Heat map state
        let heatMapWs = null;
        let currentHeatMapData = null;
        let errorPatterns = [];
        let severityBreakdown = {{}};

        function connect() {{
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${{protocol}}//${{window.location.host}}/ws/dashboard/overview`;

            ws = new WebSocket(wsUrl);

            // Connect intelligence WebSockets
            connectIntelligenceStreams();

            ws.onopen = function() {{
                isConnected = true;
                updateConnectionStatus();
                console.log('Connected to monitoring dashboard');
            }};

            ws.onmessage = function(event) {{
                const message = JSON.parse(event.data);
                handleMessage(message);
            }};

            ws.onclose = function() {{
                isConnected = false;
                updateConnectionStatus();
                console.log('Disconnected from monitoring dashboard');
                setTimeout(connect, reconnectInterval);
            }};

            ws.onerror = function(error) {{
                console.error('WebSocket error:', error);
            }};
        }}

        function handleMessage(message) {{
            switch(message.type) {{
                case 'dashboard_update':
                    updateDashboard(message.data);
                    break;
                case 'metrics_update':
                    updateMetrics(message.data);
                    break;
                case 'alert':
                    handleAlert(message.data);
                    break;
            }}
        }}

        function updateConnectionStatus() {{
            const statusEl = document.getElementById('connection-status');
            if (isConnected) {{
                statusEl.textContent = 'Connected';
                statusEl.className = 'connected';
            }} else {{
                statusEl.textContent = 'Disconnected';
                statusEl.className = 'disconnected';
            }}
        }}

        function updateDashboard(data) {{
            currentMetrics = data.current_metrics;
            historicalData = data.historical_data || [];
            activeAlerts = data.active_alerts || [];

            renderMetricsCards();
            renderQualityChart();
            renderCoverageChart();
            renderHealthChart();
            renderAlertsPanel();
            renderAnomaliesPanel();
            renderPredictionsPanel();
            renderPatternsPanel();
        }}

        function updateMetrics(data) {{
            currentMetrics = data;
            renderMetricsCards();
        }}

        function handleAlert(alert) {{
            activeAlerts.unshift(alert);
            renderAlertsPanel();

            // Show browser notification if permissions granted
            if (Notification.permission === 'granted') {{
                new Notification('Crackerjack Alert', {{
                    body: alert.message,
                    icon: '/favicon.ico'
                }});
            }}
        }}

        function renderMetricsCards() {{
            const container = document.getElementById('metrics-cards');
            const metrics = currentMetrics;

            if (!metrics) return;

            const cards = [
                {{
                    label: 'Quality Score',
                    value: metrics.quality_score || 0,
                    trend: metrics.trend_direction || 'stable'
                }},
                {{
                    label: 'Test Coverage',
                    value: `${{(metrics.test_coverage || 0).toFixed(1)}}%`,
                    trend: metrics.test_coverage > 90 ? 'improving' : 'stable'
                }},
                {{
                    label: 'Hook Duration',
                    value: `${{(metrics.hook_duration || 0).toFixed(1)}}s`,
                    trend: metrics.hook_duration < 60 ? 'improving' : 'declining'
                }},
                {{
                    label: 'Active Jobs',
                    value: metrics.active_jobs || 0,
                    trend: 'stable'
                }},
                {{
                    label: 'Error Count',
                    value: metrics.error_count || 0,
                    trend: metrics.error_count === 0 ? 'improving' : 'declining'
                }}
            ];

            container.innerHTML = cards.map(card => `
                <div class="metric-card">
                    <div class="metric-value">${{card.value}}</div>
                    <div class="metric-label">
                        ${{card.label}}
                        <span class="trend-indicator trend-${{card.trend}}">
                            ${{card.trend === 'improving' ? '↗' : card.trend === 'declining' ? '↘' : '→'}}
                        </span>
                    </div>
                </div>
            `).join('');
        }}

        function renderQualityChart() {{
            // D3.js quality score chart implementation
            const data = historicalData.map(d => ({{
                date: new Date(d.timestamp),
                score: d.quality_score
            }}));

            if (data.length === 0) return;

            const container = d3.select('#quality-chart');
            container.selectAll('*').remove();

            const margin = {{top: 20, right: 30, bottom: 40, left: 50}};
            const width = 800 - margin.left - margin.right;
            const height = 300 - margin.top - margin.bottom;

            const svg = container
                .append('svg')
                .attr('width', width + margin.left + margin.right)
                .attr('height', height + margin.top + margin.bottom);

            const g = svg.append('g')
                .attr('transform', `translate(${{margin.left}},${{margin.top}})`);

            const x = d3.scaleTime()
                .domain(d3.extent(data, d => d.date))
                .range([0, width]);

            const y = d3.scaleLinear()
                .domain([0, 100])
                .range([height, 0]);

            const line = d3.line()
                .x(d => x(d.date))
                .y(d => y(d.score))
                .curve(d3.curveMonotoneX);

            g.append('g')
                .attr('transform', `translate(0,${{height}})`)
                .call(d3.axisBottom(x));

            g.append('g')
                .call(d3.axisLeft(y));

            g.append('path')
                .datum(data)
                .attr('fill', 'none')
                .attr('stroke', '#007bff')
                .attr('stroke-width', 2)
                .attr('d', line);

            g.selectAll('.dot')
                .data(data)
                .enter().append('circle')
                .attr('class', 'dot')
                .attr('cx', d => x(d.date))
                .attr('cy', d => y(d.score))
                .attr('r', 3)
                .attr('fill', '#007bff');
        }}

        function renderCoverageChart() {{
            // Similar D3.js implementation for coverage chart
            const container = document.getElementById('coverage-chart');
            container.innerHTML = '<p>Coverage and performance charts will be rendered here</p>';
        }}

        function renderHealthChart() {{
            // System health visualization
            const container = document.getElementById('health-chart');
            container.innerHTML = '<p>System health metrics will be rendered here</p>';
        }}

        function renderAlertsPanel() {{
            const container = document.getElementById('alerts-panel');

            if (activeAlerts.length === 0) {{
                container.innerHTML = '<p style="color: #28a745;">✅ No active alerts</p>';
                return;
            }}

            container.innerHTML = activeAlerts.slice(0, 10).map(alert => `
                <div style="padding: 10px; margin: 5px 0; border-left: 4px solid ${{
                    alert.severity === 'critical' ? '#dc3545' :
                    alert.severity === 'warning' ? '#ffc107' : '#17a2b8'
                }}; background-color: #f8f9fa;">
                    <strong>${{alert.severity.toUpperCase()}}</strong>: ${{alert.message}}
                    <br>
                    <small>${{new Date(alert.timestamp).toLocaleString()}}</small>
                </div>
            `).join('');
        }}

        function connectIntelligenceStreams() {{
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const baseUrl = `${{protocol}}//${{window.location.host}}`;

            // Anomaly detection stream
            anomaliesWs = new WebSocket(`${{baseUrl}}/ws/intelligence/anomalies`);
            anomaliesWs.onmessage = function(event) {{
                const message = JSON.parse(event.data);
                if (message.type.startsWith('anomalies_')) {{
                    anomalies = message.data;
                    renderAnomaliesPanel();
                }}
            }};

            // Predictions stream
            predictionsWs = new WebSocket(`${{baseUrl}}/ws/intelligence/predictions`);
            predictionsWs.onmessage = function(event) {{
                const message = JSON.parse(event.data);
                if (message.type.startsWith('predictions_')) {{
                    if (message.data.insights) {{
                        predictions = message.data.insights;
                    }} else {{
                        predictions = message.data;
                    }}
                    renderPredictionsPanel();
                }}
            }};

            // Patterns stream
            patternsWs = new WebSocket(`${{baseUrl}}/ws/intelligence/patterns`);
            patternsWs.onmessage = function(event) {{
                const message = JSON.parse(event.data);
                if (message.type.startsWith('patterns_')) {{
                    patterns = message.data;
                    renderPatternsPanel();
                }}
            }};

            // Heat map stream
            heatMapWs = new WebSocket(`${{baseUrl}}/ws/heatmap/errors`);
            heatMapWs.onmessage = function(event) {{
                const message = JSON.parse(event.data);

                if (message.type.includes('heatmap')) {{
                    currentHeatMapData = message.data;
                    renderHeatMap(currentHeatMapData, message.type);
                }} else if (message.type === 'error_patterns') {{
                    errorPatterns = message.data;
                    renderErrorPatterns();
                    calculateSeverityBreakdown();
                }}
            }};
        }}

        function renderAnomaliesPanel() {{
            const container = document.getElementById('anomalies-panel');

            if (!anomalies || anomalies.length === 0) {{
                container.innerHTML = '<p style="color: #28a745;">✅ No anomalies detected</p>';
                return;
            }}

            container.innerHTML = anomalies.slice(0, 5).map(anomaly => `
                <div style="padding: 10px; margin: 5px 0; border-left: 4px solid ${{
                    anomaly.severity === 'critical' ? '#dc3545' :
                    anomaly.severity === 'warning' ? '#ffc107' : '#17a2b8'
                }}; background-color: #f8f9fa;">
                    <strong>🚨 ${{anomaly.metric}}</strong>: ${{anomaly.description}}
                    <br>
                    <small>Z-score: ${{anomaly.z_score.toFixed(2)}} | ${{new Date(anomaly.timestamp).toLocaleString()}}</small>
                </div>
            `).join('');
        }}

        function renderPredictionsPanel() {{
            const container = document.getElementById('predictions-panel');

            if (!predictions || Object.keys(predictions).length === 0) {{
                container.innerHTML = '<p>Loading predictions...</p>';
                return;
            }}

            let content = '';

            if (predictions.summary) {{
                content += `<div style="padding: 10px; background-color: #e7f3ff; border-radius: 5px; margin-bottom: 10px;">
                    <strong>📈 Summary:</strong> ${{predictions.summary}}
                </div>`;
            }}

            if (predictions.recommendations && predictions.recommendations.length > 0) {{
                content += '<h4>🎯 Recommendations:</h4><ul>';
                predictions.recommendations.slice(0, 3).forEach(rec => {{
                    content += `<li>${{rec}}</li>`;
                }});
                content += '</ul>';
            }}

            if (predictions.risk_factors && predictions.risk_factors.length > 0) {{
                content += '<h4>⚠️ Risk Factors:</h4><ul>';
                predictions.risk_factors.slice(0, 3).forEach(risk => {{
                    content += `<li style="color: #dc3545;">${{risk}}</li>`;
                }});
                content += '</ul>';
            }}

            container.innerHTML = content || '<p>No prediction data available</p>';
        }}

        function renderPatternsPanel() {{
            const container = document.getElementById('patterns-panel');

            if (!patterns || Object.keys(patterns).length === 0) {{
                container.innerHTML = '<p>Loading pattern analysis...</p>';
                return;
            }}

            let content = '';

            if (patterns.correlations && patterns.correlations.length > 0) {{
                content += '<h4>🔗 Strong Correlations:</h4><ul>';
                patterns.correlations.slice(0, 3).forEach(corr => {{
                    const strength = Math.abs(corr.correlation) > 0.7 ? 'Strong' : 'Moderate';
                    const direction = corr.correlation > 0 ? 'Positive' : 'Negative';
                    content += `<li>${{corr.metric1}} ↔ ${{corr.metric2}}: ${{strength}} ${{direction}} (${{corr.correlation.toFixed(3)}})</li>`;
                }});
                content += '</ul>';
            }}

            if (patterns.trends && patterns.trends.length > 0) {{
                content += '<h4>📊 Trending Patterns:</h4><ul>';
                patterns.trends.slice(0, 3).forEach(trend => {{
                    content += `<li>${{trend}}</li>`;
                }});
                content += '</ul>';
            }}

            container.innerHTML = content || '<p>No significant patterns detected</p>';
        }}

        // Dependency Graph Functions
        function loadDependencyGraph() {{
            const button = document.getElementById('load-dependency-graph');
            button.textContent = 'Loading...';
            button.disabled = true;

            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${{protocol}}//${{window.location.host}}/ws/dependencies/graph`;

            dependencyWs = new WebSocket(wsUrl);

            dependencyWs.onopen = function() {{
                console.log('Connected to dependency analysis');
            }};

            dependencyWs.onmessage = function(event) {{
                const message = JSON.parse(event.data);

                switch(message.type) {{
                    case 'analysis_started':
                        updateGraphStatus(message.message);
                        break;
                    case 'graph_data':
                    case 'filtered_graph':
                        dependencyGraph = message.data;
                        renderDependencyGraph(dependencyGraph);
                        enableGraphControls();
                        updateGraphStatus(`Graph loaded: ${{dependencyGraph.nodes.length}} nodes, ${{dependencyGraph.edges.length}} edges`);
                        break;
                    case 'keepalive':
                        // Connection alive
                        break;
                }}
            }};

            dependencyWs.onclose = function() {{
                console.log('Dependency analysis connection closed');
                button.textContent = 'Load Dependency Graph';
                button.disabled = false;
            }};

            dependencyWs.onerror = function(error) {{
                console.error('Dependency WebSocket error:', error);
                updateGraphStatus('Error loading dependency graph');
                button.textContent = 'Load Dependency Graph';
                button.disabled = false;
            }};
        }}

        function refreshDependencyGraph() {{
            if (dependencyWs && dependencyWs.readyState === WebSocket.OPEN) {{
                dependencyWs.send(JSON.stringify({{ type: 'refresh_request' }}));
                updateGraphStatus('Refreshing dependency analysis...');
            }}
        }}

        function applyGraphFilter() {{
            if (!dependencyWs || dependencyWs.readyState !== WebSocket.OPEN) return;

            const filterType = document.getElementById('graph-filter').value;
            const includeExternal = document.getElementById('include-external').checked;

            const filters = {{
                type: filterType || null,
                include_external: includeExternal,
                max_nodes: 500  // Limit for performance
            }};

            dependencyWs.send(JSON.stringify({{
                type: 'filter_request',
                filters: filters
            }}));

            updateGraphStatus('Applying filters...');
        }}

        function enableGraphControls() {{
            document.getElementById('refresh-graph').disabled = false;
            document.getElementById('graph-filter').disabled = false;
            document.getElementById('include-external').disabled = false;
        }}

        function updateGraphStatus(message) {{
            const container = document.getElementById('dependency-graph');
            if (!dependencyGraph) {{
                container.innerHTML = `<p style="padding: 20px; text-align: center;">${{message}}</p>`;
            }}
        }}

        function renderDependencyGraph(graphData) {{
            const container = d3.select('#dependency-graph');
            container.selectAll('*').remove();

            if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {{
                container.append('p')
                    .style('padding', '20px')
                    .style('text-align', 'center')
                    .text('No dependency data available');
                return;
            }}

            const width = 800;
            const height = 600;

            const svg = container
                .append('svg')
                .attr('width', width)
                .attr('height', height);

            // Create color scale for node types
            const colorScale = d3.scaleOrdinal()
                .domain(['module', 'class', 'function', 'method'])
                .range(['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']);

            // Create force simulation
            const simulation = d3.forceSimulation(graphData.nodes)
                .force('link', d3.forceLink(graphData.edges)
                    .id(d => d.id)
                    .distance(d => 50 + d.weight * 20))
                .force('charge', d3.forceManyBody()
                    .strength(d => -100 - d.size * 10))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide(d => Math.max(5, d.size * 2)));

            // Add zoom behavior
            const zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .on('zoom', function(event) {{
                    g.attr('transform', event.transform);
                }});

            svg.call(zoom);

            const g = svg.append('g');

            // Add links
            const link = g.append('g')
                .selectAll('line')
                .data(graphData.edges)
                .join('line')
                .attr('stroke', d => {{
                    switch(d.type) {{
                        case 'import': return '#999';
                        case 'inheritance': return '#ff7f0e';
                        case 'call': return '#2ca02c';
                        default: return '#ccc';
                    }}
                }})
                .attr('stroke-width', d => Math.max(1, d.weight * 2))
                .attr('stroke-opacity', 0.6);

            // Add nodes
            const node = g.append('g')
                .selectAll('circle')
                .data(graphData.nodes)
                .join('circle')
                .attr('r', d => Math.max(3, Math.min(20, d.size + d.complexity)))
                .attr('fill', d => colorScale(d.type))
                .attr('stroke', '#fff')
                .attr('stroke-width', 1.5)
                .call(d3.drag()
                    .on('start', function(event, d) {{
                        if (!event.active) simulation.alphaTarget(0.3).restart();
                        d.fx = d.x;
                        d.fy = d.y;
                    }})
                    .on('drag', function(event, d) {{
                        d.fx = event.x;
                        d.fy = event.y;
                    }})
                    .on('end', function(event, d) {{
                        if (!event.active) simulation.alphaTarget(0);
                        d.fx = null;
                        d.fy = null;
                    }}));

            // Add labels for important nodes
            const label = g.append('g')
                .selectAll('text')
                .data(graphData.nodes.filter(d => d.size > 5 || d.complexity > 10))
                .join('text')
                .text(d => d.name.split('.').pop()) // Show just the last part of the name
                .attr('font-size', '10px')
                .attr('font-family', 'Arial, sans-serif')
                .attr('fill', '#333')
                .attr('text-anchor', 'middle')
                .attr('dy', '0.3em');

            // Add tooltips
            node.append('title')
                .text(d => `${{d.name}}\\nType: ${{d.type}}\\nComplexity: ${{d.complexity}}\\nFile: ${{d.file_path}}`);

            link.append('title')
                .text(d => `${{d.source.id}} → ${{d.target.id}}\\nType: ${{d.type}}\\nWeight: ${{d.weight}}`);

            // Update positions on simulation tick
            simulation.on('tick', function() {{
                link
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);

                node
                    .attr('cx', d => d.x)
                    .attr('cy', d => d.y);

                label
                    .attr('x', d => d.x)
                    .attr('y', d => d.y);
            }});

            // Add legend
            const legend = svg.append('g')
                .attr('transform', 'translate(20, 20)');

            const legendData = [
                {{ type: 'module', color: colorScale('module') }},
                {{ type: 'class', color: colorScale('class') }},
                {{ type: 'function', color: colorScale('function') }},
                {{ type: 'method', color: colorScale('method') }}
            ];

            legend.selectAll('g')
                .data(legendData)
                .join('g')
                .attr('transform', (d, i) => `translate(0, ${{i * 20}})`)
                .each(function(d) {{
                    const g = d3.select(this);
                    g.append('circle')
                        .attr('r', 6)
                        .attr('fill', d.color);
                    g.append('text')
                        .attr('x', 15)
                        .attr('y', 0)
                        .attr('dy', '0.3em')
                        .attr('font-size', '12px')
                        .attr('fill', '#333')
                        .text(d.type);
                }});
        }}

        // Heat map functions
        function loadErrorHeatMap() {{
            const button = document.getElementById('load-heatmap');
            button.textContent = 'Loading...';
            button.disabled = true;

            // WebSocket will handle the data loading
            setTimeout(() => {{
                button.textContent = 'Load Heat Map';
                button.disabled = false;
            }}, 2000);
        }}

        function updateHeatMap() {{
            if (!heatMapWs || heatMapWs.readyState !== WebSocket.OPEN) return;

            const heatmapType = document.getElementById('heatmap-type').value;
            const days = parseInt(document.getElementById('analysis-days').value);
            const timeBuckets = document.getElementById('time-buckets').value;

            // Enable/disable time buckets input based on type
            document.getElementById('time-buckets').disabled = heatmapType !== 'temporal';

            const message = {{
                type: 'refresh_heatmap',
                heatmap_type: heatmapType,
                days: days,
                time_buckets: heatmapType === 'temporal' ? parseInt(timeBuckets) : 24
            }};

            heatMapWs.send(JSON.stringify(message));
        }}

        function updateTemporalHeatMap() {{
            if (document.getElementById('heatmap-type').value === 'temporal') {{
                updateHeatMap();
            }}
        }}

        function showHeatMapTab(tabName) {{
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(tab => {{
                tab.classList.remove('active');
            }});

            // Show selected tab content
            document.getElementById(tabName + '-tab').classList.add('active');

            // Update tab buttons
            document.querySelectorAll('.tab-button').forEach(button => {{
                button.classList.remove('active');
            }});
            event.target.classList.add('active');
        }}

        function renderHeatMap(heatmapData, type) {{
            if (!heatmapData || !heatmapData.cells || heatmapData.cells.length === 0) {{
                document.getElementById('error-heatmap').innerHTML =
                    '<div style="text-align: center; padding: 20px; color: #28a745;">✅ No error patterns found</div>';
                return;
            }}

            const container = d3.select('#error-heatmap');
            container.selectAll('*').remove();

            const margin = {{ top: 80, right: 100, bottom: 100, left: 200 }};
            const width = 1000 - margin.left - margin.right;
            const height = 600 - margin.bottom - margin.top;

            // Create SVG
            const svg = container.append('svg')
                .attr('width', width + margin.left + margin.right)
                .attr('height', height + margin.bottom + margin.top);

            const g = svg.append('g')
                .attr('transform', `translate(${{margin.left}},${{margin.top}})`);

            // Create scales
            const xScale = d3.scaleBand()
                .domain(heatmapData.x_labels)
                .range([0, width])
                .padding(0.1);

            const yScale = d3.scaleBand()
                .domain(heatmapData.y_labels)
                .range([height, 0])
                .padding(0.1);

            // Color scale based on severity
            const colorScale = d3.scaleOrdinal()
                .domain(['low', 'medium', 'high', 'critical'])
                .range(['#fffbd4', '#ffeaa7', '#fd79a8', '#e84393']);

            // Intensity scale for opacity
            const intensityScale = d3.scaleLinear()
                .domain([0, 1])
                .range([0.3, 1]);

            // Create heat map cells
            const cells = g.selectAll('.heatmap-cell')
                .data(heatmapData.cells)
                .join('rect')
                .attr('class', 'heatmap-cell')
                .attr('x', d => xScale(d.x))
                .attr('y', d => yScale(d.y))
                .attr('width', xScale.bandwidth())
                .attr('height', yScale.bandwidth())
                .attr('fill', d => colorScale(d.severity))
                .attr('opacity', d => intensityScale(d.color_intensity))
                .attr('stroke', '#fff')
                .attr('stroke-width', 1);

            // Add tooltips
            cells.append('title')
                .text(d => {{
                    const tooltip = d.tooltip_data;
                    return `${{tooltip.file || tooltip.time || tooltip.function}}
Error: ${{tooltip.error_type}}
Count: ${{tooltip.count}}
Severity: ${{tooltip.severity}}`;
                }});

            // Add value labels for high-intensity cells
            g.selectAll('.cell-label')
                .data(heatmapData.cells.filter(d => d.color_intensity > 0.6))
                .join('text')
                .attr('class', 'cell-label')
                .attr('x', d => xScale(d.x) + xScale.bandwidth() / 2)
                .attr('y', d => yScale(d.y) + yScale.bandwidth() / 2)
                .attr('dy', '0.35em')
                .attr('text-anchor', 'middle')
                .attr('fill', 'white')
                .attr('font-size', '10px')
                .attr('font-weight', 'bold')
                .text(d => d.value);

            // Add axes
            const xAxis = g.append('g')
                .attr('transform', `translate(0, ${{height}})`)
                .call(d3.axisBottom(xScale))
                .selectAll('text')
                .style('text-anchor', 'end')
                .attr('dx', '-.8em')
                .attr('dy', '.15em')
                .attr('transform', 'rotate(-45)');

            const yAxis = g.append('g')
                .call(d3.axisLeft(yScale));

            // Add title
            svg.append('text')
                .attr('x', (width + margin.left + margin.right) / 2)
                .attr('y', margin.top / 2)
                .attr('text-anchor', 'middle')
                .attr('font-size', '16px')
                .attr('font-weight', 'bold')
                .text(heatmapData.title);

            // Add subtitle
            svg.append('text')
                .attr('x', (width + margin.left + margin.right) / 2)
                .attr('y', margin.top * 0.7)
                .attr('text-anchor', 'middle')
                .attr('font-size', '12px')
                .attr('fill', '#666')
                .text(heatmapData.subtitle);

            // Add legend
            const legend = svg.append('g')
                .attr('transform', `translate(${{width + margin.left + 20}}, ${{margin.top}})`);

            const legendData = [
                {{ severity: 'low', color: colorScale('low') }},
                {{ severity: 'medium', color: colorScale('medium') }},
                {{ severity: 'high', color: colorScale('high') }},
                {{ severity: 'critical', color: colorScale('critical') }}
            ];

            legend.selectAll('g')
                .data(legendData)
                .join('g')
                .attr('transform', (d, i) => `translate(0, ${{i * 25}})`)
                .each(function(d) {{
                    const g = d3.select(this);
                    g.append('rect')
                        .attr('width', 15)
                        .attr('height', 15)
                        .attr('fill', d.color);
                    g.append('text')
                        .attr('x', 20)
                        .attr('y', 12)
                        .attr('font-size', '12px')
                        .text(d.severity);
                }});
        }}

        function renderErrorPatterns() {{
            const container = document.getElementById('error-patterns-list');

            if (!errorPatterns || errorPatterns.length === 0) {{
                container.innerHTML = '<p style="color: #28a745;">✅ No error patterns found</p>';
                return;
            }}

            // Sort by severity and count
            const sortedPatterns = [...errorPatterns].sort((a, b) => {{
                const severityOrder = {{ critical: 4, high: 3, medium: 2, low: 1 }};
                if (severityOrder[b.severity] !== severityOrder[a.severity]) {{
                    return severityOrder[b.severity] - severityOrder[a.severity];
                }}
                return b.count - a.count;
            }});

            container.innerHTML = sortedPatterns.map(pattern => {{
                const severityColor = {{
                    critical: '#e84393',
                    high: '#fd79a8',
                    medium: '#ffeaa7',
                    low: '#fffbd4'
                }};

                const trendIcon = {{
                    increasing: '📈',
                    stable: '➡️',
                    decreasing: '📉'
                }};

                return `
                    <div style="
                        padding: 15px;
                        margin: 10px 0;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        border-left: 4px solid ${{severityColor[pattern.severity]}};
                        background-color: ${{pattern.severity === 'critical' ? '#fff5f5' : '#fafafa'}};
                    ">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                            <h4 style="margin: 0; color: #333;">${{pattern.error_type}}</h4>
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <span style="
                                    background: ${{severityColor[pattern.severity]}};
                                    padding: 2px 8px;
                                    border-radius: 12px;
                                    font-size: 12px;
                                    font-weight: bold;
                                    color: ${{pattern.severity === 'low' ? '#333' : '#fff'}};
                                ">${{pattern.severity.toUpperCase()}}</span>
                                <span style="font-size: 14px;">${{trendIcon[pattern.trend]}} ${{pattern.trend}}</span>
                                <span style="font-weight: bold; color: #e74c3c;">×${{pattern.count}}</span>
                            </div>
                        </div>
                        <p style="margin: 5px 0; color: #666; font-family: monospace; background: #f8f9fa; padding: 5px; border-radius: 4px; font-size: 12px;">
                            ${{pattern.message}}
                        </p>
                        <div style="display: flex; justify-content: space-between; font-size: 12px; color: #888; margin-top: 10px;">
                            <span>📁 ${{pattern.file_path}}${{pattern.function_name ? ':' + pattern.function_name : ''}}</span>
                            <span>🕒 Last seen: ${{new Date(pattern.last_seen).toLocaleDateString()}}</span>
                        </div>
                        <div style="margin-top: 8px;">
                            <div style="background: #e9ecef; height: 4px; border-radius: 2px; overflow: hidden;">
                                <div style="
                                    background: ${{severityColor[pattern.severity]}};
                                    height: 100%;
                                    width: ${{Math.min(pattern.confidence * 100, 100)}}%;
                                    transition: width 0.3s ease;
                                "></div>
                            </div>
                            <span style="font-size: 10px; color: #999;">Confidence: ${{Math.round(pattern.confidence * 100)}}%</span>
                        </div>
                    </div>
                `;
            }}).join('');
        }}

        function calculateSeverityBreakdown() {{
            if (!errorPatterns) return;

            severityBreakdown = errorPatterns.reduce((acc, pattern) => {{
                acc[pattern.severity] = (acc[pattern.severity] || 0) + 1;
                return acc;
            }}, {{}});

            renderSeverityBreakdown();
        }}

        function renderSeverityBreakdown() {{
            const container = document.getElementById('severity-breakdown');

            if (!severityBreakdown || Object.keys(severityBreakdown).length === 0) {{
                container.innerHTML = '<p style="color: #28a745;">✅ No severity data available</p>';
                return;
            }}

            const total = Object.values(severityBreakdown).reduce((sum, count) => sum + count, 0);
            const severityColors = {{
                critical: '#e84393',
                high: '#fd79a8',
                medium: '#ffeaa7',
                low: '#fffbd4'
            }};

            const severityOrder = ['critical', 'high', 'medium', 'low'];

            container.innerHTML = `
                <div style="padding: 20px;">
                    <h3 style="margin-bottom: 20px;">Severity Distribution (${{total}} total patterns)</h3>
                    ${{severityOrder.map(severity => {{
                        const count = severityBreakdown[severity] || 0;
                        const percentage = total > 0 ? Math.round((count / total) * 100) : 0;

                        return `
                            <div style="margin-bottom: 15px;">
                                <div style="
                                    display: flex;
                                    justify-content: space-between;
                                    align-items: center;
                                    margin-bottom: 5px;
                                ">
                                    <span style="font-weight: bold; text-transform: capitalize;">
                                        ${{severity}}
                                    </span>
                                    <span>${{count}} (${{percentage}}%)</span>
                                </div>
                                <div style="
                                    background: #e9ecef;
                                    height: 8px;
                                    border-radius: 4px;
                                    overflow: hidden;
                                ">
                                    <div style="
                                        background: ${{severityColors[severity]}};
                                        height: 100%;
                                        width: ${{percentage}}%;
                                        transition: width 0.5s ease;
                                    "></div>
                                </div>
                            </div>
                        `;
                    }}).join('')}}

                    <div style="
                        margin-top: 30px;
                        padding: 15px;
                        background: #f8f9fa;
                        border-radius: 8px;
                    ">
                        <h4 style="margin-top: 0;">Recommendations</h4>
                        <ul style="margin: 0; padding-left: 20px;">
                            ${{severityBreakdown.critical ? (
                                '<li style="color: #e84393;">'
                                + '🚨 <strong>Critical errors require immediate attention</strong>'
                                + '</li>'
                            ) : ''}}
                            ${{severityBreakdown.high ? (
                                '<li style="color: #fd79a8;">'
                                + '⚠️ High severity errors should be prioritized'
                                + '</li>'
                            ) : ''}}
                            ${{severityBreakdown.medium && severityBreakdown.medium > 5 ? (
                                '<li style="color: #f39c12;">'
                                + '📊 Consider batch-fixing medium severity patterns'
                                + '</li>'
                            ) : ''}}
                            ${{severityBreakdown.low && severityBreakdown.low > 10 ? (
                                '<li style="color: #3498db;">'
                                + '🔧 Low severity issues can be automated or batched'
                                + '</li>'
                            ) : ''}}
                        </ul>
                    </div>
                </div>
            `;
        }}

        // Request notification permissions
        if ('Notification' in window && Notification.permission === 'default') {{
            Notification.requestPermission();
        }}

        // Initialize dashboard
        connect();
        updateConnectionStatus();
    </script>
</body>
</html>"""

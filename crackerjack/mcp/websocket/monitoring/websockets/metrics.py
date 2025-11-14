"""WebSocket endpoints for metrics streaming.

This module handles real-time metrics streaming, historical data,
alerts, and dashboard overview WebSocket connections.
"""

import asyncio
import json
import typing as t
from datetime import datetime

from acb.depends import depends
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from crackerjack.events import WorkflowEventTelemetry
from crackerjack.services.quality.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,
    TrendDirection,
    UnifiedMetrics,
)

from ..utils import get_current_metrics
from ..websocket_manager import MonitoringWebSocketManager


def register_metrics_websockets(
    app: FastAPI,
    job_manager: t.Any,
    ws_manager: MonitoringWebSocketManager,
    quality_service: EnhancedQualityBaselineService,
) -> None:
    """Register metrics-related WebSocket endpoints."""

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
    job_manager: t.Any,
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
    job_manager: t.Any,
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

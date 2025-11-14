"""WebSocket endpoints for intelligence features.

This module handles real-time anomaly detection, predictions,
and pattern analysis WebSocket connections.
"""

import asyncio
import json
import typing as t
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from crackerjack.services.quality.quality_intelligence import (
    QualityIntelligenceService,
)

from ..websocket_manager import MonitoringWebSocketManager


def register_intelligence_websockets(
    app: FastAPI,
    ws_manager: MonitoringWebSocketManager,
    intelligence_service: QualityIntelligenceService,
) -> None:
    """Register intelligence-related WebSocket endpoints."""

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

"""WebSocket connection manager for real-time monitoring.

This module manages WebSocket connections for metrics streaming and alert notifications.
"""

import json
from datetime import datetime

from fastapi import WebSocket

from crackerjack.services.quality.quality_baseline_enhanced import (
    QualityAlert,
    UnifiedMetrics,
)


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

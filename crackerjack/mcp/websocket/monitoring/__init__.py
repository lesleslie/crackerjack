"""Monitoring endpoints module.

This module provides WebSocket and REST API endpoints for real-time
monitoring, metrics streaming, intelligence features, and error analysis.
"""

from .factory import create_monitoring_endpoints
from .models import (
    HealthResponseModel,
    TelemetryEventModel,
    TelemetryResponseModel,
    TelemetrySnapshotModel,
    UnifiedMetricsModel,
)
from .websocket_manager import MonitoringWebSocketManager

__all__ = [
    "create_monitoring_endpoints",
    "MonitoringWebSocketManager",
    "TelemetryEventModel",
    "TelemetrySnapshotModel",
    "TelemetryResponseModel",
    "UnifiedMetricsModel",
    "HealthResponseModel",
]

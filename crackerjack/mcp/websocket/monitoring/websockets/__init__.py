"""WebSocket endpoint registration.

This module provides registration functions for all WebSocket endpoints
including metrics, intelligence, dependencies, and heatmap streaming.
"""

from .dependencies import register_dependency_websockets
from .heatmap import register_heatmap_websockets
from .intelligence import register_intelligence_websockets
from .metrics import register_metrics_websockets

__all__ = [
    "register_metrics_websockets",
    "register_intelligence_websockets",
    "register_dependency_websockets",
    "register_heatmap_websockets",
]

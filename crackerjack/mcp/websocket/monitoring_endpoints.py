"""Backward compatibility wrapper for refactored monitoring endpoints.

This module re-exports the main factory function from the new monitoring/ directory
to maintain backward compatibility with existing code that imports from
crackerjack.mcp.websocket.monitoring_endpoints.

The actual implementation has been split into organized modules:
- monitoring/models.py - Pydantic data models
- monitoring/websocket_manager.py - WebSocket connection management
- monitoring/utils.py - Utility functions
- monitoring/dashboard.py - Dashboard HTML rendering
- monitoring/websockets/ - WebSocket endpoint modules (metrics, intelligence, dependencies, heatmap)
- monitoring/api/ - REST API endpoint modules (telemetry, metrics, intelligence, dependencies, heatmap)
- monitoring/factory.py - Endpoint registration orchestration

All imports should work exactly as before via the main factory function.
"""

from .monitoring import MonitoringWebSocketManager, create_monitoring_endpoints

__all__ = ["create_monitoring_endpoints", "MonitoringWebSocketManager"]

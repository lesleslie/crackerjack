"""Factory module for monitoring endpoint registration.

This module orchestrates the initialization of all monitoring services
and registration of WebSocket and REST API endpoints.
"""

import typing as t
from pathlib import Path

from acb.depends import depends
from fastapi import FastAPI

from crackerjack.events import WorkflowEventTelemetry
from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.dependency_analyzer import DependencyAnalyzer
from crackerjack.services.monitoring.error_pattern_analyzer import (
    ErrorPatternAnalyzer,
)
from crackerjack.services.quality.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,
)
from crackerjack.services.quality.quality_intelligence import (
    QualityIntelligenceService,
)

from .api.dependencies import register_dependency_api_endpoints
from .api.heatmap import register_heatmap_api_endpoints
from .api.intelligence import register_intelligence_api_endpoints
from .api.metrics import register_metrics_api_endpoints
from .api.telemetry import register_telemetry_api_endpoints
from .dashboard import get_dashboard_html
from .websocket_manager import MonitoringWebSocketManager
from .websockets.dependencies import register_dependency_websockets
from .websockets.heatmap import register_heatmap_websockets
from .websockets.intelligence import register_intelligence_websockets
from .websockets.metrics import register_metrics_websockets


def create_monitoring_endpoints(
    app: FastAPI,
    job_manager: t.Any,
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
    job_manager: t.Any,
    ws_manager: MonitoringWebSocketManager,
    services: dict[str, t.Any],
) -> None:
    """Register all WebSocket endpoints."""
    register_metrics_websockets(
        app, job_manager, ws_manager, services["quality_service"]
    )
    register_intelligence_websockets(app, ws_manager, services["intelligence_service"])
    register_dependency_websockets(app, ws_manager, services["dependency_analyzer"])
    register_heatmap_websockets(app, services["error_analyzer"])


def _register_rest_api_endpoints(
    app: FastAPI, job_manager: t.Any, services: dict[str, t.Any]
) -> None:
    """Register all REST API endpoints."""
    register_telemetry_api_endpoints(
        app, job_manager, services["telemetry"], services["quality_service"]
    )
    register_metrics_api_endpoints(app, job_manager, services["quality_service"])
    register_intelligence_api_endpoints(app, services["intelligence_service"])
    register_dependency_api_endpoints(app, services["dependency_analyzer"])
    register_heatmap_api_endpoints(app, services["error_analyzer"], services["cache"])


def _register_dashboard_endpoint(app: FastAPI) -> None:
    """Register the dashboard HTML endpoint."""

    @app.get("/dashboard")
    async def dashboard_endpoint() -> None:
        """Serve the monitoring dashboard HTML."""
        return await get_dashboard_html()

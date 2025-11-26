"""REST API endpoints for telemetry and health monitoring.

This module provides HTTP endpoints for workflow event telemetry
and system health metrics.
"""

import typing as t
from datetime import datetime

from fastapi import FastAPI

from crackerjack.events import WorkflowEventTelemetry
from crackerjack.services.quality.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,
    UnifiedMetrics,
)

from ..metrics import get_monitoring_current_metrics
from ..models import (
    HealthResponseModel,
    TelemetryEventModel,
    TelemetryResponseModel,
    TelemetrySnapshotModel,
    UnifiedMetricsModel,
)


def register_telemetry_api_endpoints(
    app: FastAPI,
    job_manager: t.Any,
    telemetry: WorkflowEventTelemetry,
    quality_service: EnhancedQualityBaselineService,
) -> None:
    """Register telemetry and dashboard REST endpoints."""

    @app.get(
        "/monitoring/events",
        response_model=TelemetryResponseModel,
        summary="Get workflow telemetry snapshot",
    )
    async def get_monitoring_events() -> TelemetryResponseModel:
        snapshot = await telemetry.snapshot()
        data = TelemetrySnapshotModel(
            counts=snapshot.get("counts", {}),
            recent_events=[
                TelemetryEventModel.model_validate(event)
                for event in snapshot.get("recent_events", [])
            ],
            last_error=None,  # Adjust based on how last_error is stored in snapshot
        )
        return TelemetryResponseModel(
            status="success",
            data=data,
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
        data = TelemetrySnapshotModel(
            counts=snapshot.get("counts", {}),
            recent_events=[
                TelemetryEventModel.model_validate(event)
                for event in snapshot.get("recent_events", [])
            ],
            last_error=None,  # Adjust based on how last_error is stored in snapshot
        )
        return TelemetryResponseModel(
            status="success",
            data=data,
            timestamp=datetime.now(),
        )

    @app.get(
        "/monitoring/health",
        response_model=HealthResponseModel,
        summary="Retrieve aggregated monitoring health metrics",
    )
    async def get_monitoring_health() -> HealthResponseModel:
        unified_metrics = await get_monitoring_current_metrics(
            quality_service, job_manager
        )  # Use the function parameters
        return HealthResponseModel(
            status=_derive_health_status(unified_metrics),
            data=UnifiedMetricsModel.from_domain(unified_metrics),
            timestamp=datetime.now(),
        )


def _derive_health_status(metrics: UnifiedMetrics) -> str:
    """Derive a coarse health status string from unified metrics."""
    if metrics.error_count > 5 or metrics.quality_score < 40:
        return "critical"
    if metrics.error_count > 0 or metrics.quality_score < 60:
        return "warning"
    return "healthy"

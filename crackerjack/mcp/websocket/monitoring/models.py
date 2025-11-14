"""Pydantic models for monitoring endpoints.

This module contains all data models used for request/response validation
and serialization in the monitoring system.
"""

import typing as t
from datetime import datetime

from pydantic import BaseModel

from crackerjack.services.quality.quality_baseline_enhanced import (
    TrendDirection,
    UnifiedMetrics,
)


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

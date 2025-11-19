from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from crackerjack.mcp.websocket.monitoring.api.telemetry import (
    register_telemetry_api_endpoints,
)
from crackerjack.mcp.websocket.monitoring.models import (
    HealthResponseModel,
    TelemetryResponseModel,
)
from crackerjack.services.quality.quality_baseline_enhanced import (
    TrendDirection,
    UnifiedMetrics,
)


class FakeTelemetry:
    def __init__(self) -> None:
        self._snapshot = {
            "counts": {"workflow.completed": 2},
            "recent_events": [
                {
                    "event_type": "workflow.completed",
                    "timestamp": datetime.now().isoformat(),
                    "source": "tests",
                    "payload": {"workflow_id": "wf-1"},
                }
            ],
            "last_error": None,
        }

    async def snapshot(self) -> dict[str, Any]:
        return self._snapshot

    async def reset(self) -> None:
        self._snapshot = {"counts": {}, "recent_events": [], "last_error": None}


class FakeBaseline:
    coverage_percent = 82.5
    test_count = 120
    test_pass_rate = 0.96
    hook_failures = 1
    complexity_violations = 0
    security_issues = 0
    type_errors = 0
    linting_issues = 3


class FakeQualityService:
    async def aget_baseline(self) -> FakeBaseline:
        return FakeBaseline()

    def create_unified_metrics(
        self,
        current_metrics: dict[str, Any],
        active_connections: int,
    ) -> UnifiedMetrics:
        return UnifiedMetrics(
            timestamp=datetime.now(),
            quality_score=85,
            test_coverage=current_metrics["coverage_percent"],
            hook_duration=current_metrics["hook_duration"],
            active_jobs=active_connections,
            error_count=current_metrics["hook_failures"],
            trend_direction=TrendDirection.IMPROVING,
            predictions={"next_target": "90"},
        )

    def get_alert_thresholds(self) -> dict[str, Any]:
        return {"coverage": 0.75}

    def set_alert_threshold(self, metric: str, threshold: float) -> None:
        self.latest_threshold = (metric, threshold)


class FakeJobManager:
    def __init__(self) -> None:
        self.progress_dir = Path.cwd() / ".tmp"
        self.active_connections: dict[str, Any] = {}


@pytest.fixture()
def test_app() -> TestClient:
    app = FastAPI()
    services = {
        "quality_service": FakeQualityService(),
        "telemetry": FakeTelemetry(),
    }
    job_manager = FakeJobManager()
    quality_service = services["quality_service"]
    telemetry = services["telemetry"]
    register_telemetry_api_endpoints(app, job_manager, telemetry, quality_service)
    return TestClient(app)


def test_monitoring_events_endpoint(test_app: TestClient) -> None:
    response = test_app.get("/monitoring/events")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    model = TelemetryResponseModel(**payload)
    assert model.data.counts["workflow.completed"] == 2


def test_monitoring_events_reset(test_app: TestClient) -> None:
    response = test_app.post("/monitoring/events/reset")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"]["counts"] == {}


def test_monitoring_health_endpoint(test_app: TestClient) -> None:
    response = test_app.get("/monitoring/health")
    assert response.status_code == 200
    payload = response.json()
    model = HealthResponseModel(**payload)
    assert model.status in {"healthy", "warning", "critical"}
    assert model.data.quality_score == 85

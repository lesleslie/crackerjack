from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from crackerjack.data.models import ProjectHealthRecord
from crackerjack.services.monitoring.health_metrics import HealthMetricsService, ProjectHealth


class DummyFilesystem:
    pass


class FakeRepository:
    def __init__(self) -> None:
        self.saved_data: dict[str, object] | None = None

    async def get(self, project_root: str) -> ProjectHealthRecord | None:
        return None

    async def upsert(
        self,
        project_root: str,
        data: dict[str, object],
    ) -> ProjectHealthRecord:
        self.saved_data = data
        return ProjectHealthRecord(
            id=1,
            project_root=project_root,
            lint_error_trend=data["lint_error_trend"],
            test_coverage_trend=data["test_coverage_trend"],
            dependency_age=data["dependency_age"],
            config_completeness=data["config_completeness"],
        )


@pytest.mark.asyncio
async def test_health_metrics_repository_persistence(monkeypatch: pytest.MonkeyPatch) -> None:
    service = HealthMetricsService(filesystem=DummyFilesystem(), console=None)
    repo = FakeRepository()
    service._repository = repo  # type: ignore[assignment]

    # Stub expensive operations
    service._count_lint_errors = lambda: 2  # type: ignore[assignment]
    service._get_test_coverage = lambda: 80.0  # type: ignore[assignment]
    service._calculate_dependency_ages = lambda: {"example": 120}  # type: ignore[assignment]
    service._assess_config_completeness = lambda: 0.9  # type: ignore[assignment]
    service._load_from_legacy_cache = lambda: ProjectHealth()  # type: ignore[assignment]

    metrics = await asyncio.to_thread(service.collect_current_metrics)

    assert isinstance(metrics, ProjectHealth)
    assert repo.saved_data is not None
    assert repo.saved_data["lint_error_trend"][-1] == 2
    assert repo.saved_data["test_coverage_trend"][-1] == 80.0

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from crackerjack.services.monitoring.dependency_monitor import DependencyMonitorService


class DummyFilesystem:
    pass


class FakeRepository:
    def __init__(self) -> None:
        self.saved: dict[str, dict[str, object]] = {}

    async def get(self, project_root: str) -> dict[str, object] | None:
        data = self.saved.get(project_root)
        if data is None:
            return None
        return type("Record", (), {"cache_data": data})()

    async def upsert(self, project_root: str, cache_data: dict[str, object]) -> None:
        self.saved[project_root] = cache_data


@pytest.mark.asyncio
async def test_dependency_monitor_repository_persistence(tmp_path: Path) -> None:
    service = DependencyMonitorService(filesystem=DummyFilesystem(), console=None)
    service.project_root = tmp_path
    repo = FakeRepository()
    service._repository = repo  # type: ignore[assignment]

    cache_data = {"last_major_notification": 0.0}
    await service._asave_update_cache(cache_data)

    loaded = await service._aload_update_cache()

    assert loaded["last_major_notification"] == 0.0

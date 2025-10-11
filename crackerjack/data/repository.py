"""Data repositories backed by ACB SQL adapter."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import desc
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from crackerjack.data.models import (
    DependencyMonitorCacheRecord,
    ProjectHealthRecord,
    QualityBaselineRecord,
)

LOGGER = logging.getLogger(__name__)


from acb.adapters.models import ACBQuery
from acb.depends import depends


class QualityBaselineRepository:
    def __init__(self) -> None:
        self.query = depends.get(ACBQuery)

    async def upsert(self, data: dict[str, Any]) -> QualityBaselineRecord:
        return await self.query.for_model(QualityBaselineRecord).simple.create_or_update(data, "git_hash")

    async def get_by_git_hash(self, git_hash: str) -> QualityBaselineRecord | None:
        return await self.query.for_model(QualityBaselineRecord).simple.find(git_hash=git_hash)

    async def list_recent(self, limit: int = 10) -> list[QualityBaselineRecord]:
        return await self.query.for_model(QualityBaselineRecord).advanced.order_by_desc("recorded_at").limit(limit).all()

    async def delete_for_git_hash(self, git_hash: str) -> bool:
        return await self.query.for_model(QualityBaselineRecord).simple.delete(git_hash=git_hash)



class HealthMetricsRepository:
    def __init__(self) -> None:
        self.query = depends.get(ACBQuery)

    async def upsert(
        self,
        project_root: str,
        data: dict[str, Any],
    ) -> ProjectHealthRecord:
        return await self.query.for_model(ProjectHealthRecord).simple.create_or_update(data, "project_root")

    async def get(self, project_root: str) -> ProjectHealthRecord | None:
        return await self.query.for_model(ProjectHealthRecord).simple.find(project_root=project_root)



class DependencyMonitorRepository:
    def __init__(self) -> None:
        self.query = depends.get(ACBQuery)

    async def upsert(
        self,
        project_root: str,
        cache_data: dict[str, Any],
    ) -> DependencyMonitorCacheRecord:
        return await self.query.for_model(DependencyMonitorCacheRecord).simple.create_or_update(cache_data, "project_root")

    async def get(self, project_root: str) -> DependencyMonitorCacheRecord | None:
        return await self.query.for_model(DependencyMonitorCacheRecord).simple.find(project_root=project_root)


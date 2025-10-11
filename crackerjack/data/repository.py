"""Data repositories backed by ACB SQL adapter."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from acb.depends import depends
from sqlalchemy import desc
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from crackerjack.data.models import (
    DependencyMonitorCacheRecord,
    ProjectHealthRecord,
    QualityBaselineRecord,
)

LOGGER = logging.getLogger(__name__)


class QualityBaselineRepository:
    """Repository for reading and writing quality baseline records."""

    def __init__(self, sql_adapter: Any) -> None:
        """Initialize repository with SQL adapter.

        Args:
            sql_adapter: SQL adapter instance (required - must be passed from DI)
        """
        self._sql = sql_adapter
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def upsert(self, data: dict[str, Any]) -> QualityBaselineRecord:
        """Create or update a quality baseline record."""
        await self._ensure_schema()

        async with self._sql.get_session() as session:
            record = await self._find_by_git_hash(session, data["git_hash"])
            if record is None:
                record = QualityBaselineRecord(**data)
                session.add(record)
            else:
                for key, value in data.items():
                    setattr(record, key, value)
            await session.commit()
            await session.refresh(record)
            return record

    async def get_by_git_hash(self, git_hash: str) -> QualityBaselineRecord | None:
        """Retrieve a record for a specific commit."""
        await self._ensure_schema()

        async with self._sql.get_session() as session:
            return await self._find_by_git_hash(session, git_hash)

    async def list_recent(self, limit: int = 10) -> list[QualityBaselineRecord]:
        """Return the most recent baseline records."""
        await self._ensure_schema()

        async with self._sql.get_session() as session:
            statement = (
                select(QualityBaselineRecord)
                .order_by(desc(QualityBaselineRecord.recorded_at))
                .limit(limit)
            )
            result = await session.exec(statement)
            rows: Iterable[QualityBaselineRecord] = result.all()
            return list(rows)

    async def delete_for_git_hash(self, git_hash: str) -> bool:
        """Delete a baseline record."""
        await self._ensure_schema()

        async with self._sql.get_session() as session:
            record = await self._find_by_git_hash(session, git_hash)
            if record is None:
                return False
            await session.delete(record)
            await session.commit()
            return True

    async def _find_by_git_hash(
        self,
        session: AsyncSession,
        git_hash: str,
    ) -> QualityBaselineRecord | None:
        statement = select(QualityBaselineRecord).where(
            QualityBaselineRecord.git_hash == git_hash,
        )
        result = await session.exec(statement)
        return result.one_or_none()

    async def _ensure_schema(self) -> None:
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            try:
                async with self._sql.get_conn() as conn:
                    def create_table(sync_conn: Any) -> None:
                        QualityBaselineRecord.__table__.create(  # type: ignore[attr-defined]
                            sync_conn,
                            checkfirst=True,
                        )

                    await conn.run_sync(create_table)
            except Exception:
                LOGGER.exception("Failed to ensure quality baseline table")
                raise
            else:
                self._initialized = True


class HealthMetricsRepository:
    """Repository for storing project health metrics."""

    def __init__(self, sql_adapter: Any) -> None:
        """Initialize repository with SQL adapter.

        Args:
            sql_adapter: SQL adapter instance (required - must be passed from DI)
        """
        self._sql = sql_adapter
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def upsert(
        self,
        project_root: str,
        data: dict[str, Any],
    ) -> ProjectHealthRecord:
        await self._ensure_schema()

        async with self._sql.get_session() as session:
            record = await self._get_by_project_root(session, project_root)
            if record is None:
                record = ProjectHealthRecord(project_root=project_root, **data)
                session.add(record)
            else:
                for key, value in data.items():
                    setattr(record, key, value)
            await session.commit()
            await session.refresh(record)
            return record

    async def get(self, project_root: str) -> ProjectHealthRecord | None:
        await self._ensure_schema()

        async with self._sql.get_session() as session:
            return await self._get_by_project_root(session, project_root)

    async def _get_by_project_root(
        self,
        session: AsyncSession,
        project_root: str,
    ) -> ProjectHealthRecord | None:
        statement = select(ProjectHealthRecord).where(
            ProjectHealthRecord.project_root == project_root,
        )
        result = await session.exec(statement)
        return result.one_or_none()

    async def _ensure_schema(self) -> None:
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            try:
                async with self._sql.get_conn() as conn:
                    def create_table(sync_conn: Any) -> None:
                        ProjectHealthRecord.__table__.create(  # type: ignore[attr-defined]
                            sync_conn,
                            checkfirst=True,
                        )

                    await conn.run_sync(create_table)
            except Exception:
                LOGGER.exception("Failed to ensure project health table")
                raise
            else:
                self._initialized = True


class DependencyMonitorRepository:
    """Repository for dependency monitor cache state."""

    def __init__(self, sql_adapter: Any) -> None:
        """Initialize repository with SQL adapter.

        Args:
            sql_adapter: SQL adapter instance (required - must be passed from DI)
        """
        self._sql = sql_adapter
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def upsert(
        self,
        project_root: str,
        cache_data: dict[str, Any],
    ) -> DependencyMonitorCacheRecord:
        await self._ensure_schema()

        async with self._sql.get_session() as session:
            record = await self._get_by_project_root(session, project_root)
            if record is None:
                record = DependencyMonitorCacheRecord(
                    project_root=project_root,
                    cache_data=cache_data,
                )
                session.add(record)
            else:
                record.cache_data = cache_data
                record.updated_at = datetime.utcnow()
            await session.commit()
            await session.refresh(record)
            return record

    async def get(self, project_root: str) -> DependencyMonitorCacheRecord | None:
        await self._ensure_schema()

        async with self._sql.get_session() as session:
            return await self._get_by_project_root(session, project_root)

    async def _get_by_project_root(
        self,
        session: AsyncSession,
        project_root: str,
    ) -> DependencyMonitorCacheRecord | None:
        statement = select(DependencyMonitorCacheRecord).where(
            DependencyMonitorCacheRecord.project_root == project_root,
        )
        result = await session.exec(statement)
        return result.one_or_none()

    async def _ensure_schema(self) -> None:
        if self._initialized:
            return

        async with self._init_lock:
            if self._initialized:
                return

            try:
                async with self._sql.get_conn() as conn:
                    def create_table(sync_conn: Any) -> None:
                        DependencyMonitorCacheRecord.__table__.create(  # type: ignore[attr-defined]
                            sync_conn,
                            checkfirst=True,
                        )

                    await conn.run_sync(create_table)
            except Exception:
                LOGGER.exception("Failed to ensure dependency monitor table")
                raise
            else:
                self._initialized = True

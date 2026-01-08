from __future__ import annotations

import typing as t
from typing import Any

from crackerjack.data.models import (
    DependencyMonitorCacheRecord,
    ProjectHealthRecord,
    QualityBaselineRecord,
)


class _InMemorySimpleOps:
    def __init__(self, model: type[Any], store: list[Any]) -> None:
        self._model = model
        self._store = store

    async def create_or_update(
        self,
        data: dict[str, Any],
        key_field: str,
    ) -> Any:
        key_value = data.get(key_field)
        existing = self._find_existing_by_key(key_field, key_value)

        if existing:
            return self._update_existing(existing, data)

        return self._create_new(data)

    def _find_existing_by_key(self, key_field: str, key_value: Any) -> Any | None:
        for existing in self._store:
            if getattr(existing, key_field, None) == key_value:
                return existing
        return None

    def _update_existing(self, existing: Any, data: dict[str, Any]) -> Any:
        if hasattr(existing, "update_from_dict"):
            existing.update_from_dict(data)
        else:
            self._update_entity_fields(existing, data)
        return existing

    def _update_entity_fields(self, existing: Any, data: dict[str, Any]) -> None:
        for key, value in data.items():
            if hasattr(existing, key):
                setattr(existing, key, value)

    def _create_new(self, data: dict[str, Any]) -> Any:
        instance = self._model(**data)
        self._store.append(instance)
        return instance

    async def find(self, **filters: Any) -> Any | None:
        for existing in self._store:
            if all(
                getattr(existing, key, None) == value for key, value in filters.items()
            ):
                return existing
        return None

    async def delete(self, **filters: Any) -> bool:
        to_remove = [
            existing
            for existing in self._store
            if all(
                getattr(existing, key, None) == value for key, value in filters.items()
            )
        ]
        for item in to_remove:
            self._store.remove(item)
        return bool(to_remove)

    async def all(self) -> list[Any]:
        return self._store.copy()


class _InMemoryAdvancedOps:
    def __init__(self, simple_ops: _InMemorySimpleOps) -> None:
        self._simple = simple_ops
        self._order_field: str | None = None
        self._limit: int | None = None

    def order_by_desc(self, field: str) -> _InMemoryAdvancedOps:
        self._order_field = field
        return self

    def limit(self, limit: int) -> _InMemoryAdvancedOps:
        self._limit = limit
        return self

    async def all(self) -> list[Any]:
        records = await self._simple.all()
        if self._order_field:

            def key_fn(item: Any) -> Any:
                return getattr(item, self._order_field or "", None)

            records.sort(key=key_fn, reverse=True)
        if self._limit is not None:
            records = records[: self._limit]
        return records


class _InMemoryModelInterface:
    def __init__(self, model: type[Any], store: list[Any]) -> None:
        self.simple = _InMemorySimpleOps(model, store)
        self.advanced = _InMemoryAdvancedOps(self.simple)


class InMemoryQuery:
    def __init__(self) -> None:
        self._stores: dict[type[Any], list[Any]] = {}

    def for_model(self, model: type[Any]) -> _InMemoryModelInterface:
        if model not in self._stores:
            self._stores[model] = []
        return _InMemoryModelInterface(model, self._stores[model])


_QUERY = InMemoryQuery()


class QualityBaselineRepository:
    def __init__(self) -> None:
        self.query = _QUERY

    async def upsert(self, data: dict[str, Any]) -> QualityBaselineRecord:
        result = await self.query.for_model(
            QualityBaselineRecord
        ).simple.create_or_update(data, "git_hash")
        return t.cast(QualityBaselineRecord, result)

    async def get_by_git_hash(self, git_hash: str) -> QualityBaselineRecord | None:
        result = await self.query.for_model(QualityBaselineRecord).simple.find(
            git_hash=git_hash
        )
        return t.cast(QualityBaselineRecord | None, result)

    async def list_recent(self, limit: int = 10) -> list[QualityBaselineRecord]:
        result = (
            await self.query.for_model(QualityBaselineRecord)
            .advanced.order_by_desc("recorded_at")
            .limit(limit)
            .all()
        )
        return t.cast(list[QualityBaselineRecord], result)

    async def delete_for_git_hash(self, git_hash: str) -> bool:
        result = await self.query.for_model(QualityBaselineRecord).simple.delete(
            git_hash=git_hash
        )
        return t.cast(bool, result)


class HealthMetricsRepository:
    def __init__(self) -> None:
        self.query = _QUERY

    async def upsert(
        self,
        project_name: str,
        data: dict[str, Any],
    ) -> ProjectHealthRecord:
        data = {"project_name": project_name} | data
        result = await self.query.for_model(
            ProjectHealthRecord
        ).simple.create_or_update(data, "project_name")
        return t.cast(ProjectHealthRecord, result)

    async def get(self, project_name: str) -> ProjectHealthRecord | None:
        result = await self.query.for_model(ProjectHealthRecord).simple.find(
            project_name=project_name
        )
        return t.cast(ProjectHealthRecord | None, result)


class DependencyMonitorRepository:
    def __init__(self) -> None:
        self.query = _QUERY

    async def upsert(
        self,
        project_root: str,
        cache_data: dict[str, Any],
    ) -> DependencyMonitorCacheRecord:
        result = await self.query.for_model(
            DependencyMonitorCacheRecord
        ).simple.create_or_update(cache_data, "project_root")
        return t.cast(DependencyMonitorCacheRecord, result)

    async def get(self, project_root: str) -> DependencyMonitorCacheRecord | None:
        result = await self.query.for_model(DependencyMonitorCacheRecord).simple.find(
            project_root=project_root
        )
        return t.cast(DependencyMonitorCacheRecord | None, result)

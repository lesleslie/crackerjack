"""Data repositories backed by ACB SQL adapter."""

from __future__ import annotations

import logging
from typing import Any

from crackerjack.data.models import (
    DependencyMonitorCacheRecord,
    ProjectHealthRecord,
    QualityBaselineRecord,
)

LOGGER = logging.getLogger(__name__)


from acb.depends import depends

try:
    from acb.adapters.models._hybrid import ACBQuery  # type: ignore[attr-defined]
    from acb.adapters.models._memory import (
        MemoryDatabaseAdapter,  # type: ignore[attr-defined]
    )
    from acb.adapters.models._pydantic import (
        PydanticModelAdapter,  # type: ignore[attr-defined]
    )
    from acb.adapters.models._query import registry  # type: ignore[attr-defined]

    # Register in-memory adapters for default usage
    registry.register_database_adapter("memory", MemoryDatabaseAdapter())
    registry.register_model_adapter("pydantic", PydanticModelAdapter())

    # ACB hybrid query is available - use in-memory adapter as default
    # (SQL/NoSQL adapters can be configured when those databases are set up)
    _query_instance = ACBQuery(
        database_adapter_name="memory",
        model_adapter_name="pydantic",
    )
    depends.set(ACBQuery, _query_instance)

except ImportError:  # pragma: no cover - fallback when hybrid query missing
    LOGGER.warning(
        "ACB hybrid query adapter not available; using in-memory query fallback.",
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
            for existing in self._store:
                if getattr(existing, key_field, None) == key_value:
                    if hasattr(existing, "update_from_dict"):
                        existing.update_from_dict(data)
                    else:
                        for key, value in data.items():
                            if hasattr(existing, key):
                                setattr(existing, key, value)
                    return existing
            instance = self._model(**data)
            self._store.append(instance)
            return instance

        async def find(self, **filters: Any) -> Any | None:
            for existing in self._store:
                if all(
                    getattr(existing, key, None) == value
                    for key, value in filters.items()
                ):
                    return existing
            return None

        async def delete(self, **filters: Any) -> bool:
            to_remove: list[Any] = []
            for existing in self._store:
                if all(
                    getattr(existing, key, None) == value
                    for key, value in filters.items()
                ):
                    to_remove.append(existing)
            for item in to_remove:
                self._store.remove(item)
            return bool(to_remove)

        async def all(self) -> list[Any]:
            return list(self._store)

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
                records = sorted(
                    records,
                    key=lambda item: getattr(item, self._order_field or "", None),
                    reverse=True,
                )
            if self._limit is not None:
                records = records[: self._limit]
            return records

    class _InMemoryModelInterface:
        def __init__(self, model: type[Any], store: list[Any]) -> None:
            self.simple = _InMemorySimpleOps(model, store)
            self.advanced = _InMemoryAdvancedOps(self.simple)

    class ACBQuery:  # type: ignore[no-redef]
        def __init__(self) -> None:
            self._stores: dict[type[Any], list[Any]] = {}

        def for_model(self, model: type[Any]) -> _InMemoryModelInterface:
            if model not in self._stores:
                self._stores[model] = []
            return _InMemoryModelInterface(model, self._stores[model])

    depends.set(ACBQuery, ACBQuery())


class QualityBaselineRepository:
    def __init__(self) -> None:
        self.query = depends.get_sync(ACBQuery)

    async def upsert(self, data: dict[str, Any]) -> QualityBaselineRecord:
        return await self.query.for_model(
            QualityBaselineRecord
        ).simple.create_or_update(data, "git_hash")

    async def get_by_git_hash(self, git_hash: str) -> QualityBaselineRecord | None:
        return await self.query.for_model(QualityBaselineRecord).simple.find(
            git_hash=git_hash
        )

    async def list_recent(self, limit: int = 10) -> list[QualityBaselineRecord]:
        return (
            await self.query.for_model(QualityBaselineRecord)
            .advanced.order_by_desc("recorded_at")
            .limit(limit)
            .all()
        )

    async def delete_for_git_hash(self, git_hash: str) -> bool:
        return await self.query.for_model(QualityBaselineRecord).simple.delete(
            git_hash=git_hash
        )


class HealthMetricsRepository:
    def __init__(self) -> None:
        self.query = depends.get_sync(ACBQuery)

    async def upsert(
        self,
        project_root: str,
        data: dict[str, Any],
    ) -> ProjectHealthRecord:
        return await self.query.for_model(ProjectHealthRecord).simple.create_or_update(
            data, "project_root"
        )

    async def get(self, project_root: str) -> ProjectHealthRecord | None:
        return await self.query.for_model(ProjectHealthRecord).simple.find(
            project_root=project_root
        )


class DependencyMonitorRepository:
    def __init__(self) -> None:
        self.query = depends.get_sync(ACBQuery)

    async def upsert(
        self,
        project_root: str,
        cache_data: dict[str, Any],
    ) -> DependencyMonitorCacheRecord:
        return await self.query.for_model(
            DependencyMonitorCacheRecord
        ).simple.create_or_update(cache_data, "project_root")

    async def get(self, project_root: str) -> DependencyMonitorCacheRecord | None:
        return await self.query.for_model(DependencyMonitorCacheRecord).simple.find(
            project_root=project_root
        )

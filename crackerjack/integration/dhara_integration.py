from __future__ import annotations

import asyncio
import json
import logging
import operator
import sqlite3
import tempfile
import typing as t
import weakref
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

if t.TYPE_CHECKING:
    from dhara.core.connection import AsyncConnection

from crackerjack.integration.dhara_mcp_client import (
    DharaMCPClient,
    DharaMCPConfig,
)

logger = logging.getLogger(__name__)


def _days_ago_iso(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).date().isoformat()


@dataclass(frozen=True)
class AdapterAttemptRecord:
    adapter_name: str
    file_type: str
    file_size: int
    project_context: dict[str, t.Any]
    success: bool
    execution_time_ms: int
    error_type: str | None
    timestamp: datetime

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "adapter_name": self.adapter_name,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "project_context": self.project_context,
            "success": self.success,
            "execution_time_ms": self.execution_time_ms,
            "error_type": self.error_type,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> AdapterAttemptRecord:
        return cls(
            adapter_name=data["adapter_name"],
            file_type=data["file_type"],
            file_size=data["file_size"],
            project_context=data["project_context"],
            success=data["success"],
            execution_time_ms=data["execution_time_ms"],
            error_type=data.get("error_type"),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass(frozen=True)
class AdapterEffectiveness:
    adapter_name: str
    file_type: str
    total_attempts: int
    successful_attempts: int
    success_rate: float
    avg_execution_time_ms: float
    common_errors: list[tuple[str, int]]
    last_attempted: datetime | None


@t.runtime_checkable
class AdapterLearnerProtocol(t.Protocol):
    def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None: ...

    def recommend_adapter(
        self,
        file_path: str,
        project_context: dict[str, t.Any],
        candidates: list[str],
    ) -> str | None: ...

    def get_adapter_effectiveness(
        self,
        adapter_name: str,
        file_type: str,
    ) -> AdapterEffectiveness | None: ...

    def get_best_adapters_for_file_type(
        self,
        file_type: str,
    ) -> list[tuple[str, float]]: ...

    def is_enabled(self) -> bool: ...

    def close(self) -> None: ...


@dataclass
class NoOpAdapterLearner:
    backend_name: str = "none"

    def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None:
        logger.debug("No-op adapter learner: skipping record_adapter_attempt")

    def recommend_adapter(
        self,
        file_path: str,
        project_context: dict[str, t.Any],
        candidates: list[str],
    ) -> str | None:
        return None

    def get_adapter_effectiveness(
        self,
        adapter_name: str,
        file_type: str,
    ) -> AdapterEffectiveness | None:
        return None

    def get_best_adapters_for_file_type(
        self,
        file_type: str,
    ) -> list[tuple[str, float]]:
        return []

    def is_enabled(self) -> bool:
        return False

    def close(self) -> None:
        pass


@dataclass
class SQLiteAdapterLearner:
    db_path: Path
    min_attempts: int = 5
    _initialized: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        self._initialize_db()

    def _initialize_db(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS adapter_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    adapter_name TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    project_context TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    execution_time_ms INTEGER NOT NULL,
                    error_type TEXT,
                    timestamp TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS adapter_effectiveness (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    adapter_name TEXT NOT NULL,
                    file_type TEXT NOT NULL UNIQUE,
                    total_attempts INTEGER DEFAULT 0,
                    successful_attempts INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    avg_execution_time_ms REAL DEFAULT 0.0,
                    common_errors TEXT NOT NULL,
                    last_attempted TEXT,
                    last_updated TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_adapter_file_type
                ON adapter_attempts(adapter_name, file_type)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_file_type
                ON adapter_attempts(file_type)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_success
                ON adapter_attempts(success)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON adapter_attempts(timestamp DESC)
                """
            )

            conn.commit()
            conn.close()

            self._initialized = True
            logger.info(f"✅ Adapter learner initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize adapter learner: {e}")
            raise

    def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None:
        if not self._initialized:
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO adapter_attempts (
                    adapter_name, file_type, file_size, project_context,
                    success, execution_time_ms, error_type, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.adapter_name,
                    attempt.file_type,
                    attempt.file_size,
                    json.dumps(attempt.project_context),
                    attempt.success,
                    attempt.execution_time_ms,
                    attempt.error_type,
                    attempt.timestamp.isoformat(),
                ),
            )

            self._update_effectiveness_metrics(cursor, attempt)

            conn.commit()
            conn.close()

            logger.debug(
                f"Recorded adapter attempt: {attempt.adapter_name} for {attempt.file_type} "
                f"(success={attempt.success})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to record adapter attempt: {e}")

    def _update_effectiveness_metrics(
        self,
        cursor: sqlite3.Cursor,
        attempt: AdapterAttemptRecord,
    ) -> None:
        key = (attempt.adapter_name, attempt.file_type)

        cursor.execute(
            """
            SELECT total_attempts, successful_attempts, avg_execution_time_ms
            FROM adapter_effectiveness
            WHERE adapter_name = ? AND file_type = ?
            """,
            key,
        )

        row = cursor.fetchone()

        if row:
            total_attempts, successful_attempts, avg_time = row
            new_total = total_attempts + 1
            new_successful = successful_attempts + (1 if attempt.success else 0)
            new_success_rate = new_successful / new_total if new_total > 0 else 0.0

            new_avg_time = (
                avg_time * total_attempts + attempt.execution_time_ms
            ) / new_total

            cursor.execute(
                """
                SELECT common_errors FROM adapter_effectiveness
                WHERE adapter_name = ? AND file_type = ?
                """,
                key,
            )
            errors_json = cursor.fetchone()[0]
            errors = json.loads(errors_json)

            if attempt.error_type:
                error_key = attempt.error_type
                errors_found = False
                for i, (err_type, count) in enumerate(errors):
                    if err_type == error_key:
                        errors[i] = (err_type, count + 1)
                        errors_found = True
                        break
                if not errors_found:
                    errors.append((error_key, 1))

            cursor.execute(
                """
                UPDATE adapter_effectiveness
                SET total_attempts = ?,
                    successful_attempts = ?,
                    success_rate = ?,
                    avg_execution_time_ms = ?,
                    common_errors = ?,
                    last_attempted = ?,
                    last_updated = ?
                WHERE adapter_name = ? AND file_type = ?
                """,
                (
                    new_total,
                    new_successful,
                    new_success_rate,
                    new_avg_time,
                    json.dumps(errors),
                    attempt.timestamp.isoformat(),
                    datetime.now().isoformat(),
                    attempt.adapter_name,
                    attempt.file_type,
                ),
            )
        else:
            errors = [(attempt.error_type, 1)] if attempt.error_type else []

            cursor.execute(
                """
                INSERT INTO adapter_effectiveness (
                    adapter_name, file_type, total_attempts, successful_attempts,
                    success_rate, avg_execution_time_ms, common_errors,
                    last_attempted, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attempt.adapter_name,
                    attempt.file_type,
                    1,
                    1 if attempt.success else 0,
                    1.0 if attempt.success else 0.0,
                    attempt.execution_time_ms,
                    json.dumps(errors),
                    attempt.timestamp.isoformat(),
                    datetime.now().isoformat(),
                ),
            )

    def recommend_adapter(
        self,
        file_path: str,
        project_context: dict[str, t.Any],
        candidates: list[str],
    ) -> str | None:
        if not self._initialized:
            return None

        file_type = Path(file_path).suffix

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            placeholders = ", ".join(["?"] * len(candidates))
            cursor.execute(
                f"""
                SELECT adapter_name, success_rate, total_attempts
                FROM adapter_effectiveness
                WHERE file_type = ?
                AND adapter_name IN ({placeholders})
                AND total_attempts >= ?
                ORDER BY success_rate DESC
                LIMIT 1
                """,
                [file_type] + candidates + [self.min_attempts],
            )

            row = cursor.fetchone()
            conn.close()

            if row:
                adapter_name, success_rate, _ = row
                logger.debug(
                    f"Recommending adapter {adapter_name} for {file_type} "
                    f"(success_rate={success_rate:.2%})"
                )
                return adapter_name

            return None

        except Exception as e:
            logger.error(f"❌ Failed to recommend adapter: {e}")
            return None

    def get_adapter_effectiveness(
        self,
        adapter_name: str,
        file_type: str,
    ) -> AdapterEffectiveness | None:
        if not self._initialized:
            return None

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT total_attempts, successful_attempts, success_rate,
                       avg_execution_time_ms, common_errors, last_attempted
                FROM adapter_effectiveness
                WHERE adapter_name = ? AND file_type = ?
                """,
                (adapter_name, file_type),
            )

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            (
                total_attempts,
                successful_attempts,
                success_rate,
                avg_time,
                errors_json,
                last_attempted,
            ) = row

            common_errors = [
                (err_type, count) for err_type, count in json.loads(errors_json)
            ]

            return AdapterEffectiveness(
                adapter_name=adapter_name,
                file_type=file_type,
                total_attempts=total_attempts,
                successful_attempts=successful_attempts,
                success_rate=success_rate,
                avg_execution_time_ms=avg_time,
                common_errors=common_errors,
                last_attempted=datetime.fromisoformat(last_attempted)
                if last_attempted
                else None,
            )

        except Exception as e:
            logger.error(f"❌ Failed to get adapter effectiveness: {e}")
            return None

    def get_best_adapters_for_file_type(
        self,
        file_type: str,
    ) -> list[tuple[str, float]]:
        if not self._initialized:
            return []

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT adapter_name, success_rate, total_attempts
                FROM adapter_effectiveness
                WHERE file_type = ?
                AND total_attempts >= ?
                ORDER BY success_rate DESC
                LIMIT 10
                """,
                (file_type, self.min_attempts),
            )

            rows = cursor.fetchall()
            conn.close()

            return [(row[0], row[1]) for row in rows]

        except Exception as e:
            logger.error(f"❌ Failed to get best adapters: {e}")
            return []

    def is_enabled(self) -> bool:
        return self._initialized

    def close(self) -> None:
        pass


@dataclass
class DharaAdapterLearner:
    db_path: Path
    min_attempts: int = 5
    retention_days: int = 90
    _initialized: bool = field(init=False, default=False)
    _async_connection: AsyncConnection | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        import asyncio

        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            from dhara.core.connection import AsyncConnection
            from dhara.storage.sqlite import AsyncSqliteStorage

            async def _init_connection() -> None:
                storage = AsyncSqliteStorage(url=f"sqlite+aiosqlite://{self.db_path}")
                await storage.init()
                self._async_connection = await AsyncConnection.new(storage)

            try:
                asyncio.run(_init_connection())
            except Exception as e:
                if isinstance(e, OSError) and (
                    isinstance(e, BlockingIOError) or "locked" in str(e).lower()
                ):
                    raise
                raise RuntimeError(
                    f"Failed to initialize async Dhara connection at {self.db_path}: {e}"
                ) from e

            from dhara.mcp.kv_timeseries import (
                AsyncKVTimeSeriesStore,
                TimeSeriesRetention,
            )

            self._ts_store = AsyncKVTimeSeriesStore(
                self._async_connection,
                retention=TimeSeriesRetention(retention_days=self.retention_days),
            )
            self._initialized = True
            logger.info(f"✅ Dhara adapter learner initialized (async): {self.db_path}")
            weakref.finalize(self, _safe_abort_sync, self._async_connection)
        except BlockingIOError as e:
            logger.warning(
                f"Dhara backend unavailable at {self.db_path}: "
                f"resource locked (errno={e.errno}). "
                "Another process likely holds the lock."
            )
            raise
        except Exception as e:
            logger.error(
                "❌ Failed to initialize Dhara adapter learner at "
                f"{self.db_path}: {type(e).__name__}: {e}"
            )
            raise RuntimeError(
                "Dhara adapter storage must use a dedicated Dhara-formatted file"
            ) from e

    def close(self) -> None:
        if self._initialized and self._async_connection is not None:
            asyncio.run(self._async_connection.abort())
            self._async_connection = None
            self._initialized = False

    def _effectiveness_key(self, adapter_name: str, file_type: str) -> str:
        return f"effectiveness:{adapter_name}:{file_type}"

    def _file_type_index_key(self, file_type: str) -> str:
        return f"file_type_index:{file_type}"

    async def _record_attempt_async(self, attempt: AdapterAttemptRecord) -> None:
        entity_id = f"{attempt.adapter_name}:{attempt.file_type}"

        await self._ts_store.record_time_series_async(
            metric_type="adapter_attempt",
            entity_id=entity_id,
            record=attempt.to_dict(),
        )

        eff_key = self._effectiveness_key(attempt.adapter_name, attempt.file_type)
        current = await self._ts_store.get_async(eff_key)
        existing = current.get("value")

        if existing:
            total = existing["total_attempts"] + 1
            successful = existing["successful_attempts"] + (1 if attempt.success else 0)
            avg_time = (
                existing["avg_execution_time_ms"] * existing["total_attempts"]
                + attempt.execution_time_ms
            ) / total
            errors = list(existing.get("common_errors", []))

            if attempt.error_type:
                found = False
                for i, (err_type, count) in enumerate(errors):
                    if err_type == attempt.error_type:
                        errors[i] = (err_type, count + 1)
                        found = True
                        break
                if not found:
                    errors.append((attempt.error_type, 1))
        else:
            total = 1
            successful = 1 if attempt.success else 0
            avg_time = float(attempt.execution_time_ms)
            errors = [(attempt.error_type, 1)] if attempt.error_type else []

        aggregate = {
            "adapter_name": attempt.adapter_name,
            "file_type": attempt.file_type,
            "total_attempts": total,
            "successful_attempts": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_execution_time_ms": round(avg_time, 1),
            "common_errors": errors,
            "last_attempted": attempt.timestamp.isoformat(),
        }

        await self._ts_store.put_async(eff_key, aggregate)

        idx_key = self._file_type_index_key(attempt.file_type)
        idx_result = await self._ts_store.get_async(idx_key)
        adapter_names: list[str] = idx_result.get("value") or []
        if attempt.adapter_name not in adapter_names:
            adapter_names = adapter_names.copy()
            adapter_names.append(attempt.adapter_name)
            await self._ts_store.put_async(idx_key, adapter_names)

    def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None:
        if not self._initialized:
            return
        try:
            asyncio.run(self._record_attempt_async(attempt))
            logger.debug(
                f"Recorded adapter attempt via Dhara: {attempt.adapter_name} for {attempt.file_type} "
                f"(success={attempt.success})"
            )
        except Exception as e:
            logger.error(f"❌ Failed to record adapter attempt via Dhara: {e}")

    def recommend_adapter(
        self,
        file_path: str,
        project_context: dict[str, t.Any],
        candidates: list[str],
    ) -> str | None:
        if not self._initialized:
            return None

        try:
            file_type = Path(file_path).suffix
            best_adapter = None
            best_rate = -1.0

            for candidate in candidates:
                eff_key = self._effectiveness_key(candidate, file_type)
                result = asyncio.run(self._ts_store.get_async(eff_key))
                eff = result.get("value")

                if eff and eff.get("total_attempts", 0) >= self.min_attempts:
                    rate = eff.get("success_rate", 0.0)
                    if rate > best_rate:
                        best_rate = rate
                        best_adapter = candidate

            if best_adapter:
                logger.debug(
                    f"Dhara recommending adapter {best_adapter} for {file_type} "
                    f"(success_rate={best_rate:.2%})"
                )
            return best_adapter

        except Exception as e:
            logger.error(f"❌ Failed to recommend adapter via Dhara: {e}")
            return None

    def get_adapter_effectiveness(
        self,
        adapter_name: str,
        file_type: str,
    ) -> AdapterEffectiveness | None:
        if not self._initialized:
            return None

        try:
            eff_key = self._effectiveness_key(adapter_name, file_type)
            result = asyncio.run(self._ts_store.get_async(eff_key))
            eff = result.get("value")

            if not eff:
                return None

            common_errors = [
                (err_type, count) for err_type, count in eff.get("common_errors", [])
            ]

            return AdapterEffectiveness(
                adapter_name=adapter_name,
                file_type=file_type,
                total_attempts=eff["total_attempts"],
                successful_attempts=eff["successful_attempts"],
                success_rate=eff["success_rate"],
                avg_execution_time_ms=eff["avg_execution_time_ms"],
                common_errors=common_errors,
                last_attempted=datetime.fromisoformat(eff["last_attempted"])
                if eff.get("last_attempted")
                else None,
            )

        except Exception as e:
            logger.error(f"❌ Failed to get adapter effectiveness via Dhara: {e}")
            return None

    def get_best_adapters_for_file_type(
        self,
        file_type: str,
    ) -> list[tuple[str, float]]:
        if not self._initialized:
            return []

        try:
            idx_key = self._file_type_index_key(file_type)
            idx_result = asyncio.run(self._ts_store.get_async(idx_key))
            adapter_names: list[str] = idx_result.get("value") or [] # type: ignore

            results = []
            for adapter_name in adapter_names:
                eff_key = self._effectiveness_key(adapter_name, file_type)
                result = asyncio.run(self._ts_store.get_async(eff_key))
                eff = result.get("value")

                if eff and eff.get("total_attempts", 0) >= self.min_attempts:
                    results.append((adapter_name, eff["success_rate"]))

            results.sort(key=operator.itemgetter(1), reverse=True)
            return results[:10]

        except Exception as e:
            logger.error(f"❌ Failed to get best adapters via Dhara: {e}")
            return []

    def is_enabled(self) -> bool:
        return self._initialized


class DharaMCPAdapterLearner:
    def __init__(self, config: DharaMCPConfig) -> None:
        self._client = DharaMCPClient(config)

    def _derive_pattern(self, attempt: AdapterAttemptRecord) -> str:
        if attempt.success:
            return f"success:{attempt.adapter_name}"
        error_name = attempt.error_type or "unknown"
        return f"error:{error_name}"

    def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None:
        asyncio.run(self._record_attempt_async(attempt))

    async def _record_attempt_async(self, attempt: AdapterAttemptRecord) -> None:
        try:
            connected = await self._client.connect()
            if not connected:
                logger.debug("DharaMCPAdapterLearner: not connected, skipping record")
                return
            record = attempt.to_dict() | {"pattern": self._derive_pattern(attempt)}
            await self._client.record_time_series(
                metric_type="adapter_attempt",
                entity_id=attempt.adapter_name,
                record=record,
                timestamp=datetime.now(UTC).isoformat(),
            )
        except Exception as exc:
            logger.debug(
                f"DharaMCPAdapterLearner.record_adapter_attempt failed: {exc!r}"
            )

    def close(self) -> None:
        try:
            asyncio.run(self._client.disconnect())
        except Exception as exc:
            logger.debug(f"DharaMCPAdapterLearner.close failed: {exc!r}")

    def recommend_adapter(
        self,
        file_path: str,
        project_context: dict[str, t.Any],
        candidates: list[str],
    ) -> str | None:
        try:
            start = _days_ago_iso(30)
            patterns = asyncio.run(
                self._client.aggregate_patterns(start, min_occurrences=1)
            )
        except Exception as exc:
            logger.debug(f"DharaMCPAdapterLearner.recommend_adapter failed: {exc!r}")
            return None

        if not patterns:
            return None

        best: str | None = None
        best_count = -1
        for entry in patterns:
            if not isinstance(entry, dict):
                continue
            pattern = entry.get("pattern", "")
            if not isinstance(pattern, str) or not pattern.startswith("success:"):
                continue
            adapter = pattern.removeprefix("success:")
            if adapter in candidates and entry.get("count", 0) > best_count:
                best = adapter
                best_count = entry["count"]
        return best

    def get_adapter_effectiveness(
        self,
        adapter_name: str,
        file_type: str,
    ) -> AdapterEffectiveness | None:
        try:
            start = _days_ago_iso(30)
            records = asyncio.run(
                self._client.query_time_series(
                    metric_type="adapter_attempt",
                    entity_id=adapter_name,
                    start_date=start,
                    limit=1000,
                )
            )
        except Exception as exc:
            logger.debug(
                f"DharaMCPAdapterLearner.get_adapter_effectiveness failed: {exc!r}"
            )
            return None

        matching = [
            r
            for r in records
            if isinstance(r, dict) and r.get("file_type") == file_type
        ]
        if not matching:
            return None

        total = len(matching)
        successful = sum(1 for r in matching if r.get("success"))
        success_rate = successful / total

        times: list[float] = []
        for r in matching:
            value = r.get("execution_time_ms")
            if isinstance(value, (int, float)):
                times.append(float(value))
        avg_time = sum(times) / len(times) if times else 0.0

        errors: dict[str, int] = {}
        for r in matching:
            if not r.get("success"):
                error_type = r.get("error_type")
                if isinstance(error_type, str) and error_type:
                    errors[error_type] = errors.get(error_type, 0) + 1
        common_errors = sorted(errors.items(), key=lambda kv: -kv[1])[:5]

        last_dt: datetime | None = None
        last = matching[0].get("timestamp")
        if isinstance(last, str) and last:
            try:
                last_dt = datetime.fromisoformat(last)
            except ValueError:
                last_dt = None

        return AdapterEffectiveness(
            adapter_name=adapter_name,
            file_type=file_type,
            total_attempts=total,
            successful_attempts=successful,
            success_rate=success_rate,
            avg_execution_time_ms=avg_time,
            common_errors=common_errors,
            last_attempted=last_dt,
        )

    def get_best_adapters_for_file_type(
        self,
        file_type: str,
    ) -> list[tuple[str, float]]:
        try:
            start = _days_ago_iso(30)
            patterns = asyncio.run(
                self._client.aggregate_patterns(start, min_occurrences=1)
            )
        except Exception as exc:
            logger.debug(
                f"DharaMCPAdapterLearner.get_best_adapters_for_file_type failed: {exc!r}"
            )
            return []

        success_counts: dict[str, int] = {}
        for entry in patterns:
            if not isinstance(entry, dict):
                continue
            pattern = entry.get("pattern", "")
            if not isinstance(pattern, str) or not pattern.startswith("success:"):
                continue
            adapter = pattern.removeprefix("success:")
            count = entry.get("count", 0)
            if isinstance(count, (int, float)):
                success_counts[adapter] = success_counts.get(adapter, 0) + int(count)

        return sorted(success_counts.items(), key=lambda kv: -kv[1])

    def is_enabled(self) -> bool:
        return self._client.config.enabled


def _safe_abort_sync(connection: t.Any) -> None:
    if connection is None:
        return
    try:
        abort = getattr(connection, "abort", None)
        if abort is None:
            return
        result = abort()
        if asyncio.iscoroutine(result):
            asyncio.run(result)
    except BaseException as exc: # noqa: BLE001 - by design
        logger.debug(f"finalizer: connection abort failed: {exc!r}")


def _load_dhara_mcp_config() -> DharaMCPConfig:
    from crackerjack.config.settings import DharaMCPSettings

    try:
        settings = DharaMCPSettings()
        return DharaMCPConfig(
            url=settings.url,
            timeout_seconds=settings.timeout_seconds,
            enabled=settings.enabled,
            token=settings.token,
        )
    except Exception as exc:
        logger.debug(f"failed to load DharaMCPSettings: {exc!r}")
        return DharaMCPConfig(enabled=False)


def create_adapter_learner(
    enabled: bool = True,
    db_path: Path | None = None,
    min_attempts: int = 5,
    backend: str = "auto",
) -> AdapterLearnerProtocol:
    if not enabled:
        logger.info("adapter_learning: disabled, using NoOp")
        return NoOpAdapterLearner()

    db_path = db_path or Path(".crackerjack/adapter_learning.db")
    mcp_config = _load_dhara_mcp_config()

    if backend in ("auto", "dhara") and mcp_config.enabled:
        try:
            learner = DharaMCPAdapterLearner(mcp_config)
            logger.info(
                f"adapter_learning: selected Dhara MCP at {mcp_config.url} "
                f"(will probe on first use)"
            )
            return learner
        except Exception as exc:
            logger.warning(
                f"Dhara MCP unavailable "
                f"({type(exc).__name__}: {exc}); "
                f"falling back to in-process Dhara"
            )

    if backend in ("auto", "dhara"):
        for candidate in _dhara_adapter_learning_db_candidates(db_path):
            try:
                learner = DharaAdapterLearner(
                    db_path=candidate,
                    min_attempts=min_attempts,
                )
                logger.info(f"adapter_learning: using in-process Dhara at {candidate}")
                return learner
            except Exception as exc:
                logger.warning(f"Dhara in-process unavailable at {candidate}: {exc}")
                continue
        if backend == "dhara":
            logger.warning("Dhara backend unavailable, using NoOp as requested")
            return NoOpAdapterLearner()

    for candidate in _adapter_learning_db_candidates(db_path):
        try:
            learner = SQLiteAdapterLearner(
                db_path=candidate,
                min_attempts=min_attempts,
            )
            logger.info(f"adapter_learning: using SQLite at {candidate}")
            return learner
        except Exception as exc:
            logger.warning(f"SQLite adapter learner unavailable: {exc}")

    logger.warning("adapter_learning: all backends failed, using NoOp")
    return NoOpAdapterLearner()


def _adapter_learning_db_candidates(db_path: Path) -> list[Path]:
    candidates = [
        db_path,
        Path.cwd() / ".crackerjack" / db_path.name,
        Path(tempfile.gettempdir()) / "crackerjack" / db_path.name,
    ]
    unique_candidates = list(dict.fromkeys(candidates))
    return unique_candidates


def _dhara_adapter_learning_db_candidates(db_path: Path) -> list[Path]:
    dhara_name = db_path.with_suffix(".dhara").name
    candidates = [
        db_path.with_suffix(".dhara"),
        Path.cwd() / ".crackerjack" / dhara_name,
        Path(tempfile.gettempdir()) / "crackerjack" / dhara_name,
    ]
    unique_candidates = list(dict.fromkeys(candidates))
    return unique_candidates


@dataclass
class DharaLearningIntegration:
    adapter_learner: AdapterLearnerProtocol
    min_attempts: int = 5

    def track_adapter_execution(
        self,
        adapter_name: str,
        file_path: str,
        file_size: int,
        project_context: dict[str, t.Any],
        success: bool,
        execution_time_ms: int,
        error_type: str | None = None,
    ) -> None:
        attempt = AdapterAttemptRecord(
            adapter_name=adapter_name,
            file_type=Path(file_path).suffix,
            file_size=file_size,
            project_context=project_context,
            success=success,
            execution_time_ms=execution_time_ms,
            error_type=error_type,
            timestamp=datetime.now(),
        )

        self.adapter_learner.record_adapter_attempt(attempt)

    def get_adapter_recommendation(
        self,
        file_path: str,
        project_context: dict[str, t.Any],
        available_adapters: list[str],
    ) -> str | None:
        return self.adapter_learner.recommend_adapter(
            file_path=file_path,
            project_context=project_context,
            candidates=available_adapters,
        )

    def get_adapter_stats(
        self,
        adapter_name: str,
        file_type: str,
    ) -> AdapterEffectiveness | None:
        return self.adapter_learner.get_adapter_effectiveness(
            adapter_name=adapter_name,
            file_type=file_type,
        )

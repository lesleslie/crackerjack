from __future__ import annotations

import json
import logging
import sqlite3
import tempfile
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


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

            placeholders = ",".join(["?"] * len(candidates))
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
    """Adapter learner backed by Dhara ACID storage.

    Uses KVTimeSeriesStore for both time-series records and effectiveness
    summaries. All data persisted via Connection.commit().
    """

    db_path: Path
    min_attempts: int = 5
    retention_days: int = 90
    _initialized: bool = field(init=False, default=False)

    def __post_init__(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            from dhara.core.connection import Connection
            from dhara.mcp.kv_timeseries import KVTimeSeriesStore, TimeSeriesRetention

            self._connection = Connection(str(self.db_path))
            self._ts_store = KVTimeSeriesStore(
                self._connection,
                retention=TimeSeriesRetention(retention_days=self.retention_days),
            )
            self._initialized = True
            logger.info(f"✅ Dhara adapter learner initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Dhara adapter learner: {e}")
            raise

    def close(self) -> None:
        """Release the Dhara connection."""
        if self._initialized and hasattr(self, "_connection"):
            self._connection.abort()
            self._initialized = False

    def _effectiveness_key(self, adapter_name: str, file_type: str) -> str:
        return f"effectiveness:{adapter_name}:{file_type}"

    def _file_type_index_key(self, file_type: str) -> str:
        return f"file_type_index:{file_type}"

    def record_adapter_attempt(self, attempt: AdapterAttemptRecord) -> None:
        if not self._initialized:
            return

        try:
            entity_id = f"{attempt.adapter_name}:{attempt.file_type}"

            # Record time-series data point
            self._ts_store.record_time_series(
                metric_type="adapter_attempt",
                entity_id=entity_id,
                record=attempt.to_dict(),
            )

            # Update effectiveness summary
            eff_key = self._effectiveness_key(attempt.adapter_name, attempt.file_type)
            current = self._ts_store.get(eff_key)
            existing = current.get("value")

            if existing:
                total = existing["total_attempts"] + 1
                successful = existing["successful_attempts"] + (
                    1 if attempt.success else 0
                )
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

            # put() auto-commits
            self._ts_store.put(eff_key, aggregate)

            # Update file type index (track which adapters have data per file type)
            idx_key = self._file_type_index_key(attempt.file_type)
            idx_result = self._ts_store.get(idx_key)
            adapter_names = idx_result.get("value") or []
            if attempt.adapter_name not in adapter_names:
                adapter_names = list(adapter_names)
                adapter_names.append(attempt.adapter_name)
                self._ts_store.put(idx_key, adapter_names)

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
                result = self._ts_store.get(eff_key)
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
            result = self._ts_store.get(eff_key)
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
            idx_result = self._ts_store.get(idx_key)
            adapter_names = idx_result.get("value") or []

            results = []
            for adapter_name in adapter_names:
                eff_key = self._effectiveness_key(adapter_name, file_type)
                result = self._ts_store.get(eff_key)
                eff = result.get("value")

                if eff and eff.get("total_attempts", 0) >= self.min_attempts:
                    results.append((adapter_name, eff["success_rate"]))

            results.sort(key=lambda x: x[1], reverse=True)
            return results[:10]

        except Exception as e:
            logger.error(f"❌ Failed to get best adapters via Dhara: {e}")
            return []

    def is_enabled(self) -> bool:
        return self._initialized


def create_adapter_learner(
    enabled: bool = True,
    db_path: Path | None = None,
    min_attempts: int = 5,
    backend: str = "auto",
) -> AdapterLearnerProtocol:
    if not enabled:
        logger.info("Adapter learning is disabled")
        return NoOpAdapterLearner()

    db_path = db_path or Path(".crackerjack/adapter_learning.db")
    candidate_paths = _adapter_learning_db_candidates(db_path)

    # Try Dhara first when backend is "auto" or "dhara"
    if backend in ("auto", "dhara"):
        for candidate_path in candidate_paths:
            try:
                return DharaAdapterLearner(
                    db_path=candidate_path,
                    min_attempts=min_attempts,
                )
            except Exception as e:
                detail = f": {e}" if str(e) else ""
                logger.warning(f"Dhara backend unavailable at {candidate_path}{detail}")
        if backend == "dhara":
            logger.warning("Dhara backend unavailable, using NoOp as requested")
            return NoOpAdapterLearner()

    # SQLite backend (also auto-fallback)
    for candidate_path in candidate_paths:
        try:
            return SQLiteAdapterLearner(
                db_path=candidate_path,
                min_attempts=min_attempts,
            )
        except Exception as e:
            logger.warning(
                f"SQLite adapter learner unavailable at {candidate_path}: {e}"
            )

    logger.error("Failed to create adapter learner with all candidate paths")
    return NoOpAdapterLearner()


def _adapter_learning_db_candidates(db_path: Path) -> list[Path]:
    candidates = [
        db_path,
        Path.cwd() / ".crackerjack" / db_path.name,
        Path(tempfile.gettempdir()) / "crackerjack" / db_path.name,
    ]
    unique_candidates: list[Path] = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
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

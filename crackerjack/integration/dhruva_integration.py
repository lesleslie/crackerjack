from __future__ import annotations

import json
import logging
import sqlite3
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


def create_adapter_learner(
    enabled: bool = True,
    db_path: Path | None = None,
    min_attempts: int = 5,
) -> AdapterLearnerProtocol:
    if not enabled:
        logger.info("Adapter learning is disabled")
        return NoOpAdapterLearner()

    db_path = db_path or Path(".crackerjack/adapter_learning.db")

    try:
        return SQLiteAdapterLearner(
            db_path=db_path,
            min_attempts=min_attempts,
        )
    except Exception as e:
        logger.error(f"Failed to create adapter learner: {e}")
        return NoOpAdapterLearner()


@dataclass
class DhruvaLearningIntegration:
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

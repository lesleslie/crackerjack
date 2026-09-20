from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import tempfile
import typing as t
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

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
                    datetime.now(UTC).isoformat(),
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
                    datetime.now(UTC).isoformat(),
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
            params: list[t.Any] = [file_type, *candidates, self.min_attempts]
            cursor.execute(
                "SELECT adapter_name, success_rate, total_attempts "
                "FROM adapter_effectiveness "
                "WHERE file_type = ? "
                f"AND adapter_name IN ({placeholders}) "
                "AND total_attempts >= ? "
                "ORDER BY success_rate DESC "
                "LIMIT 1",
                params,
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


def _adapter_learning_db_candidates(db_path: Path) -> list[Path]:
    candidates = [
        db_path,
        Path.cwd() / ".crackerjack" / db_path.name,
        Path(tempfile.gettempdir()) / "crackerjack" / db_path.name,
    ]
    unique_candidates = list(dict.fromkeys(candidates))
    return unique_candidates


# First 16 bytes of every valid SQLite 3.x database file, per
# https://www.sqlite.org/fileformat.html. Reads that don't match this
# header mean the file is something else (the Dhara backend, before it was
# decommissioned 2026-09-20, wrote ``dhara.collections.PersistentDict``
# shelves to ``.crackerjack/adapter_learning.db`` — same filename, very
# different format).
SQLITE_MAGIC_HEADER = b"SQLite format 3\x00"


def _is_valid_sqlite_file(path: Path) -> bool:
    """True iff ``path`` exists, is non-empty, and begins with the SQLite magic header.

    Reads only the first 16 bytes and never invokes ``sqlite3.connect``,
    so it won't acquire a write lock or create ``-journal`` / ``-wal``
    sidecars against a file we may decide to quarantine.
    """
    try:
        if not path.is_file() or path.stat().st_size < 16:
            return False
    except OSError:
        return False
    try:
        with path.open("rb") as f:
            return f.read(16) == SQLITE_MAGIC_HEADER
    except OSError:
        return False


def _quarantine_legacy_file(path: Path) -> Path | None:
    """Move a non-SQLite file at ``path`` aside with a timestamp suffix.

    Returns the new path, or None if ``path`` was already valid SQLite or
    didn't exist. The legacy file is preserved on disk so users can
    inspect it manually; we never destroy user data.

    Uses ``shutil.move`` rather than ``Path.rename`` because the rename
    syscall raises ``OSError(EXDEV)`` when source and destination land on
    different filesystems — and on macOS the temp-dir fallback candidate
    lives on a different APFS volume from ``.crackerjack/``, so a rename
    would re-create the very cross-device crash we're trying to avoid.

    Mirrors the precedence set by
    ``mahavishnu.core.worktree_session_registry.quarantine_corrupt_file``,
    which solved the same problem for its JSON registry.
    """
    if not path.exists():
        return None
    if _is_valid_sqlite_file(path):
        return None
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.legacy-{ts}")
    # If somehow a backup with that exact timestamp already exists
    # (collision window of 1s, only when running the factory twice in
    # the same second), append a counter so we never overwrite the
    # preserved file.
    counter = 0
    while backup.exists():
        counter += 1
        backup = path.with_name(f"{path.name}.legacy-{ts}.{counter}")
    shutil.move(str(path), str(backup))
    logger.info(
        "adapter_learning: moved legacy non-SQLite file aside "
        "(%s → %s); creating fresh SQLite db at original path",
        path.name,
        backup.name,
    )
    return backup


def create_adapter_learner(
    enabled: bool = True,
    db_path: Path | None = None,
    min_attempts: int = 5,
    backend: str = "auto",
) -> AdapterLearnerProtocol:
    """Build an :class:`AdapterLearnerProtocol`.

    With Dhara decommissioned (2026-09-20), the only non-no-op backend is
    SQLite. ``backend="dhara"`` is preserved as a keyword so old config
    files keep loading, but resolves to NoOp (with a warning) so users see
    the deprecation rather than a crash.

    Before attempting SQLite init at each candidate path, the factory
    checks for a legacy non-SQLite file (typically a ``PersistentDict``
    shelf left over from the Dhara backend) and moves it aside with a
    timestamped suffix. This prevents the recurring
    ``file is not a database`` error that would otherwise surface on
    every run for any repo whose ``.crackerjack/adapter_learning.db``
    predates the Dhara→SQLite switch.
    """
    if not enabled:
        logger.info("adapter_learning: disabled, using NoOp")
        return NoOpAdapterLearner()

    if backend == "dhara":
        logger.warning(
            "adapter_learning: backend='dhara' is no longer supported (Dhara "
            "decommissioned 2026-09-20); falling back to NoOp"
        )
        return NoOpAdapterLearner()

    db_path = db_path or Path(".crackerjack/adapter_learning.db")

    for candidate in _adapter_learning_db_candidates(db_path):
        _quarantine_legacy_file(candidate)
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


@dataclass
class AdapterLearningIntegration:
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
            timestamp=datetime.now(UTC),
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

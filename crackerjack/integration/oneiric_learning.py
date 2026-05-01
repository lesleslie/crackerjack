from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DAGExecutionRecord:
    dag_hash: str
    task_ordering: list[str]
    parallelization_strategy: str
    execution_time_ms: int
    success: bool
    resource_usage: dict[str, t.Any]
    conflicts_detected: int
    timestamp: datetime

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "dag_hash": self.dag_hash,
            "task_ordering": self.task_ordering,
            "parallelization_strategy": self.parallelization_strategy,
            "execution_time_ms": self.execution_time_ms,
            "success": self.success,
            "resource_usage": self.resource_usage,
            "conflicts_detected": self.conflicts_detected,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> DAGExecutionRecord:
        return cls(
            dag_hash=data["dag_hash"],
            task_ordering=data["task_ordering"],
            parallelization_strategy=data["parallelization_strategy"],
            execution_time_ms=data["execution_time_ms"],
            success=data["success"],
            resource_usage=data["resource_usage"],
            conflicts_detected=data["conflicts_detected"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass(frozen=True)
class ExecutionStrategy:
    dag_hash: str
    recommended_ordering: list[str]
    recommended_parallelization: dict[str, list[str]]
    expected_time_ms: int
    confidence: float
    reason: str


@t.runtime_checkable
class DAGO_optimizerProtocol(t.Protocol):
    def record_execution(self, record: DAGExecutionRecord) -> None: ...

    def get_optimal_execution_strategy(
        self,
        dag_structure: dict,
        context: dict[str, t.Any],
    ) -> ExecutionStrategy | None: ...

    def learn_task_ordering(
        self,
        dag_hash: str,
        optimal_ordering: list[str],
        performance_improvement: float,
    ) -> None: ...

    def get_execution_history(
        self,
        dag_hash: str,
    ) -> list[DAGExecutionRecord]: ...

    def is_enabled(self) -> bool: ...


@dataclass
class NoOpDAGO_optimizer:
    backend_name: str = "none"

    def record_execution(self, record: DAGExecutionRecord) -> None:
        logger.debug("No-op DAG optimizer: skipping record_execution")

    def get_optimal_execution_strategy(
        self,
        dag_structure: dict,
        context: dict[str, t.Any],
    ) -> ExecutionStrategy | None:
        return None

    def learn_task_ordering(
        self,
        dag_hash: str,
        optimal_ordering: list[str],
        performance_improvement: float,
    ) -> None:
        pass

    def get_execution_history(
        self,
        dag_hash: str,
    ) -> list[DAGExecutionRecord]:
        return []

    def is_enabled(self) -> bool:
        return False


@dataclass
class SQLiteDAGO_optimizer:
    db_path: Path
    min_executions: int = 5
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
                CREATE TABLE IF NOT EXISTS dag_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dag_hash TEXT NOT NULL,
                    task_ordering TEXT NOT NULL,
                    parallelization_strategy TEXT NOT NULL,
                    execution_time_ms INTEGER NOT NULL,
                    success BOOLEAN NOT NULL,
                    resource_usage TEXT NOT NULL,
                    conflicts_detected INTEGER NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS dag_strategies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dag_hash TEXT NOT NULL UNIQUE,
                    recommended_ordering TEXT NOT NULL,
                    recommended_parallelization TEXT NOT NULL,
                    expected_time_ms INTEGER NOT NULL,
                    success_rate REAL NOT NULL,
                    sample_size INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    last_updated TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_dag_hash
                ON dag_executions(dag_hash)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_success
                ON dag_executions(success)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_execution_time
                ON dag_executions(execution_time_ms)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON dag_executions(timestamp DESC)
                """
            )

            conn.commit()
            conn.close()

            self._initialized = True
            logger.info(f"✅ DAG optimizer initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize DAG optimizer: {e}")
            raise

    def _compute_dag_hash(self, dag_structure: dict) -> str:

        normalized = json.dumps(dag_structure, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def record_execution(self, record: DAGExecutionRecord) -> None:
        if not self._initialized:
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO dag_executions (
                    dag_hash, task_ordering, parallelization_strategy,
                    execution_time_ms, success, resource_usage,
                    conflicts_detected, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.dag_hash,
                    json.dumps(record.task_ordering),
                    record.parallelization_strategy,
                    record.execution_time_ms,
                    record.success,
                    json.dumps(record.resource_usage),
                    record.conflicts_detected,
                    record.timestamp.isoformat(),
                ),
            )

            if record.success:
                self._update_optimal_strategy(cursor, record)

            conn.commit()
            conn.close()

            logger.debug(
                f"Recorded DAG execution: {record.dag_hash[:8]}... "
                f"(time={record.execution_time_ms}ms, success={record.success})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to record DAG execution: {e}")

    def _update_optimal_strategy(
        self,
        cursor: sqlite3.Cursor,
        record: DAGExecutionRecord,
    ) -> None:

        cursor.execute(
            """
            SELECT expected_time_ms, success_rate, sample_size
            FROM dag_strategies
            WHERE dag_hash = ?
            """,
            (record.dag_hash,),
        )

        row = cursor.fetchone()

        if row:
            old_time_ms, old_success_rate, old_sample_size = row

            if record.execution_time_ms < old_time_ms:
                new_sample_size = old_sample_size + 1
                new_success_rate = (
                    old_success_rate * old_sample_size + 1.0
                ) / new_sample_size
                confidence = min(new_success_rate, 0.95)

                cursor.execute(
                    """
                    UPDATE dag_strategies
                    SET recommended_ordering = ?,
                        recommended_parallelization = ?,
                        expected_time_ms = ?,
                        success_rate = ?,
                        sample_size = ?,
                        confidence = ?,
                        last_updated = ?
                    WHERE dag_hash = ?
                    """,
                    (
                        json.dumps(record.task_ordering),
                        record.parallelization_strategy,
                        record.execution_time_ms,
                        new_success_rate,
                        new_sample_size,
                        confidence,
                        datetime.now().isoformat(),
                        record.dag_hash,
                    ),
                )
        else:
            cursor.execute(
                """
                INSERT INTO dag_strategies (
                    dag_hash, recommended_ordering, recommended_parallelization,
                    expected_time_ms, success_rate, sample_size,
                    confidence, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.dag_hash,
                    json.dumps(record.task_ordering),
                    record.parallelization_strategy,
                    record.execution_time_ms,
                    1.0,
                    1,
                    0.5,
                    datetime.now().isoformat(),
                ),
            )

    def get_optimal_execution_strategy(
        self,
        dag_structure: dict,
        context: dict[str, t.Any],
    ) -> ExecutionStrategy | None:
        if not self._initialized:
            return None

        try:
            dag_hash = self._compute_dag_hash(dag_structure)

            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT recommended_ordering, recommended_parallelization,
                       expected_time_ms, success_rate, sample_size, confidence
                FROM dag_strategies
                WHERE dag_hash = ?
                AND sample_size >= ?
                """,
                (dag_hash, self.min_executions),
            )

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            (
                ordering_json,
                parallelization_json,
                expected_time_ms,
                success_rate,
                sample_size,
                confidence,
            ) = row

            return ExecutionStrategy(
                dag_hash=dag_hash,
                recommended_ordering=json.loads(ordering_json),
                recommended_parallelization=json.loads(parallelization_json),
                expected_time_ms=expected_time_ms,
                confidence=confidence,
                reason=f"Learned from {sample_size} executions "
                f"with {success_rate:.0%} success rate",
            )

        except Exception as e:
            logger.error(f"❌ Failed to get optimal execution strategy: {e}")
            return None

    def learn_task_ordering(
        self,
        dag_hash: str,
        optimal_ordering: list[str],
        performance_improvement: float,
    ) -> None:
        if not self._initialized:
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT expected_time_ms, success_rate, sample_size
                FROM dag_strategies
                WHERE dag_hash = ?
                """,
                (dag_hash,),
            )

            row = cursor.fetchone()

            if row:
                old_time_ms, old_success_rate, old_sample_size = row
                new_time_ms = int(old_time_ms * (1.0 - performance_improvement))
                new_sample_size = old_sample_size + 1

                cursor.execute(
                    """
                    UPDATE dag_strategies
                    SET recommended_ordering = ?,
                        expected_time_ms = ?,
                        sample_size = ?,
                        confidence = MIN(confidence + 0.1, 0.95),
                        last_updated = ?
                    WHERE dag_hash = ?
                    """,
                    (
                        json.dumps(optimal_ordering),
                        new_time_ms,
                        new_sample_size,
                        datetime.now().isoformat(),
                        dag_hash,
                    ),
                )

            conn.commit()
            conn.close()

            logger.info(
                f"Learned improved task ordering for {dag_hash[:8]}...: "
                f"{performance_improvement:.1%} performance improvement"
            )

        except Exception as e:
            logger.error(f"❌ Failed to learn task ordering: {e}")

    def get_execution_history(
        self,
        dag_hash: str,
    ) -> list[DAGExecutionRecord]:
        if not self._initialized:
            return []

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT dag_hash, task_ordering, parallelization_strategy,
                       execution_time_ms, success, resource_usage,
                       conflicts_detected, timestamp
                FROM dag_executions
                WHERE dag_hash = ?
                ORDER BY timestamp DESC
                LIMIT 100
                """,
                (dag_hash,),
            )

            rows = cursor.fetchall()
            conn.close()

            return [
                DAGExecutionRecord(
                    dag_hash=row[0],
                    task_ordering=json.loads(row[1]),
                    parallelization_strategy=row[2],
                    execution_time_ms=row[3],
                    success=row[4],
                    resource_usage=json.loads(row[5]),
                    conflicts_detected=row[6],
                    timestamp=datetime.fromisoformat(row[7]),
                )
                for row in rows
            ]

        except Exception as e:
            logger.error(f"❌ Failed to get execution history: {e}")
            return []

    def is_enabled(self) -> bool:
        return self._initialized


def create_dag_optimizer(
    enabled: bool = True,
    db_path: Path | None = None,
    min_executions: int = 5,
) -> DAGO_optimizerProtocol:
    if not enabled:
        logger.info("DAG optimization learning is disabled")
        return NoOpDAGO_optimizer()

    db_path = db_path or Path(".crackerjack/dag_learning.db")

    try:
        return SQLiteDAGO_optimizer(
            db_path=db_path,
            min_executions=min_executions,
        )
    except Exception as e:
        logger.error(f"Failed to create DAG optimizer: {e}")
        return NoOpDAGO_optimizer()


@dataclass
class OneiricLearningIntegration:
    dag_optimizer: DAGO_optimizerProtocol
    min_executions: int = 5

    def track_dag_execution(
        self,
        dag_structure: dict,
        task_ordering: list[str],
        parallelization_strategy: str,
        execution_time_ms: int,
        success: bool,
        resource_usage: dict[str, t.Any],
        conflicts_detected: int = 0,
    ) -> None:
        dag_hash = self._compute_dag_hash(dag_structure)

        record = DAGExecutionRecord(
            dag_hash=dag_hash,
            task_ordering=task_ordering,
            parallelization_strategy=parallelization_strategy,
            execution_time_ms=execution_time_ms,
            success=success,
            resource_usage=resource_usage,
            conflicts_detected=conflicts_detected,
            timestamp=datetime.now(),
        )

        self.dag_optimizer.record_execution(record)

    def get_execution_strategy(
        self,
        dag_structure: dict,
        context: dict[str, t.Any],
    ) -> ExecutionStrategy | None:
        return self.dag_optimizer.get_optimal_execution_strategy(
            dag_structure=dag_structure,
            context=context,
        )

    def learn_improved_ordering(
        self,
        dag_structure: dict,
        improved_ordering: list[str],
        baseline_time_ms: int,
        improved_time_ms: int,
    ) -> None:
        dag_hash = self._compute_dag_hash(dag_structure)
        improvement = (baseline_time_ms - improved_time_ms) / baseline_time_ms

        if improvement > 0.05:
            self.dag_optimizer.learn_task_ordering(
                dag_hash=dag_hash,
                optimal_ordering=improved_ordering,
                performance_improvement=improvement,
            )

    def _compute_dag_hash(self, dag_structure: dict) -> str:
        import hashlib

        normalized = json.dumps(dag_structure, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

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
class WorkflowExecutionRecord:
    workflow_id: str
    project_context: dict[str, t.Any]
    execution_strategy: str
    execution_time_ms: int
    success: bool
    quality_score: float
    resource_efficiency: float
    timestamp: datetime

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "workflow_id": self.workflow_id,
            "project_context": self.project_context,
            "execution_strategy": self.execution_strategy,
            "execution_time_ms": self.execution_time_ms,
            "success": self.success,
            "quality_score": self.quality_score,
            "resource_efficiency": self.resource_efficiency,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> WorkflowExecutionRecord:
        return cls(
            workflow_id=data["workflow_id"],
            project_context=data["project_context"],
            execution_strategy=data["execution_strategy"],
            execution_time_ms=data["execution_time_ms"],
            success=data["success"],
            quality_score=data["quality_score"],
            resource_efficiency=data["resource_efficiency"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass(frozen=True)
class WorkflowRecommendation:
    workflow_id: str
    recommended_strategy: str
    expected_quality_score: float
    expected_execution_time_ms: int
    confidence: float
    reason: str
    similar_projects: list[str]


@dataclass(frozen=True)
class WorkflowEffectiveness:
    workflow_id: str
    execution_strategy: str
    total_executions: int
    successful_executions: int
    success_rate: float
    avg_quality_score: float
    avg_execution_time_ms: float
    avg_resource_efficiency: float
    best_project_contexts: list[dict[str, t.Any]]
    worst_project_contexts: list[dict[str, t.Any]]
    last_executed: datetime | None


@t.runtime_checkable
class WorkflowLearnerProtocol(t.Protocol):
    def record_workflow_execution(self, record: WorkflowExecutionRecord) -> None: ...

    def recommend_workflow(
        self,
        project_metrics: dict[str, t.Any],
        available_workflows: list[str],
    ) -> WorkflowRecommendation | None: ...

    def get_workflow_effectiveness(
        self,
        workflow_id: str,
        execution_strategy: str,
    ) -> WorkflowEffectiveness | None: ...

    def get_best_strategies_for_workflow(
        self,
        workflow_id: str,
    ) -> list[tuple[str, float]]: ...

    def is_enabled(self) -> bool: ...


@dataclass
class NoOpWorkflowLearner:
    backend_name: str = "none"

    def record_workflow_execution(self, record: WorkflowExecutionRecord) -> None:
        logger.debug("No-op workflow learner: skipping record_workflow_execution")

    def recommend_workflow(
        self,
        project_metrics: dict[str, t.Any],
        available_workflows: list[str],
    ) -> WorkflowRecommendation | None:
        return None

    def get_workflow_effectiveness(
        self,
        workflow_id: str,
        execution_strategy: str,
    ) -> WorkflowEffectiveness | None:
        return None

    def get_best_strategies_for_workflow(
        self,
        workflow_id: str,
    ) -> list[tuple[str, float]]:
        return []

    def is_enabled(self) -> bool:
        return False


@dataclass
class SQLiteWorkflowLearner:
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
                CREATE TABLE IF NOT EXISTS workflow_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    project_context TEXT NOT NULL,
                    execution_strategy TEXT NOT NULL,
                    execution_time_ms INTEGER NOT NULL,
                    success BOOLEAN NOT NULL,
                    quality_score REAL NOT NULL,
                    resource_efficiency REAL NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_effectiveness (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workflow_id TEXT NOT NULL,
                    execution_strategy TEXT NOT NULL UNIQUE,
                    total_executions INTEGER DEFAULT 0,
                    successful_executions INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    avg_quality_score REAL DEFAULT 0.0,
                    avg_execution_time_ms REAL DEFAULT 0.0,
                    avg_resource_efficiency REAL DEFAULT 0.0,
                    best_contexts TEXT NOT NULL,
                    worst_contexts TEXT NOT NULL,
                    last_executed TEXT,
                    last_updated TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_strategy
                ON workflow_executions(workflow_id, execution_strategy)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_workflow_id
                ON workflow_executions(workflow_id)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_success
                ON workflow_executions(success)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON workflow_executions(timestamp DESC)
                """
            )

            conn.commit()
            conn.close()

            self._initialized = True
            logger.info(f"✅ Workflow learner initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize workflow learner: {e}")
            raise

    def record_workflow_execution(self, record: WorkflowExecutionRecord) -> None:
        if not self._initialized:
            return

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO workflow_executions (
                    workflow_id, project_context, execution_strategy,
                    execution_time_ms, success, quality_score,
                    resource_efficiency, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.workflow_id,
                    json.dumps(record.project_context),
                    record.execution_strategy,
                    record.execution_time_ms,
                    record.success,
                    record.quality_score,
                    record.resource_efficiency,
                    record.timestamp.isoformat(),
                ),
            )

            if record.success:
                self._update_effectiveness_metrics(cursor, record)

            conn.commit()
            conn.close()

            logger.debug(
                f"Recorded workflow execution: {record.workflow_id} "
                f"(strategy={record.execution_strategy}, success={record.success})"
            )

        except Exception as e:
            logger.error(f"❌ Failed to record workflow execution: {e}")

    def _update_effectiveness_metrics(
        self,
        cursor: sqlite3.Cursor,
        record: WorkflowExecutionRecord,
    ) -> None:
        key = (record.workflow_id, record.execution_strategy)

        cursor.execute(
            """
            SELECT total_executions, successful_executions,
                   avg_quality_score, avg_execution_time_ms, avg_resource_efficiency,
                   best_contexts, worst_contexts
            FROM workflow_effectiveness
            WHERE workflow_id = ? AND execution_strategy = ?
            """,
            key,
        )

        row = cursor.fetchone()

        if row:
            (
                total_executions,
                successful_executions,
                avg_quality,
                avg_time,
                avg_efficiency,
                best_contexts_json,
                worst_contexts_json,
            ) = row

            new_total = total_executions + 1
            new_successful = successful_executions + 1
            new_success_rate = new_successful / new_total if new_total > 0 else 0.0

            new_avg_quality = (
                avg_quality * total_executions + record.quality_score
            ) / new_total
            new_avg_time = (
                avg_time * total_executions + record.execution_time_ms
            ) / new_total
            new_avg_efficiency = (
                avg_efficiency * total_executions + record.resource_efficiency
            ) / new_total

            best_contexts = json.loads(best_contexts_json)
            worst_contexts = json.loads(worst_contexts_json)

            if record.quality_score > 0.8:
                best_contexts.append(record.project_context)

                best_contexts.sort(key=lambda c: c.get("health_score", 0), reverse=True)
                best_contexts = best_contexts[:3]

            if record.quality_score < 0.5:
                worst_contexts.append(record.project_context)

                worst_contexts.sort(key=lambda c: c.get("health_score", 0))
                worst_contexts = worst_contexts[:3]

            cursor.execute(
                """
                UPDATE workflow_effectiveness
                SET total_executions = ?,
                    successful_executions = ?,
                    success_rate = ?,
                    avg_quality_score = ?,
                    avg_execution_time_ms = ?,
                    avg_resource_efficiency = ?,
                    best_contexts = ?,
                    worst_contexts = ?,
                    last_executed = ?,
                    last_updated = ?
                WHERE workflow_id = ? AND execution_strategy = ?
                """,
                (
                    new_total,
                    new_successful,
                    new_success_rate,
                    new_avg_quality,
                    new_avg_time,
                    new_avg_efficiency,
                    json.dumps(best_contexts),
                    json.dumps(worst_contexts),
                    record.timestamp.isoformat(),
                    datetime.now().isoformat(),
                    record.workflow_id,
                    record.execution_strategy,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO workflow_effectiveness (
                    workflow_id, execution_strategy, total_executions,
                    successful_executions, success_rate, avg_quality_score,
                    avg_execution_time_ms, avg_resource_efficiency,
                    best_contexts, worst_contexts, last_executed, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.workflow_id,
                    record.execution_strategy,
                    1,
                    1,
                    1.0,
                    record.quality_score,
                    record.execution_time_ms,
                    record.resource_efficiency,
                    json.dumps(
                        [record.project_context] if record.quality_score > 0.8 else []
                    ),
                    json.dumps(
                        [record.project_context] if record.quality_score < 0.5 else []
                    ),
                    record.timestamp.isoformat(),
                    datetime.now().isoformat(),
                ),
            )

    def recommend_workflow(
        self,
        project_metrics: dict[str, t.Any],
        available_workflows: list[str],
    ) -> WorkflowRecommendation | None:
        if not self._initialized:
            return None

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            placeholders = ",".join(["?"] * len(available_workflows))

            cursor.execute(
                f"""
                SELECT
                    workflow_id, execution_strategy,
                    avg_quality_score, avg_execution_time_ms,
                    success_rate, project_context
                FROM workflow_executions
                WHERE workflow_id IN ({placeholders})
                AND success = 1
                ORDER BY timestamp DESC
                LIMIT 100
                """,
                available_workflows,
            )

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return None

            workflow_scores: dict[str, list[tuple[float, dict]]] = {}

            for row in rows:
                (
                    workflow_id,
                    strategy,
                    quality_score,
                    execution_time,
                    success_rate,
                    context_json,
                ) = row

                context = json.loads(context_json)
                similarity = self._calculate_project_similarity(
                    project_metrics, context
                )

                combined_score = quality_score * success_rate * (1.0 + similarity)

                key = f"{workflow_id}:{strategy}"
                if key not in workflow_scores:
                    workflow_scores[key] = []
                workflow_scores[key].append((combined_score, context))

            best_key = max(
                workflow_scores.keys(),
                key=lambda k: np.mean([s[0] for s in workflow_scores[k]]),
            )
            best_scores = workflow_scores[best_key]
            workflow_id, strategy = best_key.split(":")

            avg_quality = np.mean(
                [row[2] for row in rows if row[0] == workflow_id and row[1] == strategy]
            )
            avg_time = int(
                np.mean(
                    [
                        row[3]
                        for row in rows
                        if row[0] == workflow_id and row[1] == strategy
                    ]
                )
            )
            confidence = min(len(best_scores) / 10.0, 1.0)
            similar_projects = [
                s[1].get("repository_name", "unknown") for s in best_scores[:3]
            ]

            return WorkflowRecommendation(
                workflow_id=workflow_id,
                recommended_strategy=strategy,
                expected_quality_score=float(avg_quality),
                expected_execution_time_ms=avg_time,
                confidence=confidence,
                reason=f"Similar to {len(best_scores)} successful projects "
                f"with {avg_quality:.1%} average quality",
                similar_projects=similar_projects,
            )

        except Exception as e:
            logger.error(f"❌ Failed to recommend workflow: {e}")
            return None

    def _calculate_project_similarity(
        self,
        context1: dict[str, t.Any],
        context2: dict[str, t.Any],
    ) -> float:
        matches = 0
        total_keys = 0

        for key in set(context1.keys()) | set(context2.keys()):
            total_keys += 1
            val1 = context1.get(key)
            val2 = context2.get(key)

            if val1 == val2:
                matches += 1

            elif isinstance(val1, (int, float)) and isinstance(val2, (int, float)):
                diff = abs(val1 - val2)
                max_val = max(abs(val1), abs(val2), 1)
                if diff / max_val < 0.2:
                    matches += 0.5

        return matches / total_keys if total_keys > 0 else 0.0

    def get_workflow_effectiveness(
        self,
        workflow_id: str,
        execution_strategy: str,
    ) -> WorkflowEffectiveness | None:
        if not self._initialized:
            return None

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT total_executions, successful_executions, success_rate,
                       avg_quality_score, avg_execution_time_ms, avg_resource_efficiency,
                       best_contexts, worst_contexts, last_executed
                FROM workflow_effectiveness
                WHERE workflow_id = ? AND execution_strategy = ?
                """,
                (workflow_id, execution_strategy),
            )

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            (
                total_executions,
                successful_executions,
                success_rate,
                avg_quality,
                avg_time,
                avg_efficiency,
                best_contexts_json,
                worst_contexts_json,
                last_executed,
            ) = row

            return WorkflowEffectiveness(
                workflow_id=workflow_id,
                execution_strategy=execution_strategy,
                total_executions=total_executions,
                successful_executions=successful_executions,
                success_rate=success_rate,
                avg_quality_score=avg_quality,
                avg_execution_time_ms=avg_time,
                avg_resource_efficiency=avg_efficiency,
                best_contexts=json.loads(best_contexts_json),
                worst_contexts=json.loads(worst_contexts_json),
                last_executed=datetime.fromisoformat(last_executed)
                if last_executed
                else None,
            )

        except Exception as e:
            logger.error(f"❌ Failed to get workflow effectiveness: {e}")
            return None

    def get_best_strategies_for_workflow(
        self,
        workflow_id: str,
    ) -> list[tuple[str, float]]:
        if not self._initialized:
            return []

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT execution_strategy, success_rate, avg_quality_score
                FROM workflow_effectiveness
                WHERE workflow_id = ?
                AND total_executions >= ?
                ORDER BY success_rate DESC, avg_quality_score DESC
                LIMIT 10
                """,
                (workflow_id, self.min_executions),
            )

            rows = cursor.fetchall()
            conn.close()

            strategies = []
            for row in rows:
                strategy, success_rate, quality_score = row
                effectiveness = success_rate * quality_score
                strategies.append((strategy, effectiveness))

            return strategies

        except Exception as e:
            logger.error(f"❌ Failed to get best strategies: {e}")
            return []

    def is_enabled(self) -> bool:
        return self._initialized


import numpy as np


def create_workflow_learner(
    enabled: bool = True,
    db_path: Path | None = None,
    min_executions: int = 5,
) -> WorkflowLearnerProtocol:
    if not enabled:
        logger.info("Workflow learning is disabled")
        return NoOpWorkflowLearner()

    db_path = db_path or Path(".crackerjack/workflow_learning.db")

    try:
        return SQLiteWorkflowLearner(
            db_path=db_path,
            min_executions=min_executions,
        )
    except Exception as e:
        logger.error(f"Failed to create workflow learner: {e}")
        return NoOpWorkflowLearner()


@dataclass
class MahavishnuLearningIntegration:
    workflow_learner: WorkflowLearnerProtocol
    min_executions: int = 5

    def track_workflow_execution(
        self,
        workflow_id: str,
        project_context: dict[str, t.Any],
        execution_strategy: str,
        execution_time_ms: int,
        success: bool,
        quality_score: float = 0.8,
        resource_efficiency: float = 0.8,
    ) -> None:
        record = WorkflowExecutionRecord(
            workflow_id=workflow_id,
            project_context=project_context,
            execution_strategy=execution_strategy,
            execution_time_ms=execution_time_ms,
            success=success,
            quality_score=quality_score,
            resource_efficiency=resource_efficiency,
            timestamp=datetime.now(),
        )

        self.workflow_learner.record_workflow_execution(record)

    def get_workflow_recommendation(
        self,
        project_metrics: dict[str, t.Any],
        available_workflows: list[str],
    ) -> WorkflowRecommendation | None:
        return self.workflow_learner.recommend_workflow(
            project_metrics=project_metrics,
            available_workflows=available_workflows,
        )

    def get_workflow_stats(
        self,
        workflow_id: str,
        execution_strategy: str,
    ) -> WorkflowEffectiveness | None:
        return self.workflow_learner.get_workflow_effectiveness(
            workflow_id=workflow_id,
            execution_strategy=execution_strategy,
        )

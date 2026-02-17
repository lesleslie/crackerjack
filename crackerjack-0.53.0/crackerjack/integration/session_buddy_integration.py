from __future__ import annotations

import logging
import sqlite3
import typing as t
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitVelocityMetrics:
    commit_velocity_per_hour: float
    commit_velocity_per_day: float
    conventional_compliance_rate: float
    breaking_change_count: int
    avg_commits_per_week: float
    most_active_hour: int
    most_active_day: int
    total_commits: int
    period_start: datetime
    period_end: datetime


@dataclass(frozen=True)
class ExtendedSessionMetrics:
    session_id: str
    project_path: str
    started_at: datetime
    ended_at: datetime | None
    duration_minutes: float | None
    checkpoint_count: int
    commit_count: int
    quality_start: float
    quality_end: float
    quality_delta: float
    avg_quality: float
    files_modified: int
    tools_used: list[str]
    primary_language: str | None
    time_of_day: str

    git_velocity_per_hour: float | None = None
    git_velocity_per_day: float | None = None
    git_conventional_compliance: float | None = None
    git_breaking_changes: int | None = None
    git_avg_commits_per_week: float | None = None
    git_most_active_hour: int | None = None
    git_most_active_day: int | None = None

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "session_id": self.session_id,
            "project_path": self.project_path,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_minutes": self.duration_minutes,
            "checkpoint_count": self.checkpoint_count,
            "commit_count": self.commit_count,
            "quality_start": self.quality_start,
            "quality_end": self.quality_end,
            "quality_delta": self.quality_delta,
            "avg_quality": self.avg_quality,
            "files_modified": self.files_modified,
            "tools_used": self.tools_used,
            "primary_language": self.primary_language,
            "time_of_day": self.time_of_day,
            "git_velocity_per_hour": self.git_velocity_per_hour,
            "git_velocity_per_day": self.git_velocity_per_day,
            "git_conventional_compliance": self.git_conventional_compliance,
            "git_breaking_changes": self.git_breaking_changes,
            "git_avg_commits_per_week": self.git_avg_commits_per_week,
            "git_most_active_hour": self.git_most_active_hour,
            "git_most_active_day": self.git_most_active_day,
        }


@dataclass
class CorrelationInsight:
    correlation_type: str
    correlation_coefficient: float
    strength: str
    direction: str
    description: str
    confidence: float
    sample_size: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@runtime_checkable
class GitMetricsReader(Protocol):
    def get_metrics(
        self,
        repository_path: str,
        metric_types: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[t.Any]: ...

    def get_latest_metrics(self, repository_path: str) -> dict[str, t.Any]: ...


@runtime_checkable
class SessionBuddyClient(Protocol):
    async def get_session_metrics(
        self,
        session_id: str | None = None,
        project_path: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Sequence[t.Any]: ...

    async def get_workflow_metrics(
        self,
        project_path: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> t.Any: ...


@runtime_checkable
class CorrelationStorage(Protocol):
    async def store_insight(self, insight: CorrelationInsight) -> None: ...

    async def get_insights(
        self,
        project_path: str | None = None,
        since: datetime | None = None,
    ) -> list[CorrelationInsight]: ...


class NoOpGitMetricsReader:
    def get_metrics(
        self,
        repository_path: str,
        metric_types: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[t.Any]:
        return []

    def get_latest_metrics(self, repository_path: str) -> dict[str, t.Any]:
        return {}


class NoOpSessionBuddyClient:
    async def get_session_metrics(
        self,
        session_id: str | None = None,
        project_path: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Sequence[t.Any]:
        return []

    async def get_workflow_metrics(
        self,
        project_path: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> t.Any:
        return None


class NoOpCorrelationStorage:
    async def store_insight(self, insight: CorrelationInsight) -> None:
        logger.debug(f"No-op storage: would store insight {insight.correlation_type}")

    async def get_insights(
        self,
        project_path: str | None = None,
        since: datetime | None = None,
    ) -> list[CorrelationInsight]:
        return []


class SessionBuddyIntegration:
    def __init__(
        self,
        git_metrics_reader: GitMetricsReader | None = None,
        session_buddy_client: SessionBuddyClient | None = None,
        correlation_storage: CorrelationStorage | None = None,
    ) -> None:
        self.git_reader = git_metrics_reader or NoOpGitMetricsReader()
        self.session_buddy = session_buddy_client or NoOpSessionBuddyClient()
        self.storage = correlation_storage or NoOpCorrelationStorage()

        logger.info("Session-buddy integration initialized")

    async def collect_extended_session_metrics(
        self,
        session_id: str,
        project_path: str,
    ) -> ExtendedSessionMetrics | None:

        sessions = await self.session_buddy.get_session_metrics(
            session_id=session_id,
            project_path=project_path,
        )

        if not sessions:
            logger.warning(f"No session found: {session_id}")
            return None

        session_data = sessions[0]

        start_dt = (
            datetime.fromisoformat(session_data["started_at"])
            if session_data.get("started_at")
            else None
        )
        end_dt = (
            datetime.fromisoformat(session_data["ended_at"])
            if session_data.get("ended_at")
            else None
        )

        git_metrics = await self._load_git_metrics(
            repository_path=project_path,
            start_date=start_dt,
            end_date=end_dt,
        )

        extended = ExtendedSessionMetrics(
            session_id=session_data["session_id"],
            project_path=session_data["project_path"],
            started_at=datetime.fromisoformat(session_data["started_at"]),
            ended_at=(
                datetime.fromisoformat(session_data["ended_at"])
                if session_data.get("ended_at")
                else None
            ),
            duration_minutes=session_data.get("duration_minutes"),
            checkpoint_count=session_data.get("checkpoint_count", 0),
            commit_count=session_data.get("commit_count", 0),
            quality_start=session_data.get("quality_start", 0.0),
            quality_end=session_data.get("quality_end", 0.0),
            quality_delta=session_data.get("quality_delta", 0.0),
            avg_quality=session_data.get("avg_quality", 0.0),
            files_modified=session_data.get("files_modified", 0),
            tools_used=session_data.get("tools_used", []),
            primary_language=session_data.get("primary_language"),
            time_of_day=session_data.get("time_of_day", "unknown"),
            git_velocity_per_hour=git_metrics.get("velocity_per_hour")
            if git_metrics
            else None,
            git_velocity_per_day=git_metrics.get("velocity_per_day")
            if git_metrics
            else None,
            git_conventional_compliance=git_metrics.get("conventional_compliance")
            if git_metrics
            else None,
            git_breaking_changes=git_metrics.get("breaking_changes")
            if git_metrics
            else None,
            git_avg_commits_per_week=git_metrics.get("avg_commits_per_week")
            if git_metrics
            else None,
            git_most_active_hour=git_metrics.get("most_active_hour")
            if git_metrics
            else None,
            git_most_active_day=git_metrics.get("most_active_day")
            if git_metrics
            else None,
        )

        logger.debug(f"Extended session metrics: {session_id}")
        return extended

    async def calculate_correlations(
        self,
        project_path: str,
        days_back: int = 30,
    ) -> list[CorrelationInsight]:
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days_back)

        workflow = await self.session_buddy.get_workflow_metrics(
            project_path=project_path,
            start_date=start_date,
            end_date=end_date,
        )

        if not workflow:
            logger.warning(f"No workflow metrics found for {project_path}")
            return []

        git_metrics_list = self.git_reader.get_metrics(
            repository_path=project_path,
            since=start_date,
            until=end_date,
        )

        if not git_metrics_list:
            logger.warning(f"No git metrics found for {project_path}")
            return []

        insights: list[CorrelationInsight] = []

        velocity_quality_insight = self._calculate_quality_velocity_correlation(
            workflow_metrics=workflow,
            git_metrics=git_metrics_list,
        )
        if velocity_quality_insight:
            insights.append(velocity_quality_insight)

        conventional_insight = self._calculate_conventional_quality_correlation(
            workflow_metrics=workflow,
            git_metrics=git_metrics_list,
        )
        if conventional_insight:
            insights.append(conventional_insight)

        for insight in insights:
            await self.storage.store_insight(insight)

        logger.info(f"Generated {len(insights)} correlation insights")
        return insights

    async def _load_git_metrics(
        self,
        repository_path: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, t.Any] | None:
        try:
            metrics = self.git_reader.get_metrics(
                repository_path=repository_path,
                since=start_date,
                until=end_date,
            )

            if not metrics:
                return None

            return {
                "velocity_per_hour": self._average_metric(
                    metrics, "commit_velocity_per_hour"
                ),
                "velocity_per_day": self._average_metric(
                    metrics, "commit_velocity_per_day"
                ),
                "conventional_compliance": self._average_metric(
                    metrics, "conventional_compliance_rate"
                ),
                "breaking_changes": sum(
                    m.get("value", 0)
                    for m in metrics
                    if m.get("metric_type") == "breaking_changes"
                ),
                "avg_commits_per_week": self._average_metric(
                    metrics, "avg_commits_per_week"
                ),
                "most_active_hour": self._mode_metric(metrics, "most_active_hour"),
                "most_active_day": self._mode_metric(metrics, "most_active_day"),
            }

        except Exception as e:
            logger.error(f"Failed to load git metrics: {e}")
            return None

    def _average_metric(self, metrics: list[t.Any], metric_type: str) -> float | None:
        values = [
            m.get("value", 0) for m in metrics if m.get("metric_type") == metric_type
        ]

        if not values:
            return None

        return sum(values) / len(values)

    def _mode_metric(self, metrics: list[t.Any], metric_type: str) -> int | None:
        values = [
            m.get("value", 0) for m in metrics if m.get("metric_type") == metric_type
        ]

        if not values:
            return None

        from collections import Counter

        counter = Counter(int(v) for v in values)
        return counter.most_common(1)[0][0] if counter else None

    def _calculate_quality_velocity_correlation(
        self,
        workflow_metrics: t.Any,
        git_metrics: list[t.Any],
    ) -> CorrelationInsight | None:
        try:
            quality_trend = getattr(workflow_metrics, "quality_trend", "stable")
            getattr(workflow_metrics, "avg_quality_score", 0.0)

            velocity_values = [
                m.get("value", 0)
                for m in git_metrics
                if m.get("metric_type")
                in ("commit_velocity_per_hour", "commit_velocity_per_day")
            ]

            if not velocity_values:
                return None

            avg_velocity = sum(velocity_values) / len(velocity_values)

            correlation = 0.0

            if quality_trend == "improving" and avg_velocity > 1.0:
                correlation = 0.6
            elif quality_trend == "declining" and avg_velocity > 1.0:
                correlation = -0.4
            else:
                correlation = 0.1

            return CorrelationInsight(
                correlation_type="quality_vs_velocity",
                correlation_coefficient=correlation,
                strength=self._classify_strength(abs(correlation)),
                direction=self._classify_direction(correlation),
                description=f"Quality trend is '{quality_trend}' with avg velocity {avg_velocity:.2f} commits/hour",
                confidence=0.7 if len(git_metrics) > 5 else 0.4,
                sample_size=len(git_metrics),
            )

        except Exception as e:
            logger.warning(f"Failed to calculate quality-velocity correlation: {e}")
            return None

    def _calculate_conventional_quality_correlation(
        self,
        workflow_metrics: t.Any,
        git_metrics: list[t.Any],
    ) -> CorrelationInsight | None:
        try:
            avg_quality = getattr(workflow_metrics, "avg_quality_score", 0.0)

            compliance_values = [
                m.get("value", 0)
                for m in git_metrics
                if m.get("metric_type") == "conventional_compliance_rate"
            ]

            if not compliance_values:
                return None

            avg_compliance = sum(compliance_values) / len(compliance_values)

            correlation = (avg_compliance / 100.0) * (avg_quality / 100.0)

            return CorrelationInsight(
                correlation_type="conventional_vs_quality",
                correlation_coefficient=correlation,
                strength=self._classify_strength(abs(correlation)),
                direction=self._classify_direction(correlation),
                description=f"Conventional compliance {avg_compliance:.1f}% vs quality {avg_quality:.1f}",
                confidence=0.6 if len(git_metrics) > 3 else 0.3,
                sample_size=len(git_metrics),
            )

        except Exception as e:
            logger.warning(f"Failed to calculate conventional-quality correlation: {e}")
            return None

    def _classify_strength(self, correlation: float) -> str:
        if correlation >= 0.7:
            return "strong"
        elif correlation >= 0.4:
            return "moderate"
        elif correlation >= 0.2:
            return "weak"
        return "none"

    def _classify_direction(self, correlation: float) -> str:
        if correlation > 0.1:
            return "positive"
        elif correlation < -0.1:
            return "negative"
        return "neutral"


class SessionBuddyDirectClient:
    def __init__(self, db_path: str = "~/.claude/data/workflow_metrics.db") -> None:
        import os

        self.db_path = os.path.expanduser(db_path)
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            import os

            db_exists = os.path.exists(self.db_path)

            if not db_exists:
                import sqlite3

                self._conn = sqlite3.connect(":memory:")
                self._conn.row_factory = sqlite3.Row
                return self._conn

            try:
                import duckdb

                self._conn = duckdb.connect(self.db_path)  # type: ignore[attr-defined]
            except ImportError:
                self._conn = sqlite3.connect(self.db_path)
                self._conn.row_factory = sqlite3.Row

        return self._conn

    async def get_session_metrics(
        self,
        session_id: str | None = None,
        project_path: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Sequence[t.Any]:
        conn = self._get_conn()

        where_clauses = []
        params: list[t.Any] = []

        if session_id:
            where_clauses.append("session_id = ?")
            params.append(session_id)

        if project_path:
            where_clauses.append("project_path = ?")
            params.append(project_path)

        if start_date:
            where_clauses.append("started_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            where_clauses.append("started_at <= ?")
            params.append(end_date.isoformat())

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        query = f"""
            SELECT * FROM session_metrics
            {where_sql}
            ORDER BY started_at DESC
        """

        try:
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            result = []
            for row in rows:
                if isinstance(row, tuple):
                    columns = [desc[0] for desc in cursor.description]
                    result.append(dict(zip(columns, row)))
                else:
                    result.append(dict(row))
            return result

        except Exception as e:
            logger.error(f"Failed to get session metrics: {e}")
            return []

    async def get_workflow_metrics(
        self,
        project_path: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> t.Any:

        try:
            from session_buddy.core.workflow_metrics import WorkflowMetricsStore

            store = WorkflowMetricsStore(db_path=self.db_path)
            return await store.get_workflow_metrics(
                project_path=project_path,
                start_date=start_date,
                end_date=end_date,
            )

        except ImportError:
            logger.debug("WorkflowMetricsStore not available")
            return None

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


class CorrelationStorageSQLite:
    def __init__(
        self, db_path: str | Path = "~/.claude/data/correlation_insights.db"
    ) -> None:
        import os

        self.db_path = Path(os.path.expanduser(db_path))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn: sqlite3.Connection | None = None
        self._initialize_db()

    def _initialize_db(self) -> None:
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS correlation_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                correlation_type TEXT NOT NULL,
                correlation_coefficient REAL NOT NULL,
                strength TEXT NOT NULL,
                direction TEXT NOT NULL,
                description TEXT,
                confidence REAL NOT NULL,
                sample_size INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                project_path TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_insights_type
            ON correlation_insights(correlation_type)
        """)

        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_insights_timestamp
            ON correlation_insights(timestamp DESC)
        """)

        self.conn.commit()
        logger.info(f"Correlation insights storage initialized: {self.db_path}")

    async def store_insight(self, insight: CorrelationInsight) -> None:
        if not self.conn:
            return

        try:
            self.conn.execute(
                """
                INSERT INTO correlation_insights (
                    correlation_type, correlation_coefficient, strength, direction,
                    description, confidence, sample_size, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    insight.correlation_type,
                    insight.correlation_coefficient,
                    insight.strength,
                    insight.direction,
                    insight.description,
                    insight.confidence,
                    insight.sample_size,
                    insight.timestamp.isoformat(),
                ),
            )
            self.conn.commit()

            logger.debug(f"Stored insight: {insight.correlation_type}")

        except Exception as e:
            logger.error(f"Failed to store insight: {e}")

    async def get_insights(
        self,
        project_path: str | None = None,
        since: datetime | None = None,
    ) -> list[CorrelationInsight]:
        if not self.conn:
            return []

        try:
            where_clauses = []
            params: list[t.Any] = []

            if project_path:
                where_clauses.append("project_path = ?")
                params.append(project_path)

            if since:
                where_clauses.append("timestamp >= ?")
                params.append(since.isoformat())

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            query = f"""
                SELECT * FROM correlation_insights
                {where_sql}
                ORDER BY timestamp DESC
                LIMIT 100
            """

            cursor = self.conn.execute(query, params)
            rows = cursor.fetchall()

            return [
                CorrelationInsight(
                    correlation_type=row["correlation_type"],
                    correlation_coefficient=row["correlation_coefficient"],
                    strength=row["strength"],
                    direction=row["direction"],
                    description=row["description"],
                    confidence=row["confidence"],
                    sample_size=row["sample_size"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                )
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to get insights: {e}")
            return []

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None


def create_session_buddy_integration(
    git_metrics_reader: GitMetricsReader | None = None,
    db_path: str = "~/.claude/data/workflow_metrics.db",
    insights_db_path: str = "~/.claude/data/correlation_insights.db",
) -> SessionBuddyIntegration:

    session_buddy_client = SessionBuddyDirectClient(db_path=db_path)

    correlation_storage = CorrelationStorageSQLite(db_path=insights_db_path)

    return SessionBuddyIntegration(
        git_metrics_reader=git_metrics_reader,
        session_buddy_client=session_buddy_client,
        correlation_storage=correlation_storage,
    )

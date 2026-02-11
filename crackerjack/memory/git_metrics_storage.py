import logging
import sqlite3
import typing as t
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class GitMetric:
    repository_path: str
    metric_type: str
    value: float
    metadata: str | None = None
    timestamp: datetime


class GitMetricsStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn: sqlite3.Connection(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            schema_path = Path(__file__).parent / "git_metrics_schema.sql"
            if schema_path.exists():
                schema_sql = schema_path.read_text(encoding="utf-8")
                self.conn.executescript(schema_sql)
                self.conn.commit()
                logger.info(f"✅ Git metrics storage initialized: {self.db_path}")
            else:
                logger.error(f"Schema file not found: {schema_path}")
                raise FileNotFoundError(f"Schema file not found: {schema_path}")

        except Exception as e:
            logger.error(f"❌ Failed to initialize git metrics storage: {e}")
            raise

    def store_metric(
        self,
        repository_path: str,
        metric_type: str,
        value: float,
        metadata: str | None = None,
        timestamp: datetime | None = None,
    ) -> None:
        if timestamp is None:
            timestamp = datetime.now()

        try:
            self.conn.execute(
                """
                INSERT INTO git_metrics (repository_path, metric_type, value, metadata, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (repository_path, metric_type, value, metadata, timestamp.isoformat()),
            )
            self.conn.commit()
            logger.debug(
                f"Stored metric: {metric_type}={value:.4f} for {repository_path}"
            )

        except Exception as e:
            logger.error(f"Failed to store metric: {e}")

    def log_event(
        self,
        repository_path: str,
        event_type: str,
        details: str,
        timestamp: datetime | None = None,
    ) -> None:
        if timestamp is None:
            timestamp = datetime.now()

        try:
            self.conn.execute(
                """
                INSERT INTO git_events (repository_path, event_type, details, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (repository_path, event_type, details, timestamp.isoformat()),
            )
            self.conn.commit()
            logger.debug(f"Logged event: {event_type} for {repository_path}")

        except Exception as e:
            logger.error(f"Failed to log event: {e}")

    def get_metrics(
        self,
        repository_path: str,
        metric_types: list[str] | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[GitMetric]:
        try:
            query = "SELECT * FROM git_metrics WHERE repository_path = ?"
            params: [repository_path]

            if metric_types:
                placeholders = ", ".join(["?"] * len(metric_types))
                query += f" AND metric_type IN ({placeholders})"
                params.extend(metric_types)

            if since:
                query += " AND timestamp >= ?"
                params.append(since.isoformat())

            if until:
                query += " AND timestamp <= ?"
                params.append(until.isoformat())

            query += " ORDER BY timestamp DESC"

            cursor = self.conn.execute(query, params)
            rows = cursor.fetchall()

            return [
                GitMetric(
                    repository_path=row["repository_path"],
                    metric_type=row["metric_type"],
                    value=row["value"],
                    metadata=row.get("metadata"),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                )
                for row in rows
            ]

        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return []

    def get_latest_metrics(self, repository_path: str) -> dict[str, GitMetric]:
        try:
            cursor = self.conn.execute(
                """
                SELECT metric_type, value, metadata, timestamp
                FROM v_git_metrics_latest
                WHERE repository_path = ?
                """,
                (repository_path,),
            )
            rows = cursor.fetchall()

            return {
                row["metric_type"]: GitMetric(
                    repository_path=repository_path,
                    metric_type=row["metric_type"],
                    value=row["value"],
                    metadata=row.get("metadata"),
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                )
                for row in rows
            }

        except Exception as e:
            logger.error(f"Failed to get latest metrics: {e}")
            return {}

    def get_velocity_dashboard(
        self, repository_path: str, days_back: int = 30
    ) -> dict[str, t.Any]:
        since = datetime.now() - timedelta(days=days_back)

        try:
            cursor = self.conn.execute(
                """
                SELECT
                    metric_type,
                    COUNT(*) as count,
                    AVG(value) as avg_value,
                    MIN(timestamp) as first_timestamp,
                    MAX(timestamp) as last_timestamp
                FROM git_metrics
                WHERE repository_path = ?
                  AND timestamp >= ?
                  AND metric_type IN ('commit_velocity', 'total_commits', 'conventional_commits')
                GROUP BY metric_type
                """,
                (repository_path, since.isoformat()),
            )

            rows = cursor.fetchall()

            dashboard: dict[str, t.Any] = {
                "repository_path": repository_path,
                "period_days": days_back,
                "period_start": since.isoformat(),
                "metrics": {},
                "trend_data": [],
            }

            for row in rows:
                metric_type = row["metric_type"]
                dashboard["metrics"][metric_type] = {
                    "count": row["count"],
                    "average": row["avg_value"],
                    "first_seen": row["first_timestamp"],
                    "last_seen": row["last_timestamp"],
                }

                if row["last_timestamp"]:
                    dashboard["trend_data"].append(
                        {
                            "timestamp": row["last_timestamp"],
                            "metric_type": metric_type,
                            "value": row["avg_value"],
                        }
                    )

            logger.info(f"Generated velocity dashboard for {repository_path}")
            return dashboard

        except Exception as e:
            logger.error(f"Failed to get velocity dashboard: {e}")
            return {}

    def get_repository_health(self, repository_path: str) -> dict[str, t.Any]:
        try:
            cursor = self.conn.execute(
                """
                SELECT details
                FROM git_events
                WHERE repository_path = ?
                  AND event_type = 'branch_create'
                  AND timestamp < datetime('now', '-90 days').isoformat()
                ORDER BY timestamp DESC
                """,
                (repository_path,),
            )
            stale_branches = [row["details"] for row in cursor.fetchall()]

            cursor = self.conn.execute(
                """
                SELECT COUNT(*) as count
                FROM git_events
                WHERE repository_path = ?
                  AND timestamp >= datetime('now', '-7 days').isoformat()
                """,
                (repository_path,),
            )
            recent_activity_count = cursor.fetchone()["count"]

            health = {
                "repository_path": repository_path,
                "stale_branches": stale_branches,
                "recent_activity_count": recent_activity_count,
                "last_activity_timestamp": None,
                "health_score": len(stale_branches) * 10 + recent_activity_count,
            }

            if recent_activity_count > 0:
                cursor = self.conn.execute(
                    """
                    SELECT MAX(timestamp)
                    FROM git_events
                    WHERE repository_path = ?
                    """,
                    (repository_path,),
                )
                last_activity = cursor.fetchone()
                if last_activity:
                    health["last_activity_timestamp"] = last_activity["MAX(timestamp)"]

            logger.info(f"Generated repository health for {repository_path}")
            return health

        except Exception as e:
            logger.error(f"Failed to get repository health: {e}")
            return {}

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.debug("Git metrics storage closed")

    def __enter__(self) -> "GitMetricsStorage":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

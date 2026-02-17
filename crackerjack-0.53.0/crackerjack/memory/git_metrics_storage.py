import logging
import sqlite3
import threading
import typing as t
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


_thread_local = threading.local()


@dataclass
class GitMetric:
    repository_path: str
    metric_type: str
    value: float
    metadata: str | None = None
    timestamp: datetime


class GitMetricsStorage:
    @property
    def conn(self) -> sqlite3.Connection:
        if not hasattr(_thread_local, "conn") or _thread_local.conn is None:
            _thread_local.conn = sqlite3.connect(str(self.db_path))
            _thread_local.conn.row_factory = sqlite3.Row
        return _thread_local.conn

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

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
    ) -> dict[str, t.Any]:
        if self.conn is None:
            return {}

        try:
            params: list[t.Any] = [repository_path]
            if metric_types:
                params.append(metric_types)

            query = "SELECT metric_type, value, metadata, MAX(timestamp) FROM git_metrics WHERE repository_path = ?"
            cursor = self.conn.execute(query, params)
            row = cursor.fetchone()

            metrics: dict[str, t.Any] = {}
            if row:
                metrics["total_value"] = row["value"]
                metrics["last_timestamp"] = row["MAX(timestamp)"]
                metrics["repository_path"] = row["repository_path"]

            return metrics
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {}

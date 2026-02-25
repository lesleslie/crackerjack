"""Crackerjack metrics collection for tracking agent and provider performance."""

import sqlite3
import threading
import typing as t
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


class MetricsCollector:
    """Collects and tracks Crackerjack quality metrics."""

    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_dir = Path.home() / ".cache" / "crackerjack"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / "metrics.db"

        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the metrics database schema."""
        with self._get_connection() as conn:
            conn.executescript("""
                -- Agent executions table
                CREATE TABLE IF NOT EXISTS agent_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    fixes_applied INTEGER NOT NULL,
                    files_modified INTEGER NOT NULL,
                    remaining_issues INTEGER NOT NULL,
                    execution_time_ms REAL,
                    timestamp TIMESTAMP NOT NULL
                );

                -- Provider performance table
                CREATE TABLE IF NOT EXISTS provider_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_id TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    latency_ms REAL,
                    error_message TEXT,
                    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                -- Jobs table
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    status TEXT NOT NULL,
                    issue_count INTEGER DEFAULT 0,
                    fixes_applied INTEGER DEFAULT 0
                );

                -- Create indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_agent_executions_job_id ON agent_executions(job_id);
                CREATE INDEX IF NOT EXISTS idx_agent_executions_agent_name ON agent_executions(agent_name);
                CREATE INDEX IF NOT EXISTS idx_provider_performance_provider_id ON provider_performance(provider_id);
            """)

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper configuration."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a SQL statement with parameters."""
        with self._lock:
            with self._get_connection() as conn:
                conn.execute(sql, params)

    def execute_query(
        self, sql: str, params: tuple = ()
    ) -> list[sqlite3.Row]:
        """Execute a SQL query and return results."""
        with self._lock:
            with self._get_connection() as conn:
                cursor = conn.execute(sql, params)
                return cursor.fetchall()

    def track_provider_selection(
        self,
        provider_id: str,
        success: bool,
        latency_ms: float | None = None,
    ) -> None:
        """Track a provider selection event."""
        self.execute(
            """
            INSERT INTO provider_performance (provider_id, success, latency_ms, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (provider_id, int(success), latency_ms, datetime.now(UTC)),
        )

    def track_agent_execution(
        self,
        job_id: str,
        agent_name: str,
        issue_type: str,
        success: bool,
        confidence: float,
        fixes_applied: int,
        files_modified: int,
        remaining_issues: int,
        execution_time_ms: float | None = None,
    ) -> None:
        """Track an agent execution event."""
        self.execute(
            """
            INSERT INTO agent_executions
            (job_id, agent_name, issue_type, success, confidence,
             fixes_applied, files_modified, remaining_issues, execution_time_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                agent_name,
                issue_type,
                int(success),
                confidence,
                fixes_applied,
                files_modified,
                remaining_issues,
                execution_time_ms,
                datetime.now(UTC),
            ),
        )

    def get_provider_stats(self, provider_id: str | None = None) -> list[dict]:
        """Get statistics for providers."""
        if provider_id:
            rows = self.execute_query(
                """
                SELECT provider_id,
                       COUNT(*) as total_selections,
                       SUM(success) as successful_selections,
                       AVG(latency_ms) as avg_latency_ms
                FROM provider_performance
                WHERE provider_id = ?
                GROUP BY provider_id
                """,
                (provider_id,),
            )
        else:
            rows = self.execute_query(
                """
                SELECT provider_id,
                       COUNT(*) as total_selections,
                       SUM(success) as successful_selections,
                       AVG(latency_ms) as avg_latency_ms
                FROM provider_performance
                GROUP BY provider_id
                """
            )
        return [dict(row) for row in rows]

    def get_agent_stats(self, agent_name: str | None = None) -> list[dict]:
        """Get statistics for agents."""
        if agent_name:
            rows = self.execute_query(
                """
                SELECT agent_name,
                       COUNT(*) as total_executions,
                       SUM(success) as successful_executions,
                       AVG(confidence) as avg_confidence,
                       SUM(fixes_applied) as total_fixes
                FROM agent_executions
                WHERE agent_name = ?
                GROUP BY agent_name
                """,
                (agent_name,),
            )
        else:
            rows = self.execute_query(
                """
                SELECT agent_name,
                       COUNT(*) as total_executions,
                       SUM(success) as successful_executions,
                       AVG(confidence) as avg_confidence,
                       SUM(fixes_applied) as total_fixes
                FROM agent_executions
                GROUP BY agent_name
                """
            )
        return [dict(row) for row in rows]

    def close(self) -> None:
        """Close the database connection."""
        pass  # Connections are closed after each operation


# Global metrics collector instance
_metrics_collector: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def reset_metrics() -> None:
    """Reset the global metrics collector (useful for testing)."""
    global _metrics_collector
    if _metrics_collector is not None:
        _metrics_collector.close()
    _metrics_collector = None

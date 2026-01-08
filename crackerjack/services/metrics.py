import json
import sqlite3
import threading
import typing as t
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any


class MetricsCollector:
    def __init__(self, db_path: Path | None = None) -> None:
        if db_path is None:
            db_dir = Path.home() / ".cache" / "crackerjack"
            db_dir.mkdir(parents=True, exist_ok=True)
            db_path = db_dir / "metrics.db"

        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_database()

    def _init_database(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                -- Jobs table
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    status TEXT NOT NULL, -- 'running', 'success', 'failed', 'cancelled'
                    iterations INTEGER DEFAULT 0,
                    ai_agent BOOLEAN DEFAULT 0,
                    error_message TEXT,
                    metadata TEXT -- JSON field for additional data
                );

                -- Errors table
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    error_type TEXT NOT NULL, -- 'hook', 'test', 'lint', 'type_check', etc.
                    error_category TEXT, -- 'ruff', 'pyright', 'pytest', etc.
                    error_message TEXT,
                    file_path TEXT,
                    line_number INTEGER,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );

                -- Hook executions table
                CREATE TABLE IF NOT EXISTS hook_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    hook_name TEXT NOT NULL,
                    hook_type TEXT, -- 'fast', 'comprehensive'
                    execution_time_ms INTEGER,
                    status TEXT, -- 'success', 'failed', 'skipped'
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );

                -- Test executions table
                CREATE TABLE IF NOT EXISTS test_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    total_tests INTEGER,
                    passed INTEGER,
                    failed INTEGER,
                    skipped INTEGER,
                    execution_time_ms INTEGER,
                    coverage_percent REAL,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );

                -- Orchestration executions table (NEW)
                CREATE TABLE IF NOT EXISTS orchestration_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    execution_strategy TEXT NOT NULL, -- 'batch', 'individual', 'adaptive', 'selective'
                    progress_level TEXT NOT NULL, -- 'basic', 'detailed', 'granular', 'streaming'
                    ai_mode TEXT NOT NULL, -- 'single-agent', 'multi-agent', 'coordinator'
                    iteration_count INTEGER DEFAULT 1,
                    strategy_switches INTEGER DEFAULT 0, -- How many times strategy changed
                    correlation_insights TEXT, -- JSON of correlation analysis results
                    total_execution_time_ms INTEGER,
                    hooks_execution_time_ms INTEGER,
                    tests_execution_time_ms INTEGER,
                    ai_analysis_time_ms INTEGER,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );

                -- Strategy decisions table (NEW)
                CREATE TABLE IF NOT EXISTS strategy_decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    iteration INTEGER,
                    timestamp TIMESTAMP NOT NULL,
                    previous_strategy TEXT,
                    selected_strategy TEXT NOT NULL,
                    decision_reason TEXT, -- Why this strategy was chosen
                    context_data TEXT, -- JSON of execution context
                    effectiveness_score REAL, -- How well the strategy worked (0 - 1)
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );

                -- Individual test executions table (NEW - more granular than test_executions)
                CREATE TABLE IF NOT EXISTS individual_test_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    test_id TEXT NOT NULL, -- Full test identifier
                    test_file TEXT NOT NULL,
                    test_class TEXT,
                    test_method TEXT,
                    status TEXT NOT NULL, -- 'passed', 'failed', 'skipped', 'error'
                    execution_time_ms INTEGER,
                    error_message TEXT,
                    error_traceback TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                );

                -- Daily summary table (for quick stats)
                CREATE TABLE IF NOT EXISTS daily_summary (
                    date DATE PRIMARY KEY,
                    total_jobs INTEGER DEFAULT 0,
                    successful_jobs INTEGER DEFAULT 0,
                    failed_jobs INTEGER DEFAULT 0,
                    total_errors INTEGER DEFAULT 0,
                    hook_errors INTEGER DEFAULT 0,
                    test_errors INTEGER DEFAULT 0,
                    lint_errors INTEGER DEFAULT 0,
                    type_errors INTEGER DEFAULT 0,
                    avg_job_duration_ms INTEGER,
                    total_ai_fixes INTEGER DEFAULT 0,
                    orchestrated_jobs INTEGER DEFAULT 0, -- NEW
                    avg_orchestration_iterations REAL DEFAULT 0, -- NEW
                    most_effective_strategy TEXT -- NEW
                );

                --Create indexes for performance
                CREATE INDEX IF NOT EXISTS idx_jobs_start_time ON jobs(start_time);
                CREATE INDEX IF NOT EXISTS idx_errors_job_id ON errors(job_id);
                CREATE INDEX IF NOT EXISTS idx_errors_type ON errors(error_type);
                CREATE INDEX IF NOT EXISTS idx_hooks_job_id ON hook_executions(job_id);
                CREATE INDEX IF NOT EXISTS idx_tests_job_id ON test_executions(job_id);
                CREATE INDEX IF NOT EXISTS idx_orchestration_job_id ON orchestration_executions(job_id);
                CREATE INDEX IF NOT EXISTS idx_strategy_decisions_job_id ON strategy_decisions(job_id);
                CREATE INDEX IF NOT EXISTS idx_individual_tests_job_id ON individual_test_executions(job_id);
                CREATE INDEX IF NOT EXISTS idx_strategy_decisions_strategy ON strategy_decisions(selected_strategy);
            """)

    @contextmanager
    def _get_connection(self) -> t.Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def start_job(
        self,
        job_id: str,
        ai_agent: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                    INSERT INTO jobs (job_id, start_time, status, ai_agent, metadata)
                    VALUES (?, ?, 'running', ?, ?)
                """,
                (job_id, datetime.now(), ai_agent, json.dumps(metadata or {})),
            )

    def end_job(
        self,
        job_id: str,
        status: str,
        iterations: int = 0,
        error_message: str | None = None,
    ) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                    UPDATE jobs
                    SET end_time=?, status=?, iterations=?, error_message=?
                    WHERE job_id=?
                """,
                (datetime.now(), status, iterations, error_message, job_id),
            )

            self._update_daily_summary(conn, datetime.now().date())

    def record_error(
        self,
        job_id: str,
        error_type: str,
        error_category: str,
        error_message: str,
        file_path: str | None = None,
        line_number: int | None = None,
    ) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                    INSERT INTO errors (job_id, timestamp, error_type, error_category,
                                      error_message, file_path, line_number)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    datetime.now(),
                    error_type,
                    error_category,
                    error_message,
                    file_path,
                    line_number,
                ),
            )

    def record_hook_execution(
        self,
        job_id: str,
        hook_name: str,
        hook_type: str,
        execution_time_ms: int,
        status: str,
    ) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                    INSERT INTO hook_executions (job_id, timestamp, hook_name,
                                               hook_type, execution_time_ms, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    datetime.now(),
                    hook_name,
                    hook_type,
                    execution_time_ms,
                    status,
                ),
            )

    def record_test_execution(
        self,
        job_id: str,
        total_tests: int,
        passed: int,
        failed: int,
        skipped: int,
        execution_time_ms: int,
        coverage_percent: float | None = None,
    ) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                    INSERT INTO test_executions (job_id, timestamp, total_tests,
                                               passed, failed, skipped,
                                               execution_time_ms, coverage_percent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    datetime.now(),
                    total_tests,
                    passed,
                    failed,
                    skipped,
                    execution_time_ms,
                    coverage_percent,
                ),
            )

    def record_orchestration_execution(
        self,
        job_id: str,
        execution_strategy: str,
        progress_level: str,
        ai_mode: str,
        iteration_count: int,
        strategy_switches: int,
        correlation_insights: dict[str, Any],
        total_execution_time_ms: int,
        hooks_execution_time_ms: int,
        tests_execution_time_ms: int,
        ai_analysis_time_ms: int,
    ) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                    INSERT INTO orchestration_executions
                    (job_id, timestamp, execution_strategy, progress_level, ai_mode,
                     iteration_count, strategy_switches, correlation_insights,
                     total_execution_time_ms, hooks_execution_time_ms,
                     tests_execution_time_ms, ai_analysis_time_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    job_id,
                    datetime.now(),
                    execution_strategy,
                    progress_level,
                    ai_mode,
                    iteration_count,
                    strategy_switches,
                    json.dumps(correlation_insights),
                    total_execution_time_ms,
                    hooks_execution_time_ms,
                    tests_execution_time_ms,
                    ai_analysis_time_ms,
                ),
            )

    def record_strategy_decision(
        self,
        job_id: str,
        iteration: int,
        previous_strategy: str | None,
        selected_strategy: str,
        decision_reason: str,
        context_data: dict[str, Any],
        effectiveness_score: float | None = None,
    ) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                    INSERT INTO strategy_decisions
                    (job_id, iteration, timestamp, previous_strategy, selected_strategy,
                     decision_reason, context_data, effectiveness_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    job_id,
                    iteration,
                    datetime.now(),
                    previous_strategy,
                    selected_strategy,
                    decision_reason,
                    json.dumps(context_data),
                    effectiveness_score,
                ),
            )

    def record_individual_test(
        self,
        job_id: str,
        test_id: str,
        test_file: str,
        test_class: str | None,
        test_method: str | None,
        status: str,
        execution_time_ms: int | None,
        error_message: str | None = None,
        error_traceback: str | None = None,
    ) -> None:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                    INSERT INTO individual_test_executions
                    (job_id, timestamp, test_id, test_file, test_class, test_method,
                     status, execution_time_ms, error_message, error_traceback)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                (
                    job_id,
                    datetime.now(),
                    test_id,
                    test_file,
                    test_class,
                    test_method,
                    status,
                    execution_time_ms,
                    error_message,
                    error_traceback,
                ),
            )

    def get_orchestration_stats(self) -> dict[str, Any]:
        with self._get_connection() as conn:
            strategy_stats = conn.execute("""
                SELECT
                    selected_strategy,
                    COUNT(*) as usage_count,
                    AVG(effectiveness_score) as avg_effectiveness,
                    AVG(
                        SELECT iteration_count
                        FROM orchestration_executions o
                        WHERE o.job_id=sd.job_id
                    ) as avg_iterations_needed
                FROM strategy_decisions sd
                WHERE effectiveness_score IS NOT NULL
                GROUP BY selected_strategy
                ORDER BY avg_effectiveness DESC, usage_count DESC
            """).fetchall()

            correlation_patterns = conn.execute("""
                SELECT
                    json_extract(correlation_insights, '$.problematic_hooks') as problematic_hooks,
                    COUNT(*) as frequency
                FROM orchestration_executions
                WHERE correlation_insights != 'null'
                AND correlation_insights != '{}'
                GROUP BY problematic_hooks
                ORDER BY frequency DESC
                LIMIT 10
            """).fetchall()

            performance_stats = conn.execute("""
                SELECT
                    execution_strategy,
                    COUNT(*) as executions,
                    AVG(total_execution_time_ms) as avg_total_time,
                    AVG(hooks_execution_time_ms) as avg_hooks_time,
                    AVG(tests_execution_time_ms) as avg_tests_time,
                    AVG(ai_analysis_time_ms) as avg_ai_time,
                    AVG(iteration_count) as avg_iterations
                FROM orchestration_executions
                GROUP BY execution_strategy
            """).fetchall()

            test_failure_patterns = conn.execute("""
                SELECT
                    test_file,
                    test_class,
                    test_method,
                    COUNT(*) as failure_count,
                    AVG(execution_time_ms) as avg_execution_time
                FROM individual_test_executions
                WHERE status='failed'
                GROUP BY test_file, test_class, test_method
                ORDER BY failure_count DESC
                LIMIT 15
            """).fetchall()

            return {
                "strategy_effectiveness": [
                    dict[str, t.Any](row) for row in strategy_stats
                ],
                "correlation_patterns": [
                    dict[str, t.Any](row) for row in correlation_patterns
                ],
                "performance_by_strategy": [
                    dict[str, t.Any](row) for row in performance_stats
                ],
                "test_failure_patterns": [
                    dict[str, t.Any](row) for row in test_failure_patterns
                ],
            }

    def _update_daily_summary(
        self,
        conn: sqlite3.Connection,
        date: date,
    ) -> None:
        job_stats = conn.execute(
            """
            SELECT
                COUNT(*) as total_jobs,
                SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as successful_jobs,
                SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed_jobs,
                AVG(CASE
                    WHEN end_time IS NOT NULL
                    THEN (julianday(end_time)-julianday(start_time)) * 86400000
                    ELSE NULL
                END) as avg_duration_ms,
                SUM(CASE WHEN ai_agent=1 AND status='success' THEN 1 ELSE 0 END) as ai_fixes
            FROM jobs
            WHERE DATE(start_time) = ?
        """,
            (date,),
        ).fetchone()

        error_stats = conn.execute(
            """
            SELECT
                COUNT(*) as total_errors,
                SUM(CASE WHEN error_type='hook' THEN 1 ELSE 0 END) as hook_errors,
                SUM(CASE WHEN error_type='test' THEN 1 ELSE 0 END) as test_errors,
                SUM(CASE WHEN error_type='lint' THEN 1 ELSE 0 END) as lint_errors,
                SUM(CASE WHEN error_type='type_check' THEN 1 ELSE 0 END) as type_errors
            FROM errors
            WHERE DATE(timestamp) = ?
        """,
            (date,),
        ).fetchone()

        orchestration_stats = conn.execute(
            """
            SELECT
                COUNT(*) as orchestrated_jobs,
                AVG(iteration_count) as avg_iterations,
                (SELECT selected_strategy
                 FROM strategy_decisions sd2
                 WHERE DATE(sd2.timestamp) = ?
                 GROUP BY selected_strategy
                 ORDER BY COUNT(*) DESC
                 LIMIT 1) as most_effective_strategy
            FROM orchestration_executions
            WHERE DATE(timestamp) = ?
        """,
            (date, date),
        ).fetchone()

        conn.execute(
            """
            INSERT OR REPLACE INTO daily_summary
            (date, total_jobs, successful_jobs, failed_jobs, total_errors,
             hook_errors, test_errors, lint_errors, type_errors,
             avg_job_duration_ms, total_ai_fixes, orchestrated_jobs,
             avg_orchestration_iterations, most_effective_strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                date,
                job_stats["total_jobs"] or 0,
                job_stats["successful_jobs"] or 0,
                job_stats["failed_jobs"] or 0,
                error_stats["total_errors"] or 0,
                error_stats["hook_errors"] or 0,
                error_stats["test_errors"] or 0,
                error_stats["lint_errors"] or 0,
                error_stats["type_errors"] or 0,
                int(job_stats["avg_duration_ms"] or 0),
                job_stats["ai_fixes"] or 0,
                orchestration_stats["orchestrated_jobs"] or 0,
                float(orchestration_stats["avg_iterations"] or 0),
                orchestration_stats["most_effective_strategy"],
            ),
        )

    def get_all_time_stats(self) -> dict[str, Any]:
        with self._get_connection() as conn:
            job_stats = conn.execute("""
                SELECT
                    COUNT(*) as total_jobs,
                    SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as successful_jobs,
                    SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed_jobs,
                    SUM(CASE WHEN ai_agent=1 THEN 1 ELSE 0 END) as ai_agent_jobs,
                    AVG(iterations) as avg_iterations
                FROM jobs
            """).fetchone()

            error_stats = conn.execute("""
                SELECT error_type, COUNT( * ) as count
                FROM errors
                GROUP BY error_type
            """).fetchall()

            common_errors = conn.execute("""
                SELECT error_category, error_message, COUNT( * ) as count
                FROM errors
                GROUP BY error_category, error_message
                ORDER BY count DESC
                LIMIT 10
            """).fetchall()

            return {
                "total_jobs": job_stats["total_jobs"] or 0,
                "successful_jobs": job_stats["successful_jobs"] or 0,
                "failed_jobs": job_stats["failed_jobs"] or 0,
                "ai_agent_jobs": job_stats["ai_agent_jobs"] or 0,
                "avg_iterations": float(job_stats["avg_iterations"] or 0),
                "error_breakdown": {
                    row["error_type"]: row["count"] for row in error_stats
                },
                "common_errors": [dict[str, t.Any](row) for row in common_errors],
            }


_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

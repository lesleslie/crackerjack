import json
import sqlite3
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

from crackerjack.services.metrics import MetricsCollector


class TestMetricsCollector:
    def test_init_with_default_path(self):
        with patch("pathlib.Path.home") as mock_home:
            mock_home.return_value = Path(" / fake / home")

            collector = MetricsCollector()

            expected_path = (
                Path(" / fake / home") / ".cache" / "crackerjack" / "metrics.db"
            )
            assert collector.db_path == expected_path

    def test_init_with_custom_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"

            collector = MetricsCollector(db_path=db_path)

            assert collector.db_path == db_path
            assert db_path.exists()

    def test_database_initialization(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"

            MetricsCollector(db_path=db_path)

            assert db_path.exists()

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
                )
                assert cursor.fetchone() is not None

                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'hooks'"
                )
                assert cursor.fetchone() is not None

                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'tests'"
                )
                assert cursor.fetchone() is not None

    def test_start_job(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"
            collector = MetricsCollector(db_path=db_path)

            job_id = "test - job - 123"
            collector.start_job(job_id, ai_agent=True, metadata={"test": "data"})

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT job_id, status, ai_agent, metadata FROM jobs WHERE job_id = ?",
                    (job_id,),
                )
                row = cursor.fetchone()

                assert row is not None
                assert row[0] == job_id
                assert row[1] == "running"
                assert row[2] == 1
                assert json.loads(row[3]) == {"test": "data"}

    def test_end_job_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"
            collector = MetricsCollector(db_path=db_path)

            job_id = "test - job - 456"
            collector.start_job(job_id)
            collector.end_job(job_id, status="success", iterations=3)

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT status, iterations, end_time FROM jobs WHERE job_id = ?",
                    (job_id,),
                )
                row = cursor.fetchone()

                assert row is not None
                assert row[0] == "success"
                assert row[1] == 3
                assert row[2] is not None

    def test_end_job_with_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"
            collector = MetricsCollector(db_path=db_path)

            job_id = "test - job - error"
            error_msg = "Test error occurred"

            collector.start_job(job_id)
            collector.end_job(job_id, status="failed", error_message=error_msg)

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT status, error_message FROM jobs WHERE job_id = ?", (job_id,)
                )
                row = cursor.fetchone()

                assert row is not None
                assert row[0] == "failed"
                assert row[1] == error_msg

    def test_record_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"
            collector = MetricsCollector(db_path=db_path)

            job_id = "test - job - error"
            collector.start_job(job_id)

            collector.record_error(
                job_id=job_id,
                error_type="type_error",
                error_message="Type annotation missing",
                file_path="test.py",
                line_number=42,
                stage="comprehensive",
            )

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT error_type, error_message, file_path, line_number, stage FROM errors WHERE job_id = ?",
                    (job_id,),
                )
                row = cursor.fetchone()

                assert row is not None
                assert row[0] == "type_error"
                assert row[1] == "Type annotation missing"
                assert row[2] == "test.py"
                assert row[3] == 42
                assert row[4] == "comprehensive"

    def test_record_hook_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"
            collector = MetricsCollector(db_path=db_path)

            job_id = "test - job - hooks"
            collector.start_job(job_id)

            collector.record_hook_execution(
                job_id=job_id,
                hook_name="ruff - check",
                hook_type="fast",
                execution_time_ms=1500,
                status="success",
            )

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT hook_name, hook_type, execution_time_ms, status FROM hook_executions WHERE job_id = ?",
                    (job_id,),
                )
                row = cursor.fetchone()

                assert row is not None
                assert row[0] == "ruff - check"
                assert row[1] == "fast"
                assert row[2] == 1500
                assert row[3] == "success"

    def test_record_test_execution(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"
            collector = MetricsCollector(db_path=db_path)

            job_id = "test - job - tests"
            collector.start_job(job_id)

            collector.record_test_execution(
                job_id=job_id,
                total_tests=100,
                passed=95,
                failed=5,
                skipped=0,
                execution_time_ms=30500,
                coverage_percent=87.5,
            )

            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT total_tests, passed, failed, skipped, execution_time_ms, coverage_percent FROM test_executions WHERE job_id = ?",
                    (job_id,),
                )
                row = cursor.fetchone()

                assert row is not None
                assert row[0] == 100
                assert row[1] == 95
                assert row[2] == 5
                assert row[3] == 0
                assert row[4] == 30500
                assert row[5] == 87.5

    def test_get_all_time_stats(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"
            collector = MetricsCollector(db_path=db_path)

            collector.start_job("job1", ai_agent=True)
            collector.end_job("job1", status="success", iterations=2)

            collector.start_job("job2", ai_agent=False)
            collector.end_job("job2", status="failed", error_message="Test error")

            stats = collector.get_all_time_stats()

            assert isinstance(stats, dict)
            assert "jobs" in stats
            assert "errors" in stats
            assert "hooks" in stats
            assert "tests" in stats

    def test_thread_safety(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"
            collector = MetricsCollector(db_path=db_path)

            def create_jobs(start_idx: int, count: int):
                for i in range(start_idx, start_idx + count):
                    job_id = f"thread - job - {i}"
                    collector.start_job(job_id)
                    collector.end_job(job_id, status="success", iterations=1)

            threads = []
            for i in range(3):
                thread = threading.Thread(target=create_jobs, args=(i * 10, 10))
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            stats = collector.get_all_time_stats()
            assert stats["jobs"]["total"] == 30

    def test_context_manager(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test_metrics.db"
            collector = MetricsCollector(db_path=db_path)

            with collector._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT( * ) FROM jobs")
                result = cursor.fetchone()
                assert result[0] == 0

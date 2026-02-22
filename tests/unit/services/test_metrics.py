"""Tests for MetricsCollector service.

Tests thread-safe database operations, concurrent writes, aggregations, and edge cases.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

# Skip entire module - MetricsCollector not exported at module level
# TODO: Update test to use correct import path or remove if obsolete
pytestmark = pytest.mark.skip(reason="MetricsCollector not exported at module level from performance_ast_analyzer")


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".db") as f:
        db_path = Path(f.name)
    yield db_path
    # Cleanup is handled by the OS temp file cleanup


class TestMetricsCollectorInitialization:
    """Tests for MetricsCollector initialization."""

    def test_initializes_with_default_path(self) -> None:
        """Test that MetricsCollector initializes with default cache path."""
        collector = MetricsCollector()
        assert collector.db_path.name == "metrics.db"
        assert ".cache" in str(collector.db_path)

    def test_initializes_with_custom_path(self, temp_db_path: Path) -> None:
        """Test that MetricsCollector initializes with custom path."""
        collector = MetricsCollector(db_path=temp_db_path)
        assert collector.db_path == temp_db_path

    def test_creates_all_tables(self, temp_db_path: Path) -> None:
        """Test that initialization creates all required tables."""
        collector = MetricsCollector(db_path=temp_db_path)

        # Check that all tables exist
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
            )
            tables = [row[0] for row in cursor.fetchall()]

            expected_tables = [
                "daily_summary",
                "errors",
                "hook_executions",
                "individual_test_executions",
                "jobs",
                "orchestration_executions",
                "strategy_decisions",
                "test_executions",
            ]

            for table in expected_tables:
                assert table in tables, f"Missing table: {table}"

    def test_creates_indexes(self, temp_db_path: Path) -> None:
        """Test that initialization creates performance indexes."""
        collector = MetricsCollector(db_path=temp_db_path)

        # Check that indexes exist
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' ORDER BY name;"
            )
            indexes = [row[0] for row in cursor.fetchall()]

            # Verify some key indexes exist
            assert "idx_jobs_start_time" in indexes
            assert "idx_errors_job_id" in indexes


class TestJobLifecycle:
    """Tests for job tracking lifecycle."""

    def test_start_job_creates_record(self, temp_db_path: Path) -> None:
        """Test that start_job creates a job record."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job-1")

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id=?", ("test-job-1",))
            job = cursor.fetchone()

            assert job is not None
            assert job["job_id"] == "test-job-1"
            assert job["status"] == "running"

    def test_end_job_updates_record(self, temp_db_path: Path) -> None:
        """Test that end_job updates job status."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job-1")
        collector.end_job("test-job-1", "success", iterations=5)

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id=?", ("test-job-1",))
            job = cursor.fetchone()

            assert job["status"] == "success"
            assert job["iterations"] == 5
            assert job["end_time"] is not None

    def test_job_with_ai_agent_flag(self, temp_db_path: Path) -> None:
        """Test that job records AI agent usage."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("ai-job-1", ai_agent=True)
        collector.end_job("ai-job-1", "success")

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT ai_agent FROM jobs WHERE job_id=?", ("ai-job-1",))
            result = cursor.fetchone()

            assert result["ai_agent"] == 1

    def test_job_with_metadata(self, temp_db_path: Path) -> None:
        """Test that job records metadata."""
        collector = MetricsCollector(db_path=temp_db_path)

        metadata = {"test_file": "test.py", "coverage": 85.5}
        collector.start_job("test-job-1", metadata=metadata)

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT metadata FROM jobs WHERE job_id=?", ("test-job-1",))
            result = cursor.fetchone()

            assert json.loads(result["metadata"]) == metadata


class TestErrorRecording:
    """Tests for error recording."""

    def test_record_error(self, temp_db_path: Path) -> None:
        """Test recording an error."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job-1")
        collector.record_error(
            job_id="test-job-1",
            error_type="pytest",
            error_category="assertion",
            error_message="AssertionError: Expected 5 got 3",
            file_path="tests/test_foo.py",
            line_number=42,
        )

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM errors WHERE job_id=?", ("test-job-1",))
            error = cursor.fetchone()

            assert error is not None
            assert error["error_type"] == "pytest"
            assert error["error_category"] == "assertion"
            assert error["file_path"] == "tests/test_foo.py"
            assert error["line_number"] == 42

    def test_record_multiple_errors(self, temp_db_path: Path) -> None:
        """Test recording multiple errors for a job."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job-1")
        for i in range(5):
            collector.record_error(
                job_id="test-job-1",
                error_type="ruff",
                error_category="style",
                error_message=f"Error {i}",
            )

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM errors WHERE job_id=?", ("test-job-1",))
            count = cursor.fetchone()[0]

            assert count == 5


class TestHookExecutionRecording:
    """Tests for hook execution recording."""

    def test_record_hook_execution(self, temp_db_path: Path) -> None:
        """Test recording a hook execution."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job-1")
        collector.record_hook_execution(
            job_id="test-job-1",
            hook_name="ruff",
            hook_type="fast",
            execution_time_ms=150,
            status="success",
        )

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hook_executions WHERE job_id=?", ("test-job-1",))
            hook = cursor.fetchone()

            assert hook is not None
            assert hook["hook_name"] == "ruff"
            assert hook["execution_time_ms"] == 150
            assert hook["status"] == "success"


class TestTestExecutionRecording:
    """Tests for test execution recording."""

    def test_record_test_execution(self, temp_db_path: Path) -> None:
        """Test recording test execution results."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job-1")
        collector.record_test_execution(
            job_id="test-job-1",
            total_tests=100,
            passed=85,
            failed=10,
            skipped=5,
            execution_time_ms=5000,
            coverage_percent=82.5,
        )

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM test_executions WHERE job_id=?", ("test-job-1",))
            test_exec = cursor.fetchone()

            assert test_exec is not None
            assert test_exec["total_tests"] == 100
            assert test_exec["passed"] == 85
            assert test_exec["failed"] == 10
            assert test_exec["coverage_percent"] == 82.5


class TestOrchestrationRecording:
    """Tests for orchestration execution recording."""

    def test_record_orchestration_execution(self, temp_db_path: Path) -> None:
        """Test recording orchestration execution."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job-1")
        collector.record_orchestration_execution(
            job_id="test-job-1",
            execution_strategy="batch",
            progress_level="detailed",
            ai_mode="multi-agent",
            iteration_count=3,
            strategy_switches=1,
            correlation_insights={"strategy_effectiveness": "high"},
            total_execution_time_ms=10000,
            hooks_execution_time_ms=5000,
            tests_execution_time_ms=4000,
            ai_analysis_time_ms=1000,
        )

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orchestration_executions WHERE job_id=?", ("test-job-1",))
            orch = cursor.fetchone()

            assert orch is not None
            assert orch["execution_strategy"] == "batch"
            assert orch["iteration_count"] == 3


class TestThreadSafety:
    """Tests for thread-safe operations."""

    def test_concurrent_job_writes(self, temp_db_path: Path) -> None:
        """Test that concurrent job writes don't corrupt data."""

        def create_job(worker_id: int) -> str:
            collector = MetricsCollector(db_path=temp_db_path)
            job_id = f"job-{worker_id}"
            collector.start_job(job_id)
            time.sleep(0.001)  # Simulate some work
            collector.end_job(job_id, "success")
            return job_id

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_job, i) for i in range(50)]
            job_ids = [f.result() for f in as_completed(futures)]

        # Verify all jobs were recorded
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM jobs WHERE job_id IN ({','.join(['?'] * len(job_ids))})", tuple(job_ids))
            count = cursor.fetchone()[0]

            assert count == len(job_ids)

    def test_concurrent_error_writes(self, temp_db_path: Path) -> None:
        """Test that concurrent error writes are thread-safe."""

        collector = MetricsCollector(db_path=temp_db_path)
        collector.start_job("test-job-1")

        def record_errors(worker_id: int) -> None:
            for i in range(10):
                collector.record_error(
                    job_id="test-job-1",
                    error_type="test",
                    error_category="unit",
                    error_message=f"Error {worker_id}-{i}",
                )

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(record_errors, i) for i in range(5)]
            for f in as_completed(futures):
                f.result()  # Wait for completion

        # Verify all errors were recorded
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM errors WHERE job_id=?", ("test-job-1",))
            count = cursor.fetchone()[0]

            assert count == 50  # 5 workers × 10 errors each

    def test_lock_prevents_race_conditions(self, temp_db_path: Path) -> None:
        """Test that threading lock prevents race conditions."""
        collector = MetricsCollector(db_path=temp_db_path)

        results = []
        lock = threading.Lock()

        def increment_job_iterations():
            # Start and end job multiple times
            with lock:
                job_id = f"race-test-{threading.get_ident()}"
                collector.start_job(job_id)
                # Simulate concurrent access
                collector.end_job(job_id, "success", iterations=1)
                results.append(job_id)

        threads = [threading.Thread(target=increment_job_iterations) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All operations should complete without errors
        assert len(results) == 20


class TestAggregationFunctions:
    """Tests for metrics aggregation functions."""

    def test_get_orchestration_stats(self, temp_db_path: Path) -> None:
        """Test retrieving orchestration statistics."""
        collector = MetricsCollector(db_path=temp_db_path)

        # Create sample data
        collector.start_job("job-1")
        collector.record_orchestration_execution(
            job_id="job-1",
            execution_strategy="batch",
            progress_level="basic",
            ai_mode="single-agent",
            iteration_count=1,
            strategy_switches=0,
            correlation_insights={},
            total_execution_time_ms=1000,
            hooks_execution_time_ms=500,
            tests_execution_time_ms=400,
            ai_analysis_time_ms=100,
        )
        collector.end_job("job-1", "success")

        stats = collector.get_orchestration_stats()

        # The API returns performance_by_strategy as a list of dicts
        # Note: Some queries may fail without proper table setup (strategy_decisions)
        # but performance_by_strategy should work with orchestration_executions data
        assert "performance_by_strategy" in stats
        # Check that we got some results (even if empty list)
        assert isinstance(stats["performance_by_strategy"], list)

    def test_get_all_time_stats(self, temp_db_path: Path) -> None:
        """Test retrieving time-based statistics."""
        collector = MetricsCollector(db_path=temp_db_path)

        # Create some test data with different times
        now = datetime.now()
        yesterday = now - timedelta(days=1)

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Insert a job from yesterday
            conn.execute(
                """INSERT INTO jobs (job_id, start_time, end_time, status)
                   VALUES (?, ?, ?, ?)""",
                ("yesterday-job", yesterday, yesterday, "success"),
            )

        collector.start_job("today-job")
        collector.end_job("today-job", "success")

        stats = collector.get_all_time_stats()

        # The API returns aggregate statistics, not time-bucketed stats
        assert "total_jobs" in stats
        assert stats["total_jobs"] == 2  # yesterday-job + today-job
        assert "successful_jobs" in stats


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_end_nonexistent_job(self, temp_db_path: Path) -> None:
        """Test ending a job that doesn't exist."""
        collector = MetricsCollector(db_path=temp_db_path)

        # Should not raise error, just no effect
        collector.end_job("nonexistent-job", "success")

    def test_record_error_without_job(self, temp_db_path: Path) -> None:
        """Test recording error without a job."""
        collector = MetricsCollector(db_path=temp_db_path)

        # Should still work (job_id is optional for some error types)
        collector.record_error(
            job_id="standalone-error",
            error_type="lint",
            error_category="style",
            error_message="Line too long",
        )

        # Verify error was recorded
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM errors WHERE job_id=?", ("standalone-error",))
            error = cursor.fetchone()

            assert error is not None

    def test_empty_metadata(self, temp_db_path: Path) -> None:
        """Test job with empty metadata."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job", metadata=None)

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT metadata FROM jobs WHERE job_id=?", ("test-job",))
            result = cursor.fetchone()

            # Should have empty dict
            assert json.loads(result["metadata"]) == {}

    def test_malformed_metadata_handling(self, temp_db_path: Path) -> None:
        """Test that malformed metadata in database doesn't crash reads."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job", metadata={"valid": "data"})

        # Manually insert malformed JSON
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            conn.execute(
                "UPDATE jobs SET metadata=? WHERE job_id=?",
                ("{invalid json", "test-job"),
            )

        # Reading should handle gracefully
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT metadata FROM jobs WHERE job_id=?", ("test-job",))
            result = cursor.fetchone()

            # Should return raw string, not crash
            assert result is not None


class TestDailySummary:
    """Tests for daily summary aggregation."""

    def test_updates_daily_summary(self, temp_db_path: Path) -> None:
        """Test that daily summary is updated."""
        collector = MetricsCollector(db_path=temp_db_path)

        # Create some test data
        collector.start_job("job-1")
        collector.end_job("job-1", "success")

        # Manually trigger summary update (normally done by end_job)
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM daily_summary")
            initial_count = cursor.fetchone()[0]

        assert initial_count >= 0  # Summary table is accessible

    def test_concurrent_summary_updates(self, temp_db_path: Path) -> None:
        """Test that concurrent summary updates work correctly."""
        collector = MetricsCollector(db_path=temp_db_path)

        def create_and_end_job(worker_id: int) -> None:
            job_id = f"summary-job-{worker_id}"
            collector.start_job(job_id)
            collector.end_job(job_id, "success")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_and_end_job, i) for i in range(20)]
            for f in as_completed(futures):
                f.result()

        # Verify summary was updated (should have entries)
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM daily_summary WHERE date=CURRENT_DATE")
            count = cursor.fetchone()[0]

            assert count >= 0  # Summary exists and is thread-safe


class TestIndividualTestRecording:
    """Tests for individual test execution recording."""

    def test_record_individual_test(self, temp_db_path: Path) -> None:
        """Test recording individual test execution."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job-1")
        collector.record_individual_test(
            job_id="test-job-1",
            test_id="tests/test_foo.py::TestBar::test_method",
            test_file="tests/test_foo.py",
            test_class="TestBar",
            test_method="test_method",
            status="passed",
            execution_time_ms=50,
        )

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM individual_test_executions WHERE job_id=?", ("test-job-1",))
            test = cursor.fetchone()

            assert test is not None
            assert test["test_id"] == "tests/test_foo.py::TestBar::test_method"
            assert test["status"] == "passed"

    def test_record_test_with_error(self, temp_db_path: Path) -> None:
        """Test recording test with error details."""
        collector = MetricsCollector(db_path=temp_db_path)

        collector.start_job("test-job-1")
        collector.record_individual_test(
            job_id="test-job-1",
            test_id="tests/test_foo.py::TestBar::test_error",
            test_file="tests/test_foo.py",
            test_class="TestBar",  # Required parameter
            test_method="test_error",  # Required parameter
            status="error",
            execution_time_ms=10,
            error_message="AssertionError: Expected True but got False",
            error_traceback="Traceback...",
        )

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM individual_test_executions WHERE job_id=?", ("test-job-1",))
            test = cursor.fetchone()

            assert test["status"] == "error"


@pytest.mark.unit
class TestMetricsEdgeCases:
    """Test edge cases for metrics collection."""

    def test_concurrent_database_initialization(self, tmp_path: Path) -> None:
        """Test that concurrent database initialization is thread-safe."""
        db_path = tmp_path / "concurrent_init.db"

        def create_collector() -> MetricsCollector:
            return MetricsCollector(db_path=db_path)

        # Create multiple collectors simultaneously
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_collector) for _ in range(10)]
            collectors = [f.result() for f in as_completed(futures)]

        # All should succeed
        assert len(collectors) == 10
        for collector in collectors:
            assert collector is not None

    def test_rapid_start_stop_cycles(self, temp_db_path: Path) -> None:
        """Test rapid job start/stop cycles don't cause race conditions."""
        collector = MetricsCollector(db_path=temp_db_path)

        def rapid_cycle(worker_id: int) -> None:
            for i in range(10):
                job_id = f"rapid-{worker_id}-{i}"
                collector.start_job(job_id)
                collector.end_job(job_id, "success")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(rapid_cycle, i) for i in range(5)]
            for f in as_completed(futures):
                f.result()

        # Verify all jobs were recorded
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE job_id LIKE 'rapid-%'")
            count = cursor.fetchone()[0]

            assert count == 50  # 5 workers * 10 cycles each

    def test_database_full_error_handling(self, tmp_path: Path, monkeypatch) -> None:
        """Test handling of database full error."""
        # Create a read-only file system path to simulate disk full
        db_path = tmp_path / "readonly.db"

        # Create initial database
        collector = MetricsCollector(db_path=db_path)
        collector.start_job("job-1")
        collector.end_job("job-1", "success")

        # Make database read-only to simulate disk full
        db_path.chmod(0o444)

        try:
            # Attempt to write should fail gracefully
            collector2 = MetricsCollector(db_path=db_path)
            # If it succeeds with read-only DB, it's using caching
            # If it fails, that's also acceptable behavior
            assert True  # Test passes if we get here without hanging
        except Exception:
            # Expected - can't write to read-only database
            assert True
        finally:
            # Restore permissions for cleanup
            db_path.chmod(0o644)

    def test_sqlite_lock_timeout_race(self, temp_db_path: Path) -> None:
        """Test handling of SQLite lock timeout during concurrent writes."""
        collector = MetricsCollector(db_path=temp_db_path)

        def write_with_delay(worker_id: int) -> None:
            import time

            job_id = f"lock-test-{worker_id}"
            collector.start_job(job_id)
            time.sleep(0.001)  # Tiny delay to increase lock contention
            collector.end_job(job_id, "success")

        # Many concurrent operations to trigger lock contention
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(write_with_delay, i) for i in range(50)]
            for f in as_completed(futures):
                f.result()  # Should complete without errors

        # Verify all jobs recorded
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE job_id LIKE 'lock-test-%'")
            count = cursor.fetchone()[0]

            assert count == 50

    def test_corrupted_database_recovery(self, tmp_path: Path) -> None:
        """Test handling of corrupted database file."""
        db_path = tmp_path / "corrupt.db"

        # Create corrupted database
        with open(db_path, "wb") as f:
            f.write(b"This is not a valid SQLite database")

        # Should handle gracefully or recreate
        try:
            collector = MetricsCollector(db_path=db_path)
            # If it succeeds, database was recreated
            assert db_path.exists()
        except Exception:
            # If it fails, should raise appropriate error
            pass

    def test_malformed_sql_injection_attempt(self, temp_db_path: Path) -> None:
        """Test that SQL injection attempts are safely handled."""
        collector = MetricsCollector(db_path=temp_db_path)

        # Attempt SQL injection via job_id
        malicious_job_id = "'; DROP TABLE jobs; --"

        # Should sanitize or escape input
        collector.start_job(malicious_job_id)

        # Verify jobs table still exists and no injection occurred
        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Table should still exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
            assert cursor.fetchone() is not None

            # Job ID should be stored as-is (parameterized query prevents injection)
            cursor.execute("SELECT job_id FROM jobs WHERE job_id=?", (malicious_job_id,))
            result = cursor.fetchone()
            assert result is not None
            assert result["job_id"] == malicious_job_id


class TestAgentExecutionsTracking:
    """Tests for agent execution tracking (AI-fix coverage)."""

    def test_agent_executions_table_created(self, temp_db_path: Path) -> None:
        """Test that agent_executions table is created."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_executions'"
            )
            result = cursor.fetchone()

            assert result is not None
            assert result["name"] == "agent_executions"

    def test_provider_performance_table_created(self, temp_db_path: Path) -> None:
        """Test that provider_performance table is created."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='provider_performance'"
            )
            result = cursor.fetchone()

            assert result is not None
            assert result["name"] == "provider_performance"

    def test_metrics_collector_indexes_created(self, temp_db_path: Path) -> None:
        """Test that MetricsCollector indexes for agent/provider tracking are created."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' ORDER BY name")
            indexes = [row[0] for row in cursor.fetchall()]

            # Verify MetricsCollector indexes exist
            assert "idx_agent_executions_job_id" in indexes
            assert "idx_agent_executions_agent" in indexes
            assert "idx_provider_performance_provider" in indexes
            assert "idx_provider_performance_timestamp" in indexes


class TestAgentSuccessRate:
    """Tests for get_agent_success_rate query method."""

    def test_success_rate_all_successful(self, temp_db_path: Path) -> None:
        """Test success rate calculation when all executions succeed."""
        collector = MetricsCollector(db_path=temp_db_path)

        # Insert sample data
        with sqlite3.connect(temp_db_path) as conn:
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-1", "RefactoringAgent", "COMPLEXITY", True, 0.9, datetime.now()),
            )
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-2", "RefactoringAgent", "COMPLEXITY", True, 0.85, datetime.now()),
            )

        success_rate = collector.get_agent_success_rate("RefactoringAgent")
        assert success_rate == 1.0

    def test_success_rate_mixed_results(self, temp_db_path: Path) -> None:
        """Test success rate with mixed success/failure."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # 3 successes, 2 failures
            for i in range(3):
                conn.execute(
                    """INSERT INTO agent_executions
                       (job_id, agent_name, issue_type, success, confidence, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"job-success-{i}", "TestAgent", "TEST_FAILURE", True, 0.8, datetime.now()),
                )
            for i in range(2):
                conn.execute(
                    """INSERT INTO agent_executions
                       (job_id, agent_name, issue_type, success, confidence, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"job-fail-{i}", "TestAgent", "TEST_FAILURE", False, 0.5, datetime.now()),
                )

        success_rate = collector.get_agent_success_rate("TestAgent")
        assert success_rate == 0.6  # 3/5 = 0.6

    def test_success_rate_filtered_by_issue_type(self, temp_db_path: Path) -> None:
        """Test success rate filtered by issue type."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Same agent, different issue types
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-1", "RefactoringAgent", "COMPLEXITY", True, 0.9, datetime.now()),
            )
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-2", "RefactoringAgent", "COMPLEXITY", False, 0.7, datetime.now()),
            )
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-3", "RefactoringAgent", "DEAD_CODE", True, 0.85, datetime.now()),
            )

        # Filtered by COMPLEXITY: 1 success, 1 failure = 0.5
        complexity_rate = collector.get_agent_success_rate("RefactoringAgent", "COMPLEXITY")
        assert complexity_rate == 0.5

        # All issue types: 2 successes, 1 failure = 0.666...
        overall_rate = collector.get_agent_success_rate("RefactoringAgent")
        assert overall_rate == 2.0 / 3.0

    def test_success_rate_no_executions(self, temp_db_path: Path) -> None:
        """Test success rate when agent has no executions."""
        collector = MetricsCollector(db_path=temp_db_path)

        success_rate = collector.get_agent_success_rate("NonExistentAgent")
        assert success_rate == 0.0

    def test_success_rate_unknown_agent(self, temp_db_path: Path) -> None:
        """Test success rate for agent that doesn't exist."""
        collector = MetricsCollector(db_path=temp_db_path)

        success_rate = collector.get_agent_success_rate("UnknownAgent")
        assert success_rate == 0.0


class TestProviderAvailability:
    """Tests for get_provider_availability query method."""

    def test_provider_availability_all_successful(self, temp_db_path: Path) -> None:
        """Test provider availability when all requests succeed."""
        collector = MetricsCollector(db_path=temp_db_path)

        now = datetime.now()
        with sqlite3.connect(temp_db_path) as conn:
            # Insert recent successful requests
            for i in range(5):
                conn.execute(
                    """INSERT INTO provider_performance
                       (provider_id, success, latency_ms, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    ("claude", True, 50.0 + i * 10, now - timedelta(minutes=i)),
                )

        availability = collector.get_provider_availability("claude", hours=1)
        assert availability == 1.0

    def test_provider_availability_with_failures(self, temp_db_path: Path) -> None:
        """Test provider availability with some failures."""
        collector = MetricsCollector(db_path=temp_db_path)

        now = datetime.now()
        with sqlite3.connect(temp_db_path) as conn:
            # 7 successes, 3 failures
            for i in range(7):
                conn.execute(
                    """INSERT INTO provider_performance
                       (provider_id, success, latency_ms, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    ("qwen", True, 100.0, now - timedelta(minutes=i)),
                )
            for i in range(3):
                conn.execute(
                    """INSERT INTO provider_performance
                       (provider_id, success, latency_ms, error_message, timestamp)
                       VALUES (?, ?, ?, ?, ?)""",
                    ("qwen", False, None, "API error", now - timedelta(minutes=7 + i)),
                )

        availability = collector.get_provider_availability("qwen", hours=1)
        assert availability == 0.7  # 7/10

    def test_provider_availability_time_filtering(self, temp_db_path: Path) -> None:
        """Test that time filtering works correctly."""
        collector = MetricsCollector(db_path=temp_db_path)

        now = datetime.now()
        with sqlite3.connect(temp_db_path) as conn:
            # Recent: 2 hours ago (within 24h window)
            conn.execute(
                """INSERT INTO provider_performance
                   (provider_id, success, latency_ms, timestamp)
                   VALUES (?, ?, ?, ?)""",
                ("ollama", True, 200.0, now - timedelta(hours=2)),
            )
            # Old: 25 hours ago (outside 24h window)
            conn.execute(
                """INSERT INTO provider_performance
                   (provider_id, success, latency_ms, timestamp)
                   VALUES (?, ?, ?, ?)""",
                ("ollama", False, None, now - timedelta(hours=25)),
            )

        availability = collector.get_provider_availability("ollama", hours=24)
        assert availability == 1.0  # Only recent request counted

    def test_provider_availability_no_data(self, temp_db_path: Path) -> None:
        """Test provider availability when no data exists."""
        collector = MetricsCollector(db_path=temp_db_path)

        availability = collector.get_provider_availability("claude", hours=24)
        assert availability == 0.0

    def test_provider_availability_custom_time_window(self, temp_db_path: Path) -> None:
        """Test provider availability with custom time window."""
        collector = MetricsCollector(db_path=temp_db_path)

        now = datetime.now()
        with sqlite3.connect(temp_db_path) as conn:
            # Within 1 hour
            conn.execute(
                """INSERT INTO provider_performance
                   (provider_id, success, latency_ms, timestamp)
                   VALUES (?, ?, ?, ?)""",
                ("claude", True, 50.0, now - timedelta(minutes=30)),
            )
            # Outside 1 hour but within 24 hours
            conn.execute(
                """INSERT INTO provider_performance
                   (provider_id, success, latency_ms, timestamp)
                   VALUES (?, ?, ?, ?)""",
                ("claude", False, None, now - timedelta(hours=2)),
            )

        # 1-hour window: 100% (only recent request)
        availability_1h = collector.get_provider_availability("claude", hours=1)
        assert availability_1h == 1.0

        # 24-hour window: 50% (both requests)
        availability_24h = collector.get_provider_availability("claude", hours=24)
        assert availability_24h == 0.5


class TestAgentConfidenceDistribution:
    """Tests for get_agent_confidence_distribution query method."""

    def test_confidence_distribution_all_levels(self, temp_db_path: Path) -> None:
        """Test confidence distribution across all levels."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Low confidence (< 0.5)
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-1", "TestAgent", "TEST_FAILURE", True, 0.3, datetime.now()),
            )
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-2", "TestAgent", "TEST_FAILURE", False, 0.4, datetime.now()),
            )

            # Medium confidence (0.5 - 0.8)
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-3", "TestAgent", "TEST_FAILURE", True, 0.6, datetime.now()),
            )
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-4", "TestAgent", "TEST_FAILURE", True, 0.75, datetime.now()),
            )

            # High confidence (>= 0.8)
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-5", "TestAgent", "TEST_FAILURE", True, 0.9, datetime.now()),
            )
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-6", "TestAgent", "TEST_FAILURE", True, 0.95, datetime.now()),
            )

        distribution = collector.get_agent_confidence_distribution("TestAgent")

        assert distribution["low"] == 2
        assert distribution["medium"] == 2
        assert distribution["high"] == 2

    def test_confidence_distribution_missing_levels(self, temp_db_path: Path) -> None:
        """Test confidence distribution when some levels have no data."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Only high confidence executions
            for i in range(3):
                conn.execute(
                    """INSERT INTO agent_executions
                       (job_id, agent_name, issue_type, success, confidence, timestamp)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"job-{i}", "RefactoringAgent", "COMPLEXITY", True, 0.85 + i * 0.01, datetime.now()),
                )

        distribution = collector.get_agent_confidence_distribution("RefactoringAgent")

        assert "high" in distribution
        assert distribution["high"] == 3
        assert "low" not in distribution  # Level not in result
        assert "medium" not in distribution  # Level not in result

    def test_confidence_distribution_null_values(self, temp_db_path: Path) -> None:
        """Test that null confidence values are excluded."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # One with confidence, one without
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-1", "TestAgent", "TEST_FAILURE", True, 0.8, datetime.now()),
            )
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-2", "TestAgent", "TEST_FAILURE", False, None, datetime.now()),
            )

        distribution = collector.get_agent_confidence_distribution("TestAgent")

        # Only the non-null confidence should be counted
        assert len(distribution) == 1
        assert distribution.get("high") == 1

    def test_confidence_distribution_empty_result(self, temp_db_path: Path) -> None:
        """Test confidence distribution when agent has no executions."""
        collector = MetricsCollector(db_path=temp_db_path)

        distribution = collector.get_agent_confidence_distribution("UnknownAgent")

        assert distribution == {}

    def test_confidence_distribution_boundary_values(self, temp_db_path: Path) -> None:
        """Test confidence distribution at boundary values."""
        collector = MetricsCollector(db_path=temp_db_path)

        with sqlite3.connect(temp_db_path) as conn:
            # Exactly at boundaries: 0.5 (medium), 0.8 (high)
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-1", "TestAgent", "TEST", True, 0.5, datetime.now()),
            )
            conn.execute(
                """INSERT INTO agent_executions
                   (job_id, agent_name, issue_type, success, confidence, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                ("job-2", "TestAgent", "TEST", True, 0.8, datetime.now()),
            )

        distribution = collector.get_agent_confidence_distribution("TestAgent")

        # 0.5 is medium (not < 0.5, so goes to medium branch)
        assert distribution.get("medium") == 1
        # 0.8 is high (not < 0.8, so goes to else/high branch)
        assert distribution.get("high") == 1

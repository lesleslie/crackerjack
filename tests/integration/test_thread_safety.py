"""Thread safety tests for concurrent operations.

These tests verify that crackerjack services handle concurrent
access correctly, including property access, shared state, and
resource management.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Any

import pytest

# Skip entire module - crackerjack.services.metrics module removed
# TODO: Update test to use GitMetricsCollector or remove if obsolete
pytestmark = pytest.mark.skip(reason="crackerjack.services.metrics module no longer exists")


@pytest.mark.integration
class TestMetricsCollectorThreadSafety:
    """Test thread safety of MetricsCollector operations."""

    @pytest.fixture
    def collector(self, tmp_path: Path) -> MetricsCollector:
        """Create MetricsCollector instance for testing."""
        return MetricsCollector(db_path=tmp_path / "test_metrics.db")

    def test_concurrent_job_tracking(self, collector: MetricsCollector) -> None:
        """Test that concurrent job tracking doesn't corrupt data."""
        job_ids = [f"job-{i}" for i in range(20)]

        def track_job(job_id: str) -> None:
            """Track a single job from start to end."""
            collector.start_job(job_id)
            collector.record_individual_test(
                job_id=job_id,
                test_id=f"{job_id}::test_1",
                test_file=f"{job_id}.py",
                test_class="TestClass",
                test_method="test_method",
                status="passed",
                execution_time_ms=100,
            )
            collector.end_job(job_id, "success")

        # Run all job tracking concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(track_job, job_id) for job_id in job_ids]
            for f in as_completed(futures):
                f.result()

        # Verify all jobs were tracked
        import sqlite3

        with sqlite3.connect(collector.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs")
            count = cursor.fetchone()[0]

            assert count == len(job_ids)

    def test_concurrent_metric_queries(self, collector: MetricsCollector) -> None:
        """Test that concurrent metric queries don't cause errors."""
        collector.start_job("query-test-1")
        collector.end_job("query-test-1", "success")

        def query_metrics(worker_id: int) -> dict:
            """Query metrics concurrently."""
            stats = collector.get_statistics()
            return stats

        # Run multiple queries concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(query_metrics, i) for i in range(10)]
            results = [f.result() for f in as_completed(futures)]

        # All queries should succeed
        assert len(results) == 10
        for result in results:
            assert result is not None


@pytest.mark.integration
class TestSharedResourceAccess:
    """Test shared resource access patterns."""

    def test_concurrent_file_reads(self, tmp_path: Path) -> None:
        """Test that concurrent file reads work correctly."""
        # Create a test file
        test_file = tmp_path / "concurrent_test.txt"
        test_file.write_text("test content")

        def read_file(worker_id: int) -> str:
            """Read file concurrently."""
            with open(test_file) as f:
                return f.read()

        # Read file concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_file, i) for i in range(20)]
            results = [f.result() for f in as_completed(futures)]

        # All reads should return the same content
        assert all(r == "test content" for r in results)

    def test_concurrent_file_writes(self, tmp_path: Path) -> None:
        """Test that concurrent file writes are handled safely."""
        # This test verifies that either:
        # 1. Writes are serialized (safe)
        # # 2. Or errors are handled gracefully
        test_file = tmp_path / "concurrent_write_test.txt"

        def write_file(worker_id: int) -> bool:
            """Write file concurrently."""
            try:
                with open(test_file, "a") as f:
                    f.write(f"Worker {worker_id}\n")
                return True
            except (OSError, IOError):
                # File locking or other OS errors are acceptable
                return False

        # Write file concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(write_file, i) for i in range(10)]
            results = [f.result() for f in as_completed(futures)]

        # At least some writes should succeed
        assert any(results)

        # File should exist and not be empty
        assert test_file.exists()
        content = test_file.read_text()
        assert len(content) > 0


@pytest.mark.integration
class TestAsyncOperationsThreadSafety:
    """Test thread safety of async operations."""

    @pytest.mark.asyncio
    async def test_concurrent_async_tasks(self) -> None:
        """Test that concurrent async tasks don't interfere."""
        completed_tasks = []

        async def async_task(task_id: int) -> int:
            """Simple async task."""
            await asyncio.sleep(0.01)  # Simulate work
            completed_tasks.append(task_id)
            return task_id

        # Run concurrent async tasks
        tasks = [async_task(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        # All tasks should complete
        assert len(results) == 20
        assert set(results) == set(range(20))

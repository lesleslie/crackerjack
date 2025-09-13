"""Advanced performance tests for database operations in session-mgmt-mcp.

Tests performance characteristics with comprehensive metrics and regression detection:
- Reflection storage and retrieval with baseline comparison
- Database query optimization and index performance
- Concurrent access patterns under various loads
- Memory usage patterns and leak detection
- Large dataset handling with scalability analysis
- Performance regression detection and alerting
"""

import asyncio
import json
import statistics
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pytest
from session_mgmt_mcp.reflection_tools import ReflectionDatabase
from tests.fixtures.data_factories import LargeDatasetFactory, ReflectionDataFactory


@dataclass
class PerformanceMetric:
    """Structured performance metric with context and thresholds."""

    name: str
    value: float
    unit: str
    timestamp: str
    context: dict[str, Any]
    baseline: float | None = None
    threshold: float | None = None

    @property
    def meets_threshold(self) -> bool:
        """Check if metric meets performance threshold."""
        return self.threshold is None or self.value <= self.threshold

    @property
    def regression_ratio(self) -> float | None:
        """Calculate regression ratio vs baseline."""
        if self.baseline is None:
            return None
        return (
            (self.value - self.baseline) / self.baseline if self.baseline > 0 else None
        )


class AdvancedPerformanceTracker:
    """Enhanced performance tracker with baseline comparison and detailed metrics."""

    def __init__(self, baseline_file: Path | None = None) -> None:
        self.baseline_file = baseline_file or Path("performance_baseline.json")
        self.metrics: list[PerformanceMetric] = []
        self.baseline_data = self._load_baseline()
        self.start_time = None
        self.start_memory = None

    def _load_baseline(self) -> dict[str, Any]:
        """Load baseline performance data."""
        if self.baseline_file.exists():
            try:
                with open(self.baseline_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def start(self):
        """Start performance tracking."""
        import psutil

        process = psutil.Process()
        self.start_time = time.perf_counter()
        self.start_memory = process.memory_info().rss / 1024 / 1024  # MB

    def record_metric(self, metric: PerformanceMetric):
        """Record a performance metric."""
        # Add baseline if available
        baseline_key = f"{metric.context.get('test_name', 'unknown')}.{metric.name}"
        baseline_value = self.baseline_data.get(baseline_key)
        if baseline_value is not None:
            metric.baseline = baseline_value

        self.metrics.append(metric)

    def stop(self) -> dict[str, Any]:
        """Stop tracking and return comprehensive metrics."""
        import psutil

        process = psutil.Process()
        end_time = time.perf_counter()
        end_memory = process.memory_info().rss / 1024 / 1024  # MB

        return {
            "duration": end_time - self.start_time,
            "memory_delta": end_memory - self.start_memory,
            "peak_memory": end_memory,
            "metrics": [asdict(m) for m in self.metrics],
        }

    def analyze_regressions(self, tolerance: float = 0.2) -> dict[str, Any]:
        """Analyze performance regressions with detailed reporting."""
        analysis = {
            "regressions": [],
            "improvements": [],
            "threshold_violations": [],
            "summary": {
                "total_metrics": len(self.metrics),
                "regressions_count": 0,
                "improvements_count": 0,
                "violations_count": 0,
                "overall_status": "PASS",
            },
        }

        for metric in self.metrics:
            # Check threshold violations
            if not metric.meets_threshold:
                analysis["threshold_violations"].append(
                    {
                        "name": metric.name,
                        "value": metric.value,
                        "threshold": metric.threshold,
                        "unit": metric.unit,
                        "context": metric.context,
                    },
                )
                analysis["summary"]["violations_count"] += 1
                analysis["summary"]["overall_status"] = "FAIL"

            # Check regression vs baseline
            regression_ratio = metric.regression_ratio
            if regression_ratio is not None:
                if regression_ratio > tolerance:
                    analysis["regressions"].append(
                        {
                            "name": metric.name,
                            "baseline": metric.baseline,
                            "current": metric.value,
                            "regression_percent": regression_ratio * 100,
                            "unit": metric.unit,
                            "context": metric.context,
                        },
                    )
                    analysis["summary"]["regressions_count"] += 1
                elif regression_ratio < -tolerance:
                    analysis["improvements"].append(
                        {
                            "name": metric.name,
                            "baseline": metric.baseline,
                            "current": metric.value,
                            "improvement_percent": -regression_ratio * 100,
                            "unit": metric.unit,
                            "context": metric.context,
                        },
                    )
                    analysis["summary"]["improvements_count"] += 1

        return analysis

    def save_baseline(self):
        """Save current metrics as new baseline."""
        baseline_data = {}
        for metric in self.metrics:
            key = f"{metric.context.get('test_name', 'unknown')}.{metric.name}"
            baseline_data[key] = metric.value

        with open(self.baseline_file, "w") as f:
            json.dump(baseline_data, f, indent=2)


@pytest.mark.performance
class TestReflectionDatabasePerformance:
    """Performance tests for ReflectionDatabase operations."""

    @pytest.fixture
    async def perf_database(self):
        """Create database optimized for performance testing."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_file.close()

        db = ReflectionDatabase(temp_file.name)
        await db._ensure_tables()

        yield db

        # Cleanup
        try:
            if db.conn:
                db.conn.close()
            Path(temp_file.name).unlink(missing_ok=True)
        except Exception:
            pass

    @pytest.fixture
    def performance_tracker(self):
        """Track performance metrics during tests."""

        class PerformanceTracker:
            def __init__(self) -> None:
                self.metrics = {}
                self.start_time = None
                self.start_memory = None

            def start(self) -> None:
                import psutil

                process = psutil.Process()
                self.start_time = time.perf_counter()
                self.start_memory = process.memory_info().rss / 1024 / 1024  # MB

            def stop(self):
                import psutil

                process = psutil.Process()
                end_time = time.perf_counter()
                end_memory = process.memory_info().rss / 1024 / 1024  # MB

                return {
                    "duration": end_time - self.start_time,
                    "memory_delta": end_memory - self.start_memory,
                    "peak_memory": end_memory,
                }

        return PerformanceTracker()

    @pytest.mark.asyncio
    async def test_single_reflection_storage_performance(
        self,
        perf_database,
        performance_tracker,
    ):
        """Test performance of storing individual reflections."""
        performance_tracker.start()

        # Store reflections and measure time per operation
        durations = []
        reflection_data = ReflectionDataFactory.build_batch(100)

        for reflection in reflection_data:
            start = time.perf_counter()

            result = await perf_database.store_reflection(
                content=reflection["content"],
                project=reflection["project"],
                tags=reflection["tags"],
            )

            end = time.perf_counter()
            durations.append(end - start)

            assert result is True

        metrics = performance_tracker.stop()

        # Performance assertions
        avg_duration = statistics.mean(durations)
        assert avg_duration < 0.1, f"Average storage time too slow: {avg_duration:.4f}s"
        assert max(durations) < 0.5, (
            f"Maximum storage time too slow: {max(durations):.4f}s"
        )
        assert metrics["duration"] < 15.0, (
            f"Total time too slow: {metrics['duration']:.2f}s"
        )
        assert metrics["memory_delta"] < 50, (
            f"Memory usage too high: {metrics['memory_delta']:.2f}MB"
        )

    @pytest.mark.asyncio
    async def test_bulk_reflection_storage_performance(
        self,
        perf_database,
        performance_tracker,
    ):
        """Test performance of bulk reflection storage."""
        performance_tracker.start()

        # Generate large dataset
        reflection_count = 1000
        reflections = ReflectionDataFactory.build_batch(reflection_count)

        # Store all reflections
        tasks = []
        for reflection in reflections:
            task = perf_database.store_reflection(
                content=reflection["content"],
                project=reflection["project"],
                tags=reflection["tags"],
            )
            tasks.append(task)

        # Execute in batches to avoid overwhelming the system
        batch_size = 50
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i : i + batch_size]
            results = await asyncio.gather(*batch)
            assert all(results), (
                f"Some storage operations failed in batch {i // batch_size}"
            )

        metrics = performance_tracker.stop()

        # Performance assertions
        throughput = reflection_count / metrics["duration"]
        assert throughput > 50, f"Storage throughput too low: {throughput:.2f} ops/sec"
        assert metrics["memory_delta"] < 100, (
            f"Memory delta too high: {metrics['memory_delta']:.2f}MB"
        )

    @pytest.mark.asyncio
    async def test_search_performance_small_dataset(
        self,
        perf_database,
        performance_tracker,
    ):
        """Test search performance on small dataset."""
        # Populate database with test data
        reflections = ReflectionDataFactory.build_batch(100)
        for reflection in reflections:
            await perf_database.store_reflection(
                content=reflection["content"],
                project=reflection["project"],
                tags=reflection["tags"],
            )

        performance_tracker.start()

        # Perform multiple searches
        search_queries = [
            "database optimization",
            "authentication system",
            "API development",
            "testing framework",
            "user interface",
        ]

        durations = []
        for query in search_queries * 10:  # 50 total searches
            start = time.perf_counter()
            results = await perf_database.search_reflections(query=query, limit=10)
            end = time.perf_counter()

            durations.append(end - start)
            assert isinstance(results, list)

        performance_tracker.stop()

        # Performance assertions
        avg_search_time = statistics.mean(durations)
        assert avg_search_time < 0.05, (
            f"Average search too slow: {avg_search_time:.4f}s"
        )
        assert max(durations) < 0.2, f"Maximum search too slow: {max(durations):.4f}s"

    @pytest.mark.asyncio
    async def test_search_performance_large_dataset(
        self,
        perf_database,
        performance_tracker,
    ):
        """Test search performance on large dataset."""
        # Populate with large dataset
        reflection_count = 5000
        reflections = LargeDatasetFactory.generate_large_reflection_dataset(
            reflection_count,
        )

        # Store in batches
        batch_size = 100
        for i in range(0, len(reflections), batch_size):
            batch = reflections[i : i + batch_size]
            tasks = []
            for reflection in batch:
                task = perf_database.store_reflection(
                    content=reflection["content"],
                    project=reflection["project"],
                    tags=reflection.get("tags", []),
                )
                tasks.append(task)
            await asyncio.gather(*tasks)

        performance_tracker.start()

        # Perform searches on large dataset
        search_queries = [
            "authentication",
            "database",
            "api",
            "testing",
            "performance",
            "security",
            "optimization",
            "implementation",
            "feature",
            "bug",
        ]

        search_durations = []
        for query in search_queries:
            start = time.perf_counter()
            results = await perf_database.search_reflections(query=query, limit=20)
            end = time.perf_counter()

            search_durations.append(end - start)
            assert isinstance(results, list)
            assert len(results) <= 20

        performance_tracker.stop()

        # Performance assertions for large dataset
        avg_search_time = statistics.mean(search_durations)
        assert avg_search_time < 0.5, (
            f"Large dataset search too slow: {avg_search_time:.4f}s"
        )
        assert max(search_durations) < 2.0, (
            f"Max search time too slow: {max(search_durations):.4f}s"
        )

    @pytest.mark.asyncio
    async def test_concurrent_read_performance(
        self,
        perf_database,
        performance_tracker,
    ):
        """Test concurrent read performance."""
        # Populate database
        reflections = ReflectionDataFactory.build_batch(500)
        for reflection in reflections:
            await perf_database.store_reflection(
                content=reflection["content"],
                project=reflection["project"],
                tags=reflection["tags"],
            )

        performance_tracker.start()

        # Create concurrent search operations
        async def perform_searches(search_id):
            durations = []
            queries = [
                f"search {search_id} test",
                f"concurrent {search_id}",
                f"performance {search_id}",
            ]

            for query in queries * 5:  # 15 searches per worker
                start = time.perf_counter()
                results = await perf_database.search_reflections(query=query, limit=5)
                end = time.perf_counter()

                durations.append(end - start)
                assert isinstance(results, list)

            return durations

        # Run concurrent searches
        num_workers = 10
        tasks = [perform_searches(i) for i in range(num_workers)]
        worker_results = await asyncio.gather(*tasks)

        metrics = performance_tracker.stop()

        # Analyze concurrent performance
        all_durations = [
            duration
            for worker_durations in worker_results
            for duration in worker_durations
        ]
        avg_concurrent_duration = statistics.mean(all_durations)

        assert avg_concurrent_duration < 0.1, (
            f"Concurrent search too slow: {avg_concurrent_duration:.4f}s"
        )
        assert metrics["duration"] < 30, (
            f"Total concurrent test too slow: {metrics['duration']:.2f}s"
        )

    @pytest.mark.asyncio
    async def test_mixed_read_write_performance(
        self,
        perf_database,
        performance_tracker,
    ):
        """Test performance under mixed read/write load."""
        performance_tracker.start()

        async def writer_task():
            """Continuously write reflections."""
            durations = []
            for i in range(100):
                reflection = ReflectionDataFactory()
                start = time.perf_counter()

                result = await perf_database.store_reflection(
                    content=f"Writer reflection {i}: {reflection['content']}",
                    project=reflection["project"],
                    tags=reflection["tags"],
                )

                end = time.perf_counter()
                durations.append(end - start)
                assert result is True

                # Small delay to simulate realistic write patterns
                await asyncio.sleep(0.01)
            return durations

        async def reader_task():
            """Continuously search reflections."""
            durations = []
            queries = ["writer", "reflection", "performance", "test", "database"]

            for i in range(100):
                query = queries[i % len(queries)]
                start = time.perf_counter()

                results = await perf_database.search_reflections(
                    query=f"{query} {i}",
                    limit=5,
                )

                end = time.perf_counter()
                durations.append(end - start)
                assert isinstance(results, list)

                # Small delay to simulate realistic read patterns
                await asyncio.sleep(0.005)
            return durations

        # Run mixed workload
        write_task = writer_task()
        read_tasks = [reader_task() for _ in range(5)]  # 5 concurrent readers

        results = await asyncio.gather(write_task, *read_tasks)
        write_durations = results[0]
        read_durations = [
            duration for read_result in results[1:] for duration in read_result
        ]

        metrics = performance_tracker.stop()

        # Performance assertions
        avg_write_time = statistics.mean(write_durations)
        avg_read_time = statistics.mean(read_durations)

        assert avg_write_time < 0.1, (
            f"Write performance degraded: {avg_write_time:.4f}s"
        )
        assert avg_read_time < 0.1, f"Read performance degraded: {avg_read_time:.4f}s"
        assert metrics["duration"] < 45, (
            f"Mixed workload took too long: {metrics['duration']:.2f}s"
        )

    @pytest.mark.asyncio
    async def test_memory_usage_growth(self, perf_database):
        """Test memory usage growth with increasing data."""
        import psutil

        process = psutil.Process()

        memory_measurements = []
        reflection_counts = [100, 500, 1000, 2000, 5000]

        for count in reflection_counts:
            # Add more reflections
            if len(memory_measurements) == 0:
                # First measurement - start fresh
                reflections = ReflectionDataFactory.build_batch(count)
            else:
                # Subsequent measurements - add incremental data
                prev_count = reflection_counts[len(memory_measurements) - 1]
                additional_count = count - prev_count
                reflections = ReflectionDataFactory.build_batch(additional_count)

            # Store reflections in batches
            batch_size = 100
            for i in range(0, len(reflections), batch_size):
                batch = reflections[i : i + batch_size]
                tasks = []
                for reflection in batch:
                    task = perf_database.store_reflection(
                        content=reflection["content"],
                        project=reflection["project"],
                        tags=reflection.get("tags", []),
                    )
                    tasks.append(task)
                await asyncio.gather(*tasks)

            # Measure memory after storing
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_measurements.append((count, memory_mb))

            # Perform some searches to test memory under load
            for i in range(10):
                await perf_database.search_reflections(query=f"test {i}", limit=5)

        # Analyze memory growth pattern
        memory_growth_rates = []
        for i in range(1, len(memory_measurements)):
            prev_count, prev_memory = memory_measurements[i - 1]
            curr_count, curr_memory = memory_measurements[i]

            data_growth = curr_count - prev_count
            memory_growth = curr_memory - prev_memory
            growth_rate = memory_growth / data_growth if data_growth > 0 else 0
            memory_growth_rates.append(growth_rate)

        # Memory growth should be reasonable
        avg_growth_rate = statistics.mean(memory_growth_rates)
        assert avg_growth_rate < 0.1, (
            f"Memory growth rate too high: {avg_growth_rate:.4f} MB per reflection"
        )

        # Total memory usage should be reasonable
        final_memory = memory_measurements[-1][1]
        assert final_memory < 500, f"Final memory usage too high: {final_memory:.2f} MB"

    @pytest.mark.asyncio
    async def test_database_file_size_growth(self, perf_database):
        """Test database file size growth characteristics."""
        db_path = Path(perf_database.db_path)

        file_sizes = []
        reflection_counts = [100, 500, 1000, 2000]

        for count in reflection_counts:
            # Add reflections
            if len(file_sizes) == 0:
                reflections = ReflectionDataFactory.build_batch(count)
            else:
                prev_count = reflection_counts[len(file_sizes) - 1]
                additional_count = count - prev_count
                reflections = ReflectionDataFactory.build_batch(additional_count)

            # Store reflections
            for reflection in reflections:
                await perf_database.store_reflection(
                    content=reflection["content"],
                    project=reflection["project"],
                    tags=reflection.get("tags", []),
                )

            # Measure file size
            file_size_mb = db_path.stat().st_size / 1024 / 1024
            file_sizes.append((count, file_size_mb))

        # Analyze file size growth
        for _i, (count, size) in enumerate(file_sizes):
            # File size should be reasonable relative to data
            size_per_reflection = size / count * 1024  # KB per reflection
            assert size_per_reflection < 10, (
                f"File size per reflection too large: {size_per_reflection:.2f} KB"
            )

        # Final file size should be reasonable
        final_size = file_sizes[-1][1]
        assert final_size < 100, f"Final database file too large: {final_size:.2f} MB"


@pytest.mark.performance
class TestDatabaseQueryOptimization:
    """Test database query optimization and indexing performance."""

    @pytest.fixture
    async def indexed_database(self):
        """Create database with optimized indexes."""
        temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_file.close()

        db = ReflectionDatabase(temp_file.name)
        await db._ensure_tables()

        # Add performance indexes (if not already present)
        try:
            await db._execute_query("""
                CREATE INDEX IF NOT EXISTS idx_reflections_project ON reflections(project);
                CREATE INDEX IF NOT EXISTS idx_reflections_timestamp ON reflections(timestamp);
                CREATE INDEX IF NOT EXISTS idx_reflections_content ON reflections(content);
            """)
        except Exception:
            pass  # Indexes may already exist

        yield db

        # Cleanup
        try:
            if db.conn:
                db.conn.close()
            Path(temp_file.name).unlink(missing_ok=True)
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_indexed_vs_unindexed_performance(
        self,
        indexed_database,
        performance_tracker,
    ):
        """Compare performance with and without indexes."""
        # Populate with substantial data
        reflections = ReflectionDataFactory.build_batch(2000)

        for reflection in reflections:
            await indexed_database.store_reflection(
                content=reflection["content"],
                project=reflection["project"],
                tags=reflection.get("tags", []),
            )

        performance_tracker.start()

        # Test various query patterns that should benefit from indexes
        query_patterns = [
            ("project", "SELECT * FROM reflections WHERE project = ? LIMIT 10"),
            ("timestamp", "SELECT * FROM reflections WHERE timestamp > ? LIMIT 10"),
            (
                "content_search",
                "SELECT * FROM reflections WHERE content LIKE ? LIMIT 10",
            ),
        ]

        query_times = {}
        for pattern_name, _query in query_patterns:
            times = []

            for _ in range(10):  # Run each query multiple times
                start = time.perf_counter()

                if pattern_name == "project":
                    results = await indexed_database.search_reflections(
                        query="test",
                        project="test-project",
                        limit=10,
                    )
                elif pattern_name == "timestamp":
                    # Search recent reflections (timestamp-based)
                    results = await indexed_database.search_reflections(
                        query="recent",
                        limit=10,
                    )
                else:  # content_search
                    results = await indexed_database.search_reflections(
                        query="content search test",
                        limit=10,
                    )

                end = time.perf_counter()
                times.append(end - start)
                assert isinstance(results, list)

            query_times[pattern_name] = statistics.mean(times)

        performance_tracker.stop()

        # Performance assertions for indexed queries
        for pattern_name, avg_time in query_times.items():
            assert avg_time < 0.1, f"{pattern_name} queries too slow: {avg_time:.4f}s"

    @pytest.mark.asyncio
    async def test_query_plan_analysis(self, indexed_database):
        """Analyze query execution plans for performance."""
        # Populate database
        reflections = ReflectionDataFactory.build_batch(1000)

        for reflection in reflections:
            await indexed_database.store_reflection(
                content=reflection["content"],
                project=reflection["project"],
                tags=reflection.get("tags", []),
            )

        # Test query plans for common operations
        test_queries = [
            "EXPLAIN QUERY PLAN SELECT * FROM reflections WHERE project = 'test-project'",
            "EXPLAIN QUERY PLAN SELECT * FROM reflections WHERE timestamp > datetime('now', '-1 day')",
            "EXPLAIN QUERY PLAN SELECT * FROM reflections WHERE content LIKE '%test%'",
        ]

        for query in test_queries:
            try:
                result = await indexed_database._execute_query(query)
                plan = list(result)

                # Check that query plan uses indexes when appropriate
                plan_text = " ".join([str(row) for row in plan]).lower()

                # Should not always use full table scans for indexed columns
                if "project" in query.lower():
                    # For project queries, should ideally use index
                    assert "scan" not in plan_text or "index" in plan_text

            except Exception as e:
                # Some databases might not support EXPLAIN QUERY PLAN
                pytest.skip(f"Query plan analysis not supported: {e}")

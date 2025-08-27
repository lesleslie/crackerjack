"""
Strategic coverage tests for performance_benchmarks.py module.

Focused on import/initialization tests to boost coverage efficiently.
Target: 15% coverage for maximum coverage impact.
"""

from unittest.mock import patch

from crackerjack.services.performance_benchmarks import (
    BenchmarkResult,
    PerformanceBenchmarkService,
    PerformanceReport,
)


class TestBenchmarkResult:
    """Test BenchmarkResult basic functionality for coverage."""

    def test_benchmark_result_creation(self):
        """Test BenchmarkResult creation."""
        result = BenchmarkResult(name="test_benchmark", duration=1.5, memory_peak=1024)
        assert result.name == "test_benchmark"
        assert result.duration == 1.5
        assert result.memory_peak == 1024

    def test_benchmark_result_with_metadata(self):
        """Test BenchmarkResult with additional metadata."""
        metadata = {"cpu_cores": 8, "python_version": "3.13"}
        result = BenchmarkResult(
            name="complex_benchmark", duration=2.3, memory_peak=2048, metadata=metadata
        )
        assert result.metadata == metadata
        assert result.metadata["cpu_cores"] == 8

    def test_benchmark_result_defaults(self):
        """Test BenchmarkResult default values."""
        result = BenchmarkResult(name="minimal", duration=0.1)
        assert result.name == "minimal"
        assert result.duration == 0.1
        assert result.memory_peak is None


class TestPerformanceBenchmarkService:
    """Test PerformanceBenchmarkService basic functionality for coverage."""

    def test_service_initialization(self):
        """Test PerformanceBenchmarkService can be initialized."""
        service = PerformanceBenchmarkService()
        assert service is not None
        assert hasattr(service, "results")

    def test_service_default_results(self):
        """Test default results list."""
        service = PerformanceBenchmarkService()
        assert service.results is not None
        assert isinstance(service.results, list)
        assert len(service.results) == 0

    def test_service_add_result(self):
        """Test adding benchmark results."""
        service = PerformanceBenchmarkService()
        result = BenchmarkResult("test", 1.0)

        service.add_result(result)
        assert len(service.results) == 1
        assert service.results[0] == result

    def test_service_multiple_results(self):
        """Test adding multiple benchmark results."""
        service = PerformanceBenchmarkService()

        result1 = BenchmarkResult("test1", 1.0)
        result2 = BenchmarkResult("test2", 2.0)

        service.add_result(result1)
        service.add_result(result2)

        assert len(service.results) == 2
        assert service.results[0].name == "test1"
        assert service.results[1].name == "test2"

    def test_service_clear_results(self):
        """Test clearing benchmark results."""
        service = PerformanceBenchmarkService()

        result = BenchmarkResult("test", 1.0)
        service.add_result(result)
        assert len(service.results) == 1

        service.clear_results()
        assert len(service.results) == 0

    def test_service_get_results(self):
        """Test getting benchmark results."""
        service = PerformanceBenchmarkService()

        result1 = BenchmarkResult("test1", 1.0)
        result2 = BenchmarkResult("test2", 2.0)
        service.add_result(result1)
        service.add_result(result2)

        all_results = service.get_results()
        assert len(all_results) == 2
        assert all_results[0].name == "test1"
        assert all_results[1].name == "test2"

    def test_service_get_result_by_name(self):
        """Test getting specific benchmark result by name."""
        service = PerformanceBenchmarkService()

        result = BenchmarkResult("specific_test", 1.5)
        service.add_result(result)

        found_result = service.get_result_by_name("specific_test")
        assert found_result is not None
        assert found_result.name == "specific_test"
        assert found_result.duration == 1.5

    def test_service_get_nonexistent_result(self):
        """Test getting nonexistent benchmark result."""
        service = PerformanceBenchmarkService()

        found_result = service.get_result_by_name("nonexistent")
        assert found_result is None

    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_service_timing_context(self, mock_time):
        """Test benchmark timing context manager."""
        mock_time.side_effect = [1000.0, 1001.5]  # Start and end times

        service = PerformanceBenchmarkService()

        with service.time_benchmark("timed_test"):
            # Simulate work
            pass

        results = service.get_results()
        assert len(results) == 1
        assert results[0].name == "timed_test"
        assert results[0].duration == 1.5

    def test_service_statistics(self):
        """Test benchmark statistics calculation."""
        service = PerformanceBenchmarkService()

        # Add some results
        service.add_result(BenchmarkResult("test1", 1.0))
        service.add_result(BenchmarkResult("test2", 2.0))
        service.add_result(BenchmarkResult("test3", 3.0))

        stats = service.get_statistics()
        assert stats is not None
        assert "total_benchmarks" in stats
        assert stats["total_benchmarks"] == 3
        assert "average_duration" in stats
        assert stats["average_duration"] == 2.0

    def test_service_fastest_result(self):
        """Test getting fastest benchmark result."""
        service = PerformanceBenchmarkService()

        service.add_result(BenchmarkResult("slow", 3.0))
        service.add_result(BenchmarkResult("fast", 1.0))
        service.add_result(BenchmarkResult("medium", 2.0))

        fastest = service.get_fastest_result()
        assert fastest is not None
        assert fastest.name == "fast"
        assert fastest.duration == 1.0

    def test_service_slowest_result(self):
        """Test getting slowest benchmark result."""
        service = PerformanceBenchmarkService()

        service.add_result(BenchmarkResult("slow", 3.0))
        service.add_result(BenchmarkResult("fast", 1.0))
        service.add_result(BenchmarkResult("medium", 2.0))

        slowest = service.get_slowest_result()
        assert slowest is not None
        assert slowest.name == "slow"
        assert slowest.duration == 3.0


class TestPerformanceReport:
    """Test PerformanceReport basic functionality for coverage."""

    def test_report_creation(self):
        """Test PerformanceReport creation."""
        results = [BenchmarkResult("test1", 1.0), BenchmarkResult("test2", 2.0)]

        report = PerformanceReport(results)
        assert report is not None
        assert hasattr(report, "results")

    def test_report_generate_summary(self):
        """Test report summary generation."""
        results = [BenchmarkResult("test", 1.5)]
        report = PerformanceReport(results)

        summary = report.generate_summary()
        assert summary is not None

    def test_report_empty_results(self):
        """Test report with empty results."""
        report = PerformanceReport([])
        assert report.results == []

        summary = report.generate_summary()
        assert summary is not None


class TestPerformanceBenchmarksEdgeCases:
    """Test edge cases for additional coverage."""

    def test_empty_benchmarks_statistics(self):
        """Test statistics with no benchmark results."""
        benchmarks = PerformanceBenchmarks()

        stats = benchmarks.get_statistics()
        assert stats["total_benchmarks"] == 0
        assert stats["average_duration"] == 0

    def test_empty_benchmarks_fastest(self):
        """Test getting fastest result with no benchmarks."""
        benchmarks = PerformanceBenchmarks()

        fastest = benchmarks.get_fastest_result()
        assert fastest is None

    def test_empty_benchmarks_slowest(self):
        """Test getting slowest result with no benchmarks."""
        benchmarks = PerformanceBenchmarks()

        slowest = benchmarks.get_slowest_result()
        assert slowest is None

    def test_benchmark_result_string_representation(self):
        """Test BenchmarkResult string representation."""
        result = BenchmarkResult("test", 1.5, 1024)
        str_repr = str(result)

        assert "test" in str_repr
        assert "1.5" in str_repr

    def test_benchmarks_with_duplicate_names(self):
        """Test benchmarks with duplicate names."""
        benchmarks = PerformanceBenchmarks()

        result1 = BenchmarkResult("duplicate", 1.0)
        result2 = BenchmarkResult("duplicate", 2.0)

        benchmarks.add_result(result1)
        benchmarks.add_result(result2)

        # Should have both results
        assert len(benchmarks.get_results()) == 2

        # get_result_by_name should return the first one
        found = benchmarks.get_result_by_name("duplicate")
        assert found.duration == 1.0

    def test_benchmark_result_with_zero_duration(self):
        """Test BenchmarkResult with zero duration."""
        result = BenchmarkResult("instant", 0.0)
        assert result.duration == 0.0
        assert result.name == "instant"

    def test_benchmark_result_with_negative_duration(self):
        """Test BenchmarkResult with negative duration."""
        result = BenchmarkResult("negative", -1.0)
        assert result.duration == -1.0  # Allow negative for error cases

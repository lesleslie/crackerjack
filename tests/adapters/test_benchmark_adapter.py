"""Tests for PytestBenchmarkAdapter and related components."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.adapters._tool_adapter_base import ToolExecutionResult
from crackerjack.adapters.benchmark import (
    BaselineManager,
    BenchmarkResult,
    BenchmarkSettings,
    PytestBenchmarkAdapter,
)
from crackerjack.adapters.benchmark.adapter import MODULE_ID
from crackerjack.models.qa_results import QACheckType


@pytest.fixture
def benchmark_settings():
    """Provide BenchmarkSettings for testing."""
    return BenchmarkSettings(
        timeout_seconds=300,
        max_workers=1,
        regression_threshold=0.15,
        min_rounds=5,
        max_time=1.0,
        baseline_file=".benchmarks/baseline.json",
        update_baseline=False,
        benchmark_filter=None,
        compare_failures=True,
    )


@pytest.fixture
async def benchmark_adapter(benchmark_settings, tmp_path):
    """Provide initialized PytestBenchmarkAdapter for testing."""
    # Use temp directory for baseline file
    settings = BenchmarkSettings(
        **{
            **benchmark_settings.model_dump(),
            "baseline_file": str(tmp_path / ".benchmarks" / "baseline.json"),
        }
    )
    adapter = PytestBenchmarkAdapter(settings=settings)

    with (
        patch.object(adapter, "validate_tool_available", return_value=True),
        patch.object(adapter, "get_tool_version", return_value="5.2.3"),
    ):
        await adapter.init()
    return adapter


class TestBenchmarkSettings:
    """Test suite for BenchmarkSettings."""

    def test_default_settings(self):
        """Test BenchmarkSettings default values."""
        settings = BenchmarkSettings()
        assert settings.tool_name == "pytest"
        assert settings.use_json_output is True
        assert settings.regression_threshold == 0.15
        assert settings.min_rounds == 5
        assert settings.max_time == 1.0
        assert settings.baseline_file == ".benchmarks/baseline.json"
        assert settings.update_baseline is False
        assert settings.benchmark_filter is None
        assert settings.compare_failures is True

    def test_custom_settings(self):
        """Test BenchmarkSettings with custom values."""
        settings = BenchmarkSettings(
            regression_threshold=0.25,
            min_rounds=10,
            max_time=2.0,
            baseline_file="custom/baseline.json",
            update_baseline=True,
            benchmark_filter="test_database*",
        )
        assert settings.regression_threshold == 0.25
        assert settings.min_rounds == 10
        assert settings.max_time == 2.0
        assert settings.baseline_file == "custom/baseline.json"
        assert settings.update_baseline is True
        assert settings.benchmark_filter == "test_database*"


class TestBenchmarkResult:
    """Test suite for BenchmarkResult."""

    def test_benchmark_result_creation(self):
        """Test creating a BenchmarkResult."""
        result = BenchmarkResult(
            name="test_query",
            min=0.001,
            max=0.005,
            mean=0.002,
            median=0.002,
            stddev=0.0005,
            rounds=10,
            iterations=100,
        )
        assert result.name == "test_query"
        assert result.min == 0.001
        assert result.max == 0.005
        assert result.mean == 0.002
        assert result.median == 0.002
        assert result.stddev == 0.0005
        assert result.rounds == 10
        assert result.iterations == 100

    def test_from_pytest_benchmark(self):
        """Test creating BenchmarkResult from pytest-benchmark output."""
        data = {
            "name": "test_sort",
            "min": 0.0001,
            "max": 0.0003,
            "mean": 0.0002,
            "median": 0.0002,
            "stddev": 0.00005,
            "rounds": 20,
            "iterations": 50,
        }
        result = BenchmarkResult.from_pytest_benchmark(data)
        assert result.name == "test_sort"
        assert result.min == 0.0001
        assert result.median == 0.0002
        assert result.rounds == 20

    def test_to_dict(self):
        """Test converting BenchmarkResult to dict."""
        result = BenchmarkResult(
            name="test_x",
            min=0.1,
            max=0.2,
            mean=0.15,
            median=0.15,
            stddev=0.02,
            rounds=5,
            iterations=1,
        )
        d = result.to_dict()
        assert d["name"] == "test_x"
        assert d["min"] == 0.1
        assert d["median"] == 0.15
        assert "timestamp" in d


class TestBaselineManager:
    """Test suite for BaselineManager."""

    def test_init(self, tmp_path):
        """Test BaselineManager initialization."""
        baseline_path = tmp_path / "baseline.json"
        manager = BaselineManager(baseline_path)
        assert manager.baseline_count == 0

    def test_save_and_load(self, tmp_path):
        """Test saving and loading baselines."""
        baseline_path = tmp_path / "baseline.json"
        manager = BaselineManager(baseline_path)

        # Add baseline
        result = BenchmarkResult(
            name="test_a",
            min=0.1,
            max=0.2,
            mean=0.15,
            median=0.15,
            stddev=0.02,
            rounds=10,
            iterations=1,
        )
        manager.update("test_a", result)
        manager.save()

        # Create new manager and load
        manager2 = BaselineManager(baseline_path)
        manager2.load()

        assert manager2.baseline_count == 1
        loaded = manager2.get_baseline("test_a")
        assert loaded is not None
        assert loaded.median == 0.15

    def test_compare_new_benchmark(self, tmp_path):
        """Test comparing a new benchmark without baseline."""
        manager = BaselineManager(tmp_path / "baseline.json")
        current = BenchmarkResult(
            name="new_bench",
            min=0.1,
            max=0.2,
            mean=0.15,
            median=0.15,
            stddev=0.02,
            rounds=5,
            iterations=1,
        )

        check = manager.compare("new_bench", current, threshold=0.15)
        assert check.is_new is True
        assert check.is_regression is False
        assert check.baseline is None

    def test_compare_regression(self, tmp_path):
        """Test detecting a performance regression."""
        manager = BaselineManager(tmp_path / "baseline.json")

        # Set baseline
        baseline = BenchmarkResult(
            name="test_slow",
            min=0.1,
            max=0.2,
            mean=0.15,
            median=0.15,
            stddev=0.02,
            rounds=10,
            iterations=1,
        )
        manager.update("test_slow", baseline)

        # Current is 20% slower (exceeds 15% threshold)
        current = BenchmarkResult(
            name="test_slow",
            min=0.12,
            max=0.24,
            mean=0.18,
            median=0.18,  # 20% slower
            stddev=0.02,
            rounds=10,
            iterations=1,
        )

        check = manager.compare("test_slow", current, threshold=0.15)
        assert check.is_regression is True
        assert check.change_percent > 15
        assert check.baseline is not None

    def test_compare_improvement(self, tmp_path):
        """Test detecting a performance improvement."""
        manager = BaselineManager(tmp_path / "baseline.json")

        baseline = BenchmarkResult(
            name="test_fast",
            min=0.1,
            max=0.2,
            mean=0.15,
            median=0.15,
            stddev=0.02,
            rounds=10,
            iterations=1,
        )
        manager.update("test_fast", baseline)

        # Current is 25% faster
        current = BenchmarkResult(
            name="test_fast",
            min=0.075,
            max=0.15,
            mean=0.112,
            median=0.112,
            stddev=0.02,
            rounds=10,
            iterations=1,
        )

        check = manager.compare("test_fast", current, threshold=0.15)
        assert check.is_regression is False
        assert check.is_improvement is True
        assert check.change_percent < 0

    def test_get_all_names(self, tmp_path):
        """Test getting all baseline names."""
        manager = BaselineManager(tmp_path / "baseline.json")

        result = BenchmarkResult(
            name="test",
            min=0.1,
            max=0.2,
            mean=0.15,
            median=0.15,
            stddev=0.02,
            rounds=5,
            iterations=1,
        )

        manager.update("bench_a", result)
        manager.update("bench_b", result)

        names = manager.get_all_names()
        assert "bench_a" in names
        assert "bench_b" in names

    def test_clear(self, tmp_path):
        """Test clearing all baselines."""
        manager = BaselineManager(tmp_path / "baseline.json")

        result = BenchmarkResult(
            name="test",
            min=0.1,
            max=0.2,
            mean=0.15,
            median=0.15,
            stddev=0.02,
            rounds=5,
            iterations=1,
        )
        manager.update("bench_a", result)
        assert manager.baseline_count == 1

        manager.clear()
        assert manager.baseline_count == 0


class TestPytestBenchmarkAdapterProperties:
    """Test suite for PytestBenchmarkAdapter properties."""

    def test_adapter_name(self, benchmark_adapter):
        """Test adapter_name property."""
        assert benchmark_adapter.adapter_name == "pytest-benchmark"

    def test_module_id(self, benchmark_adapter):
        """Test module_id is correct UUID."""
        assert benchmark_adapter.module_id == MODULE_ID

    def test_tool_name(self, benchmark_adapter):
        """Test tool_name property."""
        assert benchmark_adapter.tool_name == "pytest"


class TestBuildCommand:
    """Test suite for build_command method."""

    def test_build_command_basic(self, benchmark_adapter, tmp_path):
        """Test building basic command."""
        test_file = tmp_path / "test_perf.py"
        test_file.write_text("def test_x(): pass\n")

        cmd = benchmark_adapter.build_command([test_file])

        assert "pytest" in cmd
        assert "--benchmark-only" in cmd
        assert "--benchmark-json=-" in cmd
        assert str(test_file) in cmd

    def test_build_command_with_filter(self, tmp_path):
        """Test command with benchmark filter."""
        settings = BenchmarkSettings(benchmark_filter="test_database*")
        adapter = PytestBenchmarkAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "-k" in cmd
        assert "test_database*" in cmd

    def test_build_command_with_custom_rounds(self, tmp_path):
        """Test command with custom min_rounds."""
        settings = BenchmarkSettings(min_rounds=20)
        adapter = PytestBenchmarkAdapter(settings=settings)
        adapter.settings = settings
        test_file = tmp_path / "test.py"

        cmd = adapter.build_command([test_file])

        assert "--benchmark-min-rounds=20" in cmd

    def test_build_command_raises_without_settings(self, tmp_path):
        """Test build_command raises RuntimeError without settings."""
        adapter = PytestBenchmarkAdapter(settings=None)
        test_file = tmp_path / "test.py"

        with pytest.raises(RuntimeError, match="Settings not initialized"):
            adapter.build_command([test_file])


class TestParseOutput:
    """Test suite for parse_output method."""

    @pytest.mark.asyncio
    async def test_parse_valid_json_output(self, benchmark_adapter):
        """Test parsing valid JSON output."""
        benchmark_output = json.dumps({
            "benchmarks": [
                {
                    "name": "test_sort",
                    "min": 0.001,
                    "max": 0.002,
                    "mean": 0.0015,
                    "median": 0.0015,
                    "stddev": 0.0002,
                    "rounds": 10,
                    "iterations": 100,
                }
            ]
        })

        result = ToolExecutionResult(raw_output=benchmark_output)
        issues = await benchmark_adapter.parse_output(result)

        # No regression since no baseline exists
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_invalid_json(self, benchmark_adapter):
        """Test parsing invalid JSON output."""
        result = ToolExecutionResult(raw_output="not valid json")
        issues = await benchmark_adapter.parse_output(result)

        assert len(issues) == 1
        assert issues[0].code == "BM002"
        assert issues[0].severity == "error"

    @pytest.mark.asyncio
    async def test_parse_empty_output(self, benchmark_adapter):
        """Test parsing empty output."""
        result = ToolExecutionResult(raw_output="")
        issues = await benchmark_adapter.parse_output(result)
        assert len(issues) == 0

    @pytest.mark.asyncio
    async def test_parse_with_regression(self, benchmark_adapter, tmp_path):
        """Test detecting regression in output."""
        # First, establish a baseline
        baseline_manager = BaselineManager(
            tmp_path / ".benchmarks" / "baseline.json"
        )
        baseline = BenchmarkResult(
            name="test_slow",
            min=0.001,
            max=0.002,
            mean=0.0015,
            median=0.0015,
            stddev=0.0002,
            rounds=10,
            iterations=100,
        )
        baseline_manager.update("test_slow", baseline)
        baseline_manager.save()

        # Set the adapter's baseline manager
        benchmark_adapter._baseline_manager = baseline_manager

        # Current result is 25% slower
        benchmark_output = json.dumps({
            "benchmarks": [
                {
                    "name": "test_slow",
                    "min": 0.00125,
                    "max": 0.0025,
                    "mean": 0.001875,
                    "median": 0.001875,  # 25% slower
                    "stddev": 0.0002,
                    "rounds": 10,
                    "iterations": 100,
                }
            ]
        })

        result = ToolExecutionResult(raw_output=benchmark_output)
        issues = await benchmark_adapter.parse_output(result)

        # Should detect regression (BM001)
        regression_issues = [i for i in issues if i.code == "BM001"]
        assert len(regression_issues) == 1
        assert "regression" in regression_issues[0].message.lower()


class TestGetDefaultConfig:
    """Test suite for get_default_config method."""

    def test_get_default_config(self, benchmark_adapter):
        """Test default configuration."""
        config = benchmark_adapter.get_default_config()

        assert config.check_name == "pytest-benchmark"
        assert config.check_type == QACheckType.BENCHMARK
        assert config.enabled is True
        assert config.stage == "comprehensive"
        assert config.parallel_safe is False
        assert "**/test_*.py" in config.file_patterns


class TestGetCheckType:
    """Test suite for _get_check_type method."""

    def test_get_check_type(self, benchmark_adapter):
        """Test check type is BENCHMARK."""
        assert benchmark_adapter._get_check_type() == QACheckType.BENCHMARK


class TestUpdateBaseline:
    """Test suite for baseline update functionality."""

    @pytest.mark.asyncio
    async def test_update_baseline_mode(self, tmp_path):
        """Test update_baseline mode updates baselines without checking."""
        settings = BenchmarkSettings(
            update_baseline=True,
            baseline_file=str(tmp_path / ".benchmarks" / "baseline.json"),
        )
        adapter = PytestBenchmarkAdapter(settings=settings)

        with (
            patch.object(adapter, "validate_tool_available", return_value=True),
            patch.object(adapter, "get_tool_version", return_value="5.2.3"),
        ):
            await adapter.init()

        benchmark_output = json.dumps({
            "benchmarks": [
                {
                    "name": "test_new",
                    "min": 0.001,
                    "max": 0.002,
                    "mean": 0.0015,
                    "median": 0.0015,
                    "stddev": 0.0002,
                    "rounds": 10,
                    "iterations": 100,
                }
            ]
        })

        result = ToolExecutionResult(raw_output=benchmark_output)
        issues = await adapter.parse_output(result)

        # Should not report any issues when updating baseline
        assert len(issues) == 0

        # Baseline should be stored
        assert adapter._baseline_manager is not None
        baseline = adapter._baseline_manager.get_baseline("test_new")
        assert baseline is not None
        assert baseline.median == 0.0015


class TestInsufficientRounds:
    """Test suite for insufficient rounds detection."""

    @pytest.mark.asyncio
    async def test_insufficient_rounds_warning(self, benchmark_adapter):
        """Test warning for insufficient rounds."""
        # Benchmark with only 3 rounds (below min_rounds=5)
        benchmark_output = json.dumps({
            "benchmarks": [
                {
                    "name": "test_short",
                    "min": 0.001,
                    "max": 0.002,
                    "mean": 0.0015,
                    "median": 0.0015,
                    "stddev": 0.0002,
                    "rounds": 3,  # Below min_rounds
                    "iterations": 100,
                }
            ]
        })

        result = ToolExecutionResult(raw_output=benchmark_output)
        issues = await benchmark_adapter.parse_output(result)

        # Should detect insufficient rounds (BM003)
        rounds_issues = [i for i in issues if i.code == "BM003"]
        assert len(rounds_issues) == 1
        assert rounds_issues[0].severity == "warning"

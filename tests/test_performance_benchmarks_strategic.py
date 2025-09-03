import json
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, call, mock_open, patch

import pytest
from rich.console import Console

from crackerjack.models.protocols import FileSystemInterface
from crackerjack.services.performance_benchmarks import (
    BenchmarkResult,
    PerformanceBenchmarkService,
    PerformanceReport,
)


class TestBenchmarkResult:
    def test_benchmark_result_creation(self):
        result = BenchmarkResult(
            name="test_benchmark",
            duration_seconds=1.5,
            memory_usage_mb=100.0,
            cpu_percent=25.0,
            iterations=3,
            metadata={"files": 42},
        )

        assert result.name == "test_benchmark"
        assert result.duration_seconds == 1.5
        assert result.memory_usage_mb == 100.0
        assert result.cpu_percent == 25.0
        assert result.iterations == 3
        assert result.metadata == {"files": 42}

    def test_benchmark_result_defaults(self):
        result = BenchmarkResult(name="minimal", duration_seconds=0.5)

        assert result.memory_usage_mb == 0.0
        assert result.cpu_percent == 0.0
        assert result.iterations == 1
        assert result.metadata == {}


class TestPerformanceReport:
    def test_performance_report_creation(self):
        report = PerformanceReport(
            total_duration=10.5,
            workflow_benchmarks=[BenchmarkResult("test", 1.0)],
            test_benchmarks={"iter_1": {"success": True}},
            hook_performance={"ruff": 2.5},
            recommendations=["Use caching"],
            baseline_comparison={"improvement": 15.0},
        )

        assert report.total_duration == 10.5
        assert len(report.workflow_benchmarks) == 1
        assert report.test_benchmarks["iter_1"]["success"] is True
        assert report.hook_performance["ruff"] == 2.5
        assert "Use caching" in report.recommendations
        assert report.baseline_comparison["improvement"] == 15.0

    def test_performance_report_defaults(self):
        report = PerformanceReport(total_duration=5.0)

        assert report.workflow_benchmarks == []
        assert report.test_benchmarks == {}
        assert report.hook_performance == {}
        assert report.file_operation_stats == {}
        assert report.recommendations == []
        assert report.baseline_comparison == {}


@pytest.fixture
def mock_filesystem():
    filesystem = Mock(spec=FileSystemInterface)
    filesystem.read_file.return_value = "test content"
    filesystem.write_file.return_value = True
    filesystem.exists.return_value = True
    return filesystem


@pytest.fixture
def mock_console():
    console = Mock(spec=Console)
    return console


@pytest.fixture
def benchmark_service(mock_filesystem, mock_console):
    with patch("crackerjack.services.performance_benchmarks.Path.cwd") as mock_cwd:
        mock_cwd.return_value = Path("/ test / project")

        with patch("crackerjack.services.performance_benchmarks.Path.mkdir"):
            service = PerformanceBenchmarkService(
                filesystem=mock_filesystem, console=mock_console
            )
            return service


@pytest.fixture
def sample_performance_history():
    return [
        {
            "timestamp": time.time() - 86400,
            "total_duration": 30.5,
            "component_durations": {"file_discovery": 1.2, "config_loading": 0.8},
            "hook_durations": {"ruff": 5.0, "pyright": 15.0},
            "recommendations_count": 2,
        },
        {
            "timestamp": time.time() - 3600,
            "total_duration": 25.0,
            "component_durations": {"file_discovery": 1.0, "config_loading": 0.6},
            "hook_durations": {"ruff": 4.5, "pyright": 12.0},
            "recommendations_count": 1,
        },
    ]


class TestPerformanceBenchmarkServiceInit:
    def test_service_initialization(self, mock_filesystem, mock_console):
        with patch("crackerjack.services.performance_benchmarks.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/ test / project")

            with patch(
                "crackerjack.services.performance_benchmarks.Path.mkdir"
            ) as mock_mkdir:
                service = PerformanceBenchmarkService(
                    filesystem=mock_filesystem, console=mock_console
                )

                assert service.filesystem == mock_filesystem
                assert service.console == mock_console
                assert service.project_root == Path("/ test / project")
                assert service.benchmarks_dir == Path("/ test / project /.benchmarks")
                assert service.history_file == Path(
                    "/ test / project /.benchmarks / performance_history.json"
                )
                mock_mkdir.assert_called_once_with(exist_ok=True)

    def test_service_initialization_default_console(self, mock_filesystem):
        with patch("crackerjack.services.performance_benchmarks.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/ test / project")

            with patch("crackerjack.services.performance_benchmarks.Path.mkdir"):
                service = PerformanceBenchmarkService(filesystem=mock_filesystem)

                assert isinstance(service.console, Console)


class TestComprehensiveBenchmark:
    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_run_comprehensive_benchmark_full(self, mock_time, benchmark_service):
        mock_time.side_effect = [1000.0, 1010.5]

        with (
            patch.object(benchmark_service, "_benchmark_test_suite") as mock_tests,
            patch.object(benchmark_service, "_benchmark_hooks") as mock_hooks,
            patch.object(
                benchmark_service, "_benchmark_workflow_components"
            ) as mock_components,
            patch.object(
                benchmark_service, "_benchmark_file_operations"
            ) as mock_file_ops,
            patch.object(
                benchmark_service, "_generate_performance_recommendations"
            ) as mock_recommendations,
            patch.object(benchmark_service, "_compare_with_baseline") as mock_baseline,
            patch.object(benchmark_service, "_save_performance_history") as mock_save,
        ):
            mock_tests.return_value = {
                "iter_1": {"success": True, "total_duration": 5.0}
            }
            mock_hooks.return_value = {"ruff": {"mean_duration": 2.0}}
            mock_components.return_value = [BenchmarkResult("file_discovery", 1.5)]
            mock_file_ops.return_value = {"file_read_ops": 0.1}
            mock_recommendations.return_value = ["Consider optimization"]
            mock_baseline.return_value = {"improvement": 10.0}

            report = benchmark_service.run_comprehensive_benchmark(
                run_tests=True, run_hooks=True, iterations=2
            )

            assert report.total_duration == 10.5
            assert report.test_benchmarks == {
                "iter_1": {"success": True, "total_duration": 5.0}
            }
            assert report.hook_performance == {"ruff": {"mean_duration": 2.0}}
            assert len(report.workflow_benchmarks) == 1
            assert report.file_operation_stats == {"file_read_ops": 0.1}
            assert report.recommendations == ["Consider optimization"]
            assert report.baseline_comparison == {"improvement": 10.0}

            mock_tests.assert_called_once_with(2)
            mock_hooks.assert_called_once_with(2)
            mock_components.assert_called_once_with(2)
            mock_file_ops.assert_called_once()
            mock_recommendations.assert_called_once_with(report)
            mock_baseline.assert_called_once_with(report)
            mock_save.assert_called_once_with(report)

    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_run_comprehensive_benchmark_selective(self, mock_time, benchmark_service):
        mock_time.side_effect = [1000.0, 1005.0]

        with (
            patch.object(benchmark_service, "_benchmark_test_suite") as mock_tests,
            patch.object(benchmark_service, "_benchmark_hooks") as mock_hooks,
            patch.object(
                benchmark_service, "_benchmark_workflow_components"
            ) as mock_components,
            patch.object(
                benchmark_service, "_benchmark_file_operations"
            ) as mock_file_ops,
            patch.object(
                benchmark_service, "_generate_performance_recommendations"
            ) as mock_recommendations,
            patch.object(benchmark_service, "_compare_with_baseline") as mock_baseline,
            patch.object(benchmark_service, "_save_performance_history"),
        ):
            mock_components.return_value = []
            mock_file_ops.return_value = {}
            mock_recommendations.return_value = []
            mock_baseline.return_value = {}

            benchmark_service.run_comprehensive_benchmark(
                run_tests=False, run_hooks=False, iterations=1
            )

            mock_tests.assert_not_called()
            mock_hooks.assert_not_called()
            mock_components.assert_called_once_with(1)
            mock_file_ops.assert_called_once()


class TestTestSuiteBenchmarking:
    @patch("crackerjack.services.performance_benchmarks.subprocess.run")
    @patch("crackerjack.services.performance_benchmarks.time.time")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open")
    def test_benchmark_test_suite_success(
        self,
        mock_path_open,
        mock_path_exists,
        mock_time,
        mock_subprocess,
        benchmark_service,
    ):
        mock_time.side_effect = [1000.0, 1005.0, 1010.0, 1015.0]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        benchmark_data = {
            "benchmarks": [{"name": "test_func", "mean": 0.001, "stddev": 0.0001}]
        }

        mock_path_exists.return_value = True

        mock_file = mock_open(read_data=json.dumps(benchmark_data))
        mock_path_open.return_value = mock_file.return_value

        result = benchmark_service._benchmark_test_suite(iterations=2)

        assert "iteration_1" in result
        assert "iteration_2" in result
        assert result["iteration_1"]["success"] is True
        assert result["iteration_1"]["total_duration"] == 5.0
        assert result["iteration_1"]["benchmark_data"] == benchmark_data
        assert result["iteration_2"]["success"] is True
        assert result["iteration_2"]["total_duration"] == 5.0

        expected_cmd = [
            "uv",
            "run",
            "pytest",
            "- - benchmark - only",
            "- - benchmark - json =.benchmarks / test_benchmark.json",
            "- - tb = no",
            "- q",
        ]
        assert mock_subprocess.call_count == 2
        mock_subprocess.assert_has_calls(
            [
                call(
                    expected_cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=300,
                ),
                call(
                    expected_cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=300,
                ),
            ]
        )

    @patch("crackerjack.services.performance_benchmarks.subprocess.run")
    @patch("crackerjack.services.performance_benchmarks.time.time")
    @patch("pathlib.Path.exists")
    def test_benchmark_test_suite_no_benchmark_file(
        self, mock_path_exists, mock_time, mock_subprocess, benchmark_service
    ):
        mock_time.side_effect = [1000.0, 1003.0]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        mock_path_exists.return_value = False

        result = benchmark_service._benchmark_test_suite(iterations=1)

        assert "iteration_1" in result
        assert result["iteration_1"]["success"] is True
        assert result["iteration_1"]["total_duration"] == 3.0
        assert result["iteration_1"]["note"] == "No benchmark tests found"

    @patch("crackerjack.services.performance_benchmarks.subprocess.run")
    def test_benchmark_test_suite_timeout(self, mock_subprocess, benchmark_service):
        mock_subprocess.side_effect = subprocess.TimeoutExpired("pytest", 300)

        result = benchmark_service._benchmark_test_suite(iterations=1)

        assert "error" in result
        assert "timed out" in result["error"]

    @patch("crackerjack.services.performance_benchmarks.subprocess.run")
    def test_benchmark_test_suite_exception(self, mock_subprocess, benchmark_service):
        mock_subprocess.side_effect = Exception("Test error")

        result = benchmark_service._benchmark_test_suite(iterations=1)

        assert "error" in result
        assert "Test error" in result["error"]


class TestHookBenchmarking:
    @patch("crackerjack.services.performance_benchmarks.subprocess.run")
    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_benchmark_hooks_success(
        self, mock_time, mock_subprocess, benchmark_service
    ):
        mock_time.side_effect = [
            1000.0,
            1002.0,
            1005.0,
            1007.0,
            1010.0,
            1015.0,
            1020.0,
            1022.0,
        ]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        with patch.object(benchmark_service, "_benchmark_hooks") as mock_method:

            def benchmark_hooks_impl(iterations):
                hook_performance = {}
                hooks_to_test = ["ruff - format", "pyright"]

                for hook_name in hooks_to_test:
                    durations = []
                    for _ in range(iterations):
                        start_time = time.time()

                        subprocess.run(
                            [
                                "uv",
                                "run",
                                "pre - commit",
                                "run",
                                hook_name,
                                "- - all - files",
                            ],
                            check=False,
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        duration = time.time() - start_time
                        durations.append(duration)

                    if durations and all(d != float("inf") for d in durations):
                        hook_performance[hook_name] = {
                            "mean_duration": statistics.mean(durations),
                            "min_duration": min(durations),
                            "max_duration": max(durations),
                        }

                return hook_performance

            mock_method.side_effect = benchmark_hooks_impl

            benchmark_service._benchmark_hooks(iterations=2)

            mock_method.assert_called_once_with(2)

    @patch("crackerjack.services.performance_benchmarks.subprocess.run")
    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_benchmark_hooks_individual_success(
        self, mock_time, mock_subprocess, benchmark_service
    ):
        mock_time.side_effect = [1000.0, 1002.5, 1005.0, 1006.0]

        mock_result = Mock()
        mock_result.returncode = 0
        mock_subprocess.return_value = mock_result

        def test_benchmark_hooks(iterations):
            hook_performance = {}
            hooks_to_test = ["ruff - format"]

            for hook_name in hooks_to_test:
                durations = []
                for _ in range(iterations):
                    try:
                        start_time = time.time()
                        subprocess.run(
                            [
                                "uv",
                                "run",
                                "pre - commit",
                                "run",
                                hook_name,
                                "- - all - files",
                            ],
                            check=False,
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        duration = time.time() - start_time
                        durations.append(duration)
                    except subprocess.TimeoutExpired:
                        durations.append(120.0)
                    except Exception:
                        durations.append(float("inf"))

                if durations and all(d != float("inf") for d in durations):
                    hook_performance[hook_name] = {
                        "mean_duration": statistics.mean(durations),
                        "min_duration": min(durations),
                        "max_duration": max(durations),
                    }

            return hook_performance

        result = test_benchmark_hooks(iterations=2)

        assert "ruff - format" in result
        assert result["ruff - format"]["mean_duration"] == 1.75
        assert result["ruff - format"]["min_duration"] == 1.0
        assert result["ruff - format"]["max_duration"] == 2.5

    @patch("crackerjack.services.performance_benchmarks.subprocess.run")
    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_benchmark_hooks_timeout_handling(
        self, mock_time, mock_subprocess, benchmark_service
    ):
        mock_time.side_effect = [1000.0, 1000.0]
        mock_subprocess.side_effect = subprocess.TimeoutExpired("pre - commit", 120)

        hooks_to_test = ["pyright"]
        hook_performance = {}

        for hook_name in hooks_to_test:
            durations = []
            for _ in range(1):
                try:
                    start_time = time.time()
                    subprocess.run(
                        [
                            "uv",
                            "run",
                            "pre - commit",
                            "run",
                            hook_name,
                            "- - all - files",
                        ],
                        check=False,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    duration = time.time() - start_time
                    durations.append(duration)
                except subprocess.TimeoutExpired:
                    durations.append(120.0)
                except Exception:
                    durations.append(float("inf"))

            if durations and all(d != float("inf") for d in durations):
                hook_performance[hook_name] = {
                    "mean_duration": statistics.mean(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations),
                }

        assert "pyright" in hook_performance
        assert hook_performance["pyright"]["mean_duration"] == 120.0


class TestWorkflowComponentBenchmarking:
    @patch("crackerjack.services.performance_benchmarks.time.time")
    @patch("pathlib.Path.rglob")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open")
    @patch("tomllib.load")
    def test_benchmark_workflow_components_file_discovery(
        self,
        mock_tomllib,
        mock_path_open,
        mock_path_exists,
        mock_rglob,
        mock_time,
        benchmark_service,
    ):
        mock_time.side_effect = [
            1000.0,
            1001.5,
            1002.0,
            1002.2,
        ]

        python_files = [Path("test1.py"), Path("test2.py"), Path("test3.py")]
        mock_rglob.return_value = python_files
        mock_path_exists.return_value = True
        mock_path_open.return_value = mock_open(
            read_data=b'[tool.pytest.ini_options]\ntestpaths = ["tests"]'
        )()
        mock_tomllib.return_value = {"tool": {"pytest": {}}}

        results = benchmark_service._benchmark_workflow_components(iterations=1)

        file_discovery = next((r for r in results if r.name == "file_discovery"), None)
        assert file_discovery is not None
        assert file_discovery.duration_seconds == 1.5
        assert file_discovery.metadata["files_found"] == 3

        config_loading = next((r for r in results if r.name == "config_loading"), None)
        assert config_loading is not None
        assert config_loading.duration_seconds == 0.2

    @patch("crackerjack.services.performance_benchmarks.time.time")
    @patch("pathlib.Path.rglob")
    @patch("pathlib.Path.exists")
    def test_benchmark_workflow_components_no_config(
        self, mock_path_exists, mock_rglob, mock_time, benchmark_service
    ):
        mock_time.side_effect = [1000.0, 1001.0]

        mock_rglob.return_value = []
        mock_path_exists.return_value = False

        results = benchmark_service._benchmark_workflow_components(iterations=1)

        assert len(results) == 1
        assert results[0].name == "file_discovery"
        assert results[0].metadata["files_found"] == 0

    @patch("crackerjack.services.performance_benchmarks.time.time")
    @patch("pathlib.Path.rglob")
    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.open")
    @patch("tomllib.load")
    def test_benchmark_workflow_components_config_load_error(
        self,
        mock_tomllib,
        mock_path_open,
        mock_path_exists,
        mock_rglob,
        mock_time,
        benchmark_service,
    ):
        mock_time.side_effect = [1000.0, 1001.0, 1002.0, 1003.0]

        mock_rglob.return_value = [Path("test.py")]
        mock_path_exists.return_value = True
        mock_path_open.return_value = mock_open()()
        mock_tomllib.side_effect = Exception("Parse error")

        results = benchmark_service._benchmark_workflow_components(iterations=1)

        assert len(results) == 1
        assert results[0].name == "file_discovery"


class TestFileOperationsBenchmarking:
    @patch("crackerjack.services.performance_benchmarks.time.time")
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.read_text")
    def test_benchmark_file_operations_success(
        self, mock_read_text, mock_glob, mock_time, benchmark_service
    ):
        mock_time.side_effect = [1000.0, 1002.0]

        test_files = [Path("file1.py"), Path("file2.py"), Path("file3.py")]
        mock_glob.return_value = test_files
        mock_read_text.return_value = "test content"

        stats = benchmark_service._benchmark_file_operations()

        assert "file_read_ops" in stats
        assert stats["file_read_ops"] == 2.0 / 3

    @patch("pathlib.Path.glob")
    def test_benchmark_file_operations_no_files(self, mock_glob, benchmark_service):
        mock_glob.return_value = []
        stats = benchmark_service._benchmark_file_operations()
        assert stats == {}

    @patch("crackerjack.services.performance_benchmarks.time.time")
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.read_text")
    def test_benchmark_file_operations_read_error(
        self, mock_read_text, mock_glob, mock_time, benchmark_service
    ):
        mock_time.side_effect = [1000.0, 1001.0]

        test_files = [Path("file1.py"), Path("file2.py")]
        mock_glob.return_value = test_files
        mock_read_text.side_effect = Exception("Read error")

        stats = benchmark_service._benchmark_file_operations()

        assert "file_read_ops" in stats
        assert stats["file_read_ops"] == 1.0 / 2


class TestPerformanceRecommendations:
    def test_generate_performance_recommendations_comprehensive(
        self, benchmark_service
    ):
        report = PerformanceReport(
            total_duration=400.0,
            test_benchmarks={"iteration_1": {"total_duration": 70.0, "success": True}},
            hook_performance={
                "pyright": {
                    "mean_duration": 45.0,
                    "min_duration": 40.0,
                    "max_duration": 50.0,
                },
                "ruff": {
                    "mean_duration": 2.0,
                    "min_duration": 1.8,
                    "max_duration": 2.2,
                },
            },
            workflow_benchmarks=[
                BenchmarkResult("slow_component", 8.0),
                BenchmarkResult("fast_component", 1.0),
            ],
        )

        recommendations = benchmark_service._generate_performance_recommendations(
            report
        )

        test_rec = next((r for r in recommendations if "test suite" in r), None)
        assert test_rec is not None

        hook_rec = next(
            (r for r in recommendations if "Slow hooks detected" in r), None
        )
        assert hook_rec is not None
        assert "pyright(45.0s)" in hook_rec

        component_rec = next(
            (r for r in recommendations if "Slow workflow components" in r), None
        )
        assert component_rec is not None
        assert "slow_component" in component_rec

        overall_rec = next(
            (r for r in recommendations if "Overall workflow execution is slow" in r),
            None,
        )
        assert overall_rec is not None
        assert "- - skip - hooks" in overall_rec

    def test_generate_performance_recommendations_no_issues(self, benchmark_service):
        report = PerformanceReport(
            total_duration=30.0,
            test_benchmarks={"iteration_1": {"total_duration": 15.0, "success": True}},
            hook_performance={"ruff": {"mean_duration": 2.0}},
            workflow_benchmarks=[BenchmarkResult("component", 1.0)],
        )

        recommendations = benchmark_service._generate_performance_recommendations(
            report
        )

        assert recommendations == []

    def test_identify_slow_hooks(self, benchmark_service):
        hook_performance = {
            "fast_hook": {
                "mean_duration": 5.0,
                "min_duration": 4.0,
                "max_duration": 6.0,
            },
            "slow_hook": {
                "mean_duration": 35.0,
                "min_duration": 30.0,
                "max_duration": 40.0,
            },
            "very_slow_hook": {
                "mean_duration": 50.0,
                "min_duration": 45.0,
                "max_duration": 55.0,
            },
            "invalid_hook": "invalid_data",
        }

        slow_hooks = benchmark_service._identify_slow_hooks(hook_performance)

        assert len(slow_hooks) == 2
        assert ("slow_hook", 35.0) in slow_hooks
        assert ("very_slow_hook", 50.0) in slow_hooks
        assert ("fast_hook", 5.0) not in slow_hooks

    def test_format_slow_hooks_message(self, benchmark_service):
        slow_hooks = [
            ("pyright", 45.5),
            ("bandit", 32.1),
            ("vulture", 28.9),
            ("creosote", 25.3),
        ]

        message = benchmark_service._format_slow_hooks_message(slow_hooks)

        assert "pyright(45.5s)" in message
        assert "bandit(32.1s)" in message
        assert "vulture(28.9s)" in message
        assert "creosote" not in message
        assert "Consider hook optimization" in message

    def test_identify_slow_components(self, benchmark_service):
        workflow_benchmarks = [
            BenchmarkResult("fast_component", 2.0),
            BenchmarkResult("slow_component", 8.0),
            BenchmarkResult("very_slow_component", 12.0),
        ]

        slow_components = benchmark_service._identify_slow_components(
            workflow_benchmarks
        )

        assert len(slow_components) == 2
        assert any(c.name == "slow_component" for c in slow_components)
        assert any(c.name == "very_slow_component" for c in slow_components)
        assert not any(c.name == "fast_component" for c in slow_components)


class TestHistoryManagement:
    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    @patch("json.dump")
    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_save_performance_history_new_file(
        self,
        mock_time,
        mock_json_dump,
        mock_open_builtin,
        mock_path_exists,
        benchmark_service,
    ):
        report = PerformanceReport(
            total_duration=25.0,
            workflow_benchmarks=[BenchmarkResult("test_component", 2.0)],
            hook_performance={"ruff": {"mean_duration": 3.0}, "invalid": "data"},
            recommendations=["Test recommendation"],
        )

        mock_path_exists.return_value = False
        mock_time.return_value = 1000.0

        benchmark_service._save_performance_history(report)

        mock_open_builtin.assert_called_with("w")
        mock_json_dump.assert_called_once()

        call_args = mock_json_dump.call_args[0]
        saved_data = call_args[0]

        assert len(saved_data) == 1
        record = saved_data[0]
        assert record["timestamp"] == 1000.0
        assert record["total_duration"] == 25.0
        assert record["component_durations"] == {"test_component": 2.0}
        assert record["hook_durations"] == {"ruff": 3.0, "invalid": "data"}
        assert record["recommendations_count"] == 1

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    @patch("json.load")
    @patch("json.dump")
    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_save_performance_history_existing_file(
        self,
        mock_time,
        mock_json_dump,
        mock_json_load,
        mock_open_builtin,
        mock_path_exists,
        benchmark_service,
        sample_performance_history,
    ):
        report = PerformanceReport(total_duration=20.0, recommendations=[])

        mock_path_exists.return_value = True
        mock_json_load.return_value = sample_performance_history
        mock_time.return_value = 2000.0

        benchmark_service._save_performance_history(report)

        call_args = mock_json_dump.call_args[0]
        saved_data = call_args[0]

        assert len(saved_data) == 3
        assert saved_data[-1]["timestamp"] == 2000.0
        assert saved_data[-1]["total_duration"] == 20.0

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    @patch("json.load")
    @patch("json.dump")
    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_save_performance_history_limit_records(
        self,
        mock_time,
        mock_json_dump,
        mock_json_load,
        mock_open_builtin,
        mock_path_exists,
        benchmark_service,
    ):
        large_history = [{"timestamp": i, "total_duration": 10.0} for i in range(51)]

        report = PerformanceReport(total_duration=15.0, recommendations=[])

        mock_path_exists.return_value = True
        mock_json_load.return_value = large_history
        mock_time.return_value = 3000.0

        benchmark_service._save_performance_history(report)

        call_args = mock_json_dump.call_args[0]
        saved_data = call_args[0]

        assert len(saved_data) == 50
        assert saved_data[-1]["timestamp"] == 3000.0
        assert saved_data[0]["timestamp"] == 1

    @patch("pathlib.Path.exists")
    def test_save_performance_history_error_handling(
        self, mock_path_exists, benchmark_service
    ):
        report = PerformanceReport(total_duration=10.0)

        mock_path_exists.side_effect = Exception("File error")

        benchmark_service._save_performance_history(report)

        benchmark_service.console.print.assert_called_with(
            "[yellow]⚠️[/ yellow] Could not save performance history: File error"
        )

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    @patch("json.load")
    def test_load_performance_history_success(
        self,
        mock_json_load,
        mock_open_builtin,
        mock_path_exists,
        benchmark_service,
        sample_performance_history,
    ):
        mock_path_exists.return_value = True
        mock_json_load.return_value = sample_performance_history

        history = benchmark_service._load_performance_history()

        assert history == sample_performance_history
        assert len(history) == 2

    @patch("pathlib.Path.exists")
    def test_load_performance_history_no_file(
        self, mock_path_exists, benchmark_service
    ):
        mock_path_exists.return_value = False
        history = benchmark_service._load_performance_history()
        assert history is None

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    @patch("json.load")
    def test_load_performance_history_insufficient_data(
        self, mock_json_load, mock_open_builtin, mock_path_exists, benchmark_service
    ):
        insufficient_history = [{"timestamp": 1000.0, "total_duration": 10.0}]

        mock_path_exists.return_value = True
        mock_json_load.return_value = insufficient_history

        history = benchmark_service._load_performance_history()
        assert history is None


class TestBaselineComparison:
    def test_compare_with_baseline_success(
        self, benchmark_service, sample_performance_history
    ):
        current_report = PerformanceReport(
            total_duration=20.0,
            workflow_benchmarks=[
                BenchmarkResult("file_discovery", 0.8),
                BenchmarkResult("config_loading", 0.9),
                BenchmarkResult("new_component", 1.0),
            ],
        )

        with patch.object(
            benchmark_service,
            "_load_performance_history",
            return_value=sample_performance_history,
        ):
            comparison = benchmark_service._compare_with_baseline(current_report)

            assert "overall_performance_change_percent" in comparison

            expected_change = ((20.0 - 27.75) / 27.75) * 100
            assert (
                abs(comparison["overall_performance_change_percent"] - expected_change)
                < 0.1
            )

            assert "file_discovery_change_percent" in comparison
            assert "config_loading_change_percent" in comparison

            assert abs(comparison["file_discovery_change_percent"] - (-20.0)) < 0.1

            assert abs(comparison["config_loading_change_percent"] - 50.0) < 0.1

    def test_compare_with_baseline_no_history(self, benchmark_service):
        current_report = PerformanceReport(total_duration=15.0)

        with patch.object(
            benchmark_service, "_load_performance_history", return_value=None
        ):
            comparison = benchmark_service._compare_with_baseline(current_report)
            assert comparison == {}

    def test_compare_with_baseline_error(self, benchmark_service):
        current_report = PerformanceReport(total_duration=15.0)

        with patch.object(
            benchmark_service,
            "_load_performance_history",
            side_effect=Exception("Load error"),
        ):
            comparison = benchmark_service._compare_with_baseline(current_report)

            assert "error" in comparison
            assert "Could not load baseline: Load error" == comparison["error"]

    def test_calculate_performance_change(self, benchmark_service):
        change = benchmark_service._calculate_performance_change(8.0, 10.0)
        assert change == -20.0

        change = benchmark_service._calculate_performance_change(12.0, 10.0)
        assert change == 20.0

        change = benchmark_service._calculate_performance_change(10.0, 10.0)
        assert change == 0.0


class TestTrendAnalysis:
    def test_get_performance_trends_success(
        self, benchmark_service, sample_performance_history
    ):
        extended_history = sample_performance_history + [
            {
                "timestamp": time.time() - 1800,
                "total_duration": 22.0,
                "component_durations": {"file_discovery": 0.9, "config_loading": 0.5},
                "hook_durations": {"ruff": 4.0, "pyright": 10.0},
                "recommendations_count": 0,
            }
        ]

        with patch.object(
            benchmark_service, "_get_recent_history", return_value=extended_history
        ):
            trends = benchmark_service.get_performance_trends(days=7)

            assert "duration_trend" in trends
            assert "component_trends" in trends
            assert "data_points" in trends

            duration_trend = trends["duration_trend"]
            assert duration_trend["current"] == 22.0
            assert duration_trend["average"] == statistics.mean([30.5, 25.0, 22.0])
            assert duration_trend["trend"] in ["improving", "degrading"]

            component_trends = trends["component_trends"]
            assert "file_discovery" in component_trends
            assert "config_loading" in component_trends

            file_discovery_trend = component_trends["file_discovery"]
            assert file_discovery_trend["current"] == 0.9
            assert file_discovery_trend["trend"] in ["improving", "degrading"]

            assert trends["data_points"] == 3

    def test_get_performance_trends_no_history(self, benchmark_service):
        with patch.object(benchmark_service, "_get_recent_history", return_value=None):
            trends = benchmark_service.get_performance_trends(days=7)

            assert "error" in trends
            assert "No performance history available" == trends["error"]

    def test_get_performance_trends_insufficient_data(self, benchmark_service):
        [{"timestamp": time.time(), "total_duration": 10.0}]

        with patch.object(benchmark_service, "_get_recent_history", return_value=None):
            trends = benchmark_service.get_performance_trends(days=7)

            assert "error" in trends
            assert "Insufficient data for trend analysis" == trends["error"]

    def test_get_performance_trends_exception(self, benchmark_service):
        with patch.object(
            benchmark_service,
            "_get_recent_history",
            side_effect=Exception("Analysis error"),
        ):
            trends = benchmark_service.get_performance_trends(days=7)

            assert "error" in trends
            assert "Could not analyze trends: Analysis error" == trends["error"]

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    @patch("json.load")
    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_get_recent_history_filtering(
        self,
        mock_time,
        mock_json_load,
        mock_open_builtin,
        mock_path_exists,
        benchmark_service,
    ):
        current_time = time.time()

        mixed_history = [
            {
                "timestamp": current_time - (10 * 86400),
                "total_duration": 50.0,
            },
            {
                "timestamp": current_time - (5 * 86400),
                "total_duration": 30.0,
            },
            {
                "timestamp": current_time - (2 * 86400),
                "total_duration": 25.0,
            },
            {
                "timestamp": current_time - (1 * 86400),
                "total_duration": 20.0,
            },
        ]

        mock_path_exists.return_value = True
        mock_json_load.return_value = mixed_history
        mock_time.return_value = current_time

        recent_history = benchmark_service._get_recent_history(days=7)

        assert len(recent_history) == 3
        assert all(r["timestamp"] > current_time - (7 * 86400) for r in recent_history)
        assert recent_history[0]["total_duration"] == 30.0
        assert recent_history[-1]["total_duration"] == 20.0

    def test_determine_trend_direction(self, benchmark_service):
        durations = [10.0, 9.0, 8.0, 7.0, 6.0]
        trend = benchmark_service._determine_trend_direction(durations)
        assert trend == "improving"

        durations = [6.0, 7.0, 8.0, 9.0, 10.0]
        trend = benchmark_service._determine_trend_direction(durations)
        assert trend == "degrading"

        durations = [8.0, 8.0, 8.0, 8.0]
        trend = benchmark_service._determine_trend_direction(durations)
        assert trend == "degrading"

    def test_extract_component_durations(self, benchmark_service):
        history = [
            {"component_durations": {"file_discovery": 1.0, "config_loading": 0.5}},
            {"component_durations": {"file_discovery": 1.2, "other": 0.8}},
            {"component_durations": {"file_discovery": 0.9, "config_loading": 0.6}},
            {"other_data": "irrelevant"},
        ]

        durations = benchmark_service._extract_component_durations(
            history, "file_discovery"
        )
        assert durations == [1.0, 1.2, 0.9]

        durations = benchmark_service._extract_component_durations(
            history, "config_loading"
        )
        assert durations == [0.5, 0.6]

        durations = benchmark_service._extract_component_durations(
            history, "non_existent"
        )
        assert durations == []


class TestDisplayFunctionality:
    def test_display_performance_report_full(self, benchmark_service):
        report = PerformanceReport(
            total_duration=45.0,
            workflow_benchmarks=[
                BenchmarkResult("file_discovery", 2.5, metadata={"files": 150}),
                BenchmarkResult("config_loading", 0.8),
            ],
            hook_performance={
                "ruff": {
                    "mean_duration": 3.2,
                    "min_duration": 2.8,
                    "max_duration": 3.6,
                },
                "pyright": {
                    "mean_duration": 12.5,
                    "min_duration": 11.0,
                    "max_duration": 14.0,
                },
            },
            baseline_comparison={
                "overall_performance_change_percent": -15.5,
                "file_discovery_change_percent": 10.2,
            },
            recommendations=["Consider optimization", "Enable caching"],
        )

        benchmark_service.display_performance_report(report)

        console_calls = benchmark_service.console.print.call_args_list

        console_output = " ".join(str(call) for call in console_calls)
        assert "Total Duration: 45.00s" in console_output
        assert "Benchmark data saved to" in console_output

        assert len(console_calls) >= 5

    def test_display_performance_report_minimal(self, benchmark_service):
        report = PerformanceReport(total_duration=15.0)

        benchmark_service.display_performance_report(report)

        console_calls = benchmark_service.console.print.call_args_list

        overall_stats_call = next(
            (call for call in console_calls if "Total Duration: 15.00s" in str(call)),
            None,
        )
        assert overall_stats_call is not None

        benchmarks_dir_call = next(
            (call for call in console_calls if "Benchmark data saved to" in str(call)),
            None,
        )
        assert benchmarks_dir_call is not None

        no_issues_call = next(
            (
                call
                for call in console_calls
                if "No performance issues detected !" in str(call)
            ),
            None,
        )
        assert no_issues_call is not None

    def test_print_comparison_metrics(self, benchmark_service):
        baseline_comparison = {
            "overall_performance_change_percent": -12.5,
            "file_discovery_change_percent": 8.3,
            "config_loading_change_percent": 25.7,
            "non_percent_metric": "some_value",
            "hook_analysis_count": 5,
        }

        benchmark_service._print_comparison_metrics(baseline_comparison)

        console_calls = benchmark_service.console.print.call_args_list

        improvement_call = next(
            (
                call
                for call in console_calls
                if "12.5 % faster" in str(call) and "[green]" in str(call)
            ),
            None,
        )
        assert improvement_call is not None

        minor_degradation_call = next(
            (
                call
                for call in console_calls
                if "8.3 % slower" in str(call) and "[yellow]" in str(call)
            ),
            None,
        )
        assert minor_degradation_call is not None

        major_degradation_call = next(
            (
                call
                for call in console_calls
                if "25.7 % slower" in str(call) and "[red]" in str(call)
            ),
            None,
        )
        assert major_degradation_call is not None


class TestPerformanceBenchmarkingIntegration:
    def test_comprehensive_benchmark_integration(self, mock_filesystem, mock_console):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch(
                "crackerjack.services.performance_benchmarks.Path.cwd",
                return_value=temp_path,
            ):
                service = PerformanceBenchmarkService(
                    filesystem=mock_filesystem, console=mock_console
                )

                with (
                    patch.object(service, "_benchmark_test_suite") as mock_tests,
                    patch.object(service, "_benchmark_hooks") as mock_hooks,
                    patch.object(
                        service, "_benchmark_workflow_components"
                    ) as mock_components,
                    patch.object(
                        service, "_benchmark_file_operations"
                    ) as mock_file_ops,
                    patch.object(service, "_save_performance_history") as mock_save,
                ):
                    mock_tests.return_value = {
                        "iteration_1": {"success": True, "total_duration": 30.0}
                    }
                    mock_hooks.return_value = {
                        "ruff": {
                            "mean_duration": 2.5,
                            "min_duration": 2.0,
                            "max_duration": 3.0,
                        }
                    }
                    mock_components.return_value = [
                        BenchmarkResult("file_discovery", 1.2, metadata={"files": 50})
                    ]
                    mock_file_ops.return_value = {"file_read_ops": 0.05}

                    report = service.run_comprehensive_benchmark(
                        run_tests=True, run_hooks=True, iterations=1
                    )

                    assert report.total_duration > 0
                    assert "iteration_1" in report.test_benchmarks
                    assert "ruff" in report.hook_performance
                    assert len(report.workflow_benchmarks) == 1
                    assert "file_read_ops" in report.file_operation_stats
                    assert isinstance(report.recommendations, list)
                    assert isinstance(report.baseline_comparison, dict)

                    mock_tests.assert_called_once_with(1)
                    mock_hooks.assert_called_once_with(1)
                    mock_components.assert_called_once_with(1)
                    mock_file_ops.assert_called_once()
                    mock_save.assert_called_once_with(report)

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    @patch("json.load")
    @patch("crackerjack.services.performance_benchmarks.time.time")
    def test_trend_analysis_integration(
        self,
        mock_time,
        mock_json_load,
        mock_open_builtin,
        mock_path_exists,
        benchmark_service,
    ):
        current_time = time.time()
        performance_history = [
            {
                "timestamp": current_time - (5 * 86400),
                "total_duration": 35.0,
                "component_durations": {"file_discovery": 2.0, "config_loading": 1.0},
                "hook_durations": {"ruff": 5.0, "pyright": 15.0},
            },
            {
                "timestamp": current_time - (3 * 86400),
                "total_duration": 30.0,
                "component_durations": {"file_discovery": 1.8, "config_loading": 0.9},
                "hook_durations": {"ruff": 4.5, "pyright": 12.0},
            },
            {
                "timestamp": current_time - (1 * 86400),
                "total_duration": 25.0,
                "component_durations": {"file_discovery": 1.5, "config_loading": 0.8},
                "hook_durations": {"ruff": 4.0, "pyright": 10.0},
            },
        ]

        mock_path_exists.return_value = True
        mock_json_load.return_value = performance_history
        mock_time.return_value = current_time

        trends = benchmark_service.get_performance_trends(days=7)

        assert "duration_trend" in trends
        assert "component_trends" in trends
        assert "data_points" in trends

        duration_trend = trends["duration_trend"]
        assert duration_trend["current"] == 25.0
        assert duration_trend["average"] == statistics.mean([35.0, 30.0, 25.0])
        assert duration_trend["trend"] == "improving"

        component_trends = trends["component_trends"]
        assert "file_discovery" in component_trends
        assert "config_loading" in component_trends

        file_trend = component_trends["file_discovery"]
        assert file_trend["current"] == 1.5
        assert file_trend["trend"] == "improving"

        config_trend = component_trends["config_loading"]
        assert config_trend["current"] == 0.8
        assert config_trend["trend"] == "improving"

        assert trends["data_points"] == 3

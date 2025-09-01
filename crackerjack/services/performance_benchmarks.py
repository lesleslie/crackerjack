import json
import statistics
import subprocess
import time
import typing as t
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from crackerjack.models.protocols import FileSystemInterface


@dataclass
class BenchmarkResult:
    name: str
    duration_seconds: float
    memory_usage_mb: float = 0.0
    cpu_percent: float = 0.0
    iterations: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceReport:
    total_duration: float
    workflow_benchmarks: list[BenchmarkResult] = field(default_factory=list)
    test_benchmarks: dict[str, Any] = field(default_factory=dict)
    hook_performance: dict[str, float] = field(default_factory=dict)
    file_operation_stats: dict[str, float] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    baseline_comparison: dict[str, float] = field(default_factory=dict)


class PerformanceBenchmarkService:
    def __init__(
        self,
        filesystem: FileSystemInterface,
        console: Console | None = None,
    ) -> None:
        self.filesystem = filesystem
        self.console = console or Console()
        self.project_root = Path.cwd()
        self.benchmarks_dir = self.project_root / ".benchmarks"
        self.history_file = self.benchmarks_dir / "performance_history.json"

        self.benchmarks_dir.mkdir(exist_ok=True)

    def run_comprehensive_benchmark(
        self,
        run_tests: bool = True,
        run_hooks: bool = True,
        iterations: int = 1,
    ) -> PerformanceReport:
        """Run comprehensive performance benchmark across all components."""
        self.console.print(
            "[cyan]🚀 Starting comprehensive performance benchmark...[/cyan]",
        )

        start_time = time.time()
        report = self._initialize_performance_report()

        self._run_requested_benchmarks(report, run_tests, run_hooks, iterations)
        self._finalize_performance_report(report, start_time)

        return report

    def _initialize_performance_report(self) -> PerformanceReport:
        """Initialize a new performance report."""
        return PerformanceReport(total_duration=0.0)

    def _run_requested_benchmarks(
        self,
        report: PerformanceReport,
        run_tests: bool,
        run_hooks: bool,
        iterations: int,
    ) -> None:
        """Run the requested benchmark types."""
        if run_tests:
            report.test_benchmarks = self._benchmark_test_suite(iterations)

        if run_hooks:
            report.hook_performance = self._benchmark_hooks(iterations)

        report.workflow_benchmarks = self._benchmark_workflow_components(iterations)
        report.file_operation_stats = self._benchmark_file_operations()

    def _finalize_performance_report(
        self,
        report: PerformanceReport,
        start_time: float,
    ) -> None:
        """Finalize performance report with analysis and history."""
        report.total_duration = time.time() - start_time
        report.recommendations = self._generate_performance_recommendations(report)
        report.baseline_comparison = self._compare_with_baseline(report)
        self._save_performance_history(report)

    def _benchmark_test_suite(self, iterations: int = 1) -> dict[str, Any]:
        self.console.print("[dim]📊 Benchmarking test suite...[/dim]")

        benchmark_results = {}

        try:
            for i in range(iterations):
                start_time = time.time()

                result = subprocess.run(
                    [
                        "uv",
                        "run",
                        "pytest",
                        "--benchmark-only",
                        "--benchmark-json=.benchmarks/test_benchmark.json",
                        "--tb=no",
                        "-q",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )

                duration = time.time() - start_time

                benchmark_file = self.benchmarks_dir / "test_benchmark.json"
                if benchmark_file.exists():
                    with benchmark_file.open() as f:
                        benchmark_data = json.load(f)

                    benchmark_results[f"iteration_{i + 1}"] = {
                        "total_duration": duration,
                        "benchmark_data": benchmark_data,
                        "success": result.returncode == 0,
                    }
                else:
                    benchmark_results[f"iteration_{i + 1}"] = {
                        "total_duration": duration,
                        "success": result.returncode == 0,
                        "note": "No benchmark tests found",
                    }

        except subprocess.TimeoutExpired:
            benchmark_results["error"] = "Test benchmarking timed out"
        except Exception as e:
            benchmark_results["error"] = f"Test benchmarking failed: {e}"

        return benchmark_results

    def _benchmark_hooks(self, iterations: int = 1) -> dict[str, float]:
        self.console.print("[dim]🔧 Benchmarking hooks performance...[/dim]")

        hook_performance = {}

        hooks_to_test = [
            "trailing-whitespace",
            "end-of-file-fixer",
            "ruff-format",
            "ruff-check",
            "gitleaks",
            "pyright",
            "bandit",
            "vulture",
        ]

        for hook_name in hooks_to_test:
            durations: list[float] = []

            for _i in range(iterations):
                try:
                    start_time = time.time()
                    subprocess.run(
                        [
                            "uv",
                            "run",
                            "pre-commit",
                            "run",
                            hook_name,
                            "--all-files",
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

    def _benchmark_workflow_components(
        self,
        iterations: int = 1,
    ) -> list[BenchmarkResult]:
        self.console.print("[dim]⚙️ Benchmarking workflow components...[/dim]")

        results = []

        start_time = time.time()
        python_files = list(self.project_root.rglob("*.py"))
        file_discovery_duration = time.time() - start_time

        results.append(
            BenchmarkResult(
                name="file_discovery",
                duration_seconds=file_discovery_duration,
                metadata={"files_found": len(python_files)},
            ),
        )

        start_time = time.time()
        pyproject_path = self.project_root / "pyproject.toml"
        if pyproject_path.exists():
            with suppress(Exception):
                import tomllib

                with pyproject_path.open("rb") as f:
                    tomllib.load(f)
                config_load_duration = time.time() - start_time

                results.append(
                    BenchmarkResult(
                        name="config_loading",
                        duration_seconds=config_load_duration,
                    ),
                )

        return results

    def _benchmark_file_operations(self) -> dict[str, float]:
        stats = {}

        test_files = list(self.project_root.glob("*.py"))[:10]
        if test_files:
            start_time = time.time()
            for file_path in test_files:
                with suppress(Exception):
                    file_path.read_text(encoding="utf-8")
            read_duration = time.time() - start_time
            stats["file_read_ops"] = read_duration / len(test_files)

        return stats

    def _generate_performance_recommendations(
        self,
        report: PerformanceReport,
    ) -> list[str]:
        """Generate performance recommendations based on benchmark results."""
        recommendations = []

        self._add_test_suite_recommendations(report, recommendations)
        self._add_hook_performance_recommendations(report, recommendations)
        self._add_component_performance_recommendations(report, recommendations)
        self._add_overall_performance_recommendations(report, recommendations)

        return recommendations

    def _add_test_suite_recommendations(
        self,
        report: PerformanceReport,
        recommendations: list[str],
    ) -> None:
        """Add recommendations for test suite performance."""
        if not report.test_benchmarks:
            return

        for iteration_data in report.test_benchmarks.values():
            if self._is_slow_test_iteration(iteration_data):
                recommendations.append(
                    "Consider optimizing test suite - execution time exceeds 1 minute",
                )
                break

    def _is_slow_test_iteration(self, iteration_data: Any) -> bool:
        """Check if test iteration is slow."""
        return (
            isinstance(iteration_data, dict)
            and iteration_data.get("total_duration", 0) > 60
        )

    def _add_hook_performance_recommendations(
        self,
        report: PerformanceReport,
        recommendations: list[str],
    ) -> None:
        """Add recommendations for hook performance."""
        slow_hooks = self._identify_slow_hooks(report.hook_performance)
        if slow_hooks:
            recommendations.append(self._format_slow_hooks_message(slow_hooks))

    def _identify_slow_hooks(
        self,
        hook_performance: dict[str, float],
    ) -> list[tuple[str, float]]:
        """Identify hooks with slow performance."""
        slow_hooks = []
        for hook_name, perf_data in hook_performance.items():
            if isinstance(perf_data, dict):
                mean_duration = perf_data.get("mean_duration", 0)
                if mean_duration > 30:
                    slow_hooks.append((hook_name, mean_duration))
        return slow_hooks

    def _format_slow_hooks_message(self, slow_hooks: list[tuple[str, float]]) -> str:
        """Format message for slow hooks recommendation."""
        hooks_info = ", ".join(f"{h}({d:.1f}s)" for h, d in slow_hooks[:3])
        return (
            f"Slow hooks detected: {hooks_info}. "
            "Consider hook optimization or selective execution."
        )

    def _add_component_performance_recommendations(
        self,
        report: PerformanceReport,
        recommendations: list[str],
    ) -> None:
        """Add recommendations for component performance."""
        slow_components = self._identify_slow_components(report.workflow_benchmarks)
        if slow_components:
            components_names = ", ".join(c.name for c in slow_components)
            recommendations.append(
                f"Slow workflow components: {components_names}. "
                "Consider caching or optimization.",
            )

    def _identify_slow_components(
        self,
        workflow_benchmarks: list[BenchmarkResult],
    ) -> list[BenchmarkResult]:
        """Identify slow workflow components."""
        return [b for b in workflow_benchmarks if b.duration_seconds > 5]

    def _add_overall_performance_recommendations(
        self,
        report: PerformanceReport,
        recommendations: list[str],
    ) -> None:
        """Add recommendations for overall performance."""
        if report.total_duration > 300:
            recommendations.append(
                "Overall workflow execution is slow. Consider enabling --skip-hooks "
                "during development iterations.",
            )

    def _compare_with_baseline(
        self,
        current_report: PerformanceReport,
    ) -> dict[str, float]:
        """Compare current performance with historical baseline."""
        baseline_comparison = {}

        try:
            history = self._load_performance_history()
            if not history:
                return baseline_comparison

            self._add_overall_performance_comparison(
                current_report,
                history,
                baseline_comparison,
            )
            self._add_component_performance_comparison(
                current_report,
                history,
                baseline_comparison,
            )

        except Exception as e:
            baseline_comparison["error"] = f"Could not load baseline: {e}"

        return baseline_comparison

    def _load_performance_history(self) -> list[dict[str, Any]] | None:
        """Load performance history from file."""
        if not self.history_file.exists():
            return None

        with self.history_file.open() as f:
            history = json.load(f)

        return history if history and len(history) > 1 else None

    def _add_overall_performance_comparison(
        self,
        current_report: PerformanceReport,
        history: list[dict[str, Any]],
        comparison: dict[str, Any],
    ) -> None:
        """Add overall performance comparison to baseline."""
        recent_runs = history[-5:]
        baseline_duration = statistics.median(
            [r["total_duration"] for r in recent_runs],
        )

        performance_change = (
            (current_report.total_duration - baseline_duration) / baseline_duration
        ) * 100
        comparison["overall_performance_change_percent"] = performance_change

    def _add_component_performance_comparison(
        self,
        current_report: PerformanceReport,
        history: list[dict[str, Any]],
        comparison: dict[str, Any],
    ) -> None:
        """Add component-level performance comparison."""
        recent_runs = history[-5:]
        if not recent_runs:
            return

        component_durations = recent_runs[-1].get("component_durations", {})

        for component in current_report.workflow_benchmarks:
            if component.name in component_durations:
                old_duration = component_durations[component.name]
                change = self._calculate_performance_change(
                    component.duration_seconds,
                    old_duration,
                )
                comparison[f"{component.name}_change_percent"] = change

    def _calculate_performance_change(
        self,
        current_duration: float,
        old_duration: float,
    ) -> float:
        """Calculate performance change percentage."""
        return ((current_duration - old_duration) / old_duration) * 100

    def _save_performance_history(self, report: PerformanceReport) -> None:
        try:
            history = []
            if self.history_file.exists():
                with self.history_file.open() as f:
                    history = json.load(f)

            record = {
                "timestamp": time.time(),
                "total_duration": report.total_duration,
                "component_durations": {
                    c.name: c.duration_seconds for c in report.workflow_benchmarks
                },
                "hook_durations": {
                    hook: (perf["mean_duration"] if isinstance(perf, dict) else perf)
                    for hook, perf in report.hook_performance.items()
                },
                "recommendations_count": len(report.recommendations),
            }

            history.append(record)

            history = history[-50:]

            with self.history_file.open("w") as f:
                json.dump(history, f, indent=2)

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️[/yellow] Could not save performance history: {e}",
            )

    def display_performance_report(self, report: PerformanceReport) -> None:
        self.console.print("\n[bold cyan]🚀 Performance Benchmark Report[/bold cyan]\n")

        self._display_overall_stats(report)
        self._display_workflow_components(report)
        self._display_hook_performance(report)
        self._display_baseline_comparison(report)
        self._display_recommendations(report)

        self.console.print(
            f"\n[dim]📁 Benchmark data saved to: {self.benchmarks_dir}[/dim]",
        )

    def _display_overall_stats(self, report: PerformanceReport) -> None:
        self.console.print(
            f"[green]⏱️ Total Duration: {report.total_duration:.2f}s[/green]",
        )

    def _display_workflow_components(self, report: PerformanceReport) -> None:
        if not report.workflow_benchmarks:
            return

        table = Table(title="Workflow Component Performance")
        table.add_column("Component", style="cyan")
        table.add_column("Duration (s)", style="yellow", justify="right")
        table.add_column("Metadata", style="dim")

        for benchmark in report.workflow_benchmarks:
            metadata_str = ", ".join(f"{k}={v}" for k, v in benchmark.metadata.items())
            table.add_row(
                benchmark.name,
                f"{benchmark.duration_seconds:.3f}",
                metadata_str,
            )

        self.console.print(table)
        self.console.print()

    def _display_hook_performance(self, report: PerformanceReport) -> None:
        if not report.hook_performance:
            return

        table = Table(title="Hook Performance Analysis")
        table.add_column("Hook", style="cyan")
        table.add_column("Mean (s)", style="yellow", justify="right")
        table.add_column("Min (s)", style="green", justify="right")
        table.add_column("Max (s)", style="red", justify="right")

        for hook_name, perf_data in report.hook_performance.items():
            if isinstance(perf_data, dict):
                table.add_row(
                    hook_name,
                    f"{perf_data.get('mean_duration', 0):.2f}",
                    f"{perf_data.get('min_duration', 0):.2f}",
                    f"{perf_data.get('max_duration', 0):.2f}",
                )

        self.console.print(table)
        self.console.print()

    def _display_baseline_comparison(self, report: PerformanceReport) -> None:
        if not report.baseline_comparison:
            return

        self._print_comparison_header()
        self._print_comparison_metrics(report.baseline_comparison)
        self.console.print()

    def _print_comparison_header(self) -> None:
        """Print performance comparison header."""
        self.console.print("[bold]📊 Performance Comparison[/bold]")

    def _print_comparison_metrics(self, baseline_comparison: dict[str, t.Any]) -> None:
        """Print individual comparison metrics with appropriate colors."""
        for metric, value in baseline_comparison.items():
            if isinstance(value, float | int) and "percent" in metric:
                color = "green" if value < 0 else "red" if value > 10 else "yellow"
                direction = "faster" if value < 0 else "slower"
                self.console.print(
                    f" {metric}: [{color}]{abs(value):.1f}% {direction}[/{color}]",
                )

    def _display_recommendations(self, report: PerformanceReport) -> None:
        if report.recommendations:
            self.console.print(
                "[bold yellow]💡 Performance Recommendations[/bold yellow]",
            )
            for i, rec in enumerate(report.recommendations, 1):
                self.console.print(f" {i}. {rec}")
        else:
            self.console.print("[green]✨ No performance issues detected![/green]")

    def get_performance_trends(self, days: int = 7) -> dict[str, Any]:
        """Get performance trends over specified time period."""
        try:
            recent_history = self._get_recent_history(days)
            if not recent_history:
                return self._handle_insufficient_trend_data()

            trends = {}
            self._add_duration_trends(recent_history, trends)
            self._add_component_trends(recent_history, trends)
            trends["data_points"] = len(recent_history)

            return trends

        except Exception as e:
            return {"error": f"Could not analyze trends: {e}"}

    def _get_recent_history(self, days: int) -> list[dict[str, Any]] | None:
        """Get recent performance history within specified days."""
        if not self.history_file.exists():
            return None

        with self.history_file.open() as f:
            history = json.load(f)

        cutoff_time = time.time() - (days * 86400)
        recent_history = [r for r in history if r.get("timestamp", 0) > cutoff_time]

        return recent_history if len(recent_history) >= 2 else None

    def _handle_insufficient_trend_data(self) -> dict[str, str]:
        """Handle cases where insufficient data is available for trend analysis."""
        if not self.history_file.exists():
            return {"error": "No performance history available"}
        return {"error": "Insufficient data for trend analysis"}

    def _add_duration_trends(
        self, recent_history: list[dict[str, Any]], trends: dict[str, Any]
    ) -> None:
        """Add overall duration trends to results."""
        durations = [r["total_duration"] for r in recent_history]
        trends["duration_trend"] = {
            "current": durations[-1],
            "average": statistics.mean(durations),
            "trend": self._determine_trend_direction(durations),
        }

    def _add_component_trends(
        self, recent_history: list[dict[str, Any]], trends: dict[str, Any]
    ) -> None:
        """Add component-level trends to results."""
        component_trends = {}
        latest_components = recent_history[-1].get("component_durations", {})

        for component in latest_components:
            component_durations = self._extract_component_durations(
                recent_history,
                component,
            )
            if len(component_durations) >= 2:
                component_trends[component] = {
                    "current": component_durations[-1],
                    "average": statistics.mean(component_durations),
                    "trend": self._determine_trend_direction(component_durations),
                }

        trends["component_trends"] = component_trends

    def _extract_component_durations(
        self,
        recent_history: list[dict[str, Any]],
        component: str,
    ) -> list[float]:
        """Extract duration data for a specific component."""
        return [
            r.get("component_durations", {}).get(component)
            for r in recent_history
            if component in r.get("component_durations", {})
        ]

    def _determine_trend_direction(self, durations: list[float]) -> str:
        """Determine if trend is improving or degrading."""
        current = durations[-1]
        historical_average = statistics.mean(durations[:-1])
        return "improving" if current < historical_average else "degrading"

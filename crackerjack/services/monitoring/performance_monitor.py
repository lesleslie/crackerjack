import json
import typing as t
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from acb.depends import Inject, depends
from acb.logger import Logger

from crackerjack.services.memory_optimizer import MemoryOptimizer
from crackerjack.services.monitoring.performance_cache import get_performance_cache


@dataclass
class PerformanceMetric:
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict[str, t.Any])


@dataclass
class PhasePerformance:
    phase_name: str
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    memory_start_mb: float = 0.0
    memory_peak_mb: float = 0.0
    memory_end_mb: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0
    parallel_operations: int = 0
    sequential_operations: int = 0
    success: bool = True
    metrics: list[PerformanceMetric] = field(default_factory=list)

    def finalize(self, end_time: datetime | None = None) -> None:
        self.end_time = end_time or datetime.now()
        self.duration_seconds = (self.end_time - self.start_time).total_seconds()


@dataclass
class WorkflowPerformance:
    workflow_id: str
    start_time: datetime
    end_time: datetime | None = None
    total_duration_seconds: float = 0.0
    phases: list[PhasePerformance] = field(default_factory=list)
    overall_success: bool = True
    performance_score: float = 0.0

    def add_phase(self, phase: PhasePerformance) -> None:
        self.phases.append(phase)

    def finalize(self, success: bool = True) -> None:
        self.end_time = datetime.now()
        self.total_duration_seconds = (self.end_time - self.start_time).total_seconds()
        self.overall_success = success
        self.performance_score = self._calculate_performance_score()

    def _calculate_performance_score(self) -> float:
        if not self.phases:
            return 0.0

        duration_score = max(0, 100 - (self.total_duration_seconds / 10))

        total_hits = sum(p.cache_hits for p in self.phases)
        total_misses = sum(p.cache_misses for p in self.phases)
        cache_ratio = (
            total_hits / (total_hits + total_misses)
            if total_hits + total_misses > 0
            else 0
        )
        cache_score = cache_ratio * 20

        total_parallel = sum(p.parallel_operations for p in self.phases)
        total_sequential = sum(p.sequential_operations for p in self.phases)
        parallel_ratio = (
            total_parallel / (total_parallel + total_sequential)
            if total_parallel + total_sequential > 0
            else 0
        )
        parallel_score = parallel_ratio * 15

        max_memory = max((p.memory_peak_mb for p in self.phases), default=0)
        memory_score = max(0, 15 - (max_memory / 50))

        success_score = 10 if self.overall_success else 0

        return min(
            100,
            duration_score
            + cache_score
            + parallel_score
            + memory_score
            + success_score,
        )


@dataclass
class PerformanceBenchmark:
    operation_name: str
    baseline_duration_seconds: float
    current_duration_seconds: float
    improvement_percentage: float = 0.0
    regression: bool = False

    def __post_init__(self) -> None:
        if self.baseline_duration_seconds > 0:
            self.improvement_percentage = (
                (self.baseline_duration_seconds - self.current_duration_seconds)
                / self.baseline_duration_seconds
                * 100
            )
            self.regression = self.improvement_percentage < 0


class PerformanceMonitor:
    @depends.inject
    def __init__(
        self,
        logger: Inject[Logger],
        data_retention_days: int = 30,
        benchmark_history_size: int = 100,
    ):
        self.data_retention_days = data_retention_days
        self.benchmark_history_size = benchmark_history_size
        self._initialize_data_structures(benchmark_history_size)
        self._initialize_services(logger)
        self._initialize_thresholds()

    def _initialize_data_structures(self, history_size: int) -> None:
        self._active_workflows: dict[str, WorkflowPerformance] = {}
        self._active_phases: dict[str, PhasePerformance] = {}
        self._completed_workflows: deque[WorkflowPerformance] = deque(
            maxlen=history_size
        )
        self._benchmarks: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=history_size)  # type: ignore[arg-type]
        )

    def _initialize_services(self, logger: Logger) -> None:
        self._lock = Lock()
        self._logger = logger
        self._memory_optimizer = MemoryOptimizer.get_instance()
        self._cache = get_performance_cache()

    def _initialize_thresholds(self) -> None:
        self._warning_thresholds = {
            "duration_seconds": 30.0,
            "memory_mb": 100.0,
            "cache_hit_ratio": 0.5,
        }

    def start_workflow(self, workflow_id: str) -> None:
        with self._lock:
            if workflow_id in self._active_workflows:
                self._logger.warning(f"Workflow {workflow_id} already being monitored")
                return

            workflow = WorkflowPerformance(
                workflow_id=workflow_id,
                start_time=datetime.now(),
            )

            self._active_workflows[workflow_id] = workflow
            self._logger.debug(f"Started monitoring workflow: {workflow_id}")

            self._memory_optimizer.start_profiling()

    def end_workflow(
        self, workflow_id: str, success: bool = True
    ) -> WorkflowPerformance:
        with self._lock:
            if workflow_id not in self._active_workflows:
                self._logger.warning(f"Workflow {workflow_id} not found for ending")
                return WorkflowPerformance(
                    workflow_id=workflow_id, start_time=datetime.now()
                )

            workflow = self._active_workflows.pop(workflow_id)
            workflow.finalize(success)

            self._completed_workflows.append(workflow)

            self._logger.info(
                f"Completed workflow {workflow_id}: "
                f"{workflow.total_duration_seconds: .2f}s, "
                f"score: {workflow.performance_score: .1f}, "
                f"phases: {len(workflow.phases)}"
            )

            self._check_performance_warnings(workflow)

            return workflow

    def start_phase(self, workflow_id: str, phase_name: str) -> None:
        phase_key = f"{workflow_id}: {phase_name}"

        with self._lock:
            if phase_key in self._active_phases:
                self._logger.warning(f"Phase {phase_key} already being monitored")
                return

            memory_mb = self._memory_optimizer.record_checkpoint(f"{phase_name}_start")

            phase = PhasePerformance(
                phase_name=phase_name,
                start_time=datetime.now(),
                memory_start_mb=memory_mb,
            )

            self._active_phases[phase_key] = phase
            self._logger.debug(f"Started monitoring phase: {phase_key}")

    def end_phase(
        self, workflow_id: str, phase_name: str, success: bool = True
    ) -> PhasePerformance:
        phase_key = f"{workflow_id}: {phase_name}"

        with self._lock:
            if phase_key not in self._active_phases:
                self._logger.warning(f"Phase {phase_key} not found for ending")
                return PhasePerformance(
                    phase_name=phase_name, start_time=datetime.now()
                )

            phase = self._active_phases.pop(phase_key)
            phase.success = success

            phase.memory_end_mb = self._memory_optimizer.record_checkpoint(
                f"{phase_name}_end"
            )

            cache_stats = self._cache.get_stats()
            phase.cache_hits = cache_stats.hits
            phase.cache_misses = cache_stats.misses

            phase.finalize()

            if workflow_id in self._active_workflows:
                self._active_workflows[workflow_id].add_phase(phase)

            self._logger.debug(
                f"Completed phase {phase_key}: {phase.duration_seconds: .2f}s"
            )

            return phase

    def record_metric(
        self,
        workflow_id: str,
        phase_name: str,
        metric_name: str,
        value: float,
        unit: str = "",
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        metric = PerformanceMetric(
            name=metric_name,
            value=value,
            unit=unit,
            metadata=metadata or {},
        )

        phase_key = f"{workflow_id}: {phase_name}"

        with self._lock:
            if phase_key in self._active_phases:
                self._active_phases[phase_key].metrics.append(metric)
            else:
                self._logger.warning(
                    f"Phase {phase_key} not found for metric {metric_name}"
                )

    def record_parallel_operation(self, workflow_id: str, phase_name: str) -> None:
        phase_key = f"{workflow_id}: {phase_name}"

        with self._lock:
            if phase_key in self._active_phases:
                self._active_phases[phase_key].parallel_operations += 1

    def record_sequential_operation(self, workflow_id: str, phase_name: str) -> None:
        phase_key = f"{workflow_id}: {phase_name}"

        with self._lock:
            if phase_key in self._active_phases:
                self._active_phases[phase_key].sequential_operations += 1

    def benchmark_operation(
        self, operation_name: str, duration_seconds: float
    ) -> PerformanceBenchmark:
        with self._lock:
            history = self._benchmarks[operation_name]
            history.append(duration_seconds)

            if len(history) > 1:
                sorted_history = sorted(history)
                baseline = sorted_history[len(sorted_history) // 2]

                return PerformanceBenchmark(
                    operation_name=operation_name,
                    baseline_duration_seconds=baseline,
                    current_duration_seconds=duration_seconds,
                )
            else:
                return PerformanceBenchmark(
                    operation_name=operation_name,
                    baseline_duration_seconds=duration_seconds,
                    current_duration_seconds=duration_seconds,
                )

    def get_performance_summary(self, last_n_workflows: int = 10) -> dict[str, Any]:
        with self._lock:
            recent_workflows = list[t.Any](self._completed_workflows)[
                -last_n_workflows:
            ]

            if not recent_workflows:
                return {"message": "No completed workflows to analyze"}

            basic_stats = self._calculate_basic_workflow_stats(recent_workflows)
            cache_stats = self._calculate_cache_statistics(recent_workflows)
            parallel_stats = self._calculate_parallelization_statistics(
                recent_workflows
            )

            return (
                {
                    "workflows_analyzed": len(recent_workflows),
                }
                | basic_stats
                | cache_stats
                | parallel_stats
                | {}
            )

    def _calculate_basic_workflow_stats(
        self, workflows: list[WorkflowPerformance]
    ) -> dict[str, Any]:
        total_duration = sum(w.total_duration_seconds for w in workflows)
        avg_duration = total_duration / len(workflows)
        avg_score = sum(w.performance_score for w in workflows) / len(workflows)
        success_rate = sum(1 for w in workflows if w.overall_success) / len(workflows)

        return {
            "avg_duration_seconds": round(avg_duration, 2),
            "avg_performance_score": round(avg_score, 1),
            "success_rate": round(success_rate, 2),
        }

    def _calculate_cache_statistics(
        self, workflows: list[WorkflowPerformance]
    ) -> dict[str, Any]:
        total_cache_hits = sum(sum(p.cache_hits for p in w.phases) for w in workflows)
        total_cache_misses = sum(
            sum(p.cache_misses for p in w.phases) for w in workflows
        )

        cache_hit_ratio = (
            total_cache_hits / (total_cache_hits + total_cache_misses)
            if total_cache_hits + total_cache_misses > 0
            else 0
        )

        return {
            "cache_hit_ratio": round(cache_hit_ratio, 2),
            "total_cache_hits": total_cache_hits,
            "total_cache_misses": total_cache_misses,
        }

    def _calculate_parallelization_statistics(
        self, workflows: list[WorkflowPerformance]
    ) -> dict[str, Any]:
        total_parallel = sum(
            sum(p.parallel_operations for p in w.phases) for w in workflows
        )
        total_sequential = sum(
            sum(p.sequential_operations for p in w.phases) for w in workflows
        )

        parallel_ratio = (
            total_parallel / (total_parallel + total_sequential)
            if total_parallel + total_sequential > 0
            else 0
        )

        return {
            "parallel_operation_ratio": round(parallel_ratio, 2),
            "total_parallel_operations": total_parallel,
            "total_sequential_operations": total_sequential,
        }

    def get_benchmark_trends(self) -> dict[str, dict[str, Any]]:
        trends = {}

        with self._lock:
            for operation_name, history in self._benchmarks.items():
                if len(history) < 2:
                    continue

                history_list = list[t.Any](history)
                basic_stats = self._calculate_benchmark_basic_stats(history_list)
                trend_percentage = self._calculate_trend_percentage(history_list)

                trends[operation_name] = basic_stats | {
                    "trend_percentage": round(trend_percentage, 1),
                    "sample_count": len(history_list),
                }

        return trends

    def _calculate_benchmark_basic_stats(
        self, history_list: list[float]
    ) -> dict[str, float]:
        avg_duration = sum(history_list) / len(history_list)
        min_duration = min(history_list)
        max_duration = max(history_list)

        return {
            "avg_duration_seconds": round(avg_duration, 3),
            "min_duration_seconds": round(min_duration, 3),
            "max_duration_seconds": round(max_duration, 3),
        }

    def _calculate_trend_percentage(self, history_list: list[float]) -> float:
        if len(history_list) < 5:
            return 0.0

        recent_avg = sum(history_list[-5:]) / 5
        older_avg = (
            sum(history_list[:-5]) / len(history_list[:-5])
            if len(history_list) > 5
            else recent_avg
        )

        return ((older_avg - recent_avg) / older_avg * 100) if older_avg > 0 else 0.0

    def export_performance_data(self, output_path: Path) -> None:
        with self._lock:
            data = {
                "export_timestamp": datetime.now().isoformat(),
                "completed_workflows": [
                    {
                        "workflow_id": w.workflow_id,
                        "start_time": w.start_time.isoformat(),
                        "end_time": w.end_time.isoformat() if w.end_time else None,
                        "duration_seconds": w.total_duration_seconds,
                        "performance_score": w.performance_score,
                        "success": w.overall_success,
                        "phases": [
                            {
                                "name": p.phase_name,
                                "duration_seconds": p.duration_seconds,
                                "memory_peak_mb": p.memory_peak_mb,
                                "cache_hits": p.cache_hits,
                                "cache_misses": p.cache_misses,
                                "parallel_operations": p.parallel_operations,
                                "sequential_operations": p.sequential_operations,
                                "success": p.success,
                            }
                            for p in w.phases
                        ],
                    }
                    for w in self._completed_workflows
                ],
                "benchmarks": {
                    name: list[t.Any](history)
                    for name, history in self._benchmarks.items()
                },
                "summary": self.get_performance_summary(),
                "trends": self.get_benchmark_trends(),
            }

        with output_path.open("w") as f:
            json.dump(data, f, indent=2)

        self._logger.info(f"Exported performance data to {output_path}")

    def _check_performance_warnings(self, workflow: WorkflowPerformance) -> None:
        warnings = []

        warnings.extend(self._check_duration_warning(workflow))
        warnings.extend(self._check_memory_warning(workflow))
        warnings.extend(self._check_cache_warning(workflow))

        for warning in warnings:
            self._logger.debug(
                f"Performance warning for {workflow.workflow_id}: {warning}"
            )

    def _check_duration_warning(self, workflow: WorkflowPerformance) -> list[str]:
        if (
            workflow.total_duration_seconds
            > self._warning_thresholds["duration_seconds"]
        ):
            return [
                f"Slow workflow duration: {workflow.total_duration_seconds: .1f}s "
                f"(threshold: {self._warning_thresholds['duration_seconds']}s)"
            ]
        return []

    def _check_memory_warning(self, workflow: WorkflowPerformance) -> list[str]:
        max_memory = max((p.memory_peak_mb for p in workflow.phases), default=0)
        if max_memory > self._warning_thresholds["memory_mb"]:
            return [
                f"High memory usage: {max_memory: .1f}MB "
                f"(threshold: {self._warning_thresholds['memory_mb']}MB)"
            ]
        return []

    def _check_cache_warning(self, workflow: WorkflowPerformance) -> list[str]:
        total_hits = sum(p.cache_hits for p in workflow.phases)
        total_misses = sum(p.cache_misses for p in workflow.phases)

        if total_hits + total_misses > 0:
            hit_ratio = total_hits / (total_hits + total_misses)
            if hit_ratio < self._warning_thresholds["cache_hit_ratio"]:
                return [
                    f"Low cache hit ratio: {hit_ratio: .2f} "
                    f"(threshold: {self._warning_thresholds['cache_hit_ratio']})"
                ]
        return []


_global_monitor: PerformanceMonitor | None = None
_monitor_lock = Lock()


def get_performance_monitor() -> PerformanceMonitor:
    global _global_monitor
    with _monitor_lock:
        if _global_monitor is None:
            _global_monitor = PerformanceMonitor(logger=depends.get_sync(Logger))
        return _global_monitor


class phase_monitor:
    def __init__(self, workflow_id: str, phase_name: str):
        self.workflow_id = workflow_id
        self.phase_name = phase_name
        self.monitor = get_performance_monitor()

    def __enter__(self) -> "phase_monitor":
        self.monitor.start_phase(self.workflow_id, self.phase_name)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        success = exc_type is None
        self.monitor.end_phase(self.workflow_id, self.phase_name, success)

    def record_parallel_op(self) -> None:
        self.monitor.record_parallel_operation(self.workflow_id, self.phase_name)

    def record_sequential_op(self) -> None:
        self.monitor.record_sequential_operation(self.workflow_id, self.phase_name)

    def record_metric(self, name: str, value: float, unit: str = "") -> None:
        self.monitor.record_metric(self.workflow_id, self.phase_name, name, value, unit)

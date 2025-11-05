"""Real-time metrics collection service for unified monitoring dashboard."""

import asyncio
import logging
import time
import typing as t
from collections import deque
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from acb.console import Console
from acb.depends import depends

from crackerjack.monitoring.ai_agent_watchdog import AgentPerformanceMetrics
from crackerjack.services.acb_cache_adapter import CrackerjackCache

logger = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """System-level performance metrics."""

    cpu_usage: float = 0.0
    memory_usage_mb: float = 0.0
    disk_usage_gb: float = 0.0
    active_processes: int = 0
    uptime_seconds: float = 0.0

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class QualityMetrics:
    """Code quality and workflow metrics."""

    total_issues_found: int = 0
    issues_fixed: int = 0
    success_rate: float = 0.0
    average_confidence: float = 0.0
    test_coverage: float = 0.0
    complexity_violations: int = 0
    security_issues: int = 0
    performance_issues: int = 0

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class WorkflowMetrics:
    """Workflow execution and timing metrics."""

    jobs_completed: int = 0
    jobs_failed: int = 0
    average_job_duration: float = 0.0
    fastest_job_time: float = 0.0
    slowest_job_time: float = 0.0
    queue_depth: int = 0
    throughput_per_hour: float = 0.0

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class AgentMetrics:
    """AI agent performance and utilization metrics."""

    active_agents: int = 0
    total_fixes_applied: int = 0
    cache_hit_rate: float = 0.0
    average_response_time: float = 0.0
    agent_effectiveness: dict[str, float] = field(default_factory=dict[str, t.Any])
    issue_type_distribution: dict[str, int] = field(default_factory=dict[str, t.Any])

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class UnifiedDashboardMetrics:
    """Combined metrics for unified dashboard display."""

    timestamp: datetime = field(default_factory=datetime.now)
    system: SystemMetrics = field(default_factory=SystemMetrics)
    quality: QualityMetrics = field(default_factory=QualityMetrics)
    workflow: WorkflowMetrics = field(default_factory=WorkflowMetrics)
    agents: AgentMetrics = field(default_factory=AgentMetrics)

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "system": self.system.to_dict(),
            "quality": self.quality.to_dict(),
            "workflow": self.workflow.to_dict(),
            "agents": self.agents.to_dict(),
        }


class MetricsCollector:
    """
    Real-time metrics collection service for unified monitoring dashboard.

    Collects and aggregates metrics from multiple sources:
    - System performance (CPU, memory, disk)
    - Code quality (issues, coverage, complexity)
    - Workflow execution (jobs, timing, throughput)
    - AI agent performance (fixes, confidence, cache hits)
    """

    def __init__(self, cache: CrackerjackCache | None = None):
        self.console = depends.get_sync(Console)
        self.cache = cache or CrackerjackCache()

        self.is_collecting = False
        self.collection_interval = 5.0  # seconds
        self.history_size = 100

        # Metrics storage
        self.metrics_history: deque[UnifiedDashboardMetrics] = deque(
            maxlen=self.history_size
        )
        self.current_metrics = UnifiedDashboardMetrics()

        # Agent performance tracking
        self.agent_metrics: dict[str, AgentPerformanceMetrics] = {}

        # Workflow tracking
        self.job_start_times: dict[str, float] = {}
        self.job_durations: list[float] = []

        # Collection tasks
        self.collection_task: asyncio.Task[t.Any] | None = None
        self.listeners: list[Callable[[UnifiedDashboardMetrics], None]] = []

    async def start_collection(self) -> None:
        """Start the metrics collection service."""
        if self.is_collecting:
            logger.warning("Metrics collection already running")
            return

        self.is_collecting = True
        self.collection_task = asyncio.create_task(self._collection_loop())

        logger.info("🔍 Metrics collection started")

    async def stop_collection(self) -> None:
        """Stop the metrics collection service."""
        self.is_collecting = False

        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass

        logger.info("🔍 Metrics collection stopped")

    def add_metrics_listener(
        self, callback: Callable[[UnifiedDashboardMetrics], None]
    ) -> None:
        """Add a callback to be notified of new metrics."""
        self.listeners.append(callback)

    def remove_metrics_listener(
        self, callback: Callable[[UnifiedDashboardMetrics], None]
    ) -> None:
        """Remove a metrics callback."""
        if callback in self.listeners:
            self.listeners.remove(callback)

    async def _collection_loop(self) -> None:
        """Main metrics collection loop."""
        while self.is_collecting:
            try:
                await self._collect_all_metrics()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
                await asyncio.sleep(self.collection_interval)

    async def _collect_all_metrics(self) -> None:
        """Collect all metrics from various sources."""
        # Collect system metrics
        system_metrics = await self._collect_system_metrics()

        # Collect quality metrics
        quality_metrics = await self._collect_quality_metrics()

        # Collect workflow metrics
        workflow_metrics = await self._collect_workflow_metrics()

        # Collect agent metrics
        agent_metrics = await self._collect_agent_metrics()

        # Create unified metrics
        unified_metrics = UnifiedDashboardMetrics(
            system=system_metrics,
            quality=quality_metrics,
            workflow=workflow_metrics,
            agents=agent_metrics,
        )

        # Store metrics
        self.current_metrics = unified_metrics
        self.metrics_history.append(unified_metrics)

        # Notify listeners
        for listener in self.listeners:
            try:
                listener(unified_metrics)
            except Exception as e:
                logger.error(f"Error in metrics listener: {e}")

    async def _collect_system_metrics(self) -> SystemMetrics:
        """Collect system performance metrics."""
        try:
            import psutil

            cpu_usage = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            memory_mb = memory.used / (1024 * 1024)
            disk = psutil.disk_usage("/")
            disk_gb = disk.used / (1024 * 1024 * 1024)

            return SystemMetrics(
                cpu_usage=cpu_usage,
                memory_usage_mb=memory_mb,
                disk_usage_gb=disk_gb,
                active_processes=len(psutil.pids()),
                uptime_seconds=time.time() - psutil.boot_time(),
            )
        except ImportError:
            # Fallback if psutil not available
            return SystemMetrics()
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return SystemMetrics()

    async def _collect_quality_metrics(self) -> QualityMetrics:
        """Collect code quality metrics."""
        try:
            # Try to get metrics from cache or recent runs
            quality_data = self.cache.get("quality_metrics", {})

            return QualityMetrics(
                total_issues_found=quality_data.get("total_issues", 0),
                issues_fixed=quality_data.get("issues_fixed", 0),
                success_rate=quality_data.get("success_rate", 0.0),
                average_confidence=quality_data.get("avg_confidence", 0.0),
                test_coverage=quality_data.get("test_coverage", 0.0),
                complexity_violations=quality_data.get("complexity_violations", 0),
                security_issues=quality_data.get("security_issues", 0),
                performance_issues=quality_data.get("performance_issues", 0),
            )
        except Exception as e:
            logger.error(f"Error collecting quality metrics: {e}")
            return QualityMetrics()

    async def _collect_workflow_metrics(self) -> WorkflowMetrics:
        """Collect workflow execution metrics."""
        try:
            workflow_data = self.cache.get("workflow_metrics", {})

            # Calculate throughput
            recent_jobs = len([d for d in self.job_durations if d > 0])
            throughput = recent_jobs / max(
                1, self.collection_interval / 3600
            )  # per hour

            return WorkflowMetrics(
                jobs_completed=workflow_data.get("jobs_completed", 0),
                jobs_failed=workflow_data.get("jobs_failed", 0),
                average_job_duration=sum(self.job_durations)
                / max(1, len(self.job_durations)),
                fastest_job_time=min(self.job_durations) if self.job_durations else 0.0,
                slowest_job_time=max(self.job_durations) if self.job_durations else 0.0,
                queue_depth=workflow_data.get("queue_depth", 0),
                throughput_per_hour=throughput,
            )
        except Exception as e:
            logger.error(f"Error collecting workflow metrics: {e}")
            return WorkflowMetrics()

    async def _collect_agent_metrics(self) -> AgentMetrics:
        """Collect AI agent performance metrics."""
        try:
            agent_data = self.cache.get("agent_metrics", {})

            # Calculate agent effectiveness
            effectiveness = {}
            issue_distribution: dict[str, int] = {}
            total_fixes = 0
            total_response_time = 0.0

            for agent_name, metrics in self.agent_metrics.items():
                if metrics.total_issues_handled > 0:
                    success_rate = (
                        metrics.successful_fixes / metrics.total_issues_handled
                    )
                    effectiveness[agent_name] = success_rate
                    total_fixes += metrics.successful_fixes
                    total_response_time += metrics.average_execution_time

                    for issue_type, count in metrics.issue_types_handled.items():
                        issue_distribution[issue_type.value] = (
                            issue_distribution.get(issue_type.value, 0) + count
                        )

            # Calculate cache hit rate from agent usage
            cache_stats = agent_data.get("cache_stats", {})
            cache_hits = cache_stats.get("hits", 0)
            cache_misses = cache_stats.get("misses", 0)
            cache_hit_rate = cache_hits / max(1, cache_hits + cache_misses)

            return AgentMetrics(
                active_agents=len(self.agent_metrics),
                total_fixes_applied=total_fixes,
                cache_hit_rate=cache_hit_rate,
                average_response_time=total_response_time
                / max(1, len(self.agent_metrics)),
                agent_effectiveness=effectiveness,
                issue_type_distribution=issue_distribution,
            )
        except Exception as e:
            logger.error(f"Error collecting agent metrics: {e}")
            return AgentMetrics()

    # Integration methods for external systems

    def record_job_start(self, job_id: str) -> None:
        """Record the start of a job for timing."""
        self.job_start_times[job_id] = time.time()

    def record_job_completion(self, job_id: str, success: bool = True) -> None:
        """Record job completion and calculate duration."""
        if job_id in self.job_start_times:
            duration = time.time() - self.job_start_times[job_id]
            self.job_durations.append(duration)
            del self.job_start_times[job_id]

            # Keep only recent job durations
            if len(self.job_durations) > self.history_size:
                self.job_durations = self.job_durations[-self.history_size :]

            # Update cache
            workflow_data = self.cache.get("workflow_metrics", {})
            if success:
                workflow_data["jobs_completed"] = (
                    workflow_data.get("jobs_completed", 0) + 1
                )
            else:
                workflow_data["jobs_failed"] = workflow_data.get("jobs_failed", 0) + 1
            self.cache.set("workflow_metrics", workflow_data)

    def record_agent_performance(
        self, agent_name: str, metrics: AgentPerformanceMetrics
    ) -> None:
        """Record agent performance metrics."""
        self.agent_metrics[agent_name] = metrics

    def record_quality_data(
        self, issues_found: int, issues_fixed: int, coverage: float, success_rate: float
    ) -> None:
        """Record quality metrics from a run."""
        quality_data = {
            "total_issues": issues_found,
            "issues_fixed": issues_fixed,
            "test_coverage": coverage,
            "success_rate": success_rate,
            "timestamp": datetime.now().isoformat(),
        }
        self.cache.set("quality_metrics", quality_data)

    def get_current_metrics(self) -> UnifiedDashboardMetrics:
        """Get the current metrics snapshot."""
        return self.current_metrics

    def get_metrics_history(self, hours: int = 1) -> list[UnifiedDashboardMetrics]:
        """Get metrics history for the specified number of hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [m for m in self.metrics_history if m.timestamp > cutoff]

    def get_metrics_summary(self) -> dict[str, t.Any]:
        """Get a summary of current metrics for display."""
        metrics = self.current_metrics

        return {
            "system": {
                "cpu": f"{metrics.system.cpu_usage:.1f}%",
                "memory": f"{metrics.system.memory_usage_mb:.0f}MB",
                "disk": f"{metrics.system.disk_usage_gb:.1f}GB",
                "uptime": self._format_uptime(metrics.system.uptime_seconds),
            },
            "quality": {
                "success_rate": f"{metrics.quality.success_rate:.1%}",
                "issues_fixed": metrics.quality.issues_fixed,
                "test_coverage": f"{metrics.quality.test_coverage:.1%}",
                "avg_confidence": f"{metrics.quality.average_confidence:.2f}",
            },
            "workflow": {
                "jobs_completed": metrics.workflow.jobs_completed,
                "avg_duration": f"{metrics.workflow.average_job_duration:.1f}s",
                "throughput": f"{metrics.workflow.throughput_per_hour:.1f}/h",
                "queue_depth": metrics.workflow.queue_depth,
            },
            "agents": {
                "active_agents": metrics.agents.active_agents,
                "total_fixes": metrics.agents.total_fixes_applied,
                "cache_hit_rate": f"{metrics.agents.cache_hit_rate:.1%}",
                "avg_response": f"{metrics.agents.average_response_time:.1f}s",
            },
        }

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime in human-readable format."""
        if seconds < 3600:
            return f"{seconds / 60:.0f}m"
        elif seconds < 86400:
            return f"{seconds / 3600:.0f}h"
        return f"{seconds / 86400:.0f}d"

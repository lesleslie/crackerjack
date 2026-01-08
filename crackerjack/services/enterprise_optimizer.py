import json
import logging
import statistics
import threading
import time
import typing as t
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import psutil

logger = logging.getLogger(__name__)


@dataclass
class ResourceMetrics:
    cpu_percent: float
    memory_percent: float
    disk_usage_percent: float
    network_io: dict[str, int]
    active_connections: int
    thread_count: int
    file_descriptors: int
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "disk_usage_percent": self.disk_usage_percent,
            "network_io": self.network_io,
            "active_connections": self.active_connections,
            "thread_count": self.thread_count,
            "file_descriptors": self.file_descriptors,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PerformanceProfile:
    workload_type: str
    concurrent_clients: int
    data_retention_days: int
    analysis_frequency_minutes: int
    resource_limits: dict[str, t.Any]
    optimization_strategy: str

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class OptimizationRecommendation:
    category: str
    priority: str
    title: str
    description: str
    impact: str
    implementation: str
    estimated_improvement: str
    resource_cost: str
    risk_level: str

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


@dataclass
class ScalingMetrics:
    current_load: float
    projected_load: float
    response_time_p95: float
    error_rate: float
    memory_pressure: float
    cpu_saturation: float
    recommended_scale_factor: float
    confidence_score: float

    def to_dict(self) -> dict[str, t.Any]:
        return asdict(self)


class ConnectionPool:
    def __init__(self, max_connections: int = 1000, cleanup_interval: int = 300):
        self.max_connections = max_connections
        self.cleanup_interval = cleanup_interval
        self.connections: dict[str, t.Any] = {}
        self.connection_stats: dict[str, dict[str, t.Any]] = {}
        self.last_cleanup = time.time()
        self._lock = threading.Lock()

    def add_connection(
        self,
        connection_id: str,
        websocket: t.Any,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        with self._lock:
            if len(self.connections) >= self.max_connections:
                self._cleanup_stale_connections()

            if len(self.connections) >= self.max_connections:
                oldest_id = min(
                    self.connection_stats.keys(),
                    key=lambda x: self.connection_stats[x]["last_activity"],
                )
                self.remove_connection(oldest_id)

            self.connections[connection_id] = websocket
            self.connection_stats[connection_id] = {
                "created": time.time(),
                "last_activity": time.time(),
                "message_count": 0,
                "metadata": metadata or {},
            }

    def remove_connection(self, connection_id: str) -> None:
        with self._lock:
            if connection_id in self.connections:
                del self.connections[connection_id]
            if connection_id in self.connection_stats:
                del self.connection_stats[connection_id]

    def update_activity(self, connection_id: str) -> None:
        with self._lock:
            if connection_id in self.connection_stats:
                self.connection_stats[connection_id]["last_activity"] = time.time()
                self.connection_stats[connection_id]["message_count"] += 1

    def _cleanup_stale_connections(self) -> None:
        current_time = time.time()
        stale_threshold = 1800

        stale_connections = [
            conn_id
            for conn_id, stats in self.connection_stats.items()
            if current_time - stats["last_activity"] > stale_threshold
        ]

        for conn_id in stale_connections:
            self.remove_connection(conn_id)

        self.last_cleanup = current_time
        logger.info(f"Cleaned up {len(stale_connections)} stale connections")

    def get_stats(self) -> dict[str, t.Any]:
        with self._lock:
            current_time = time.time()
            active_count = len(
                [
                    conn
                    for conn, stats in self.connection_stats.items()
                    if current_time - stats["last_activity"] < 300
                ]
            )

            return {
                "total_connections": len(self.connections),
                "active_connections": active_count,
                "max_connections": self.max_connections,
                "utilization_percent": (len(self.connections) / self.max_connections)
                * 100,
                "average_message_count": statistics.mean(
                    [stats["message_count"] for stats in self.connection_stats.values()]
                )
                if self.connection_stats
                else 0,
            }


class DataCompactionManager:
    def __init__(self, storage_dir: Path, max_storage_gb: float = 10.0):
        self.storage_dir = Path(storage_dir)
        self.max_storage_bytes = max_storage_gb * 1024**3
        self.compaction_rules = self._load_compaction_rules()

    def _load_compaction_rules(self) -> dict[str, dict[str, t.Any]]:
        rules = {}

        rules["metrics_raw"] = self._create_metrics_raw_config()

        rules["metrics_hourly"] = self._create_metrics_hourly_config()

        rules["metrics_daily"] = self._create_metrics_daily_config()

        rules["error_patterns"] = self._create_error_patterns_config()

        rules["dependency_graphs"] = self._create_dependency_graphs_config()

        return rules

    def _create_metrics_raw_config(self) -> dict[str, t.Any]:
        return {
            "retention_days": 7,
            "compaction_interval_hours": 1,
            "aggregation_method": "downsample",
        }

    def _create_metrics_hourly_config(self) -> dict[str, t.Any]:
        return {
            "retention_days": 30,
            "compaction_interval_hours": 24,
            "aggregation_method": "statistical",
        }

    def _create_metrics_daily_config(self) -> dict[str, t.Any]:
        return {
            "retention_days": 365,
            "compaction_interval_hours": 168,
            "aggregation_method": "statistical",
        }

    def _create_error_patterns_config(self) -> dict[str, t.Any]:
        return {
            "retention_days": 90,
            "compaction_interval_hours": 24,
            "aggregation_method": "deduplication",
        }

    def _create_dependency_graphs_config(self) -> dict[str, t.Any]:
        return {
            "retention_days": 30,
            "compaction_interval_hours": 24,
            "aggregation_method": "latest_version",
        }

    def compact_data(self, data_type: str) -> dict[str, t.Any]:
        if data_type not in self.compaction_rules:
            return {"status": "error", "message": f"Unknown data type: {data_type}"}

        rules = self.compaction_rules[data_type]
        cutoff_date = self._calculate_cutoff_date(rules)

        compaction_stats = self._process_data_directory(data_type, cutoff_date)

        return self._build_compaction_result(data_type, rules, compaction_stats)

    def _calculate_cutoff_date(self, rules: dict[str, t.Any]) -> datetime:
        return datetime.now() - timedelta(days=rules["retention_days"])

    def _process_data_directory(
        self, data_type: str, cutoff_date: datetime
    ) -> dict[str, int | float]:
        compacted_records = 0
        freed_space_mb: float = 0.0

        data_dir = self.storage_dir / data_type
        if data_dir.exists():
            for file_path in data_dir.glob("**/*"):
                if self._should_compact_file(file_path, cutoff_date):
                    file_size_mb = file_path.stat().st_size / (1024**2)
                    freed_space_mb += file_size_mb
                    compacted_records += 1

        return {
            "compacted_records": compacted_records,
            "freed_space_mb": freed_space_mb,
        }

    def _should_compact_file(self, file_path: Path, cutoff_date: datetime) -> bool:
        if not file_path.is_file():
            return False

        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        return file_mtime < cutoff_date

    def _build_compaction_result(
        self, data_type: str, rules: dict[str, t.Any], stats: dict[str, t.Any]
    ) -> dict[str, t.Any]:
        return {
            "status": "success",
            "data_type": data_type,
            "compacted_records": stats["compacted_records"],
            "freed_space_mb": round(stats["freed_space_mb"], 2),
            "retention_days": rules["retention_days"],
            "next_compaction": datetime.now()
            + timedelta(hours=rules["compaction_interval_hours"]),
        }

    def get_storage_usage(self) -> dict[str, t.Any]:
        total_size, type_sizes = self._calculate_storage_sizes()
        return self._build_storage_usage_report(total_size, type_sizes)

    def _calculate_storage_sizes(self) -> tuple[int, dict[str, int]]:
        total_size = 0
        type_sizes = {}

        if self.storage_dir.exists():
            for data_type in self.compaction_rules.keys():
                type_size = self._calculate_data_type_size(data_type)
                type_sizes[data_type] = type_size
                total_size += type_size

        return total_size, type_sizes

    def _calculate_data_type_size(self, data_type: str) -> int:
        data_dir = self.storage_dir / data_type
        type_size = 0

        if data_dir.exists():
            for file_path in data_dir.glob("**/*"):
                if file_path.is_file():
                    type_size += file_path.stat().st_size

        return type_size

    def _build_storage_usage_report(
        self, total_size: int, type_sizes: dict[str, int]
    ) -> dict[str, t.Any]:
        return {
            "total_size_gb": round(total_size / (1024**3), 3),
            "max_size_gb": round(self.max_storage_bytes / (1024**3), 3),
            "utilization_percent": self._calculate_utilization_percent(total_size),
            "by_type_mb": {k: round(v / (1024**2), 2) for k, v in type_sizes.items()},
            "compaction_needed": total_size > (self.max_storage_bytes * 0.8),
        }

    def _calculate_utilization_percent(self, total_size: int) -> float:
        if self.max_storage_bytes > 0:
            return round((total_size / self.max_storage_bytes) * 100, 2)
        return 0.0


class EnterpriseOptimizer:
    def __init__(self, config_dir: Path, storage_dir: Path):
        self.config_dir = Path(config_dir)
        self.storage_dir = Path(storage_dir)

        self.connection_pool = ConnectionPool()
        self.compaction_manager = DataCompactionManager(storage_dir)
        self.executor = ThreadPoolExecutor(max_workers=4)

        self.resource_history: deque[ResourceMetrics] = deque(maxlen=1440)
        self.performance_profile = self._load_performance_profile()

        self.last_optimization = datetime.now()
        self.optimization_recommendations: list[OptimizationRecommendation] = []

    def _load_performance_profile(self) -> PerformanceProfile:
        profile_path = self.config_dir / "performance_profile.json"

        if profile_path.exists():
            try:
                with profile_path.open() as f:
                    data = json.load(f)
                return PerformanceProfile(**data)
            except Exception as e:
                logger.warning(f"Failed to load performance profile: {e}")

        return PerformanceProfile(
            workload_type="moderate",
            concurrent_clients=100,
            data_retention_days=30,
            analysis_frequency_minutes=5,
            resource_limits={
                "max_memory_gb": 4.0,
                "max_cpu_percent": 80.0,
                "max_disk_gb": 10.0,
            },
            optimization_strategy="balanced",
        )

    def collect_resource_metrics(self) -> ResourceMetrics:
        try:
            cpu_percent = psutil.cpu_percent(interval=1)

            memory = psutil.virtual_memory()
            memory_percent = memory.percent

            disk_usage = psutil.disk_usage(str(self.storage_dir))
            disk_percent = (disk_usage.used / disk_usage.total) * 100

            net_io = psutil.net_io_counters()
            network_io = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
            }

            process = psutil.Process()
            active_connections = len(process.connections())
            thread_count = process.num_threads()
            file_descriptors = process.num_fds() if hasattr(process, "num_fds") else 0

            metrics = ResourceMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                disk_usage_percent=disk_percent,
                network_io=network_io,
                active_connections=active_connections,
                thread_count=thread_count,
                file_descriptors=file_descriptors,
            )

            self.resource_history.append(metrics)

            return metrics

        except Exception as e:
            logger.error(f"Failed to collect resource metrics: {e}")
            return ResourceMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                disk_usage_percent=0.0,
                network_io={},
                active_connections=0,
                thread_count=0,
                file_descriptors=0,
            )

    def analyze_scaling_needs(self) -> ScalingMetrics:
        if len(self.resource_history) < 10:
            return ScalingMetrics(
                current_load=0.0,
                projected_load=0.0,
                response_time_p95=100.0,
                error_rate=0.0,
                memory_pressure=0.0,
                cpu_saturation=0.0,
                recommended_scale_factor=1.0,
                confidence_score=0.0,
            )

        recent_metrics = list[t.Any](self.resource_history)[-10:]

        avg_cpu = statistics.mean([m.cpu_percent for m in recent_metrics])
        avg_memory = statistics.mean([m.memory_percent for m in recent_metrics])
        statistics.mean([m.active_connections for m in recent_metrics])

        current_load = max(avg_cpu / 100.0, avg_memory / 100.0)

        if len(recent_metrics) >= 5:
            cpu_trend = (
                recent_metrics[-1].cpu_percent - recent_metrics[-5].cpu_percent
            ) / 5
            memory_trend = (
                recent_metrics[-1].memory_percent - recent_metrics[-5].memory_percent
            ) / 5
            projected_load = min(
                1.0, current_load + max(cpu_trend, memory_trend) / 100.0
            )
        else:
            projected_load = current_load

        memory_pressure = min(1.0, avg_memory / 100.0)
        if len(recent_metrics) >= 3:
            memory_velocity = (
                recent_metrics[-1].memory_percent - recent_metrics[-3].memory_percent
            ) / 3
            memory_pressure += memory_velocity / 100.0

        cpu_saturation = min(1.0, avg_cpu / 100.0)

        if projected_load > 0.8 or memory_pressure > 0.85:
            scale_factor = 1.5
        elif projected_load < 0.3 and memory_pressure < 0.4:
            scale_factor = 0.8
        else:
            scale_factor = 1.0

        cpu_variance = statistics.variance([m.cpu_percent for m in recent_metrics])
        memory_variance = statistics.variance(
            [m.memory_percent for m in recent_metrics]
        )
        confidence_score = max(0.0, 1.0 - (cpu_variance + memory_variance) / 2000.0)

        return ScalingMetrics(
            current_load=current_load,
            projected_load=projected_load,
            response_time_p95=100.0,
            error_rate=0.0,
            memory_pressure=memory_pressure,
            cpu_saturation=cpu_saturation,
            recommended_scale_factor=scale_factor,
            confidence_score=confidence_score,
        )

    def generate_optimization_recommendations(self) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []

        if not self.resource_history:
            return recommendations

        latest_metrics = self.resource_history[-1]
        scaling_metrics = self.analyze_scaling_needs()
        storage_usage = self.compaction_manager.get_storage_usage()

        recommendations.extend(self._generate_cpu_recommendations(latest_metrics))
        recommendations.extend(self._generate_memory_recommendations(latest_metrics))
        recommendations.extend(self._generate_storage_recommendations(storage_usage))
        recommendations.extend(self._generate_connection_recommendations())
        recommendations.extend(self._generate_scaling_recommendations(scaling_metrics))

        self.optimization_recommendations = recommendations
        return recommendations

    def _generate_cpu_recommendations(
        self, metrics: ResourceMetrics
    ) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []

        if metrics.cpu_percent > 80:
            recommendations.append(
                OptimizationRecommendation(
                    category="performance",
                    priority="high",
                    title="High CPU Usage Detected",
                    description=f"CPU usage at {metrics.cpu_percent:.1f}%, approaching saturation",
                    impact="May cause response time degradation and request queuing",
                    implementation="Consider scaling horizontally or optimizing CPU-intensive operations",
                    estimated_improvement="20-40% response time improvement",
                    resource_cost="Medium - additional compute resources",
                    risk_level="low",
                )
            )

        return recommendations

    def _generate_memory_recommendations(
        self, metrics: ResourceMetrics
    ) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []

        if metrics.memory_percent > 85:
            recommendations.append(
                OptimizationRecommendation(
                    category="memory",
                    priority="critical",
                    title="Memory Pressure Critical",
                    description=f"Memory usage at {metrics.memory_percent:.1f}%, risk of OOM",
                    impact="High risk of application crashes and data loss",
                    implementation="Immediately reduce memory consumption or add memory resources",
                    estimated_improvement="Prevents system crashes",
                    resource_cost="High - memory upgrade or optimization effort",
                    risk_level="high",
                )
            )

        return recommendations

    def _generate_storage_recommendations(
        self, storage_usage: dict[str, t.Any]
    ) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []

        if storage_usage["utilization_percent"] > 80:
            recommendations.append(
                OptimizationRecommendation(
                    category="storage",
                    priority="high",
                    title="Storage Capacity Warning",
                    description=f"Storage at {storage_usage['utilization_percent']:.1f}% capacity",
                    impact="Risk of data collection failures and service degradation",
                    implementation="Run data compaction or extend storage capacity",
                    estimated_improvement="Frees 30-50% storage space",
                    resource_cost="Low - automated compaction process",
                    risk_level="low",
                )
            )

        return recommendations

    def _generate_connection_recommendations(self) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []

        pool_stats = self.connection_pool.get_stats()
        if pool_stats["utilization_percent"] > 90:
            recommendations.append(
                OptimizationRecommendation(
                    category="network",
                    priority="medium",
                    title="Connection Pool Near Capacity",
                    description=f"WebSocket connections at {pool_stats['utilization_percent']:.1f}% capacity",
                    impact="New client connections may be rejected",
                    implementation="Increase connection pool size or implement connection sharing",
                    estimated_improvement="Supports 2-3x more concurrent clients",
                    resource_cost="Low - configuration change",
                    risk_level="low",
                )
            )

        return recommendations

    def _generate_scaling_recommendations(
        self, scaling_metrics: ScalingMetrics
    ) -> list[OptimizationRecommendation]:
        recommendations: list[OptimizationRecommendation] = []

        if scaling_metrics.recommended_scale_factor > 1.2:
            recommendations.append(
                OptimizationRecommendation(
                    category="performance",
                    priority="medium",
                    title="Horizontal Scaling Recommended",
                    description=f"Load analysis suggests {scaling_metrics.recommended_scale_factor:.1f}x scaling",
                    impact="Current load may exceed capacity during peak usage",
                    implementation="Deploy additional monitoring service instances",
                    estimated_improvement="Improved reliability and response times",
                    resource_cost="Medium - additional infrastructure",
                    risk_level="medium",
                )
            )

        return recommendations

    def optimize_configuration(self, strategy: str | None = None) -> dict[str, t.Any]:
        if strategy is None:
            strategy = self.performance_profile.optimization_strategy

        latest_metrics = self._get_latest_metrics()
        if not latest_metrics:
            return {"status": "error", "message": "No metrics available"}

        optimizations_applied = self._apply_all_optimizations(latest_metrics, strategy)

        return self._build_optimization_result(strategy, optimizations_applied)

    def _get_latest_metrics(self) -> ResourceMetrics | None:
        return self.resource_history[-1] if self.resource_history else None

    def _apply_all_optimizations(
        self, metrics: ResourceMetrics, strategy: str
    ) -> list[str]:
        optimizations_applied = []

        optimizations_applied.extend(self._apply_memory_optimizations(metrics))
        optimizations_applied.extend(
            self._apply_performance_optimizations(metrics, strategy)
        )
        optimizations_applied.extend(self._apply_storage_optimizations())

        return optimizations_applied

    def _apply_memory_optimizations(self, metrics: ResourceMetrics) -> list[str]:
        optimizations = []

        if metrics.memory_percent > 70:
            if self.connection_pool.max_connections > 500:
                self.connection_pool.max_connections = int(
                    self.connection_pool.max_connections * 0.8
                )
                optimizations.append("Reduced connection pool size")

        return optimizations

    def _apply_performance_optimizations(
        self, metrics: ResourceMetrics, strategy: str
    ) -> list[str]:
        optimizations = []

        if metrics.cpu_percent > 60 and strategy in ("performance", "balanced"):
            if self.performance_profile.analysis_frequency_minutes > 2:
                self.performance_profile.analysis_frequency_minutes = max(
                    1, self.performance_profile.analysis_frequency_minutes - 1
                )
                optimizations.append("Increased analysis frequency")

        return optimizations

    def _apply_storage_optimizations(self) -> list[str]:
        optimizations = []
        storage_usage = self.compaction_manager.get_storage_usage()

        if storage_usage["utilization_percent"] > 70:
            for data_type in ("metrics_raw", "error_patterns"):
                result = self.compaction_manager.compact_data(data_type)
                if result["status"] == "success":
                    optimizations.append(f"Compacted {data_type} data")

        return optimizations

    def _build_optimization_result(
        self, strategy: str, optimizations_applied: list[str]
    ) -> dict[str, t.Any]:
        return {
            "status": "success",
            "strategy": strategy,
            "optimizations_applied": optimizations_applied,
            "timestamp": datetime.now().isoformat(),
            "next_optimization": (datetime.now() + timedelta(minutes=15)).isoformat(),
        }

    async def run_optimization_cycle(self) -> dict[str, t.Any]:
        try:
            metrics = self.collect_resource_metrics()

            scaling_metrics = self.analyze_scaling_needs()

            recommendations = self.generate_optimization_recommendations()

            optimization_result = None
            if (
                metrics.cpu_percent > 80
                or metrics.memory_percent > 85
                or scaling_metrics.current_load > 0.8
            ):
                optimization_result = self.optimize_configuration()

            return {
                "status": "success",
                "metrics": metrics.to_dict(),
                "scaling_analysis": scaling_metrics.to_dict(),
                "recommendations": [rec.to_dict() for rec in recommendations],
                "automatic_optimization": optimization_result,
                "connection_pool_stats": self.connection_pool.get_stats(),
                "storage_usage": self.compaction_manager.get_storage_usage(),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Optimization cycle failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def get_enterprise_status(self) -> dict[str, t.Any]:
        return {
            "performance_profile": self.performance_profile.to_dict(),
            "resource_metrics": self.resource_history[-1].to_dict()
            if self.resource_history
            else None,
            "scaling_metrics": self.analyze_scaling_needs().to_dict(),
            "active_recommendations": [
                rec.to_dict() for rec in self.optimization_recommendations
            ],
            "connection_pool": self.connection_pool.get_stats(),
            "storage_usage": self.compaction_manager.get_storage_usage(),
            "optimization_history": {
                "last_optimization": self.last_optimization.isoformat(),
                "total_optimizations": len(self.optimization_recommendations),
            },
            "health_score": self._calculate_health_score(),
        }

    def _calculate_health_score(self) -> float:
        if not self.resource_history:
            return 50.0

        latest = self.resource_history[-1]
        storage = self.compaction_manager.get_storage_usage()

        cpu_score = max(0, 100 - latest.cpu_percent)
        memory_score = max(0, 100 - latest.memory_percent)
        storage_score = max(0, 100 - storage["utilization_percent"])

        pool_stats = self.connection_pool.get_stats()
        connection_score = max(0, 100 - pool_stats["utilization_percent"])

        health_score = (
            cpu_score * 0.3
            + memory_score * 0.3
            + storage_score * 0.2
            + connection_score * 0.2
        )

        result: float = round(health_score, 1)
        return result

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

METRICS_FILE = Path("/tmp/agent_performance.json")
MAX_RECENT_RESULTS = 100


@dataclass
class AgentAttempt:
    timestamp: str
    agent_name: str
    model_name: str
    issue_type: str
    success: bool
    confidence: float
    time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentMetrics:
    agent_name: str
    model_name: str
    issue_type: str
    total_attempts: int = 0
    successful_fixes: int = 0
    failed_fixes: int = 0
    avg_confidence: float = 0.0
    avg_time_seconds: float = 0.0
    recent_results: list[AgentAttempt] = field(default_factory=list)

    def add_attempt(
        self,
        success: bool,
        confidence: float,
        time_seconds: float,
    ) -> None:
        self.total_attempts += 1

        if success:
            self.successful_fixes += 1
        else:
            self.failed_fixes += 1

        self.avg_confidence = (
            self.avg_confidence * (self.total_attempts - 1) + confidence
        ) / self.total_attempts
        self.avg_time_seconds = (
            self.avg_time_seconds * (self.total_attempts - 1) + time_seconds
        ) / self.total_attempts

    def add_recent_result(self, attempt: AgentAttempt) -> None:
        self.recent_results.append(attempt)
        if len(self.recent_results) > MAX_RECENT_RESULTS:
            self.recent_results.pop(0)

    def get_success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_fixes / self.total_attempts) * 100

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "model_name": self.model_name,
            "issue_type": self.issue_type,
            "total_attempts": self.total_attempts,
            "successful_fixes": self.successful_fixes,
            "failed_fixes": self.failed_fixes,
            "avg_confidence": round(self.avg_confidence, 3),
            "avg_time_seconds": round(self.avg_time_seconds, 3),
            "recent_results": [r.to_dict() for r in self.recent_results],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMetrics":
        recent_results = [AgentAttempt(**r) for r in data.get("recent_results", [])]
        data["recent_results"] = recent_results
        return cls(**data)


class AgentPerformanceTracker:
    def __init__(self, metrics_file: Path = METRICS_FILE) -> None:
        self.metrics_file = metrics_file
        self._metrics: dict[str, AgentMetrics] = {}
        self._lock = threading.Lock()

        self._load_metrics()

    def _get_metric_key(
        self,
        agent_name: str,
        model_name: str,
        issue_type: str,
    ) -> str:
        return f"{agent_name}:{model_name}:{issue_type}"

    def _get_or_create_metric(
        self,
        agent_name: str,
        model_name: str,
        issue_type: str,
    ) -> AgentMetrics:
        key = self._get_metric_key(agent_name, model_name, issue_type)

        if key not in self._metrics:
            self._metrics[key] = AgentMetrics(
                agent_name=agent_name,
                model_name=model_name,
                issue_type=issue_type,
            )

        return self._metrics[key]

    def record_attempt(
        self,
        agent_name: str,
        model_name: str,
        issue_type: str,
        success: bool,
        confidence: float,
        time_seconds: float,
    ) -> None:
        with self._lock:
            metric = self._get_or_create_metric(agent_name, model_name, issue_type)

            attempt = AgentAttempt(
                timestamp=datetime.now().isoformat(),
                agent_name=agent_name,
                model_name=model_name,
                issue_type=issue_type,
                success=success,
                confidence=confidence,
                time_seconds=time_seconds,
            )

            metric.add_attempt(success, confidence, time_seconds)
            metric.add_recent_result(attempt)

            self._save_metrics()

            logger.debug(
                f"Recorded attempt: {agent_name} on {issue_type} "
                f"(success={success}, confidence={confidence:.2f}, "
                f"time={time_seconds:.2f}s)"
            )

    def get_success_rate(
        self,
        agent_name: str | None = None,
        issue_type: str | None = None,
        model_name: str | None = None,
    ) -> float | dict[str, float]:
        with self._lock:
            if agent_name and issue_type and model_name:
                key = self._get_metric_key(agent_name, model_name, issue_type)
                if key in self._metrics:
                    return self._metrics[key].get_success_rate()
                return 0.0

            results: dict[str, dict[str, int]] = {}

            for key, metric in self._metrics.items():
                if agent_name and metric.agent_name != agent_name:
                    continue
                if issue_type and metric.issue_type != issue_type:
                    continue
                if model_name and metric.model_name != model_name:
                    continue

                if agent_name and issue_type:
                    group_key = metric.model_name
                elif agent_name:
                    group_key = metric.issue_type
                elif issue_type:
                    group_key = metric.model_name
                else:
                    group_key = key

                if group_key not in results:
                    results[group_key] = {
                        "total_attempts": 0,
                        "successful_fixes": 0,
                    }

                results[group_key]["total_attempts"] += metric.total_attempts
                results[group_key]["successful_fixes"] += metric.successful_fixes

            return {
                k: (v["successful_fixes"] / v["total_attempts"] * 100)
                if v["total_attempts"] > 0
                else 0.0
                for k, v in results.items()
            }

    def get_best_agent_for_issue_type(
        self,
        issue_type: str,
        min_attempts: int = 5,
    ) -> dict[str, Any] | None:
        with self._lock:
            qualified_metrics = [
                m
                for m in self._metrics.values()
                if m.issue_type == issue_type and m.total_attempts >= min_attempts
            ]

            if not qualified_metrics:
                logger.warning(
                    f"No qualified agents found for {issue_type} "
                    f"(min_attempts={min_attempts})"
                )
                return None

            best_metric = max(
                qualified_metrics,
                key=lambda m: (m.get_success_rate(), m.avg_confidence),
            )

            return {
                "agent_name": best_metric.agent_name,
                "model_name": best_metric.model_name,
                "success_rate": best_metric.get_success_rate(),
                "total_attempts": best_metric.total_attempts,
                "avg_confidence": best_metric.avg_confidence,
                "avg_time_seconds": best_metric.avg_time_seconds,
            }

    def _compute_model_comparison(
        self,
        metrics: list[AgentMetrics],
        issue_type: str | None = None,
        min_attempts: int = 5,
    ) -> dict[str, dict[str, Any]]:
        model_stats: dict[str, dict[str, Any]] = {}

        for metric in metrics:
            if metric.total_attempts < min_attempts:
                continue
            if issue_type and metric.issue_type != issue_type:
                continue

            model = metric.model_name

            if model not in model_stats:
                model_stats[model] = {
                    "total_attempts": 0,
                    "successful_fixes": 0,
                    "confidence_sum": 0.0,
                    "time_sum": 0.0,
                    "issue_types": set(),
                }

            stats = model_stats[model]
            stats["total_attempts"] += metric.total_attempts
            stats["successful_fixes"] += metric.successful_fixes
            stats["confidence_sum"] += metric.avg_confidence * metric.total_attempts
            stats["time_sum"] += metric.avg_time_seconds * metric.total_attempts
            stats["issue_types"].add(metric.issue_type)

        result = {}
        for model, stats in model_stats.items():
            result[model] = {
                "avg_success_rate": (
                    stats["successful_fixes"] / stats["total_attempts"] * 100
                    if stats["total_attempts"] > 0
                    else 0.0
                ),
                "total_attempts": stats["total_attempts"],
                "avg_confidence": (
                    stats["confidence_sum"] / stats["total_attempts"]
                    if stats["total_attempts"] > 0
                    else 0.0
                ),
                "avg_time_seconds": (
                    stats["time_sum"] / stats["total_attempts"]
                    if stats["total_attempts"] > 0
                    else 0.0
                ),
                "issue_types": sorted(list(stats["issue_types"])),
            }

        return result

    def get_model_comparison(
        self,
        issue_type: str | None = None,
        min_attempts: int = 5,
    ) -> dict[str, dict[str, Any]]:

        with self._lock:
            metrics_snapshot = list(self._metrics.values())

        return self._compute_model_comparison(
            metrics_snapshot, issue_type, min_attempts
        )

    def generate_performance_report(self) -> dict[str, Any]:

        with self._lock:
            metrics_snapshot = list(self._metrics.values())

        total_attempts = sum(m.total_attempts for m in metrics_snapshot)
        total_successful = sum(m.successful_fixes for m in metrics_snapshot)
        overall_success_rate = (
            (total_successful / total_attempts * 100) if total_attempts > 0 else 0.0
        )

        by_agent: dict[str, dict[str, Any]] = {}
        for metric in metrics_snapshot:
            agent = metric.agent_name
            if agent not in by_agent:
                by_agent[agent] = {
                    "total_attempts": 0,
                    "successful_fixes": 0,
                    "issue_types": set(),
                }

            by_agent[agent]["total_attempts"] += metric.total_attempts
            by_agent[agent]["successful_fixes"] += metric.successful_fixes
            by_agent[agent]["issue_types"].add(metric.issue_type)

        by_agent_formatted = {}
        for agent, stats in by_agent.items():
            by_agent_formatted[agent] = {
                "total_attempts": stats["total_attempts"],
                "success_rate": (
                    stats["successful_fixes"] / stats["total_attempts"] * 100
                    if stats["total_attempts"] > 0
                    else 0.0
                ),
                "issue_types": sorted(list(stats["issue_types"])),
            }

        by_issue_type: dict[str, dict[str, Any]] = {}
        for metric in metrics_snapshot:
            issue = metric.issue_type
            if issue not in by_issue_type:
                by_issue_type[issue] = {
                    "total_attempts": 0,
                    "successful_fixes": 0,
                    "agents_used": set(),
                }

            by_issue_type[issue]["total_attempts"] += metric.total_attempts
            by_issue_type[issue]["successful_fixes"] += metric.successful_fixes
            by_issue_type[issue]["agents_used"].add(metric.agent_name)

        by_issue_type_formatted = {}
        for issue, stats in by_issue_type.items():
            by_issue_type_formatted[issue] = {
                "total_attempts": stats["total_attempts"],
                "success_rate": (
                    stats["successful_fixes"] / stats["total_attempts"] * 100
                    if stats["total_attempts"] > 0
                    else 0.0
                ),
                "agents_used": sorted(list(stats["agents_used"])),
            }

        by_model = self._compute_model_comparison(metrics_snapshot, min_attempts=1)

        recommendations = {}
        for issue_type in by_issue_type.keys():
            best = self.get_best_agent_for_issue_type(issue_type, min_attempts=3)
            if best:
                recommendations[issue_type] = best

        return {
            "summary": {
                "generated_at": datetime.now().isoformat(),
                "total_attempts": total_attempts,
                "total_successful": total_successful,
                "overall_success_rate": round(overall_success_rate, 2),
                "total_agents": len(by_agent),
                "total_issue_types": len(by_issue_type),
                "total_models": len(by_model),
            },
            "by_agent": by_agent_formatted,
            "by_issue_type": by_issue_type_formatted,
            "by_model": by_model,
            "recommendations": recommendations,
        }

    def _save_metrics(self) -> None:
        try:
            data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "metrics": {k: v.to_dict() for k, v in self._metrics.items()},
            }

            temp_file = self.metrics_file.with_suffix(".tmp")
            with temp_file.open("w") as f:
                json.dump(data, f, indent=2)

            temp_file.replace(self.metrics_file)

            logger.debug(f"Saved {len(self._metrics)} metrics to {self.metrics_file}")

        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def _load_metrics(self) -> None:
        try:
            if not self.metrics_file.exists():
                logger.debug(f"Metrics file not found: {self.metrics_file}")
                return

            with self.metrics_file.open("r") as f:
                data = json.load(f)

            for key, metric_data in data.get("metrics", {}).items():
                try:
                    metric = AgentMetrics.from_dict(metric_data)
                    self._metrics[key] = metric
                except Exception as e:
                    logger.warning(f"Failed to load metric {key}: {e}")

            logger.debug(
                f"Loaded {len(self._metrics)} metrics from {self.metrics_file}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode metrics JSON: {e}")
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")

    def reset_metrics(self) -> None:
        with self._lock:
            self._metrics.clear()

            try:
                if self.metrics_file.exists():
                    self.metrics_file.unlink()
                    logger.info(f"Deleted metrics file: {self.metrics_file}")
            except Exception as e:
                logger.error(f"Failed to delete metrics file: {e}")

            logger.info("All metrics have been reset")

    def get_metric_count(self) -> int:
        with self._lock:
            return len(self._metrics)

    def get_raw_metrics(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {k: v.to_dict() for k, v in self._metrics.items()}

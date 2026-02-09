"""
Agent Performance Tracking System

This module provides comprehensive performance tracking for AI agents, monitoring
success rates, timing, confidence levels, and model effectiveness. The system persists
metrics to disk and provides detailed analytics for agent optimization.

Key Features:
- AgentMetrics dataclass for structured performance data
- Thread-safe operations with file-based persistence
- Comprehensive reporting and analysis capabilities
- Model comparison and agent recommendation

Usage:
    tracker = AgentPerformanceTracker()
    tracker.record_attempt(
        agent_name="RefactoringAgent",
        model_name="claude-sonnet-4-5-20250929",
        issue_type="complexity",
        success=True,
        confidence=0.85,
        time_seconds=2.3,
    )

    # Get best agent for specific issue type
    best_agent = tracker.get_best_agent_for_issue_type("complexity")

    # Generate comprehensive report
    report = tracker.generate_performance_report()
"""

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
    """Represents a single agent fix attempt with detailed metrics."""

    timestamp: str
    agent_name: str
    model_name: str
    issue_type: str
    success: bool
    confidence: float
    time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert attempt to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class AgentMetrics:
    """
    Performance metrics for a specific agent and model combination.

    Tracks comprehensive statistics including success rates, timing data,
    confidence levels, and recent execution history.
    """

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
        """
        Record a new attempt and update aggregated metrics.

        Uses incremental averaging to maintain running averages without
        storing all historical data.

        Args:
            success: Whether the fix attempt was successful
            confidence: Agent's confidence score (0.0-1.0)
            time_seconds: Time taken for the fix attempt
        """
        self.total_attempts += 1

        if success:
            self.successful_fixes += 1
        else:
            self.failed_fixes += 1

        # Incremental average calculation
        self.avg_confidence = (
            (self.avg_confidence * (self.total_attempts - 1) + confidence)
            / self.total_attempts
        )
        self.avg_time_seconds = (
            (self.avg_time_seconds * (self.total_attempts - 1) + time_seconds)
            / self.total_attempts
        )

    def add_recent_result(self, attempt: AgentAttempt) -> None:
        """
        Add attempt to recent results list, maintaining max size limit.

        Args:
            attempt: The attempt to add to recent results
        """
        self.recent_results.append(attempt)
        if len(self.recent_results) > MAX_RECENT_RESULTS:
            self.recent_results.pop(0)

    def get_success_rate(self) -> float:
        """
        Calculate success rate as percentage.

        Returns:
            Success rate as float (0.0-100.0), or 0.0 if no attempts
        """
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_fixes / self.total_attempts) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for JSON serialization."""
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
        """
        Create AgentMetrics from dictionary.

        Args:
            data: Dictionary containing metrics data

        Returns:
            AgentMetrics instance
        """
        recent_results = [
            AgentAttempt(**r) for r in data.get("recent_results", [])
        ]
        data["recent_results"] = recent_results
        return cls(**data)


class AgentPerformanceTracker:
    """
    Thread-safe performance tracker for AI agent execution metrics.

    Provides comprehensive tracking, analysis, and reporting of agent
    performance across different models and issue types.

    Features:
    - Thread-safe operations using locks
    - JSON persistence to /tmp/agent_performance.json
    - Success rate tracking by agent and issue type
    - Model comparison and recommendation
    - Comprehensive performance reports
    """

    def __init__(self, metrics_file: Path = METRICS_FILE) -> None:
        """
        Initialize the performance tracker.

        Args:
            metrics_file: Path to JSON file for persisting metrics
        """
        self.metrics_file = metrics_file
        self._metrics: dict[str, AgentMetrics] = {}
        self._lock = threading.Lock()

        # Load existing metrics on initialization
        self._load_metrics()

    def _get_metric_key(
        self,
        agent_name: str,
        model_name: str,
        issue_type: str,
    ) -> str:
        """
        Generate unique key for metrics storage.

        Args:
            agent_name: Name of the agent
            model_name: Name of the model
            issue_type: Type of issue being handled

        Returns:
            Unique string key for metrics lookup
        """
        return f"{agent_name}:{model_name}:{issue_type}"

    def _get_or_create_metric(
        self,
        agent_name: str,
        model_name: str,
        issue_type: str,
    ) -> AgentMetrics:
        """
        Get existing metrics or create new entry.

        Args:
            agent_name: Name of the agent
            model_name: Name of the model
            issue_type: Type of issue being handled

        Returns:
            AgentMetrics instance
        """
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
        """
        Record a single agent fix attempt with metrics.

        Thread-safe operation that updates metrics in memory and persists
        to disk. Automatically saves after each recording.

        Args:
            agent_name: Name of the agent (e.g., "RefactoringAgent")
            model_name: Model used (e.g., "claude-sonnet-4-5-20250929")
            issue_type: Type of issue (e.g., "complexity", "formatting")
            success: Whether the fix was successful
            confidence: Agent's confidence score (0.0-1.0)
            time_seconds: Execution time in seconds
        """
        with self._lock:
            metric = self._get_or_create_metric(agent_name, model_name, issue_type)

            # Create attempt record
            attempt = AgentAttempt(
                timestamp=datetime.now().isoformat(),
                agent_name=agent_name,
                model_name=model_name,
                issue_type=issue_type,
                success=success,
                confidence=confidence,
                time_seconds=time_seconds,
            )

            # Update aggregated metrics
            metric.add_attempt(success, confidence, time_seconds)
            metric.add_recent_result(attempt)

            # Persist to disk
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
        """
        Get success rate(s) for agents, optionally filtered by issue type or model.

        Args:
            agent_name: Specific agent name, or None for all agents
            issue_type: Specific issue type, or None for all types
            model_name: Specific model name, or None for all models

        Returns:
            Success rate as float (0.0-100.0) for single query,
            or dict mapping keys to success rates for aggregate query
        """
        with self._lock:
            if agent_name and issue_type and model_name:
                # Single specific metric
                key = self._get_metric_key(agent_name, model_name, issue_type)
                if key in self._metrics:
                    return self._metrics[key].get_success_rate()
                return 0.0

            # Aggregate query
            results: dict[str, float] = {}

            for key, metric in self._metrics.items():
                # Apply filters
                if agent_name and metric.agent_name != agent_name:
                    continue
                if issue_type and metric.issue_type != issue_type:
                    continue
                if model_name and metric.model_name != model_name:
                    continue

                # Group by appropriate key
                if agent_name and issue_type:
                    # Group by model
                    group_key = metric.model_name
                elif agent_name:
                    # Group by issue type
                    group_key = metric.issue_type
                elif issue_type:
                    # Group by agent
                    group_key = metric.agent_name
                else:
                    # No grouping, use full key
                    group_key = key

                # Aggregate success rates
                if group_key not in results:
                    results[group_key] = {
                        "total_attempts": 0,
                        "successful_fixes": 0,
                    }

                results[group_key]["total_attempts"] += metric.total_attempts
                results[group_key]["successful_fixes"] += metric.successful_fixes

            # Calculate percentages
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
        """
        Find the best performing agent for a specific issue type.

        Rankings are based on success rate, with minimum attempt threshold
        to ensure statistical significance.

        Args:
            issue_type: Type of issue to find best agent for
            min_attempts: Minimum number of attempts required for consideration

        Returns:
            Dictionary with best agent info, or None if no qualified agents
            {
                "agent_name": str,
                "model_name": str,
                "success_rate": float,
                "total_attempts": int,
                "avg_confidence": float,
                "avg_time_seconds": float
            }
        """
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

            # Sort by success rate, then by confidence
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

    def get_model_comparison(
        self,
        issue_type: str | None = None,
        min_attempts: int = 5,
    ) -> dict[str, dict[str, Any]]:
        """
        Compare performance across different models.

        Args:
            issue_type: Filter by specific issue type, or None for all
            min_attempts: Minimum attempts required for inclusion

        Returns:
            Dictionary mapping model names to performance metrics
            {
                "model_name": {
                    "avg_success_rate": float,
                    "total_attempts": int,
                    "avg_confidence": float,
                    "avg_time_seconds": float,
                    "issue_types": [str]
                }
            }
        """
        with self._lock:
            model_stats: dict[str, dict[str, Any]] = {}

            for metric in self._metrics.values():
                # Apply filters
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
                stats["confidence_sum"] += (
                    metric.avg_confidence * metric.total_attempts
                )
                stats["time_sum"] += metric.avg_time_seconds * metric.total_attempts
                stats["issue_types"].add(metric.issue_type)

            # Calculate averages
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

    def generate_performance_report(self) -> dict[str, Any]:
        """
        Generate comprehensive performance report across all agents.

        Returns:
            Dictionary containing:
            - summary: Overall statistics
            - by_agent: Performance breakdown by agent
            - by_issue_type: Performance breakdown by issue type
            - by_model: Performance breakdown by model
            - recommendations: Agent recommendations per issue type
        """
        with self._lock:
            # Calculate overall summary
            total_attempts = sum(m.total_attempts for m in self._metrics.values())
            total_successful = sum(m.successful_fixes for m in self._metrics.values())
            overall_success_rate = (
                (total_successful / total_attempts * 100) if total_attempts > 0 else 0.0
            )

            # Group by agent
            by_agent: dict[str, dict[str, Any]] = {}
            for metric in self._metrics.values():
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

            # Format agent data
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

            # Group by issue type
            by_issue_type: dict[str, dict[str, Any]] = {}
            for metric in self._metrics.values():
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

            # Format issue type data
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

            # Model comparison
            by_model = self.get_model_comparison(min_attempts=1)

            # Generate recommendations
            recommendations = {}
            for issue_type in by_issue_type.keys():
                best = self.get_best_agent_for_issue_type(issue_type, min_attempts=3)
                if best:
                    recommendations[issue_type] = best

            return {
                "generated_at": datetime.now().isoformat(),
                "summary": {
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
        """
        Persist metrics to JSON file.

        Thread-safe operation that converts all metrics to dictionaries
        and writes to disk. Handles I/O errors gracefully.
        """
        try:
            # Convert to serializable format
            data = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "metrics": {k: v.to_dict() for k, v in self._metrics.items()},
            }

            # Write to file with atomic operation
            temp_file = self.metrics_file.with_suffix(".tmp")
            with temp_file.open("w") as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_file.replace(self.metrics_file)

            logger.debug(f"Saved {len(self._metrics)} metrics to {self.metrics_file}")

        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")

    def _load_metrics(self) -> None:
        """
        Load metrics from JSON file.

        Thread-safe operation that reads persisted metrics and reconstructs
        AgentMetrics objects. Handles missing or corrupt files gracefully.
        """
        try:
            if not self.metrics_file.exists():
                logger.debug(f"Metrics file not found: {self.metrics_file}")
                return

            with self.metrics_file.open("r") as f:
                data = json.load(f)

            # Reconstruct metrics
            for key, metric_data in data.get("metrics", {}).items():
                try:
                    metric = AgentMetrics.from_dict(metric_data)
                    self._metrics[key] = metric
                except Exception as e:
                    logger.warning(f"Failed to load metric {key}: {e}")

            logger.debug(f"Loaded {len(self._metrics)} metrics from {self.metrics_file}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode metrics JSON: {e}")
        except Exception as e:
            logger.error(f"Failed to load metrics: {e}")

    def reset_metrics(self) -> None:
        """
        Reset all metrics (use with caution).

        Thread-safe operation that clears all in-memory metrics and
        removes the persisted file.
        """
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
        """
        Get the total number of metric entries being tracked.

        Returns:
            Number of unique agent/model/issue_type combinations
        """
        with self._lock:
            return len(self._metrics)

    def get_raw_metrics(self) -> dict[str, dict[str, Any]]:
        """
        Get raw metrics data for custom analysis.

        Returns:
            Dictionary mapping metric keys to their serialized form
        """
        with self._lock:
            return {k: v.to_dict() for k, v in self._metrics.items()}

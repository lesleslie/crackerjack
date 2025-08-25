import time
import typing as t
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .base import FixResult, Issue


@dataclass
class AgentActivity:
    agent_type: str
    confidence: float
    status: str
    current_issue: Issue | None = None
    start_time: float = field(default_factory=time.time)
    processing_time: float = 0.0
    result: FixResult | None = None


class AgentTracker:
    def __init__(self) -> None:
        self.active_agents: dict[str, AgentActivity] = {}
        self.completed_activities: list[AgentActivity] = []
        self.performance_metrics: defaultdict[str, list[float]] = defaultdict(list)
        self.cache_stats = {"hits": 0, "misses": 0}
        self.total_issues_processed = 0
        self.coordinator_status = "idle"
        self.agent_registry: dict[str, t.Any] = {
            "total_agents": 0,
            "initialized_agents": 0,
            "agent_types": [],
        }

    def set_coordinator_status(self, status: str) -> None:
        self.coordinator_status = status

    def register_agents(self, agent_types: list[str]) -> None:
        self.agent_registry = {
            "total_agents": len(agent_types),
            "initialized_agents": len(agent_types),
            "agent_types": agent_types,
        }

    def track_agent_evaluation(
        self,
        agent_type: str,
        issue: Issue,
        confidence: float,
    ) -> None:
        self.active_agents[agent_type] = AgentActivity(
            agent_type=agent_type,
            confidence=confidence,
            status="evaluating",
            current_issue=issue,
        )

    def track_agent_processing(
        self,
        agent_type: str,
        issue: Issue,
        confidence: float,
    ) -> None:
        if agent_type in self.active_agents:
            activity = self.active_agents[agent_type]
            activity.status = "processing"
            activity.current_issue = issue
            activity.confidence = confidence
        else:
            self.active_agents[agent_type] = AgentActivity(
                agent_type=agent_type,
                confidence=confidence,
                status="processing",
                current_issue=issue,
            )

    def track_agent_complete(self, agent_type: str, result: FixResult) -> None:
        if agent_type not in self.active_agents:
            return

        activity = self.active_agents[agent_type]
        activity.status = "completed" if result.success else "failed"
        activity.result = result
        activity.processing_time = time.time() - activity.start_time

        self.performance_metrics[agent_type].append(activity.processing_time)
        self.total_issues_processed += 1

        self.completed_activities.append(activity)
        del self.active_agents[agent_type]

    def track_cache_hit(self) -> None:
        self.cache_stats["hits"] += 1

    def track_cache_miss(self) -> None:
        self.cache_stats["misses"] += 1

    def get_status(self) -> dict[str, Any]:
        active_agents: list[dict[str, Any]] = []

        for agent_type, activity in self.active_agents.items():
            agent_data: dict[str, Any] = {
                "agent_type": agent_type,
                "confidence": activity.confidence,
                "status": activity.status,
                "processing_time": time.time() - activity.start_time,
                "start_time": activity.start_time,
            }

            if activity.current_issue:
                agent_data["current_issue"] = {
                    "type": activity.current_issue.type.value,
                    "message": activity.current_issue.message,
                    "priority": activity.current_issue.severity.value,
                    "file_path": activity.current_issue.file_path,
                }

            active_agents.append(agent_data)

        return {
            "coordinator_status": self.coordinator_status,
            "active_agents": active_agents,
            "agent_registry": self.agent_registry.copy(),
        }

    def get_metrics(self) -> dict[str, Any]:
        total_completed = len(self.completed_activities)
        successful = sum(
            1
            for activity in self.completed_activities
            if activity.result and activity.result.success
        )
        success_rate = successful / total_completed if total_completed > 0 else 0.0

        all_times: list[float] = []
        for times in self.performance_metrics.values():
            all_times.extend(times)

        avg_processing_time = sum(all_times) / len(all_times) if all_times else 0.0

        total_requests = self.cache_stats["hits"] + self.cache_stats["misses"]
        cache_hit_rate = (
            self.cache_stats["hits"] / total_requests if total_requests > 0 else 0.0
        )

        return {
            "total_issues_processed": self.total_issues_processed,
            "cache_hits": self.cache_stats["hits"],
            "cache_misses": self.cache_stats["misses"],
            "cache_hit_rate": cache_hit_rate,
            "average_processing_time": avg_processing_time,
            "success_rate": success_rate,
            "completed_activities": total_completed,
        }

    def get_agent_summary(self) -> dict[str, Any]:
        active_count = len(self.active_agents)
        cache_hits = self.cache_stats["hits"]

        active_summary: list[dict[str, Any]] = []
        for agent_type, activity in self.active_agents.items():
            emoji = self._get_agent_emoji(agent_type)
            processing_time = time.time() - activity.start_time

            active_summary.append(
                {
                    "display": f"{emoji} {agent_type}: {activity.status.title()} ({processing_time:.1f}s)",
                    "agent_type": agent_type,
                    "status": activity.status,
                    "processing_time": processing_time,
                },
            )

        return {
            "active_count": active_count,
            "cached_fixes": cache_hits,
            "active_agents": active_summary,
        }

    def _get_agent_emoji(self, agent_type: str) -> str:
        return {
            "FormattingAgent": "🎨",
            "SecurityAgent": "🔒",
            "TestSpecialistAgent": "🧪",
            "TestCreationAgent": "➕",
        }.get(agent_type, "🤖")

    def reset(self) -> None:
        self.active_agents.clear()
        self.completed_activities.clear()
        self.performance_metrics.clear()
        self.cache_stats = {"hits": 0, "misses": 0}
        self.total_issues_processed = 0
        self.coordinator_status = "idle"


_global_tracker = None


def get_agent_tracker() -> AgentTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = AgentTracker()
    return _global_tracker


def reset_agent_tracker() -> None:
    global _global_tracker
    if _global_tracker:
        _global_tracker.reset()
    else:
        _global_tracker = AgentTracker()

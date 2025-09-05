import time
import typing as t
from collections import defaultdict
from dataclasses import dataclass, field

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

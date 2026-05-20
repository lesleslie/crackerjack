from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(frozen=True)
class AIFixEvent:
    run_id: str
    iteration: int
    ts: float = field(default_factory=time.time)


@dataclass(frozen=True)
class RunStarted(AIFixEvent):
    kind: ClassVar[str] = "run_started"
    stage: str = ""
    initial_issue_count: int = 0


@dataclass(frozen=True)
class IterationStarted(AIFixEvent):
    kind: ClassVar[str] = "iteration_started"
    strategy: str = ""
    issue_count: int = 0


@dataclass(frozen=True)
class AgentDispatched(AIFixEvent):
    kind: ClassVar[str] = "agent_dispatched"
    agent: str = ""
    action: str = ""
    file: str = ""


@dataclass(frozen=True)
class IssueResolved(AIFixEvent):
    kind: ClassVar[str] = "issue_resolved"
    agent: str = ""
    file: str = ""
    duration_s: float = 0.0


@dataclass(frozen=True)
class IssueFailed(AIFixEvent):
    kind: ClassVar[str] = "issue_failed"
    agent: str = ""
    file: str = ""
    reason: str = ""


@dataclass(frozen=True)
class IterationFinished(AIFixEvent):
    kind: ClassVar[str] = "iteration_finished"
    resolved: int = 0
    failed: int = 0
    success: bool = True


@dataclass(frozen=True)
class RunFinished(AIFixEvent):
    kind: ClassVar[str] = "run_finished"
    success: bool = True
    total_iterations: int = 0
    total_resolved: int = 0


@dataclass(frozen=True)
class PreflightStarted(AIFixEvent):
    kind: ClassVar[str] = "preflight_started"
    tools: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PreflightFinished(AIFixEvent):
    kind: ClassVar[str] = "preflight_finished"
    issues_saved: int = 0
    duration_s: float = 0.0

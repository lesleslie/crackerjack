from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path
from typing import IO

from .ai_fix_events import (
    AgentDispatched,
    AIFixEvent,
    IssueFailed,
    IssueResolved,
    IterationFinished,
    IterationStarted,
    PreflightFinished,
    PreflightStarted,
    RunFinished,
    RunStarted,
)

logger = logging.getLogger(__name__)


class LoggingSink:

    _FORMATTERS: dict[str, type[AIFixEvent]] = {
        "run_started": RunStarted,
        "iteration_started": IterationStarted,
        "agent_dispatched": AgentDispatched,
        "issue_resolved": IssueResolved,
        "issue_failed": IssueFailed,
        "iteration_finished": IterationFinished,
        "run_finished": RunFinished,
    }

    async def handle(self, event: AIFixEvent) -> None:
        msg = self._format(event)
        if msg:
            logger.info(msg)

    @staticmethod
    def _format(event: AIFixEvent) -> str:
        if isinstance(event, RunStarted):
            return (
                f"AI-fix run {event.run_id} started "
                f"(stage={event.stage}, issues={event.initial_issue_count})"
            )
        if isinstance(event, IterationStarted):
            return (
                f"Iteration {event.iteration} started "
                f"(strategy={event.strategy}, issues={event.issue_count})"
            )
        if isinstance(event, AgentDispatched):
            return f"{event.agent}: {event.action} → {event.file}"
        if isinstance(event, IssueResolved):
            return f"✅ {event.agent} resolved {event.file} ({event.duration_s:.1f}s)"
        if isinstance(event, IssueFailed):
            return f"⚠️ {event.agent} failed on {event.file}: {event.reason}"
        if isinstance(event, IterationFinished):
            return (
                f"Iteration {event.iteration} finished "
                f"(resolved={event.resolved}, failed={event.failed}, ok={event.success})"
            )
        if isinstance(event, RunFinished):
            return (
                f"AI-fix run {event.run_id} finished "
                f"(success={event.success}, iterations={event.total_iterations})"
            )
        if isinstance(event, PreflightStarted):
            return f"Pre-flight started (tools={list(event.tools)})"
        if isinstance(event, PreflightFinished):
            return (
                f"Pre-flight finished "
                f"(saved≈{event.issues_saved} issues, {event.duration_s:.1f}s)"
            )
        return ""


class JsonlSink:

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or Path.cwd()
        self._file: IO[str] | None = None

    async def handle(self, event: AIFixEvent) -> None:
        if isinstance(event, RunStarted):
            self._open(event.run_id)
        if self._file is not None:
            line = json.dumps(dataclasses.asdict(event), default=str)
            self._file.write(line + "\n")
            self._file.flush()

    def _open(self, run_id: str) -> None:
        run_dir = self._base_dir / ".crackerjack" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self._file = (run_dir / "events.jsonl").open("a", encoding="utf-8")

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


class MetricsSink:

    def __init__(self) -> None:
        self.preflight_issues_saved: int = 0
        self.preflight_duration_s: float = 0.0
        self.total_resolved: int = 0
        self.total_failed: int = 0

    async def handle(self, event: AIFixEvent) -> None:
        if isinstance(event, PreflightFinished):
            self.preflight_issues_saved += event.issues_saved
            self.preflight_duration_s += event.duration_s
        elif isinstance(event, IssueResolved):
            self.total_resolved += 1
        elif isinstance(event, IssueFailed):
            self.total_failed += 1

    def summary(self) -> dict[str, object]:
        return {
            "preflight_issues_saved": self.preflight_issues_saved,
            "preflight_duration_s": self.preflight_duration_s,
            "total_resolved": self.total_resolved,
            "total_failed": self.total_failed,
        }


def build_default_bus(base_dir: Path | None = None) -> object:
    from .ai_fix_event_bus import AIFixEventBus

    bus = AIFixEventBus()
    bus.subscribe(LoggingSink())
    bus.subscribe(JsonlSink(base_dir=base_dir))
    bus.subscribe(MetricsSink())
    return bus

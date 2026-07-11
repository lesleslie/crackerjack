from __future__ import annotations

import dataclasses
import json
import logging
import time
from collections.abc import Iterator
from pathlib import Path
from typing import IO

from .ai_fix_events import (
    AgentDispatched,
    AIFixEvent,
    FixSessionFinished,
    FixSessionStarted,
    IssueFailed,
    IssueResolved,
    IterationFinished,
    IterationStarted,
    PhaseChanged,
    PreflightFinished,
    PreflightStarted,
    RunFinished,
    RunStarted,
    TierTransitioned,
)

logger = logging.getLogger(__name__)

_EVENT_CLASSES: tuple[type[AIFixEvent], ...] = (
    RunStarted,
    IterationStarted,
    AgentDispatched,
    IssueResolved,
    IssueFailed,
    IterationFinished,
    RunFinished,
    PhaseChanged,
    PreflightStarted,
    PreflightFinished,
    FixSessionStarted,
    TierTransitioned,
    FixSessionFinished,
)


class LoggingSink:
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
                f"(resolved={event.resolved}, failed={event.failed}, ok={event.success})"  # noqa: E501
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
        if isinstance(event, FixSessionStarted):
            return (
                f"fix-session started: {event.issue_type} in {event.file}"
                f" (sig={event.issue_signature})"
            )
        if isinstance(event, TierTransitioned):
            return (
                f"tier transition: {event.from_tier} → {event.to_tier} "
                f"({event.reason}) for {event.file}"
            )
        if isinstance(event, FixSessionFinished):
            outcome = "resolved" if event.success else "failed"
            return (
                f"fix-session {outcome}: {event.file} "
                f"(tier={event.final_tier}, no-ops={event.no_op_count}, "
                f"{event.total_duration_s:.1f}s)"
            )
        return ""


class JsonlSink:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or Path.cwd()
        self._file: IO[str] | None = None
        self._run_dir: Path | None = None

    async def handle(self, event: AIFixEvent) -> None:
        if isinstance(event, RunStarted):
            self._open(event.run_id)
        if self._file is None:
            return
        try:
            payload = dataclasses.asdict(event)
            kind = getattr(type(event), "kind", None)
            if isinstance(kind, str):
                payload["kind"] = kind
            line = json.dumps(payload, default=str)
            self._file.write(line + "\n")
            self._file.flush()
        except OSError as exc:
            logger.warning("JsonlSink dropped event after write error: %s", exc)
            self._file = None

    def _open(self, run_id: str) -> None:
        run_dir = self._base_dir / ".crackerjack" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        self._file = (run_dir / "events.jsonl").open("a", encoding="utf-8")
        self._run_dir = run_dir

        (run_dir / ".open").write_text(str(time.time()))

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
        if self._run_dir is not None:
            sidecar = self._run_dir / ".open"
            if sidecar.exists():
                sidecar.unlink()
            self._run_dir = None

    @classmethod
    def restore_run(
        cls,
        run_id: str,
        base_dir: Path | None = None,
    ) -> Iterator[AIFixEvent]:
        root = (base_dir or Path.cwd()) / ".crackerjack" / "runs" / run_id
        jsonl_path = root / "events.jsonl"
        if not jsonl_path.exists():
            return
        kind_to_cls = {event_cls.kind: event_cls for event_cls in _EVENT_CLASSES}
        for line in jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            kind = data.pop("kind", None)
            event_cls = kind_to_cls.get(kind) if isinstance(kind, str) else None
            if event_cls is None:
                continue
            valid_fields = {f.name for f in dataclasses.fields(event_cls)}
            yield event_cls(**{k: v for k, v in data.items() if k in valid_fields})


class DebugFileSink:
    def __init__(self, base_dir: Path, run_id: str) -> None:
        self._base_dir = base_dir
        self._run_id = run_id
        self._file: IO[str] | None = None
        self._run_dir: Path | None = None

    async def handle(self, event: AIFixEvent) -> None:
        if self._file is None:
            self._open()
        if self._file is None:
            return
        try:
            payload = dataclasses.asdict(event)
            kind = getattr(type(event), "kind", None)
            if isinstance(kind, str):
                payload["kind"] = kind
            line = json.dumps(payload, default=str)
            self._file.write(line + "\n")
            self._file.flush()
        except OSError as exc:
            logger.warning("DebugFileSink dropped event after write error: %s", exc)
            self._file = None

    def _open(self) -> None:
        run_dir = self._base_dir / ".crackerjack" / "runs" / self._run_id
        try:
            run_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("DebugFileSink could not create %s: %s", run_dir, exc)
            return
        try:
            self._file = (run_dir / "debug.log").open("a", encoding="utf-8")
            self._run_dir = run_dir
        except OSError as exc:
            logger.warning("DebugFileSink could not open debug.log: %s", exc)
            self._file = None

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
        self._run_dir = None


class MetricsSink:
    def __init__(self) -> None:
        self.preflight_issues_saved: int = 0
        self.preflight_duration_s: float = 0.0
        self.total_resolved: int = 0
        self.total_failed: int = 0
        self.total_sessions_started: int = 0
        self.total_sessions_finished: int = 0
        self.total_no_op_count: int = 0

    async def handle(self, event: AIFixEvent) -> None:
        if isinstance(event, PreflightFinished):
            self.preflight_issues_saved += event.issues_saved
            self.preflight_duration_s += event.duration_s
        elif isinstance(event, IssueResolved):
            self.total_resolved += 1
        elif isinstance(event, IssueFailed):
            self.total_failed += 1
        elif isinstance(event, FixSessionStarted):
            self.total_sessions_started += 1
        elif isinstance(event, FixSessionFinished):
            self.total_sessions_finished += 1
            self.total_no_op_count += event.no_op_count

    def summary(self) -> dict[str, object]:
        return {
            "preflight_issues_saved": self.preflight_issues_saved,
            "preflight_duration_s": self.preflight_duration_s,
            "total_resolved": self.total_resolved,
            "total_failed": self.total_failed,
            "total_sessions_started": self.total_sessions_started,
            "total_sessions_finished": self.total_sessions_finished,
            "total_no_op_count": self.total_no_op_count,
        }


def build_default_bus(base_dir: Path | None = None) -> object:
    from .ai_fix_event_bus import AIFixEventBus

    bus = AIFixEventBus()
    bus.subscribe(LoggingSink())
    bus.subscribe(JsonlSink(base_dir=base_dir))
    bus.subscribe(MetricsSink())
    return bus


def detect_orphan_sidecars(base_dir: Path | None = None) -> list[str]:
    root = (base_dir or Path.cwd()) / ".crackerjack" / "runs"
    if not root.exists():
        return []
    orphans: list[str] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        sidecar = child / ".open"
        events = child / "events.jsonl"
        if sidecar.exists() and events.exists():
            orphans.append(child.name)
    return orphans

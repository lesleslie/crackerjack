"""Telemetry collection for workflow events."""

from __future__ import annotations

import asyncio
import json
import typing as t
from collections import Counter, deque
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from acb.events import Event, EventHandlerResult

from .workflow_bus import WorkflowEvent

if TYPE_CHECKING:  # pragma: no cover - typing helper
    from .workflow_bus import WorkflowEventBus

HistoryEntry = dict[str, t.Any]


@dataclass
class WorkflowEventTelemetry:
    """Collects lightweight metrics about workflow events."""

    max_history: int = 100
    state_file: Path | None = None
    rollup_interval_seconds: float = 3600.0
    rollup_file: Path | None = None
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)
    _counts: Counter[str] = field(default_factory=Counter, init=False)
    _history: deque[HistoryEntry] = field(init=False)
    _last_error: HistoryEntry | None = field(default=None, init=False)
    _persist_task: asyncio.Task[None] | None = field(
        default=None, init=False, repr=False
    )
    _rollup_task: asyncio.Task[None] | None = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._history = deque(maxlen=self.max_history)
        if self.rollup_file is None and self.state_file is not None:
            self.rollup_file = self.state_file.with_name(
                f"{self.state_file.stem}_rollups.jsonl"
            )

    async def handle_event(self, event: Event) -> EventHandlerResult:
        """Event bus subscriber that records event metadata."""
        entry: HistoryEntry = {
            "event_type": event.metadata.event_type,
            "timestamp": event.metadata.timestamp.isoformat(),
            "source": event.metadata.source,
            "payload": event.payload,
        }

        async with self._lock:
            self._counts[event.metadata.event_type] += 1
            self._history.append(entry)
            if event.metadata.event_type == WorkflowEvent.WORKFLOW_FAILED.value:
                self._last_error = entry

        if self.state_file is not None:
            await self._schedule_persist()
        await self._ensure_rollup_task()

        return EventHandlerResult(success=True)

    async def snapshot(self) -> dict[str, t.Any]:
        """Return a snapshot of the telemetry counters and history."""
        async with self._lock:
            return {
                "counts": dict(self._counts),
                "recent_events": list(self._history),
                "last_error": self._last_error,
            }

    async def reset(self) -> None:
        """Reset telemetry counters."""
        async with self._lock:
            self._counts.clear()
            self._history.clear()
            self._last_error = None
        if self.state_file and self.state_file.exists():
            with suppress(Exception):
                self.state_file.unlink()

    async def shutdown(self) -> None:
        """Shutdown background persistence tasks."""
        if self._persist_task and not self._persist_task.done():
            self._persist_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._persist_task
        if self._rollup_task and not self._rollup_task.done():
            self._rollup_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._rollup_task

    async def _schedule_persist(self) -> None:
        if self.state_file is None:
            return

        if self._persist_task and not self._persist_task.done():
            return

        async def _persist() -> None:
            snapshot = await self.snapshot()
            state_file = self.state_file
            if state_file is None:
                return
            with suppress(Exception):
                state_file.parent.mkdir(parents=True, exist_ok=True)
                await asyncio.to_thread(
                    state_file.write_text,
                    json.dumps(snapshot, indent=2),
                )

        self._persist_task = asyncio.create_task(_persist())

    async def _ensure_rollup_task(self) -> None:
        if self.rollup_file is None or self.rollup_interval_seconds <= 0:
            return
        loop = asyncio.get_running_loop()
        if self._rollup_task and not self._rollup_task.done():
            return

        async def _rollup_loop() -> None:
            try:
                while True:
                    await asyncio.sleep(self.rollup_interval_seconds)
                    await self._persist_rollup()
            except asyncio.CancelledError:  # pragma: no cover - loop cancellation
                raise

        self._rollup_task = loop.create_task(_rollup_loop())

    async def _persist_rollup(self) -> None:
        if self.rollup_file is None:
            return
        snapshot = await self.snapshot()
        rollup_entry = {
            "timestamp": datetime.now().isoformat(),
            "counts": snapshot["counts"],
            "total_events": sum(snapshot["counts"].values()),
            "last_error": snapshot["last_error"],
        }

        rollup_file = self.rollup_file

        def _write() -> None:
            if rollup_file is None:
                return
            rollup_file.parent.mkdir(parents=True, exist_ok=True)
            with rollup_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rollup_entry))
                fh.write("\n")

        await asyncio.to_thread(_write)


def register_default_subscribers(
    event_bus: WorkflowEventBus,
    telemetry: WorkflowEventTelemetry,
) -> None:
    """Attach default subscribers to the workflow event bus."""
    event_bus.register_logging_handler()
    event_bus.subscribe(
        event_type=None,
        handler=telemetry.handle_event,
        description="workflow.telemetry",
        max_concurrent=1,
    )

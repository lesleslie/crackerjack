
from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Protocol

import typer
from pydantic import BaseModel, Field, field_validator


class ProgressSnapshot(BaseModel):

    workflow_id: str
    step: str
    percent: int
    message: str
    ts: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    @field_validator("percent", mode="before")
    @classmethod
    def _clamp_percent(cls, value: Any) -> Any:
        try:
            ivalue = int(value)
        except (TypeError, ValueError):
            return value
        return max(0, min(100, ivalue))


class WorkflowProgressRecorder(Protocol):

    def record(self, snapshot: ProgressSnapshot) -> None:

    async def latest(self, workflow_id: str) -> ProgressSnapshot | None:

    def subscribe(self, workflow_id: str) -> AsyncIterator[ProgressSnapshot]:
        ... # pragma: no cover - Protocol marker


class InMemoryRecorder:

    def __init__(self) -> None:
        self._latest: dict[str, ProgressSnapshot] = {}
        self._subscribers: dict[str, list[asyncio.Queue[ProgressSnapshot]]] = (
            defaultdict(list)
        )
        self._lock = asyncio.Lock()

    def record(self, snapshot: ProgressSnapshot) -> None:
        self._latest[snapshot.workflow_id] = snapshot
        for queue in list(self._subscribers.get(snapshot.workflow_id, ())):
            try:
                queue.put_nowait(snapshot)
            except asyncio.QueueFull: # pragma: no cover - unbounded
                pass

    async def latest(self, workflow_id: str) -> ProgressSnapshot | None:
        async with self._lock:
            return self._latest.get(workflow_id)

    async def subscribe(self, workflow_id: str) -> AsyncIterator[ProgressSnapshot]:
        queue: asyncio.Queue[ProgressSnapshot] = asyncio.Queue()
        async with self._lock:
            self._subscribers[workflow_id].append(queue)
        try:
            while True:
                snap = await queue.get()
                yield snap
        finally:
            async with self._lock:
                if queue in self._subscribers.get(workflow_id, []):
                    self._subscribers[workflow_id].remove(queue)


class RemotePersister:

    def __init__(self, dhara_url: str | None = None) -> None:
        self.dhara_url = dhara_url or os.environ.get(
            "MAHAVISHNU_DHARA_URL", "http://localhost: 8683"
        )

    async def send(self, snapshot: ProgressSnapshot) -> dict[str, Any]:
        raise NotImplementedError(
            "TODO(Workstream-C): RemotePersister.send is stubbed while the "
            "Dhara HTTP CRUD substrate (Phase 3 Workstream C) is blocked. "
            "Wire to POST {dhara_url}/workflows/{workflow_id}/progress-snapshots "
            "when Workstream C lands."
        )


def _default_recorder() -> InMemoryRecorder:
    return InMemoryRecorder()


def watch(
    workflow_id: str = typer.Argument(help="Workflow ID to watch"),
    poll: float = typer.Option(
        0.5, "--poll", help="Polling cadence in seconds (used as fallback sleep)"
    ),
    max_iterations: int = typer.Option(
        1,
        "--max-iterations",
        help="Stop after this many snapshots have been observed (test bound).",
    ),
) -> None:
    rec = _default_recorder()

    async def _run() -> int:


        latest = await rec.latest(workflow_id)
        count = 0
        if latest is None:
            typer.echo(f"No data for {workflow_id}.")
            return 1
        typer.echo(
            f"[latest] {latest.workflow_id} step={latest.step} "
            f"percent={latest.percent} message={latest.message!r}"
        )
        count = 1
        if count >= max_iterations:
            return 0
        async for snap in rec.subscribe(workflow_id):
            typer.echo(
                f"[{snap.ts}] {snap.workflow_id} step={snap.step} "
                f"percent={snap.percent} message={snap.message!r}"
            )
            count += 1
            if count >= max_iterations:
                break
            if poll > 0:
                await asyncio.sleep(poll)
        return 0

    exit_code = asyncio.run(_run())
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def build_cli() -> typer.Typer:
    app = typer.Typer(help="Workflow observation (Spec #10: live-observe)")
    app.command("watch")(watch)
    return app


cli = build_cli()

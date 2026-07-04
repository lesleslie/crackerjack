"""Spec #10: live-observe-presence-over-gate.

Workflows publish live progress snapshots instead of waiting at the gate.

Phase 3 substrate dependency:
    HTTP CRUD at ``/workflows/<id>/progress-snapshots`` is owned by
    Workstream C (Dhara thin client + HTTP CRUD). That workstream is
    **http_blocked** in the current dispatch. This module ships the
    *local* interface (model + Protocol + in-process recorder + CLI)
    and stubs the remote persister behind a clearly-labelled TODO so
    workers and operators have a stable surface to integrate against
    now and swap in real HTTP the moment Workstream C lands.

Boundaries:
    * Workers call ``WorkflowProgressRecorder.record(snapshot)``.
    * Operators run ``mahavishnu workflow watch <id>`` to subscribe.
    * The CLI resolves a recorder via ``_default_recorder()`` so
      tests can monkeypatch it.
"""

from __future__ import annotations

import asyncio
import os
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, Protocol

import typer
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class ProgressSnapshot(BaseModel):
    """A point-in-time snapshot of an in-flight workflow.

    Required schema: workflow_id, step, percent, message, ts.
    The ``ts`` field is populated by the model itself (ISO 8601, UTC).
    """

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


# ---------------------------------------------------------------------------
# Recorder interface (Protocol)
# ---------------------------------------------------------------------------


class WorkflowProgressRecorder(Protocol):
    """Surface that worker code calls to publish progress.

    Concrete adapters (in-memory now, HTTP persister when Workstream C
    ships) satisfy this Protocol. Workers should type-hint against
    ``WorkflowProgressRecorder`` rather than a concrete class.
    """

    def record(self, snapshot: ProgressSnapshot) -> None:
        """Synchronously enqueue a snapshot. Must be cheap and non-blocking."""

    async def latest(self, workflow_id: str) -> ProgressSnapshot | None:
        """Return the most recent snapshot for a workflow, or None."""

    def subscribe(self, workflow_id: str) -> AsyncIterator[ProgressSnapshot]:
        """Async-iterate over *new* snapshots for a workflow."""
        ...  # pragma: no cover - Protocol marker


# ---------------------------------------------------------------------------
# In-process default implementation
# ---------------------------------------------------------------------------


class InMemoryRecorder:
    """Default recorder used while the Workstream C substrate is blocked.

    Stores the latest snapshot per workflow and an asyncio.Queue per
    subscriber. ``subscribe()`` first yields the cached latest snapshot
    (if any), then yields every subsequent new snapshot as it arrives.
    """

    def __init__(self) -> None:
        self._latest: dict[str, ProgressSnapshot] = {}
        self._subscribers: dict[str, list[asyncio.Queue[ProgressSnapshot]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def record(self, snapshot: ProgressSnapshot) -> None:
        """Synchronously record. Updates latest + fans out to subscribers."""
        self._latest[snapshot.workflow_id] = snapshot
        for queue in list(self._subscribers.get(snapshot.workflow_id, ())):
            try:
                queue.put_nowait(snapshot)
            except asyncio.QueueFull:  # pragma: no cover - unbounded
                pass

    async def latest(self, workflow_id: str) -> ProgressSnapshot | None:
        async with self._lock:
            return self._latest.get(workflow_id)

    async def subscribe(self, workflow_id: str) -> AsyncIterator[ProgressSnapshot]:
        """Yield *only* snapshots that are recorded after subscribe() is called.

        Pre-existing snapshots are visible via ``latest()`` but not replayed
        on subscribe. This matches the "presence, not replay" semantic:
        subscribers see new state, not history.
        """
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


# ---------------------------------------------------------------------------
# Remote persister stub (http_blocked)
# ---------------------------------------------------------------------------


class RemotePersister:
    """Stub for the Dhara-backed HTTP CRUD persister.

    TODO(Workstream-C): replace ``send()`` with an httpx POST to
    ``{dhara_url}/workflows/{snapshot.workflow_id}/progress-snapshots``
    once Workstream C lands the Dhara thin-client + HTTP CRUD surface.
    Reference: phase-3 substrate plan, Workstream C; spec
    ``2026-06-22-live-observe-presence-over-gate-design.md``.
    """

    def __init__(self, dhara_url: str | None = None) -> None:
        self.dhara_url = dhara_url or os.environ.get(
            "MAHAVISHNU_DHARA_URL", "http://localhost:8683"
        )

    async def send(self, snapshot: ProgressSnapshot) -> dict[str, Any]:
        raise NotImplementedError(
            "TODO(Workstream-C): RemotePersister.send is stubbed while the "
            "Dhara HTTP CRUD substrate (Phase 3 Workstream C) is blocked. "
            "Wire to POST {dhara_url}/workflows/{workflow_id}/progress-snapshots "
            "when Workstream C lands."
        )


# ---------------------------------------------------------------------------
# Default recorder factory (overridable for tests)
# ---------------------------------------------------------------------------


def _default_recorder() -> InMemoryRecorder:
    """Process-local default recorder. Tests monkeypatch this."""
    return InMemoryRecorder()


# ---------------------------------------------------------------------------
# CLI: ``mahavishnu workflow watch <workflow_id>``
# ---------------------------------------------------------------------------


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
    """Poll workflow snapshots via the recorder and print each one.

    The watch loop subscribes via the recorder. When the HTTP substrate
    lands, ``_default_recorder()`` can be swapped for an adapter that
    proxies through ``RemotePersister.send``.
    """
    rec = _default_recorder()

    async def _run() -> int:
        # Show the cached latest first (presence, not replay). Then
        # subscribe for new snapshots. If nothing exists, fail fast.
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
    """Build the ``workflow watch`` typer CLI.

    Returns a fresh app so tests can construct it without touching the
    process-global typer registry. The watch command is exposed as the
    root command so CliRunner can invoke it directly with
    ``["<workflow_id>", "--max-iterations", "2", "--poll", "0"]``.

    Integrators that want a nested ``mahavishnu workflow ...`` surface
    should call ``main_app.add_typer(build_cli(), name="workflow")``;
    Typer sub-commands will then resolve ``workflow watch <id>``.
    """
    app = typer.Typer(help="Workflow observation (Spec #10: live-observe)")
    app.command("watch")(watch)
    return app


# Convenience: a module-level CLI instance for entry-points.
cli = build_cli()
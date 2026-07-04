"""TDD tests for Spec #10: live-observe-presence-over-gate.

Workflows publish live progress snapshots instead of waiting at the gate.
Phase 3 substrate (HTTP CRUD ``/workflows/<id>/progress-snapshots``) is
**http_blocked** in this dispatch (it is owned by Workstream C - Dhara thin
client + HTTP CRUD). Until Workstream C lands, this test module pins the
local interface that workers and the CLI must satisfy, and stubs the
remote CRUD call behind a clearly-labelled TODO.

Goals of the slice:

1.  ``ProgressSnapshot`` Pydantic model with the agreed schema
    (workflow_id, step, percent, message, ts).
2.  ``WorkflowProgressRecorder`` interface (Protocol) - sync entry point
    for worker code.
3.  A default in-process recorder implementation that buffers snapshots in
    memory. The remote HTTP persister is a stub with a TODO referencing
    Workstream C substrate.
4.  ``mahavishnu workflow watch <workflow_id>`` CLI subscribes via the
    persister and prints new snapshots. Stubs out cleanly when the
    substrate is http_blocked.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest
from typer.testing import CliRunner

from crackerjack.mahavishnu.workflows.progress import (
    InMemoryRecorder,
    ProgressSnapshot,
    WorkflowProgressRecorder,
    build_cli,
)


# ---------------------------------------------------------------------------
# ProgressSnapshot model
# ---------------------------------------------------------------------------


class TestProgressSnapshot:
    """The model is a plain Pydantic v2 dataclass-like record."""

    def test_carries_required_fields(self) -> None:
        snap = ProgressSnapshot(
            workflow_id="wf-1",
            step="executing",
            percent=42,
            message="running iteration 3",
        )
        assert snap.workflow_id == "wf-1"
        assert snap.step == "executing"
        assert snap.percent == 42
        assert snap.message == "running iteration 3"
        # ts is populated by the model itself.
        assert snap.ts  # non-empty string

    def test_ts_is_iso8601_utc(self) -> None:
        snap = ProgressSnapshot(
            workflow_id="wf-1",
            step="executing",
            percent=0,
            message="start",
        )
        # YYYY-MM-DDTHH:MM:SS(.ffffff)?+00:00 or trailing 'Z'
        assert snap.ts.endswith("+00:00") or snap.ts.endswith("Z")

    def test_percent_is_clamped_zero_to_hundred(self) -> None:
        low = ProgressSnapshot(workflow_id="wf", step="s", percent=-5, message="m")
        high = ProgressSnapshot(workflow_id="wf", step="s", percent=150, message="m")
        assert low.percent == 0
        assert high.percent == 100

    def test_serialize_roundtrip(self) -> None:
        snap = ProgressSnapshot(
            workflow_id="wf-1",
            step="executing",
            percent=10,
            message="hello",
        )
        dumped = snap.model_dump()
        assert dumped["workflow_id"] == "wf-1"
        assert dumped["step"] == "executing"
        assert dumped["percent"] == 10
        assert dumped["message"] == "hello"
        assert dumped["ts"] == snap.ts


# ---------------------------------------------------------------------------
# WorkflowProgressRecorder interface
# ---------------------------------------------------------------------------


class TestWorkflowProgressRecorderInterface:
    """The recorder is a Protocol so adapters can satisfy it."""

    def test_recorder_is_a_protocol(self) -> None:
        assert isinstance(WorkflowProgressRecorder, type)
        # Protocol classes in Python's typing module expose _is_protocol.
        assert getattr(WorkflowProgressRecorder, "_is_protocol", False)

    def test_required_methods(self) -> None:
        required = {"record", "latest", "subscribe"}
        assert required.issubset(set(dir(WorkflowProgressRecorder)))

    def test_dummy_implementation_satisfies_protocol(self) -> None:
        class DummyRecorder:
            def record(self, snapshot: ProgressSnapshot) -> None:
                return None

            async def latest(self, workflow_id: str) -> ProgressSnapshot | None:
                return None

            async def subscribe(self, workflow_id: str) -> Any:
                if False:
                    yield  # pragma: no cover - async generator marker

        dummy: WorkflowProgressRecorder = DummyRecorder()
        assert hasattr(dummy, "record")
        assert hasattr(dummy, "latest")
        assert hasattr(dummy, "subscribe")


# ---------------------------------------------------------------------------
# InMemoryRecorder (default in-process implementation)
# ---------------------------------------------------------------------------


class TestInMemoryRecorder:
    """Used until Workstream C substrate (HTTP CRUD) is unblocked."""

    @pytest.mark.asyncio
    async def test_record_then_latest_returns_snapshot(self) -> None:
        rec = InMemoryRecorder()
        snap = ProgressSnapshot(
            workflow_id="wf-1",
            step="executing",
            percent=50,
            message="halfway",
        )
        rec.record(snap)
        got = await rec.latest("wf-1")
        assert got is not None
        assert got.workflow_id == "wf-1"
        assert got.percent == 50

    @pytest.mark.asyncio
    async def test_latest_returns_most_recent_only(self) -> None:
        rec = InMemoryRecorder()
        rec.record(
            ProgressSnapshot(workflow_id="wf-1", step="a", percent=10, message="m1")
        )
        time.sleep(0.001)
        rec.record(
            ProgressSnapshot(workflow_id="wf-1", step="b", percent=80, message="m2")
        )
        got = await rec.latest("wf-1")
        assert got is not None
        assert got.step == "b"
        assert got.percent == 80

    @pytest.mark.asyncio
    async def test_latest_returns_none_for_unknown_workflow(self) -> None:
        rec = InMemoryRecorder()
        assert await rec.latest("missing") is None

    @pytest.mark.asyncio
    async def test_subscribe_yields_only_new_snapshots(self) -> None:
        rec = InMemoryRecorder()
        rec.record(
            ProgressSnapshot(workflow_id="wf-1", step="a", percent=10, message="m1")
        )

        # Drive subscribe as a background coroutine.
        seen: list[ProgressSnapshot] = []

        async def consumer() -> None:
            async for snap in rec.subscribe("wf-1"):
                seen.append(snap)
                if len(seen) >= 2:
                    return

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.01)  # let consumer subscribe
        rec.record(
            ProgressSnapshot(workflow_id="wf-1", step="b", percent=20, message="m2")
        )
        rec.record(
            ProgressSnapshot(workflow_id="wf-1", step="c", percent=30, message="m3")
        )
        await asyncio.wait_for(task, timeout=1.0)

        steps = [s.step for s in seen]
        assert steps == ["b", "c"]


# ---------------------------------------------------------------------------
# HTTP CRUD call stub (Workstream C substrate; http_blocked)
# ---------------------------------------------------------------------------


class TestHTTPCrudStub:
    """The remote persister is stubbed until Workstream C substrate lands."""

    def test_remote_persister_raises_substrate_blocked(self) -> None:
        from crackerjack.mahavishnu.workflows.progress import RemotePersister

        persister = RemotePersister(dhara_url="http://localhost:8683")
        snap = ProgressSnapshot(
            workflow_id="wf-1",
            step="executing",
            percent=50,
            message="halfway",
        )
        with pytest.raises(NotImplementedError) as exc_info:
            asyncio.run(persister.send(snap))
        # TODO(Workstream-C): replace with httpx POST to
        # /workflows/<id>/progress-snapshots once the Dhara HTTP CRUD
        # surface lands. Reference: phase-3 substrate plan, Workstream C.
        assert "Workstream-C" in str(exc_info.value) or "TODO" in str(exc_info.value)


# ---------------------------------------------------------------------------
# CLI: ``mahavishnu workflow watch <workflow_id>``
# ---------------------------------------------------------------------------


class TestWatchCLI:
    """The CLI subscribes via the persister and prints snapshots as they arrive.

    With the HTTP substrate http_blocked, the watch command must stub out
    cleanly: it should still construct the recorder, fail fast on missing
    substrate, and not silently swallow errors.
    """

    def test_watch_prints_seen_snapshots_via_recorder(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = InMemoryRecorder()
        # Seed two snapshots so the CLI can subscribe and exit on count.
        rec.record(
            ProgressSnapshot(workflow_id="wf-1", step="a", percent=10, message="m1")
        )
        rec.record(
            ProgressSnapshot(workflow_id="wf-1", step="b", percent=20, message="m2")
        )

        # Patch the recorder factory to return our seeded recorder.
        import crackerjack.mahavishnu.workflows.progress as progress_mod

        monkeypatch.setattr(
            progress_mod, "_default_recorder", lambda: rec, raising=False
        )

        cli = build_cli()
        runner = CliRunner()
        # max-iterations keeps the test bounded: stop after seeing 2 snapshots.
        result = runner.invoke(
            cli, ["wf-1", "--max-iterations", "2", "--poll", "0"]
        )
        assert result.exit_code == 0, result.output
        assert "wf-1" in result.output
        # At least one step label should appear.
        assert "a" in result.output or "b" in result.output

    def test_watch_errors_clearly_on_unknown_workflow(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = InMemoryRecorder()
        # No record() calls - latest() returns None.
        import crackerjack.mahavishnu.workflows.progress as progress_mod

        monkeypatch.setattr(
            progress_mod, "_default_recorder", lambda: rec, raising=False
        )

        cli = build_cli()
        runner = CliRunner()
        result = runner.invoke(
            cli, ["missing-wf", "--max-iterations", "1", "--poll", "0"]
        )
        # Non-zero exit code is acceptable; the message must mention "missing-wf".
        assert result.exit_code != 0
        assert "missing-wf" in result.output
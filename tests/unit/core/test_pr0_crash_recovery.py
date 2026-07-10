from __future__ import annotations

import json
from pathlib import Path

import pytest

from crackerjack.core.ai_fix_events import (
    AIFixEvent,
    FixSessionStarted,
    IterationStarted,
    RunStarted,
)
from crackerjack.core.ai_fix_sinks import JsonlSink, detect_orphan_sidecars


RUN_ID = "2026-07-07-1200-abcd"


# ─── Crash recovery: sidecar markers ────────────────────────────────────────


class TestSidecarOnOpen:
    @pytest.mark.asyncio
    async def test_open_creates_sidecar(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        run_dir = tmp_path / ".crackerjack" / "runs" / RUN_ID
        assert (run_dir / ".open").exists()
        sink.close()

    @pytest.mark.asyncio
    async def test_close_removes_sidecar(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        run_dir = tmp_path / ".crackerjack" / "runs" / RUN_ID
        assert (run_dir / ".open").exists()
        sink.close()
        assert not (run_dir / ".open").exists()


class TestCrashLeavesOrphan:
    @pytest.mark.asyncio
    async def test_simulated_crash_leaves_sidecar(self, tmp_path: Path) -> None:
        """Simulate a crash by writing events and never calling close()."""
        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        await sink.handle(IterationStarted(run_id=RUN_ID, iteration=0, issue_count=3))
        await sink.handle(
            FixSessionStarted(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-1",
                file="a.py",
            )
        )
        # Intentionally NOT calling sink.close() — simulates process crash.
        run_dir = tmp_path / ".crackerjack" / "runs" / RUN_ID
        assert (run_dir / ".open").exists()

        # Orphan detector sees it.
        orphans = detect_orphan_sidecars(tmp_path)
        assert RUN_ID in orphans

        # Restore can still read the events that were written before the crash.
        events = list(JsonlSink.restore_run(RUN_ID, base_dir=tmp_path))
        kinds = [type(e).__name__ for e in events]
        assert "RunStarted" in kinds
        assert "IterationStarted" in kinds
        assert "FixSessionStarted" in kinds


# ─── Replay workflow: restore_run + render ──────────────────────────────────


class TestReplayWorkflow:
    @pytest.mark.asyncio
    async def test_restore_run_yields_events(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        events: list[AIFixEvent] = [
            RunStarted(run_id=RUN_ID, iteration=0, stage="comprehensive"),
            IterationStarted(run_id=RUN_ID, iteration=0, issue_count=5),
            FixSessionStarted(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="s",
                file="a.py",
            ),
        ]
        for e in events:
            await sink.handle(e)
        sink.close()

        restored = list(JsonlSink.restore_run(RUN_ID, base_dir=tmp_path))
        assert len(restored) == 3
        assert [type(e).__name__ for e in restored] == [
            "RunStarted",
            "IterationStarted",
            "FixSessionStarted",
        ]

    @pytest.mark.asyncio
    async def test_restore_run_returns_empty_for_missing_run(self, tmp_path: Path) -> None:
        restored = list(JsonlSink.restore_run("nonexistent", base_dir=tmp_path))
        assert restored == []

    @pytest.mark.asyncio
    async def test_restore_run_round_trips_new_event_types(self, tmp_path: Path) -> None:
        from crackerjack.core.ai_fix_events import (
            FixSessionFinished,
            TierTransitioned,
        )

        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        await sink.handle(
            TierTransitioned(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="s",
                from_tier=1,
                to_tier=2,
                reason="x",
                file="a.py",
            )
        )
        await sink.handle(
            FixSessionFinished(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="s",
                file="a.py",
                success=True,
                final_tier=2,
            )
        )
        sink.close()

        restored = list(JsonlSink.restore_run(RUN_ID, base_dir=tmp_path))
        kinds = [type(e).__name__ for e in restored]
        assert kinds == ["RunStarted", "TierTransitioned", "FixSessionFinished"]
        finished = restored[-1]
        assert finished.success is True
        assert finished.final_tier == 2
        assert finished.file == "a.py"

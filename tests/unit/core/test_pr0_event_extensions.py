from __future__ import annotations

import dataclasses
import json
import logging
from pathlib import Path

import pytest

from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import (
    AIFixEvent,
    FixSessionFinished,
    FixSessionStarted,
    RunStarted,
    TierTransitioned,
)
from crackerjack.core.ai_fix_sinks import (
    DebugFileSink,
    JsonlSink,
    LoggingSink,
    MetricsSink,
    build_default_bus,
    detect_orphan_sidecars,
)


RUN_ID = "2026-07-07-1200-abcd"


# ─── New event types ────────────────────────────────────────────────────────


class TestFixSessionStarted:
    def test_kind(self) -> None:
        assert FixSessionStarted.kind == "fix_session_started"

    def test_fields(self) -> None:
        event = FixSessionStarted(
            run_id="r",
            iteration=0,
            issue_signature="sig-1",
            file="a.py",
            issue_type="TYPE_ERROR",
        )
        assert event.issue_signature == "sig-1"
        assert event.file == "a.py"
        assert event.issue_type == "TYPE_ERROR"


class TestTierTransitioned:
    def test_kind(self) -> None:
        assert TierTransitioned.kind == "tier_transitioned"

    def test_fields(self) -> None:
        event = TierTransitioned(
            run_id="r",
            iteration=0,
            issue_signature="sig-1",
            from_tier=1,
            to_tier=2,
            reason="no-op fix",
            file="a.py",
        )
        assert event.from_tier == 1
        assert event.to_tier == 2
        assert event.reason == "no-op fix"
        assert event.file == "a.py"


class TestFixSessionFinished:
    def test_kind(self) -> None:
        assert FixSessionFinished.kind == "fix_session_finished"

    def test_defaults(self) -> None:
        event = FixSessionFinished(
            run_id="r",
            iteration=0,
            issue_signature="sig-1",
            file="a.py",
        )
        assert event.success is False
        assert event.final_tier == 0
        assert event.total_duration_s == 0.0
        assert event.no_op_count == 0

    def test_fields(self) -> None:
        event = FixSessionFinished(
            run_id="r",
            iteration=0,
            issue_signature="sig-1",
            file="a.py",
            success=True,
            final_tier=2,
            total_duration_s=3.5,
            no_op_count=2,
        )
        assert event.success is True
        assert event.final_tier == 2
        assert event.total_duration_s == 3.5
        assert event.no_op_count == 2


class TestAllEventsAreAIFixEvent:
    def test_new_events_are_ai_fix_event(self) -> None:
        events: list[AIFixEvent] = [
            FixSessionStarted(
                run_id="r", iteration=0, issue_signature="s", file="a.py"
            ),
            TierTransitioned(
                run_id="r",
                iteration=0,
                issue_signature="s",
                from_tier=1,
                to_tier=2,
                reason="x",
                file="a.py",
            ),
            FixSessionFinished(
                run_id="r",
                iteration=0,
                issue_signature="s",
                file="a.py",
                success=True,
            ),
        ]
        for e in events:
            assert isinstance(e, AIFixEvent)

    def test_new_events_serialisable(self) -> None:
        e = FixSessionFinished(
            run_id="r",
            iteration=0,
            issue_signature="s",
            file="a.py",
            success=True,
            final_tier=3,
            total_duration_s=1.5,
            no_op_count=2,
        )
        d = dataclasses.asdict(e)
        json.dumps(d)  # must not raise


# ─── DebugFileSink ───────────────────────────────────────────────────────────


class TestDebugFileSink:
    @pytest.mark.asyncio
    async def test_writes_event_lines_to_file(self, tmp_path: Path) -> None:
        sink = DebugFileSink(base_dir=tmp_path, run_id=RUN_ID)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        await sink.handle(
            FixSessionStarted(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-1",
                file="a.py",
            )
        )
        sink.close()
        debug_path = tmp_path / ".crackerjack" / "runs" / RUN_ID / "debug.log"
        assert debug_path.exists()
        text = debug_path.read_text()
        assert "run_started" in text
        assert "fix_session_started" in text

    @pytest.mark.asyncio
    async def test_idempotent_close(self, tmp_path: Path) -> None:
        sink = DebugFileSink(base_dir=tmp_path, run_id=RUN_ID)
        sink.close()
        sink.close()  # must not raise

    @pytest.mark.asyncio
    async def test_lines_are_valid_json(self, tmp_path: Path) -> None:
        sink = DebugFileSink(base_dir=tmp_path, run_id=RUN_ID)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0, stage="fast"))
        sink.close()
        debug_path = tmp_path / ".crackerjack" / "runs" / RUN_ID / "debug.log"
        for line in debug_path.read_text().splitlines():
            if not line.strip():
                continue
            json.loads(line)  # must not raise

    def test_lazy_open(self, tmp_path: Path) -> None:
        """DebugFileSink should not open file until first event arrives."""
        sink = DebugFileSink(base_dir=tmp_path, run_id=RUN_ID)
        debug_path = tmp_path / ".crackerjack" / "runs" / RUN_ID / "debug.log"
        assert not debug_path.exists()
        sink.close()


# ─── Sidecar consumer / orphan detection ────────────────────────────────────


class TestDetectOrphanSidecars:
    def test_returns_empty_when_no_runs_dir(self, tmp_path: Path) -> None:
        orphans = detect_orphan_sidecars(tmp_path)
        assert orphans == []

    def test_returns_empty_when_only_completed_runs(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / ".crackerjack" / "runs"
        run_dir = runs_dir / "old-run"
        run_dir.mkdir(parents=True)
        (run_dir / "events.jsonl").write_text("")
        # no .open sidecar -> not orphan
        orphans = detect_orphan_sidecars(tmp_path)
        assert orphans == []

    def test_returns_orphan_run_ids(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / ".crackerjack" / "runs"
        for name in ("completed-1", "crashed-1", "crashed-2"):
            run_dir = runs_dir / name
            run_dir.mkdir(parents=True)
            (run_dir / "events.jsonl").write_text("")
        # mark crashed-* as orphan via .open sidecar
        for name in ("crashed-1", "crashed-2"):
            (runs_dir / name / ".open").write_text("100.0")

        orphans = detect_orphan_sidecars(tmp_path)
        assert set(orphans) == {"crashed-1", "crashed-2"}

    def test_skips_runs_without_events(self, tmp_path: Path) -> None:
        runs_dir = tmp_path / ".crackerjack" / "runs"
        empty_dir = runs_dir / "empty"
        empty_dir.mkdir(parents=True)
        (empty_dir / ".open").write_text("100.0")
        orphans = detect_orphan_sidecars(tmp_path)
        # A run dir with only .open (no events.jsonl) shouldn't be reported
        # as replayable; the helper filters by event presence.
        assert orphans == []


# ─── build_default_bus includes AIFixDashboard hook ──────────────────────────


class TestBuildDefaultBus:
    def test_returns_bus(self) -> None:
        bus = build_default_bus()
        assert isinstance(bus, AIFixEventBus)

    def test_default_sinks_present(self) -> None:
        bus = build_default_bus()
        sink_types = [type(s).__name__ for s in bus._sinks]  # type: ignore[attr-defined]
        assert "LoggingSink" in sink_types
        assert "JsonlSink" in sink_types
        assert "MetricsSink" in sink_types

    @pytest.mark.asyncio
    async def test_default_bus_emits_full_event_set(self, tmp_path: Path) -> None:
        bus = build_default_bus(base_dir=tmp_path)
        await bus.emit(RunStarted(run_id=RUN_ID, iteration=0, stage="fast"))
        await bus.emit(
            FixSessionStarted(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="s",
                file="a.py",
            )
        )
        # Close the jsonl sink via the bus if available
        for sink in bus._sinks:  # type: ignore[attr-defined]
            close = getattr(sink, "close", None)
            if callable(close):
                close()
        events_path = tmp_path / ".crackerjack" / "runs" / RUN_ID / "events.jsonl"
        assert events_path.exists()
        kinds = [
            json.loads(line).get("kind")
            for line in events_path.read_text().splitlines()
            if line.strip()
        ]
        assert "run_started" in kinds
        assert "fix_session_started" in kinds


# ─── Round-trip: new event types survive serialize/deserialize ──────────────


class TestEventRoundTrip:
    @pytest.mark.asyncio
    async def test_fix_session_started_roundtrip(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        await sink.handle(
            FixSessionStarted(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-1",
                file="a.py",
                issue_type="TYPE_ERROR",
            )
        )
        sink.close()
        events = list(JsonlSink.restore_run(RUN_ID, base_dir=tmp_path))
        kinds = [type(e).__name__ for e in events]
        assert "FixSessionStarted" in kinds

    @pytest.mark.asyncio
    async def test_fix_session_finished_roundtrip(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        await sink.handle(
            FixSessionFinished(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-1",
                file="a.py",
                success=True,
                final_tier=2,
                total_duration_s=2.5,
                no_op_count=3,
            )
        )
        sink.close()
        events = list(JsonlSink.restore_run(RUN_ID, base_dir=tmp_path))
        kinds = [type(e).__name__ for e in events]
        assert "FixSessionFinished" in kinds
        finished = next(e for e in events if isinstance(e, FixSessionFinished))
        assert finished.success is True
        assert finished.final_tier == 2
        assert finished.no_op_count == 3

    @pytest.mark.asyncio
    async def test_tier_transitioned_roundtrip(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        await sink.handle(
            TierTransitioned(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="sig-1",
                from_tier=1,
                to_tier=3,
                reason="escalation",
                file="a.py",
            )
        )
        sink.close()
        events = list(JsonlSink.restore_run(RUN_ID, base_dir=tmp_path))
        kinds = [type(e).__name__ for e in events]
        assert "TierTransitioned" in kinds
        t = next(e for e in events if isinstance(e, TierTransitioned))
        assert t.from_tier == 1
        assert t.to_tier == 3
        assert t.reason == "escalation"


# ─── Verbosity enum & configure_logging ────────────────────────────────────


class TestVerbosity:
    def test_levels_ordered(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity

        assert Verbosity.NORMAL < Verbosity.VERBOSE
        assert Verbosity.VERBOSE < Verbosity.VERY_VERBOSE
        assert Verbosity.VERY_VERBOSE < Verbosity.DEBUG

    def test_from_count(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity

        assert Verbosity.from_count(0) is Verbosity.NORMAL
        assert Verbosity.from_count(1) is Verbosity.VERBOSE
        assert Verbosity.from_count(2) is Verbosity.VERY_VERBOSE
        assert Verbosity.from_count(3) is Verbosity.DEBUG
        assert Verbosity.from_count(4) is Verbosity.DEBUG  # cap

    def test_should_log_event_active_at_very_verbose(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity

        assert Verbosity.NORMAL.should_log_event() is False
        assert Verbosity.VERBOSE.should_log_event() is False
        assert Verbosity.VERY_VERBOSE.should_log_event() is True
        assert Verbosity.DEBUG.should_log_event() is True

    def test_should_dump_json_to_stderr_at_debug(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity

        assert Verbosity.NORMAL.should_dump_json_to_stderr() is False
        assert Verbosity.VERY_VERBOSE.should_dump_json_to_stderr() is False
        assert Verbosity.DEBUG.should_dump_json_to_stderr() is True

    def test_should_write_debug_file_at_debug(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity

        assert Verbosity.NORMAL.should_write_debug_file() is False
        assert Verbosity.DEBUG.should_write_debug_file() is True


class TestConfigureLogging:
    def test_configure_does_not_raise(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity, configure_logging

        # Just must not raise for any level
        for v in Verbosity:
            configure_logging(v)

    def test_configure_sets_handler(self) -> None:
        import logging

        from crackerjack.core.ai_fix_verbosity import Verbosity, configure_logging

        configure_logging(Verbosity.DEBUG)
        # The ai_fix_sinks logger should have at least one handler attached
        log = logging.getLogger("crackerjack.core.ai_fix_sinks")
        assert len(log.handlers) > 0

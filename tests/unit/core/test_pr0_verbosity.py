from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import (
    FixSessionStarted,
    IterationStarted,
    RunStarted,
)
from crackerjack.core.ai_fix_sinks import (
    DebugFileSink,
    JsonlSink,
    build_default_bus,
)
from crackerjack.core.ai_fix_verbosity import (
    Verbosity,
    build_bus_for_verbosity,
    configure_logging,
)


RUN_ID = "2026-07-07-1200-abcd"


# ─── build_bus_for_verbosity: which sinks are active at each level ─────────


class TestBuildBusForVerbosity:
    def test_normal_level_registers_metrics_only(self, tmp_path: Path) -> None:
        bus, _dashboard = build_bus_for_verbosity(
            level=Verbosity.NORMAL,
            base_dir=tmp_path,
            run_id=RUN_ID,
            dashboard_mode="off",
        )
        sink_names = [type(s).__name__ for s in bus._sinks]  # type: ignore[attr-defined]
        # JSONL is always on per spec: "(default) Live dashboard when TTY;
        # JSONL always; no event log to stdout"
        assert "JsonlSink" in sink_names
        assert "MetricsSink" in sink_names
        # Logging sink (per-event log to stderr) is NOT active at NORMAL.
        assert "LoggingSink" not in sink_names
        # DebugFileSink only at DEBUG
        assert "DebugFileSink" not in sink_names

    def test_verbose_no_extra_sinks(self, tmp_path: Path) -> None:
        bus, _ = build_bus_for_verbosity(
            level=Verbosity.VERBOSE,
            base_dir=tmp_path,
            run_id=RUN_ID,
            dashboard_mode="off",
        )
        sink_names = [type(s).__name__ for s in bus._sinks]  # type: ignore[attr-defined]
        # -v adds per-event log in the dashboard panel (no separate sink)
        assert "LoggingSink" not in sink_names
        assert "JsonlSink" in sink_names
        assert "MetricsSink" in sink_names
        assert "DebugFileSink" not in sink_names

    def test_very_verbose_adds_logging_sink(self, tmp_path: Path) -> None:
        bus, _ = build_bus_for_verbosity(
            level=Verbosity.VERY_VERBOSE,
            base_dir=tmp_path,
            run_id=RUN_ID,
            dashboard_mode="off",
        )
        sink_names = [type(s).__name__ for s in bus._sinks]  # type: ignore[attr-defined]
        assert "LoggingSink" in sink_names
        assert "JsonlSink" in sink_names
        assert "MetricsSink" in sink_names
        assert "DebugFileSink" not in sink_names

    def test_debug_adds_debug_file_sink(self, tmp_path: Path) -> None:
        bus, _ = build_bus_for_verbosity(
            level=Verbosity.DEBUG,
            base_dir=tmp_path,
            run_id=RUN_ID,
            dashboard_mode="off",
        )
        sink_names = [type(s).__name__ for s in bus._sinks]  # type: ignore[attr-defined]
        assert "JsonlSink" in sink_names
        assert "LoggingSink" in sink_names
        assert "DebugFileSink" in sink_names

    def test_dashboard_attached_when_requested(self, tmp_path: Path) -> None:
        bus, dashboard = build_bus_for_verbosity(
            level=Verbosity.NORMAL,
            base_dir=tmp_path,
            run_id=RUN_ID,
            dashboard_mode="on",
        )
        assert dashboard is not None

    def test_no_dashboard_in_off_mode(self, tmp_path: Path) -> None:
        _bus, dashboard = build_bus_for_verbosity(
            level=Verbosity.NORMAL,
            base_dir=tmp_path,
            run_id=RUN_ID,
            dashboard_mode="off",
        )
        assert dashboard is None


# ─── Each verbosity level emits the right events ───────────────────────────


class TestVerbosityEmission:
    @pytest.mark.asyncio
    async def test_normal_emits_via_metrics_and_jsonl(self, tmp_path: Path) -> None:
        bus, _ = build_bus_for_verbosity(
            level=Verbosity.NORMAL,
            base_dir=tmp_path,
            run_id=RUN_ID,
            dashboard_mode="off",
        )
        await bus.emit(RunStarted(run_id=RUN_ID, iteration=0))
        await bus.emit(
            FixSessionStarted(
                run_id=RUN_ID,
                iteration=0,
                issue_signature="s",
                file="a.py",
            )
        )
        # Close jsonl sink explicitly to flush.
        for sink in bus._sinks:  # type: ignore[attr-defined]
            close = getattr(sink, "close", None)
            if callable(close):
                close()
        events_path = tmp_path / ".crackerjack" / "runs" / RUN_ID / "events.jsonl"
        assert events_path.exists()

    @pytest.mark.asyncio
    async def test_debug_writes_debug_log(self, tmp_path: Path) -> None:
        bus, _ = build_bus_for_verbosity(
            level=Verbosity.DEBUG,
            base_dir=tmp_path,
            run_id=RUN_ID,
            dashboard_mode="off",
        )
        await bus.emit(RunStarted(run_id=RUN_ID, iteration=0))
        await bus.emit(IterationStarted(run_id=RUN_ID, iteration=0, issue_count=1))
        # Find and close the DebugFileSink
        for sink in bus._sinks:  # type: ignore[attr-defined]
            close = getattr(sink, "close", None)
            if callable(close):
                close()
        debug_path = tmp_path / ".crackerjack" / "runs" / RUN_ID / "debug.log"
        assert debug_path.exists()
        content = debug_path.read_text()
        assert "run_started" in content
        assert "iteration_started" in content


# ─── configure_logging ─────────────────────────────────────────────────────


class TestConfigureLoggingSideEffects:
    def test_configure_logging_normal(self) -> None:
        # Should not raise; resets handlers on the ai_fix_sinks logger.
        configure_logging(Verbosity.NORMAL)

    def test_configure_logging_verbose_adds_handler(self) -> None:
        configure_logging(Verbosity.VERBOSE)
        log = logging.getLogger("crackerjack.core.ai_fix_sinks")
        assert any(
            isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
            for h in log.handlers
        )

    def test_configure_logging_debug_sets_debug_level(self) -> None:
        configure_logging(Verbosity.DEBUG)
        log = logging.getLogger("crackerjack.core.ai_fix_sinks")
        assert log.level == logging.DEBUG


# ─── CLI flag → verbosity mapping ──────────────────────────────────────────


class TestParseVerbosity:
    def test_zero_count_is_normal(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity, parse_verbosity

        assert parse_verbosity(0, ai_fix_debug=False) is Verbosity.NORMAL

    def test_one_v_is_verbose(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity, parse_verbosity

        assert parse_verbosity(1, ai_fix_debug=False) is Verbosity.VERBOSE

    def test_two_vv_is_very_verbose(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity, parse_verbosity

        assert parse_verbosity(2, ai_fix_debug=False) is Verbosity.VERY_VERBOSE

    def test_three_vvv_is_debug(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity, parse_verbosity

        assert parse_verbosity(3, ai_fix_debug=False) is Verbosity.DEBUG

    def test_ai_fix_debug_forces_debug(self) -> None:
        from crackerjack.core.ai_fix_verbosity import Verbosity, parse_verbosity

        assert parse_verbosity(0, ai_fix_debug=True) is Verbosity.DEBUG
        assert parse_verbosity(1, ai_fix_debug=True) is Verbosity.DEBUG
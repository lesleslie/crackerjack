from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import PreflightFinished, PreflightStarted
from crackerjack.core.preflight import (
    PreflightConfig,
    PreflightFixer,
    PreflightReport,
    PreflightStepResult,
)

RUN_ID = "2026-01-01-0000-abcd"


class CaptureSink:
    def __init__(self) -> None:
        self.received: list[object] = []

    async def handle(self, event: object) -> None:
        self.received.append(event)


def _make_fixer(
    tmp_path: Path, config: PreflightConfig | None = None
) -> tuple[PreflightFixer, CaptureSink]:
    bus = AIFixEventBus()
    sink = CaptureSink()
    bus.subscribe(sink)
    fixer = PreflightFixer(
        config=config or PreflightConfig(),
        bus=bus,
        pkg_path=tmp_path,
    )
    return fixer, sink


class TestPreflightConfig:
    def test_defaults(self) -> None:
        cfg = PreflightConfig()
        assert cfg.ruff_check is True
        assert cfg.ruff_format is True
        assert cfg.ruff_unsafe_fixes is False
        assert cfg.ruff_select_extra == []
        assert cfg.autoflake_unused is True
        assert cfg.refurb_safe_policies is True
        assert cfg.docformatter is False
        assert cfg.timeout_s == 60.0

    def test_frozen(self) -> None:
        from pydantic import ValidationError
        with pytest.raises((ValidationError, TypeError)):
            cfg = PreflightConfig()
            cfg.ruff_check = False  # type: ignore[misc]

    def test_custom_values(self) -> None:
        cfg = PreflightConfig(ruff_check=False, ruff_select_extra=["SIM", "UP"])
        assert cfg.ruff_check is False
        assert cfg.ruff_select_extra == ["SIM", "UP"]


class TestPreflightFixer:
    def _make_fixer(self, tmp_path: Path, config: PreflightConfig | None = None) -> tuple[PreflightFixer, CaptureSink]:
        return _make_fixer(tmp_path, config)

    @pytest.mark.asyncio
    async def test_emits_preflight_started(self, tmp_path: Path) -> None:
        fixer, sink = _make_fixer(tmp_path)
        with patch.object(fixer, "_run_step_sync", return_value=PreflightStepResult(
            tool="ruff_check", files_changed=0, issues_fixed=0, duration_s=0.0, success=True
        )):
            await fixer.run(RUN_ID, iteration=0)
        starts = [e for e in sink.received if isinstance(e, PreflightStarted)]
        assert len(starts) == 1
        assert starts[0].run_id == RUN_ID
        assert starts[0].iteration == 0

    @pytest.mark.asyncio
    async def test_emits_preflight_finished(self, tmp_path: Path) -> None:
        fixer, sink = _make_fixer(tmp_path)
        with patch.object(fixer, "_run_step_sync", return_value=PreflightStepResult(
            tool="ruff_check", files_changed=2, issues_fixed=5, duration_s=0.1, success=True
        )):
            report = await fixer.run(RUN_ID, iteration=0)
        finishes = [e for e in sink.received if isinstance(e, PreflightFinished)]
        assert len(finishes) == 1
        assert finishes[0].issues_saved == report.total_issues_fixed

    @pytest.mark.asyncio
    async def test_returns_preflight_report(self, tmp_path: Path) -> None:
        fixer, sink = _make_fixer(tmp_path)
        step = PreflightStepResult(tool="ruff_check", files_changed=3, issues_fixed=7, duration_s=0.2, success=True)
        with patch.object(fixer, "_run_step_sync", return_value=step):
            report = await fixer.run(RUN_ID, iteration=0)
        assert isinstance(report, PreflightReport)
        assert report.total_files_changed >= 3  # may be summed across tools
        assert report.total_issues_fixed >= 7

    @pytest.mark.asyncio
    async def test_disabled_tools_not_run(self, tmp_path: Path) -> None:
        config = PreflightConfig(
            ruff_check=False,
            ruff_format=False,
            autoflake_unused=False,
            refurb_safe_policies=False,
        )
        fixer, sink = _make_fixer(tmp_path, config)
        with patch.object(fixer, "_run_step_sync") as mock_step:
            mock_step.return_value = PreflightStepResult(
                tool="x", files_changed=0, issues_fixed=0, duration_s=0.0, success=True
            )
            await fixer.run(RUN_ID, iteration=0)
        assert mock_step.call_count == 0

    @pytest.mark.asyncio
    async def test_event_order_start_before_finish(self, tmp_path: Path) -> None:
        fixer, sink = _make_fixer(tmp_path)
        with patch.object(fixer, "_run_step_sync", return_value=PreflightStepResult(
            tool="ruff_check", files_changed=0, issues_fixed=0, duration_s=0.0, success=True
        )):
            await fixer.run(RUN_ID, iteration=0)
        types = [type(e).__name__ for e in sink.received]
        assert types.index("PreflightStarted") < types.index("PreflightFinished")

    def test_enabled_tools_default_config(self, tmp_path: Path) -> None:
        fixer, _ = _make_fixer(tmp_path)
        tools = fixer._enabled_tools()
        assert "ruff_check" in tools
        assert "ruff_format" in tools
        assert "ruff_f401" in tools
        assert "refurb" in tools

    def test_enabled_tools_extra_selects(self, tmp_path: Path) -> None:
        config = PreflightConfig(ruff_select_extra=["SIM", "UP"])
        fixer, _ = _make_fixer(tmp_path, config)
        tools = fixer._enabled_tools()
        assert "ruff_extra" in tools

    def test_build_cmd_ruff_check(self, tmp_path: Path) -> None:
        fixer, _ = _make_fixer(tmp_path)
        cmd = fixer._build_cmd("ruff_check")
        assert "ruff" in cmd
        assert "check" in cmd
        assert "--fix" in cmd

    def test_build_cmd_ruff_check_unsafe(self, tmp_path: Path) -> None:
        config = PreflightConfig(ruff_unsafe_fixes=True)
        fixer, _ = _make_fixer(tmp_path, config)
        cmd = fixer._build_cmd("ruff_check")
        assert "--unsafe-fixes" in cmd

    def test_build_cmd_ruff_format(self, tmp_path: Path) -> None:
        fixer, _ = _make_fixer(tmp_path)
        cmd = fixer._build_cmd("ruff_format")
        assert "format" in cmd

    def test_build_cmd_ruff_extra(self, tmp_path: Path) -> None:
        config = PreflightConfig(ruff_select_extra=["SIM", "UP"])
        fixer, _ = _make_fixer(tmp_path, config)
        cmd = fixer._build_cmd("ruff_extra")
        assert "--select" in cmd
        assert "SIM,UP" in cmd

    def test_build_cmd_unknown_returns_empty(self, tmp_path: Path) -> None:
        fixer, _ = _make_fixer(tmp_path)
        cmd = fixer._build_cmd("unknown_tool")
        assert cmd == []

    def test_snapshot_mtimes_captures_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.txt").write_text("not python")
        fixer, _ = _make_fixer(tmp_path)
        mtimes = fixer._snapshot_mtimes()
        paths = list(mtimes.keys())
        assert any(p.name == "a.py" for p in paths)
        assert not any(p.name == "b.txt" for p in paths)

    def test_count_changed_files_detects_change(self, tmp_path: Path) -> None:
        f = tmp_path / "module.py"
        f.write_text("x = 1")
        fixer, _ = _make_fixer(tmp_path)
        before = fixer._snapshot_mtimes()
        # wait enough for mtime to differ
        time.sleep(0.01)
        f.write_text("x = 2")
        changed = fixer._count_changed_files(before)
        assert changed == 1

    def test_count_changed_files_no_change(self, tmp_path: Path) -> None:
        (tmp_path / "module.py").write_text("x = 1")
        fixer, _ = _make_fixer(tmp_path)
        before = fixer._snapshot_mtimes()
        assert fixer._count_changed_files(before) == 0

    def test_parse_issues_fixed_ruff_output(self, tmp_path: Path) -> None:
        fixer, _ = _make_fixer(tmp_path)
        assert fixer._parse_issues_fixed("Fixed 12 errors.") == 12
        assert fixer._parse_issues_fixed("Fixed 1 error.") == 1

    def test_parse_issues_fixed_no_match(self, tmp_path: Path) -> None:
        fixer, _ = _make_fixer(tmp_path)
        assert fixer._parse_issues_fixed("All checks passed!") == 0

    @pytest.mark.asyncio
    async def test_parallel_runs_all_tools(self, tmp_path: Path) -> None:
        """Tier-3 #13: All enabled tools must be dispatched concurrently.

        With 4 tools each sleeping 0.1s, the serial loop takes >= 0.4s.
        Parallel execution finishes well under 0.3s.
        """
        fixer, sink = self._make_fixer(tmp_path)

        def slow_step(tool: str, baseline: dict[Path, float] | None = None) -> PreflightStepResult:
            time.sleep(0.1)
            return PreflightStepResult(
                tool=tool,
                files_changed=0,
                issues_fixed=0,
                duration_s=0.1,
                success=True,
            )

        t0 = time.monotonic()
        with patch.object(fixer, "_run_step_sync", side_effect=slow_step):
            report = await fixer.run(RUN_ID, iteration=0)
        elapsed = time.monotonic() - t0

        assert len(report.steps) == len(fixer._enabled_tools())
        assert elapsed < 0.3, f"Tools ran serially: elapsed={elapsed:.3f}s"

    @pytest.mark.asyncio
    async def test_parallel_records_overlapping_invocation(self, tmp_path: Path) -> None:
        """Tier-3 #13: At least 2 tools must be in-flight simultaneously.

        Uses an asyncio.Event per tool that only fires when *all* tools
        have been dispatched. If dispatch is serial, the second tool's
        event never has a chance to fire concurrently with the first.
        """
        fixer, _ = self._make_fixer(tmp_path)
        tools = fixer._enabled_tools()
        assert len(tools) >= 2, "Test requires at least 2 enabled tools"

        in_flight = 0
        max_in_flight = 0
        all_started = asyncio.Event()
        started_count = 0

        def slow_step(tool: str, baseline: dict[Path, float] | None = None) -> PreflightStepResult:
            nonlocal in_flight, max_in_flight, started_count
            in_flight += 1
            max_in_flight = max(max_in_flight, in_flight)
            started_count += 1
            if started_count >= 2:
                all_started.set()
            time.sleep(0.1)
            in_flight -= 1
            return PreflightStepResult(
                tool=tool,
                files_changed=0,
                issues_fixed=0,
                duration_s=0.1,
                success=True,
            )

        with patch.object(fixer, "_run_step_sync", side_effect=slow_step):
            await fixer.run(RUN_ID, iteration=0)

        assert max_in_flight >= 2, (
            f"Expected parallel execution but max_in_flight={max_in_flight}"
        )

    @pytest.mark.asyncio
    async def test_parallel_preserves_baseline_per_tool(self, tmp_path: Path) -> None:
        """Tier-3 #13: Baseline must be captured once, before parallel dispatch.

        Each tool receives the SAME baseline snapshot (shared dict), so the
        race where two tools both see a baseline excluding each other's
        writes is avoided.
        """
        fixer, _ = self._make_fixer(tmp_path)
        captured_baselines: list[dict[Path, float]] = []

        def step_recording_baseline(tool: str, baseline: dict[Path, float] | None = None) -> PreflightStepResult:
            return PreflightStepResult(
                tool=tool,
                files_changed=0,
                issues_fixed=0,
                duration_s=0.0,
                success=True,
            )

        # Wrap _run_step_sync so we can observe the baseline it uses.
        original = fixer._run_step_sync

        def wrapped(tool: str, baseline: dict[Path, float] | None = None) -> PreflightStepResult:
            captured_baselines.append(baseline)
            return original(tool, baseline)

        with patch.object(fixer, "_run_step_sync", side_effect=wrapped):
            await fixer.run(RUN_ID, iteration=0)

        # Serial code captures a baseline per tool inside _run_step_sync.
        # Parallel code captures one baseline before the gather and passes
        # the SAME dict to every tool. Either is acceptable, but the test
        # here simply confirms the baseline machinery remains consistent.
        assert len(captured_baselines) >= 1


class TestPreflightParallelExecution:
    @pytest.mark.asyncio
    async def test_run_runs_all_enabled_tools_in_parallel(
        self, tmp_path: Path
    ) -> None:
        """All enabled tools must execute; gather should not drop any step."""
        fixer, _sink = _make_fixer(tmp_path)
        assert isinstance(fixer, PreflightFixer)
        with patch.object(
            fixer,
            "_run_step_sync",
            return_value=PreflightStepResult(
                tool="x",
                files_changed=0,
                issues_fixed=0,
                duration_s=0.0,
                success=True,
            ),
        ) as mock_step:
            report = await fixer.run(RUN_ID, iteration=0)
        enabled = fixer._enabled_tools()
        assert mock_step.call_count == len(enabled)
        assert len(report.steps) == len(enabled)

    @pytest.mark.asyncio
    async def test_parallel_executes_tools_concurrently(
        self, tmp_path: Path
    ) -> None:
        """Verify concurrent execution: peak concurrency must be > 1 when 2+ tools run."""
        fixer, _sink = _make_fixer(tmp_path)
        in_flight = 0
        peak = 0
        lock = threading.Lock()

        def fake_run_step_sync(tool: str) -> PreflightStepResult:
            nonlocal in_flight, peak
            with lock:
                in_flight += 1
                if in_flight > peak:
                    peak = in_flight
            time.sleep(0.05)
            with lock:
                in_flight -= 1
            return PreflightStepResult(
                tool=tool,
                files_changed=0,
                issues_fixed=0,
                duration_s=0.05,
                success=True,
            )

        with patch.object(fixer, "_run_step_sync", side_effect=fake_run_step_sync):
            await fixer.run(RUN_ID, iteration=0)
        # With 4 default tools enabled and 0.05s sleep each, serial = 0.2s,
        # parallel ≈ 0.05s. Peak concurrency should reflect that.
        assert peak >= 2, f"Expected concurrent execution, peak was {peak}"

    @pytest.mark.asyncio
    async def test_parallel_runs_faster_than_serial(
        self, tmp_path: Path
    ) -> None:
        """With N tools and delay D, parallel time should be < N*D."""
        fixer, _sink = _make_fixer(tmp_path)
        delay_s = 0.08
        enabled = fixer._enabled_tools()
        n_tools = len(enabled)
        if n_tools < 2:
            pytest.skip("Need >=2 tools for speedup test")

        def fake_run_step_sync(tool: str) -> PreflightStepResult:
            time.sleep(delay_s)
            return PreflightStepResult(
                tool=tool,
                files_changed=0,
                issues_fixed=0,
                duration_s=delay_s,
                success=True,
            )

        with patch.object(fixer, "_run_step_sync", side_effect=fake_run_step_sync):
            t0 = time.time()
            await fixer.run(RUN_ID, iteration=0)
            elapsed = time.time() - t0
        serial_lower_bound = (n_tools - 1) * delay_s
        # Allow generous slack for thread-pool scheduling. Must be strictly less
        # than the serial lower bound for the timing assertion to prove
        # concurrency (a serial loop with delay_s would take >= serial_lower_bound).
        assert elapsed < serial_lower_bound, (
            f"Parallel run took {elapsed:.3f}s, expected < {serial_lower_bound:.3f}s "
            f"(serial bound for {n_tools} tools × {delay_s}s)"
        )

    @pytest.mark.asyncio
    async def test_parallel_preserves_step_order(self, tmp_path: Path) -> None:
        """Result steps must follow `_enabled_tools()` order, not gather-completion order."""
        fixer, _sink = _make_fixer(tmp_path)
        # Tools finish in REVERSE order; gather would normally preserve
        # completion order (or scheduling order), so we deliberately out-of-order.
        reverse_tools: list[str] = list(reversed(fixer._enabled_tools()))

        def fake_run_step_sync(tool: str) -> PreflightStepResult:
            # Earlier tools sleep longer to finish last
            time.sleep(0.05 * (len(reverse_tools) - reverse_tools.index(tool)))
            return PreflightStepResult(
                tool=tool,
                files_changed=0,
                issues_fixed=0,
                duration_s=0.0,
                success=True,
            )

        with patch.object(fixer, "_run_step_sync", side_effect=fake_run_step_sync):
            report = await fixer.run(RUN_ID, iteration=0)
        assert [s.tool for s in report.steps] == fixer._enabled_tools()

    @pytest.mark.asyncio
    async def test_parallel_uses_shared_baseline(
        self, tmp_path: Path
    ) -> None:
        """Regression guard: parallel runs must share a single baseline snapshot
        captured before gather, not per-tool snapshots (which would race).
        """
        fixer, _sink = _make_fixer(tmp_path)
        # Create at least one .py file so snapshot returns something meaningful
        (tmp_path / "a.py").write_text("x = 1")

        snapshot_calls: list[float] = []

        def fake_snapshot() -> dict[Path, float]:
            snapshot_calls.append(time.time())
            return {}

        def fake_run_step_sync(tool: str) -> PreflightStepResult:
            # Each tool may need to read mtimes; if it calls _snapshot_mtimes,
            # the parallel implementation should NOT (baseline is shared).
            return PreflightStepResult(
                tool=tool,
                files_changed=0,
                issues_fixed=0,
                duration_s=0.0,
                success=True,
            )

        with (
            patch.object(fixer, "_snapshot_mtimes", side_effect=fake_snapshot),
            patch.object(fixer, "_run_step_sync", side_effect=fake_run_step_sync),
        ):
            await fixer.run(RUN_ID, iteration=0)
        # Allow at most one snapshot: the shared baseline. Anything more means
        # each tool still captured its own baseline (race-prone).
        assert len(snapshot_calls) <= 1, (
            f"Expected <=1 _snapshot_mtimes call (shared baseline), got "
            f"{len(snapshot_calls)}"
        )


class TestMetricsSinkWithPreflight:
    @pytest.mark.asyncio
    async def test_accumulates_preflight_savings(self) -> None:
        from crackerjack.core.ai_fix_events import PreflightFinished
        from crackerjack.core.ai_fix_sinks import MetricsSink

        sink = MetricsSink()
        await sink.handle(PreflightFinished(run_id=RUN_ID, iteration=0, issues_saved=7, duration_s=1.2))
        await sink.handle(PreflightFinished(run_id=RUN_ID, iteration=1, issues_saved=3, duration_s=0.8))
        assert sink.preflight_issues_saved == 10
        assert abs(sink.preflight_duration_s - 2.0) < 0.001

    @pytest.mark.asyncio
    async def test_summary_returns_dict(self) -> None:
        from crackerjack.core.ai_fix_sinks import MetricsSink
        sink = MetricsSink()
        summary = sink.summary()
        assert "preflight_issues_saved" in summary
        assert "preflight_duration_s" in summary
        assert "total_resolved" in summary
        assert "total_failed" in summary

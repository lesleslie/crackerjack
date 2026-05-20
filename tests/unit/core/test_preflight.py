from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
        bus = AIFixEventBus()
        sink = CaptureSink()
        bus.subscribe(sink)
        fixer = PreflightFixer(
            config=config or PreflightConfig(),
            bus=bus,
            pkg_path=tmp_path,
        )
        return fixer, sink

    @pytest.mark.asyncio
    async def test_emits_preflight_started(self, tmp_path: Path) -> None:
        fixer, sink = self._make_fixer(tmp_path)
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
        fixer, sink = self._make_fixer(tmp_path)
        with patch.object(fixer, "_run_step_sync", return_value=PreflightStepResult(
            tool="ruff_check", files_changed=2, issues_fixed=5, duration_s=0.1, success=True
        )):
            report = await fixer.run(RUN_ID, iteration=0)
        finishes = [e for e in sink.received if isinstance(e, PreflightFinished)]
        assert len(finishes) == 1
        assert finishes[0].issues_saved == report.total_issues_fixed

    @pytest.mark.asyncio
    async def test_returns_preflight_report(self, tmp_path: Path) -> None:
        fixer, sink = self._make_fixer(tmp_path)
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
        fixer, sink = self._make_fixer(tmp_path, config)
        with patch.object(fixer, "_run_step_sync") as mock_step:
            mock_step.return_value = PreflightStepResult(
                tool="x", files_changed=0, issues_fixed=0, duration_s=0.0, success=True
            )
            await fixer.run(RUN_ID, iteration=0)
        assert mock_step.call_count == 0

    @pytest.mark.asyncio
    async def test_event_order_start_before_finish(self, tmp_path: Path) -> None:
        fixer, sink = self._make_fixer(tmp_path)
        with patch.object(fixer, "_run_step_sync", return_value=PreflightStepResult(
            tool="ruff_check", files_changed=0, issues_fixed=0, duration_s=0.0, success=True
        )):
            await fixer.run(RUN_ID, iteration=0)
        types = [type(e).__name__ for e in sink.received]
        assert types.index("PreflightStarted") < types.index("PreflightFinished")

    def test_enabled_tools_default_config(self, tmp_path: Path) -> None:
        fixer, _ = self._make_fixer(tmp_path)
        tools = fixer._enabled_tools()
        assert "ruff_check" in tools
        assert "ruff_format" in tools
        assert "ruff_f401" in tools
        assert "refurb" in tools

    def test_enabled_tools_extra_selects(self, tmp_path: Path) -> None:
        config = PreflightConfig(ruff_select_extra=["SIM", "UP"])
        fixer, _ = self._make_fixer(tmp_path, config)
        tools = fixer._enabled_tools()
        assert "ruff_extra" in tools

    def test_build_cmd_ruff_check(self, tmp_path: Path) -> None:
        fixer, _ = self._make_fixer(tmp_path)
        cmd = fixer._build_cmd("ruff_check")
        assert "ruff" in cmd
        assert "check" in cmd
        assert "--fix" in cmd

    def test_build_cmd_ruff_check_unsafe(self, tmp_path: Path) -> None:
        config = PreflightConfig(ruff_unsafe_fixes=True)
        fixer, _ = self._make_fixer(tmp_path, config)
        cmd = fixer._build_cmd("ruff_check")
        assert "--unsafe-fixes" in cmd

    def test_build_cmd_ruff_format(self, tmp_path: Path) -> None:
        fixer, _ = self._make_fixer(tmp_path)
        cmd = fixer._build_cmd("ruff_format")
        assert "format" in cmd

    def test_build_cmd_ruff_extra(self, tmp_path: Path) -> None:
        config = PreflightConfig(ruff_select_extra=["SIM", "UP"])
        fixer, _ = self._make_fixer(tmp_path, config)
        cmd = fixer._build_cmd("ruff_extra")
        assert "--select" in cmd
        assert "SIM,UP" in cmd

    def test_build_cmd_unknown_returns_empty(self, tmp_path: Path) -> None:
        fixer, _ = self._make_fixer(tmp_path)
        cmd = fixer._build_cmd("unknown_tool")
        assert cmd == []

    def test_snapshot_mtimes_captures_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.txt").write_text("not python")
        fixer, _ = self._make_fixer(tmp_path)
        mtimes = fixer._snapshot_mtimes()
        paths = list(mtimes.keys())
        assert any(p.name == "a.py" for p in paths)
        assert not any(p.name == "b.txt" for p in paths)

    def test_count_changed_files_detects_change(self, tmp_path: Path) -> None:
        f = tmp_path / "module.py"
        f.write_text("x = 1")
        fixer, _ = self._make_fixer(tmp_path)
        before = fixer._snapshot_mtimes()
        # wait enough for mtime to differ
        time.sleep(0.01)
        f.write_text("x = 2")
        changed = fixer._count_changed_files(before)
        assert changed == 1

    def test_count_changed_files_no_change(self, tmp_path: Path) -> None:
        (tmp_path / "module.py").write_text("x = 1")
        fixer, _ = self._make_fixer(tmp_path)
        before = fixer._snapshot_mtimes()
        assert fixer._count_changed_files(before) == 0

    def test_parse_issues_fixed_ruff_output(self, tmp_path: Path) -> None:
        fixer, _ = self._make_fixer(tmp_path)
        assert fixer._parse_issues_fixed("Fixed 12 errors.") == 12
        assert fixer._parse_issues_fixed("Fixed 1 error.") == 1

    def test_parse_issues_fixed_no_match(self, tmp_path: Path) -> None:
        fixer, _ = self._make_fixer(tmp_path)
        assert fixer._parse_issues_fixed("All checks passed!") == 0


class TestMetricsSinkWithPreflight:
    @pytest.mark.asyncio
    async def test_accumulates_preflight_savings(self) -> None:
        from crackerjack.core.ai_fix_sinks import MetricsSink
        from crackerjack.core.ai_fix_events import PreflightFinished

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

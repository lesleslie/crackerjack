from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import (
    AgentDispatched,
    IssueFailed,
    IssueResolved,
    IterationFinished,
    IterationStarted,
    RunFinished,
    RunStarted,
)
from crackerjack.core.ai_fix_sinks import JsonlSink, LoggingSink, MetricsSink, build_default_bus


RUN_ID = "2026-01-01-0000-abcd"


class TestLoggingSink:
    @pytest.mark.asyncio
    async def test_run_started_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        sink = LoggingSink()
        with caplog.at_level(logging.INFO, logger="crackerjack.core.ai_fix_sinks"):
            await sink.handle(RunStarted(run_id=RUN_ID, iteration=0, stage="comprehensive", initial_issue_count=5))
        assert RUN_ID in caplog.text
        assert "stage=comprehensive" in caplog.text
        assert "issues=5" in caplog.text

    @pytest.mark.asyncio
    async def test_iteration_started_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        sink = LoggingSink()
        with caplog.at_level(logging.INFO, logger="crackerjack.core.ai_fix_sinks"):
            await sink.handle(IterationStarted(run_id=RUN_ID, iteration=2, issue_count=3))
        assert "Iteration 2 started" in caplog.text
        assert "issues=3" in caplog.text

    @pytest.mark.asyncio
    async def test_agent_dispatched_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        sink = LoggingSink()
        with caplog.at_level(logging.INFO, logger="crackerjack.core.ai_fix_sinks"):
            await sink.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="SecurityAgent", action="scan", file="auth.py"))
        assert "SecurityAgent" in caplog.text
        assert "scan" in caplog.text
        assert "auth.py" in caplog.text

    @pytest.mark.asyncio
    async def test_issue_resolved_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        sink = LoggingSink()
        with caplog.at_level(logging.INFO, logger="crackerjack.core.ai_fix_sinks"):
            await sink.handle(IssueResolved(run_id=RUN_ID, iteration=0, agent="RefactoringAgent", file="utils.py", duration_s=1.5))
        assert "resolved" in caplog.text
        assert "1.5s" in caplog.text

    @pytest.mark.asyncio
    async def test_issue_failed_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        sink = LoggingSink()
        with caplog.at_level(logging.INFO, logger="crackerjack.core.ai_fix_sinks"):
            await sink.handle(IssueFailed(run_id=RUN_ID, iteration=0, agent="SecurityAgent", file="auth.py", reason="timeout"))
        assert "failed" in caplog.text
        assert "timeout" in caplog.text

    @pytest.mark.asyncio
    async def test_iteration_finished_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        sink = LoggingSink()
        with caplog.at_level(logging.INFO, logger="crackerjack.core.ai_fix_sinks"):
            await sink.handle(IterationFinished(run_id=RUN_ID, iteration=1, resolved=3, failed=1))
        assert "Iteration 1 finished" in caplog.text
        assert "resolved=3" in caplog.text

    @pytest.mark.asyncio
    async def test_run_finished_logged(self, caplog: pytest.LogCaptureFixture) -> None:
        sink = LoggingSink()
        with caplog.at_level(logging.INFO, logger="crackerjack.core.ai_fix_sinks"):
            await sink.handle(RunFinished(run_id=RUN_ID, iteration=3, success=True, total_iterations=3))
        assert RUN_ID in caplog.text
        assert "finished" in caplog.text
        assert "success=True" in caplog.text


class TestJsonlSink:
    @pytest.mark.asyncio
    async def test_file_created_on_run_started(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        expected = tmp_path / ".crackerjack" / "runs" / RUN_ID / "events.jsonl"
        assert expected.exists()
        sink.close()

    @pytest.mark.asyncio
    async def test_events_written_as_jsonl(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        events = [
            RunStarted(run_id=RUN_ID, iteration=0, stage="fast"),
            IterationStarted(run_id=RUN_ID, iteration=1, issue_count=2),
            RunFinished(run_id=RUN_ID, iteration=1, success=True, total_iterations=1),
        ]
        for e in events:
            await sink.handle(e)
        sink.close()

        path = tmp_path / ".crackerjack" / "runs" / RUN_ID / "events.jsonl"
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 3
        for line in lines:
            json.loads(line)  # each line must be valid JSON

    @pytest.mark.asyncio
    async def test_events_before_run_started_not_written(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(IterationStarted(run_id=RUN_ID, iteration=0, issue_count=1))
        runs_dir = tmp_path / ".crackerjack" / "runs"
        assert not runs_dir.exists()

    @pytest.mark.asyncio
    async def test_run_id_in_written_lines(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        sink.close()
        path = tmp_path / ".crackerjack" / "runs" / RUN_ID / "events.jsonl"
        data = json.loads(path.read_text().strip())
        assert data["run_id"] == RUN_ID

    def test_close_idempotent(self, tmp_path: Path) -> None:
        sink = JsonlSink(base_dir=tmp_path)
        sink.close()
        sink.close()  # second close must not raise

    @pytest.mark.asyncio
    async def test_path_objects_serialised(self, tmp_path: Path) -> None:
        from crackerjack.core.ai_fix_events import AgentDispatched
        sink = JsonlSink(base_dir=tmp_path)
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        await sink.handle(AgentDispatched(run_id=RUN_ID, iteration=0, agent="A", action="fix", file=str(tmp_path / "foo.py")))
        sink.close()
        path = tmp_path / ".crackerjack" / "runs" / RUN_ID / "events.jsonl"
        lines = path.read_text().strip().splitlines()
        assert len(lines) == 2
        json.loads(lines[1])  # must not raise even with path-like string


class TestMetricsSink:
    @pytest.mark.asyncio
    async def test_noop(self) -> None:
        sink = MetricsSink()
        # Should not raise for any event
        await sink.handle(RunStarted(run_id=RUN_ID, iteration=0))
        await sink.handle(RunFinished(run_id=RUN_ID, iteration=0))


class TestBuildDefaultBus:
    def test_returns_bus(self) -> None:
        bus = build_default_bus()
        assert isinstance(bus, AIFixEventBus)

    @pytest.mark.asyncio
    async def test_default_bus_emits_without_error(self, tmp_path: Path) -> None:
        bus = build_default_bus(base_dir=tmp_path)
        assert isinstance(bus, AIFixEventBus)
        await bus.emit(RunStarted(run_id=RUN_ID, iteration=0, stage="fast"))
        await bus.emit(RunFinished(run_id=RUN_ID, iteration=0, success=True))

"""Tests for ai_fix_sinks module."""

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.core.ai_fix_events import (
    AIFixEvent,
    AgentDispatched,
    IssueFailed,
    IssueResolved,
    IterationFinished,
    IterationStarted,
    PreflightFinished,
    PreflightStarted,
    RunFinished,
    RunStarted,
)
from crackerjack.core.ai_fix_sinks import (
    JsonlSink,
    LoggingSink,
    MetricsSink,
    build_default_bus,
)


class TestLoggingSink:
    """Tests for LoggingSink class."""

    @pytest.fixture
    def logging_sink(self) -> LoggingSink:
        """Create a LoggingSink instance for testing."""
        return LoggingSink()

    def test_init(self) -> None:
        """Test LoggingSink initialization."""
        sink = LoggingSink()
        assert sink._FORMATTERS is not None
        assert len(sink._FORMATTERS) > 0

    @pytest.mark.asyncio
    async def test_handle_run_started(self, logging_sink: LoggingSink) -> None:
        """Test handling RunStarted event."""
        event = RunStarted(
            run_id="test-123",
            iteration=0,
            stage="preflight",
            initial_issue_count=5,
        )
        msg = logging_sink._format(event)
        assert "AI-fix run test-123 started" in msg
        assert "stage=preflight" in msg
        assert "issues=5" in msg

    @pytest.mark.asyncio
    async def test_handle_iteration_started(self, logging_sink: LoggingSink) -> None:
        """Test handling IterationStarted event."""
        event = IterationStarted(
            run_id="test-123",
            iteration=2,
            strategy="aggressive",
            issue_count=3,
        )
        msg = logging_sink._format(event)
        assert "Iteration 2 started" in msg
        assert "strategy=aggressive" in msg
        assert "issues=3" in msg

    @pytest.mark.asyncio
    async def test_handle_agent_dispatched(self, logging_sink: LoggingSink) -> None:
        """Test handling AgentDispatched event."""
        event = AgentDispatched(
            run_id="test-123",
            iteration=1,
            agent="refurb",
            action="remove_dead_code",
            file="src/main.py",
        )
        msg = logging_sink._format(event)
        assert "refurb: remove_dead_code" in msg
        assert "src/main.py" in msg

    @pytest.mark.asyncio
    async def test_handle_issue_resolved(self, logging_sink: LoggingSink) -> None:
        """Test handling IssueResolved event."""
        event = IssueResolved(
            run_id="test-123",
            iteration=1,
            agent="security",
            file="src/auth.py",
            duration_s=1.5,
        )
        msg = logging_sink._format(event)
        assert "security" in msg
        assert "resolved" in msg
        assert "src/auth.py" in msg
        assert "1.5s" in msg

    @pytest.mark.asyncio
    async def test_handle_issue_failed(self, logging_sink: LoggingSink) -> None:
        """Test handling IssueFailed event."""
        event = IssueFailed(
            run_id="test-123",
            iteration=1,
            agent="refurb",
            file="src/broken.py",
            reason="Syntax error",
        )
        msg = logging_sink._format(event)
        assert "refurb" in msg
        assert "failed" in msg
        assert "src/broken.py" in msg
        assert "Syntax error" in msg

    @pytest.mark.asyncio
    async def test_handle_iteration_finished(self, logging_sink: LoggingSink) -> None:
        """Test handling IterationFinished event."""
        event = IterationFinished(
            run_id="test-123",
            iteration=2,
            resolved=5,
            failed=1,
            success=True,
        )
        msg = logging_sink._format(event)
        assert "Iteration 2 finished" in msg
        assert "resolved=5" in msg
        assert "failed=1" in msg
        assert "ok=True" in msg

    @pytest.mark.asyncio
    async def test_handle_run_finished(self, logging_sink: LoggingSink) -> None:
        """Test handling RunFinished event."""
        event = RunFinished(
            run_id="test-123",
            iteration=5,
            success=True,
            total_iterations=3,
            total_resolved=10,
        )
        msg = logging_sink._format(event)
        assert "AI-fix run test-123 finished" in msg
        assert "success=True" in msg
        assert "iterations=3" in msg

    @pytest.mark.asyncio
    async def test_handle_preflight_started(self, logging_sink: LoggingSink) -> None:
        """Test handling PreflightStarted event."""
        event = PreflightStarted(
            run_id="test-123",
            iteration=0,
            tools=("ruff", "mypy"),
        )
        msg = logging_sink._format(event)
        assert "Pre-flight started" in msg
        assert "ruff" in msg
        assert "mypy" in msg

    @pytest.mark.asyncio
    async def test_handle_preflight_finished(self, logging_sink: LoggingSink) -> None:
        """Test handling PreflightFinished event."""
        event = PreflightFinished(
            run_id="test-123",
            iteration=0,
            issues_saved=5,
            duration_s=2.5,
        )
        msg = logging_sink._format(event)
        assert "Pre-flight finished" in msg
        assert "saved≈5 issues" in msg
        assert "2.5s" in msg

    @pytest.mark.asyncio
    async def test_handle_unknown_event(self, logging_sink: LoggingSink) -> None:
        """Test handling unknown event type."""
        event = AIFixEvent(run_id="test-123", iteration=99)
        msg = logging_sink._format(event)
        assert msg == ""

    @pytest.mark.asyncio
    async def test_async_handle_logs_to_logger(self, logging_sink: LoggingSink, caplog: pytest.LogCaptureFixture) -> None:
        """Test that async handle method logs to logger."""
        event = RunStarted(run_id="test-123", iteration=0, stage="test", initial_issue_count=1)
        with caplog.at_level(logging.INFO):
            await logging_sink.handle(event)
        assert "AI-fix run test-123 started" in caplog.text


class TestJsonlSink:
    """Tests for JsonlSink class."""

    @pytest.fixture
    def temp_dir(self, tmp_path: Path) -> Path:
        """Create a temporary directory for testing."""
        return tmp_path

    def test_init_default_base_dir(self) -> None:
        """Test JsonlSink initialization with default base_dir."""
        sink = JsonlSink()
        assert sink._base_dir == Path.cwd()
        assert sink._file is None

    def test_init_custom_base_dir(self, temp_dir: Path) -> None:
        """Test JsonlSink initialization with custom base_dir."""
        sink = JsonlSink(base_dir=temp_dir)
        assert sink._base_dir == temp_dir
        assert sink._file is None

    @pytest.mark.asyncio
    async def test_handle_creates_run_directory(self, temp_dir: Path) -> None:
        """Test that handle creates the run directory on RunStarted."""
        sink = JsonlSink(base_dir=temp_dir)
        event = RunStarted(run_id="test-run-456", iteration=0, stage="test", initial_issue_count=1)

        await sink.handle(event)

        run_dir = temp_dir / ".crackerjack" / "runs" / "test-run-456"
        assert run_dir.exists()

    @pytest.mark.asyncio
    async def test_handle_writes_jsonl(self, temp_dir: Path) -> None:
        """Test that handle writes events to JSONL file."""
        sink = JsonlSink(base_dir=temp_dir)
        event = RunStarted(run_id="test-run-789", iteration=0, stage="test", initial_issue_count=2)

        await sink.handle(event)

        jsonl_file = temp_dir / ".crackerjack" / "runs" / "test-run-789" / "events.jsonl"
        assert jsonl_file.exists()
        content = jsonl_file.read_text()
        assert "test-run-789" in content

    @pytest.mark.asyncio
    async def test_handle_multiple_events(self, temp_dir: Path) -> None:
        """Test writing multiple events to JSONL."""
        sink = JsonlSink(base_dir=temp_dir)

        await sink.handle(RunStarted(run_id="multi-test", iteration=0, stage="preflight", initial_issue_count=3))
        await sink.handle(IterationStarted(run_id="multi-test", iteration=1, strategy="fast", issue_count=3))
        await sink.handle(IssueResolved(run_id="multi-test", iteration=1, agent="test", file="test.py", duration_s=0.5))

        jsonl_file = temp_dir / ".crackerjack" / "runs" / "multi-test" / "events.jsonl"
        lines = jsonl_file.read_text().strip().split("\n")
        assert len(lines) == 3

    def test_close(self, temp_dir: Path) -> None:
        """Test closing the JSONL sink."""
        sink = JsonlSink(base_dir=temp_dir)
        event = RunStarted(run_id="close-test", iteration=0, stage="test", initial_issue_count=1)

        import asyncio
        asyncio.run(sink.handle(event))
        sink.close()

        assert sink._file is None

    def test_close_when_not_open(self) -> None:
        """Test closing when no file is open."""
        sink = JsonlSink()
        # Should not raise
        sink.close()

    @pytest.mark.asyncio
    async def test_handle_before_run_started_no_write(self, temp_dir: Path) -> None:
        """Test that non-RunStarted events don't write before RunStarted."""
        sink = JsonlSink(base_dir=temp_dir)
        event = IterationStarted(run_id="early-test", iteration=1, strategy="fast", issue_count=1)

        await sink.handle(event)

        # No file should be created yet
        jsonl_file = temp_dir / ".crackerjack" / "runs" / "early-test" / "events.jsonl"
        assert not jsonl_file.exists()

    @pytest.mark.asyncio
    async def test_handle_after_run_started_writes(self, temp_dir: Path) -> None:
        """Test that events after RunStarted are written."""
        sink = JsonlSink(base_dir=temp_dir)

        await sink.handle(RunStarted(run_id="after-test", iteration=0, stage="test", initial_issue_count=1))
        await sink.handle(IterationStarted(run_id="after-test", iteration=1, strategy="fast", issue_count=1))

        jsonl_file = temp_dir / ".crackerjack" / "runs" / "after-test" / "events.jsonl"
        assert jsonl_file.exists()
        lines = jsonl_file.read_text().strip().split("\n")
        assert len(lines) == 2


class TestMetricsSink:
    """Tests for MetricsSink class."""

    @pytest.fixture
    def metrics_sink(self) -> MetricsSink:
        """Create a MetricsSink instance for testing."""
        return MetricsSink()

    def test_init(self, metrics_sink: MetricsSink) -> None:
        """Test MetricsSink initialization."""
        assert metrics_sink.preflight_issues_saved == 0
        assert metrics_sink.preflight_duration_s == 0.0
        assert metrics_sink.total_resolved == 0
        assert metrics_sink.total_failed == 0

    @pytest.mark.asyncio
    async def test_handle_preflight_finished(self, metrics_sink: MetricsSink) -> None:
        """Test handling PreflightFinished updates metrics."""
        event = PreflightFinished(
            run_id="test-123",
            iteration=0,
            issues_saved=5,
            duration_s=2.5,
        )
        await metrics_sink.handle(event)
        assert metrics_sink.preflight_issues_saved == 5
        assert metrics_sink.preflight_duration_s == 2.5

    @pytest.mark.asyncio
    async def test_handle_multiple_preflight_finished(self, metrics_sink: MetricsSink) -> None:
        """Test handling multiple PreflightFinished events accumulates."""
        event1 = PreflightFinished(run_id="test-1", iteration=0, issues_saved=3, duration_s=1.0)
        event2 = PreflightFinished(run_id="test-2", iteration=0, issues_saved=7, duration_s=2.0)

        await metrics_sink.handle(event1)
        await metrics_sink.handle(event2)

        assert metrics_sink.preflight_issues_saved == 10
        assert metrics_sink.preflight_duration_s == 3.0

    @pytest.mark.asyncio
    async def test_handle_issue_resolved(self, metrics_sink: MetricsSink) -> None:
        """Test handling IssueResolved increments total_resolved."""
        event = IssueResolved(
            run_id="test-123",
            iteration=1,
            agent="test",
            file="test.py",
            duration_s=0.5,
        )
        await metrics_sink.handle(event)
        assert metrics_sink.total_resolved == 1

    @pytest.mark.asyncio
    async def test_handle_issue_failed(self, metrics_sink: MetricsSink) -> None:
        """Test handling IssueFailed increments total_failed."""
        event = IssueFailed(
            run_id="test-123",
            iteration=1,
            agent="test",
            file="test.py",
            reason="error",
        )
        await metrics_sink.handle(event)
        assert metrics_sink.total_failed == 1

    @pytest.mark.asyncio
    async def test_handle_ignored_events(self, metrics_sink: MetricsSink) -> None:
        """Test that other event types are ignored."""
        events = [
            RunStarted(run_id="test", iteration=0, stage="test", initial_issue_count=1),
            IterationStarted(run_id="test", iteration=1, strategy="fast", issue_count=1),
            AgentDispatched(run_id="test", iteration=1, agent="test", action="act", file="f.py"),
            IterationFinished(run_id="test", iteration=1, resolved=1, failed=0),
            RunFinished(run_id="test", iteration=1, success=True, total_iterations=1, total_resolved=1),
            PreflightStarted(run_id="test", iteration=0, tools=("t",)),
        ]

        for event in events:
            await metrics_sink.handle(event)

        # Only issue events should have modified counters
        assert metrics_sink.preflight_issues_saved == 0
        assert metrics_sink.preflight_duration_s == 0.0
        assert metrics_sink.total_resolved == 0
        assert metrics_sink.total_failed == 0

    def test_summary(self, metrics_sink: MetricsSink) -> None:
        """Test summary returns expected structure."""
        metrics_sink.preflight_issues_saved = 10
        metrics_sink.preflight_duration_s = 5.0
        metrics_sink.total_resolved = 15
        metrics_sink.total_failed = 2

        summary = metrics_sink.summary()

        assert summary["preflight_issues_saved"] == 10
        assert summary["preflight_duration_s"] == 5.0
        assert summary["total_resolved"] == 15
        assert summary["total_failed"] == 2


class TestBuildDefaultBus:
    """Tests for build_default_bus function."""

    def test_build_default_bus_returns_bus(self) -> None:
        """Test build_default_bus returns an AIFixEventBus."""
        from crackerjack.core.ai_fix_event_bus import AIFixEventBus
        bus = build_default_bus()
        assert isinstance(bus, AIFixEventBus)

    def test_build_default_bus_has_three_sinks(self) -> None:
        """Test build_default_bus subscribes three sinks."""
        bus = build_default_bus()
        assert len(bus._sinks) == 3

    def test_build_default_bus_with_custom_base_dir(self, tmp_path: Path) -> None:
        """Test build_default_bus with custom base_dir."""
        bus = build_default_bus(base_dir=tmp_path)
        assert isinstance(bus._sinks[1], JsonlSink)
        # Access the JsonlSink's base_dir
        jsonl_sink = bus._sinks[1]
        assert jsonl_sink._base_dir == tmp_path

    @pytest.mark.asyncio
    async def test_default_bus_emits_to_all_sinks(self, tmp_path: Path) -> None:
        """Test that default bus emits to all subscribed sinks."""
        bus = build_default_bus(base_dir=tmp_path)
        event = RunStarted(run_id="default-bus-test", iteration=0, stage="test", initial_issue_count=1)

        await bus.emit(event)

        # Verify JSONL file was created
        jsonl_file = tmp_path / ".crackerjack" / "runs" / "default-bus-test" / "events.jsonl"
        assert jsonl_file.exists()
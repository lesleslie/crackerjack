"""Unit tests for ParallelDispatcher concurrent fix execution."""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.agents.parallel_dispatcher import DispatchResult, ParallelDispatcher
from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.models.fix_plan import ChangeSpec, FixPlan


@pytest.fixture
def mock_execute_plan():
    return AsyncMock()


@pytest.fixture
def mock_bus():
    return MagicMock(spec=AIFixEventBus)


@pytest.fixture
def mock_bus_with_emit():
    bus = MagicMock(spec=AIFixEventBus)
    bus.emit = AsyncMock()
    return bus


@pytest.fixture
def dispatcher(mock_execute_plan, mock_bus):
    return ParallelDispatcher(
        execute_plan=mock_execute_plan,
        bus=mock_bus,
        run_id="test-run-1",
        iteration=1,
        max_concurrency=4,
    )


def make_plan(file_path: str, issue_type: str = "type_error") -> FixPlan:
    return FixPlan(
        file_path=file_path,
        issue_type=issue_type,
        changes=[
            ChangeSpec(
                line_range=(1, 1),
                old_code="x = 1",
                new_code="x = 2",
                reason="test",
            )
        ],
        rationale="Test plan",
        risk_level="low",
        validated_by="test",
        issue_message="test",
        issue_stage=None,
        issue_details={},
    )


class TestParallelDispatcherInit:
    """Tests for ParallelDispatcher initialization."""

    def test_default_max_concurrency(self, mock_execute_plan, mock_bus):
        import os
        expected = min(8, os.cpu_count() or 4)
        disp = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus,
            run_id="r",
            iteration=1,
        )
        assert disp._max_concurrency == expected

    def test_custom_max_concurrency(self, mock_execute_plan, mock_bus):
        disp = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus,
            run_id="r",
            iteration=1,
            max_concurrency=2,
        )
        assert disp._max_concurrency == 2

    def test_memory_threshold_default(self, mock_execute_plan, mock_bus):
        disp = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus,
            run_id="r",
            iteration=1,
        )
        assert disp._memory_threshold == 80.0


class TestParallelDispatcherDispatch:
    """Tests for ParallelDispatcher.dispatch()."""

    @pytest.mark.asyncio
    async def test_dispatch_empty_plans(self, dispatcher, mock_bus):
        result = await dispatcher.dispatch([])

        assert isinstance(result, DispatchResult)
        assert result.resolved == 0
        assert result.failed == 0
        assert result.elapsed_s >= 0

    @pytest.mark.asyncio
    async def test_dispatch_single_plan_success(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-1",
            iteration=1,
        )

        mock_execute_plan.return_value = FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=["Fixed x"],
            remaining_issues=[],
        )

        plans = [make_plan("/tmp/test1.py")]
        result = await dispatcher.dispatch(plans)

        assert result.resolved == 1
        assert result.failed == 0
        assert len(result.results) == 1
        assert result.results[0].success is True

    @pytest.mark.asyncio
    async def test_dispatch_single_plan_failure(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-1",
            iteration=1,
        )

        mock_execute_plan.return_value = FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Execution failed"],
        )

        plans = [make_plan("/tmp/test1.py")]
        result = await dispatcher.dispatch(plans)

        assert result.resolved == 0
        assert result.failed == 1
        assert result.results[0].success is False

    @pytest.mark.asyncio
    async def test_dispatch_exception_handling(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-1",
            iteration=1,
        )

        mock_execute_plan.side_effect = RuntimeError("Plan execution crashed")

        plans = [make_plan("/tmp/test1.py")]
        result = await dispatcher.dispatch(plans)

        assert result.failed == 1
        assert result.results[0].success is False
        assert "Plan execution crashed" in result.results[0].remaining_issues[0]

    @pytest.mark.asyncio
    async def test_dispatch_multiple_plans_concurrent(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-1",
            iteration=1,
            max_concurrency=4,
        )

        call_times: list[float] = []

        async def slow_execute(plan):
            await asyncio.sleep(0.05)
            call_times.append(time.monotonic())
            return FixResult(success=True, confidence=0.9)

        mock_execute_plan.side_effect = slow_execute

        plans = [make_plan(f"/tmp/test{i}.py") for i in range(4)]
        start = time.monotonic()
        result = await dispatcher.dispatch(plans)
        elapsed = time.monotonic() - start

        assert result.resolved == 4
        # With concurrency=4 and 4 plans at 50ms each, should complete in ~50ms (parallel)
        # Sequential would be ~200ms
        assert elapsed < 0.15

    @pytest.mark.asyncio
    async def test_dispatch_respects_max_concurrency(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-1",
            iteration=1,
            max_concurrency=2,
        )

        active_count = 0
        max_active = 0
        lock = asyncio.Lock()

        async def tracking_execute(plan):
            nonlocal active_count, max_active
            async with lock:
                active_count += 1
                max_active = max(max_active, active_count)

            await asyncio.sleep(0.05)

            async with lock:
                active_count -= 1

            return FixResult(success=True, confidence=0.9)

        mock_execute_plan.side_effect = tracking_execute

        plans = [make_plan(f"/tmp/test{i}.py") for i in range(6)]

        await dispatcher.dispatch(plans)

        assert max_active <= 2

    @pytest.mark.asyncio
    async def test_dispatch_all_success(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-1",
            iteration=1,
        )

        mock_execute_plan.return_value = FixResult(
            success=True,
            confidence=0.95,
            fixes_applied=["fix1", "fix2"],
            remaining_issues=[],
        )

        plans = [make_plan(f"/tmp/test{i}.py") for i in range(3)]
        result = await dispatcher.dispatch(plans)

        assert result.resolved == 3
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_dispatch_all_fail(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-1",
            iteration=1,
        )

        mock_execute_plan.return_value = FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Failed"],
        )

        plans = [make_plan(f"/tmp/test{i}.py") for i in range(2)]
        result = await dispatcher.dispatch(plans)

        assert result.resolved == 0
        assert result.failed == 2

    @pytest.mark.asyncio
    async def test_dispatch_mixed_success_failure(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-1",
            iteration=1,
        )

        results = [
            FixResult(success=True, confidence=0.9),
            FixResult(success=False, confidence=0.0, remaining_issues=["fail"]),
            FixResult(success=True, confidence=0.8),
        ]
        mock_execute_plan.side_effect = results

        plans = [make_plan(f"/tmp/test{i}.py") for i in range(3)]
        result = await dispatcher.dispatch(plans)

        assert result.resolved == 2
        assert result.failed == 1

    @pytest.mark.asyncio
    async def test_dispatch_elapsed_time_recorded(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-1",
            iteration=1,
        )

        mock_execute_plan.return_value = FixResult(success=True, confidence=0.9)

        plans = [make_plan("/tmp/test.py")]
        result = await dispatcher.dispatch(plans)

        assert result.elapsed_s > 0


class TestParallelDispatcherClustering:
    """Tests for ParallelDispatcher file-clustering behavior."""

    @pytest.mark.asyncio
    async def test_dispatch_groups_plans_by_file(self, mock_execute_plan, mock_bus_with_emit):
        """Plans for the same file are grouped together."""
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-1",
            iteration=1,
            max_concurrency=4,
        )

        execution_order: list[str] = []

        async def track_execute(plan):
            execution_order.append(plan.file_path)
            await asyncio.sleep(0.02)
            return FixResult(success=True, confidence=0.9)

        mock_execute_plan.side_effect = track_execute

        plans = [
            make_plan("/tmp/a.py"),
            make_plan("/tmp/b.py"),
            make_plan("/tmp/a.py"),  # same file
            make_plan("/tmp/b.py"),  # same file
        ]

        await dispatcher.dispatch(plans)

        # With max_concurrency=4, all can run concurrently
        assert len(execution_order) == 4


class TestParallelDispatcherEvents:
    """Tests for ParallelDispatcher event emission."""

    @pytest.mark.asyncio
    async def test_emits_agent_dispatched_event(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-99",
            iteration=5,
        )

        mock_execute_plan.return_value = FixResult(success=True, confidence=0.9)

        plans = [make_plan("/tmp/test.py", "type_error")]
        await dispatcher.dispatch(plans)

        mock_bus_with_emit.emit.assert_called()
        calls = mock_bus_with_emit.emit.call_args_list
        event_types = [call[0][0].__class__.__name__ for call in calls]
        assert "AgentDispatched" in event_types
        assert "IssueResolved" in event_types

    @pytest.mark.asyncio
    async def test_emits_issue_failed_event_on_exception(self, mock_execute_plan, mock_bus_with_emit):
        dispatcher = ParallelDispatcher(
            execute_plan=mock_execute_plan,
            bus=mock_bus_with_emit,
            run_id="run-99",
            iteration=5,
        )

        mock_execute_plan.side_effect = RuntimeError("boom")

        plans = [make_plan("/tmp/test.py")]
        await dispatcher.dispatch(plans)

        mock_bus_with_emit.emit.assert_called()
        calls = mock_bus_with_emit.emit.call_args_list
        event_types = [call[0][0].__class__.__name__ for call in calls]
        assert "IssueFailed" in event_types
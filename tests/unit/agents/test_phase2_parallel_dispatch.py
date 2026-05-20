from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.agents.issue_clusterer import EditUnit, IssueClusterer
from crackerjack.agents.parallel_dispatcher import DispatchResult, ParallelDispatcher
from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import AgentDispatched, IssueFailed, IssueResolved
from crackerjack.executors.hook_lock_manager import FileEditLock
from crackerjack.models.fix_plan import FixPlan


RUN_ID = "2026-01-01-0000-test"


# ─── helpers ─────────────────────────────────────────────────────────────────

def make_plan(file_path: str, issue_type: str = "type_error", line: int = 1) -> FixPlan:
    change = MagicMock()
    change.line_range = (line, line + 3)
    plan = MagicMock(spec=FixPlan)
    plan.file_path = file_path
    plan.issue_type = issue_type
    plan.changes = [change]
    return plan


class CaptureSink:
    def __init__(self) -> None:
        self.received: list[object] = []

    async def handle(self, event: object) -> None:
        self.received.append(event)


def make_dispatcher(
    execute_plan=None,
    max_concurrency: int = 4,
) -> tuple[ParallelDispatcher, CaptureSink]:
    bus = AIFixEventBus()
    sink = CaptureSink()
    bus.subscribe(sink)
    if execute_plan is None:
        execute_plan = AsyncMock(return_value=FixResult(success=True, confidence=0.9))
    dispatcher = ParallelDispatcher(
        execute_plan=execute_plan,
        bus=bus,
        run_id=RUN_ID,
        iteration=0,
        max_concurrency=max_concurrency,
    )
    return dispatcher, sink


# ─── FileEditLock ─────────────────────────────────────────────────────────────

class TestFileEditLock:
    def setup_method(self) -> None:
        FileEditLock.clear_registry()

    def teardown_method(self) -> None:
        FileEditLock.clear_registry()

    @pytest.mark.asyncio
    async def test_same_path_same_lock(self, tmp_path: Path) -> None:
        f = tmp_path / "module.py"
        lock_a = FileEditLock(f)
        lock_b = FileEditLock(f)
        assert await lock_a._lock() is await lock_b._lock()

    @pytest.mark.asyncio
    async def test_different_paths_different_locks(self, tmp_path: Path) -> None:
        lock_a = FileEditLock(tmp_path / "a.py")
        lock_b = FileEditLock(tmp_path / "b.py")
        assert await lock_a._lock() is not await lock_b._lock()

    @pytest.mark.asyncio
    async def test_context_manager_acquires_and_releases(self, tmp_path: Path) -> None:
        f = tmp_path / "x.py"
        async with FileEditLock(f) as lock:
            assert lock is not None
        # lock should be released — acquiring again must not block
        async with asyncio.timeout(0.1):
            async with FileEditLock(f):
                pass

    @pytest.mark.asyncio
    async def test_serializes_concurrent_access(self, tmp_path: Path) -> None:
        """Two coroutines on the same file must not overlap."""
        f = tmp_path / "shared.py"
        order: list[str] = []

        async def enter(label: str) -> None:
            async with FileEditLock(f):
                order.append(f"{label}_enter")
                await asyncio.sleep(0.01)
                order.append(f"{label}_exit")

        await asyncio.gather(enter("A"), enter("B"))
        # Entries and exits must be strictly nested
        assert order[0].endswith("_enter")
        assert order[1].endswith("_exit")
        assert order[2].endswith("_enter")
        assert order[3].endswith("_exit")

    @pytest.mark.asyncio
    async def test_clear_registry(self, tmp_path: Path) -> None:
        f = tmp_path / "m.py"
        lock_a = FileEditLock(f)
        original_lock = await lock_a._lock()  # populates registry
        FileEditLock.clear_registry()
        lock_b = FileEditLock(f)
        new_lock = await lock_b._lock()
        # After clear, a brand-new Lock instance is created for the same path
        assert new_lock is not original_lock


# ─── IssueClusterer ───────────────────────────────────────────────────────────

class TestIssueClusterer:
    def test_cluster_plans_groups_by_file(self) -> None:
        plans = [
            make_plan("a.py", line=1),
            make_plan("b.py", line=5),
            make_plan("a.py", line=10),
        ]
        clusterer = IssueClusterer()
        groups = clusterer.cluster_plans(plans)
        files = [g[0].file_path for g in groups]
        assert "a.py" in files
        assert "b.py" in files
        a_group = next(g for g in groups if g[0].file_path == "a.py")
        assert len(a_group) == 2

    def test_cluster_plans_sorted_by_line(self) -> None:
        plans = [make_plan("a.py", line=20), make_plan("a.py", line=5)]
        clusterer = IssueClusterer()
        groups = clusterer.cluster_plans(plans)
        a_group = groups[0]
        lines = [p.changes[0].line_range[0] for p in a_group]
        assert lines == sorted(lines)

    def test_cluster_plans_descending_by_group_size(self) -> None:
        plans = [
            make_plan("a.py", line=1),
            make_plan("a.py", line=2),
            make_plan("a.py", line=3),
            make_plan("b.py", line=1),
        ]
        clusterer = IssueClusterer()
        groups = clusterer.cluster_plans(plans)
        sizes = [len(g) for g in groups]
        assert sizes == sorted(sizes, reverse=True)

    def test_cluster_plans_empty(self) -> None:
        assert IssueClusterer().cluster_plans([]) == []

    def test_cluster_plans_single_plan(self) -> None:
        plans = [make_plan("only.py")]
        groups = IssueClusterer().cluster_plans(plans)
        assert len(groups) == 1
        assert groups[0][0].file_path == "only.py"


# ─── ParallelDispatcher ───────────────────────────────────────────────────────

class TestParallelDispatcher:
    def teardown_method(self) -> None:
        FileEditLock.clear_registry()

    @pytest.mark.asyncio
    async def test_empty_plans_returns_empty_result(self) -> None:
        dispatcher, _ = make_dispatcher()
        result = await dispatcher.dispatch([])
        assert result.results == []
        assert result.resolved == 0
        assert result.failed == 0

    @pytest.mark.asyncio
    async def test_successful_plan_increments_resolved(self) -> None:
        dispatcher, _ = make_dispatcher()
        result = await dispatcher.dispatch([make_plan("a.py")])
        assert result.resolved == 1
        assert result.failed == 0
        assert len(result.results) == 1
        assert result.results[0].success is True

    @pytest.mark.asyncio
    async def test_failed_plan_increments_failed(self) -> None:
        execute = AsyncMock(return_value=FixResult(success=False, confidence=0.0, remaining_issues=["oops"]))
        dispatcher, _ = make_dispatcher(execute_plan=execute)
        result = await dispatcher.dispatch([make_plan("a.py")])
        assert result.failed == 1
        assert result.resolved == 0

    @pytest.mark.asyncio
    async def test_exception_in_execute_counts_as_failed(self) -> None:
        execute = AsyncMock(side_effect=RuntimeError("boom"))
        dispatcher, _ = make_dispatcher(execute_plan=execute)
        result = await dispatcher.dispatch([make_plan("a.py")])
        assert result.failed == 1
        assert result.results[0].success is False

    @pytest.mark.asyncio
    async def test_emits_agent_dispatched_event(self) -> None:
        dispatcher, sink = make_dispatcher()
        await dispatcher.dispatch([make_plan("mod.py", issue_type="security")])
        dispatched = [e for e in sink.received if isinstance(e, AgentDispatched)]
        assert len(dispatched) == 1
        assert dispatched[0].file == "mod.py"
        assert dispatched[0].agent == "security"

    @pytest.mark.asyncio
    async def test_emits_issue_resolved_on_success(self) -> None:
        dispatcher, sink = make_dispatcher()
        await dispatcher.dispatch([make_plan("ok.py")])
        resolved = [e for e in sink.received if isinstance(e, IssueResolved)]
        assert len(resolved) == 1
        assert resolved[0].file == "ok.py"

    @pytest.mark.asyncio
    async def test_emits_issue_failed_on_failure(self) -> None:
        execute = AsyncMock(return_value=FixResult(success=False, remaining_issues=["e"]))
        dispatcher, sink = make_dispatcher(execute_plan=execute)
        await dispatcher.dispatch([make_plan("bad.py")])
        failed_events = [e for e in sink.received if isinstance(e, IssueFailed)]
        assert len(failed_events) == 1
        assert failed_events[0].file == "bad.py"

    @pytest.mark.asyncio
    async def test_plans_for_same_file_run_serially(self) -> None:
        """Verify same-file plans do not overlap (FileEditLock)."""
        order: list[str] = []

        async def execute(plan: FixPlan) -> FixResult:
            label = f"{plan.file_path}:{plan.changes[0].line_range[0]}"
            order.append(f"{label}_start")
            await asyncio.sleep(0.01)
            order.append(f"{label}_end")
            return FixResult(success=True)

        plans = [make_plan("same.py", line=1), make_plan("same.py", line=10)]
        dispatcher, _ = make_dispatcher(execute_plan=execute)
        await dispatcher.dispatch(plans)

        # Interleaving would be: same.py:1_start, same.py:10_start, ...
        # Serialized: same.py:1_start, same.py:1_end, same.py:10_start, same.py:10_end
        assert order.index("same.py:1_end") < order.index("same.py:10_start")

    @pytest.mark.asyncio
    async def test_plans_for_different_files_run_concurrently(self) -> None:
        """Different files should not be serialized."""
        started: list[str] = []
        barrier = asyncio.Event()

        async def execute(plan: FixPlan) -> FixResult:
            started.append(plan.file_path)
            if len(started) == 2:
                barrier.set()
            await asyncio.wait_for(barrier.wait(), timeout=2.0)
            return FixResult(success=True)

        plans = [make_plan("a.py"), make_plan("b.py")]
        dispatcher, _ = make_dispatcher(execute_plan=execute, max_concurrency=4)
        result = await dispatcher.dispatch(plans)
        assert result.resolved == 2
        # Both files started before either finished (barrier proves overlap)
        assert len(started) == 2

    @pytest.mark.asyncio
    async def test_dispatch_result_has_elapsed(self) -> None:
        dispatcher, _ = make_dispatcher()
        result = await dispatcher.dispatch([make_plan("a.py")])
        assert result.elapsed_s >= 0.0

    @pytest.mark.asyncio
    async def test_early_exit_defers_remaining_plans(self) -> None:
        """When resolved/total >= 0.5 after 15s, remaining plans are deferred."""
        plans = [make_plan(f"{i}.py") for i in range(4)]

        call_count = 0

        async def slow_execute(plan: FixPlan) -> FixResult:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return FixResult(success=True)
            # Remaining would block until early-exit fires
            await asyncio.sleep(10)
            return FixResult(success=True)

        dispatcher, _ = make_dispatcher(execute_plan=slow_execute, max_concurrency=1)
        dispatcher._EARLY_EXIT_ELAPSED_S = 0.05
        dispatcher._MONITOR_INTERVAL_S = 0.02
        result = await dispatcher.dispatch(plans)
        assert result.resolved >= 2
        # Some plans should be deferred due to early exit
        assert len(result.deferred) + result.resolved + result.failed == 4

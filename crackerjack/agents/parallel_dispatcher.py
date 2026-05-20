from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from crackerjack.agents.base import FixResult
from crackerjack.agents.issue_clusterer import IssueClusterer
from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import AgentDispatched, IssueFailed, IssueResolved
from crackerjack.executors.hook_lock_manager import FileEditLock
from crackerjack.models.fix_plan import FixPlan


@dataclass
class DispatchResult:
    results: list[FixResult] = field(default_factory=list)
    resolved: int = 0
    failed: int = 0
    deferred: list[FixPlan] = field(default_factory=list)
    elapsed_s: float = 0.0


class ParallelDispatcher:
    """Dispatch FixPlans concurrently at file-group granularity.

    Plans for the same file run sequentially (FileEditLock held); plans for
    different files run concurrently under a shared asyncio.Semaphore.
    """

    _DEFAULT_MAX_CONCURRENCY = min(8, os.cpu_count() or 4)
    _EARLY_EXIT_RATIO = 0.5
    _EARLY_EXIT_ELAPSED_S = 15.0
    _MONITOR_INTERVAL_S = 5.0

    def __init__(
        self,
        execute_plan: Callable[[FixPlan], Awaitable[FixResult]],
        bus: AIFixEventBus,
        run_id: str,
        iteration: int,
        max_concurrency: int | None = None,
    ) -> None:
        self._execute_plan = execute_plan
        self._bus = bus
        self._run_id = run_id
        self._iteration = iteration
        self._max_concurrency = (
            max_concurrency
            if max_concurrency is not None
            else self._DEFAULT_MAX_CONCURRENCY
        )

    async def dispatch(self, plans: list[FixPlan]) -> DispatchResult:
        if not plans:
            return DispatchResult()

        clusterer = IssueClusterer()
        groups = clusterer.cluster_plans(plans)

        total = len(plans)
        semaphore = asyncio.Semaphore(self._max_concurrency)
        early_exit = asyncio.Event()
        result = DispatchResult()
        start = time.monotonic()

        monitor = asyncio.get_running_loop().create_task(
            self._monitor_early_exit(result, total, start, early_exit)
        )

        tasks = [
            asyncio.get_running_loop().create_task(
                self._process_group(group, semaphore, early_exit, result)
            )
            for group in groups
        ]

        await asyncio.gather(*tasks, return_exceptions=True)
        monitor.cancel()
        try:
            await monitor
        except asyncio.CancelledError:
            pass

        result.elapsed_s = time.monotonic() - start
        return result

    async def _process_group(
        self,
        group: list[FixPlan],
        semaphore: asyncio.Semaphore,
        early_exit: asyncio.Event,
        result: DispatchResult,
    ) -> None:
        file_path = group[0].file_path if group else ""
        async with semaphore:
            async with FileEditLock(Path(file_path)):
                for plan in group:
                    if early_exit.is_set():
                        result.deferred.append(plan)
                        continue
                    await self._execute_one(plan, result)

    async def _execute_one(self, plan: FixPlan, result: DispatchResult) -> None:
        agent_label = plan.issue_type or "ai_fix_agent"
        file_label = plan.file_path
        t0 = time.monotonic()

        await self._bus.emit(
            AgentDispatched(
                run_id=self._run_id,
                iteration=self._iteration,
                agent=agent_label,
                action="fix",
                file=file_label,
            )
        )

        try:
            fix_result = await self._execute_plan(plan)
        except Exception as exc:
            await self._bus.emit(
                IssueFailed(
                    run_id=self._run_id,
                    iteration=self._iteration,
                    agent=agent_label,
                    file=file_label,
                    reason=str(exc),
                )
            )
            result.results.append(
                FixResult(success=False, confidence=0.0, remaining_issues=[str(exc)])
            )
            result.failed += 1
            return

        if fix_result.success:
            await self._bus.emit(
                IssueResolved(
                    run_id=self._run_id,
                    iteration=self._iteration,
                    agent=agent_label,
                    file=file_label,
                    duration_s=time.monotonic() - t0,
                )
            )
            result.resolved += 1
        else:
            reason = (
                "; ".join(fix_result.remaining_issues)
                if fix_result.remaining_issues
                else "fix failed"
            )
            await self._bus.emit(
                IssueFailed(
                    run_id=self._run_id,
                    iteration=self._iteration,
                    agent=agent_label,
                    file=file_label,
                    reason=reason,
                )
            )
            result.failed += 1

        result.results.append(fix_result)

    async def _monitor_early_exit(
        self,
        result: DispatchResult,
        total: int,
        start: float,
        early_exit: asyncio.Event,
    ) -> None:
        while True:
            await asyncio.sleep(self._MONITOR_INTERVAL_S)
            elapsed = time.monotonic() - start
            if total > 0 and elapsed >= self._EARLY_EXIT_ELAPSED_S:
                ratio = result.resolved / total
                if ratio >= self._EARLY_EXIT_RATIO:
                    early_exit.set()
                    return

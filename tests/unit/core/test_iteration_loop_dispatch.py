"""Unit tests for the V1/V2 iteration loop dispatcher (Tier-3 #11).

Tier-3 #11 deduplicates the V1 (sync) and V2 (async) iteration loops in
``crackerjack/core/autofix_coordinator.py`` by introducing a shared
``_run_iteration_loop_dispatch`` step-protocol. This test module verifies
the dispatcher protocol without re-testing the V1/V2 internals.

The contract under test:

* ``_run_iteration_loop_dispatch`` is an ``async def`` method that walks
  the iteration protocol (init, completion check, step call, progress
  update, finalization) and returns ``True`` on success, ``False`` on
  failure.
* It accepts an async ``step_fn`` callable returning a ``StepResult``
  with ``(success, fixes_applied, files_modified, failure_reason)``.
* It respects ``max_iterations`` via the ``AutoFixContext`` and emits
  the ``RunFinished`` event exactly once at graceful termination.
* V2's ``_run_v2_ai_fix_iteration_loop`` becomes a thin wrapper that
  builds the ``AutoFixContext`` and delegates to the dispatcher with its
  ``_v2_iteration_step``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.core.autofix_coordinator import AutofixCoordinator


@dataclass
class _FakeStepResult:
    """Lightweight stand-in for the dispatcher ``StepResult`` shape."""

    success: bool
    fixes_applied: int = 0
    files_modified: list[Path] = field(default_factory=list)
    failure_reason: str = ""


def _make_issues(count: int) -> list[Issue]:
    """Build ``count`` simple issues for iteration tests."""
    return [
        Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message=f"issue {i}",
            file_path=f"/tmp/example_{i}.py",
            line_number=1,
            stage="ruff",
        )
        for i in range(count)
    ]


def _make_ctx(coordinator: AutofixCoordinator, **overrides: object) -> object:
    """Build a minimal AutoFixContext for dispatcher tests."""
    from crackerjack.core.autofix_coordinator import AutoFixContext

    defaults: dict[str, object] = {
        "iteration": 0,
        "initial_issue_count": 0,
        "current_issues": _make_issues(0),
        "previous_issues": [],
        "previous_files_modified": [],
        "previous_hook_statuses": {},
        "previous_fixes_applied": 0,
        "stage": "fast",
        "max_iterations": coordinator._max_iterations or 5,
        "coordinator_set": {},
    }
    defaults.update(overrides)
    return AutoFixContext(**defaults)  # type: ignore[arg-type]


class TestIterationLoopDispatcherExists:
    """Pin the dispatcher surface so a refactor cannot silently remove it."""

    def test_dispatch_method_is_async(self) -> None:
        """``_run_iteration_loop_dispatch`` must be an async coroutine function."""
        import inspect

        assert hasattr(AutofixCoordinator, "_run_iteration_loop_dispatch"), (
            "Expected `_run_iteration_loop_dispatch` on AutofixCoordinator — "
            "Tier-3 #11 requires a shared dispatcher."
        )
        dispatch = getattr(AutofixCoordinator, "_run_iteration_loop_dispatch")
        assert inspect.iscoroutinefunction(dispatch), (
            "_run_iteration_loop_dispatch must be `async def` (per plan)."
        )

    def test_step_result_type_exists(self) -> None:
        """``StepResult`` must be importable from the module."""
        from crackerjack.core import autofix_coordinator as mod

        assert hasattr(mod, "StepResult"), (
            "StepResult dataclass must be exported for dispatcher protocol."
        )

    def test_auto_fix_context_type_exists(self) -> None:
        """``AutoFixContext`` must be importable from the module."""
        from crackerjack.core import autofix_coordinator as mod

        assert hasattr(mod, "AutoFixContext"), (
            "AutoFixContext dataclass must exist for dispatcher protocol."
        )


class TestIterationLoopDispatcherBehavior:
    """Verify the dispatcher honours the iteration protocol."""

    @pytest.mark.asyncio
    async def test_dispatcher_stops_at_max_iterations(self) -> None:
        """When completion returns False on the Nth call, dispatcher bails."""
        coordinator = AutofixCoordinator()
        coordinator._max_iterations = 3

        step_call_count = 0

        async def stub_step(ctx: object) -> _FakeStepResult:
            nonlocal step_call_count
            step_call_count += 1
            return _FakeStepResult(success=True, fixes_applied=1)

        # Three None returns (keep looping), then False (bail).
        completion_side_effects = [None, None, False]

        event_bus = MagicMock()
        event_bus.emit = AsyncMock()
        event_bus.emit_nowait = MagicMock()

        with (
            patch.object(
                coordinator,
                "_get_iteration_issues_with_log",
                return_value=(_make_issues(3), {}),
            ),
            patch.object(
                coordinator,
                "_check_iteration_completion",
                side_effect=completion_side_effects,
            ),
            patch.object(coordinator, "_event_bus", event_bus),
            patch.object(coordinator, "progress_manager") as pm,
        ):
            ctx = _make_ctx(
                coordinator,
                current_issues=_make_issues(3),
                initial_issue_count=3,
                max_iterations=coordinator._max_iterations,
            )
            result = await coordinator._run_iteration_loop_dispatch(
                ctx=ctx,
                step_fn=stub_step,
            )

        assert result is False
        # step_fn is called twice (None, None), then completion returns False.
        assert step_call_count == 2
        # Finalization must have run.
        pm.end_iteration.assert_called()
        pm.finish_session.assert_called()

    @pytest.mark.asyncio
    async def test_dispatcher_returns_false_when_step_fails(self) -> None:
        """When step_fn returns success=False, dispatcher finalizes and returns False."""
        coordinator = AutofixCoordinator()
        coordinator._max_iterations = 5

        call_count = 0

        async def stub_step(ctx: object) -> _FakeStepResult:
            nonlocal call_count
            call_count += 1
            return _FakeStepResult(success=False, fixes_applied=0)

        event_bus = MagicMock()
        event_bus.emit = AsyncMock()
        event_bus.emit_nowait = MagicMock()

        with (
            patch.object(
                coordinator,
                "_check_iteration_completion",
                side_effect=[None, True],
            ),
            patch.object(coordinator, "_event_bus", event_bus),
            patch.object(coordinator, "progress_manager") as pm,
        ):
            ctx = _make_ctx(coordinator, current_issues=_make_issues(5))
            result = await coordinator._run_iteration_loop_dispatch(
                ctx=ctx,
                step_fn=stub_step,
            )

        assert result is False
        assert call_count == 1
        pm.finish_session.assert_called()

    @pytest.mark.asyncio
    async def test_dispatcher_emits_run_finished_once(self) -> None:
        """RunFinished must be emitted exactly once on graceful termination."""
        coordinator = AutofixCoordinator()
        coordinator._max_iterations = 2

        call_count = 0

        async def stub_step(ctx: object) -> _FakeStepResult:
            nonlocal call_count
            call_count += 1
            ctx.current_issues = _make_issues(2)
            return _FakeStepResult(success=True, fixes_applied=1)

        event_bus = MagicMock()
        event_bus.emit = AsyncMock()
        emit_calls: list[tuple[object, ...]] = []
        event_bus.emit.side_effect = lambda event: emit_calls.append((event,))

        with (
            patch.object(
                coordinator,
                "_check_iteration_completion",
                side_effect=[None, True],
            ),
            patch.object(coordinator, "_event_bus", event_bus),
            patch.object(coordinator, "progress_manager"),
        ):
            ctx = _make_ctx(
                coordinator,
                current_issues=_make_issues(3),
                initial_issue_count=3,
            )
            await coordinator._run_iteration_loop_dispatch(
                ctx=ctx,
                step_fn=stub_step,
            )

        # At least one RunFinished event must have been emitted.
        run_finished_emits = [
            c for c in emit_calls if c and c[0].__class__.__name__ == "RunFinished"
        ]
        assert len(run_finished_emits) == 1, (
            f"Expected exactly one RunFinished emit, got {len(run_finished_emits)}"
        )


class TestV2UsesDispatcher:
    """V2 must delegate iteration loop body to the dispatcher."""

    @pytest.mark.asyncio
    async def test_v2_loop_calls_dispatcher(self) -> None:
        """``_run_v2_ai_fix_iteration_loop`` should drive the dispatcher."""
        coordinator = AutofixCoordinator()
        coordinator._max_iterations = 3

        dispatcher_spy = AsyncMock(return_value=True)

        with (
            patch.object(
                coordinator,
                "_run_iteration_loop_dispatch",
                dispatcher_spy,
            ),
            patch.object(
                coordinator,
                "_check_iteration_completion",
                return_value=True,
            ),
            patch.object(coordinator, "_event_bus"),
            patch.object(coordinator, "progress_manager"),
            patch.object(
                coordinator,
                "_create_fix_plans",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch.object(
                coordinator,
                "_execute_plans_with_validation",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await coordinator._run_v2_ai_fix_iteration_loop(
                analysis_coordinator=MagicMock(),
                fixer_coordinator=MagicMock(),
                validation_coordinator=MagicMock(),
                initial_issues=_make_issues(3),
                hook_results=[],
                stage="fast",
            )

        assert result is True
        assert dispatcher_spy.await_count == 1
        # The dispatcher must receive a step_fn kwarg.
        call_kwargs = dispatcher_spy.call_args.kwargs
        assert "step_fn" in call_kwargs


class TestV2StepFnShape:
    """The V2 step_fn returned by ``_v2_iteration_step`` must conform."""

    @pytest.mark.asyncio
    async def test_v2_step_fn_returns_step_result(self) -> None:
        """``_v2_iteration_step`` must return a StepResult-like object."""
        from crackerjack.core.autofix_coordinator import StepResult

        coordinator = AutofixCoordinator()

        with (
            patch.object(
                coordinator,
                "_create_fix_plans",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            result = await coordinator._v2_iteration_step(
                ctx=MagicMock(),
                analysis_coordinator=MagicMock(),
                fixer_coordinator=MagicMock(),
                validation_coordinator=MagicMock(),
            )

        assert isinstance(result, StepResult)
        assert hasattr(result, "success")
        assert hasattr(result, "fixes_applied")
        assert hasattr(result, "files_modified")

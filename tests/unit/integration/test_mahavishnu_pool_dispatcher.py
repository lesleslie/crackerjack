from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.agents.parallel_dispatcher import DispatchResult, ParallelDispatcher
from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import AgentDispatched, IssueFailed, IssueResolved
from crackerjack.executors.hook_lock_manager import FileEditLock
from crackerjack.integration.mahavishnu_pool_dispatcher import (
    MahavishnuPoolDispatcher,
    ParallelismConfig,
    _parse_pool_response,
    _plan_to_prompt,
    choose_dispatcher,
)
from crackerjack.models.fix_plan import FixPlan


RUN_ID = "2026-01-01-0000-test"


# ─── helpers ─────────────────────────────────────────────────────────────────


def make_plan(file_path: str = "a.py", issue_type: str = "type_error", line: int = 1) -> FixPlan:
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


def make_pool_dispatcher(
    execute_plan=None,
    config: ParallelismConfig | None = None,
) -> tuple[MahavishnuPoolDispatcher, CaptureSink]:
    bus = AIFixEventBus()
    sink = CaptureSink()
    bus.subscribe(sink)
    if execute_plan is None:
        execute_plan = AsyncMock(return_value=FixResult(success=True, confidence=0.9))
    dispatcher = MahavishnuPoolDispatcher(
        execute_plan_local=execute_plan,
        bus=bus,
        run_id=RUN_ID,
        iteration=0,
        config=config or ParallelismConfig(),
    )
    return dispatcher, sink


# ─── ParallelismConfig ────────────────────────────────────────────────────────


class TestParallelismConfig:
    def test_defaults(self) -> None:
        cfg = ParallelismConfig()
        assert cfg.strategy == "local"
        assert cfg.pool_threshold_issues == 12
        assert cfg.pool_url == "http://localhost:8680/mcp"
        assert cfg.pool_selector == "least_loaded"

    def test_frozen(self) -> None:
        from pydantic import ValidationError
        with pytest.raises((ValidationError, TypeError)):
            cfg = ParallelismConfig()
            cfg.strategy = "auto"  # type: ignore[misc]

    def test_custom_strategy(self) -> None:
        cfg = ParallelismConfig(strategy="mahavishnu_pool", pool_threshold_issues=5)
        assert cfg.strategy == "mahavishnu_pool"
        assert cfg.pool_threshold_issues == 5


# ─── helpers unit tests ───────────────────────────────────────────────────────


class TestPlanToPrompt:
    def test_includes_file_and_type(self) -> None:
        plan = make_plan("core/app.py", "security")
        prompt = _plan_to_prompt(plan)
        assert "core/app.py" in prompt
        assert "security" in prompt

    def test_includes_line_range(self) -> None:
        plan = make_plan(line=42)
        prompt = _plan_to_prompt(plan)
        assert "42" in prompt

    def test_no_changes_no_crash(self) -> None:
        plan = make_plan()
        plan.changes = []
        prompt = _plan_to_prompt(plan)
        assert "crackerjack:fix_plan" in prompt


class TestParsePoolResponse:
    def test_dict_success(self) -> None:
        result = _parse_pool_response({"success": True, "confidence": 0.8, "fixes_applied": ["fix1"]})
        assert result.success is True
        assert result.confidence == 0.8
        assert "fix1" in result.fixes_applied

    def test_dict_failure_with_reason(self) -> None:
        result = _parse_pool_response({"success": False, "remaining_issues": ["type mismatch"]})
        assert result.success is False
        assert "type mismatch" in result.remaining_issues

    def test_mcp_content_response(self) -> None:
        import json
        content_item = MagicMock()
        content_item.text = json.dumps({"success": True, "confidence": 0.95})
        response = MagicMock()
        response.content = [content_item]
        result = _parse_pool_response(response)
        assert result.success is True
        assert result.confidence == 0.95

    def test_malformed_response_returns_failure(self) -> None:
        result = _parse_pool_response("not_json_or_dict")
        assert result.success is False
        assert result.remaining_issues

    def test_empty_dict_returns_failure(self) -> None:
        result = _parse_pool_response({})
        assert result.success is False


# ─── MahavishnuPoolDispatcher fallback ────────────────────────────────────────


class TestMahavishnuPoolDispatcherFallback:
    def teardown_method(self) -> None:
        FileEditLock.clear_registry()

    @pytest.mark.asyncio
    async def test_falls_back_to_local_when_connect_fails(self) -> None:
        dispatcher, sink = make_pool_dispatcher()
        with patch.object(dispatcher, "_try_connect", return_value=None):
            result = await dispatcher.dispatch([make_plan("x.py")])
        # local fallback ran, so we should get a resolved result
        assert result.resolved == 1

    @pytest.mark.asyncio
    async def test_empty_plans_returns_empty(self) -> None:
        dispatcher, _ = make_pool_dispatcher()
        result = await dispatcher.dispatch([])
        assert result.results == []
        assert result.resolved == 0

    @pytest.mark.asyncio
    async def test_pool_timeout_falls_back_to_local(self) -> None:
        async def slow_pool(plan: FixPlan, client: object) -> FixResult:
            import asyncio
            await asyncio.sleep(10)
            return FixResult(success=True)

        dispatcher, _ = make_pool_dispatcher()
        fake_client = MagicMock()
        with patch.object(dispatcher, "_try_connect", return_value=fake_client):
            with patch.object(dispatcher, "_call_pool", side_effect=slow_pool):
                result = await dispatcher.dispatch([make_plan("t.py")])
        # should have fallen back
        assert result.resolved + result.failed == 1

    @pytest.mark.asyncio
    async def test_pool_exception_falls_back_to_local(self) -> None:
        execute = AsyncMock(return_value=FixResult(success=True))
        dispatcher, _ = make_pool_dispatcher(execute_plan=execute)
        fake_client = MagicMock()
        with patch.object(dispatcher, "_try_connect", return_value=fake_client):
            with patch.object(dispatcher, "_call_pool", side_effect=RuntimeError("pool boom")):
                result = await dispatcher.dispatch([make_plan("f.py")])
        assert result.resolved == 1  # local fallback succeeded

    @pytest.mark.asyncio
    async def test_emits_agent_dispatched_event(self) -> None:
        dispatcher, sink = make_pool_dispatcher()
        with patch.object(dispatcher, "_try_connect", return_value=None):
            await dispatcher.dispatch([make_plan("ev.py", "security")])
        dispatched = [e for e in sink.received if isinstance(e, AgentDispatched)]
        assert any(e.file == "ev.py" for e in dispatched)

    @pytest.mark.asyncio
    async def test_emits_issue_resolved_on_success(self) -> None:
        dispatcher, sink = make_pool_dispatcher()
        with patch.object(dispatcher, "_try_connect", return_value=None):
            await dispatcher.dispatch([make_plan("ok.py")])
        resolved = [e for e in sink.received if isinstance(e, IssueResolved)]
        assert len(resolved) == 1

    @pytest.mark.asyncio
    async def test_emits_issue_failed_on_failure(self) -> None:
        execute = AsyncMock(return_value=FixResult(success=False, remaining_issues=["oops"]))
        dispatcher, sink = make_pool_dispatcher(execute_plan=execute)
        with patch.object(dispatcher, "_try_connect", return_value=None):
            await dispatcher.dispatch([make_plan("bad.py")])
        failed = [e for e in sink.received if isinstance(e, IssueFailed)]
        assert len(failed) == 1


# ─── choose_dispatcher ────────────────────────────────────────────────────────


class TestChooseDispatcher:
    def _make_bus_and_execute(self):
        bus = AIFixEventBus()
        execute = AsyncMock(return_value=FixResult(success=True))
        return bus, execute

    def test_local_strategy_returns_parallel_dispatcher(self) -> None:
        bus, execute = self._make_bus_and_execute()
        plans = [make_plan()]
        cfg = ParallelismConfig(strategy="local")
        d = choose_dispatcher(plans, execute, bus, RUN_ID, 0, cfg)
        assert isinstance(d, ParallelDispatcher)

    def test_mahavishnu_pool_strategy_returns_pool_dispatcher(self) -> None:
        bus, execute = self._make_bus_and_execute()
        plans = [make_plan()]
        cfg = ParallelismConfig(strategy="mahavishnu_pool")
        d = choose_dispatcher(plans, execute, bus, RUN_ID, 0, cfg)
        assert isinstance(d, MahavishnuPoolDispatcher)

    def test_auto_below_threshold_returns_local(self) -> None:
        bus, execute = self._make_bus_and_execute()
        plans = [make_plan() for _ in range(3)]
        cfg = ParallelismConfig(strategy="auto", pool_threshold_issues=12)
        d = choose_dispatcher(plans, execute, bus, RUN_ID, 0, cfg)
        assert isinstance(d, ParallelDispatcher)

    def test_auto_above_threshold_returns_pool(self) -> None:
        bus, execute = self._make_bus_and_execute()
        plans = [make_plan(f"{i}.py") for i in range(15)]
        cfg = ParallelismConfig(strategy="auto", pool_threshold_issues=12)
        d = choose_dispatcher(plans, execute, bus, RUN_ID, 0, cfg)
        assert isinstance(d, MahavishnuPoolDispatcher)

    def test_auto_exactly_at_threshold_returns_pool(self) -> None:
        bus, execute = self._make_bus_and_execute()
        plans = [make_plan(f"{i}.py") for i in range(12)]
        cfg = ParallelismConfig(strategy="auto", pool_threshold_issues=12)
        d = choose_dispatcher(plans, execute, bus, RUN_ID, 0, cfg)
        assert isinstance(d, MahavishnuPoolDispatcher)

    def test_default_config_uses_local(self) -> None:
        bus, execute = self._make_bus_and_execute()
        plans = [make_plan()]
        d = choose_dispatcher(plans, execute, bus, RUN_ID, 0)
        assert isinstance(d, ParallelDispatcher)

    def test_max_concurrency_passed_to_local(self) -> None:
        bus, execute = self._make_bus_and_execute()
        plans = [make_plan()]
        cfg = ParallelismConfig(strategy="local", max_concurrency=3)
        d = choose_dispatcher(plans, execute, bus, RUN_ID, 0, cfg)
        assert isinstance(d, ParallelDispatcher)
        assert d._max_concurrency == 3

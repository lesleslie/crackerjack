from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from pydantic import BaseModel

from crackerjack.agents.base import FixResult
from crackerjack.agents.issue_clusterer import IssueClusterer
from crackerjack.agents.parallel_dispatcher import DispatchResult, ParallelDispatcher
from crackerjack.core.ai_fix_event_bus import AIFixEventBus
from crackerjack.core.ai_fix_events import AgentDispatched, IssueFailed, IssueResolved
from crackerjack.models.fix_plan import FixPlan

logger = logging.getLogger(__name__)

_POOL_TIMEOUT_S = 5.0  # per spec §9: all Bodai component calls use 5s timeout


class ParallelismConfig(BaseModel):
    """Configuration for the parallel/pool dispatch strategy."""

    strategy: str = "local"  # local | mahavishnu_pool | auto
    max_concurrency: int = min(8, os.cpu_count() or 4)
    pool_threshold_issues: int = 12
    pool_threshold_seconds: float = 30.0
    pool_url: str = "http://localhost:8680/mcp"
    pool_selector: str = "least_loaded"
    model_config = {"frozen": True}


class MahavishnuPoolDispatcher:
    """Routes FixPlans to a Mahavishnu pool worker for remote LLM execution.

    Falls back to ParallelDispatcher (local) on any connection failure, timeout,
    or unavailability — preserving Crackerjack's standalone-works invariant.
    """

    def __init__(
        self,
        execute_plan_local: Callable[[FixPlan], Awaitable[FixResult]],
        bus: AIFixEventBus,
        run_id: str,
        iteration: int,
        config: ParallelismConfig | None = None,
    ) -> None:
        self._execute_plan_local = execute_plan_local
        self._bus = bus
        self._run_id = run_id
        self._iteration = iteration
        self._config = config or ParallelismConfig()
        self._local_fallback = ParallelDispatcher(
            execute_plan=execute_plan_local,
            bus=bus,
            run_id=run_id,
            iteration=iteration,
            max_concurrency=self._config.max_concurrency,
        )

    async def dispatch(self, plans: list[FixPlan]) -> DispatchResult:
        if not plans:
            return DispatchResult()

        client = await self._try_connect()
        if client is None:
            logger.warning(
                "Mahavishnu pool unavailable — falling back to local parallel dispatch"
            )
            return await self._local_fallback.dispatch(plans)

        clusterer = IssueClusterer()
        groups = clusterer.cluster_plans(plans)
        result = DispatchResult()
        start = time.monotonic()

        await asyncio.gather(
            *[self._dispatch_group(group, client, result) for group in groups],
            return_exceptions=True,
        )
        result.elapsed_s = time.monotonic() - start
        await self._close_client(client)
        return result

    # ── per-group / per-plan ──────────────────────────────────────────────────

    async def _dispatch_group(
        self,
        group: list[FixPlan],
        client: Any,
        result: DispatchResult,
    ) -> None:
        for plan in group:
            await self._dispatch_one(plan, client, result)

    async def _dispatch_one(
        self,
        plan: FixPlan,
        client: Any,
        result: DispatchResult,
    ) -> None:
        agent_label = plan.issue_type or "ai_fix_agent"
        file_label = plan.file_path or ""
        t0 = time.monotonic()

        await self._bus.emit(
            AgentDispatched(
                run_id=self._run_id,
                iteration=self._iteration,
                agent=agent_label,
                action="fix_via_pool",
                file=file_label,
            )
        )

        fix_result = await self._execute_via_pool_or_local(plan, client, agent_label, file_label)

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

    async def _execute_via_pool_or_local(
        self,
        plan: FixPlan,
        client: Any,
        agent_label: str,
        file_label: str,
    ) -> FixResult:
        try:
            return await asyncio.wait_for(
                self._call_pool(plan, client),
                timeout=_POOL_TIMEOUT_S,
            )
        except Exception as exc:
            logger.debug(f"Pool execution for {file_label} failed ({exc}); running locally")
        try:
            return await self._execute_plan_local(plan)
        except Exception as exc:
            return FixResult(success=False, confidence=0.0, remaining_issues=[str(exc)])

    # ── pool transport ────────────────────────────────────────────────────────

    async def _try_connect(self) -> Any | None:
        try:
            try:
                from mcp import ClientSession
                from mcp.client.streamablehttp import streamablehttp_client

                transport = streamablehttp_client(url=self._config.pool_url)
                session: Any = ClientSession(transport)  # type: ignore[arg-type]
                await asyncio.wait_for(
                    session.__aenter__(), timeout=_POOL_TIMEOUT_S
                )
                return session
            except ImportError:
                import httpx

                return httpx.AsyncClient(
                    base_url=self._config.pool_url,
                    timeout=_POOL_TIMEOUT_S,
                )
        except Exception as exc:
            logger.debug(f"Mahavishnu pool connect failed: {exc}")
            return None

    async def _call_pool(self, plan: FixPlan, client: Any) -> FixResult:
        prompt = _plan_to_prompt(plan)
        try:
            from mcp import ClientSession

            if isinstance(client, ClientSession):
                response = await client.call_tool(
                    "pool_route_execute",
                    {"prompt": prompt, "selector": self._config.pool_selector},
                )
                return _parse_pool_response(response)
        except ImportError:
            pass

        import httpx

        if isinstance(client, httpx.AsyncClient):
            resp = await client.post(
                "/tools/pool_route_execute",
                json={"prompt": prompt, "selector": self._config.pool_selector},
            )
            resp.raise_for_status()
            return _parse_pool_response(resp.json())

        raise RuntimeError(f"Unsupported pool client type: {type(client)!r}")

    @staticmethod
    async def _close_client(client: Any) -> None:
        with suppress(Exception):
            if hasattr(client, "__aexit__"):
                await client.__aexit__(None, None, None)
            elif hasattr(client, "aclose"):
                await client.aclose()


# ── helpers ───────────────────────────────────────────────────────────────────


def _plan_to_prompt(plan: FixPlan) -> str:
    changes_summary = "; ".join(
        f"line {c.line_range[0]}-{c.line_range[1]}" for c in (plan.changes or [])[:3]
    )
    return (
        f"crackerjack:fix_plan|file={plan.file_path}|type={plan.issue_type}"
        + (f"|changes={changes_summary}" if changes_summary else "")
    )


def _parse_pool_response(response: Any) -> FixResult:
    try:
        if hasattr(response, "content") and response.content:
            data = json.loads(response.content[0].text)
        elif isinstance(response, dict):
            data = response
        else:
            return FixResult(
                success=False,
                remaining_issues=[f"Unrecognised pool response type: {type(response).__name__}"],
            )
        return FixResult(
            success=data.get("success", False),
            confidence=float(data.get("confidence", 0.0)),
            fixes_applied=list(data.get("fixes_applied", [])),
            remaining_issues=list(data.get("remaining_issues", [])),
        )
    except Exception:
        return FixResult(success=False, remaining_issues=["Failed to parse pool response"])


# ── dispatcher selection ──────────────────────────────────────────────────────


def choose_dispatcher(
    plans: list[FixPlan],
    execute_plan: Callable[[FixPlan], Awaitable[FixResult]],
    bus: AIFixEventBus,
    run_id: str,
    iteration: int,
    config: ParallelismConfig | None = None,
) -> ParallelDispatcher | MahavishnuPoolDispatcher:
    """Return the appropriate dispatcher based on config and issue volume."""
    cfg = config or ParallelismConfig()

    if cfg.strategy == "local":
        return ParallelDispatcher(
            execute_plan=execute_plan,
            bus=bus,
            run_id=run_id,
            iteration=iteration,
            max_concurrency=cfg.max_concurrency,
        )

    if cfg.strategy == "mahavishnu_pool":
        return MahavishnuPoolDispatcher(
            execute_plan_local=execute_plan,
            bus=bus,
            run_id=run_id,
            iteration=iteration,
            config=cfg,
        )

    # auto: volume-based threshold
    if len(plans) >= cfg.pool_threshold_issues:
        return MahavishnuPoolDispatcher(
            execute_plan_local=execute_plan,
            bus=bus,
            run_id=run_id,
            iteration=iteration,
            config=cfg,
        )

    return ParallelDispatcher(
        execute_plan=execute_plan,
        bus=bus,
        run_id=run_id,
        iteration=iteration,
        max_concurrency=cfg.max_concurrency,
    )

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from crackerjack.models.session_metrics import SessionMetrics


logger = logging.getLogger(__name__)


@dataclass
class MCPClientConfig:
    server_url: str = "http://localhost: 8678"
    timeout_seconds: int = 5
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    health_check_interval: int = 30
    enable_fallback: bool = True


@dataclass
class SessionBuddyMCPClient:
    config: MCPClientConfig = field(default_factory=MCPClientConfig)
    session_id: str = "default"
    _client: Any | None = field(init=False, default=None)
    _is_connected: bool = field(init=False, default=False)
    _fallback_tracker: Any | None = field(init=False, default=None)
    _last_health_check: float = field(init=False, default=0)

    def __post_init__(self) -> None:
        if self.config.enable_fallback:
            self._initialize_fallback()

    async def connect(self) -> bool:
        try:
            # TODO: Replace with actual MCP client initialization

            logger.info(
                f"Connecting to session-buddy MCP server at {self.config.server_url}"
            )

            self._is_connected = True
            self._last_health_check = asyncio.get_event_loop().time()

            logger.info("✅ Connected to session-buddy MCP server")
            return True

        except Exception as e:
            logger.warning(f"Failed to connect to MCP server: {e}")
            self._is_connected = False
            return False

    async def disconnect(self) -> None:
        if self._client:
            try:
                # TODO: Call actual MCP disconnect
                pass
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")

        self._is_connected = False
        self._client = None

    def _initialize_fallback(self) -> None:
        try:
            from crackerjack.integration.skills_tracking import (
                SessionBuddyDirectTracker,
            )

            self._fallback_tracker = SessionBuddyDirectTracker(
                session_id=self.session_id,
            )

            logger.info("✅ Fallback direct tracker initialized")

        except Exception as e:
            logger.warning(f"Failed to initialize fallback tracker: {e}")
            self._fallback_tracker = None

    async def _ensure_connection(self) -> bool:
        current_time = asyncio.get_event_loop().time()

        if (
            self._is_connected
            and (current_time - self._last_health_check)
            < self.config.health_check_interval
        ):
            return True

        is_healthy = await self._health_check()

        if not is_healthy:
            logger.info("MCP server unhealthy, attempting reconnection...")
            return await self.connect()

        return True

    async def _health_check(self) -> bool:
        try:
            # TODO: Implement actual MCP health check

            return self._is_connected

        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        for attempt in range(self.config.max_retries):
            try:
                if not await self._ensure_connection():
                    raise RuntimeError("Not connected to MCP server")

                # TODO: Implement actual MCP tool call

                await asyncio.sleep(0.1)
                return {"status": "success", "data": None}

            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    wait_time = self.config.retry_delay_seconds * (2**attempt)
                    logger.warning(
                        f"Tool call failed (attempt {attempt + 1}/{self.config.max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"Tool call failed after {self.config.max_retries} attempts: {e}"
                    )
                    raise

    async def track_invocation(
        self,
        skill_name: str,
        user_query: str | None = None,
        alternatives_considered: list[str] | None = None,
        selection_rank: int | None = None,
        workflow_phase: str | None = None,
    ) -> Callable[..., Any] | None:

        try:
            if await self._ensure_connection():
                await self._call_tool(
                    "track_invocation",
                    {
                        "session_id": self.session_id,
                        "skill_name": skill_name,
                        "user_query": user_query,
                        "alternatives_considered": alternatives_considered or [],
                        "selection_rank": selection_rank,
                        "workflow_phase": workflow_phase,
                    },
                )

                async def completer(
                    *,
                    completed: bool = True,
                    follow_up_actions: list[str] | None = None,
                    error_type: str | None = None,
                ) -> None:
                    try:
                        await self._call_tool(
                            "complete_invocation",
                            {
                                "session_id": self.session_id,
                                "skill_name": skill_name,
                                "completed": completed,
                                "follow_up_actions": follow_up_actions or [],
                                "error_type": error_type,
                            },
                        )
                        logger.debug(
                            f"Skills tracking (MCP): {skill_name} - "
                            f"completed={completed}, phase={workflow_phase}"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to complete tracking via MCP: {e}")

                return completer

        except Exception as e:
            logger.warning(f"MCP tracking failed, using fallback: {e}")

        if self._fallback_tracker:
            logger.debug("Using fallback direct tracker")
            completer = self._fallback_tracker.track_invocation(
                skill_name=skill_name,
                user_query=user_query,
                alternatives_considered=alternatives_considered,
                selection_rank=selection_rank,
                workflow_phase=workflow_phase,
            )

            async def async_completer(
                *,
                completed: bool = True,
                follow_up_actions: list[str] | None = None,
                error_type: str | None = None,
            ) -> None:
                if completer:
                    await completer(  # type: ignore[misc]
                        completed=completed,
                        follow_up_actions=follow_up_actions,
                        error_type=error_type,
                    )

            return async_completer

        return None

    async def get_recommendations(
        self,
        user_query: str,
        limit: int = 5,
        workflow_phase: str | None = None,
    ) -> list[dict[str, Any]]:

        try:
            if await self._ensure_connection():
                result = await self._call_tool(
                    "recommend_skills",
                    {
                        "session_id": self.session_id,
                        "user_query": user_query,
                        "limit": limit,
                        "workflow_phase": workflow_phase,
                    },
                )

                # TODO: Parse actual MCP result
                recommendations = result.get("recommendations", [])
                logger.debug(f"Got {len(recommendations)} recommendations via MCP")
                return recommendations

        except Exception as e:
            logger.warning(f"MCP recommendations failed, using fallback: {e}")

        if self._fallback_tracker:
            logger.debug("Using fallback direct tracker for recommendations")
            return self._fallback_tracker.get_recommendations(
                user_query=user_query,
                limit=limit,
                workflow_phase=workflow_phase,
            )

        return []

    async def record_git_metrics(self, metrics: SessionMetrics) -> None:
        try:
            if await self._ensure_connection():
                await self._call_tool(
                    "record_git_metrics",
                    {
                        "session_id": self.session_id,
                        "metrics": {
                            "commit_velocity": metrics.git_commit_velocity,
                            "branch_count": metrics.git_branch_count,
                            "merge_success_rate": metrics.git_merge_success_rate,
                            "conventional_compliance": (
                                metrics.conventional_commit_compliance
                            ),
                            "workflow_efficiency": metrics.git_workflow_efficiency_score,
                        },
                    },
                )
                logger.debug(
                    f"Git metrics recorded via MCP for session {self.session_id}"
                )
                return

        except Exception as e:
            logger.warning(f"MCP git metrics recording failed: {e}")

        if self._fallback_tracker:
            logger.debug("Using fallback direct tracker for git metrics")
            try:
                await self._fallback_tracker.record_git_metrics(metrics)
            except Exception as e:
                logger.warning(f"Fallback git metrics recording failed: {e}")

    async def get_workflow_recommendations(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        try:
            if await self._ensure_connection():
                result = await self._call_tool(
                    "get_workflow_recommendations",
                    {
                        "session_id": session_id,
                    },
                )

                recommendations = result.get("recommendations", [])
                logger.debug(
                    f"Got {len(recommendations)} workflow recommendations via MCP"
                )
                return recommendations

        except Exception as e:
            logger.warning(f"MCP workflow recommendations failed: {e}")

        return []

    def is_connected(self) -> bool:
        return self._is_connected

    def is_enabled(self) -> bool:
        return self._is_connected or self._fallback_tracker is not None

    def get_backend(self) -> str:
        if self._is_connected:
            return "mcp"
        elif self._fallback_tracker:
            return f"direct-fallback ({self._fallback_tracker.get_backend()})"

        return "none"


def create_mcp_client(
    session_id: str,
    config: MCPClientConfig | None = None,
) -> SessionBuddyMCPClient:
    client = SessionBuddyMCPClient(
        session_id=session_id,
        config=config or MCPClientConfig(),
    )

    return client

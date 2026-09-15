"""Async MCP client for Session-Buddy's MCP server.

Transport migrated to :class:`mcp_common.clients.CommonMCPClient` on
2026-09-14 (see
``mahavishnu/docs/plans/2026-09-14-common-mcp-client-transport-unification.md``).

Before the migration, this module shipped its own
``streamable_http_client`` lifecycle, a manual retry loop, an
httpx-based HTTP fallback, and a custom JSON-RPC content parser —
all of which :class:`CommonMCPClient` now provides natively. The
bespoke transport surface area was ~150 LOC.

What survives:
- :class:`MCPClientConfig` — shape preserved (including
  ``max_retries``/``retry_delay_seconds`` which are no-ops post-migration;
  callers passing them continue to work but the values are ignored).
- :class:`SessionBuddyMCPClient` public methods:
  ``track_invocation``, ``get_recommendations``,
  ``record_git_metrics``, ``get_workflow_recommendations``,
  ``connect``/``disconnect``, ``is_connected``, ``is_enabled``,
  ``get_backend``.
- :func:`create_mcp_client` factory.
- ``SessionBuddyDirectTracker`` fallback — orthogonal to the transport
  migration; still used when MCP is unavailable.

What's gone:
- ``_ensure_connection``, ``_health_check`` — periodic-recheck was tied
  to the bespoke session model and is no longer needed.
- ``_call_tool``, ``_call_mcp_session``, ``_call_http_endpoint``,
  ``_parse_mcp_content`` — replaced by direct delegation to
  ``CommonMCPClient.call_tool``.
- ``_should_retry``, ``_sleep_before_retry`` — SDK surfaces failures via
  typed exceptions; callers should branch on ``MCPClientError`` rather
  than retrying blindly.
- ``_connect_http_fallback`` — SDK handles all transport concerns.
"""

from __future__ import annotations

import json
import logging
import typing as t
from dataclasses import dataclass, field

if t.TYPE_CHECKING:
    from collections.abc import Callable

    from crackerjack.models.session_metrics import SessionMetrics


logger = logging.getLogger(__name__)


@dataclass
class MCPClientConfig:
    server_url: str = "http://localhost:8678"
    timeout_seconds: int = 5
    max_retries: int = 3  # Deprecated: SDK surfaces typed errors now; ignored.
    retry_delay_seconds: float = 1.0  # Deprecated: see ``max_retries``.
    health_check_interval: int = 30  # Deprecated: see ``_last_health_check`` docstring.
    enable_fallback: bool = True


def _extract_payload(result: t.Any) -> dict[str, t.Any] | None:
    """Unwrap an MCP tool-call result to a dict (or None).

    Handles the two wire shapes the upstream MCP SDK may return:
    1. Structured output: ``result.data`` is set to a dict.
    2. Plain text: ``result.content[0].text`` is JSON.
    """
    data = getattr(result, "data", None)
    if isinstance(data, dict):
        return data

    content = getattr(result, "content", None)
    if content:
        for item in content:
            text = getattr(item, "text", None)
            if text:
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return None
                if isinstance(parsed, dict):
                    return parsed
                return None

    return None


@dataclass
class SessionBuddyMCPClient:
    config: MCPClientConfig = field(default_factory=MCPClientConfig)
    session_id: str = "default"
    _client: t.Any | None = field(init=False, default=None)
    _is_connected: bool = field(init=False, default=False)
    _fallback_tracker: t.Any | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if self.config.enable_fallback:
            self._initialize_fallback()

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

    def _mcp_url(self) -> str:
        base = self.config.server_url.rstrip("/")
        return base if base.endswith("/mcp") else f"{base}/mcp"

    async def connect(self) -> bool:
        """Open the MCP session via :class:`CommonMCPClient`.

        Returns True on success, False on any error or when MCP isn't
        reachable. Idempotent: calling connect when already connected
        is a no-op and returns True.
        """
        if self._is_connected and self._client is not None:
            return True

        await self._safe_close()

        from mcp_common.clients.common_mcp_client import CommonMCPClient

        try:
            client = CommonMCPClient(
                base_url=self._mcp_url(),
                timeout=float(self.config.timeout_seconds),
            )
            await client.__aenter__()
        except Exception as exc:
            logger.warning(
                f"SessionBuddyMCPClient.connect failed: {type(exc).__name__}: {exc!r}"
            )
            await self._safe_close()
            self._is_connected = False
            return False

        self._client = client
        self._is_connected = True
        logger.info(f"✅ Connected to session-buddy MCP server at {self.config.server_url}")
        return True

    async def _safe_close(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except RuntimeError as exc:
                if "different task" not in str(exc):
                    logger.debug(
                        f"SessionBuddyMCPClient: aclose runtime error: {exc!r}"
                    )
            except Exception as exc:
                logger.debug(
                    f"SessionBuddyMCPClient: aclose failed: {type(exc).__name__}: {exc!r}"
                )
            finally:
                self._client = None
        self._is_connected = False

    async def disconnect(self) -> None:
        await self._safe_close()

    async def _call_tool(
        self, tool_name: str, arguments: dict[str, t.Any]
    ) -> dict[str, t.Any] | None:
        """Delegate to :meth:`CommonMCPClient.call_tool` and unwrap the payload.

        Returns None if not connected, on transport failure, or when the
        SDK response carries no structured-data attribute.
        """
        if not self._is_connected or self._client is None:
            logger.debug(
                f"SessionBuddyMCPClient._call_tool({tool_name}): not connected"
            )
            return None
        try:
            result = await self._client.call_tool(
                tool_name, arguments=arguments, timeout=float(self.config.timeout_seconds)
            )
        except Exception as exc:
            logger.warning(
                f"SessionBuddyMCPClient._call_tool({tool_name}) failed: "
                f"{type(exc).__name__}: {exc!r}"
            )
            return None
        return _extract_payload(result)

    async def track_invocation(
        self,
        skill_name: str,
        user_query: str | None = None,
        alternatives_considered: list[str] | None = None,
        selection_rank: int | None = None,
        workflow_phase: str | None = None,
    ) -> Callable[..., t.Any] | None:

        if not await self.connect():
            logger.warning(
                "SessionBuddyMCPClient.track_invocation: connect() failed"
            )
        else:
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

            return completer

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
    ) -> list[dict[str, t.Any]]:

        if not await self.connect():
            logger.warning(
                "SessionBuddyMCPClient.get_recommendations: connect() failed"
            )
        else:
            result = await self._call_tool(
                "recommend_skills",
                {
                    "session_id": self.session_id,
                    "user_query": user_query,
                    "limit": limit,
                    "workflow_phase": workflow_phase,
                },
            )

            if isinstance(result, dict):
                recommendations = result.get("recommendations", [])
                if isinstance(recommendations, list):
                    logger.debug(
                        f"Got {len(recommendations)} recommendations via MCP"
                    )
                    return [r for r in recommendations if isinstance(r, dict)]
                logger.debug("MCP recommendations returned non-list 'recommendations'")

        if self._fallback_tracker:
            logger.debug("Using fallback direct tracker for recommendations")
            return self._fallback_tracker.get_recommendations(
                user_query=user_query,
                limit=limit,
                workflow_phase=workflow_phase,
            )

        return []

    async def record_git_metrics(self, metrics: "SessionMetrics") -> None:
        if not await self.connect():
            logger.warning(
                "SessionBuddyMCPClient.record_git_metrics: connect() failed"
            )
            if self._fallback_tracker:
                try:
                    await self._fallback_tracker.record_git_metrics(metrics)
                except Exception as exc:
                    logger.warning(
                        f"Fallback git metrics recording failed: {exc}"
                    )
            return

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

    async def get_workflow_recommendations(
        self,
        session_id: str,
    ) -> list[dict[str, t.Any]]:
        if not await self.connect():
            logger.warning(
                "SessionBuddyMCPClient.get_workflow_recommendations: connect() failed"
            )
            return []

        result = await self._call_tool(
            "get_workflow_recommendations",
            {"session_id": session_id},
        )

        if isinstance(result, dict):
            recommendations = result.get("recommendations", [])
            if isinstance(recommendations, list):
                logger.debug(
                    f"Got {len(recommendations)} workflow recommendations via MCP"
                )
                return [r for r in recommendations if isinstance(r, dict)]
            logger.debug("MCP workflow recommendations returned non-list 'recommendations'")
        return []

    def is_connected(self) -> bool:
        return self._is_connected

    def is_enabled(self) -> bool:
        return self._is_connected or self._fallback_tracker is not None

    def get_backend(self) -> str:
        if self._is_connected:
            return "mcp"
        if self._fallback_tracker:
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

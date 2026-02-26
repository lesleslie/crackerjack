from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable


logger = logging.getLogger(__name__)
_SESSION_BUDDY_WARNING_SHOWN = False


@runtime_checkable
class SkillsTrackerProtocol(Protocol):
    def track_invocation(
        self,
        skill_name: str,
        user_query: str | None = None,
        alternatives_considered: list[str] | None = None,
        selection_rank: int | None = None,
        workflow_phase: str | None = None,
    ) -> Callable[..., None] | None: ...

    def get_recommendations(
        self,
        user_query: str,
        limit: int = 5,
        workflow_phase: str | None = None,
    ) -> list[dict[str, object]]: ...

    def recommend_skills(
        self,
        user_query: str,
        limit: int = 5,
        session_id: str | None = None,
        workflow_phase: str | None = None,
    ) -> list[dict[str, object]]: ...

    def is_enabled(self) -> bool: ...

    def get_backend(self) -> str: ...


@dataclass
class NoOpSkillsTracker:
    backend_name: str = "none"

    def track_invocation(
        self,
        skill_name: str,
        user_query: str | None = None,
        alternatives_considered: list[str] | None = None,
        selection_rank: int | None = None,
        workflow_phase: str | None = None,
    ) -> Callable[..., None] | None:
        return None

    def get_recommendations(
        self,
        user_query: str,
        limit: int = 5,
        workflow_phase: str | None = None,
    ) -> list[dict[str, object]]:
        return []

    def is_enabled(self) -> bool:
        return False

    def get_backend(self) -> str:
        return self.backend_name


@dataclass
class SessionBuddyDirectTracker:
    session_id: str
    db_path: Path = field(
        default_factory=lambda: Path.cwd() / ".session-buddy" / "skills.db"
    )
    _skills_tracker: SkillsTrackerProtocol | None = field(init=False, default=None)
    backend_name: str = "session-buddy-direct"

    def __post_init__(self) -> None:
        self._initialize_tracker()

    def _initialize_tracker(self) -> None:
        global _SESSION_BUDDY_WARNING_SHOWN
        try:
            from crackerjack.integration.session_buddy_skills_compat import (
                get_session_tracker,
            )

            tracker = get_session_tracker(
                session_id=self.session_id,
                db_path=self.db_path,
            )
            self._skills_tracker = tracker  # type: ignore[assignment]

            logger.info(
                f"✅ Session-buddy skills tracking initialized (session={self.session_id})"
            )
        except ImportError as e:
            if not _SESSION_BUDDY_WARNING_SHOWN:
                logger.debug(
                    f"⚠️  Session-buddy skills tracking not available: {e}. Skills tracking disabled."
                )
                _SESSION_BUDDY_WARNING_SHOWN = True
            self._skills_tracker = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize skills tracker: {e}")
            self._skills_tracker = None

    def track_invocation(
        self,
        skill_name: str,
        user_query: str | None = None,
        alternatives_considered: list[str] | None = None,
        selection_rank: int | None = None,
        workflow_phase: str | None = None,
    ) -> Callable[..., None] | None:
        if self._skills_tracker is None:
            return None

        try:
            completer = self._skills_tracker.track_invocation(
                skill_name=skill_name,
                workflow_phase=workflow_phase,
                user_query=user_query,
                alternatives_considered=alternatives_considered,
                selection_rank=selection_rank,
            )

            def logged_completer(
                *,
                completed: bool = True,
                follow_up_actions: list[str] | None = None,
                error_type: str | None = None,
            ) -> None:
                logger.debug(
                    f"Skills tracking: {skill_name} - "
                    f"completed={completed}, phase={workflow_phase}"
                )

                completer(
                    completed=completed,
                    follow_up_actions=follow_up_actions,
                    error_type=error_type,
                )

            return logged_completer

        except Exception as e:
            logger.error(f"❌ Failed to track skill invocation: {e}")
            return None

    def get_recommendations(
        self,
        user_query: str,
        limit: int = 5,
        workflow_phase: str | None = None,
    ) -> list[dict[str, object]]:
        if self._skills_tracker is None:
            return []

        try:
            recommendations = self._skills_tracker.recommend_skills(
                user_query=user_query,
                limit=limit,
                session_id=self.session_id,
                workflow_phase=workflow_phase,
            )

            logger.debug(
                f"Got {len(recommendations)} skill recommendations for query: {user_query[:50]}..."
            )

            return recommendations

        except Exception as e:
            logger.error(f"❌ Failed to get recommendations: {e}")
            return []

    def is_enabled(self) -> bool:
        return self._skills_tracker is not None

    def get_backend(self) -> str:
        return self.backend_name


@dataclass
class SessionBuddyMCPTracker:
    session_id: str
    mcp_server_url: str = "http://localhost: 8678"
    timeout_seconds: int = 5
    _mcp_client: object | None = field(init=False, default=None)
    backend_name: str = "session-buddy-mcp"
    _fallback_tracker: SessionBuddyDirectTracker | None = field(
        init=False, default=None
    )

    def __post_init__(self) -> None:
        self._initialize_mcp_client()

    def _initialize_mcp_client(self) -> None:
        try:
            from crackerjack.integration.session_buddy_mcp import (
                MCPClientConfig,
                create_mcp_client,
            )

            config = MCPClientConfig(
                server_url=self.mcp_server_url,
                timeout_seconds=self.timeout_seconds,
                enable_fallback=True,
            )

            self._mcp_client = create_mcp_client(
                session_id=self.session_id,
                config=config,
            )

            logger.info(
                f"✅ MCP client initialized for session-buddy at {self.mcp_server_url}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to initialize MCP client: {e}")

            self._initialize_fallback()

    def _initialize_fallback(self) -> None:
        try:
            self._fallback_tracker = SessionBuddyDirectTracker(
                session_id=self.session_id
            )
            logger.info("✅ Fallback direct tracker initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize fallback tracker: {e}")

    def track_invocation(
        self,
        skill_name: str,
        user_query: str | None = None,
        alternatives_considered: list[str] | None = None,
        selection_rank: int | None = None,
        workflow_phase: str | None = None,
    ) -> Callable[..., None] | None:

        if self._mcp_client and self._mcp_client.is_connected():
            try:
                async_completer = asyncio.create_task(
                    self._mcp_client.track_invocation(
                        skill_name=skill_name,
                        user_query=user_query,
                        alternatives_considered=alternatives_considered,
                        selection_rank=selection_rank,
                        workflow_phase=workflow_phase,
                    )
                )

                def sync_wrapper(
                    *,
                    completed: bool = True,
                    follow_up_actions: list[str] | None = None,
                    error_type: str | None = None,
                ) -> None:

                    try:
                        completer = asyncio.run(async_completer.get_result())

                        if completer:
                            completer(
                                completed=completed,
                                follow_up_actions=follow_up_actions,
                                error_type=error_type,
                            )
                    except Exception as e:
                        logger.warning(f"Failed to complete async tracking: {e}")

                return sync_wrapper

            except Exception as e:
                logger.warning(f"MCP tracking failed: {e}")

        if self._fallback_tracker:
            logger.debug("Using fallback direct tracker")
            return self._fallback_tracker.track_invocation(
                skill_name=skill_name,
                user_query=user_query,
                alternatives_considered=alternatives_considered,
                selection_rank=selection_rank,
                workflow_phase=workflow_phase,
            )

        return None

    def get_recommendations(
        self,
        user_query: str,
        limit: int = 5,
        workflow_phase: str | None = None,
    ) -> list[dict[str, object]]:

        if self._mcp_client:
            try:
                recommendations = asyncio.run(
                    self._mcp_client.get_recommendations(
                        user_query=user_query,
                        limit=limit,
                        workflow_phase=workflow_phase,
                    )
                )

                return recommendations

            except Exception as e:
                logger.warning(f"MCP recommendations failed: {e}")

        if self._fallback_tracker:
            logger.debug("Using fallback direct tracker for recommendations")
            return self._fallback_tracker.get_recommendations(
                user_query=user_query,
                limit=limit,
                workflow_phase=workflow_phase,
            )

        return []

    def is_enabled(self) -> bool:

        if self._mcp_client and self._mcp_client.is_connected():
            return True

        if self._fallback_tracker is not None:
            return True

        if self._mcp_client and hasattr(self._mcp_client, '_fallback_tracker'):
            return self._mcp_client._fallback_tracker is not None
        return False

    def get_backend(self) -> str:
        if self._mcp_client and self._mcp_client.is_connected():
            return f"{self.backend_name} (connected)"
        elif self._fallback_tracker:
            return f"{self.backend_name} (using fallback: {self._fallback_tracker.get_backend()})"
        elif self._mcp_client and hasattr(self._mcp_client, '_fallback_tracker') and self._mcp_client._fallback_tracker:
            return f"{self.backend_name} (using client fallback: {self._mcp_client._fallback_tracker.get_backend()})"

        return f"{self.backend_name} (disconnected)"


def create_skills_tracker(
    session_id: str,
    enabled: bool = True,
    backend: str = "direct",
    db_path: Path | None = None,
    mcp_server_url: str = "http://localhost: 8678",
) -> SkillsTrackerProtocol:
    if not enabled:
        logger.info("Skills tracking is disabled")
        return NoOpSkillsTracker()

    if backend == "direct":
        logger.info("Using session-buddy direct integration (Option A)")
        return SessionBuddyDirectTracker(
            session_id=session_id,
            db_path=db_path or Path.cwd() / ".session-buddy" / "skills.db",
        )

    if backend == "mcp":
        logger.info("Using session-buddy MCP bridge (Option B)")
        return SessionBuddyMCPTracker(
            session_id=session_id,
            mcp_server_url=mcp_server_url,
        )

    if backend == "auto":
        logger.info("Auto-detecting backend, trying MCP first...")
        mcp_tracker = SessionBuddyMCPTracker(
            session_id=session_id,
            mcp_server_url=mcp_server_url,
        )

        if mcp_tracker.is_enabled():
            return mcp_tracker
        else:
            logger.info("MCP unavailable, falling back to direct integration")
            return SessionBuddyDirectTracker(
                session_id=session_id,
                db_path=db_path or Path.cwd() / ".session-buddy" / "skills.db",
            )

    logger.debug(f"Unknown backend '{backend}', using no-op")
    return NoOpSkillsTracker()


@dataclass
class SkillExecutionContext:
    skill_name: str
    user_query: str | None = None
    workflow_phase: str | None = None
    alternatives_considered: list[str] = field(default_factory=list)
    selection_rank: int | None = None

    @classmethod
    def from_agent_execution(
        cls,
        agent_name: str,
        issue: object | None = None,
        workflow_phase: str | None = None,
        candidates: list[object] | None = None,
    ) -> SkillExecutionContext:

        user_query = None
        if issue and hasattr(issue, "message"):
            user_query = issue.message

        alternatives = []
        if candidates:
            alternatives = []
            for c in candidates:
                name = c.name if hasattr(c, "name") else str(c)
                if name != agent_name:
                    alternatives.append(name)

        selection_rank = 1

        return cls(
            skill_name=agent_name,
            user_query=user_query,
            workflow_phase=workflow_phase,
            alternatives_considered=alternatives,
            selection_rank=selection_rank,
        )

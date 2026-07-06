"""Build an ``IterativeFixAgent`` appropriate for the current environment.

The tier-3 auto-fix path (see ``crackerjack.agents.iterative_fix_agent``
and ``docs/plans/2026-07-06-ai-fix-tier-architecture.md``) needs:

* a ``WorkerPool`` — dispatches a full-CLI session with Read/Edit/Bash.
* a ``SkillStore`` — records and replays successful fix patterns.

This module chooses the right concrete implementations based on
the runtime environment:

* If ``MAHAVISHNU_MCP_URL`` is set, use ``MahavishnuPool`` to route
  work through Mahavishnu's pool (cross-server, scalable).
* Otherwise, fall back to ``LocalClaudeSubprocess`` which spawns
  ``claude --print`` directly.
* If ``SESSION_BUDDY_MCP_URL`` is set, use ``SessionBuddySkillStore``
  for cross-session skill persistence.
* Otherwise, fall back to ``InMemorySkillStore`` (process-scoped).

The factory never raises. If neither pool nor store can be built
(e.g., the imports themselves fail), it returns ``None`` so the
caller can skip tier-3 gracefully rather than crash the whole
ai-fix run.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crackerjack.agents.iterative_fix_agent import (
        IterativeFixAgent,
        SkillStore,
        WorkerPool,
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration via environment
# ---------------------------------------------------------------------------


def _mahavishnu_mcp_url() -> str | None:
    """Return the configured Mahavishnu MCP URL or None."""
    return os.environ.get("MAHAVISHNU_MCP_URL")


def _session_buddy_mcp_url() -> str | None:
    """Return the configured Session-Buddy MCP URL or None."""
    return os.environ.get("SESSION_BUDDY_MCP_URL")


def _has_claude_binary() -> bool:
    """Check whether the ``claude`` binary is on PATH."""
    import shutil

    return shutil.which("claude") is not None


# ---------------------------------------------------------------------------
# Pool + store builders
# ---------------------------------------------------------------------------


def build_worker_pool() -> WorkerPool | None:
    """Construct a WorkerPool, preferring Mahavishnu when available.

    Returns ``None`` only if neither the Mahavishnu pool nor the local
    ``claude`` binary is available. In practice the local path
    always succeeds (no-op) so this almost never returns None.
    """
    from crackerjack.agents.iterative_fix_agent import LocalClaudeSubprocess

    if _mahavishnu_mcp_url():
        try:
            from crackerjack.agents.iterative_fix_agent import MahavishnuPool

            client = _make_mahavishnu_client(_mahavishnu_mcp_url())
            if client is not None:
                logger.debug(
                    "Tier-3: using MahavishnuPool at %s",
                    _mahavishnu_mcp_url(),
                )
                return MahavishnuPool(mcp_client=client)
        except Exception as exc:
            logger.warning(
                "Tier-3: MahavishnuPool init failed (%s); falling back to local",
                exc,
            )
    if _has_claude_binary():
        logger.debug("Tier-3: using LocalClaudeSubprocess (claude on PATH)")
        return LocalClaudeSubprocess()
    logger.debug("Tier-3: no claude binary and no Mahavishnu; pool disabled")
    return None


def build_skill_store() -> SkillStore:
    """Construct a SkillStore, preferring Session-Buddy when available.

    Always returns a store. The in-memory fallback is the default;
    Session-Buddy is an upgrade, not a requirement.
    """
    from crackerjack.agents.iterative_fix_agent import InMemorySkillStore

    if _session_buddy_mcp_url():
        try:
            from crackerjack.agents.iterative_fix_agent import (
                SessionBuddySkillStore,
            )

            client = _make_session_buddy_client(_session_buddy_mcp_url())
            if client is not None:
                logger.debug(
                    "Tier-3: using SessionBuddySkillStore at %s",
                    _session_buddy_mcp_url(),
                )
                return SessionBuddySkillStore(mcp_client=client)
        except Exception as exc:
            logger.warning(
                "Tier-3: SessionBuddySkillStore init failed (%s); "
                "falling back to in-memory",
                exc,
            )
    logger.debug("Tier-3: using InMemorySkillStore (process-scoped)")
    return InMemorySkillStore()


# ---------------------------------------------------------------------------
# Top-level: build the full agent
# ---------------------------------------------------------------------------


def build_iterative_agent(
    project_root: Path | None = None,
) -> IterativeFixAgent | None:
    """Build the full IterativeFixAgent for the current environment.

    Returns ``None`` if no WorkerPool is available (no claude, no
    Mahavishnu). In that case the caller should NOT attach tier-3
    to the FixerCoordinator.

    Never raises — any unexpected failure degrades to ``None`` so
    the ai-fix run can proceed without tier-3.
    """
    try:
        pool = build_worker_pool()
    except Exception as exc:
        logger.warning("Tier-3: build_worker_pool raised (%s); skipping", exc)
        return None
    if pool is None:
        return None
    try:
        skill_store = build_skill_store()
    except Exception as exc:
        logger.warning(
            "Tier-3: build_skill_store raised (%s); using in-memory fallback",
            exc,
        )
        from crackerjack.agents.iterative_fix_agent import InMemorySkillStore

        skill_store = InMemorySkillStore()
    try:
        from crackerjack.agents.iterative_fix_agent import IterativeFixAgent

        agent = IterativeFixAgent(pool=pool, skill_store=skill_store)
    except Exception as exc:
        logger.warning(
            "Tier-3: IterativeFixAgent construction raised (%s); skipping", exc
        )
        return None
    logger.info(
        "Tier-3 IterativeFixAgent built (pool=%s, store=%s)",
        type(pool).__name__,
        type(skill_store).__name__,
    )
    return agent


# ---------------------------------------------------------------------------
# MCP client shims
# ---------------------------------------------------------------------------


def _make_mahavishnu_client(url: str) -> object | None:
    """Build a Mahavishnu MCP client object.

    The actual MCP client wiring is environment-specific (HTTP,
    stdio, etc.) and lives outside this module. This stub returns
    a callable wrapper that the ``MahavishnuPool`` can drive via
    ``pool_route_execute``.

    Real production wiring: import your MCP client SDK here and
    return a thin adapter exposing ``pool_route_execute(prompt,
    pool_selector, timeout)``. The scaffold below makes it trivial
    to swap in a real client — just change the return value.
    """
    # Scaffolding: return None so we fall back to LocalClaudeSubprocess.
    # Production callers wire a real client (HTTP or stdio MCP).
    logger.debug(
        "Mahavishnu MCP client wiring not yet implemented for %s; "
        "falling back to local pool",
        url,
    )
    return None


def _make_session_buddy_client(url: str) -> object | None:
    """Build a Session-Buddy MCP client object.

    Real production wiring: same pattern as Mahavishnu — import
    your MCP SDK and return an adapter exposing
    ``distill_skills_now(...)`` and ``search_distilled_skills(...)``.
    """
    logger.debug(
        "Session-Buddy MCP client wiring not yet implemented for %s; "
        "falling back to in-memory store",
        url,
    )
    return None

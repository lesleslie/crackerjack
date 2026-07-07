"""Build an ``IterativeFixAgent`` appropriate for the current environment.

The tier-3 auto-fix path (see ``crackerjack.agents.iterative_fix_agent``
and ``docs/plans/2026-07-06-ai-fix-tier-architecture.md``) needs:

* a ``WorkerPool`` — dispatches a full-CLI session with Read/Edit/Bash.
* a ``SkillStore`` — records and replays successful fix patterns.

This module chooses the right concrete implementations based on
the runtime environment:

* If ``MAHAVISHNU_MCP_URL`` is set AND a real MCP client is wired
  (see ``_make_mahavishnu_client``), use ``MahavishnuPool`` to
  route work through Mahavishnu's pool (cross-server, scalable).
* Otherwise, fall back to ``LocalClaudeSubprocess`` which spawns
  ``claude --print`` directly.
* If ``SESSION_BUDDY_MCP_URL`` is set AND a real MCP client is wired
  (see ``_make_session_buddy_client``), use ``SessionBuddySkillStore``
  for cross-session skill persistence.
* Otherwise, fall back to ``InMemorySkillStore`` (process-scoped).

**Current state (scaffold):** The MCP-client factories
(``_make_mahavishnu_client``, ``_make_session_buddy_client``) are
TODOs — they always return ``None`` so the live code path always
uses the local fallbacks. To enable production pools, follow the
docstrings on those functions to import an MCP client SDK and
return an adapter with the documented method names.

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
# MCP client shims (HTTP via httpx — production-ready)
# ---------------------------------------------------------------------------


def _make_mahavishnu_client(url: str) -> object | None:
    """Build a Mahavishnu MCP client adapter.

    Returns an adapter that exposes
    ``pool_route_execute(prompt, pool_selector, timeout)`` matching
    the contract ``MahavishnuPool`` expects. Falls back to ``None``
    if the URL is invalid or ``httpx`` can't initialize the client.

    The adapter speaks HTTP to the Mahavishnu MCP endpoint, so
    the deployment just needs ``MAHAVISHNU_MCP_URL`` set and the
    Mahavishnu server reachable. No SDK coupling — we use the
    stdlib JSON-RPC shape directly.

    Set ``MAHAVISHNU_MCP_URL`` in the environment to enable
    Mahavishnu dispatch. Without it the factory falls back to
    ``LocalClaudeSubprocess``.
    """
    try:
        return _HTTPMahavishnuClient(base_url=url)
    except (ValueError, ImportError) as exc:
        logger.debug(
            "Mahavishnu MCP client init failed for %s: %s; falling back to local",
            url,
            exc,
        )
        return None


def _make_session_buddy_client(url: str) -> object | None:
    """Build a Session-Buddy MCP client adapter.

    Returns an adapter that exposes
    ``distill_skills_now(problem, because, approach, evidence_threshold)``
    and ``search_distilled_skills(query)`` matching the contract
    ``SessionBuddySkillStore`` expects.

    Set ``SESSION_BUDDY_MCP_URL`` in the environment to enable
    cross-session skill persistence. Without it the factory falls
    back to ``InMemorySkillStore``.
    """
    try:
        return _HTTPSessionBuddyClient(base_url=url)
    except (ValueError, ImportError) as exc:
        logger.debug(
            "Session-Buddy MCP client init failed for %s: %s; falling back to in-memory",
            url,
            exc,
        )
        return None


class _HTTPMahavishnuClient:
    """HTTP adapter for the Mahavishnu MCP ``pool_route_execute`` tool.

    Returns a dict shaped ``{"success": bool, "result": str | dict,
    "message": str}`` so ``MahavishnuPool._parse_pool_route_result``
    can consume it without knowing the transport.

    The HTTP shape mirrors what a local MCP server exposes: a
    single endpoint that accepts JSON-RPC-shaped POSTs. Real
    production may use stdio or a different RPC framework; the
    adapter interface (``pool_route_execute``) is stable.
    """

    def __init__(self, base_url: str) -> None:
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise ValueError(f"Mahavishnu URL must be http(s); got {base_url!r}")
        import httpx

        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(30.0, connect=5.0),
            headers={"Content-Type": "application/json"},
        )

    def pool_route_execute(
        self,
        prompt: str,
        pool_selector: str = "least_loaded",
        timeout: int = 600,
    ) -> dict:
        """Dispatch a prompt via Mahavishnu's pool_route_execute.

        Returns a dict the same shape ``MahavishnuPool`` expects from
        the local stub. Translates HTTP errors into the same
        failure dict so callers can handle them uniformly.
        """
        try:
            response = self._client.post(
                "/mcp/tools/pool_route_execute",
                json={
                    "prompt": prompt,
                    "pool_selector": pool_selector,
                    "timeout": timeout,
                },
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return {
                "success": False,
                "result": "",
                "message": f"HTTP dispatch failed: {exc}",
            }
        return {
            "success": bool(data.get("success", False)),
            "result": data.get("result", data.get("diff", "")),
            "message": data.get("message", ""),
        }


class _HTTPSessionBuddyClient:
    """HTTP adapter for Session-Buddy's skill-distillation MCP tools.

    The expected HTTP shape:
    * POST ``/mcp/tools/distill_skills_now`` → ``{"ok": bool}``
    * POST ``/mcp/tools/search_distilled_skills`` → ``{"hits": [...]}``

    Production deployments may use a different shape; the adapter
    interface (``distill_skills_now``, ``search_distilled_skills``)
    is stable and matches ``SessionBuddySkillStore``'s contract.
    """

    def __init__(self, base_url: str) -> None:
        if not base_url or not base_url.startswith(("http://", "https://")):
            raise ValueError(f"Session-Buddy URL must be http(s); got {base_url!r}")
        import httpx

        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(30.0, connect=5.0),
            headers={"Content-Type": "application/json"},
        )

    def distill_skills_now(
        self,
        problem: str,
        because: str,
        approach: str,
        evidence_threshold: int = 3,
    ) -> dict:
        """Record a successful fix pattern."""
        try:
            response = self._client.post(
                "/mcp/tools/distill_skills_now",
                json={
                    "problem": problem,
                    "because": because,
                    "approach": approach,
                    "evidence_threshold": evidence_threshold,
                },
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": bool(data.get("ok", True))}

    def search_distilled_skills(self, query: str, limit: int = 5) -> list[dict]:
        """Look up skills by signature query."""
        try:
            response = self._client.post(
                "/mcp/tools/search_distilled_skills",
                json={"query": query, "limit": limit},
            )
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []
        hits = data.get("hits", [])
        return hits if isinstance(hits, list) else []

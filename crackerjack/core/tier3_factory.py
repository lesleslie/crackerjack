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


def _mahavishnu_mcp_url() -> str | None:
    return os.environ.get("MAHAVISHNU_MCP_URL")


def _session_buddy_mcp_url() -> str | None:
    return os.environ.get("SESSION_BUDDY_MCP_URL")


def _has_claude_binary() -> bool:
    import shutil

    return shutil.which("claude") is not None


def build_worker_pool() -> WorkerPool | None:
    from crackerjack.agents.iterative_fix_agent import LocalClaudeSubprocess

    if _mahavishnu_mcp_url():
        try:
            from crackerjack.agents.iterative_fix_agent import MahavishnuPool

            client = _make_mahavishnu_client(_mahavishnu_mcp_url())  # type: ignore
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
    from crackerjack.agents.iterative_fix_agent import InMemorySkillStore

    if _session_buddy_mcp_url():
        try:
            from crackerjack.agents.iterative_fix_agent import (
                SessionBuddySkillStore,
            )

            client = _make_session_buddy_client(_session_buddy_mcp_url())  # type: ignore
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


def build_iterative_agent(
    project_root: Path | None = None,
) -> IterativeFixAgent | None:
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


def _make_mahavishnu_client(url: str) -> object | None:
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
    try:
        return _HTTPSessionBuddyClient(base_url=url)
    except (ValueError, ImportError) as exc:
        logger.debug(
            "Session-Buddy MCP client init failed for %s: %s; falling back to in-memory",  # noqa: E501
            url,
            exc,
        )
        return None


class _HTTPMahavishnuClient:
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

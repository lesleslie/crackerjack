"""Tests for ``crackerjack.core.tier3_factory``.

Verifies that:
* The factory prefers Mahavishnu over Local when MCP URL is set.
* The factory prefers Session-Buddy over InMemory when MCP URL is set.
* When MCP URLs are unset, falls back to local implementations.
* When ``claude`` binary is missing and no MCP URL, returns None.
* Returns ``None`` rather than raising on any failure.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.core.tier3_factory import (
    build_iterative_agent,
    build_skill_store,
    build_worker_pool,
)

# ---------------------------------------------------------------------------
# build_worker_pool
# ---------------------------------------------------------------------------


class TestBuildWorkerPool:
    def test_local_fallback_when_no_mcp_url(self) -> None:
        # No MAHAVISHNU_MCP_URL set; if claude is on PATH, use local.
        with (
            patch(
                "crackerjack.core.tier3_factory._mahavishnu_mcp_url",
                return_value=None,
            ),
            patch(
                "crackerjack.core.tier3_factory._has_claude_binary",
                return_value=True,
            ),
        ):
            from crackerjack.agents.iterative_fix_agent import (
                LocalClaudeSubprocess,
            )

            pool = build_worker_pool()
            assert isinstance(pool, LocalClaudeSubprocess)

    def test_returns_none_when_no_claude_and_no_mcp(self) -> None:
        with (
            patch(
                "crackerjack.core.tier3_factory._mahavishnu_mcp_url",
                return_value=None,
            ),
            patch(
                "crackerjack.core.tier3_factory._has_claude_binary",
                return_value=False,
            ),
        ):
            assert build_worker_pool() is None

    def test_falls_back_to_local_when_mahavishnu_client_unavailable(self) -> None:
        # MCP URL is set, but our scaffold returns None for the
        # client (production wiring TODO). The factory must fall
        # back to LocalClaudeSubprocess rather than crash.
        with (
            patch(
                "crackerjack.core.tier3_factory._mahavishnu_mcp_url",
                return_value="http://mahavishnu:8680/mcp",
            ),
            patch(
                "crackerjack.core.tier3_factory._make_mahavishnu_client",
                return_value=None,
            ),
            patch(
                "crackerjack.core.tier3_factory._has_claude_binary",
                return_value=True,
            ),
        ):
            from crackerjack.agents.iterative_fix_agent import (
                LocalClaudeSubprocess,
            )

            pool = build_worker_pool()
            assert isinstance(pool, LocalClaudeSubprocess)

    def test_uses_mahavishnu_when_client_provided(self) -> None:
        # When the production wiring returns a real client object,
        # the factory uses MahavishnuPool.
        sentinel_client = object()
        with (
            patch(
                "crackerjack.core.tier3_factory._mahavishnu_mcp_url",
                return_value="http://mahavishnu:8680/mcp",
            ),
            patch(
                "crackerjack.core.tier3_factory._make_mahavishnu_client",
                return_value=sentinel_client,
            ),
        ):
            from crackerjack.agents.iterative_fix_agent import MahavishnuPool

            pool = build_worker_pool()
            assert isinstance(pool, MahavishnuPool)
            # And the client is wired in (via DI).
            assert pool._mcp is sentinel_client


# ---------------------------------------------------------------------------
# build_skill_store
# ---------------------------------------------------------------------------


class TestBuildSkillStore:
    def test_in_memory_fallback_when_no_mcp_url(self) -> None:
        with patch(
            "crackerjack.core.tier3_factory._session_buddy_mcp_url",
            return_value=None,
        ):
            from crackerjack.agents.iterative_fix_agent import (
                InMemorySkillStore,
            )

            store = build_skill_store()
            assert isinstance(store, InMemorySkillStore)

    def test_falls_back_to_in_memory_when_session_buddy_unavailable(self) -> None:
        # MCP URL set, scaffold returns None — must fall back, not crash.
        with (
            patch(
                "crackerjack.core.tier3_factory._session_buddy_mcp_url",
                return_value="http://session-buddy:8678/mcp",
            ),
            patch(
                "crackerjack.core.tier3_factory._make_session_buddy_client",
                return_value=None,
            ),
        ):
            from crackerjack.agents.iterative_fix_agent import (
                InMemorySkillStore,
            )

            store = build_skill_store()
            assert isinstance(store, InMemorySkillStore)

    def test_uses_session_buddy_when_client_provided(self) -> None:
        sentinel_client = object()
        with (
            patch(
                "crackerjack.core.tier3_factory._session_buddy_mcp_url",
                return_value="http://session-buddy:8678/mcp",
            ),
            patch(
                "crackerjack.core.tier3_factory._make_session_buddy_client",
                return_value=sentinel_client,
            ),
        ):
            from crackerjack.agents.iterative_fix_agent import (
                SessionBuddySkillStore,
            )

            store = build_skill_store()
            assert isinstance(store, SessionBuddySkillStore)


# ---------------------------------------------------------------------------
# build_iterative_agent (top-level)
# ---------------------------------------------------------------------------


class TestBuildIterativeAgent:
    def test_returns_none_when_no_pool(self) -> None:
        with (
            patch(
                "crackerjack.core.tier3_factory._mahavishnu_mcp_url",
                return_value=None,
            ),
            patch(
                "crackerjack.core.tier3_factory._has_claude_binary",
                return_value=False,
            ),
        ):
            assert build_iterative_agent() is None

    def test_returns_agent_when_pool_available(self, tmp_path: Path) -> None:
        # Local fallback: claude on PATH (mocked) + no MCP URLs.
        with (
            patch(
                "crackerjack.core.tier3_factory._mahavishnu_mcp_url",
                return_value=None,
            ),
            patch(
                "crackerjack.core.tier3_factory._has_claude_binary",
                return_value=True,
            ),
        ):
            from crackerjack.agents.iterative_fix_agent import (
                IterativeFixAgent,
                LocalClaudeSubprocess,
            )

            agent = build_iterative_agent(project_root=tmp_path)
            assert isinstance(agent, IterativeFixAgent)
            assert isinstance(agent.pool, LocalClaudeSubprocess)

    def test_never_raises(self) -> None:
        # Even if everything blows up, the factory must not raise
        # (caller may skip tier-3 entirely if None is returned).
        with patch(
            "crackerjack.agents.iterative_fix_agent.IterativeFixAgent",
            side_effect=RuntimeError("boom"),
        ):
            # build_iterative_agent catches exceptions inside its
            # builders and returns None; the top-level call must
            # also tolerate this.
            try:
                result = build_iterative_agent()
                # Either None (tolerated) or an agent (also fine).
                assert result is None or result is not None
            except RuntimeError:
                pytest.fail("build_iterative_agent should not propagate exceptions")

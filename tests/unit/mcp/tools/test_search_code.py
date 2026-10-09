"""Wire-envelope regression tests for ``mcp__crackerjack__search_code``.

Per REQ-003 + REQ-012 of
``mahavishnu/docs/plans/2026-10-09-bodai-search-infrastructure-fix.md``,
the tool must:

- Return ``status="ok"`` with ``count >= 1`` for a literal regex like
  ``def test_`` against ``*.py`` (the crackerjack repo has many such test
  functions).
- Return ``status="degraded"`` (never silent empty) when nothing matches.
- Always return a JSON envelope with a ``status`` field — assertions
  parse ``result.content[0].text`` via ``_extract_payload`` and check
  ``assert not result.is_error`` separately.

Per REQ-007 the test must fail on the current bug and pass on the fix;
``test_search_code_no_match_returns_degraded`` is the second guard.
"""

from __future__ import annotations

import os
import typing as t
import uuid
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

from crackerjack.mcp.context import (
    MCPServerConfig,
    MCPServerContext,
    set_context,
)
from crackerjack.mcp.tools import pycharm_tools
from tests.unit.mcp.tools import _extract_payload  # noqa: TID


def _make_app_with_context(project_root: Path) -> FastMCP:
    """Build a fresh FastMCP app + seed the MCP server context.

    Mirrors ``crackerjack/mcp/server_core.py:_setup_server_context`` —
    ``set_context`` populates the singleton that ``pycharm_tools._get_adapter``
    reads at request time.
    """
    set_context(
        MCPServerContext(MCPServerConfig(project_path=project_root.resolve())),
    )
    app = FastMCP("crackerjack-search-code-test")
    pycharm_tools.register_pycharm_tools(app)
    return app


@pytest.fixture
def crackerjack_repo_root() -> Path:
    """Absolute path to the crackerjack repo (the project under test)."""
    # this file lives at <repo>/tests/unit/mcp/tools/test_search_code.py
    return Path(__file__).resolve().parents[4]


@pytest.fixture(autouse=True)
def _reset_mcp_context() -> t.Iterator[None]:
    """Reset the shared MCP context singleton on entry/exit.

    Other test files in this suite also call ``set_context`` with their own
    project_path; without isolation, ``pycharm_tools._resolve_local_search_root``
    would read the wrong project_path and the local-fallback path would
    walk a non-Python directory, breaking the assertion that ``def test_``
    produces ≥1 result. Per-test isolation keeps the wire-envelope contract
    hermetic.
    """
    from crackerjack.mcp.context import clear_context

    clear_context()
    yield
    clear_context()


class TestSearchCodeWireEnvelope:
    """REQ-003 + REQ-012: wire-envelope assertions via FastMCP Client."""

    @pytest.mark.anyio
    async def test_search_code_finds_test_function(
        self, crackerjack_repo_root: Path
    ) -> None:
        """``def test_`` against ``*.py`` returns ``>= 1`` result via the
        local fallback path (no PyCharm MCP adapter attached)."""
        app = _make_app_with_context(crackerjack_repo_root)

        async with Client(app) as client:
            result = await client.call_tool(
                "search_code",
                {"pattern": "def test_", "file_pattern": "*.py"},
            )

        payload = _extract_payload(result)
        assert payload["success"] is True
        assert payload["status"] == "ok"
        assert payload["count"] >= 1, (
            f"expected ≥1 result for 'def test_' in crackerjack repo, "
            f"got count={payload['count']}"
        )
        assert isinstance(payload["results"], list)
        for r in payload["results"]:
            assert "file_path" in r
            assert "line" in r
            assert "match" in r

    @pytest.mark.anyio
    async def test_search_code_no_match_returns_degraded(
        self, crackerjack_repo_root: Path
    ) -> None:
        """A non-matching pattern returns ``status="degraded"`` (not the
        silent-empty ``success=true, count=0`` failure mode)."""
        app = _make_app_with_context(crackerjack_repo_root)

        # Random UUID string unique to this test run. Vanishingly unlikely to
        # appear in the crackerjack repo (or in this test file itself,
        # which the local fallback walks alongside the rest).
        non_matching = f"xqv_NN_2026_unmatchable_marker_{uuid.uuid4().hex}"

        async with Client(app) as client:
            result = await client.call_tool(
                "search_code",
                {
                    "pattern": non_matching,
                    "file_pattern": "*.py",
                },
            )

        payload = _extract_payload(result)
        assert payload["success"] is True
        assert payload["status"] == "degraded"
        assert payload["count"] == 0
        assert "hint" in payload

    @pytest.mark.anyio
    async def test_search_code_envelope_shape(
        self, crackerjack_repo_root: Path
    ) -> None:
        """Envelope includes ``status`` and ``source`` keys (the new
        contract per the Phase-2 fix)."""
        app = _make_app_with_context(crackerjack_repo_root)

        async with Client(app) as client:
            result = await client.call_tool(
                "search_code",
                {"pattern": "def test_", "file_pattern": "*.py"},
            )

        payload = _extract_payload(result)
        assert "status" in payload
        assert payload["status"] in {"ok", "degraded"}
        assert "source" in payload
        assert payload["source"] in {"pycharm_adapter", "local_fallback"}

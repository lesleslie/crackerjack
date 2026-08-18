"""Behavioral tests for ``crackerjack.mcp.tools.discover_query.crackerjack_discovery``.

Pins the query-filter contract that the W0 helper relies on via
``discovery_fn=crackerjack_discovery``. A regression in either the
``discovery_fn(server, query)`` call signature from the W0 helper
or in this module's substring-match logic would silently break the
``discover_tools`` meta-tool registered at every profile tier.

The historical contract (deleted in W2a:
``crackerjack/mcp/tools/discover_tools.py:189-229``) was:
  * ``query=None`` → return the full tool set.
  * ``query="..."`` → case-insensitive substring match on
    ``name`` OR ``description``.

We exercise that contract against a freshly built server (no env-var
override) so the surface matches production behavior.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from fastmcp import FastMCP


REPO_ROOT = "/Users/les/Projects/crackerjack"


async def _build_server() -> "FastMCP":
    """Build a Crackerjack MCP server at the FULL profile.

    FULL is the default when ``CRACKERJACK_TOOL_PROFILE`` is unset, so
    the surface matches what production agents see today.
    """
    from crackerjack.mcp.server_core import create_mcp_server

    server = await create_mcp_server({"http_port": 8676, "http_host": "127.0.0.1"})
    assert server is not None
    return server


@pytest.mark.asyncio
async def test_query_none_returns_full_set() -> None:
    """When query is None, every registered tool is returned."""
    from crackerjack.mcp.tools.discover_query import crackerjack_discovery

    server = await _build_server()
    result = await crackerjack_discovery(server, None)
    names = {entry["name"] for entry in result}
    # Sanity: discovery tool itself is in the surface
    assert "discover_tools" in names
    # Sanity: a few staples from the FULL profile
    assert {"execute_crackerjack", "run_crackerjack_stage"}.issubset(names)


@pytest.mark.asyncio
async def test_query_filters_by_name_substring() -> None:
    """query="search" filters by name substring (case-insensitive)."""
    from crackerjack.mcp.tools.discover_query import crackerjack_discovery

    server = await _build_server()
    result = await crackerjack_discovery(server, "search")
    # Every matched entry's name OR description contains "search"
    for entry in result:
        assert "search" in entry["name"].lower() or "search" in entry["description"].lower(), (
            f"{entry['name']!r} did not match query 'search'"
        )
    # Sanity: at least one semantic_tools entry matches by name
    names = {entry["name"] for entry in result}
    assert any("search" in n.lower() for n in names)


@pytest.mark.asyncio
async def test_query_is_case_insensitive() -> None:
    """query='Health' (uppercase H) must match lowercase 'health' in tool names."""
    from crackerjack.mcp.tools.discover_query import crackerjack_discovery

    server = await _build_server()
    lower = await crackerjack_discovery(server, "health")
    upper = await crackerjack_discovery(server, "HEALTH")
    mixed = await crackerjack_discovery(server, "Health")
    assert {entry["name"] for entry in lower} == {entry["name"] for entry in upper}
    assert {entry["name"] for entry in lower} == {entry["name"] for entry in mixed}
    # Sanity: at least one health probe is matched
    assert any("health" in entry["name"].lower() for entry in lower)


@pytest.mark.asyncio
async def test_query_filters_by_description_substring() -> None:
    """query='status' filters by description substring (e.g. get_*_status tools)."""
    from crackerjack.mcp.tools.discover_query import crackerjack_discovery

    server = await _build_server()
    result = await crackerjack_discovery(server, "status")
    for entry in result:
        assert "status" in entry["name"].lower() or "status" in entry["description"].lower()
    # Sanity: the monitoring_tools group has status-related entries
    names = {entry["name"] for entry in result}
    assert any("status" in n.lower() for n in names)


@pytest.mark.asyncio
async def test_query_empty_string_treated_as_none() -> None:
    """query='' is falsy → treated as None → returns the full set.

    The historical contract returned the full set when query was None
    or empty. ``crackerjack_discovery`` treats ``filter_query`` as a
    truthy check, so '' (empty) is treated identically to None.
    """
    from crackerjack.mcp.tools.discover_query import crackerjack_discovery

    server = await _build_server()
    full = await crackerjack_discovery(server, None)
    empty = await crackerjack_discovery(server, "")
    assert {entry["name"] for entry in full} == {entry["name"] for entry in empty}


@pytest.mark.asyncio
async def test_query_no_matches_returns_empty_list() -> None:
    """A query that matches nothing returns an empty list (not an error)."""
    from crackerjack.mcp.tools.discover_query import crackerjack_discovery

    server = await _build_server()
    result = await crackerjack_discovery(server, "this-string-matches-nothing-xyzzy-12345")
    assert result == []


@pytest.mark.asyncio
async def test_result_entries_have_required_keys() -> None:
    """Each entry exposes the documented response shape (name, description, inputSchema, group)."""
    from crackerjack.mcp.tools.discover_query import crackerjack_discovery

    server = await _build_server()
    result = await crackerjack_discovery(server, None)
    assert result, "FULL profile must register at least one tool"
    for entry in result:
        assert set(entry.keys()) == {"name", "description", "inputSchema", "group"}
        assert isinstance(entry["name"], str) and entry["name"]
        assert isinstance(entry["description"], str)

"""Crackerjack's ``crackerjack_discovery`` override for the W0 helper.

Preserves the historical ``discover_tools`` query filter behavior from the
deleted ``crackerjack/mcp/tools/discover_tools.py:189-229``. The W0 helper
auto-registers a ``discover_tools`` meta-tool that delegates to
``discovery_fn(server, query)``; this module provides the override that
filters the registered tools by a case-insensitive substring on the
tool's name or description.

The ``_TOOL_GROUPS`` map is populated from the deleted ``TOOL_REGISTRY``
(see ``tests/fixtures/_tool_groups_mapping.json``) so each surfaced tool
still carries its group label.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastmcp import FastMCP

_FIXTURE_PATH = Path("tests/fixtures/_tool_groups_mapping.json")


def _load_tool_groups() -> dict[str, str]:
    """Load the captured tool-name → group mapping.

    Lazily evaluated so importing this module is cheap. Failures fall back
    to an empty mapping (the discovery tool still works, just without the
    ``group`` field).
    """
    try:
        return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


_TOOL_GROUPS: dict[str, str] = _load_tool_groups()


async def crackerjack_discovery(
    server: FastMCP,
    filter_query: str | None,
) -> list[dict[str, object]]:
    """List tools registered in this server, optionally filtered by query.

    Mirrors the filter behavior from the deleted
    ``crackerjack/mcp/tools/discover_tools.py:189-229``:
      * When ``filter_query`` is None → return all tools.
      * Otherwise → case-insensitive substring match on ``name`` OR
        ``description``.
    """
    tools = await server.list_tools()
    result: list[dict[str, object]] = [
        {
            "name": t.name,
            "description": t.description or "",
            "inputSchema": t.parameters,
            "group": _TOOL_GROUPS.get(t.name),
        }
        for t in tools
    ]
    if filter_query:
        q = filter_query.lower()
        result = [
            entry
            for entry in result
            if q in str(entry["name"]).lower() or q in str(entry["description"]).lower()
        ]
    return result


__all__ = ["crackerjack_discovery"]

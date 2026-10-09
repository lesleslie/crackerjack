"""Wire-envelope helpers for FastMCP Client tests.

The Bodai MCP convention per REQ-012 of
``mahavishnu/docs/plans/2026-10-09-bodai-search-infrastructure-fix.md`` is
to assert on the wire-shape envelope (not the in-process return value) so
regressions in JSON serialization get caught here. ``InMemoryTransport``
was deprecated in fastmcp 3.x in favor of ``Client(app)`` direct
construction; both serve the same role for in-process testing.
"""

from __future__ import annotations

import json
import typing as t


def _extract_payload(result: t.Any) -> dict[str, t.Any]:
    """Parse the first text block from a ``CallToolResult`` to a dict.

    Raises ``AssertionError`` if the envelope is missing or unstructured —
    any non-text ``content`` block, an empty ``content`` list, or a
    ``content[0].text`` that doesn't parse as JSON is treated as a
    regression per REQ-012.
    """
    from fastmcp.client.client import CallToolResult

    assert isinstance(result, CallToolResult), (
        f"expected CallToolResult, got {type(result).__name__}"
    )
    assert not result.is_error, (
        f"CallToolResult.is_error=True: {result.content!r}"
    )
    assert result.content, "CallToolResult.content is empty"
    block = result.content[0]
    text = getattr(block, "text", None)
    assert isinstance(text, str), (
        f"first content block has no .text: type={type(block).__name__}"
    )
    parsed = json.loads(text)
    assert isinstance(parsed, dict), (
        f"envelope payload is not a dict: {type(parsed).__name__}"
    )
    return parsed

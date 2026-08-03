"""Crackerjack pre-commit gate: Phase 1.5 skill coverage.

Reads ``mcp__session-buddy__distilled_skill_health`` and emits a
warn-only verdict. The gate is non-LLM and never consumes the
LLM-Cost-Ceiling budget.

Return values:

  0 — all skills fresh (pass)
  1 — stale skills detected or Session-Buddy unreachable (warn)
  2 — programming bug (reserved; not exercised by the current logic)

Spec: ``docs/superpowers/specs/2026-07-29-session-buddy-extension-design.md``
(Q5: Phase 1.5 close-out).
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

DEFAULT_SESSION_BUDDY_URL: str = "http://localhost:8678/mcp"
DEFAULT_TIMEOUT_SECONDS: float = 5.0


async def fetch_skill_health(
    *,
    session_buddy_url: str | None = None,
    threshold_days: int = 90,
) -> dict[str, object]:
    """Call ``mcp__session-buddy__distilled_skill_health`` via HTTP JSON-RPC.

    Returns a summary dict shaped like ``{"status": "fresh"|"stale", "stale_count": int}``.
    Raises ``ConnectionError`` when Session-Buddy is unreachable or returns
    an unparseable payload.

    The MCP response envelope is a ``CallToolResult`` — the JSON payload
    lives at ``raw.content[0].text``. See the project's
    ``fastmcp-call-tool-returns-calltoolresult`` memory.
    """
    url = session_buddy_url or os.environ.get(
        "SESSION_BUDDY_MCP_URL", DEFAULT_SESSION_BUDDY_URL
    )

    import httpx

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "distilled_skill_health",
            "arguments": {
                "threshold_days": threshold_days,
            },
        },
    }

    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            body = resp.json()
    except (httpx.HTTPError, OSError, ValueError) as exc:
        raise ConnectionError(f"cannot reach session-buddy: {exc}") from exc

    text = _extract_text(body.get("result"))
    if text is None:
        return {"status": "fresh", "stale_count": 0}

    try:
        rows = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise ConnectionError(f"invalid JSON from session-buddy: {exc}") from exc

    return _summarize_health(rows)


def _extract_text(result: object) -> str | None:
    """Pull the JSON payload from a FastMCP ``CallToolResult`` envelope."""
    if not isinstance(result, dict):
        return None
    content = result.get("content")
    if not isinstance(content, list) or not content:
        return None
    first = content[0]
    if not isinstance(first, dict):
        return None
    text = first.get("text")
    return text if isinstance(text, str) else None


def _summarize_health(rows: object) -> dict[str, object]:
    """Collapse a list of distilled-skill rows into ``{status, stale_count}``."""
    if not isinstance(rows, list):
        return {"status": "fresh", "stale_count": 0}
    stale_count = sum(
        1 for r in rows if isinstance(r, dict) and str(r.get("status", "")) == "stale"
    )
    if stale_count > 0:
        return {"status": "stale", "stale_count": stale_count}
    return {"status": "fresh", "stale_count": 0}


async def pre_commit_skill_coverage_gate(repo_path: pathlib.Path) -> int:
    """Pre-commit gate. Non-LLM; never consumes LLM-Cost-Ceiling budget.

    Args:
        repo_path: Repository root. Currently informational only — the gate
            reads the global Session-Buddy MCP endpoint, not the repo state.

    Returns:
        0 — all skills fresh.
        1 — stale skills detected or Session-Buddy unreachable (warn-only default).
        2 — programming bug (assertion failed, schema mismatch).

    Operators opt into making this gate fatal via the existing
    ``crackerjack run --strict`` flag. ``--no-verify`` skips the gate
    entirely per the existing pre-commit convention.
    """
    del repo_path  # currently unused; reserved for future repo-scoped queries

    try:
        health: dict[str, object] = await fetch_skill_health()
    except Exception as exc:  # noqa: BLE001 — gate must never raise
        print(
            f"[skill-coverage] WARNING: cannot reach Session-Buddy: {exc}",
            file=sys.stderr,
        )
        return 1

    status = health.get("status")
    stale_count = _as_int(health.get("stale_count", 0))

    if status == "fresh" and stale_count == 0:
        return 0

    print(
        f"[skill-coverage] WARNING: {stale_count} stale skill(s) detected. "
        "Run `distill_skills_now` to refresh. Use `--no-verify` to skip.",
        file=sys.stderr,
    )
    return 1


def _as_int(value: object) -> int:
    """Coerce arbitrary JSON-decoded scalars to ``int`` for the gate verdict."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


__all__ = [
    "DEFAULT_SESSION_BUDDY_URL",
    "DEFAULT_TIMEOUT_SECONDS",
    "fetch_skill_health",
    "pre_commit_skill_coverage_gate",
]

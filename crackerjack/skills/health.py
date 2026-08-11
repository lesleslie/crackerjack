from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

DEFAULT_SESSION_BUDDY_URL: str = "http://localhost:8678/mcp"
DEFAULT_TIMEOUT_SECONDS: float = 5.0
DEFAULT_THRESHOLD_DAYS: int = 90

HttpClientFactory = Callable[[float], httpx.AsyncClient]


@dataclass(frozen=True, slots=True)
class SkillHealthReport:
    """Result of a `distilled_skill_health` probe.

    status values:
      fresh       — Session-Buddy reachable, zero stale skills
      stale       — Session-Buddy reachable, at least one stale skill
      unavailable — Session-Buddy unreachable / returned malformed data
    """

    status: str
    stale_count: int
    raw_rows: list[dict[str, Any]] = field(default_factory=list)


def _build_payload(threshold_days: int) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "distilled_skill_health",
            "arguments": {"threshold_days": threshold_days},
        },
    }


def _extract_text(result: object) -> str | None:
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


def _summarize(rows: object) -> SkillHealthReport:
    if not isinstance(rows, list):
        return SkillHealthReport(status="fresh", stale_count=0)
    raw = [r for r in rows if isinstance(r, dict)]
    stale_count = sum(1 for r in raw if str(r.get("status", "")) == "stale")
    status = "stale" if stale_count > 0 else "fresh"
    return SkillHealthReport(status=status, stale_count=stale_count, raw_rows=raw)


async def fetch_skill_health(
    *,
    session_buddy_url: str | None = None,
    threshold_days: int = 90,
    http_client_factory: HttpClientFactory | None = None,
) -> SkillHealthReport:
    url = session_buddy_url or os.environ.get(
        "SESSION_BUDDY_MCP_URL",
        DEFAULT_SESSION_BUDDY_URL,
    )
    factory = http_client_factory or (
        lambda timeout: httpx.AsyncClient(timeout=timeout)
    )

    try:
        async with factory(DEFAULT_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=_build_payload(threshold_days))
            resp.raise_for_status()
            body: Any = resp.json()
    except (httpx.HTTPError, OSError, ValueError):
        return SkillHealthReport(status="unavailable", stale_count=0)

    text = _extract_text(body.get("result") if isinstance(body, dict) else None)
    if text is None:
        return SkillHealthReport(status="fresh", stale_count=0)
    try:
        rows = json.loads(text)
    except (TypeError, ValueError):
        return SkillHealthReport(status="unavailable", stale_count=0)
    return _summarize(rows)


__all__ = [
    "DEFAULT_SESSION_BUDDY_URL",
    "DEFAULT_THRESHOLD_DAYS",
    "DEFAULT_TIMEOUT_SECONDS",
    "HttpClientFactory",
    "SkillHealthReport",
    "fetch_skill_health",
]

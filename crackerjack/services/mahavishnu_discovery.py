"""Probe Mahavishnu MCP for ecosystem-wide config (currently: publish_url).

Mahavishnu is the canonical source of truth for the Bodai ecosystem
registry. Crackerjack reads its own ``settings/local.yaml`` first; when
that's missing or doesn't set ``publishing.publish_url``, this module
asks Mahavishnu's MCP server whether the current repo has a custom
publish target. The probe runs **once at startup** and the result is
cached on ``PhaseCoordinator.publish_manager.publish_url`` for the
lifetime of the process.

Soft fallback: any failure (timeout, connection refused, non-2xx,
malformed response, missing tool) returns ``None``, which makes the
publish fall through to the default branch (public PyPI). This means
the probe is safe to run on every invocation — operators don't need
to know whether Mahavishnu is reachable.

Discovery: default ``http://localhost:8680/mcp`` (Mahavishnu's MCP
HTTP transport). Override via ``$MAHAVISHNU_MCP_URL``. Probe budget:
``PROBE_TIMEOUT_SECONDS`` (200 ms) — startup cost must stay cheap.

Layered precedence (matches ``crackerjack/config/ecosystem_synthesis.py:17-23``):

  1. ``Options.publish_url`` (--publish-url CLI flag / $CRACKERJACK_PUBLISH_URL)
  2. ``settings.publishing.publish_url`` (settings/local.yaml + BODAI_ECOSYSTEM_CONFIG synthesis)
  3. **Mahavishnu MCP probe** (this module) — NEW
  4. ``None`` → ``uv publish`` (default = public PyPI)
"""
from __future__ import annotations

import logging
import os

import httpx2 as httpx

logger = logging.getLogger(__name__)


DEFAULT_MAHAVISHNU_MCP_URL = "http://localhost:8680/mcp"
PROBE_TIMEOUT_SECONDS = 0.2  # 200 ms — startup cost must stay cheap.
ENV_VAR_URL_OVERRIDE = "MAHAVISHNU_MCP_URL"
PROBE_TOOL_NAME = "mahavishnu_get_publish_url"


class MahavishnuUnreachable(Exception):
    """Internal: probe failed. Callers should NOT raise this — soft fallback."""


# Module-level seam for tests: tests patch this attribute with a stub
# that returns a configured ``httpx.Response``-shaped object (a
# ``SimpleNamespace`` with ``raise_for_status`` + ``json`` is enough).
# Production code calls ``_http_post(...)`` directly; the indirection
# lets tests sidestep respx's strict ``isinstance(httpx.Response)``
# check (respx is pinned to upstream httpx, not this project's httpx2).
_http_post = httpx.post


def _mcp_endpoint_url() -> str:
    """Return the configured Mahavishnu MCP endpoint.

    Defaults to ``http://localhost:8680/mcp`` (Mahavishnu's standard
    FastMCP HTTP transport). Override with ``$MAHAVISHNU_MCP_URL``.
    """
    base = os.environ.get(ENV_VAR_URL_OVERRIDE, DEFAULT_MAHAVISHNU_MCP_URL)
    # Accept either bare ``http://host:port`` (add ``/mcp``) or a fully
    # qualified ``http://host:port/mcp`` (use as-is). Cheap heuristic —
    # the FastMCP convention is the trailing ``/mcp`` path.
    if base.rstrip("/").endswith("/mcp"):
        return base
    return base.rstrip("/") + "/mcp"


def _parse_mcp_response(payload: dict[str, object]) -> str | None:
    """Extract the publish URL from an MCP ``tools/call`` response.

    The MCP protocol wraps results in ``result.content[0].text`` as a
    stringified payload (or returns ``result`` directly for structured
    content). Tolerates both shapes so we don't break when Mahavishnu
    switches content types.
    """
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")

    # Structured-content shape (result IS the URL string): Mahavishnu
    # returns just the publish_url as a plain string. Check this
    # BEFORE the dict branch so we don't reject it.
    if isinstance(result, str):
        return result if result else None

    if not isinstance(result, dict):
        return None

    # MCP wraps isError INSIDE the result object, not at the top level
    # (the top level has ``error`` for transport-level failures).
    if result.get("isError"):
        logger.debug("Mahavishnu probe returned isError=True; soft fallback")
        return None

    content = result.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            text = first.get("text")
            if isinstance(text, str) and text:
                # Content text is the URL string per the contract documented
                # in this module's docstring.
                return text
        return None

    return None


def probe_publish_url(repo_path: str) -> str | None:
    """Return the publish_url Mahavishnu has registered for ``repo_path``.

    Args:
        repo_path: Absolute path to the repo being published. Path-matched
            via ``Path.resolve()`` on Mahavishnu's side against registered
            repos in its ecosystem registry.

    Returns:
        The publish URL string (``https://gitlab.com/api/v4/projects/...``
        or similar), or ``None`` if Mahavishnu has no entry for this
        repo or the probe failed for any reason.

    Raises:
        Never. All failure modes return ``None`` by design — this is
        soft fallback. The single call site (``PhaseCoordinator``)
        uses ``None`` as the "no override" sentinel and routes to
        public PyPI by default.
    """
    endpoint = _mcp_endpoint_url()
    try:
        response = _http_post(
            endpoint,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": PROBE_TOOL_NAME,
                    "arguments": {"repo_path": repo_path},
                },
            },
            timeout=PROBE_TIMEOUT_SECONDS,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return _parse_mcp_response(response.json())
    except httpx.HTTPError as exc:
        logger.debug(
            "Mahavishnu MCP probe failed (%s: %s); soft fallback to "
            "default publish target",
            type(exc).__name__,
            exc,
        )
        return None
    except (ValueError, KeyError, TypeError) as exc:
        # Malformed JSON, unexpected shape, etc.
        logger.debug(
            "Mahavishnu MCP probe returned malformed response (%s); "
            "soft fallback",
            exc,
        )
        return None

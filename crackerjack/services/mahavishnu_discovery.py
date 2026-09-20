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

import json
import logging
import os

import httpx2 as httpx

logger = logging.getLogger(__name__)


DEFAULT_MAHAVISHNU_MCP_URL = "http://localhost:8680/mcp"
# Timeout per HTTP round-trip. The probe does 3 calls (initialize →
# notifications/initialized → tools/call), each reading a FastMCP
# SSE-framed body. 0.2 s was too tight — SSE keeps the connection open
# and the body read timed out before the first event arrived
# (verified 2026-09-20). 5 s is plenty for the actual tools/call
# (FastMCP returns the URL in <50 ms once the request lands) and
# preserves the "non-blocking startup" budget — total worst-case
# across 3 calls is ~15 s, still well under the Akosha round-trip
# window of a typical crackerjack run.
PROBE_TIMEOUT_SECONDS = 5.0
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

    Tolerates four shapes (verified 2026-09-20 against running Mahavishnu
    with FastMCP 3.x returning ``str`` tool results):

      1. ``{"result": "<url>"}`` — bare string result
      2. ``{"result": {"content": [{"type": "text", "text": "<url>"}]}}``
         — classic envelope (empty content returns ``None``)
      3. ``{"result": {"structuredContent": {"result": "<url>"}}}``
         — FastMCP default for ``str`` returns (the URL lands here)
      4. ``{"result": {"isError": true, "content": [...]}}``
         — error wrapper, returns ``None``
    """
    if not isinstance(payload, dict):
        return None
    result = payload.get("result")

    # Shape 1: bare string result.
    if isinstance(result, str):
        return result or None

    if not isinstance(result, dict):
        return None

    # Shape 4: error wrapper.
    if result.get("isError"):
        logger.debug("Mahavishnu probe returned isError=True; soft fallback")
        return None

    # Shape 3: FastMCP's default envelope for ``str`` tool returns —
    # the URL is in structuredContent.result. Check this BEFORE the
    # content[0].text branch because ``content`` may be empty here
    # even when the call succeeded.
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        inner = structured.get("result")
        if isinstance(inner, str):
            return inner or None
        if inner is None:
            # ``str | None`` returns surface as ``result: null`` when
            # the tool returns ``None`` (no matching repo).
            return None

    # Shape 2: classic envelope.
    content = result.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and first.get("type") == "text":
            text = first.get("text")
            if isinstance(text, str) and text:
                return text
        return None

    return None


# Headers required by FastMCP's streamable-HTTP transport. The dual
# Accept is non-negotiable — the server returns HTTP 406 otherwise.
# (Verified against the running Mahavishnu on 2026-09-20.)
_MCP_ACCEPT_HEADER = "application/json, text/event-stream"
_MCP_CONTENT_TYPE = "application/json"

# Standard MCP ``initialize`` payload — protocol version pinned to the
# one Mahavishnu announces. ``clientInfo`` is informational.
_MCP_INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "crackerjack-probe", "version": "0.1.0"},
    },
}

_MCP_NOTIFICATIONS_INITIALIZED = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
    "params": {},
}


def _post_mcp(
    endpoint: str,
    *,
    json: dict[str, object],
    session_id: str | None = None,
):
    """Single-call seam: POST one JSON-RPC envelope with the right headers.

    Returns whatever ``_http_post`` returns. Tests patch this seam to
    feed canned responses in order (initialize → notifications/initialized
    → tools/call); production uses the underlying ``_http_post``.

    Why this is a separate function: the test seam needs to live at a
    level where one Python call maps to one HTTP round-trip. ``_http_post``
    still exists as a finer seam for tests that want to exercise HTTP
    error shapes (e.g. timeouts, 5xx).

    The ``json`` kwarg name is intentional — it matches the httpx
    convention so test fixtures can mirror production call shape.
    """
    headers = {
        "Content-Type": _MCP_CONTENT_TYPE,
        "Accept": _MCP_ACCEPT_HEADER,
    }
    if session_id:
        headers["mcp-session-id"] = session_id
    return _http_post(endpoint, json=json, timeout=PROBE_TIMEOUT_SECONDS, headers=headers)


def _extract_json_payload(body: str | bytes) -> object | None:
    """Extract a JSON-RPC payload from a FastMCP response body.

    FastMCP's streamable-HTTP transport returns ``text/event-stream``
    bodies even when the client accepts both types. The SSE envelope
    is ``event: message\\ndata: <JSON>\\n\\n`` — we extract the
    ``data:`` line and parse it as JSON.

    Tolerates plain JSON too so the test seam doesn't have to wrap
    every fixture in an SSE envelope.
    """
    if isinstance(body, bytes):
        try:
            body = body.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if not isinstance(body, str):
        return None

    # SSE envelope: at least one ``data:`` line, possibly preceded by
    # ``event:`` and terminated by a blank line.
    sse_data_line: str | None = None
    for line in body.splitlines():
        if line.startswith("data:"):
            sse_data_line = line[5:].lstrip()
            break

    if sse_data_line is not None:
        try:
            return json.loads(sse_data_line)
        except json.JSONDecodeError:
            return None

    # Plain JSON fallback (used by tests).
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def probe_publish_url(repo_path: str) -> str | None:
    """Return the publish_url Mahavishnu has registered for ``repo_path``.

    FastMCP's streamable-HTTP transport is stateful — a bare
    ``tools/call`` returns HTTP 406 (no SSE accept) or HTTP 400
    (missing session id). The probe therefore performs the standard
    three-call handshake:

      1. ``initialize``  → captures ``mcp-session-id`` from response header
      2. ``notifications/initialized`` (no body parse needed)
      3. ``tools/call``   → uses the session id; parses SSE body

    Every failure mode (timeout, connection refused, non-2xx, missing
    session header, malformed SSE, malformed JSON, ``isError`` payload)
    returns ``None`` by design. Callers treat ``None`` as "no override"
    and fall through to the default publish target (public PyPI).

    Args:
        repo_path: Absolute path to the repo being published. Path-matched
            via ``Path.resolve()`` on Mahavishnu's side against registered
            repos in its ecosystem registry.

    Returns:
        The publish URL string (``https://gitlab.com/api/v4/projects/...``
        or similar), or ``None`` if Mahavishnu has no entry for this
        repo or the probe failed for any reason.

    Raises:
        Never. Soft fallback by design — the single call site
        (``PhaseCoordinator``) uses ``None`` as the "no override"
        sentinel and routes to public PyPI by default.
    """
    endpoint = _mcp_endpoint_url()
    try:
        # 1) initialize — server returns a session id in the response header.
        init_resp = _post_mcp(endpoint, json=_MCP_INITIALIZE)
        init_resp.raise_for_status()
        session_id = init_resp.headers.get("mcp-session-id") if hasattr(
            init_resp, "headers"
        ) else None
        if not session_id:
            logger.debug(
                "Mahavishnu initialize response carried no session id; "
                "soft fallback to default publish target",
            )
            return None

        # 2) notifications/initialized — no body parse (FastMCP returns 202 + empty).
        #    Failure here is non-fatal: some implementations skip it.
        try:
            notif_resp = _post_mcp(
                endpoint, json=_MCP_NOTIFICATIONS_INITIALIZED, session_id=session_id,
            )
            notif_resp.raise_for_status()
        except httpx.HTTPError:
            pass

        # 3) tools/call — fetch the publish URL.
        call_resp = _post_mcp(
            endpoint,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": PROBE_TOOL_NAME,
                    "arguments": {"repo_path": repo_path},
                },
            },
            session_id=session_id,
        )
        call_resp.raise_for_status()

        body_text = call_resp.text if hasattr(call_resp, "text") else ""
        payload = _extract_json_payload(body_text)
        if payload is None:
            logger.debug(
                "Mahavishnu MCP probe returned unparseable body; soft fallback",
            )
            return None
        return _parse_mcp_response(payload)
    except httpx.HTTPError as exc:
        logger.debug(
            "Mahavishnu MCP probe failed (%s: %s); soft fallback to "
            "default publish target",
            type(exc).__name__,
            exc,
        )
        return None
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        # Malformed JSON, unexpected shape, missing attributes, etc.
        logger.debug(
            "Mahavishnu MCP probe returned malformed response (%s); soft fallback",
            exc,
        )
        return None

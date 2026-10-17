"""Oneiric runtime-facts push helper (Plan 1 Phase 3).

Boot-pushes the FastMCP tool registry summary to Oneiric via
JSON-RPC ``tools/call`` over HTTP. Oneiric unavailability MUST NOT
block Crackerjack boot — every code path is wrapped in try/except.

Design rules:

* No direct oneiric imports (httpx only). Crackerjack does NOT depend
  on oneiric at the package level; the push is a contract-only wire
  call against Oneiric's MCP surface on port 8681.
* The boot path is fire-and-forget: a daemon thread runs the async
  helper so the main() event loop / blocking call proceeds
  immediately.
* All exceptions are caught and logged — the function NEVER raises
  to its caller.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP


logger = logging.getLogger(__name__)


ONEIRIC_DEFAULT_URL = "http://127.0.0.1:8681/mcp"
ONEIRIC_DEFAULT_TOOL = "oneiric_report_runtime"
PUSH_TIMEOUT_SECONDS = 5.0
DAEMON_THREAD_NAME = "crackerjack-oneiric-runtime-push"


def _build_envelope(component: str, runtime_facts: dict[str, Any]) -> dict[str, Any]:
    """Wrap a runtime-facts payload in the Oneiric envelope.

    The envelope mirrors the structure produced by the equivalent
    Mahavishnu push (``success / registry / runtime / health``) so
    Oneiric's runtime registry sees a uniform wire shape across the
    Bodai ecosystem. ``health`` is left as ``"starting"`` because the
    push fires during boot — Oneiric will observe a subsequent
    healthy transition via the live ``/health`` feed.
    """
    return {
        "success": True,
        "registry": {
            "component": component,
            "tools": runtime_facts.get("tools", []),
            "count": runtime_facts.get("count", 0),
            "capabilities": runtime_facts.get("capabilities", {}),
        },
        "runtime": {
            "phase": "boot",
        },
        "health": "starting",
    }


def _build_jsonrpc_payload(envelope: dict[str, Any], tool_name: str) -> dict[str, Any]:
    """Wrap an envelope in a JSON-RPC 2.0 ``tools/call`` request body."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": envelope,
        },
    }


async def _post_to_oneiric(payload: dict[str, Any], url: str, tool_name: str) -> None:
    """POST the JSON-RPC payload to Oneiric and validate the response.

    Raises on transport errors, non-2xx responses, or malformed JSON
    so the caller's except-block can log ``status=fail`` cleanly.
    """
    import httpx2 as httpx

    async with httpx.AsyncClient(timeout=PUSH_TIMEOUT_SECONDS) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"oneiric returned non-JSON body (tool={tool_name}): {exc}"
            ) from exc
        if isinstance(body, dict) and body.get("error"):
            raise RuntimeError(f"oneiric rpc error: {body.get('error')!r}")


async def _push_async(
    app: FastMCP,
    url: str,
    tool_name: str,
) -> bool:
    """Async body: enumerate tools, wrap, POST. Returns True on success."""
    from crackerjack.core.runtime_facts import RuntimeFactsBuilder

    facts = RuntimeFactsBuilder(app).build_all()
    envelope = _build_envelope(component="crackerjack", runtime_facts=facts)
    payload = _build_jsonrpc_payload(envelope, tool_name=tool_name)
    await _post_to_oneiric(payload, url=url, tool_name=tool_name)
    return True


def report_runtime_to_oneiric(
    app: FastMCP,
    *,
    url: str = ONEIRIC_DEFAULT_URL,
    tool_name: str = ONEIRIC_DEFAULT_TOOL,
) -> None:
    """Fire-and-forget push of the FastMCP tool registry to Oneiric.

    The entire body is wrapped in try/except — Oneiric unavailability
    MUST NOT block Crackerjack boot. Logs at WARNING level on failure.

    The async helper runs on a daemon thread so the synchronous
    main() boot path can return immediately. The thread terminates
    when the asyncio.run coroutine completes (success or failure).
    """
    thread = threading.Thread(
        target=_run_in_thread,
        args=(app, url, tool_name),
        name=DAEMON_THREAD_NAME,
        daemon=True,
    )
    thread.start()


def _run_in_thread(app: FastMCP, url: str, tool_name: str) -> None:
    """Thread entry point: run the async push and swallow all errors."""
    try:
        asyncio.run(_push_async(app, url=url, tool_name=tool_name))
        logger.info(
            "runtime-push component=crackerjack adapter=%s status=ok",
            tool_name,
        )
    except Exception as exc:
        logger.warning(
            "runtime-push component=crackerjack adapter=%s status=fail reason=%s",
            tool_name,
            exc,
        )

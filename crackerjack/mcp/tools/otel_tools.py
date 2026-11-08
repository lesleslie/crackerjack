from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_otel_tools(mcp_app: Any) -> None:
    _register_query_local_traces(mcp_app)
    logger.info("Registered OTel trace query tools")


def _get_akosha_endpoint() -> str:
    import os

    return os.environ.get("AKOSHA_MCP_ENDPOINT", "http://localhost:8682")


async def _call_akosha_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: int = 30,
) -> list[dict[str, Any]]:
    import httpx2 as httpx

    endpoint = _get_akosha_endpoint()
    base_url = endpoint.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.post(
                f"{base_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict):
                result = data.get("result", {})
                if isinstance(result, dict):
                    content = result.get("content", [])
                    if isinstance(content, list):
                        return content
            return []

    except httpx.HTTPError as e:
        logger.warning(f"HTTP error calling Akosha {tool_name}: {e}")
        return []
    except Exception as e:
        logger.warning(f"Error calling Akosha {tool_name}: {e}")
        return []


def _register_query_local_traces(mcp_app: Any) -> None:
    @mcp_app.tool()
    async def query_local_traces(
        task_class: str,
        system_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        limit: int = 100,
        dry_run: bool = False,
    ) -> list[dict[str, Any]]:
        """Query OpenTelemetry traces for a task class from the fleet trace store.

        Returns a list of trace records; an empty list means no trace matched
        the filter. Do NOT use to fetch one trace by id — use `get_otel_trace`
        on Mahavishnu for that. Returns an empty list when the trace store is
        unreachable or when `task_class` matches nothing, so an empty result
        does not distinguish "no matches" from "query failed". Filter by an
        absolute ISO8601 window with `start_time` and `end_time`; omit both to
        search all history. Set `dry_run` to get the raw stored metadata
        instead of the full record; that mode caps results at 20 and keeps
        your `system_id` and `task_class` filters in force. Side effect: none;
        reads the trace store only.
        """
        # Implements: REQ-MCPTD-001, REQ-MCPTD-003
        try:
            arguments: dict[str, Any] = {
                "task_class": task_class,
                "limit": limit,
                "dry_run": dry_run,
            }
            if system_id is not None:
                arguments["system_id"] = system_id
            if start_time is not None:
                arguments["start_time"] = start_time
            if end_time is not None:
                arguments["end_time"] = end_time

            results = await _call_akosha_mcp_tool(
                "query_local_traces",
                arguments,
            )

            logger.info(
                "query_local_traces: task_class=%s matched=%d",
                task_class,
                len(results),
            )
            return results

        except Exception as e:
            logger.exception("Error querying traces: %s", e)
            return []

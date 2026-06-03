from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_otel_tools(mcp_app: Any) -> None:
    _register_query_local_traces(mcp_app)
    logger.info("Registered OTel trace query tools")


def _get_akosha_endpoint() -> str:
    import os

    return os.environ.get("AKOSHA_MCP_ENDPOINT", "http://localhost: 8682")


async def _call_akosha_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: int = 30,
) -> list[dict[str, Any]]:
    import httpx

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
        time_range_minutes: int = 60,
        system_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        try:
            arguments: dict[str, Any] = {
                "task_class": task_class,
                "time_range_minutes": time_range_minutes,
                "limit": limit,
            }
            if system_id is not None:
                arguments["system_id"] = system_id

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

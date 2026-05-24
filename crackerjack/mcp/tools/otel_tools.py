"""OTel trace query tools for Crackerjack.

This module provides an MCP tool for querying OTel traces by delegating
to Akosha's query_local_traces MCP endpoint. Crackerjack does not have
its own HotStore — it routes trace queries to Akosha via HTTP.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_otel_tools(mcp_app: Any) -> None:
    """Register OTel trace query tools with the MCP server.

    Args:
        mcp_app: FastMCP application instance
    """
    _register_query_local_traces(mcp_app)
    logger.info("Registered OTel trace query tools")


def _get_akosha_endpoint() -> str:
    """Get Akosha MCP endpoint from environment or default.

    Returns:
        Akosha MCP server URL (e.g. 'http://localhost:8682')
    """
    import os

    return os.environ.get("AKOSHA_MCP_ENDPOINT", "http://localhost:8682")


async def _call_akosha_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    timeout_seconds: int = 30,
) -> list[dict[str, Any]]:
    """Call a tool on Akosha's MCP HTTP endpoint.

    Args:
        tool_name: Name of the MCP tool to call
        arguments: Tool arguments as a dictionary
        timeout_seconds: HTTP request timeout

    Returns:
        List of result records from Akosha
    """
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

            # Parse JSON-RPC 2.0 response
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
        system_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
        task_class: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query OTel traces by system_id and optional attribute filters.

        Delegates to Akosha's query_local_traces MCP endpoint.
        Fetches traces for a given system_id within an optional time range,
        and optionally filtered by task.class attribute.

        Args:
            system_id: Source system identifier (e.g., 'mahavishnu', 'akosha')
            start_time: ISO8601 start time (optional)
            end_time: ISO8601 end time (optional)
            task_class: Task classification tag to filter on (optional)
            limit: Maximum number of traces to return (default 100)

        Returns:
            List of trace records matching the filter criteria
        """
        try:
            arguments: dict[str, Any] = {
                "system_id": system_id,
                "limit": limit,
            }
            if start_time is not None:
                arguments["start_time"] = start_time
            if end_time is not None:
                arguments["end_time"] = end_time
            if task_class is not None:
                arguments["task_class"] = task_class

            results = await _call_akosha_mcp_tool(
                "query_local_traces",
                arguments,
            )

            # Results from Akosha are already filtered lists
            logger.info(
                f"query_local_traces: system={system_id}, matched={len(results)}"
            )
            return results

        except Exception as e:
            logger.exception(f"Error querying traces: {e}")
            return []

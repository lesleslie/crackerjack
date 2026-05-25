
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
        system_id: str,
        start_time: str | None = None,
        end_time: str | None = None,
        task_class: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
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


            logger.info(
                f"query_local_traces: system={system_id}, matched={len(results)}"
            )
            return results

        except Exception as e:
            logger.exception(f"Error querying traces: {e}")
            return []

#!/usr/bin/env python3
import asyncio

from session_mgmt_mcp.server import mcp


async def show_tools():
    tools = await mcp.get_tools()
    print(f"Total tools: {len(tools)}")
    for i, tool_name in enumerate(list(tools)[:20]):
        print(f"{i + 1}. {tool_name}")


if __name__ == "__main__":
    asyncio.run(show_tools())

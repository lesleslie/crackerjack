from .server_core import (
    MCP_AVAILABLE,
    MCPOptions,
    MCPServerService,
    create_mcp_server,
    main,
)

__all__ = [
    "MCP_AVAILABLE",
    "MCPOptions",
    "MCPServerService",
    "create_mcp_server",
    "main",
]


if __name__ == "__main__":
    import sys

    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    websocket_port = int(sys.argv[2]) if len(sys.argv) > 2 else None

    main(project_path, websocket_port)

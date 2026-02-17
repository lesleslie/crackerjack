from .server_core import (
    MCP_AVAILABLE,
    MCPOptions,
    create_mcp_server,
    main,
)

__all__ = [
    "MCP_AVAILABLE",
    "MCPOptions",
    "create_mcp_server",
    "main",
]


if __name__ == "__main__":
    import sys

    project_path = sys.argv[1] if len(sys.argv) > 1 else "."

    main(project_path)

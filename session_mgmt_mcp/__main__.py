#!/usr/bin/env python3
"""Session Management MCP Server - Module Entry Point.

Allows running the server as: python -m session-mgmt-mcp --start-server
"""

import argparse


def main() -> None:
    """Main entry point for the session management MCP server."""
    parser = argparse.ArgumentParser(
        description="Session Management MCP Server",
        prog="session-mgmt-mcp",
    )

    parser.add_argument(
        "--start-server",
        action="store_true",
        help="Start the MCP server for session management",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information",
    )

    args = parser.parse_args()

    if args.version:
        print("Session Management MCP Server v2.0.0")
        return

    if args.start_server:
        # Import and run the server
        from .server import main as server_main

        server_main()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

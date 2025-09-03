"""Claude Session Management MCP Server.

A dedicated MCP server that provides session management functionality
including initialization, checkpoints, and cleanup across all projects.
"""

__version__ = "0.1.0"
__author__ = "Les Leslie"
__email__ = "les@wedgwoodwebworks.com"

from .server import mcp

__all__ = ["mcp"]

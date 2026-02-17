"""MCP tools for workspace management."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mcp.server import FastMCP
from pydantic import Field, validate_call

from crackerjack.mahavishnu.workspace import get_manager

logger = logging.getLogger(__name__)

mcp = FastMCP("crackerjack-workspace")


def register_workspace_tools(mcp_app: FastMCP) -> None:
    """Register workspace tools with MCP server."""
    mcp_app.tool()(create_workspace)
    mcp_app.tool()(list_workspaces)
    mcp_app.tool()(get_workspace_info)
    mcp_app.tool()(remove_workspace)


@mcp.tool()
@validate_call
def create_workspace(
    name: str,
    repos: list[str] | None = Field(
        default=None, description="List of repository paths to include"
    ),
    branch: str | None = Field(
        default=None, description="Branch name (default: <workspace-name>)"
    ),
    create_branch: bool = Field(
        default=True, description="Whether to create new branch"
    ),
) -> dict[str, Any]:
    """Create a new workspace with git worktrees.

    Args:
        name: Workspace name
        repos: List of repository paths to include
        branch: Branch name (default: workspace name)
        create_branch: Whether to create new branch

    Returns:
        Dict with workspace info including 'repos' list
    """
    manager = get_manager()

    result = asyncio.run(
        manager.create_workspace(
            name=name,
            repos=repos,
            branch=branch,
            create_branch=create_branch,
        )
    )

    logger.info(f"Created workspace: {result['name']}")
    return result


@mcp.tool()
@validate_call
def list_workspaces(
    active_only: bool = Field(
        default=False, description="Only show workspaces with uncommitted changes"
    ),
) -> list[dict[str, Any]]:
    """List all workspaces.

    Args:
        active_only: Only show workspaces with uncommitted changes

    Returns:
        List of workspace info dicts
    """
    manager = get_manager()

    workspaces = asyncio.run(manager.list_workspaces(active_only=active_only))

    logger.info(f"Listed {len(workspaces)} workspaces")
    return workspaces


@mcp.tool()
@validate_call
def get_workspace_info(
    name: str,
) -> dict[str, Any]:
    """Get detailed information about a workspace.

    Args:
        name: Workspace name

    Returns:
        Dict with workspace details
    """
    manager = get_manager()

    info = asyncio.run(manager.get_workspace_info(name))

    logger.info(f"Retrieved info for workspace: {name}")
    return info


@mcp.tool()
@validate_call
def remove_workspace(
    name: str,
    force: bool = Field(
        default=False, description="Remove even if uncommitted changes exist"
    ),
) -> dict[str, Any]:
    """Remove a workspace and its worktrees.

    Args:
        name: Workspace name
        force: Remove even if uncommitted changes exist

    Returns:
        Dict with removal results
    """
    manager = get_manager()

    result = asyncio.run(manager.remove_workspace(name, force=force))

    logger.info(f"Removed workspace: {name}")
    return result

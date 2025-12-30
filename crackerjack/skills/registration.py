"""
Skill Registration Module

Coordinates registration of all skill types with the MCP server.
This is the main entry point for enabling Crackerjack's skill system.

Usage:
    from crackerjack.skills import register_all_skills

    # In MCP server initialization
    register_all_skills(mcp_app, context)
"""

import typing as t
from pathlib import Path

from crackerjack.agents.base import AgentContext
from crackerjack.skills.agent_skills import AgentSkillRegistry
from crackerjack.skills.hybrid_skills import HybridSkillRegistry
from crackerjack.skills.mcp_skills import MCP_SKILL_GROUPS, MCPSkillRegistry


def register_agent_skills(
    context: AgentContext,
) -> AgentSkillRegistry:
    """
    Register all agent capabilities as skills.

    Args:
        context: AgentContext for agent initialization

    Returns:
        Populated AgentSkillRegistry
    """
    registry = AgentSkillRegistry()
    registry.register_all_agents(context)
    return registry


def register_mcp_skills() -> MCPSkillRegistry:
    """
    Register all MCP tool groups as skills.

    Returns:
        Populated MCPSkillRegistry
    """
    registry = MCPSkillRegistry()

    # Register all predefined skill groups
    for skill_data in MCP_SKILL_GROUPS.values():
        registry.register_skill_group(skill_data)

    return registry


def register_hybrid_skills(
    context: AgentContext,
    mcp_app: t.Any | None = None,
) -> HybridSkillRegistry:
    """
    Register all agents as hybrid skills with MCP tool integration.

    Args:
        context: AgentContext for agent initialization
        mcp_app: Optional MCP app for tool registration

    Returns:
        Populated HybridSkillRegistry
    """
    registry = HybridSkillRegistry()

    if mcp_app is not None:
        registry.register_mcp_app(mcp_app)

    registry.register_all_hybrid_skills(context)
    return registry


def register_all_skills(
    mcp_app: t.Any,
    context: AgentContext,
    enable_agent_skills: bool = True,
    enable_mcp_skills: bool = True,
    enable_hybrid_skills: bool = True,
) -> dict[str, t.Any]:
    """
    Register all skill types with the MCP server.

    This is the main entry point for enabling Crackerjack's skill system.
    Call this during MCP server initialization.

    Args:
        mcp_app: MCP application instance
        context: AgentContext for agent initialization
        enable_agent_skills: Enable agent capability skills
        enable_mcp_skills: Enable MCP tool grouping skills
        enable_hybrid_skills: Enable hybrid agent+tool skills

    Returns:
        Dictionary with all registries and statistics
    """
    registries = {}

    # Register agent skills (Option 1)
    if enable_agent_skills:
        agent_registry = register_agent_skills(context)
        registries["agent_skills"] = agent_registry

    # Register MCP skills (Option 2)
    if enable_mcp_skills:
        mcp_registry = register_mcp_skills()
        registries["mcp_skills"] = mcp_registry

    # Register hybrid skills (Option 3)
    if enable_hybrid_skills:
        hybrid_registry = register_hybrid_skills(context, mcp_app)
        registries["hybrid_skills"] = hybrid_registry

        # Register MCP tools from hybrid skills
        _register_hybrid_tools(hybrid_registry, mcp_app)

    return registries


def _register_hybrid_tools(
    hybrid_registry: HybridSkillRegistry,
    mcp_app: t.Any,
) -> None:
    """
    Register hybrid skill tools with MCP app.

    Note: FastMCP doesn't support dynamic tool registration via add_tool() method.
    Hybrid skills are accessible through the 8 skill management tools instead.
    This function is a no-op but kept for API compatibility.

    Args:
        hybrid_registry: HybridSkillRegistry with tool definitions
        mcp_app: MCP application instance (not used for hybrid skills)
    """
    # FastMCP uses @mcp_app.tool() decorator pattern, not dynamic add_tool()
    # Hybrid skills remain accessible via the 8 skill management tools:
    # - list_skills, get_skill_info, search_skills, get_skills_for_issue
    # - get_skill_statistics, execute_skill, find_best_skill
    # The hybrid skill tool definitions exist but aren't registered as separate MCP tools
    pass


def get_skill_summary(
    registries: dict[str, t.Any],
) -> dict[str, t.Any]:
    """
    Get summary statistics from all registries.

    Args:
        registries: Dictionary of registries from register_all_skills

    Returns:
        Summary statistics
    """
    summary = {}

    if "agent_skills" in registries:
        summary["agent_skills"] = registries["agent_skills"].get_statistics()

    if "mcp_skills" in registries:
        summary["mcp_skills"] = registries["mcp_skills"].get_statistics()

    if "hybrid_skills" in registries:
        hybrid_registry = registries["hybrid_skills"]
        summary["hybrid_skills"] = {
            **hybrid_registry.get_statistics(),
            "tools": hybrid_registry.get_tool_statistics(),
        }

    return summary


def create_agent_context(
    project_path: Path | str,
    temp_dir: Path | str | None = None,
    subprocess_timeout: int = 300,
    max_file_size: int = 10_000_000,
    config: dict[str, t.Any] | None = None,
) -> AgentContext:
    """
    Create an AgentContext for skill registration.

    Args:
        project_path: Path to project directory
        temp_dir: Optional temporary directory
        subprocess_timeout: Subprocess timeout in seconds
        max_file_size: Maximum file size for operations
        config: Optional configuration dictionary

    Returns:
        AgentContext instance
    """
    return AgentContext(
        project_path=Path(project_path),
        temp_dir=Path(temp_dir) if temp_dir else None,
        subprocess_timeout=subprocess_timeout,
        max_file_size=max_file_size,
        config=config or {},
    )

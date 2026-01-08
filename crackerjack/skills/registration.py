import typing as t
from pathlib import Path

from crackerjack.agents.base import AgentContext
from crackerjack.skills.agent_skills import AgentSkillRegistry
from crackerjack.skills.hybrid_skills import HybridSkillRegistry
from crackerjack.skills.mcp_skills import MCP_SKILL_GROUPS, MCPSkillRegistry


def register_agent_skills(
    context: AgentContext,
) -> AgentSkillRegistry:
    registry = AgentSkillRegistry()
    registry.register_all_agents(context)
    return registry


def register_mcp_skills() -> MCPSkillRegistry:
    registry = MCPSkillRegistry()

    for skill_data in MCP_SKILL_GROUPS.values():
        registry.register_skill_group(skill_data)

    return registry


def register_hybrid_skills(
    context: AgentContext,
    mcp_app: t.Any | None = None,
) -> HybridSkillRegistry:
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
) -> dict[str, AgentSkillRegistry | MCPSkillRegistry | HybridSkillRegistry]:
    registries: dict[
        str, AgentSkillRegistry | MCPSkillRegistry | HybridSkillRegistry
    ] = {}

    if enable_agent_skills:
        agent_registry = register_agent_skills(context)
        registries["agent_skills"] = agent_registry

    if enable_mcp_skills:
        mcp_registry = register_mcp_skills()
        registries["mcp_skills"] = mcp_registry

    if enable_hybrid_skills:
        hybrid_registry = register_hybrid_skills(context, mcp_app)
        registries["hybrid_skills"] = hybrid_registry

        _register_hybrid_tools(hybrid_registry, mcp_app)

    return registries


def _register_hybrid_tools(
    hybrid_registry: HybridSkillRegistry,
    mcp_app: t.Any,
) -> None:
    pass


def get_skill_summary(
    registries: dict[str, t.Any],
) -> dict[str, t.Any]:
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
    return AgentContext(
        project_path=Path(project_path),
        temp_dir=Path(temp_dir) if temp_dir else None,
        subprocess_timeout=subprocess_timeout,
        max_file_size=max_file_size,
        config=config or {},
    )

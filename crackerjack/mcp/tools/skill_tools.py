"""
Skill Tools for MCP Server

Exposes Crackerjack's agent skills as MCP tools.
This provides a discoverable interface to all agent capabilities.

Key Features:
- List all available skills (agent, MCP, hybrid)
- Get detailed information about specific skills
- Execute skills via MCP tools
- Search skills by category, type, or query
"""

import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


# Global registries (initialized during server startup)
_skill_registries: dict[str, t.Any] = {}
_project_path: Path | None = None


def initialize_skills(
    project_path: Path,
    mcp_app: "FastMCP",
) -> dict[str, t.Any]:
    """
    Initialize all skill registries.

    Called during MCP server startup to set up the skill system.

    Args:
        project_path: Path to project directory
        mcp_app: FastMCP application instance

    Returns:
        Dictionary of skill registries
    """
    global _skill_registries, _project_path

    _project_path = project_path

    try:
        # Import all agent modules to trigger registration
        # This is needed because agents use lazy imports
        import crackerjack.agents.architect_agent  # noqa: F401
        import crackerjack.agents.documentation_agent  # noqa: F401
        import crackerjack.agents.dry_agent  # noqa: F401
        import crackerjack.agents.formatting_agent  # noqa: F401
        import crackerjack.agents.import_optimization_agent  # noqa: F401
        import crackerjack.agents.performance_agent  # noqa: F401
        import crackerjack.agents.refactoring_agent  # noqa: F401
        import crackerjack.agents.security_agent  # noqa: F401
        import crackerjack.agents.semantic_agent  # noqa: F401
        import crackerjack.agents.test_creation_agent  # noqa: F401
        import crackerjack.agents.test_specialist_agent  # noqa: F401
        from crackerjack.agents.base import AgentContext
        from crackerjack.skills import register_all_skills

        # Create agent context
        context = AgentContext(project_path=project_path)

        # Register all skills
        _skill_registries = register_all_skills(
            mcp_app=mcp_app,
            context=context,
            enable_agent_skills=True,
            enable_mcp_skills=True,
            enable_hybrid_skills=True,
        )

        return _skill_registries

    except Exception as e:
        # Don't fail server startup if skills fail to initialize
        print(f"Warning: Failed to initialize skills: {e}")
        return {}


def get_registries() -> dict[str, t.Any]:
    """Get global skill registries."""
    return _skill_registries


def register_skill_tools(mcp_app: "FastMCP") -> None:
    """
    Register skill-related MCP tools.

    Args:
        mcp_app: FastMCP application instance
    """
    _register_list_skills(mcp_app)
    _register_get_skill_info(mcp_app)
    _register_search_skills(mcp_app)
    _register_get_skills_for_issue(mcp_app)
    _register_get_skill_statistics(mcp_app)
    _register_execute_skill(mcp_app)
    _register_find_best_skill(mcp_app)


def _register_list_skills(mcp_app: "FastMCP") -> None:
    """Register the list_skills tool."""

    @mcp_app.tool(
        name="list_skills",
        description="List all available Crackerjack skills (agent, MCP, hybrid)",
    )
    async def list_skills(
        skill_type: str = "all",
    ) -> dict[str, t.Any]:
        """
        List all available skills.

        Args:
            skill_type: Type of skills to list ("all", "agent", "mcp", "hybrid")

        Returns:
            Dictionary with skills grouped by type
        """
        result = {}

        if skill_type in ("all", "agent"):
            if "agent_skills" in _skill_registries:
                result["agent_skills"] = _skill_registries[
                    "agent_skills"
                ].list_all_skills()

        if skill_type in ("all", "mcp"):
            if "mcp_skills" in _skill_registries:
                result["mcp_skills"] = _skill_registries["mcp_skills"].list_all_skills()

        if skill_type in ("all", "hybrid"):
            if "hybrid_skills" in _skill_registries:
                result["hybrid_skills"] = _skill_registries[
                    "hybrid_skills"
                ].list_all_skills()

        return result


def _register_get_skill_info(mcp_app: "FastMCP") -> None:
    """Register the get_skill_info tool."""

    @mcp_app.tool(
        name="get_skill_info",
        description="Get detailed information about a specific skill",
    )
    async def get_skill_info(
        skill_id: str,
        skill_type: str = "agent",
    ) -> dict[str, t.Any]:
        """
        Get detailed information about a skill.

        Args:
            skill_id: ID of the skill
            skill_type: Type of skill ("agent", "mcp", "hybrid")

        Returns:
            Detailed skill information
        """
        registry_key = f"{skill_type}_skills"

        if registry_key not in _skill_registries:
            return {"error": f"Unknown skill type: {skill_type}"}

        registry = _skill_registries[registry_key]

        if skill_type == "agent":
            skill = registry.get_skill(skill_id)
            return skill.get_info() if skill else {"error": "Skill not found"}

        elif skill_type == "mcp":
            skill = registry.get_skill(skill_id)
            return skill.to_dict() if skill else {"error": "Skill not found"}

        elif skill_type == "hybrid":
            skill = registry.get_skill(skill_id)
            if skill:
                info = skill.get_info()
                # Add tool mappings
                if hasattr(skill, "get_tool_mappings"):
                    info["tools"] = [m.to_dict() for m in skill.get_tool_mappings()]
                return info
            else:
                return {"error": "Skill not found"}

        else:
            return {"error": f"Unknown skill type: {skill_type}"}


def _register_search_skills(mcp_app: "FastMCP") -> None:
    """Register the search_skills tool."""

    @mcp_app.tool(
        name="search_skills",
        description="Search for skills by query, category, or issue type",
    )
    async def search_skills(
        query: str,
        search_in: str = "all",
    ) -> dict[str, t.Any]:
        """
        Search for skills matching a query.

        Args:
            query: Search query
            search_in: Where to search ("all", "names", "descriptions", "tags")

        Returns:
            List of matching skills
        """
        results = {}

        # Search agent skills
        if "agent_skills" in _skill_registries:
            results["agent_skills"] = _search_agent_skills(query, search_in)

        # Search MCP skills
        if "mcp_skills" in _skill_registries:
            results["mcp_skills"] = _search_mcp_skills(query, search_in)

        # Search hybrid skills
        if "hybrid_skills" in _skill_registries:
            results["hybrid_skills"] = _search_hybrid_skills(query, search_in)

        return results


def _search_agent_skills(query: str, search_in: str) -> list[dict[str, t.Any]]:
    """Search for agent skills."""
    agent_skills = _skill_registries["agent_skills"]
    matching = []

    for skill_info in agent_skills.list_all_skills():
        metadata = skill_info["metadata"]

        # Search in names
        if search_in in ("all", "names"):
            if query.lower() in metadata["name"].lower():
                matching.append(skill_info)
                continue

        # Search in descriptions
        if search_in in ("all", "descriptions"):
            if query.lower() in metadata["description"].lower():
                matching.append(skill_info)
                continue

        # Search in tags
        if search_in in ("all", "tags"):
            if any(query.lower() in tag.lower() for tag in metadata.get("tags", [])):
                matching.append(skill_info)
                continue

    return matching


def _search_mcp_skills(query: str, search_in: str) -> list[dict[str, t.Any]]:
    """Search for MCP skills."""
    mcp_skills = _skill_registries["mcp_skills"]
    matching = mcp_skills.search_skills(
        query,
        search_names=search_in in ("all", "names"),
        search_tags=search_in in ("all", "tags"),
        search_descriptions=search_in in ("all", "descriptions"),
    )
    return [s.to_dict() for s in matching]


def _search_hybrid_skills(query: str, search_in: str) -> list[dict[str, t.Any]]:
    """Search for hybrid skills."""
    hybrid_skills = _skill_registries["hybrid_skills"]
    matching = []

    for skill_info in hybrid_skills.list_all_skills():
        metadata = skill_info["metadata"]

        if search_in in ("all", "names"):
            if query.lower() in metadata["name"].lower():
                matching.append(skill_info)
                continue

        if search_in in ("all", "descriptions"):
            if query.lower() in metadata["description"].lower():
                matching.append(skill_info)
                continue

        if search_in in ("all", "tags"):
            if any(query.lower() in tag.lower() for tag in metadata.get("tags", [])):
                matching.append(skill_info)
                continue

    return matching


def _register_get_skills_for_issue(mcp_app: "FastMCP") -> None:
    """Register the get_skills_for_issue tool."""

    @mcp_app.tool(
        name="get_skills_for_issue",
        description="Get skills that can handle a specific issue type",
    )
    async def get_skills_for_issue(
        issue_type: str,
    ) -> dict[str, t.Any]:
        """
        Get skills that can handle a specific issue type.

        Args:
            issue_type: Type of issue (e.g., "complexity", "security", "type_error")

        Returns:
            List of skills that can handle the issue type
        """
        from crackerjack.agents.base import IssueType

        # Parse issue type
        try:
            issue_enum = IssueType(issue_type)
        except ValueError:
            return {"error": f"Unknown issue type: {issue_type}"}

        result = {}

        # Get agent skills
        if "agent_skills" in _skill_registries:
            agent_skills = _skill_registries["agent_skills"]
            skills = agent_skills.get_skills_for_type(issue_enum)
            result["agent_skills"] = [s.get_info() for s in skills]

        # Get hybrid skills
        if "hybrid_skills" in _skill_registries:
            hybrid_skills = _skill_registries["hybrid_skills"]
            skills = hybrid_skills.get_skills_for_type(issue_enum)
            result["hybrid_skills"] = [s.get_info() for s in skills]

        return result


def _register_get_skill_statistics(mcp_app: "FastMCP") -> None:
    """Register the get_skill_statistics tool."""

    @mcp_app.tool(
        name="get_skill_statistics",
        description="Get statistics about all skill registries",
    )
    async def get_skill_statistics() -> dict[str, t.Any]:
        """
        Get statistics about all skill registries.

        Returns:
            Dictionary with statistics for each skill type
        """
        result = {}

        if "agent_skills" in _skill_registries:
            result["agent_skills"] = _skill_registries["agent_skills"].get_statistics()

        if "mcp_skills" in _skill_registries:
            result["mcp_skills"] = _skill_registries["mcp_skills"].get_statistics()

        if "hybrid_skills" in _skill_registries:
            hybrid_skills = _skill_registries["hybrid_skills"]
            stats = hybrid_skills.get_statistics()
            stats["tools"] = hybrid_skills.get_tool_statistics()
            result["hybrid_skills"] = stats

        return result


def _register_execute_skill(mcp_app: "FastMCP") -> None:
    """Register the execute_skill tool."""

    @mcp_app.tool(
        name="execute_skill",
        description="Execute a skill on an issue (hybrid skills only)",
    )
    async def execute_skill(
        skill_id: str,
        issue_type: str,
        issue_data: dict[str, t.Any],
        timeout: int | None = None,
    ) -> dict[str, t.Any]:
        """
        Execute a skill on an issue.

        Args:
            skill_id: ID of the skill to execute
            issue_type: Type of issue
            issue_data: Issue data (message, file_path, line_number, etc.)
            timeout: Optional timeout in seconds

        Returns:
            Execution result
        """
        from crackerjack.agents.base import Issue, IssueType, Priority

        if "hybrid_skills" not in _skill_registries:
            return {"error": "Hybrid skills not initialized"}

        registry = _skill_registries["hybrid_skills"]
        skill = registry.get_skill(skill_id)

        if not skill:
            return {"error": f"Skill not found: {skill_id}"}

        # Create issue
        try:
            issue_enum = IssueType(issue_type)
        except ValueError:
            return {"error": f"Unknown issue type: {issue_type}"}

        issue = Issue(
            type=issue_enum,
            severity=Priority.MEDIUM,
            message=issue_data.get("message", "Issue from tool invocation"),
            file_path=issue_data.get("file_path"),
            line_number=issue_data.get("line_number"),
            details=issue_data.get("details", []),
        )

        # Execute skill
        try:
            result = await skill.execute(issue, timeout=timeout)
            return result.to_dict()
        except Exception as e:
            return {
                "error": f"Skill execution failed: {e}",
                "skill_id": skill_id,
                "success": False,
            }


def _register_find_best_skill(mcp_app: "FastMCP") -> None:
    """Register the find_best_skill tool."""

    @mcp_app.tool(
        name="find_best_skill",
        description="Find the best skill for handling an issue",
    )
    async def find_best_skill(
        issue_type: str,
    ) -> dict[str, t.Any]:
        """
        Find the best skill for handling an issue.

        Args:
            issue_type: Type of issue

        Returns:
            Best skill for the issue type
        """
        from crackerjack.agents.base import Issue, IssueType, Priority

        if "hybrid_skills" not in _skill_registries:
            return {"error": "Hybrid skills not initialized"}

        registry = _skill_registries["hybrid_skills"]

        # Create dummy issue for matching
        try:
            issue_enum = IssueType(issue_type)
        except ValueError:
            return {"error": f"Unknown issue type: {issue_type}"}

        issue = Issue(
            type=issue_enum,
            severity=Priority.MEDIUM,
            message="Finding best skill",
        )

        # Find best skill
        try:
            best_skill = await registry.find_best_skill(issue)
            if best_skill:
                info = best_skill.get_info()
                # Add tool mappings
                if hasattr(best_skill, "get_tool_mappings"):
                    info["tools"] = [
                        m.to_dict() for m in best_skill.get_tool_mappings()
                    ]
                return info
            else:
                return {"error": "No skill found for this issue type"}
        except Exception as e:
            return {"error": f"Failed to find best skill: {e}"}

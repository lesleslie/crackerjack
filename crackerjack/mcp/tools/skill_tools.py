import typing as t
from pathlib import Path

if t.TYPE_CHECKING:
    from fastmcp import FastMCP


_skill_registries: dict[str, t.Any] = {}
_project_path: Path | None = None


def initialize_skills(
    project_path: Path,
    mcp_app: "FastMCP",
) -> dict[str, t.Any]:
    global _skill_registries, _project_path

    _project_path = project_path

    try:
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

        context = AgentContext(project_path=project_path)

        _skill_registries = register_all_skills(
            mcp_app=mcp_app,
            context=context,
            enable_agent_skills=True,
            enable_mcp_skills=True,
            enable_hybrid_skills=True,
        )

        return _skill_registries

    except Exception as e:
        print(f"Warning: Failed to initialize skills: {e}")
        return {}


def get_registries() -> dict[str, t.Any]:
    return _skill_registries


def register_skill_tools(mcp_app: "FastMCP") -> None:
    _register_list_skills(mcp_app)
    _register_get_skill_info(mcp_app)
    _register_search_skills(mcp_app)
    _register_get_skills_for_issue(mcp_app)
    _register_get_skill_statistics(mcp_app)
    _register_execute_skill(mcp_app)
    _register_find_best_skill(mcp_app)


def _register_list_skills(mcp_app: "FastMCP") -> None:
    @mcp_app.tool(
        name="list_skills",
        description="List all available Crackerjack skills (agent, MCP, hybrid)",
    )
    async def list_skills(
        skill_type: str = "all",
    ) -> dict[str, t.Any]:
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
    @mcp_app.tool(
        name="get_skill_info",
        description="Get detailed information about a specific skill",
    )
    async def get_skill_info(
        skill_id: str,
        skill_type: str = "agent",
    ) -> dict[str, t.Any]:
        registry = _get_skill_registry(skill_type)
        if registry is None:
            return {"error": f"Unknown skill type: {skill_type}"}

        skill = registry.get_skill(skill_id)
        if not skill:
            return {"error": "Skill not found"}

        return _format_skill_info(skill, skill_type)


def _get_skill_registry(skill_type: str) -> t.Any | None:
    registry_key = f"{skill_type}_skills"
    return _skill_registries.get(registry_key)


def _format_skill_info(skill: t.Any, skill_type: str) -> dict[str, t.Any]:
    if skill_type == "agent":
        return skill.get_info()

    elif skill_type == "mcp":
        return skill.to_dict()

    elif skill_type == "hybrid":
        info = skill.get_info()

        if hasattr(skill, "get_tool_mappings"):
            info["tools"] = [m.to_dict() for m in skill.get_tool_mappings()]
        return info

    return {"error": f"Unknown skill type: {skill_type}"}


def _register_search_skills(mcp_app: "FastMCP") -> None:
    @mcp_app.tool(
        name="search_skills",
        description="Search for skills by query, category, or issue type",
    )
    async def search_skills(
        query: str,
        search_in: str = "all",
    ) -> dict[str, t.Any]:
        results = {}

        if "agent_skills" in _skill_registries:
            results["agent_skills"] = _search_agent_skills(query, search_in)

        if "mcp_skills" in _skill_registries:
            results["mcp_skills"] = _search_mcp_skills(query, search_in)

        if "hybrid_skills" in _skill_registries:
            results["hybrid_skills"] = _search_hybrid_skills(query, search_in)

        return results


def _search_agent_skills(query: str, search_in: str) -> list[dict[str, t.Any]]:
    agent_skills = _skill_registries["agent_skills"]

    return [
        skill_info
        for skill_info in agent_skills.list_all_skills()
        if _matches_search_criteria(skill_info["metadata"], query, search_in)
    ]


def _matches_search_criteria(
    metadata: dict[str, t.Any], query: str, search_in: str
) -> bool:
    if search_in in ("all", "names"):
        if query.lower() in metadata["name"].lower():
            return True

    if search_in in ("all", "descriptions"):
        if query.lower() in metadata["description"].lower():
            return True

    if search_in in ("all", "tags"):
        if _matches_tags(metadata.get("tags", []), query):
            return True

    return False


def _matches_tags(tags: list[str], query: str) -> bool:
    return any(query.lower() in tag.lower() for tag in tags)


def _search_mcp_skills(query: str, search_in: str) -> list[dict[str, t.Any]]:
    mcp_skills = _skill_registries["mcp_skills"]
    matching = mcp_skills.search_skills(
        query,
        search_names=search_in in ("all", "names"),
        search_tags=search_in in ("all", "tags"),
        search_descriptions=search_in in ("all", "descriptions"),
    )
    return [s.to_dict() for s in matching]


def _search_hybrid_skills(query: str, search_in: str) -> list[dict[str, t.Any]]:
    hybrid_skills = _skill_registries["hybrid_skills"]

    return [
        skill_info
        for skill_info in hybrid_skills.list_all_skills()
        if _matches_search_criteria(skill_info["metadata"], query, search_in)
    ]


def _register_get_skills_for_issue(mcp_app: "FastMCP") -> None:
    @mcp_app.tool(
        name="get_skills_for_issue",
        description="Get skills that can handle a specific issue type",
    )
    async def get_skills_for_issue(
        issue_type: str,
    ) -> dict[str, t.Any]:
        from crackerjack.agents.base import IssueType

        try:
            issue_enum = IssueType(issue_type)
        except ValueError:
            return {"error": f"Unknown issue type: {issue_type}"}

        result = {}

        if "agent_skills" in _skill_registries:
            agent_skills = _skill_registries["agent_skills"]
            skills = agent_skills.get_skills_for_type(issue_enum)
            result["agent_skills"] = [s.get_info() for s in skills]

        if "hybrid_skills" in _skill_registries:
            hybrid_skills = _skill_registries["hybrid_skills"]
            skills = hybrid_skills.get_skills_for_type(issue_enum)
            result["hybrid_skills"] = [s.get_info() for s in skills]

        return result


def _register_get_skill_statistics(mcp_app: "FastMCP") -> None:
    @mcp_app.tool(
        name="get_skill_statistics",
        description="Get statistics about all skill registries",
    )
    async def get_skill_statistics() -> dict[str, t.Any]:
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
        from crackerjack.agents.base import Issue, IssueType, Priority

        if "hybrid_skills" not in _skill_registries:
            return {"error": "Hybrid skills not initialized"}

        registry = _skill_registries["hybrid_skills"]
        skill = registry.get_skill(skill_id)

        if not skill:
            return {"error": f"Skill not found: {skill_id}"}

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
    @mcp_app.tool(
        name="find_best_skill",
        description="Find the best skill for handling an issue",
    )
    async def find_best_skill(
        issue_type: str,
    ) -> dict[str, t.Any]:
        from crackerjack.agents.base import Issue, IssueType, Priority

        if "hybrid_skills" not in _skill_registries:
            return {"error": "Hybrid skills not initialized"}

        registry = _skill_registries["hybrid_skills"]

        try:
            issue_enum = IssueType(issue_type)
        except ValueError:
            return {"error": f"Unknown issue type: {issue_type}"}

        issue = Issue(
            type=issue_enum,
            severity=Priority.MEDIUM,
            message="Finding best skill",
        )

        try:
            best_skill = await registry.find_best_skill(issue)
            if best_skill:
                info = best_skill.get_info()

                if hasattr(best_skill, "get_tool_mappings"):
                    info["tools"] = [
                        m.to_dict() for m in best_skill.get_tool_mappings()
                    ]
                return info
            else:
                return {"error": "No skill found for this issue type"}
        except Exception as e:
            return {"error": f"Failed to find best skill: {e}"}

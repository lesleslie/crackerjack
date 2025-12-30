"""
MCP Skills System (Option 2)

Groups existing MCP tools into purpose-based skills for better discoverability.
This layer organizes tools without changing the underlying tool implementations.

Key Concepts:
- MCPSkill: A group of related MCP tools with a shared purpose
- MCPSkillRegistry: Manages MCP skills and provides tool discovery
- SkillGroup: Logical grouping of tools by functionality

Example:
    registry = MCPSkillRegistry()

    # Register tool groups as skills
    registry.register_skill_group(MCP_SKILL_GROUPS["quality_checks"])

    # Discover tools in a skill
    quality_tools = registry.get_tools_in_skill("quality_checks")

    # Get skill metadata
    info = registry.get_skill_info("quality_checks")
"""

import typing as t
from dataclasses import dataclass, field
from enum import Enum


class SkillDomain(Enum):
    """High-level domains for MCP skills."""

    EXECUTION = "execution"
    MONITORING = "monitoring"
    INTELLIGENCE = "intelligence"
    SEMANTIC = "semantic"
    PROACTIVE = "proactive"
    UTILITY = "utility"


@dataclass
class ToolReference:
    """Reference to an MCP tool."""

    name: str
    description: str
    required_params: list[str] = field(default_factory=list)
    optional_params: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "required_params": self.required_params,
            "optional_params": self.optional_params,
        }


@dataclass
class MCPSkill:
    """
    A skill that groups related MCP tools.

    Skills provide a higher-level abstraction over individual tools,
    making it easier to discover related functionality.
    """

    skill_id: str
    name: str
    description: str
    domain: SkillDomain
    tools: list[ToolReference] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)
    examples: list[str] = field(default_factory=list)

    def add_tool(
        self,
        tool_name: str,
        tool_description: str,
        required_params: list[str] | None = None,
        optional_params: list[str] | None = None,
    ) -> None:
        """Add a tool to this skill."""
        self.tools.append(
            ToolReference(
                name=tool_name,
                description=tool_description,
                required_params=required_params or [],
                optional_params=optional_params or [],
            )
        )

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain.value,
            "tools": [tool.to_dict() for tool in self.tools],
            "tags": list(self.tags),
            "examples": self.examples,
        }


class MCPSkillRegistry:
    """
    Registry for managing MCP skills.

    Provides discovery and grouping of MCP tools into skills.
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._skills: dict[str, MCPSkill] = {}
        self._domain_index: dict[SkillDomain, list[str]] = {
            domain: [] for domain in SkillDomain
        }
        self._tool_index: dict[str, str] = {}  # tool_name -> skill_id

    def register(
        self,
        skill: MCPSkill,
    ) -> None:
        """Register a skill in the registry."""
        self._skills[skill.skill_id] = skill

        # Update domain index
        self._domain_index[skill.domain].append(skill.skill_id)

        # Update tool index
        for tool in skill.tools:
            self._tool_index[tool.name] = skill.skill_id

    def register_skill_group(
        self,
        skill_data: dict[str, t.Any],
    ) -> MCPSkill:
        """
        Register a skill from a dictionary definition.

        Args:
            skill_data: Dictionary with skill definition

        Returns:
            The created MCPSkill
        """
        skill = MCPSkill(
            skill_id=skill_data["skill_id"],
            name=skill_data["name"],
            description=skill_data["description"],
            domain=SkillDomain(skill_data["domain"]),
            tags=set(skill_data.get("tags", [])),
            examples=skill_data.get("examples", []),
        )

        # Add tools
        for tool_data in skill_data.get("tools", []):
            skill.add_tool(
                tool_name=tool_data["name"],
                tool_description=tool_data["description"],
                required_params=tool_data.get("required_params", []),
                optional_params=tool_data.get("optional_params", []),
            )

        self.register(skill)
        return skill

    def get_skill(self, skill_id: str) -> MCPSkill | None:
        """Get skill by ID."""
        return self._skills.get(skill_id)

    def get_skill_by_tool(self, tool_name: str) -> MCPSkill | None:
        """Get skill that contains a specific tool."""
        skill_id = self._tool_index.get(tool_name)
        return self._skills.get(skill_id) if skill_id else None

    def get_skills_by_domain(
        self,
        domain: SkillDomain,
    ) -> list[MCPSkill]:
        """Get all skills in a domain."""
        skill_ids = self._domain_index.get(domain, [])
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    def list_all_skills(self) -> list[dict[str, t.Any]]:
        """List all registered skills with metadata."""
        return [skill.to_dict() for skill in self._skills.values()]

    def get_all_tools(self) -> list[str]:
        """Get all tool names across all skills."""
        return list(self._tool_index.keys())

    def get_tools_in_skill(self, skill_id: str) -> list[str]:
        """Get all tool names in a specific skill."""
        skill = self.get_skill(skill_id)
        return [tool.name for tool in skill.tools] if skill else []

    def search_skills(
        self,
        query: str,
        search_domains: bool = True,
        search_tags: bool = True,
        search_descriptions: bool = True,
        search_tool_names: bool = True,
    ) -> list[MCPSkill]:
        """
        Search for skills matching a query.

        Args:
            query: Search query
            search_domains: Search in domain names
            search_tags: Search in tags
            search_descriptions: Search in descriptions
            search_tool_names: Search in tool names

        Returns:
            List of matching skills
        """
        query_lower = query.lower()
        matching_skills = []

        for skill in self._skills.values():
            # Check domain
            if search_domains and query_lower in skill.domain.value:
                matching_skills.append(skill)
                continue

            # Check tags
            if search_tags and any(query_lower in tag for tag in skill.tags):
                matching_skills.append(skill)
                continue

            # Check description
            if search_descriptions and query_lower in skill.description.lower():
                matching_skills.append(skill)
                continue

            # Check tool names
            if search_tool_names and any(
                query_lower in tool.name for tool in skill.tools
            ):
                matching_skills.append(skill)
                continue

        return matching_skills

    def get_statistics(self) -> dict[str, t.Any]:
        """Get registry statistics."""
        return {
            "total_skills": len(self._skills),
            "total_tools": len(self._tool_index),
            "skills_by_domain": {
                domain.value: len(ids) for domain, ids in self._domain_index.items()
            },
            "avg_tools_per_skill": (
                len(self._tool_index) / len(self._skills) if self._skills else 0
            ),
        }


# Predefined skill groups based on existing MCP tools
MCP_SKILL_GROUPS: dict[str, dict[str, t.Any]] = {
    "quality_checks": {
        "skill_id": "quality_checks",
        "name": "Quality Checks",
        "description": "Run comprehensive quality checks and analyze results",
        "domain": "execution",
        "tags": ["quality", "testing", "validation", "checks"],
        "examples": [
            "Execute full crackerjack quality workflow",
            "Analyze errors from failed checks",
            "Get agent suggestions for fixing issues",
        ],
        "tools": [
            {
                "name": "execute_crackerjack",
                "description": "Execute crackerjack quality checks",
                "required_params": ["working_directory"],
                "optional_params": ["options", "timeout"],
            },
            {
                "name": "analyze_errors",
                "description": "Analyze errors from crackerjack output",
                "required_params": ["working_directory"],
                "optional_params": ["error_data"],
            },
            {
                "name": "get_agent_suggestions",
                "description": "Get AI agent suggestions for fixing issues",
                "required_params": ["working_directory"],
                "optional_params": [],
            },
        ],
    },
    "semantic_search": {
        "skill_id": "semantic_search",
        "name": "Semantic Search",
        "description": "Semantic code search and analysis using embeddings",
        "domain": "semantic",
        "tags": ["search", "semantic", "embeddings", "similarity"],
        "examples": [
            "Index Python files for semantic search",
            "Search for semantically similar code",
            "Calculate similarity between code snippets",
        ],
        "tools": [
            {
                "name": "index_file",
                "description": "Index a file for semantic search",
                "required_params": ["file_path"],
                "optional_params": [],
            },
            {
                "name": "search_semantic",
                "description": "Search for semantically similar code",
                "required_params": ["query", "top_k"],
                "optional_params": ["filters"],
            },
            {
                "name": "get_embeddings",
                "description": "Get embeddings for code or text",
                "required_params": ["content"],
                "optional_params": [],
            },
            {
                "name": "calculate_similarity",
                "description": "Calculate similarity between two code snippets",
                "required_params": ["content1", "content2"],
                "optional_params": [],
            },
        ],
    },
    "proactive_agent": {
        "skill_id": "proactive_agent",
        "name": "Proactive Agent",
        "description": "AI-driven development planning and architecture validation",
        "domain": "proactive",
        "tags": ["ai", "planning", "architecture", "proactive"],
        "examples": [
            "Generate development plan for a feature",
            "Validate architectural patterns",
            "Suggest refactoring opportunities",
        ],
        "tools": [
            {
                "name": "plan_development",
                "description": "Generate AI-powered development plan",
                "required_params": ["working_directory", "feature_description"],
                "optional_params": ["context"],
            },
            {
                "name": "validate_architecture",
                "description": "Validate architectural patterns",
                "required_params": ["working_directory"],
                "optional_params": [],
            },
            {
                "name": "suggest_patterns",
                "description": "Suggest design patterns",
                "required_params": ["working_directory", "scenario"],
                "optional_params": [],
            },
        ],
    },
    "monitoring": {
        "skill_id": "monitoring",
        "name": "Monitoring & Progress",
        "description": "Monitor crackerjack execution and track progress",
        "domain": "monitoring",
        "tags": ["monitoring", "progress", "status", "tracking"],
        "examples": [
            "Get comprehensive server status",
            "Track job progress in real-time",
            "Get server statistics and metrics",
        ],
        "tools": [
            {
                "name": "get_job_progress",
                "description": "Get progress of a specific job",
                "required_params": ["job_id"],
                "optional_params": [],
            },
            {
                "name": "get_comprehensive_status",
                "description": "Get comprehensive server status",
                "required_params": [],
                "optional_params": ["filter"],
            },
            {
                "name": "get_server_stats",
                "description": "Get server statistics",
                "required_params": [],
                "optional_params": [],
            },
            {
                "name": "stage_status",
                "description": "Get status of a specific stage",
                "required_params": ["stage_name"],
                "optional_params": [],
            },
        ],
    },
    "utilities": {
        "skill_id": "utilities",
        "name": "Utilities",
        "description": "Utility functions for configuration and maintenance",
        "domain": "utility",
        "tags": ["config", "cleanup", "maintenance", "utilities"],
        "examples": [
            "Clean temporary files",
            "Get or update configuration",
            "Initialize crackerjack in a project",
        ],
        "tools": [
            {
                "name": "clean",
                "description": "Clean temporary files and caches",
                "required_params": ["working_directory"],
                "optional_params": ["clean_type"],
            },
            {
                "name": "config",
                "description": "Get or update configuration",
                "required_params": ["working_directory"],
                "optional_params": ["key", "value"],
            },
            {
                "name": "init_crackerjack",
                "description": "Initialize crackerjack in a project",
                "required_params": ["working_directory"],
                "optional_params": [],
            },
            {
                "name": "analyze",
                "description": "Analyze project structure",
                "required_params": ["working_directory"],
                "optional_params": [],
            },
        ],
    },
    "intelligence": {
        "skill_id": "intelligence",
        "name": "AI Intelligence",
        "description": "AI-driven insights and analysis",
        "domain": "intelligence",
        "tags": ["ai", "intelligence", "insights", "analysis"],
        "examples": [
            "Get intelligent issue analysis",
            "AI-powered error diagnosis",
            "Smart fix recommendations",
        ],
        "tools": [
            {
                "name": "smart_error_analysis",
                "description": "AI-powered error analysis",
                "required_params": ["working_directory"],
                "optional_params": ["error_output"],
            },
        ],
    },
}

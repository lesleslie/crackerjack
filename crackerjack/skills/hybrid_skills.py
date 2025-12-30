"""
Hybrid Skills System (Option 3)

Combines agent-based skills with MCP tool delegation for the best of both worlds.
This approach provides intelligent agent capabilities with MCP tool integration.

Key Concepts:
- HybridSkill: Combines agent capabilities with MCP tool exposure
- ToolDelegator: Delegates skill execution to appropriate MCP tools
- HybridSkillRegistry: Manages hybrid skills with automatic tool registration

Example:
    registry = HybridSkillRegistry(mcp_app)
    registry.register_hybrid_skill(RefactoringAgent, context)

    # Skill executes via agent but exposes as MCP tool
    result = await registry.execute_via_tool("refactoring_skill", issue)
"""

import typing as t
from dataclasses import dataclass

from crackerjack.agents.base import (
    AgentContext,
    Issue,
    IssueType,
    SubAgent,
)
from crackerjack.skills.agent_skills import (
    AgentSkill,
    AgentSkillRegistry,
    SkillMetadata,
)


@dataclass
class ToolMapping:
    """Maps a skill to an MCP tool."""

    tool_name: str
    skill_id: str
    method_name: str
    description: str
    input_schema: dict[str, t.Any]
    output_schema: dict[str, t.Any]

    def to_dict(self) -> dict[str, t.Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "skill_id": self.skill_id,
            "method_name": self.method_name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


class ToolDelegator:
    """
    Delegates skill execution to MCP tools.

    This class bridges agent-based skills with MCP tool invocations,
    allowing skills to be exposed and executed through the MCP protocol.
    """

    def __init__(self) -> None:
        """Initialize delegator."""
        self._tool_mappings: dict[str, ToolMapping] = {}
        self._skill_mappings: dict[str, list[str]] = {}  # skill_id -> tool_names

    def register_tool_mapping(
        self,
        mapping: ToolMapping,
    ) -> None:
        """Register a tool mapping."""
        self._tool_mappings[mapping.tool_name] = mapping

        # Update skill mappings
        if mapping.skill_id not in self._skill_mappings:
            self._skill_mappings[mapping.skill_id] = []
        self._skill_mappings[mapping.skill_id].append(mapping.tool_name)

    def get_tool_mapping(self, tool_name: str) -> ToolMapping | None:
        """Get tool mapping by tool name."""
        return self._tool_mappings.get(tool_name)

    def get_tools_for_skill(self, skill_id: str) -> list[ToolMapping]:
        """Get all tool mappings for a skill."""
        tool_names = self._skill_mappings.get(skill_id, [])
        return [
            self._tool_mappings[name]
            for name in tool_names
            if name in self._tool_mappings
        ]

    def generate_tool_name(
        self,
        skill_id: str,
        operation: str,
    ) -> str:
        """Generate a standardized tool name."""
        return f"{skill_id}_{operation}"


class HybridSkill(AgentSkill):
    """
    Enhanced agent skill with MCP tool integration.

    Extends AgentSkill to add:
    - Tool delegation capabilities
    - MCP tool exposure
    - Automatic tool registration
    """

    def __init__(
        self,
        agent: SubAgent,
        metadata: SkillMetadata,
        delegator: ToolDelegator | None = None,
    ) -> None:
        """Initialize hybrid skill."""
        super().__init__(agent, metadata)
        self.delegator = delegator or ToolDelegator()
        self._tool_mappings: list[ToolMapping] = []

    def register_tool(
        self,
        operation: str,
        description: str,
        input_schema: dict[str, t.Any],
        output_schema: dict[str, t.Any],
    ) -> ToolMapping:
        """
        Register an MCP tool for this skill.

        Args:
            operation: Operation name (e.g., "analyze", "fix")
            description: Tool description
            input_schema: JSON schema for input
            output_schema: JSON schema for output

        Returns:
            Created ToolMapping
        """
        tool_name = self.delegator.generate_tool_name(
            self.skill_id,
            operation,
        )

        mapping = ToolMapping(
            tool_name=tool_name,
            skill_id=self.skill_id,
            method_name=operation,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
        )

        self.delegator.register_tool_mapping(mapping)
        self._tool_mappings.append(mapping)

        return mapping

    def generate_default_tools(self) -> list[ToolMapping]:
        """
        Generate default MCP tools for this skill.

        Creates standard tools for common operations:
        - can_handle: Check if skill can handle an issue
        - execute: Execute the skill
        - batch_execute: Execute on multiple issues
        - get_info: Get skill information

        Returns:
            List of created ToolMappings
        """
        mappings = []

        # can_handle tool
        mappings.append(
            self.register_tool(
                operation="can_handle",
                description=f"Check if {self.metadata.name} can handle an issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "issue_type": {
                            "type": "string",
                            "description": "Issue type to check",
                        },
                        "issue_data": {
                            "type": "object",
                            "description": "Issue data",
                        },
                    },
                    "required": ["issue_type"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "can_handle": {"type": "boolean"},
                        "confidence": {"type": "number"},
                    },
                },
            )
        )

        # execute tool
        mappings.append(
            self.register_tool(
                operation="execute",
                description=f"Execute {self.metadata.name} on an issue",
                input_schema={
                    "type": "object",
                    "properties": {
                        "issue_type": {
                            "type": "string",
                            "description": "Issue type",
                        },
                        "issue_data": {
                            "type": "object",
                            "description": "Issue data",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Optional timeout in seconds",
                        },
                    },
                    "required": ["issue_type", "issue_data"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "confidence": {"type": "number"},
                        "fixes_applied": {"type": "array", "items": {"type": "string"}},
                        "recommendations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            )
        )

        # batch_execute tool
        mappings.append(
            self.register_tool(
                operation="batch_execute",
                description=f"Execute {self.metadata.name} on multiple issues",
                input_schema={
                    "type": "object",
                    "properties": {
                        "issues": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "issue_type": {"type": "string"},
                                    "issue_data": {"type": "object"},
                                },
                            },
                        },
                    },
                    "required": ["issues"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "results": {
                            "type": "array",
                            "items": {"type": "object"},
                        },
                    },
                },
            )
        )

        # get_info tool
        mappings.append(
            self.register_tool(
                operation="get_info",
                description=f"Get information about {self.metadata.name}",
                input_schema={
                    "type": "object",
                    "properties": {},
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "skill_id": {"type": "string"},
                        "metadata": {"type": "object"},
                        "agent_name": {"type": "string"},
                        "tool_count": {"type": "integer"},
                    },
                },
            )
        )

        return mappings

    def get_tool_mappings(self) -> list[ToolMapping]:
        """Get all tool mappings for this skill."""
        return self._tool_mappings

    async def execute_via_tool(
        self,
        tool_name: str,
        **kwargs: t.Any,
    ) -> t.Any:
        """
        Execute skill via MCP tool.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool arguments

        Returns:
            Tool execution result
        """
        mapping = self.delegator.get_tool_mapping(tool_name)

        if not mapping or mapping.skill_id != self.skill_id:
            raise ValueError(f"Tool {tool_name} not found in skill {self.skill_id}")

        # Dispatch to appropriate method
        if mapping.method_name == "can_handle":
            issue = self._parse_issue(kwargs)
            confidence = await self.can_handle(issue)
            return {"can_handle": confidence > 0, "confidence": confidence}

        elif mapping.method_name == "execute":
            issue = self._parse_issue(kwargs)
            timeout = kwargs.get("timeout")
            result = await self.execute(issue, timeout)
            return result.to_dict()

        elif mapping.method_name == "batch_execute":
            issues_data = kwargs.get("issues", [])
            issues = [self._parse_issue(i) for i in issues_data]
            results = await self.batch_execute(issues)
            return {"results": [r.to_dict() for r in await results]}

        elif mapping.method_name == "get_info":
            info = self.get_info()
            info["tool_count"] = len(self._tool_mappings)
            return info

        else:
            raise ValueError(f"Unknown method: {mapping.method_name}")

    def _parse_issue(self, data: dict[str, t.Any]) -> Issue:
        """Parse issue from dictionary data."""
        from crackerjack.agents.base import Priority

        issue_type_str = data.get("issue_type", "unknown")
        try:
            issue_type = IssueType(issue_type_str)
        except ValueError:
            issue_type = IssueType.FORMATTING  # Default

        return Issue(
            type=issue_type,
            severity=Priority.MEDIUM,
            message=data.get("message", "Issue from tool invocation"),
            file_path=data.get("file_path"),
            line_number=data.get("line_number"),
            details=data.get("details", []),
        )


class HybridSkillRegistry(AgentSkillRegistry):
    """
    Registry for managing hybrid skills.

    Extends AgentSkillRegistry to add:
    - Tool delegation management
    - Automatic MCP tool registration
    - Skill execution via tools
    """

    def __init__(self) -> None:
        """Initialize registry."""
        super().__init__()
        self.delegator = ToolDelegator()
        self._mcp_app: t.Any = None

    def register_mcp_app(self, mcp_app: t.Any) -> None:
        """Register MCP app for tool registration."""
        self._mcp_app = mcp_app

    def register_hybrid_skill(
        self,
        agent_class: type[SubAgent],
        context: AgentContext,
        metadata: SkillMetadata | None = None,
        generate_tools: bool = True,
    ) -> HybridSkill:
        """
        Register an agent as a hybrid skill.

        Args:
            agent_class: The SubAgent subclass to register
            context: AgentContext for agent initialization
            metadata: Optional SkillMetadata (auto-generated if not provided)
            generate_tools: Whether to auto-generate MCP tools

        Returns:
            The created HybridSkill
        """
        # Create agent instance
        agent = agent_class(context)

        # Auto-generate metadata if not provided
        if metadata is None:
            metadata = self._generate_metadata(agent)

        # Create hybrid skill with shared delegator
        skill = HybridSkill(agent, metadata, self.delegator)

        # Register in parent registry
        self.register(skill)

        # Generate default tools if requested
        if generate_tools:
            skill.generate_default_tools()

        # Register tools with MCP app if available
        if self._mcp_app is not None:
            self._register_tools_with_mcp(skill)

        return skill

    def register_all_hybrid_skills(
        self,
        context: AgentContext,
    ) -> list[HybridSkill]:
        """
        Register all agents as hybrid skills.

        Args:
            context: AgentContext for agent initialization

        Returns:
            List of registered HybridSkill instances
        """
        from crackerjack.agents.base import agent_registry

        skills = []
        for agent_class in agent_registry._agents.values():
            try:
                skill = self.register_hybrid_skill(agent_class, context)
                skills.append(skill)
            except Exception as e:
                print(f"Warning: Failed to register {agent_class.__name__}: {e}")

        return skills

    async def execute_via_tool(
        self,
        tool_name: str,
        **kwargs: t.Any,
    ) -> t.Any:
        """
        Execute a skill via its MCP tool.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool arguments

        Returns:
            Tool execution result
        """
        mapping = self.delegator.get_tool_mapping(tool_name)

        if not mapping:
            raise ValueError(f"Tool {tool_name} not found")

        skill = self.get_skill(mapping.skill_id)

        if not skill or not isinstance(skill, HybridSkill):
            raise ValueError(f"Skill {mapping.skill_id} not found or not hybrid")

        return await skill.execute_via_tool(tool_name, **kwargs)

    def get_all_tool_mappings(self) -> list[ToolMapping]:
        """Get all tool mappings across all skills."""
        mappings = []
        for skill in self._skills.values():
            if isinstance(skill, HybridSkill):
                mappings.extend(skill.get_tool_mappings())
        return mappings

    def _register_tools_with_mcp(self, skill: HybridSkill) -> None:
        """Register skill tools with MCP app.

        Note: FastMCP doesn't support dynamic tool registration via add_tool() method.
        Hybrid skills are accessible through the 8 skill management tools instead.
        This method is a no-op but kept for API compatibility.
        """
        # FastMCP uses @mcp_app.tool() decorator pattern, not dynamic add_tool()
        # Hybrid skills are accessible via:
        # - execute_skill (can execute any hybrid skill)
        # - list_skills (shows all hybrid skills)
        # - get_skill_info (shows hybrid skill details with tool mappings)
        pass

    def get_tool_statistics(self) -> dict[str, t.Any]:
        """Get tool-related statistics."""
        all_mappings = self.get_all_tool_mappings()

        # Count tools by skill
        tools_by_skill: dict[str, int] = {}
        for mapping in all_mappings:
            tools_by_skill[mapping.skill_id] = (
                tools_by_skill.get(mapping.skill_id, 0) + 1
            )

        return {
            "total_tools": len(all_mappings),
            "tools_by_skill": tools_by_skill,
            "avg_tools_per_skill": (
                len(all_mappings) / len(self._skills) if self._skills else 0
            ),
        }

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
    tool_name: str
    skill_id: str
    method_name: str
    description: str
    input_schema: dict[str, t.Any]
    output_schema: dict[str, t.Any]

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "tool_name": self.tool_name,
            "skill_id": self.skill_id,
            "method_name": self.method_name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }


class ToolDelegator:
    def __init__(self) -> None:
        self._tool_mappings: dict[str, ToolMapping] = {}
        self._skill_mappings: dict[str, list[str]] = {}

    def register_tool_mapping(
        self,
        mapping: ToolMapping,
    ) -> None:
        self._tool_mappings[mapping.tool_name] = mapping

        if mapping.skill_id not in self._skill_mappings:
            self._skill_mappings[mapping.skill_id] = []
        self._skill_mappings[mapping.skill_id].append(mapping.tool_name)

    def get_tool_mapping(self, tool_name: str) -> ToolMapping | None:
        return self._tool_mappings.get(tool_name)

    def get_tools_for_skill(self, skill_id: str) -> list[ToolMapping]:
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
        return f"{skill_id}_{operation}"


class HybridSkill(AgentSkill):
    def __init__(
        self,
        agent: SubAgent,
        metadata: SkillMetadata,
        delegator: ToolDelegator | None = None,
    ) -> None:
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
        mappings = [
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
            ),
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
            ),
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
            ),
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
            ),
        ]

        return mappings

    def get_tool_mappings(self) -> list[ToolMapping]:
        return self._tool_mappings

    async def execute_via_tool(
        self,
        tool_name: str,
        **kwargs: t.Any,
    ) -> t.Any:
        mapping = self.delegator.get_tool_mapping(tool_name)

        if not mapping or mapping.skill_id != self.skill_id:
            raise ValueError(f"Tool {tool_name} not found in skill {self.skill_id}")

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
            results_coro = self.batch_execute(issues)
            results = await results_coro
            return {"results": [r.to_dict() for r in results]}

        elif mapping.method_name == "get_info":
            info = self.get_info()
            info["tool_count"] = len(self._tool_mappings)
            return info

        else:
            raise ValueError(f"Unknown method: {mapping.method_name}")

    def _parse_issue(self, data: dict[str, t.Any]) -> Issue:
        from crackerjack.agents.base import Priority

        issue_type_str = data.get("issue_type", "unknown")
        try:
            issue_type = IssueType(issue_type_str)
        except ValueError:
            issue_type = IssueType.FORMATTING

        return Issue(
            type=issue_type,
            severity=Priority.MEDIUM,
            message=data.get("message", "Issue from tool invocation"),
            file_path=data.get("file_path"),
            line_number=data.get("line_number"),
            details=data.get("details", []),
        )


class HybridSkillRegistry(AgentSkillRegistry):
    def __init__(self) -> None:
        super().__init__()
        self.delegator = ToolDelegator()
        self._mcp_app: t.Any = None

    def register_mcp_app(self, mcp_app: t.Any) -> None:
        self._mcp_app = mcp_app

    def register_hybrid_skill(
        self,
        agent_class: type[SubAgent],
        context: AgentContext,
        metadata: SkillMetadata | None = None,
        generate_tools: bool = True,
    ) -> HybridSkill:
        agent = agent_class(context)

        if metadata is None:
            metadata = self._generate_metadata(agent)

        skill = HybridSkill(agent, metadata, self.delegator)

        self.register(skill)

        if generate_tools:
            skill.generate_default_tools()

        if self._mcp_app is not None:
            self._register_tools_with_mcp(skill)

        return skill

    def register_all_hybrid_skills(
        self,
        context: AgentContext,
    ) -> list[HybridSkill]:
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
        mapping = self.delegator.get_tool_mapping(tool_name)

        if not mapping:
            raise ValueError(f"Tool {tool_name} not found")

        skill = self.get_skill(mapping.skill_id)

        if not skill or not isinstance(skill, HybridSkill):
            raise ValueError(f"Skill {mapping.skill_id} not found or not hybrid")

        return await skill.execute_via_tool(tool_name, **kwargs)

    def get_all_tool_mappings(self) -> list[ToolMapping]:
        mappings = []
        for skill in self._skills.values():
            if isinstance(skill, HybridSkill):
                mappings.extend(skill.get_tool_mappings())
        return mappings

    def _register_tools_with_mcp(self, skill: HybridSkill) -> None:
        pass

    def get_tool_statistics(self) -> dict[str, t.Any]:
        all_mappings = self.get_all_tool_mappings()

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

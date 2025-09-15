import logging
import typing as t
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from crackerjack.agents.base import SubAgent, agent_registry


class AgentSource(Enum):
    CRACKERJACK = "crackerjack"
    USER = "user"
    SYSTEM = "system"


class AgentCapability(Enum):
    ARCHITECTURE = "architecture"
    REFACTORING = "refactoring"
    TESTING = "testing"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    FORMATTING = "formatting"
    DEBUGGING = "debugging"
    CODE_ANALYSIS = "code_analysis"
    PROJECT_MANAGEMENT = "project_management"


@dataclass
class AgentMetadata:
    name: str
    source: AgentSource
    capabilities: set[AgentCapability]
    priority: int
    confidence_factor: float
    description: str
    model: str | None = None
    tags: list[str] | None = None


@dataclass
class RegisteredAgent:
    metadata: AgentMetadata
    agent: SubAgent | None = None
    agent_path: Path | None = None
    subagent_type: str | None = None


class AgentRegistry:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self._agents: dict[str, RegisteredAgent] = {}
        self._capability_map: dict[AgentCapability, list[str]] = {}
        self._user_agent_cache: dict[str, dict[str, t.Any]] = {}

    async def initialize(self) -> None:
        self.logger.info("Initializing Intelligent Agent Registry")

        await self._register_crackerjack_agents()
        await self._register_user_agents()
        await self._register_system_agents()

        self._build_capability_map()

        self.logger.info(
            f"Registry initialized with {len(self._agents)} agents: "
            f"{len([a for a in self._agents.values() if a.metadata.source == AgentSource.CRACKERJACK])} crackerjack, "
            f"{len([a for a in self._agents.values() if a.metadata.source == AgentSource.USER])} user, "
            f"{len([a for a in self._agents.values() if a.metadata.source == AgentSource.SYSTEM])} system"
        )

    async def _register_crackerjack_agents(self) -> None:
        self.logger.debug("Registering crackerjack agents")

        from crackerjack.agents.base import AgentContext

        context = AgentContext(
            project_path=Path.cwd(),
        )

        crackerjack_agents = agent_registry.create_all(context)

        for agent in crackerjack_agents:
            capabilities = self._infer_capabilities_from_agent(agent)

            metadata = AgentMetadata(
                name=agent.name,
                source=AgentSource.CRACKERJACK,
                capabilities=capabilities,
                priority=100,
                confidence_factor=1.0,
                description=f"Built-in crackerjack {agent.__class__.__name__}",
            )

            registered = RegisteredAgent(
                metadata=metadata,
                agent=agent,
            )

            self._agents[agent.name] = registered
            self.logger.debug(f"Registered crackerjack agent: {agent.name}")

    async def _register_user_agents(self) -> None:
        self.logger.debug("Registering user agents")

        user_agents_dir = Path.home() / ".claude" / "agents"
        if not user_agents_dir.exists():
            self.logger.debug("No user agents directory found")
            return

        for agent_file in user_agents_dir.glob("*.md"):
            try:
                agent_data = await self._parse_user_agent_file(agent_file)
                if agent_data:
                    capabilities = self._infer_capabilities_from_user_agent(agent_data)

                    metadata = AgentMetadata(
                        name=agent_data["name"],
                        source=AgentSource.USER,
                        capabilities=capabilities,
                        priority=80,
                        confidence_factor=0.9,
                        description=agent_data.get("description", "User agent"),
                        model=agent_data.get("model"),
                        tags=agent_data.get("tags", []),
                    )

                    registered = RegisteredAgent(
                        metadata=metadata,
                        agent_path=agent_file,
                    )

                    self._agents[agent_data["name"]] = registered
                    self._user_agent_cache[agent_data["name"]] = agent_data
                    self.logger.debug(f"Registered user agent: {agent_data['name']}")

            except Exception as e:
                self.logger.warning(f"Failed to parse user agent {agent_file}: {e}")

    async def _register_system_agents(self) -> None:
        self.logger.debug("Registering system agents")

        system_agents = [
            (
                "general-purpose",
                "General-purpose agent for researching complex questions",
            ),
            (
                "statusline-setup",
                "Configure the user's Claude Code status line setting",
            ),
            ("output-style-setup", "Create a Claude Code output style"),
        ]

        for agent_name, description in system_agents:
            capabilities = self._infer_capabilities_from_system_agent(
                agent_name, description
            )

            metadata = AgentMetadata(
                name=agent_name,
                source=AgentSource.SYSTEM,
                capabilities=capabilities,
                priority=60,
                confidence_factor=0.7,
                description=description,
            )

            registered = RegisteredAgent(
                metadata=metadata,
                subagent_type=agent_name,
            )

            self._agents[agent_name] = registered
            self.logger.debug(f"Registered system agent: {agent_name}")

    async def _parse_user_agent_file(self, agent_file: Path) -> dict[str, t.Any] | None:
        try:
            content = agent_file.read_text(encoding="utf-8")
            return self._extract_agent_data_from_content(content)
        except Exception as e:
            self.logger.error(f"Error parsing agent file {agent_file}: {e}")
            return None

    def _extract_agent_data_from_content(self, content: str) -> dict[str, t.Any] | None:
        if not content.startswith("- --\n"):
            return None

        lines = content.split("\n")
        yaml_end = self._find_yaml_end_marker(lines)

        if yaml_end == -1:
            return None

        return self._build_agent_data(lines, yaml_end)

    def _find_yaml_end_marker(self, lines: list[str]) -> int:
        for i, line in enumerate(lines[1:], 1):
            if line == "- --":
                return i
        return -1

    def _build_agent_data(self, lines: list[str], yaml_end: int) -> dict[str, t.Any]:
        yaml_lines = lines[1:yaml_end]
        agent_data: dict[str, t.Any] = {}

        for line in yaml_lines:
            if ": " in line:
                key, value = line.split(": ", 1)
                agent_data[key.strip()] = value.strip()

        agent_data["content"] = "\n".join(lines[yaml_end + 1 :])
        return agent_data

    def _infer_capabilities_from_agent(self, agent: SubAgent) -> set[AgentCapability]:
        """Infer agent capabilities from class name using keyword mapping."""
        class_name = agent.__class__.__name__.lower()
        capability_mapping = self._get_agent_capability_mapping()

        capabilities = set()
        for keywords, caps in capability_mapping:
            if self._class_name_matches_keywords(class_name, keywords):
                capabilities.update(caps)

        # Fallback to default capability if none found
        if not capabilities:
            capabilities.add(AgentCapability.CODE_ANALYSIS)

        return capabilities

    def _get_agent_capability_mapping(
        self,
    ) -> list[tuple[list[str], set[AgentCapability]]]:
        """Get mapping of keywords to agent capabilities."""
        return [
            (
                ["architect"],
                {AgentCapability.ARCHITECTURE, AgentCapability.CODE_ANALYSIS},
            ),
            (["refactor"], {AgentCapability.REFACTORING}),
            (["test"], {AgentCapability.TESTING}),
            (["security"], {AgentCapability.SECURITY}),
            (["performance"], {AgentCapability.PERFORMANCE}),
            (["documentation", "doc"], {AgentCapability.DOCUMENTATION}),
            (["format"], {AgentCapability.FORMATTING}),
            (["import"], {AgentCapability.CODE_ANALYSIS}),
            (["dry"], {AgentCapability.REFACTORING}),
        ]

    def _class_name_matches_keywords(
        self, class_name: str, keywords: list[str]
    ) -> bool:
        """Check if class name contains any of the specified keywords."""
        return any(keyword in class_name for keyword in keywords)

    def _infer_capabilities_from_user_agent(
        self, agent_data: dict[str, t.Any]
    ) -> set[AgentCapability]:
        capabilities = set()

        name = agent_data.get("name", "").lower()
        description = agent_data.get("description", "").lower()
        content = agent_data.get("content", "").lower()

        text = f"{name} {description} {content}"

        keyword_map = {
            AgentCapability.ARCHITECTURE: [
                "architect",
                "design",
                "structure",
                "pattern",
            ],
            AgentCapability.REFACTORING: ["refactor", "clean", "improve", "optimize"],
            AgentCapability.TESTING: ["test", "pytest", "coverage", "mock"],
            AgentCapability.SECURITY: ["security", "secure", "vulnerability", "audit"],
            AgentCapability.PERFORMANCE: [
                "performance",
                "speed",
                "optimize",
                "efficient",
            ],
            AgentCapability.DOCUMENTATION: ["document", "readme", "comment", "explain"],
            AgentCapability.FORMATTING: ["format", "style", "lint", "ruff"],
            AgentCapability.DEBUGGING: ["debug", "fix", "error", "troubleshoot"],
            AgentCapability.CODE_ANALYSIS: ["analyze", "review", "inspect", "examine"],
            AgentCapability.PROJECT_MANAGEMENT: [
                "project",
                "manage",
                "organize",
                "workflow",
            ],
        }

        for capability, keywords in keyword_map.items():
            if any(keyword in text for keyword in keywords):
                capabilities.add(capability)

        if not capabilities:
            capabilities.add(AgentCapability.CODE_ANALYSIS)

        return capabilities

    def _infer_capabilities_from_system_agent(
        self, name: str, description: str
    ) -> set[AgentCapability]:
        capabilities = set()

        text = f"{name} {description}".lower()

        if "general" in text or "research" in text:
            capabilities.add(AgentCapability.CODE_ANALYSIS)
        if "statusline" in text or "setup" in text:
            capabilities.add(AgentCapability.PROJECT_MANAGEMENT)
        if "output" in text or "style" in text:
            capabilities.add(AgentCapability.FORMATTING)

        if not capabilities:
            capabilities.add(AgentCapability.CODE_ANALYSIS)

        return capabilities

    def _build_capability_map(self) -> None:
        self._capability_map.clear()

        for agent_name, registered_agent in self._agents.items():
            for capability in registered_agent.metadata.capabilities:
                if capability not in self._capability_map:
                    self._capability_map[capability] = []
                self._capability_map[capability].append(agent_name)

        for agent_names in self._capability_map.values():
            agent_names.sort(
                key=lambda name: self._agents[name].metadata.priority, reverse=True
            )

    def get_agents_by_capability(
        self, capability: AgentCapability
    ) -> list[RegisteredAgent]:
        agent_names = self._capability_map.get(capability, [])
        return [self._agents[name] for name in agent_names]

    def get_agent_by_name(self, name: str) -> RegisteredAgent | None:
        return self._agents.get(name)

    def list_all_agents(self) -> list[RegisteredAgent]:
        agents = list[t.Any](self._agents.values())
        agents.sort(key=lambda a: a.metadata.priority, reverse=True)
        return agents

    def get_agent_stats(self) -> dict[str, t.Any]:
        stats: dict[str, t.Any] = {
            "total_agents": len(self._agents),
            "by_source": {},
            "by_capability": {},
        }

        for source in AgentSource:
            count = len(
                [a for a in self._agents.values() if a.metadata.source == source]
            )
            stats["by_source"][source.value] = count

        for capability in AgentCapability:
            count = len(self._capability_map.get(capability, []))
            stats["by_capability"][capability.value] = count

        return stats


agent_registry_instance = AgentRegistry()


async def get_agent_registry() -> AgentRegistry:
    if not agent_registry_instance._agents:
        await agent_registry_instance.initialize()
    return agent_registry_instance

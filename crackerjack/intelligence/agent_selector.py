"""Smart Agent Selection Engine.

Intelligently selects the best agents for tasks based on context analysis,
capability matching, and priority scoring.
"""

import logging
import re
import typing as t
from dataclasses import dataclass
from enum import Enum

from .agent_registry import (
    AgentCapability,
    AgentRegistry,
    RegisteredAgent,
    get_agent_registry,
)


class TaskContext(Enum):
    """Context categories for tasks."""

    CODE_QUALITY = "code_quality"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DEBUGGING = "debugging"
    PROJECT_SETUP = "project_setup"
    GENERAL = "general"


@dataclass
class TaskDescription:
    """Description of a task to be executed."""

    description: str
    context: TaskContext | None = None
    keywords: list[str] | None = None
    file_patterns: list[str] | None = None
    error_types: list[str] | None = None
    priority: int = 50  # 0-100, higher is more important


@dataclass
class AgentScore:
    """Score for an agent's suitability for a task."""

    agent: RegisteredAgent
    base_score: float  # 0-1 based on capability match
    context_score: float  # 0-1 based on context match
    priority_bonus: float  # 0-1 based on agent priority
    confidence_factor: float  # Multiplier from agent metadata
    final_score: float  # Combined weighted score
    reasoning: str  # Explanation of the score


class AgentSelector:
    """Intelligent agent selection engine."""

    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self.logger = logging.getLogger(__name__)
        self.registry = registry
        self._task_patterns: dict[str, list[AgentCapability]] = {}
        self._initialize_task_patterns()

    def _initialize_task_patterns(self) -> None:
        """Initialize patterns for task analysis."""
        self._task_patterns = {
            # Architecture patterns
            r"architect|design|structure|pattern|refactor.*complex": [
                AgentCapability.ARCHITECTURE,
                AgentCapability.REFACTORING,
            ],
            # Code quality patterns
            r"refurb|ruff|format|lint|style|clean.*code": [
                AgentCapability.FORMATTING,
                AgentCapability.CODE_ANALYSIS,
            ],
            # Testing patterns
            r"test|pytest|coverage|mock|fixture": [
                AgentCapability.TESTING,
            ],
            # Security patterns
            r"security|vulnerability|audit|bandit|safe": [
                AgentCapability.SECURITY,
            ],
            # Performance patterns
            r"performance|optimize|speed|efficient|complexity": [
                AgentCapability.PERFORMANCE,
                AgentCapability.CODE_ANALYSIS,
            ],
            # Documentation patterns
            r"document|readme|comment|explain|changelog": [
                AgentCapability.DOCUMENTATION,
            ],
            # Refactoring patterns
            r"refactor|improve|simplify|dry.*violation": [
                AgentCapability.REFACTORING,
                AgentCapability.CODE_ANALYSIS,
            ],
            # Debugging patterns
            r"debug|fix|error|bug|failure": [
                AgentCapability.DEBUGGING,
                AgentCapability.CODE_ANALYSIS,
            ],
        }

    async def get_registry(self) -> AgentRegistry:
        """Get or initialize the agent registry."""
        if self.registry is None:
            self.registry = await get_agent_registry()
        return self.registry

    async def select_best_agent(
        self,
        task: TaskDescription,
        max_candidates: int = 5,
    ) -> AgentScore | None:
        """Select the single best agent for a task."""
        candidates = await self.select_agents(task, max_candidates)
        return candidates[0] if candidates else None

    async def select_agents(
        self,
        task: TaskDescription,
        max_candidates: int = 3,
    ) -> list[AgentScore]:
        """Select the best agents for a task, ordered by score."""
        registry = await self.get_registry()

        # Analyze task to determine required capabilities
        required_capabilities = self._analyze_task_capabilities(task)

        # Score all agents
        scores: list[AgentScore] = []

        for agent in registry.list_all_agents():
            score = await self._score_agent_for_task(agent, task, required_capabilities)
            if score.final_score > 0.1:  # Minimum threshold
                scores.append(score)

        # Sort by final score (descending)
        scores.sort(key=lambda s: s.final_score, reverse=True)

        # Return top candidates
        selected = scores[:max_candidates]

        self.logger.debug(
            f"Selected {len(selected)} agents for task '{task.description[:50]}...': "
            f"{[f'{s.agent.metadata.name}({s.final_score:.2f})' for s in selected]}"
        )

        return selected

    def _analyze_task_capabilities(self, task: TaskDescription) -> set[AgentCapability]:
        """Analyze a task to determine required capabilities."""
        capabilities = set()

        # Apply different analysis methods
        capabilities.update(self._analyze_text_patterns(task))
        capabilities.update(self._analyze_context(task))
        capabilities.update(self._analyze_file_patterns(task))
        capabilities.update(self._analyze_error_types(task))

        # Fallback
        return capabilities or {AgentCapability.CODE_ANALYSIS}

    def _analyze_text_patterns(self, task: TaskDescription) -> set[AgentCapability]:
        """Analyze text patterns in task description and keywords."""
        text = task.description.lower()
        if task.keywords:
            text += " " + " ".join(task.keywords).lower()

        capabilities = set()
        for pattern, caps in self._task_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                capabilities.update(caps)

        return capabilities

    def _analyze_context(self, task: TaskDescription) -> set[AgentCapability]:
        """Analyze task context to determine capabilities."""
        if not task.context:
            return set()

        context_map = {
            TaskContext.CODE_QUALITY: [
                AgentCapability.CODE_ANALYSIS,
                AgentCapability.FORMATTING,
            ],
            TaskContext.ARCHITECTURE: [
                AgentCapability.ARCHITECTURE,
                AgentCapability.CODE_ANALYSIS,
            ],
            TaskContext.TESTING: [AgentCapability.TESTING],
            TaskContext.REFACTORING: [
                AgentCapability.REFACTORING,
                AgentCapability.CODE_ANALYSIS,
            ],
            TaskContext.DOCUMENTATION: [AgentCapability.DOCUMENTATION],
            TaskContext.SECURITY: [AgentCapability.SECURITY],
            TaskContext.PERFORMANCE: [
                AgentCapability.PERFORMANCE,
                AgentCapability.CODE_ANALYSIS,
            ],
            TaskContext.DEBUGGING: [
                AgentCapability.DEBUGGING,
                AgentCapability.CODE_ANALYSIS,
            ],
            TaskContext.PROJECT_SETUP: [AgentCapability.PROJECT_MANAGEMENT],
            TaskContext.GENERAL: [AgentCapability.CODE_ANALYSIS],
        }

        return set(context_map.get(task.context, []))

    def _analyze_file_patterns(self, task: TaskDescription) -> set[AgentCapability]:
        """Analyze file patterns to determine capabilities."""
        if not task.file_patterns:
            return set()

        capabilities = set()
        for pattern in task.file_patterns:
            pattern_lower = pattern.lower()
            if any(ext in pattern_lower for ext in (".py", ".pyi")):
                capabilities.add(AgentCapability.CODE_ANALYSIS)
            if any(test in pattern_lower for test in ("test_", "_test", "tests/")):
                capabilities.add(AgentCapability.TESTING)

        return capabilities

    def _analyze_error_types(self, task: TaskDescription) -> set[AgentCapability]:
        """Analyze error types to determine capabilities."""
        if not task.error_types:
            return set()

        capabilities = set()
        for error_type in task.error_types:
            error_lower = error_type.lower()
            if "furb" in error_lower or "refurb" in error_lower:
                capabilities.update(
                    [AgentCapability.REFACTORING, AgentCapability.CODE_ANALYSIS]
                )
            elif "test" in error_lower:
                capabilities.add(AgentCapability.TESTING)
            elif "type" in error_lower or "pyright" in error_lower:
                capabilities.add(AgentCapability.CODE_ANALYSIS)
            elif "security" in error_lower or "bandit" in error_lower:
                capabilities.add(AgentCapability.SECURITY)

        return capabilities

    async def _score_agent_for_task(
        self,
        agent: RegisteredAgent,
        task: TaskDescription,
        required_capabilities: set[AgentCapability],
    ) -> AgentScore:
        """Score an agent's suitability for a task."""
        # Base score: capability overlap
        agent_capabilities = agent.metadata.capabilities
        overlap = len(required_capabilities & agent_capabilities)
        max_overlap = len(required_capabilities)

        base_score = overlap / max_overlap if max_overlap > 0 else 0.0

        # Context score: how well the agent matches the task context
        context_score = self._calculate_context_score(agent, task)

        # Priority bonus: normalized agent priority (0-1)
        priority_bonus = min(agent.metadata.priority / 100.0, 1.0)

        # Confidence factor from agent metadata
        confidence_factor = agent.metadata.confidence_factor

        # Calculate weighted final score
        weights = {
            "base": 0.4,  # Capability match is most important
            "context": 0.3,  # Context matching
            "priority": 0.2,  # Agent priority (source-based)
            "bonus": 0.1,  # Additional considerations
        }

        weighted_score = (
            base_score * weights["base"]
            + context_score * weights["context"]
            + priority_bonus * weights["priority"]
        )

        # Apply confidence factor
        final_score = weighted_score * confidence_factor

        # Generate reasoning
        reasoning = self._generate_score_reasoning(
            agent, base_score, context_score, priority_bonus, required_capabilities
        )

        return AgentScore(
            agent=agent,
            base_score=base_score,
            context_score=context_score,
            priority_bonus=priority_bonus,
            confidence_factor=confidence_factor,
            final_score=final_score,
            reasoning=reasoning,
        )

    def _calculate_context_score(
        self, agent: RegisteredAgent, task: TaskDescription
    ) -> float:
        """Calculate how well an agent matches the task context."""
        score = 0.0

        agent_name_lower = agent.metadata.name.lower()
        task_text = task.description.lower()

        score += self._score_name_matches(agent_name_lower, task_text)
        score += self._score_description_matches(agent, task_text)
        score += self._score_keyword_matches(agent, task)
        score += self._score_special_patterns(agent_name_lower, task_text)

        return min(score, 1.0)

    def _score_name_matches(self, agent_name_lower: str, task_text: str) -> float:
        """Score direct name matches between agent and task."""
        if any(keyword in agent_name_lower for keyword in task_text.split()):
            return 0.3
        return 0.0

    def _score_description_matches(
        self, agent: RegisteredAgent, task_text: str
    ) -> float:
        """Score description word overlap."""
        if not agent.metadata.description:
            return 0.0

        desc_words = set(agent.metadata.description.lower().split())
        task_words = set(task_text.split())
        common_words = desc_words & task_words

        if common_words:
            return len(common_words) / max(len(task_words), 1) * 0.2
        return 0.0

    def _score_keyword_matches(
        self, agent: RegisteredAgent, task: TaskDescription
    ) -> float:
        """Score keyword/tag overlap."""
        if not task.keywords or not agent.metadata.tags:
            return 0.0

        task_keywords = {k.lower() for k in task.keywords}
        agent_tags = {t.lower() for t in agent.metadata.tags}
        overlap = len(task_keywords & agent_tags)

        if overlap > 0:
            return overlap / len(task_keywords) * 0.3
        return 0.0

    def _score_special_patterns(self, agent_name_lower: str, task_text: str) -> float:
        """Score special pattern bonuses."""
        score = 0.0

        if "architect" in agent_name_lower and (
            "architect" in task_text or "design" in task_text
        ):
            score += 0.2
        if "refactor" in agent_name_lower and "refurb" in task_text:
            score += 0.2
        if "test" in agent_name_lower and "test" in task_text:
            score += 0.2

        return score

    def _generate_score_reasoning(
        self,
        agent: RegisteredAgent,
        base_score: float,
        context_score: float,
        priority_bonus: float,
        required_capabilities: set[AgentCapability],
    ) -> str:
        """Generate human-readable reasoning for the score."""
        parts = []

        # Capability match
        overlap = len(required_capabilities & agent.metadata.capabilities)
        parts.append(f"Capabilities: {overlap}/{len(required_capabilities)} match")

        # Context relevance
        if context_score > 0.5:
            parts.append("High context relevance")
        elif context_score > 0.2:
            parts.append("Moderate context relevance")
        else:
            parts.append("Low context relevance")

        # Source priority
        source_desc = {
            "crackerjack": "Built-in specialist",
            "user": "User agent",
            "system": "System agent",
        }
        parts.append(source_desc.get(agent.metadata.source.value, "Unknown source"))

        # Special strengths
        if agent.metadata.capabilities:
            top_caps = list(agent.metadata.capabilities)[:2]
            cap_names = [cap.value.replace("_", " ") for cap in top_caps]
            parts.append(f"Strengths: {', '.join(cap_names)}")

        return " | ".join(parts)

    async def analyze_task_complexity(self, task: TaskDescription) -> dict[str, t.Any]:
        """Analyze task complexity and provide recommendations."""
        registry = await self.get_registry()
        required_capabilities = self._analyze_task_capabilities(task)

        # Get all agents that could handle this task
        all_scores = []
        for agent in registry.list_all_agents():
            score = await self._score_agent_for_task(agent, task, required_capabilities)
            if score.final_score > 0.1:
                all_scores.append(score)

        all_scores.sort(key=lambda s: s.final_score, reverse=True)

        analysis = {
            "required_capabilities": [cap.value for cap in required_capabilities],
            "complexity_level": self._assess_complexity(
                required_capabilities, all_scores
            ),
            "candidate_count": len(all_scores),
            "top_agents": [
                {
                    "name": score.agent.metadata.name,
                    "source": score.agent.metadata.source.value,
                    "score": score.final_score,
                    "reasoning": score.reasoning,
                }
                for score in all_scores[:5]
            ],
            "recommendations": self._generate_recommendations(
                required_capabilities, all_scores
            ),
        }

        return analysis

    def _assess_complexity(
        self, capabilities: set[AgentCapability], scores: list[AgentScore]
    ) -> str:
        """Assess the complexity level of a task."""
        if len(capabilities) >= 4:
            return "high"
        elif len(capabilities) >= 2:
            return "medium"
        elif not scores or scores[0].final_score < 0.3:
            return "high"  # No good matches = complex

        return "low"

    def _generate_recommendations(
        self,
        capabilities: set[AgentCapability],
        scores: list[AgentScore],
    ) -> list[str]:
        """Generate recommendations based on analysis."""
        recommendations = []

        if not scores:
            recommendations.append(
                "No suitable agents found - consider manual approach"
            )
            return recommendations

        top_score = scores[0].final_score

        if top_score > 0.8:
            recommendations.append(
                "Excellent agent match found - high confidence execution"
            )
        elif top_score > 0.6:
            recommendations.append("Good agent match - should handle task well")
        elif top_score > 0.4:
            recommendations.append("Moderate match - may need supervision")
        else:
            recommendations.append("Weak matches - consider alternative approaches")

        # Multi-agent recommendations
        if len(capabilities) > 2:
            recommendations.append("Consider multi-agent approach for complex task")

        # Source diversity
        sources = {score.agent.metadata.source for score in scores[:3]}
        if len(sources) > 1:
            recommendations.append("Multiple agent sources available for redundancy")

        return recommendations

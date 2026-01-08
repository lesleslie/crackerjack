import asyncio
import operator
import typing as t
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

from crackerjack.agents.base import (
    AgentContext,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


class SkillCategory(Enum):
    CODE_QUALITY = "code_quality"
    TESTING = "testing"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    SEMANTIC = "semantic"
    PROACTIVE = "proactive"


@dataclass
class SkillMetadata:
    name: str
    description: str
    category: SkillCategory
    supported_types: set[IssueType]
    confidence_threshold: float = 0.7
    avg_confidence: float = 0.8
    execution_count: int = 0
    success_rate: float = 1.0
    tags: set[str] = field(default_factory=set)

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "supported_types": [t.value for t in self.supported_types],
            "confidence_threshold": self.confidence_threshold,
            "avg_confidence": self.avg_confidence,
            "execution_count": self.execution_count,
            "success_rate": self.success_rate,
            "tags": list(self.tags),
        }


@dataclass
class SkillExecutionResult:
    skill_name: str
    success: bool
    confidence: float
    issues_handled: int
    fixes_applied: list[str]
    recommendations: list[str]
    files_modified: list[str]
    execution_time_ms: int = 0

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "skill_name": self.skill_name,
            "success": self.success,
            "confidence": self.confidence,
            "issues_handled": self.issues_handled,
            "fixes_applied": self.fixes_applied,
            "recommendations": self.recommendations,
            "files_modified": self.files_modified,
            "execution_time_ms": self.execution_time_ms,
        }


class AgentSkill:
    def __init__(
        self,
        agent: SubAgent,
        metadata: SkillMetadata,
    ) -> None:
        self.agent = agent
        self.metadata = metadata
        self.skill_id = f"skill_{uuid4().hex[:8]}"

    async def can_handle(self, issue: Issue) -> float:
        if issue.type not in self.metadata.supported_types:
            return 0.0

        agent_confidence = await self.agent.can_handle(issue)

        if agent_confidence >= self.metadata.confidence_threshold:
            return agent_confidence

        return 0.0

    async def execute(
        self,
        issue: Issue,
        timeout: int | None = None,
    ) -> SkillExecutionResult:
        import time

        start_time = time.time()

        try:
            if timeout:
                result = await asyncio.wait_for(
                    self.agent.analyze_and_fix(issue),
                    timeout=timeout,
                )
            else:
                result = await self.agent.analyze_and_fix(issue)

            execution_time_ms = int((time.time() - start_time) * 1000)

            self.metadata.execution_count += 1
            if result.success:
                alpha = 0.1
                self.metadata.success_rate = (
                    alpha * 1.0 + (1 - alpha) * self.metadata.success_rate
                )

            return SkillExecutionResult(
                skill_name=self.metadata.name,
                success=result.success,
                confidence=result.confidence,
                issues_handled=1,
                fixes_applied=result.fixes_applied,
                recommendations=result.recommendations,
                files_modified=result.files_modified,
                execution_time_ms=execution_time_ms,
            )

        except TimeoutError:
            return SkillExecutionResult(
                skill_name=self.metadata.name,
                success=False,
                confidence=0.0,
                issues_handled=0,
                fixes_applied=[],
                recommendations=[f"Skill execution timed out after {timeout}s"],
                files_modified=[],
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

        except Exception as e:
            return SkillExecutionResult(
                skill_name=self.metadata.name,
                success=False,
                confidence=0.0,
                issues_handled=0,
                fixes_applied=[],
                recommendations=[f"Skill execution failed: {e}"],
                files_modified=[],
                execution_time_ms=int((time.time() - start_time) * 1000),
            )

    def batch_execute(
        self,
        issues: list[Issue],
    ) -> t.Coroutine[t.Any, t.Any, list[SkillExecutionResult]]:
        async def _batch() -> list[SkillExecutionResult]:
            handleable = [i for i in issues if i.type in self.metadata.supported_types]

            tasks = [self.execute(issue) for issue in handleable]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)

            results: list[SkillExecutionResult] = []
            for result in raw_results:
                if isinstance(result, BaseException):
                    results.append(
                        SkillExecutionResult(
                            skill_name=self.skill_id,
                            success=False,
                            confidence=0.0,
                            issues_handled=0,
                            fixes_applied=[],
                            recommendations=[],
                            files_modified=[],
                            execution_time_ms=0,
                        )
                    )
                else:
                    results.append(result)

            return results

        return _batch()

    def get_info(self) -> dict[str, t.Any]:
        return {
            "skill_id": self.skill_id,
            "metadata": self.metadata.to_dict(),
            "agent_name": self.agent.name,
        }


class AgentSkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, AgentSkill] = {}
        self._category_index: dict[SkillCategory, list[str]] = {
            category: [] for category in SkillCategory
        }
        self._type_index: dict[IssueType, list[str]] = {
            issue_type: [] for issue_type in IssueType
        }

    def register(
        self,
        skill: AgentSkill,
    ) -> None:
        self._skills[skill.skill_id] = skill

        self._category_index[skill.metadata.category].append(skill.skill_id)

        for issue_type in skill.metadata.supported_types:
            self._type_index[issue_type].append(skill.skill_id)

    def register_agent(
        self,
        agent_class: type[SubAgent],
        context: AgentContext,
        metadata: SkillMetadata | None = None,
    ) -> AgentSkill:
        agent = agent_class(context)

        if metadata is None:
            metadata = self._generate_metadata(agent)

        skill = AgentSkill(agent, metadata)
        self.register(skill)

        return skill

    def register_all_agents(
        self,
        context: AgentContext,
    ) -> list[AgentSkill]:
        skills = []
        for agent_class in agent_registry._agents.values():
            try:
                skill = self.register_agent(agent_class, context)
                skills.append(skill)
            except Exception as e:
                print(f"Warning: Failed to register {agent_class.__name__}: {e}")

        return skills

    def get_skill(self, skill_id: str) -> AgentSkill | None:
        return self._skills.get(skill_id)

    def get_skills_by_category(
        self,
        category: SkillCategory,
    ) -> list[AgentSkill]:
        skill_ids = self._category_index.get(category, [])
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    def get_skills_for_type(
        self,
        issue_type: IssueType,
    ) -> list[AgentSkill]:
        skill_ids = self._type_index.get(issue_type, [])
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    def find_best_skill(
        self,
        issue: Issue,
    ) -> t.Coroutine[t.Any, t.Any, AgentSkill | None]:
        async def _find() -> AgentSkill | None:
            candidates = self.get_skills_for_type(issue.type)

            if not candidates:
                return None

            confidence_pairs = [
                (skill, await skill.can_handle(issue)) for skill in candidates
            ]

            valid_pairs = [(s, c) for s, c in confidence_pairs if c > 0]

            if not valid_pairs:
                return None

            valid_pairs.sort(key=operator.itemgetter(1), reverse=True)
            return valid_pairs[0][0]

        return _find()

    def list_all_skills(self) -> list[dict[str, t.Any]]:
        return [skill.get_info() for skill in self._skills.values()]

    def get_statistics(self) -> dict[str, t.Any]:
        return {
            "total_skills": len(self._skills),
            "skills_by_category": {
                cat.value: len(ids) for cat, ids in self._category_index.items()
            },
            "skills_by_type": {
                itype.value: len(ids) for itype, ids in self._type_index.items()
            },
            "total_executions": sum(
                skill.metadata.execution_count for skill in self._skills.values()
            ),
            "avg_success_rate": (
                sum(skill.metadata.success_rate for skill in self._skills.values())
                / len(self._skills)
                if self._skills
                else 0.0
            ),
        }

    def _generate_metadata(self, agent: SubAgent) -> SkillMetadata:
        agent_name = agent.name.lower()
        category = self._infer_category(agent_name)

        supported_types = agent.get_supported_types()

        description = (
            f"{agent.name} - handles {', '.join(t.value for t in supported_types)}"
        )

        tags = self._infer_tags(agent_name, supported_types)

        return SkillMetadata(
            name=agent.name,
            description=description,
            category=category,
            supported_types=supported_types,
            tags=tags,
        )

    def _infer_category(self, agent_name: str) -> SkillCategory:
        if "refactor" in agent_name or "complexity" in agent_name:
            return SkillCategory.CODE_QUALITY
        if "test" in agent_name:
            return SkillCategory.TESTING
        if "security" in agent_name:
            return SkillCategory.SECURITY
        if "performance" in agent_name:
            return SkillCategory.PERFORMANCE
        if "doc" in agent_name:
            return SkillCategory.DOCUMENTATION
        if "architect" in agent_name:
            return SkillCategory.ARCHITECTURE
        if "semantic" in agent_name:
            return SkillCategory.SEMANTIC
        if "proactive" in agent_name:
            return SkillCategory.PROACTIVE

        return SkillCategory.CODE_QUALITY

    def _infer_tags(
        self,
        agent_name: str,
        supported_types: set[IssueType],
    ) -> set[str]:
        tags = set()

        for word in agent_name.split("_"):
            if len(word) > 2:
                tags.add(word)

        tags.update(issue_type.value for issue_type in supported_types)

        return tags

from __future__ import annotations

import asyncio
import operator
import time
import typing as t
from dataclasses import dataclass, field
from enum import Enum
from typing import runtime_checkable
from uuid import uuid4

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)


def _elapsed_ms(start_time: float) -> int:
    return int((time.time() - start_time) * 1000)


@runtime_checkable
class _AgentWithExecute(t.Protocol):
    """Structural protocol for agents that expose ``execute(Issue | list[Issue])``.

    Used by :meth:`AgentSkill.execute` to dispatch between agents with the
    modern ``execute`` interface and those with the legacy
    ``analyze_and_fix`` interface. ``@runtime_checkable`` lets ``isinstance``
    narrow the agent type so static analysis (ty) sees the correct method.
    """

    async def execute(self, issue: Issue | list[Issue]) -> t.Any: ...


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
            "tags": self.tags.copy(),
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
        issue: Issue | list[Issue],
        timeout: int | None = None,
    ) -> SkillExecutionResult:
        start_time = time.time()
        issues, agent_input, issues_handled = self._prepare_input(issue)

        try:
            run_coro = self._build_run_coro(agent_input)
            result = await self._invoke(run_coro, timeout)
            execution_time_ms = _elapsed_ms(start_time)

            self.metadata.execution_count += 1
            success, fixes_applied, recommendations, files_modified, confidence = (
                self._extract_result_fields(result)
            )
            self._update_success_rate(success)

            return self._build_success_result(
                success=success,
                confidence=confidence,
                issues_handled=issues_handled,
                fixes_applied=fixes_applied,
                recommendations=recommendations,
                files_modified=files_modified,
                execution_time_ms=execution_time_ms,
            )

        except TimeoutError:
            return self._failure_result(
                recommendation=f"Skill execution timed out after {timeout}s",
                elapsed_ms=_elapsed_ms(start_time),
            )

        except Exception as e:
            return self._failure_result(
                recommendation=f"Skill execution failed: {e}",
                elapsed_ms=_elapsed_ms(start_time),
            )

    def _prepare_input(
        self,
        issue: Issue | list[Issue],
    ) -> tuple[list[Issue], Issue | list[Issue], int]:
        issues: list[Issue] = (
            t.cast("list[Issue]", issue)
            if isinstance(issue, list)
            else [t.cast("Issue", issue)]
        )
        issues_handled = len(issues)
        agent_input: Issue | list[Issue] = issues[0] if len(issues) == 1 else issues
        return issues, agent_input, issues_handled

    def _build_run_coro(
        self,
        agent_input: Issue | list[Issue],
    ) -> t.Coroutine[t.Any, t.Any, t.Any]:
        if isinstance(self.agent, _AgentWithExecute):
            # Modern interface: takes Issue | list[Issue]
            return self.agent.execute(agent_input)
        if isinstance(agent_input, Issue) and hasattr(self.agent, "analyze_and_fix"):
            # Legacy interface: takes single Issue only
            return self.agent.analyze_and_fix(agent_input)
        msg = (
            f"Agent {type(self.agent).__name__} has neither execute() "
            "nor analyze_and_fix()"
        )
        raise AttributeError(msg)

    @staticmethod
    async def _invoke(
        run_coro: t.Coroutine[t.Any, t.Any, t.Any],
        timeout: int | None,
    ) -> t.Any:
        if timeout:
            return await asyncio.wait_for(run_coro, timeout=timeout)
        return await run_coro

    @staticmethod
    def _extract_result_fields(
        result: t.Any,
    ) -> tuple[bool, list[str], list[str], list[str], float]:
        # Agent results are either a dict (legacy/duck-typed) or a
        # ``FixResult`` dataclass. ``t.cast`` at the boundary gives
        # ty concrete types for downstream attribute access.
        result_obj: dict[str, t.Any] | FixResult = t.cast(
            "dict[str, t.Any] | FixResult", result
        )
        if isinstance(result_obj, dict):
            # ty can't infer dict-element types from a ``dict[str, t.Any]``,
            # so extract each value into a typed ``t.Any`` local before
            # subscripting or numeric conversion.
            raw_fixes: t.Any = result_obj.get("fixes_applied", [])
            raw_recs: t.Any = result_obj.get("recommendations", [])
            raw_files: t.Any = result_obj.get("files_modified", [])
            raw_conf: t.Any = result_obj.get("confidence", 0.8)
            raw_success: t.Any = result_obj.get("success", False)
            fixes_applied: list[str] = [str(x) for x in raw_fixes]
            recommendations: list[str] = [str(x) for x in raw_recs]
            files_modified: list[str] = [str(x) for x in raw_files]
            confidence = float(raw_conf)
            success = bool(raw_success)
            return success, fixes_applied, recommendations, files_modified, confidence

        success = bool(getattr(result_obj, "success", False))
        fixes_applied = [str(x) for x in getattr(result_obj, "fixes_applied", [])]
        recommendations = [str(x) for x in getattr(result_obj, "recommendations", [])]
        files_modified = [str(x) for x in getattr(result_obj, "files_modified", [])]
        confidence = float(getattr(result_obj, "confidence", 0.8))
        return success, fixes_applied, recommendations, files_modified, confidence

    def _update_success_rate(self, success: bool) -> None:
        if not success:
            return
        alpha = 0.1
        self.metadata.success_rate = (
            alpha * 1.0 + (1 - alpha) * self.metadata.success_rate
        )

    def _build_success_result(
        self,
        *,
        success: bool,
        confidence: float,
        issues_handled: int,
        fixes_applied: list[str],
        recommendations: list[str],
        files_modified: list[str],
        execution_time_ms: int,
    ) -> SkillExecutionResult:
        return SkillExecutionResult(
            skill_name=self.metadata.name,
            success=success,
            confidence=confidence,
            issues_handled=issues_handled,
            fixes_applied=fixes_applied,
            recommendations=recommendations,
            files_modified=files_modified,
            execution_time_ms=execution_time_ms,
        )

    def _failure_result(
        self,
        *,
        recommendation: str,
        elapsed_ms: int,
    ) -> SkillExecutionResult:
        return SkillExecutionResult(
            skill_name=self.metadata.name,
            success=False,
            confidence=0.0,
            issues_handled=0,
            fixes_applied=[],
            recommendations=[recommendation],
            files_modified=[],
            execution_time_ms=elapsed_ms,
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
                        ),
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
        from contextlib import suppress

        skills = []
        for agent_class in agent_registry._agents.values():
            with suppress(Exception):
                skill = self.register_agent(agent_class, context)
                skills.append(skill)

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

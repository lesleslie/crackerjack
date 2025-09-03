import logging
import typing as t
from dataclasses import dataclass

from crackerjack.agents.base import AgentContext, FixResult, Issue

from .adaptive_learning import get_learning_system
from .agent_orchestrator import (
    ExecutionRequest,
    ExecutionStrategy,
    get_agent_orchestrator,
)
from .agent_registry import get_agent_registry
from .agent_selector import TaskContext, TaskDescription


@dataclass
class SmartAgentResult:
    success: bool
    result: t.Any
    agents_used: list[str]
    execution_time: float
    confidence: float
    recommendations: list[str]
    learning_applied: bool = False


class IntelligentAgentSystem:
    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        self.logger.info("Initializing Intelligent Agent System")

        self.registry = await get_agent_registry()
        self.orchestrator = await get_agent_orchestrator()
        self.learning_system = await get_learning_system()

        self._initialized = True

        stats = self.registry.get_agent_stats()
        self.logger.info(
            f"System initialized: {stats['total_agents']} agents available "
            f"({stats['by_source']})"
        )

    async def execute_smart_task(
        self,
        description: str,
        context: TaskContext | None = None,
        strategy: ExecutionStrategy = ExecutionStrategy.SINGLE_BEST,
        context_data: AgentContext | None = None,
    ) -> SmartAgentResult:
        await self.initialize()

        task = TaskDescription(
            description=description,
            context=context,
        )

        candidates = await self.orchestrator.selector.select_agents(
            task, max_candidates=5
        )
        candidate_names = [c.agent.metadata.name for c in candidates]

        learning_recommendations = self.learning_system.get_agent_recommendations(
            task, candidate_names
        )

        for candidate in candidates:
            agent_name = candidate.agent.metadata.name
            if agent_name in learning_recommendations:
                learning_boost = learning_recommendations[agent_name] * 0.2
                candidate.final_score = min(1.0, candidate.final_score + learning_boost)

        candidates.sort(key=lambda c: c.final_score, reverse=True)

        request = ExecutionRequest(
            task=task,
            strategy=strategy,
            max_agents=min(3, len(candidates)),
            context=context_data,
        )

        result = await self.orchestrator.execute(request)

        if candidates:
            best_candidate = candidates[0]
            await self.learning_system.record_execution(
                agent=best_candidate.agent,
                task=task,
                success=result.success,
                execution_time=result.execution_time,
                agent_score=best_candidate,
                error_message=result.error_message,
            )

        return SmartAgentResult(
            success=result.success,
            result=result.primary_result,
            agents_used=result.agents_used,
            execution_time=result.execution_time,
            confidence=candidates[0].final_score if candidates else 0.0,
            recommendations=result.recommendations or [],
            learning_applied=bool(learning_recommendations),
        )

    async def handle_crackerjack_issue(
        self,
        issue: Issue,
        context: AgentContext,
        use_learning: bool = True,
    ) -> FixResult:
        await self.initialize()

        task_context = self._map_issue_to_task_context(issue)

        task = TaskDescription(
            description=f"Fix {issue.type.value} issue: {issue.message}",
            context=task_context,
            error_types=[issue.type.value],
            priority=self._map_severity_to_priority(issue.severity),
        )

        smart_result = await self.execute_smart_task(
            description=task.description,
            context=task_context,
            context_data=context,
        )

        if smart_result.success and isinstance(smart_result.result, FixResult):
            return smart_result.result

        return FixResult(
            success=smart_result.success,
            confidence=smart_result.confidence,
            remaining_issues=[issue.message] if not smart_result.success else [],
            recommendations=smart_result.recommendations,
            fixes_applied=[
                f"Applied using intelligent agent: {', '.join(smart_result.agents_used)}"
            ]
            if smart_result.success
            else [],
        )

    async def get_best_agent_for_task(
        self,
        description: str,
        context: TaskContext | None = None,
    ) -> tuple[str, float] | None:
        await self.initialize()

        task = TaskDescription(description=description, context=context)
        best_candidate = await self.orchestrator.selector.select_best_agent(task)

        if best_candidate:
            return best_candidate.agent.metadata.name, best_candidate.final_score
        return None

    async def analyze_task_complexity(self, description: str) -> dict[str, t.Any]:
        await self.initialize()

        task = TaskDescription(description=description)
        return await self.orchestrator.selector.analyze_task_complexity(task)

    def _map_issue_to_task_context(self, issue: Issue) -> TaskContext | None:
        from crackerjack.agents.base import IssueType

        mapping = {
            IssueType.COMPLEXITY: TaskContext.REFACTORING,
            IssueType.DRY_VIOLATION: TaskContext.REFACTORING,
            IssueType.PERFORMANCE: TaskContext.PERFORMANCE,
            IssueType.SECURITY: TaskContext.SECURITY,
            IssueType.TEST_FAILURE: TaskContext.TESTING,
            IssueType.FORMATTING: TaskContext.CODE_QUALITY,
            IssueType.IMPORT_ERROR: TaskContext.CODE_QUALITY,
            IssueType.TYPE_ERROR: TaskContext.CODE_QUALITY,
            IssueType.DOCUMENTATION: TaskContext.DOCUMENTATION,
            IssueType.DEAD_CODE: TaskContext.REFACTORING,
            IssueType.DEPENDENCY: TaskContext.CODE_QUALITY,
            IssueType.TEST_ORGANIZATION: TaskContext.TESTING,
        }

        return mapping.get(issue.type) or TaskContext.GENERAL

    def _map_severity_to_priority(self, severity: t.Any) -> int:
        from crackerjack.agents.base import Priority

        mapping = {
            Priority.HIGH: 90,
            Priority.MEDIUM: 60,
            Priority.LOW: 30,
        }

        return mapping.get(severity) or 50

    async def get_system_status(self) -> dict[str, t.Any]:
        await self.initialize()

        registry_stats = self.registry.get_agent_stats()
        orchestrator_stats = self.orchestrator.get_execution_stats()
        learning_summary = self.learning_system.get_learning_summary()

        return {
            "initialized": self._initialized,
            "registry": registry_stats,
            "orchestration": orchestrator_stats,
            "learning": learning_summary,
        }


_intelligent_system_instance: IntelligentAgentSystem | None = None


async def get_intelligent_agent_system() -> IntelligentAgentSystem:
    global _intelligent_system_instance

    if _intelligent_system_instance is None:
        _intelligent_system_instance = IntelligentAgentSystem()

    return _intelligent_system_instance


async def smart_fix_issue(
    issue: Issue,
    context: AgentContext,
) -> FixResult:
    system = await get_intelligent_agent_system()
    return await system.handle_crackerjack_issue(issue, context)


async def smart_execute_task(
    description: str,
    context: TaskContext | None = None,
    strategy: ExecutionStrategy = ExecutionStrategy.SINGLE_BEST,
) -> SmartAgentResult:
    system = await get_intelligent_agent_system()
    return await system.execute_smart_task(description, context, strategy)


async def get_smart_recommendation(
    description: str,
    context: TaskContext | None = None,
) -> tuple[str, float] | None:
    system = await get_intelligent_agent_system()
    return await system.get_best_agent_for_task(description, context)

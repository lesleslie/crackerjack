"""Integration layer for Intelligent Agent Selection System.

Provides high-level API for integrating the intelligent agent system with
existing crackerjack workflows and MCP tools.
"""

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
    """Result from smart agent execution."""

    success: bool
    result: t.Any
    agents_used: list[str]
    execution_time: float
    confidence: float
    recommendations: list[str]
    learning_applied: bool = False


class IntelligentAgentSystem:
    """High-level interface to the intelligent agent system."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the intelligent agent system."""
        if self._initialized:
            return

        self.logger.info("Initializing Intelligent Agent System")

        # Initialize all components
        self.registry = await get_agent_registry()
        self.orchestrator = await get_agent_orchestrator()
        self.learning_system = await get_learning_system()

        self._initialized = True

        # Log system status
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
        """Execute a task using intelligent agent selection."""
        await self.initialize()

        # Create task description
        task = TaskDescription(
            description=description,
            context=context,
        )

        # Get learning recommendations
        candidates = await self.orchestrator.selector.select_agents(
            task, max_candidates=5
        )
        candidate_names = [c.agent.metadata.name for c in candidates]

        learning_recommendations = self.learning_system.get_agent_recommendations(
            task, candidate_names
        )

        # Apply learning to boost scores
        for candidate in candidates:
            agent_name = candidate.agent.metadata.name
            if agent_name in learning_recommendations:
                learning_boost = (
                    learning_recommendations[agent_name] * 0.2
                )  # 20% boost max
                candidate.final_score = min(1.0, candidate.final_score + learning_boost)

        # Re-sort by updated scores
        candidates.sort(key=lambda c: c.final_score, reverse=True)

        # Create execution request
        request = ExecutionRequest(
            task=task,
            strategy=strategy,
            max_agents=min(3, len(candidates)),
            context=context_data,
        )

        # Execute with orchestrator
        result = await self.orchestrator.execute(request)

        # Record results for learning
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

        # Create smart result
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
        """Handle a crackerjack Issue using intelligent agent selection."""
        await self.initialize()

        # Convert issue to task description
        task_context = self._map_issue_to_task_context(issue)

        task = TaskDescription(
            description=f"Fix {issue.type.value} issue: {issue.message}",
            context=task_context,
            error_types=[issue.type.value],
            priority=self._map_severity_to_priority(issue.severity),
        )

        # Execute smart task
        smart_result = await self.execute_smart_task(
            description=task.description,
            context=task_context,
            context_data=context,
        )

        # Convert result back to FixResult
        if smart_result.success and isinstance(smart_result.result, FixResult):
            return smart_result.result

        # Create fallback FixResult
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
        """Get the best agent for a task without executing it."""
        await self.initialize()

        task = TaskDescription(description=description, context=context)
        best_candidate = await self.orchestrator.selector.select_best_agent(task)

        if best_candidate:
            return best_candidate.agent.metadata.name, best_candidate.final_score
        return None

    async def analyze_task_complexity(self, description: str) -> dict[str, t.Any]:
        """Analyze a task's complexity and provide recommendations."""
        await self.initialize()

        task = TaskDescription(description=description)
        return await self.orchestrator.selector.analyze_task_complexity(task)

    def _map_issue_to_task_context(self, issue: Issue) -> TaskContext | None:
        """Map crackerjack Issue type to TaskContext."""
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
        """Map crackerjack Priority to task priority."""
        from crackerjack.agents.base import Priority

        mapping = {
            Priority.HIGH: 90,
            Priority.MEDIUM: 60,
            Priority.LOW: 30,
        }

        return mapping.get(severity) or 50

    async def get_system_status(self) -> dict[str, t.Any]:
        """Get comprehensive system status."""
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


# Global intelligent agent system
_intelligent_system_instance: IntelligentAgentSystem | None = None


async def get_intelligent_agent_system() -> IntelligentAgentSystem:
    """Get or create the global intelligent agent system."""
    global _intelligent_system_instance

    if _intelligent_system_instance is None:
        _intelligent_system_instance = IntelligentAgentSystem()

    return _intelligent_system_instance


# Convenience functions for common use cases
async def smart_fix_issue(
    issue: Issue,
    context: AgentContext,
) -> FixResult:
    """Fix an issue using intelligent agent selection."""
    system = await get_intelligent_agent_system()
    return await system.handle_crackerjack_issue(issue, context)


async def smart_execute_task(
    description: str,
    context: TaskContext | None = None,
    strategy: ExecutionStrategy = ExecutionStrategy.SINGLE_BEST,
) -> SmartAgentResult:
    """Execute a task using intelligent agent selection."""
    system = await get_intelligent_agent_system()
    return await system.execute_smart_task(description, context, strategy)


async def get_smart_recommendation(
    description: str,
    context: TaskContext | None = None,
) -> tuple[str, float] | None:
    """Get a smart agent recommendation without executing."""
    system = await get_intelligent_agent_system()
    return await system.get_best_agent_for_task(description, context)

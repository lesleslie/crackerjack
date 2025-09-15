import asyncio
import logging
import typing as t
from dataclasses import dataclass
from enum import Enum

from crackerjack.agents.base import AgentContext, Issue

from .agent_registry import (
    AgentRegistry,
    AgentSource,
    RegisteredAgent,
    get_agent_registry,
)
from .agent_selector import AgentScore, AgentSelector, TaskDescription


class ExecutionStrategy(Enum):
    SINGLE_BEST = "single_best"
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    CONSENSUS = "consensus"


class ExecutionMode(Enum):
    AUTONOMOUS = "autonomous"
    GUIDED = "guided"
    ADVISORY = "advisory"


@dataclass
class ExecutionRequest:
    task: TaskDescription
    strategy: ExecutionStrategy = ExecutionStrategy.SINGLE_BEST
    mode: ExecutionMode = ExecutionMode.AUTONOMOUS
    max_agents: int = 3
    timeout_seconds: int = 300
    fallback_to_system: bool = True
    context: AgentContext | None = None


@dataclass
class ExecutionResult:
    success: bool
    primary_result: t.Any | None
    all_results: list[tuple[RegisteredAgent, t.Any]]
    execution_time: float
    agents_used: list[str]
    strategy_used: ExecutionStrategy
    error_message: str | None = None
    recommendations: list[str] | None = None


class AgentOrchestrator:
    def __init__(
        self,
        registry: AgentRegistry | None = None,
        selector: AgentSelector | None = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.registry = registry
        self.selector = selector or AgentSelector(registry)
        self._execution_stats: dict[str, int] = {}

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        start_time = asyncio.get_event_loop().time()

        try:
            self.logger.info(
                f"Executing request: {request.task.description[:50]}... "
                f"(strategy: {request.strategy.value})"
            )

            candidates = await self.selector.select_agents(
                request.task, max_candidates=request.max_agents
            )

            if not candidates:
                return self._create_error_result(
                    "No suitable agents found for task",
                    start_time,
                    request.strategy,
                )

            if request.strategy == ExecutionStrategy.SINGLE_BEST:
                result = await self._execute_single_best(request, candidates)
            elif request.strategy == ExecutionStrategy.PARALLEL:
                result = await self._execute_parallel(request, candidates)
            elif request.strategy == ExecutionStrategy.SEQUENTIAL:
                result = await self._execute_sequential(request, candidates)
            elif request.strategy == ExecutionStrategy.CONSENSUS:
                result = await self._execute_consensus(request, candidates)

            execution_time = asyncio.get_event_loop().time() - start_time
            result.execution_time = execution_time

            for agent_name in result.agents_used:
                self._execution_stats[agent_name] = (
                    self._execution_stats.get(agent_name, 0) + 1
                )

            self.logger.info(
                f"Execution completed in {execution_time: .2f}s: "
                f"{'success' if result.success else 'failure'} "
                f"using {len(result.agents_used)} agents"
            )

            return result

        except Exception as e:
            self.logger.exception(f"Execution failed: {e}")
            return self._create_error_result(
                f"Execution error: {e}",
                start_time,
                request.strategy,
            )

    async def _execute_single_best(
        self,
        request: ExecutionRequest,
        candidates: list[AgentScore],
    ) -> ExecutionResult:
        best_candidate = candidates[0]

        try:
            result = await self._execute_agent(best_candidate.agent, request)

            return ExecutionResult(
                success=True,
                primary_result=result,
                all_results=[(best_candidate.agent, result)],
                execution_time=0.0,
                agents_used=[best_candidate.agent.metadata.name],
                strategy_used=ExecutionStrategy.SINGLE_BEST,
                recommendations=self._generate_recommendations(best_candidate),
            )

        except Exception as e:
            if len(candidates) > 1 and request.fallback_to_system:
                self.logger.warning(
                    f"Primary agent {best_candidate.agent.metadata.name} failed: {e}. "
                    f"Trying fallback..."
                )

                fallback_request = ExecutionRequest(
                    task=request.task,
                    strategy=ExecutionStrategy.SEQUENTIAL,
                    mode=request.mode,
                    max_agents=len(candidates) - 1,
                    timeout_seconds=request.timeout_seconds,
                    fallback_to_system=False,
                    context=request.context,
                )

                return await self._execute_sequential(fallback_request, candidates[1:])

            return ExecutionResult(
                success=False,
                primary_result=None,
                all_results=[(best_candidate.agent, e)],
                execution_time=0.0,
                agents_used=[],
                strategy_used=ExecutionStrategy.SINGLE_BEST,
                error_message=str(e),
            )

    async def _execute_parallel(
        self,
        request: ExecutionRequest,
        candidates: list[AgentScore],
    ) -> ExecutionResult:
        tasks = []
        agents_to_execute = candidates[: request.max_agents]

        for candidate in agents_to_execute:
            task = asyncio.create_task(
                self._execute_agent_safe(candidate.agent, request)
            )
            tasks.append((candidate.agent, task))

        results = []
        successful_results = []

        for agent, task in tasks:
            try:
                result = await asyncio.wait_for(task, timeout=request.timeout_seconds)
                results.append((agent, result))
                if not isinstance(result, Exception):
                    successful_results.append((agent, result))
            except TimeoutError:
                results.append((agent, TimeoutError("Agent execution timed out")))
            except Exception as e:
                results.append((agent, e))

        primary_result = None
        agents_used = []

        if successful_results:
            successful_results.sort(key=lambda x: x[0].metadata.priority, reverse=True)
            primary_result = successful_results[0][1]
            agents_used = [agent.metadata.name for agent, _ in successful_results]

        return ExecutionResult(
            success=len(successful_results) > 0,
            primary_result=primary_result,
            all_results=results,
            execution_time=0.0,
            agents_used=agents_used,
            strategy_used=ExecutionStrategy.PARALLEL,
            error_message=None if successful_results else "All parallel agents failed",
        )

    async def _execute_sequential(
        self,
        request: ExecutionRequest,
        candidates: list[AgentScore],
    ) -> ExecutionResult:
        results = []

        for candidate in candidates[: request.max_agents]:
            try:
                result = await asyncio.wait_for(
                    self._execute_agent(candidate.agent, request),
                    timeout=request.timeout_seconds,
                )

                results.append((candidate.agent, result))

                return ExecutionResult(
                    success=True,
                    primary_result=result,
                    all_results=results,
                    execution_time=0.0,
                    agents_used=[candidate.agent.metadata.name],
                    strategy_used=ExecutionStrategy.SEQUENTIAL,
                    recommendations=self._generate_recommendations(candidate),
                )

            except Exception as e:
                results.append((candidate.agent, e))
                self.logger.warning(
                    f"Sequential agent {candidate.agent.metadata.name} failed: {e}"
                )

        return ExecutionResult(
            success=False,
            primary_result=None,
            all_results=results,
            execution_time=0.0,
            agents_used=[],
            strategy_used=ExecutionStrategy.SEQUENTIAL,
            error_message="All sequential agents failed",
        )

    async def _execute_consensus(
        self,
        request: ExecutionRequest,
        candidates: list[AgentScore],
    ) -> ExecutionResult:
        parallel_request = ExecutionRequest(
            task=request.task,
            strategy=ExecutionStrategy.PARALLEL,
            mode=request.mode,
            max_agents=min(request.max_agents, 3),
            timeout_seconds=request.timeout_seconds,
            fallback_to_system=False,
            context=request.context,
        )

        parallel_result = await self._execute_parallel(parallel_request, candidates)

        if not parallel_result.success:
            return parallel_result

        successful_results = [
            (agent, result)
            for agent, result in parallel_result.all_results
            if not isinstance(result, Exception)
        ]

        if len(successful_results) < 2:
            return parallel_result

        consensus_result = self._build_consensus(successful_results)

        return ExecutionResult(
            success=True,
            primary_result=consensus_result,
            all_results=parallel_result.all_results,
            execution_time=parallel_result.execution_time,
            agents_used=parallel_result.agents_used,
            strategy_used=ExecutionStrategy.CONSENSUS,
            recommendations=["Results validated through multi-agent consensus"],
        )

    async def _execute_agent(
        self, agent: RegisteredAgent, request: ExecutionRequest
    ) -> t.Any:
        if agent.agent is not None:
            return await self._execute_crackerjack_agent(agent, request)
        elif agent.agent_path is not None:
            return await self._execute_user_agent(agent, request)
        elif agent.subagent_type is not None:
            return await self._execute_system_agent(agent, request)
        else:
            raise ValueError(f"Invalid agent configuration: {agent.metadata.name}")

    async def _execute_agent_safe(
        self, agent: RegisteredAgent, request: ExecutionRequest
    ) -> t.Any:
        try:
            return await self._execute_agent(agent, request)
        except Exception as e:
            return e

    async def _execute_crackerjack_agent(
        self,
        agent: RegisteredAgent,
        request: ExecutionRequest,
    ) -> t.Any:
        if not agent.agent:
            raise ValueError("No crackerjack agent instance available")

        issue = Issue(
            id="orchestrated_task",
            type=self._map_task_to_issue_type(request.task),
            severity=self._map_task_priority_to_severity(request.task),
            message=request.task.description,
            file_path=None,
        )

        result = await agent.agent.analyze_and_fix(issue)
        return result

    async def _execute_user_agent(
        self,
        agent: RegisteredAgent,
        request: ExecutionRequest,
    ) -> t.Any:
        from crackerjack.mcp.tools.core_tools import create_task_with_subagent

        result = await create_task_with_subagent(
            description=f"Execute task using {agent.metadata.name}",
            prompt=request.task.description,
            subagent_type=agent.metadata.name,
        )

        return result

    async def _execute_system_agent(
        self,
        agent: RegisteredAgent,
        request: ExecutionRequest,
    ) -> t.Any:
        if not agent.subagent_type:
            raise ValueError("No subagent type specified for system agent")

        from crackerjack.mcp.tools.core_tools import create_task_with_subagent

        result = await create_task_with_subagent(
            description=f"Execute task using {agent.metadata.name}",
            prompt=request.task.description,
            subagent_type=agent.subagent_type,
        )

        return result

    def _map_task_to_issue_type(self, task: TaskDescription) -> t.Any:
        from crackerjack.agents.base import IssueType

        context_map = {
            "code_quality": IssueType.FORMATTING,
            "refactoring": IssueType.COMPLEXITY,
            "testing": IssueType.TEST_FAILURE,
            "security": IssueType.SECURITY,
            "performance": IssueType.PERFORMANCE,
            "documentation": IssueType.DOCUMENTATION,
        }

        if task.context and task.context.value in context_map:
            return context_map[task.context.value]

        desc_lower = task.description.lower()
        if "test" in desc_lower:
            return IssueType.TEST_FAILURE
        elif "refurb" in desc_lower or "complexity" in desc_lower:
            return IssueType.COMPLEXITY
        elif "security" in desc_lower:
            return IssueType.SECURITY
        elif "format" in desc_lower:
            return IssueType.FORMATTING

        return IssueType.FORMATTING

    def _map_task_priority_to_severity(self, task: TaskDescription) -> t.Any:
        from crackerjack.agents.base import Priority

        if task.priority >= 80:
            return Priority.HIGH
        elif task.priority >= 50:
            return Priority.MEDIUM

        return Priority.LOW

    def _build_consensus(self, results: list[tuple[RegisteredAgent, t.Any]]) -> t.Any:
        results.sort(key=lambda x: x[0].metadata.priority, reverse=True)
        return results[0][1]

    def _generate_recommendations(self, candidate: AgentScore) -> list[str]:
        recommendations = []

        if candidate.final_score > 0.8:
            recommendations.append("High confidence in agent selection")
        elif candidate.final_score > 0.6:
            recommendations.append("Good agent match for this task")
        else:
            recommendations.append("Consider manual review of results")

        if candidate.agent.metadata.source == AgentSource.CRACKERJACK:
            recommendations.append("Using specialized built-in agent")
        elif candidate.agent.metadata.source == AgentSource.USER:
            recommendations.append("Using custom user agent")
        else:
            recommendations.append("Using general-purpose system agent")

        return recommendations

    def _create_error_result(
        self,
        error_message: str,
        start_time: float,
        strategy: ExecutionStrategy,
    ) -> ExecutionResult:
        execution_time = asyncio.get_event_loop().time() - start_time

        return ExecutionResult(
            success=False,
            primary_result=None,
            all_results=[],
            execution_time=execution_time,
            agents_used=[],
            strategy_used=strategy,
            error_message=error_message,
        )

    def get_execution_stats(self) -> dict[str, t.Any]:
        from operator import itemgetter

        return {
            "total_executions": sum(self._execution_stats.values()),
            "agent_usage": self._execution_stats.copy(),
            "most_used_agent": max(
                self._execution_stats.items(), key=itemgetter(1), default=("none", 0)
            )[0]
            if self._execution_stats
            else "none",
        }

    async def analyze_task_routing(self, task: TaskDescription) -> dict[str, t.Any]:
        analysis = await self.selector.analyze_task_complexity(task)

        if analysis["complexity_level"] == "high":
            analysis["recommended_strategy"] = ExecutionStrategy.CONSENSUS
        elif analysis["candidate_count"] > 3:
            analysis["recommended_strategy"] = ExecutionStrategy.PARALLEL
        elif analysis["candidate_count"] > 1:
            analysis["recommended_strategy"] = ExecutionStrategy.SEQUENTIAL
        else:
            analysis["recommended_strategy"] = ExecutionStrategy.SINGLE_BEST

        return analysis


_orchestrator_instance: AgentOrchestrator | None = None


async def get_agent_orchestrator() -> AgentOrchestrator:
    global _orchestrator_instance

    if _orchestrator_instance is None:
        registry = await get_agent_registry()
        selector = AgentSelector(registry)
        _orchestrator_instance = AgentOrchestrator(registry, selector)

    return _orchestrator_instance

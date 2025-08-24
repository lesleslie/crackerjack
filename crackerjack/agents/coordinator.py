import asyncio
import logging
import operator
import typing as t
from collections import defaultdict

from crackerjack.services.debug import get_ai_agent_debugger

from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
    SubAgent,
    agent_registry,
)
from .tracker import get_agent_tracker


class AgentCoordinator:
    def __init__(self, context: AgentContext) -> None:
        self.context = context
        self.agents: list[SubAgent] = []
        self.logger = logging.getLogger(__name__)
        self._issue_cache: dict[str, FixResult] = {}
        self._collaboration_threshold = 0.7
        self.tracker = get_agent_tracker()
        self.debugger = get_ai_agent_debugger()

    def initialize_agents(self) -> None:
        self.agents = agent_registry.create_all(self.context)
        agent_types = [a.name for a in self.agents]
        self.logger.info(f"Initialized {len(self.agents)} agents: {agent_types}")

        self.tracker.register_agents(agent_types)
        self.tracker.set_coordinator_status("active")

        self.debugger.log_agent_activity(
            agent_name="coordinator",
            activity="agents_initialized",
            metadata={"agent_count": len(self.agents), "agent_types": agent_types},
        )

    async def handle_issues(self, issues: list[Issue]) -> FixResult:
        if not self.agents:
            self.initialize_agents()

        if not issues:
            return FixResult(success=True, confidence=1.0)

        self.logger.info(f"Handling {len(issues)} issues")

        issues_by_type = self._group_issues_by_type(issues)

        overall_result = FixResult(success=True, confidence=1.0)

        for issue_type, type_issues in issues_by_type.items():
            type_result = await self._handle_issues_by_type(issue_type, type_issues)
            overall_result = overall_result.merge_with(type_result)

        return overall_result

    async def handle_single_issue(self, issue: Issue) -> FixResult:
        if not self.agents:
            self.initialize_agents()

        cache_key = issue.context_key
        if cache_key in self._issue_cache:
            cached_result = self._issue_cache[cache_key]
            self.logger.info(f"Using cached result for {cache_key}")
            self.tracker.track_cache_hit()
            return cached_result

        self.tracker.track_cache_miss()

        agent_scores = await self._evaluate_agents_for_issue(issue)

        if not agent_scores:
            self.logger.warning(f"No agents can handle issue: {issue.message}")
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"No agent available for: {issue.message}"],
                recommendations=["Manual intervention required"],
            )

        best_agent, best_score = agent_scores[0]

        if best_score >= self._collaboration_threshold:
            result = await self._handle_with_single_agent(best_agent, issue)
        else:
            result = await self._handle_with_collaboration(agent_scores[:3], issue)

        self._issue_cache[cache_key] = result

        return result

    async def _handle_issues_by_type(
        self, issue_type: IssueType, issues: list[Issue],
    ) -> FixResult:
        self.logger.info(f"Handling {len(issues)} {issue_type.value} issues")

        specialist_agents = [
            agent for agent in self.agents if issue_type in agent.get_supported_types()
        ]

        if not specialist_agents:
            self.logger.warning(f"No specialist agents for {issue_type.value}")
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"No agents for {issue_type.value} issues"],
            )

        tasks: list[t.Coroutine[t.Any, t.Any, FixResult]] = []
        for issue in issues:
            best_specialist = await self._find_best_specialist(specialist_agents, issue)
            if best_specialist:
                task = self._handle_with_single_agent(best_specialist, issue)
                tasks.append(task)

        if not tasks:
            return FixResult(success=False, confidence=0.0)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        combined_result = FixResult(success=True, confidence=1.0)
        for result in results:
            if isinstance(result, FixResult):
                combined_result = combined_result.merge_with(result)
            else:
                self.logger.error(f"Agent task failed: {result}")
                combined_result.success = False
                combined_result.remaining_issues.append(f"Agent failed: {result}")

        return combined_result

    async def _evaluate_agents_for_issue(
        self, issue: Issue,
    ) -> list[tuple[SubAgent, float]]:
        evaluations: list[tuple[SubAgent, float]] = []

        for agent in self.agents:
            try:
                confidence = await agent.can_handle(issue)
                if confidence > 0.0:
                    evaluations.append((agent, confidence))
            except Exception as e:
                self.logger.exception(f"Error evaluating {agent.name} for issue: {e}")

        evaluations.sort(key=operator.itemgetter(1), reverse=True)
        return evaluations

    async def _find_best_specialist(
        self, specialists: list[SubAgent], issue: Issue,
    ) -> SubAgent | None:
        best_agent = None
        best_score = 0.0

        for agent in specialists:
            try:
                score = await agent.can_handle(issue)
                if score > best_score:
                    best_score = score
                    best_agent = agent
            except Exception as e:
                self.logger.exception(f"Error evaluating specialist {agent.name}: {e}")

        return best_agent

    async def _handle_with_single_agent(
        self, agent: SubAgent, issue: Issue,
    ) -> FixResult:
        self.logger.info(f"Handling issue with {agent.name}: {issue.message[:100]}")

        confidence = await agent.can_handle(issue)
        self.tracker.track_agent_processing(agent.name, issue, confidence)

        self.debugger.log_agent_activity(
            agent_name=agent.name,
            activity="processing_started",
            issue_id=issue.id,
            confidence=confidence,
            metadata={"issue_type": issue.type.value, "severity": issue.severity.value},
        )

        try:
            result = await agent.analyze_and_fix(issue)
            if result.success:
                self.logger.info(f"{agent.name} successfully fixed issue")
            else:
                self.logger.warning(f"{agent.name} failed to fix issue")

            self.tracker.track_agent_complete(agent.name, result)

            self.debugger.log_agent_activity(
                agent_name=agent.name,
                activity="processing_completed",
                issue_id=issue.id,
                confidence=result.confidence,
                result={
                    "success": result.success,
                    "remaining_issues": len(result.remaining_issues),
                },
                metadata={"fix_applied": result.success},
            )

            return result
        except Exception as e:
            self.logger.exception(f"{agent.name} threw exception: {e}")
            error_result = FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"{agent.name} failed with exception: {e}"],
            )

            self.tracker.track_agent_complete(agent.name, error_result)
            return error_result

    async def _handle_with_collaboration(
        self, agent_scores: list[tuple[SubAgent, float]], issue: Issue,
    ) -> FixResult:
        self.logger.info(
            f"Using collaborative approach for issue: {issue.message[:100]}",
        )

        results: list[FixResult] = []

        for agent, _ in agent_scores:
            try:
                result = await agent.analyze_and_fix(issue)
                results.append(result)

                if result.success and result.confidence >= 0.8:
                    self.logger.info(f"{agent.name} solved issue with high confidence")
                    break

            except Exception as e:
                self.logger.exception(f"Collaborative agent {agent.name} failed: {e}")
                results.append(
                    FixResult(
                        success=False,
                        confidence=0.0,
                        remaining_issues=[f"{agent.name} failed: {e}"],
                    ),
                )

        if not results:
            return FixResult(success=False, confidence=0.0)

        combined_result = results[0]
        for result in results[1:]:
            combined_result = combined_result.merge_with(result)

        return combined_result

    def _group_issues_by_type(
        self, issues: list[Issue],
    ) -> dict[IssueType, list[Issue]]:
        grouped: defaultdict[IssueType, list[Issue]] = defaultdict(list)
        for issue in issues:
            grouped[issue.type].append(issue)
        return dict(grouped)

    def get_agent_capabilities(self) -> dict[str, dict[str, t.Any]]:
        if not self.agents:
            self.initialize_agents()

        capabilities = {}
        for agent in self.agents:
            capabilities[agent.name] = {
                "supported_types": [t.value for t in agent.get_supported_types()],
                "class": agent.__class__.__name__,
            }
        return capabilities

    def clear_cache(self) -> None:
        self._issue_cache.clear()
        self.logger.info("Cleared issue cache")

    async def test_agent_connectivity(self) -> dict[str, bool]:
        if not self.agents:
            self.initialize_agents()

        test_issue = Issue(
            id="test",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Test connectivity",
        )

        connectivity = {}
        for agent in self.agents:
            try:
                confidence = await agent.can_handle(test_issue)
                connectivity[agent.name] = confidence >= 0.0
            except Exception as e:
                self.logger.exception(f"Connectivity test failed for {agent.name}: {e}")
                connectivity[agent.name] = False

        return connectivity

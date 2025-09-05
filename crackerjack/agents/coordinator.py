import asyncio
import logging
import typing as t
from collections import defaultdict

from crackerjack.services.debug import get_ai_agent_debugger

from .base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
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
        self.proactive_mode = True

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

    # Removed unused method: handle_single_issue

    async def _handle_issues_by_type(
        self,
        issue_type: IssueType,
        issues: list[Issue],
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

    async def _find_best_specialist(
        self,
        specialists: list[SubAgent],
        issue: Issue,
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
        self,
        agent: SubAgent,
        issue: Issue,
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

    def _group_issues_by_type(
        self,
        issues: list[Issue],
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

    async def handle_issues_proactively(self, issues: list[Issue]) -> FixResult:
        if not self.proactive_mode:
            return await self.handle_issues(issues)

        if not self.agents:
            self.initialize_agents()

        if not issues:
            return FixResult(success=True, confidence=1.0)

        self.logger.info(f"Handling {len(issues)} issues with proactive planning")

        architectural_plan = await self._create_architectural_plan(issues)

        overall_result = await self._apply_fixes_with_plan(issues, architectural_plan)

        validation_result = await self._validate_against_plan(
            overall_result, architectural_plan
        )

        return validation_result

    async def _create_architectural_plan(self, issues: list[Issue]) -> dict[str, t.Any]:
        architect = self._get_architect_agent()

        if not architect:
            self.logger.warning("No ArchitectAgent available for planning")
            return {"strategy": "reactive_fallback", "patterns": []}

        complex_issues = [
            issue
            for issue in issues
            if issue.type
            in {IssueType.COMPLEXITY, IssueType.DRY_VIOLATION, IssueType.PERFORMANCE}
        ]

        if not complex_issues:
            return {"strategy": "simple_fixes", "patterns": ["standard_patterns"]}

        primary_issue = complex_issues[0]

        try:
            plan = await architect.plan_before_action(primary_issue)

            plan["all_issues"] = [issue.id for issue in issues]
            plan["issue_types"] = list({issue.type.value for issue in issues})

            self.logger.info(
                f"Created architectural plan: {plan.get('strategy', 'unknown')}"
            )
            return plan

        except Exception as e:
            self.logger.exception(f"Failed to create architectural plan: {e}")
            return {"strategy": "reactive_fallback", "patterns": [], "error": str(e)}

    async def _apply_fixes_with_plan(
        self, issues: list[Issue], plan: dict[str, t.Any]
    ) -> FixResult:
        strategy = plan.get("strategy", "reactive_fallback")

        if strategy == "reactive_fallback":
            return await self.handle_issues(issues)

        self.logger.info(f"Applying fixes with {strategy} strategy")

        prioritized_issues = self._prioritize_issues_by_plan(issues, plan)

        overall_result = FixResult(success=True, confidence=1.0)

        for issue_group in prioritized_issues:
            group_result = await self._handle_issue_group_with_plan(issue_group, plan)
            overall_result = overall_result.merge_with(group_result)

            if not group_result.success and self._is_critical_group(issue_group, plan):
                overall_result.success = False
                overall_result.remaining_issues.append(
                    f"Critical issue group failed: {[i.id for i in issue_group]}"
                )

        return overall_result

    async def _validate_against_plan(
        self, result: FixResult, plan: dict[str, t.Any]
    ) -> FixResult:
        validation_steps = plan.get("validation", [])

        if not validation_steps:
            return result

        self.logger.info(f"Validating against plan: {validation_steps}")

        result.recommendations.extend(
            [
                f"Validate with: {', '.join(validation_steps)}",
                f"Applied strategy: {plan.get('strategy', 'unknown')}",
                f"Used patterns: {', '.join(plan.get('patterns', []))}",
            ]
        )

        return result

    def _get_architect_agent(self) -> SubAgent | None:
        for agent in self.agents:
            if agent.__class__.__name__ == "ArchitectAgent":
                return agent
        return None

    def _prioritize_issues_by_plan(
        self, issues: list[Issue], plan: dict[str, t.Any]
    ) -> list[list[Issue]]:
        strategy = plan.get("strategy", "reactive_fallback")

        if strategy == "external_specialist_guided":
            complex_issues = [
                issue
                for issue in issues
                if issue.type in {IssueType.COMPLEXITY, IssueType.DRY_VIOLATION}
            ]
            other_issues = [issue for issue in issues if issue not in complex_issues]
            return [complex_issues, other_issues] if complex_issues else [other_issues]

        groups = self._group_issues_by_type(issues)
        return list(groups.values())

    async def _handle_issue_group_with_plan(
        self, issues: list[Issue], plan: dict[str, t.Any]
    ) -> FixResult:
        if not issues:
            return FixResult(success=True, confidence=1.0)

        representative_issue = issues[0]

        if self._should_use_architect_for_group(issues, plan):
            architect = self._get_architect_agent()
            if architect:
                group_result = FixResult(success=True, confidence=1.0)

                for issue in issues:
                    issue_result = await architect.analyze_and_fix(issue)
                    group_result = group_result.merge_with(issue_result)

                return group_result

        return await self._handle_issues_by_type(representative_issue.type, issues)

    def _should_use_architect_for_group(
        self, issues: list[Issue], plan: dict[str, t.Any]
    ) -> bool:
        strategy = plan.get("strategy", "")

        if strategy == "external_specialist_guided":
            return True

        architectural_types = {
            IssueType.COMPLEXITY,
            IssueType.DRY_VIOLATION,
            IssueType.PERFORMANCE,
        }

        return any(issue.type in architectural_types for issue in issues)

    def _is_critical_group(self, issues: list[Issue], plan: dict[str, t.Any]) -> bool:
        critical_types = {IssueType.COMPLEXITY, IssueType.DRY_VIOLATION}
        return any(issue.type in critical_types for issue in issues)

    def set_proactive_mode(self, enabled: bool) -> None:
        self.proactive_mode = enabled
        self.logger.info(f"Proactive mode {'enabled' if enabled else 'disabled'}")

import asyncio
import hashlib
import inspect
import typing as t
from collections import defaultdict
from itertools import starmap

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    SubAgent,
    agent_registry,
)
from crackerjack.agents.error_middleware import agent_error_boundary
from crackerjack.agents.tracker import get_agent_tracker
from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.debug import get_ai_agent_debugger
from crackerjack.services.logging import get_logger

ISSUE_TYPE_TO_AGENTS: dict[IssueType, list[str]] = {
    IssueType.FORMATTING: ["FormattingAgent"],
    IssueType.TYPE_ERROR: ["TestCreationAgent", "RefactoringAgent"],
    IssueType.SECURITY: ["SecurityAgent"],
    IssueType.TEST_FAILURE: ["TestSpecialistAgent", "TestCreationAgent"],
    IssueType.IMPORT_ERROR: ["ImportOptimizationAgent"],
    IssueType.COMPLEXITY: ["RefactoringAgent"],
    IssueType.DEAD_CODE: ["RefactoringAgent", "ImportOptimizationAgent"],
    IssueType.DEPENDENCY: ["ImportOptimizationAgent"],
    IssueType.DRY_VIOLATION: ["DRYAgent"],
    IssueType.PERFORMANCE: ["PerformanceAgent"],
    IssueType.DOCUMENTATION: ["DocumentationAgent"],
    IssueType.TEST_ORGANIZATION: ["TestSpecialistAgent"],
    IssueType.COVERAGE_IMPROVEMENT: ["TestCreationAgent"],
    IssueType.REGEX_VALIDATION: ["SecurityAgent", "RefactoringAgent"],
    IssueType.SEMANTIC_CONTEXT: ["SemanticAgent", "ArchitectAgent"],
}


class AgentCoordinator:
    def __init__(
        self, context: AgentContext, cache: CrackerjackCache | None = None
    ) -> None:
        self.context = context
        self.agents: list[SubAgent] = []
        self.logger = get_logger(__name__)
        self._issue_cache: dict[str, FixResult] = {}
        self._collaboration_threshold = 0.7
        self.tracker = get_agent_tracker()
        self.debugger = get_ai_agent_debugger()
        self.proactive_mode = True
        self.cache = cache or CrackerjackCache()

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

        # Optimization: Run ALL issue types in parallel instead of sequential
        tasks = list[t.Any](
            starmap(self._handle_issues_by_type, issues_by_type.items())
        )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        overall_result = FixResult(success=True, confidence=1.0)
        for result in results:
            if isinstance(result, FixResult):
                overall_result = overall_result.merge_with(result)
            else:
                self.logger.error(f"Issue type handling failed: {result}")
                overall_result.success = False
                overall_result.remaining_issues.append(
                    f"Type handling failed: {result}"
                )

        return overall_result

    async def _handle_issues_by_type(
        self,
        issue_type: IssueType,
        issues: list[Issue],
    ) -> FixResult:
        self.logger.info(f"Handling {len(issues)} {issue_type.value} issues")

        # Fast agent lookup using static mapping
        preferred_agent_names = ISSUE_TYPE_TO_AGENTS.get(issue_type, [])
        specialist_agents = []

        # First, try to use agents from static mapping for O(1) lookup
        specialist_agents = [
            agent
            for agent in self.agents
            if agent.__class__.__name__ in preferred_agent_names
        ]

        # Fallback: use traditional dynamic lookup if no static match
        if not specialist_agents:
            specialist_agents = [
                agent
                for agent in self.agents
                if issue_type in agent.get_supported_types()
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
        candidates = await self._score_all_specialists(specialists, issue)
        if not candidates:
            return None

        best_agent, best_score = self._find_highest_scoring_agent(candidates)
        return self._apply_built_in_preference(candidates, best_agent, best_score)

    async def _score_all_specialists(
        self, specialists: list[SubAgent], issue: Issue
    ) -> list[tuple[SubAgent, float]]:
        """Score all specialist agents for handling an issue."""
        candidates: list[tuple[SubAgent, float]] = []

        for agent in specialists:
            try:
                score = await agent.can_handle(issue)
                candidates.append((agent, score))
            except Exception as e:
                self.logger.exception(f"Error evaluating specialist {agent.name}: {e}")

        return candidates

    def _find_highest_scoring_agent(
        self, candidates: list[tuple[SubAgent, float]]
    ) -> tuple[SubAgent | None, float]:
        """Find the agent with the highest score."""
        best_agent = None
        best_score = 0.0

        for agent, score in candidates:
            if score > best_score:
                best_score = score
                best_agent = agent

        return best_agent, best_score

    def _apply_built_in_preference(
        self,
        candidates: list[tuple[SubAgent, float]],
        best_agent: SubAgent | None,
        best_score: float,
    ) -> SubAgent | None:
        """Apply preference for built-in agents when scores are close."""
        if not best_agent or best_score <= 0:
            return best_agent

        # Threshold for considering scores "close" (5% difference)
        CLOSE_SCORE_THRESHOLD = 0.05

        for agent, score in candidates:
            if self._should_prefer_built_in_agent(
                agent, best_agent, score, best_score, CLOSE_SCORE_THRESHOLD
            ):
                self._log_built_in_preference(
                    agent, score, best_agent, best_score, best_score - score
                )
                return agent

        return best_agent

    def _should_prefer_built_in_agent(
        self,
        agent: SubAgent,
        best_agent: SubAgent,
        score: float,
        best_score: float,
        threshold: float,
    ) -> bool:
        """Check if a built-in agent should be preferred over the current best."""
        return (
            agent != best_agent
            and self._is_built_in_agent(agent)
            and 0 < (best_score - score) <= threshold
        )

    def _log_built_in_preference(
        self,
        agent: SubAgent,
        score: float,
        best_agent: SubAgent,
        best_score: float,
        score_difference: float,
    ) -> None:
        """Log when preferring a built-in agent."""
        self.logger.info(
            f"Preferring built-in agent {agent.name} (score: {score:.2f}) "
            f"over {best_agent.name} (score: {best_score:.2f}) "
            f"due to {score_difference:.2f} threshold preference"
        )

    def _is_built_in_agent(self, agent: SubAgent) -> bool:
        """Check if agent is a built-in Crackerjack agent."""
        built_in_agent_names = {
            "ArchitectAgent",
            "DocumentationAgent",
            "DRYAgent",
            "FormattingAgent",
            "ImportOptimizationAgent",
            "PerformanceAgent",
            "RefactoringAgent",
            "SecurityAgent",
            "TestCreationAgent",
            "TestSpecialistAgent",
        }
        return agent.__class__.__name__ in built_in_agent_names

    async def _handle_with_single_agent(
        self,
        agent: SubAgent,
        issue: Issue,
    ) -> FixResult:
        self.logger.info(f"Handling issue with {agent.name}: {issue.message[:100]}")

        # Create cache key from issue content
        issue_hash = self._create_issue_hash(issue)

        # Check cache for previous agent decision
        cached_decision = self._coerce_cached_decision(
            self.cache.get_agent_decision(agent.name, issue_hash)
        )
        if cached_decision:
            self.logger.debug(f"Using cached decision for {agent.name}")
            self.tracker.track_agent_complete(agent.name, cached_decision)
            return cached_decision

        confidence = await agent.can_handle(issue)
        self.tracker.track_agent_processing(agent.name, issue, confidence)

        self.debugger.log_agent_activity(
            agent_name=agent.name,
            activity="processing_started",
            issue_id=issue.id,
            confidence=confidence,
            metadata={"issue_type": issue.type.value, "severity": issue.severity.value},
        )

        result = await self._execute_agent(agent, issue)
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

    def _group_issues_by_type(
        self,
        issues: list[Issue],
    ) -> dict[IssueType, list[Issue]]:
        grouped: defaultdict[IssueType, list[Issue]] = defaultdict(list)
        for issue in issues:
            grouped[issue.type].append(issue)
        return dict(grouped)

    def _create_issue_hash(self, issue: Issue) -> str:
        """Create a hash from issue content for caching decisions."""
        content = (
            f"{issue.type.value}:{issue.message}:{issue.file_path}:{issue.line_number}"
        )
        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()

    def _get_cache_key(self, agent_name: str, issue: Issue) -> str:
        """Get cache key for agent-issue combination."""
        issue_hash = self._create_issue_hash(issue)
        return f"{agent_name}:{issue_hash}"

    @agent_error_boundary
    async def _execute_agent(self, agent: SubAgent, issue: Issue) -> FixResult:
        """Execute agent analysis with centralized error handling."""
        return await self._cached_analyze_and_fix(agent, issue)

    async def _cached_analyze_and_fix(self, agent: SubAgent, issue: Issue) -> FixResult:
        """Analyze and fix issue with intelligent caching."""
        cache_key = self._get_cache_key(agent.name, issue)

        # Check in-memory cache first (fastest)
        if cache_key in self._issue_cache:
            self.logger.debug(f"Using in-memory cache for {agent.name}")
            return self._issue_cache[cache_key]

        # Check persistent cache
        cached_result = self._coerce_cached_decision(
            self.cache.get_agent_decision(agent.name, self._create_issue_hash(issue))
        )
        if cached_result:
            self.logger.debug(f"Using persistent cache for {agent.name}")
            # Store in memory cache for even faster future access
            self._issue_cache[cache_key] = cached_result
            return cached_result

        # No cache hit - perform actual analysis
        result = await agent.analyze_and_fix(issue)

        # Cache successful results with high confidence
        if result.success and result.confidence > 0.7:
            self._issue_cache[cache_key] = result
            self.cache.set_agent_decision(
                agent.name, self._create_issue_hash(issue), result
            )

        return result

    @staticmethod
    def _coerce_cached_decision(value: t.Any) -> FixResult | None:
        if isinstance(value, FixResult):
            return value
        if isinstance(value, dict):
            try:
                return FixResult(**value)
            except (TypeError, ValueError):
                return None
        return None

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
            return self._create_fallback_plan(
                "No ArchitectAgent available for planning"
            )

        complex_issues = self._filter_complex_issues(issues)
        if not complex_issues:
            return {"strategy": "simple_fixes", "patterns": ["standard_patterns"]}

        return await self._generate_architectural_plan(
            architect, complex_issues, issues
        )

    def _create_fallback_plan(self, reason: str) -> dict[str, t.Any]:
        """Create a fallback plan when architectural planning fails."""
        self.logger.warning(reason)
        return {"strategy": "reactive_fallback", "patterns": []}

    def _filter_complex_issues(self, issues: list[Issue]) -> list[Issue]:
        """Filter issues that require architectural planning."""
        complex_types = {
            IssueType.COMPLEXITY,
            IssueType.DRY_VIOLATION,
            IssueType.PERFORMANCE,
        }
        return [issue for issue in issues if issue.type in complex_types]

    async def _generate_architectural_plan(
        self, architect: t.Any, complex_issues: list[Issue], all_issues: list[Issue]
    ) -> dict[str, t.Any]:
        """Generate architectural plan using the architect agent."""
        primary_issue = complex_issues[0]

        try:
            plan = await architect.plan_before_action(primary_issue)
            # Ensure plan is properly typed as dict[str, Any]
            if not isinstance(plan, dict):
                plan = {"strategy": "default", "confidence": 0.5}
            enriched_plan = self._enrich_architectural_plan(plan, all_issues)

            self.logger.info(
                f"Created architectural plan: {enriched_plan.get('strategy', 'unknown')}"
            )
            return enriched_plan

        except Exception as e:
            self.logger.exception(f"Failed to create architectural plan: {e}")
            return {"strategy": "reactive_fallback", "patterns": [], "error": str(e)}

    def _enrich_architectural_plan(
        self, plan: dict[str, t.Any], issues: list[Issue]
    ) -> dict[str, t.Any]:
        """Enrich the architectural plan with issue metadata."""
        plan["all_issues"] = [issue.id for issue in issues]
        plan["issue_types"] = list[t.Any]({issue.type.value for issue in issues})
        return plan

    async def _apply_fixes_with_plan(
        self, issues: list[Issue], plan: dict[str, t.Any]
    ) -> FixResult:
        strategy = plan.get("strategy", "reactive_fallback")

        if strategy == "reactive_fallback":
            return await self.handle_issues(issues)

        self.logger.info(f"Applying fixes with {strategy} strategy")
        prioritized_issues = self._prioritize_issues_by_plan(issues, plan)

        return await self._process_prioritized_groups(prioritized_issues, plan)

    async def _process_prioritized_groups(
        self, prioritized_issues: list[list[Issue]], plan: dict[str, t.Any]
    ) -> FixResult:
        """Process prioritized issue groups according to the plan."""
        overall_result = FixResult(success=True, confidence=1.0)

        for issue_group in prioritized_issues:
            group_result = await self._handle_issue_group_with_plan(issue_group, plan)
            overall_result = overall_result.merge_with(group_result)

            if self._should_fail_on_group_failure(group_result, issue_group, plan):
                overall_result = self._mark_critical_group_failure(
                    overall_result, issue_group
                )

        return overall_result

    def _should_fail_on_group_failure(
        self, group_result: FixResult, issue_group: list[Issue], plan: dict[str, t.Any]
    ) -> bool:
        """Determine if overall process should fail when a group fails."""
        return not group_result.success and self._is_critical_group(issue_group, plan)

    def _mark_critical_group_failure(
        self, overall_result: FixResult, issue_group: list[Issue]
    ) -> FixResult:
        """Mark overall result as failed due to critical group failure."""
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
        return list[t.Any](groups.values())

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
                    maybe_result = architect.analyze_and_fix(issue)
                    if inspect.isawaitable(maybe_result):
                        issue_result = await maybe_result
                    elif isinstance(maybe_result, FixResult):
                        issue_result = maybe_result
                    else:
                        issue_result = FixResult(success=True, confidence=0.0)
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

import asyncio
import hashlib
import inspect
import time
import typing as t
from collections import defaultdict
from datetime import UTC, datetime
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
from crackerjack.agents.performance_tracker import AgentPerformanceTracker
from crackerjack.models.protocols import AgentTrackerProtocol, DebuggerProtocol
from crackerjack.services.cache import CrackerjackCache
from crackerjack.services.logging import get_logger

if t.TYPE_CHECKING:
    from crackerjack.models.session_metrics import SessionMetrics
    from crackerjack.services.workflow_optimization import (
        WorkflowInsights,
        WorkflowOptimizationEngine,
    )

ISSUE_TYPE_TO_AGENTS: dict[IssueType, list[str]] = {
    IssueType.FORMATTING: ["FormattingAgent", "ArchitectAgent"],
    IssueType.TYPE_ERROR: [
        "TypeErrorSpecialistAgent",
        "RefactoringAgent",
        "ArchitectAgent",
    ],
    IssueType.SECURITY: ["SecurityAgent", "ArchitectAgent"],
    IssueType.TEST_FAILURE: [
        "TestSpecialistAgent",
        "TestCreationAgent",
        "ArchitectAgent",
    ],
    IssueType.IMPORT_ERROR: [
        "ImportOptimizationAgent",
        "FormattingAgent",
        "TestSpecialistAgent",
        "ArchitectAgent",
    ],
    IssueType.COMPLEXITY: ["RefactoringAgent", "PatternAgent", "ArchitectAgent"],
    IssueType.DEAD_CODE: [
        "DeadCodeRemovalAgent",
        "RefactoringAgent",
        "ArchitectAgent",
    ],
    IssueType.DEPENDENCY: [
        "DependencyAgent",
        "TestCreationAgent",
        "ArchitectAgent",
    ],
    IssueType.DRY_VIOLATION: ["DRYAgent", "ArchitectAgent"],
    IssueType.PERFORMANCE: ["PerformanceAgent", "ArchitectAgent"],
    IssueType.DOCUMENTATION: ["DocumentationAgent", "ArchitectAgent"],
    IssueType.TEST_ORGANIZATION: ["TestCreationAgent", "ArchitectAgent"],
    IssueType.COVERAGE_IMPROVEMENT: ["TestCreationAgent"],
    IssueType.REGEX_VALIDATION: ["SecurityAgent"],
    IssueType.SEMANTIC_CONTEXT: ["SemanticAgent"],
}


class AgentCoordinator:
    def __init__(
        self,
        context: AgentContext,
        tracker: AgentTrackerProtocol,
        debugger: DebuggerProtocol,
        cache: CrackerjackCache | None = None,
        job_id: str | None = None,
        workflow_engine: "WorkflowOptimizationEngine | None" = None,
    ) -> None:
        self.context = context
        self.agents: list[SubAgent] = []
        self.logger = get_logger(__name__)
        self._issue_cache: dict[str, FixResult] = {}
        self._collaboration_threshold = 0.7

        self.tracker = tracker
        self.debugger = debugger
        self.proactive_mode = True
        self.cache = cache or CrackerjackCache()

        self.job_id = job_id or self._generate_job_id()

        self.performance_tracker = AgentPerformanceTracker()
        self.logger.debug("Performance tracker initialized")

        self.workflow_engine = workflow_engine
        if workflow_engine is not None:
            self.logger.info("✅ Workflow optimization engine initialized")

    def _generate_job_id(self) -> str:
        import uuid

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"job_{timestamp}_{unique_id}"

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

    async def _get_workflow_recommendations(
        self,
        session_metrics: "SessionMetrics | None" = None,
    ) -> list[str]:
        """Get workflow-based recommendations for agent selection.

        Args:
            session_metrics: Optional session metrics with git data.

        Returns:
            List of recommendation titles for logging.
        """
        if self.workflow_engine is None:
            return []

        if session_metrics is None:
            self.logger.debug("No session metrics provided, skipping workflow analysis")
            return []

        has_git_data = any(
            [
                session_metrics.git_commit_velocity is not None,
                session_metrics.git_merge_success_rate is not None,
                session_metrics.git_workflow_efficiency_score is not None,
                session_metrics.conventional_commit_compliance is not None,
            ]
        )

        if not has_git_data:
            self.logger.debug("No git metrics available, skipping workflow analysis")
            return []

        try:
            insights = self.workflow_engine.generate_insights()

            self._log_workflow_insights(insights)

            return [rec.title for rec in insights.recommendations]
        except RuntimeError as e:
            self.logger.warning(f"Workflow analysis failed: {e}")
            return []

    def _log_workflow_insights(
        self,
        insights: "WorkflowInsights | None" = None,
    ) -> None:
        """Log workflow insights with git metrics and recommendations.

        Args:
            insights: Optional workflow insights data.
        """
        if insights is None or self.workflow_engine is None:
            return

        session_metrics = self.workflow_engine.session_metrics

        velocity = session_metrics.git_commit_velocity
        merge_rate = session_metrics.git_merge_success_rate
        efficiency = session_metrics.git_workflow_efficiency_score

        metrics_str = ""
        if velocity is not None:
            metrics_str += f"velocity={velocity:.1f}/h "
        if merge_rate is not None:
            metrics_str += f"merge_rate={merge_rate:.1%} "
        if efficiency is not None:
            metrics_str += f"efficiency={efficiency:.0f}/100 "

        rec_by_priority: dict[str, list[str]] = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
        }

        for rec in insights.recommendations:
            rec_by_priority[rec.priority].append(rec.title)

        rec_str = ""
        for priority in ["critical", "high", "medium", "low"]:
            if rec_by_priority[priority]:
                rec_str += f"{priority.upper()}={len(rec_by_priority[priority])} "

        self.logger.info(
            f"📊 Workflow Insights: [{metrics_str.strip()}] → [{rec_str.strip()}]"
        )

        for priority in ["critical", "high", "medium", "low"]:
            if rec_by_priority[priority]:
                for title in rec_by_priority[priority]:
                    self.logger.info(f"   {priority.upper()}: {title}")

    async def handle_issues(self, issues: list[Issue], iteration: int = 0) -> FixResult:
        if not self.agents:
            self.initialize_agents()

        if not issues:
            return FixResult(success=True, confidence=1.0)

        self.logger.info(
            f"Handling {len(issues)} issues (iteration {iteration}, "
            f"strategy: {self._get_strategy_name(iteration)})"
        )

        await self._analyze_workflow_for_agent_selection()

        issues_by_type = self._group_issues_by_type(issues)

        tasks = list[t.Any](
            starmap(
                lambda it, iss: self._handle_issues_by_type(it, iss, iteration),
                issues_by_type.items(),
            ),
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
                    f"Type handling failed: {result}",
                )

        return overall_result

    async def _analyze_workflow_for_agent_selection(self) -> None:
        """Analyze workflow metrics to influence agent selection.

        This method retrieves workflow insights and uses them to boost
        relevant agents during selection. Falls back gracefully if no
        git metrics available.
        """
        try:
            session_metrics = self._get_session_metrics_from_context()
            await self._get_workflow_recommendations(session_metrics)
        except (AttributeError, RuntimeError) as e:
            self.logger.debug(f"Workflow analysis skipped: {e}")

    def _get_session_metrics_from_context(
        self,
    ) -> "SessionMetrics | None":
        """Extract session metrics from agent context if available.

        Returns:
            SessionMetrics if available in context, None otherwise.
        """
        session_metrics = getattr(self.context, "session_metrics", None)
        return session_metrics

    async def _handle_issues_by_type(
        self,
        issue_type: IssueType,
        issues: list[Issue],
        iteration: int = 0,
    ) -> FixResult:
        self.logger.info(
            f"Handling {len(issues)} {issue_type.value} issues (iteration {iteration})"
        )

        specialist_agents = await self._find_specialist_agents(issue_type)
        if not specialist_agents:
            return self._create_no_agents_result(issue_type)

        tasks = await self._create_issue_tasks(specialist_agents, issues, iteration)
        if not tasks:
            return FixResult(success=False, confidence=0.0)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return self._merge_fix_results(results)

    async def _find_specialist_agents(self, issue_type: IssueType) -> list[SubAgent]:
        preferred_agent_names = ISSUE_TYPE_TO_AGENTS.get(issue_type, [])

        self.logger.info(f"🔍 Finding agents for {issue_type.value}")
        self.logger.info(f"   Preferred agents: {preferred_agent_names}")
        self.logger.info(
            f"   Available agents ({len(self.agents)}): {[a.__class__.__name__ for a in self.agents]}"
        )

        specialist_agents = [
            agent
            for agent in self.agents
            if agent.__class__.__name__ in preferred_agent_names
        ]

        if specialist_agents:
            self.logger.info(
                f"   ✓ Found {len(specialist_agents)} specialists by name: {[a.__class__.__name__ for a in specialist_agents]}"
            )
        else:
            self.logger.info(
                "   ⚠️  No specialists by name, checking supported types..."
            )
            specialist_agents = [
                agent
                for agent in self.agents
                if issue_type in agent.get_supported_types()
            ]
            if specialist_agents:
                self.logger.info(
                    f"   ✓ Found {len(specialist_agents)} specialists by supported type: {[a.__class__.__name__ for a in specialist_agents]}"
                )
            else:
                self.logger.warning(f"   ❌ No agents found for {issue_type.value}")

        return specialist_agents

    def _create_no_agents_result(self, issue_type: IssueType) -> FixResult:
        self.logger.warning(f"No specialist agents for {issue_type.value}")
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[f"No agents for {issue_type.value} issues"],
        )

    async def _create_issue_tasks(
        self,
        specialist_agents: list[SubAgent],
        issues: list[Issue],
        iteration: int = 0,
    ) -> list[t.Coroutine[t.Any, t.Any, FixResult]]:
        tasks: list[t.Coroutine[t.Any, t.Any, FixResult]] = []
        skipped_count = 0

        use_multi_agent = iteration >= 5

        for issue in issues:
            if use_multi_agent:
                task = self._handle_with_multi_agent_fallback(
                    specialist_agents, issue, iteration
                )
                tasks.append(task)
            else:
                best_specialist = await self._find_best_specialist(
                    specialist_agents, issue, iteration
                )
                if best_specialist:
                    task = self._handle_with_single_agent(best_specialist, issue)
                    tasks.append(task)
                skipped_count += 1
                self.logger.warning(
                    f"   ⚠️  No specialist found for issue: {issue.file_path}:{issue.line_number} - {issue.message[:60]}..."
                )

        if skipped_count > 0:
            self.logger.warning(
                f"   ⚠️  Skipped {skipped_count}/{len(issues)} issues (no suitable agent)"
            )
        return tasks

    def _merge_fix_results(self, results: list[t.Any]) -> FixResult:
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
        iteration: int = 0,
    ) -> SubAgent | None:

        strategy_boost: dict[str, float] = {}
        if self.context.fix_strategy_memory is not None:
            try:
                from crackerjack.memory.issue_embedder import get_issue_embedder

                embedder = get_issue_embedder()
                issue_embedding = embedder.embed_issue(issue)

                recommendation = (
                    self.context.fix_strategy_memory.get_strategy_recommendation(
                        issue=issue,
                        issue_embedding=issue_embedding,
                        k=10,
                    )
                )

                if recommendation:
                    agent_strategy, confidence = recommendation

                    recommended_agent = agent_strategy.split(":")[0]

                    self.logger.info(
                        f"🧠 FIX STRATEGY MEMORY recommends: {recommended_agent} "
                        f"(confidence: {confidence:.3f})"
                    )

                    strategy_boost[recommended_agent] = confidence + 0.2
            except ImportError:
                self.logger.debug(
                    "Fix strategy memory not available (sentence-transformers not installed)"
                )
                self.logger.warning(
                    "Failed to get strategy recommendation: ML library unavailable"
                )

        workflow_boost = await self._get_workflow_agent_boost(issue)
        if workflow_boost:
            strategy_boost.update(workflow_boost)

        candidates = await self._score_all_specialists(specialists, issue)

        if strategy_boost:
            boosted_candidates = []
            for agent, score in candidates:
                agent_name = agent.__class__.__name__
                if agent_name in strategy_boost:
                    boosted_score = min(score + strategy_boost[agent_name], 1.0)
                    boosted_candidates.append((agent, boosted_score))
                    self.logger.info(
                        f"   📈 BOOSTED {agent_name}: {score:.2f} → {boosted_score:.2f} "
                        f"(+{strategy_boost[agent_name]:.2f})"
                    )
                else:
                    boosted_candidates.append((agent, score))
            candidates = boosted_candidates

        if not candidates:
            self.logger.warning(f"No candidates found for issue: {issue.message[:80]}")
            return None

        best_agent, best_score = self._find_highest_scoring_agent(candidates)
        if best_agent:
            self.logger.info(
                f"Best agent for issue {issue.type.value}: {best_agent.name} "
                f"(score: {best_score:.2f}, iteration: {iteration})"
            )
        else:
            self.logger.warning(
                f"No best agent found for issue {issue.type.value} "
                f"(best_score: {best_score:.2f}, iteration: {iteration})"
            )
        return self._apply_built_in_preference(
            candidates, best_agent, best_score, iteration
        )

    async def _get_workflow_agent_boost(
        self,
        issue: Issue,
    ) -> dict[str, float]:
        """Get agent score boosts based on workflow recommendations.

        Args:
            issue: The issue being handled.

        Returns:
            Dictionary mapping agent names to boost amounts.
        """
        if self.workflow_engine is None:
            return {}

        try:
            session_metrics = self._get_session_metrics_from_context()
            if session_metrics is None:
                return {}

            insights = self.workflow_engine.generate_insights()

            boost_map: dict[str, float] = {}

            for rec in insights.recommendations:
                if rec.priority == "critical":
                    if "workflow" in rec.title.lower() or "merge" in rec.title.lower():
                        boost_map["ArchitectAgent"] = 0.15
                        boost_map["RefactoringAgent"] = 0.1
                elif rec.priority == "high":
                    if "conventional" in rec.title.lower():
                        boost_map["DocumentationAgent"] = 0.1

            return boost_map
        except (AttributeError, RuntimeError) as e:
            self.logger.debug(f"Workflow boost calculation failed: {e}")
            return {}

    async def _score_all_specialists(
        self,
        specialists: list[SubAgent],
        issue: Issue,
    ) -> list[tuple[SubAgent, float]]:
        candidates: list[tuple[SubAgent, float]] = []

        for agent in specialists:
            try:
                score = await agent.can_handle(issue)
                self.logger.info(
                    f"   📊 Agent {agent.name} scored {score:.2f} for: {issue.message[:60]}"
                )
                candidates.append((agent, score))
            except Exception as e:
                self.logger.exception(f"Error evaluating specialist {agent.name}: {e}")

        return candidates

    def _find_highest_scoring_agent(
        self,
        candidates: list[tuple[SubAgent, float]],
    ) -> tuple[SubAgent | None, float]:
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
        iteration: int = 0,
    ) -> SubAgent | None:

        min_threshold = max(0.5 - (iteration * 0.1), 0.1)

        strategy = self._get_strategy_name(iteration)
        if not best_agent or best_score < min_threshold:
            if best_agent and best_score < min_threshold:
                self.logger.info(
                    f"   ⚠️  Best agent score ({best_score:.2f}) < threshold "
                    f"({min_threshold:.2f}) for {strategy} strategy"
                )
                self.logger.info(
                    f"   All candidate scores: {[f'{a.name}:{s:.2f}' for a, s in candidates]}"
                )

                if iteration >= 5:
                    self.logger.info(
                        f"   🎲 AGGRESSIVE MODE: Attempting fix anyway (iteration {iteration})"
                    )
                    return best_agent
            return best_agent

        CLOSE_SCORE_THRESHOLD = 0.05

        for agent, score in candidates:
            if self._should_prefer_built_in_agent(
                agent,
                best_agent,
                score,
                best_score,
                CLOSE_SCORE_THRESHOLD,
            ):
                self._log_built_in_preference(
                    agent,
                    score,
                    best_agent,
                    best_score,
                    best_score - score,
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
        self.logger.info(
            f"Preferring built-in agent {agent.name} (score: {score:.2f}) "
            f"over {best_agent.name} (score: {best_score:.2f}) "
            f"due to {score_difference:.2f} threshold preference",
        )

    def _is_built_in_agent(self, agent: SubAgent) -> bool:
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

        issue_hash = self._create_issue_hash(issue)

        cached_decision = self._coerce_cached_decision(
            self.cache.get_agent_decision(agent.name, issue_hash),
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

        start_time = time.time()

        result = await self._execute_agent(agent, issue)

        execution_time_seconds = time.time() - start_time

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

        self._record_performance_metrics(
            agent_name=agent.name,
            issue_type=issue.type.value,
            result=result,
            confidence=confidence,
            execution_time_seconds=execution_time_seconds,
        )

        await self._track_agent_execution(
            job_id=self.job_id,
            agent_name=agent.name,
            issue_type=issue.type.value,
            result=result,
            execution_time_ms=execution_time_seconds * 1000,
        )

        return result

    async def _handle_with_multi_agent_fallback(
        self,
        specialists: list[SubAgent],
        issue: Issue,
        iteration: int = 0,
    ) -> FixResult:

        if iteration < 5:
            best_agent = await self._find_best_specialist(specialists, issue, iteration)
            if best_agent:
                return await self._handle_with_single_agent(best_agent, issue)
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"No suitable agent for issue: {issue.message[:80]}"],
            )

        scored_agents = []
        for agent in specialists:
            try:
                score = await agent.can_handle(issue)
                if score > 0:
                    scored_agents.append((agent, score))
            except Exception:
                pass

        scored_agents.sort(key=lambda x: x[1], reverse=True)

        max_attempts = min(3, len(scored_agents))
        self.logger.info(
            f"🎯 MULTI-AGENT FALLBACK: Trying {max_attempts} agents for issue "
            f"(iteration {iteration}, mode: aggressive)"
        )

        for i, (agent, score) in enumerate(scored_agents[:max_attempts]):
            self.logger.info(
                f"  Attempt {i + 1}/{max_attempts}: {agent.name} (score: {score:.2f})"
            )

            result = await self._handle_with_single_agent(agent, issue)

            if result.success:
                self.logger.info(
                    f"  ✅ Agent {i + 1}/{max_attempts} ({agent.name}) succeeded!"
                )
                return result
            else:
                self.logger.info(
                    f"  ⚠️  Agent {i + 1}/{max_attempts} ({agent.name}) failed, trying next..."
                )

        self.logger.warning("  ❌ All agents failed, merging partial results...")
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[
                f"Multi-agent fallback failed after {max_attempts} attempts: {issue.message[:80]}"
            ],
        )

    def _record_performance_metrics(
        self,
        agent_name: str,
        issue_type: str,
        result: FixResult,
        confidence: float,
        execution_time_seconds: float,
    ) -> None:
        try:
            model_name = self.context.config.get("model_name", "unknown")

            self.performance_tracker.record_attempt(
                agent_name=agent_name,
                model_name=model_name,
                issue_type=issue_type,
                success=result.success,
                confidence=confidence,
                time_seconds=execution_time_seconds,
            )

            self.logger.debug(
                f"Recorded performance metrics for {agent_name} "
                f"(success={result.success}, time={execution_time_seconds:.2f}s)"
            )
        except Exception as e:
            self.logger.debug(f"Failed to record performance metrics: {e}")

    def _group_issues_by_type(
        self,
        issues: list[Issue],
    ) -> dict[IssueType, list[Issue]]:
        grouped: defaultdict[IssueType, list[Issue]] = defaultdict(list)
        for issue in issues:
            grouped[issue.type].append(issue)
        return dict(grouped)

    def _create_issue_hash(self, issue: Issue) -> str:
        content = (
            f"{issue.type.value}:{issue.message}:{issue.file_path}:{issue.line_number}"
        )
        return hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()

    def _get_cache_key(self, agent_name: str, issue: Issue) -> str:
        issue_hash = self._create_issue_hash(issue)
        return f"{agent_name}:{issue_hash}"

    @agent_error_boundary
    async def _execute_agent(self, agent: SubAgent, issue: Issue) -> FixResult:
        return await self._cached_analyze_and_fix(agent, issue)

    async def _cached_analyze_and_fix(self, agent: SubAgent, issue: Issue) -> FixResult:
        cache_key = self._get_cache_key(agent.name, issue)

        self.logger.info(f"🔧 AGENT CALL: {agent.name} → issue {issue.id[:8]}")
        self.logger.info(f"   Type: {issue.type.value}")
        self.logger.info(f"   File: {issue.file_path}:{issue.line_number}")
        self.logger.info(f"   Message: {issue.message[:80]}...")

        if cache_key in self._issue_cache:
            self.logger.debug(f"Using in-memory cache for {agent.name}")
            cached = self._issue_cache[cache_key]
            self.logger.warning(
                f"   ⚠️  RETURNING CACHED RESULT: success={cached.success}"
            )
            return cached

        cached_result = self._coerce_cached_decision(
            self.cache.get_agent_decision(agent.name, self._create_issue_hash(issue)),
        )
        if cached_result:
            self.logger.debug(f"Using persistent cache for {agent.name}")
            self.logger.warning(
                f"   ⚠️  RETURNING PERSISTENT CACHED RESULT: success={cached_result.success}"
            )

            self._issue_cache[cache_key] = cached_result
            return cached_result

        self.logger.info("   ▶️  Calling agent.analyze_and_fix()...")
        result = await agent.analyze_and_fix(issue)

        self.logger.info(f"   ✓ AGENT RESULT: {agent.name}")
        self.logger.info(f"   Success: {result.success}")
        self.logger.info(f"   Confidence: {result.confidence}")
        self.logger.info(f"   Fixes applied: {len(result.fixes_applied)}")
        if result.fixes_applied:
            for fix in result.fixes_applied[:3]:
                self.logger.info(f"     - {fix[:80]}")
        if result.remaining_issues:
            self.logger.warning(f"   Remaining issues: {len(result.remaining_issues)}")
            for remaining in result.remaining_issues[:3]:
                self.logger.warning(f"     - {remaining[:80]}")

        if result.success and result.confidence > 0.7:
            self._issue_cache[cache_key] = result
            self.cache.set_agent_decision(
                agent.name,
                self._create_issue_hash(issue),
                result,
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

    async def _track_agent_execution(
        self,
        job_id: str,
        agent_name: str,
        issue_type: str,
        result: FixResult,
        execution_time_ms: float | None = None,
    ) -> None:
        try:
            from crackerjack.services.metrics import get_metrics

            metrics = get_metrics()

            metrics.execute(
                """
                INSERT INTO agent_executions
                (job_id, agent_name, issue_type, success, confidence,
                 fixes_applied, files_modified, remaining_issues, execution_time_ms, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    agent_name,
                    issue_type,
                    result.success,
                    result.confidence,
                    len(result.fixes_applied),
                    len(result.files_modified),
                    len(result.remaining_issues),
                    execution_time_ms,
                    datetime.now(UTC),
                ),
            )
        except Exception as e:
            self.logger.debug(f"Failed to track agent execution: {e}")

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

    def _get_strategy_name(self, iteration: int) -> str:
        if iteration < 2:
            return "conservative"
        elif iteration < 5:
            return "moderate"
        elif iteration < 10:
            return "aggressive"
        else:
            return "desperate"

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

        return await self._validate_against_plan(
            overall_result,
            architectural_plan,
        )

    async def _create_architectural_plan(self, issues: list[Issue]) -> dict[str, t.Any]:
        architect = self._get_architect_agent()

        if not architect:
            return self._create_fallback_plan(
                "No ArchitectAgent available for planning",
            )

        complex_issues = self._filter_complex_issues(issues)
        if not complex_issues:
            return {"strategy": "simple_fixes", "patterns": ["standard_patterns"]}

        return await self._generate_architectural_plan(
            architect,
            complex_issues,
            issues,
        )

    def _create_fallback_plan(self, reason: str) -> dict[str, t.Any]:
        self.logger.warning(reason)
        return {"strategy": "reactive_fallback", "patterns": []}

    def _filter_complex_issues(self, issues: list[Issue]) -> list[Issue]:
        complex_types = {
            IssueType.COMPLEXITY,
            IssueType.DRY_VIOLATION,
            IssueType.PERFORMANCE,
        }
        return [issue for issue in issues if issue.type in complex_types]

    async def _generate_architectural_plan(
        self,
        architect: t.Any,
        complex_issues: list[Issue],
        all_issues: list[Issue],
    ) -> dict[str, t.Any]:
        primary_issue = complex_issues[0]

        try:
            plan = await architect.plan_before_action(primary_issue)

            if not isinstance(plan, dict):
                plan = {"strategy": "default", "confidence": 0.5}
            enriched_plan = self._enrich_architectural_plan(plan, all_issues)

            self.logger.info(
                f"Created architectural plan: {enriched_plan.get('strategy', 'unknown')}",
            )
            return enriched_plan

        except Exception as e:
            self.logger.exception(f"Failed to create architectural plan: {e}")
            return {"strategy": "reactive_fallback", "patterns": [], "error": str(e)}

    def _enrich_architectural_plan(
        self,
        plan: dict[str, t.Any],
        issues: list[Issue],
    ) -> dict[str, t.Any]:
        plan["all_issues"] = [issue.id for issue in issues]
        plan["issue_types"] = list[t.Any]({issue.type.value for issue in issues})
        return plan

    async def _apply_fixes_with_plan(
        self,
        issues: list[Issue],
        plan: dict[str, t.Any],
    ) -> FixResult:
        strategy = plan.get("strategy", "reactive_fallback")

        if strategy == "reactive_fallback":
            return await self.handle_issues(issues)

        self.logger.info(f"Applying fixes with {strategy} strategy")
        prioritized_issues = self._prioritize_issues_by_plan(issues, plan)

        return await self._process_prioritized_groups(prioritized_issues, plan)

    async def _process_prioritized_groups(
        self,
        prioritized_issues: list[list[Issue]],
        plan: dict[str, t.Any],
    ) -> FixResult:
        overall_result = FixResult(success=True, confidence=1.0)

        for issue_group in prioritized_issues:
            group_result = await self._handle_issue_group_with_plan(issue_group, plan)
            overall_result = overall_result.merge_with(group_result)

            if self._should_fail_on_group_failure(group_result, issue_group, plan):
                overall_result = self._mark_critical_group_failure(
                    overall_result,
                    issue_group,
                )

        return overall_result

    def _should_fail_on_group_failure(
        self,
        group_result: FixResult,
        issue_group: list[Issue],
        plan: dict[str, t.Any],
    ) -> bool:
        return not group_result.success and self._is_critical_group(issue_group, plan)

    def _mark_critical_group_failure(
        self,
        overall_result: FixResult,
        issue_group: list[Issue],
    ) -> FixResult:
        overall_result.success = False
        overall_result.remaining_issues.append(
            f"Critical issue group failed: {[i.id for i in issue_group]}",
        )
        return overall_result

    async def _validate_against_plan(
        self,
        result: FixResult,
        plan: dict[str, t.Any],
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
            ],
        )

        return result

    def _get_architect_agent(self) -> SubAgent | None:
        for agent in self.agents:
            if agent.__class__.__name__ == "ArchitectAgent":
                return agent
        return None

    def _prioritize_issues_by_plan(
        self,
        issues: list[Issue],
        plan: dict[str, t.Any],
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
        self,
        issues: list[Issue],
        plan: dict[str, t.Any],
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
        self,
        issues: list[Issue],
        plan: dict[str, t.Any],
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

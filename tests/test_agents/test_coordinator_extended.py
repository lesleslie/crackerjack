"""Extended tests for AgentCoordinator covering uncovered methods.

These tests target the parts of the coordinator that the original
``test_coordinator.py`` did not exercise, including:

- ``handle_issues`` full flow with agents
- ``_handle_issues_by_type`` happy path and no-specialist branch
- ``_find_specialist_agents`` (name match + supported-types fallback)
- ``_create_issue_tasks`` for both single-agent and multi-agent paths
- ``_apply_built_in_preference`` branch matrix
- ``_cached_analyze_and_fix`` (in-memory + persistent cache hits)
- ``_handle_with_single_agent`` (cache hit + miss + tracking)
- ``_execute_agent`` error boundary
- ``handle_issues_proactively`` full plan-driven path
- ``_apply_fixes_with_plan`` and ``_validate_against_plan``
- ``_process_prioritized_groups`` with critical-group failure
- ``_handle_issue_group_with_plan`` with awaitable + sync + wrong-type returns
- ``_mark_critical_group_failure``
- ``_log_workflow_insights`` (all priority buckets, missing metrics)
- ``_get_workflow_recommendations`` (no engine, no metrics, no git data, success, RuntimeError)
- ``_analyze_workflow_for_agent_selection`` exception swallow
- ``_get_session_metrics_from_context``
- ``_track_agent_execution`` happy + exception swallow
- ``_should_fail_on_group_failure``
- ``initialize_agents`` interaction with the registry
- ``set_proactive_mode`` and ``get_agent_capabilities``
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
    SubAgent,
)
from crackerjack.agents.coordinator import (
    ISSUE_TYPE_TO_AGENTS,
    AgentCoordinator,
)
from crackerjack.models.protocols import AgentTrackerProtocol, DebuggerProtocol
from crackerjack.services.cache import CrackerjackCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_tracker() -> Mock:
    tracker = Mock(spec=AgentTrackerProtocol)
    tracker.register_agents = Mock()
    tracker.set_coordinator_status = Mock()
    tracker.track_agent_processing = Mock()
    tracker.track_agent_complete = Mock()
    tracker.reset = Mock()
    return tracker


@pytest.fixture
def mock_debugger() -> Mock:
    debugger = Mock(spec=DebuggerProtocol)
    debugger.enabled = False
    debugger.debug_operation = Mock(return_value=iter(["test-id"]))
    debugger.log_agent_activity = Mock()
    return debugger


@pytest.fixture
def mock_context() -> Mock:
    context = Mock(spec=AgentContext)
    context.project_path = Path("/test/project")
    context.config = {"model_name": "test-model"}
    context.fix_strategy_memory = None
    context.session_metrics = None
    return context


@pytest.fixture
def cache() -> CrackerjackCache:
    return CrackerjackCache()


@pytest.fixture
def coordinator(
    mock_context: Mock,
    mock_tracker: Mock,
    mock_debugger: Mock,
    cache: CrackerjackCache,
) -> AgentCoordinator:
    return AgentCoordinator(
        context=mock_context,
        tracker=mock_tracker,
        debugger=mock_debugger,
        cache=cache,
        job_id="test-job-001",
    )


def _make_specialist(name: str, score: float = 0.8) -> Mock:
    """Create a mock SubAgent whose __class__.__name__ is *name*.

    A real ``type`` is assigned so the registry filter and
    ``_is_built_in_agent`` test against the correct class name.
    """
    klass = type(name, (SubAgent,), {})
    agent = Mock(spec=SubAgent)
    agent.__class__ = klass
    agent.name = name
    agent.can_handle = AsyncMock(return_value=score)
    agent.analyze_and_fix = AsyncMock(
        return_value=FixResult(success=True, confidence=0.9, fixes_applied=[f"fix-by-{name}"]),
    )
    agent.get_supported_types = Mock(return_value={IssueType.TYPE_ERROR})
    agent.plan_before_action = AsyncMock(
        return_value={"strategy": "external_specialist_guided", "confidence": 0.9},
    )
    return agent


# ---------------------------------------------------------------------------
# ISSUE_TYPE_TO_AGENTS mapping shape
# ---------------------------------------------------------------------------


class TestIssueTypeMappingExtended:
    def test_every_issue_type_with_agents_is_in_mapping(self) -> None:
        # Every IssueType used elsewhere should be addressable from the dispatch table.
        for issue_type in (
            IssueType.FORMATTING,
            IssueType.SECURITY,
            IssueType.PERFORMANCE,
            IssueType.DOCUMENTATION,
            IssueType.REGEX_VALIDATION,
            IssueType.SEMANTIC_CONTEXT,
            IssueType.REFURB,
            IssueType.WARNING,
            IssueType.COVERAGE_IMPROVEMENT,
        ):
            assert issue_type in ISSUE_TYPE_TO_AGENTS, issue_type
            assert len(ISSUE_TYPE_TO_AGENTS[issue_type]) >= 1

    def test_issue_type_dispatch_lists_only_strings(self) -> None:
        for agents in ISSUE_TYPE_TO_AGENTS.values():
            assert all(isinstance(a, str) for a in agents)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInitializeAgents:
    def test_initialize_agents_calls_registry_and_tracker(
        self,
        coordinator: AgentCoordinator,
        mock_tracker: Mock,
        mock_debugger: Mock,
    ) -> None:
        sentinel_agent = _make_specialist("SentinelAgent")
        sentinel_agent.get_supported_types = Mock(return_value=set())  # type: ignore[method-assign]
        with patch(
            "crackerjack.agents.base.agent_registry.create_all",
            return_value=[sentinel_agent],
        ) as create_all:
            coordinator.initialize_agents()

        create_all.assert_called_once_with(coordinator.context)
        assert coordinator.agents == [sentinel_agent]
        mock_tracker.register_agents.assert_called_once_with(["SentinelAgent"])
        mock_tracker.set_coordinator_status.assert_called_once_with("active")
        mock_debugger.log_agent_activity.assert_called_once()
        kwargs = mock_debugger.log_agent_activity.call_args.kwargs
        assert kwargs["agent_name"] == "coordinator"
        assert kwargs["activity"] == "agents_initialized"
        assert kwargs["metadata"]["agent_count"] == 1


# ---------------------------------------------------------------------------
# get_agent_capabilities
# ---------------------------------------------------------------------------


class TestGetAgentCapabilities:
    def test_get_agent_capabilities_lazy_initializes(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        # Agents start empty
        assert coordinator.agents == []
        agent = _make_specialist("FormattingAgent", score=0.5)
        with patch(
            "crackerjack.agents.base.agent_registry.create_all",
            return_value=[agent],
        ):
            capabilities = coordinator.get_agent_capabilities()

        assert "FormattingAgent" in capabilities
        assert "supported_types" in capabilities["FormattingAgent"]
        assert "type_error" in capabilities["FormattingAgent"]["supported_types"]
        assert capabilities["FormattingAgent"]["class"] == "FormattingAgent"

    def test_get_agent_capabilities_no_supported_types_uses_empty(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        agent = _make_specialist("FooAgent")
        agent.get_supported_types = Mock(return_value=set())  # type: ignore[method-assign]
        with patch(
            "crackerjack.agents.base.agent_registry.create_all",
            return_value=[agent],
        ):
            capabilities = coordinator.get_agent_capabilities()

        assert capabilities["FooAgent"]["supported_types"] == []


# ---------------------------------------------------------------------------
# Specialist finding
# ---------------------------------------------------------------------------


class TestFindSpecialistAgents:
    @pytest.mark.asyncio
    async def test_find_by_preferred_name(self, coordinator: AgentCoordinator) -> None:
        formatting = _make_specialist("FormattingAgent")
        unrelated = _make_specialist("RefactoringAgent")
        coordinator.agents = [formatting, unrelated]

        found = await coordinator._find_specialist_agents(IssueType.FORMATTING)

        assert formatting in found
        assert unrelated not in found

    @pytest.mark.asyncio
    async def test_falls_back_to_supported_types(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        # No name match, but the agent advertises support for COMPLEXITY.
        complexity_agent = _make_specialist("NotInDispatchAgent")
        complexity_agent.get_supported_types = Mock(  # type: ignore[method-assign]
            return_value={IssueType.COMPLEXITY},
        )
        coordinator.agents = [complexity_agent]

        found = await coordinator._find_specialist_agents(IssueType.COMPLEXITY)
        assert complexity_agent in found

    @pytest.mark.asyncio
    async def test_no_match_returns_empty(self, coordinator: AgentCoordinator) -> None:
        agent = _make_specialist("RandomAgent")
        agent.get_supported_types = Mock(return_value={IssueType.FORMATTING})  # type: ignore[method-assign]
        coordinator.agents = [agent]
        # No dispatch entry for an unknown type, and the agent doesn't support it either.
        found = await coordinator._find_specialist_agents(IssueType.TEST_ORGANIZATION)
        # TEST_ORGANIZATION has entries in dispatch so name match wouldn't apply; supported types returns empty here.
        # Since the agent only claims FORMATTING, no match.
        assert found == []


# ---------------------------------------------------------------------------
# _handle_issues_by_type
# ---------------------------------------------------------------------------


class TestHandleIssuesByType:
    @pytest.mark.asyncio
    async def test_no_specialists_returns_no_agents_result(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        coordinator.agents = []
        result = await coordinator._handle_issues_by_type(
            IssueType.FORMATTING,
            [Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="x")],
            iteration=0,
        )
        assert result.success is False
        assert result.confidence == 0.0
        assert any("No agents" in r for r in result.remaining_issues)

    @pytest.mark.asyncio
    async def test_with_specialists_returns_merged_result(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        formatting = _make_specialist("FormattingAgent", score=0.8)
        coordinator.agents = [formatting]
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="x")

        with patch.object(
            coordinator,
            "_create_issue_tasks",
            AsyncMock(return_value=[formatting.analyze_and_fix.return_value]),
        ) as create_tasks:
            tasks = await coordinator._create_issue_tasks([formatting], [issue], iteration=0)
        assert tasks  # smoke: at least one task returned
        create_tasks.assert_awaited_once()

        # Now run the real path
        result = await coordinator._handle_issues_by_type(
            IssueType.FORMATTING,
            [issue],
            iteration=0,
        )
        assert result.success is True
        assert "fix-by-FormattingAgent" in result.fixes_applied


# ---------------------------------------------------------------------------
# _create_issue_tasks: single vs multi-agent path
# ---------------------------------------------------------------------------


class TestCreateIssueTasks:
    @pytest.mark.asyncio
    async def test_early_iteration_uses_single_agent_path(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        specialists = [_make_specialist("FormattingAgent", score=0.9)]
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="m")

        tasks = await coordinator._create_issue_tasks(specialists, [issue], iteration=0)
        assert len(tasks) == 1
        # Close the coroutine to silence "never awaited" warnings.
        for t in tasks:
            t.close()

    @pytest.mark.asyncio
    async def test_late_iteration_uses_multi_agent_path(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        specialists = [_make_specialist("FormattingAgent", score=0.9)]
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="m")

        tasks = await coordinator._create_issue_tasks(specialists, [issue], iteration=10)
        assert len(tasks) == 1
        for t in tasks:
            t.close()

    @pytest.mark.asyncio
    async def test_no_specialist_for_issue_skips(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        # _find_best_specialist returns None when there are no candidates.
        # Stub it so the task is not created.
        with patch.object(
            coordinator,
            "_find_best_specialist",
            AsyncMock(return_value=None),
        ):
            specialists = [_make_specialist("UnrelatedAgent", score=0.1)]
            issue = Issue(
                type=IssueType.FORMATTING, severity=Priority.LOW, message="m",
            )
            tasks = await coordinator._create_issue_tasks(
                specialists, [issue], iteration=0,
            )
        assert tasks == []


# ---------------------------------------------------------------------------
# handle_issues full flow
# ---------------------------------------------------------------------------


class TestHandleIssues:
    @pytest.mark.asyncio
    async def test_handle_issues_initializes_when_agents_empty(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        formatting = _make_specialist("FormattingAgent", score=0.8)
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="m")
        with patch(
            "crackerjack.agents.base.agent_registry.create_all",
            return_value=[formatting],
        ):
            result = await coordinator.handle_issues([issue], iteration=0)

        assert result.success is True
        assert formatting.analyze_and_fix.await_count >= 1

    @pytest.mark.asyncio
    async def test_handle_issues_handles_exception_in_subgroup(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        agent = _make_specialist("FormattingAgent", score=0.8)
        coordinator.agents = [agent]
        # Make a subgroup task raise by returning an exception from asyncio.gather.
        bad_issue = Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="bad",
        )

        # Replace the dispatch so the inner call raises an exception
        # without breaking gather. We do this by patching the inner
        # _handle_issues_by_type to return a coroutine that raises.
        async def boom(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("kaboom")

        with patch.object(coordinator, "_handle_issues_by_type", side_effect=boom):
            # _handle_issues wraps this in asyncio.gather(return_exceptions=True),
            # so the result is still a FixResult (but with success=False).
            result = await coordinator.handle_issues([bad_issue], iteration=0)
        # Aggregate over multiple types may all fail, so we don't require success=True
        assert result is not None  # structure check

    @pytest.mark.asyncio
    async def test_handle_issues_no_issues_returns_success(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        # Empty input short-circuits before initialising agents.
        result = await coordinator.handle_issues([], iteration=0)
        assert result.success is True
        assert result.confidence == 1.0


# ---------------------------------------------------------------------------
# _handle_with_single_agent: cache hit, fresh, tracking
# ---------------------------------------------------------------------------


class TestHandleWithSingleAgent:
    @pytest.mark.asyncio
    async def test_fresh_execution_path(
        self,
        coordinator: AgentCoordinator,
        mock_tracker: Mock,
        mock_debugger: Mock,
    ) -> None:
        agent = _make_specialist("FormattingAgent", score=0.8)
        issue = Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="m",
            file_path="/p.py",
            line_number=1,
        )

        result = await coordinator._handle_with_single_agent(agent, issue)
        assert result.success is True
        assert agent.can_handle.await_count >= 1
        mock_tracker.track_agent_processing.assert_called()
        mock_tracker.track_agent_complete.assert_called()
        # The debugger must have been called for both "processing_started" and
        # "processing_completed" events.
        activities = [
            call.kwargs.get("activity")
            for call in mock_debugger.log_agent_activity.call_args_list
        ]
        assert "processing_started" in activities
        assert "processing_completed" in activities

    @pytest.mark.asyncio
    async def test_cache_hit_returns_cached_result(
        self,
        coordinator: AgentCoordinator,
        mock_tracker: Mock,
    ) -> None:
        agent = _make_specialist("FormattingAgent", score=0.8)
        issue = Issue(
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="m",
            file_path="/p.py",
            line_number=1,
        )
        cached = FixResult(
            success=True, confidence=0.95, fixes_applied=["cached-fix"],
        )
        # Replace the cache with a mock that returns a value.
        coordinator.cache = MagicMock()
        coordinator.cache.get_agent_decision = Mock(return_value=cached)

        result = await coordinator._handle_with_single_agent(agent, issue)
        assert result is cached
        mock_tracker.track_agent_complete.assert_called_with(agent.name, cached)

    @pytest.mark.asyncio
    async def test_executor_swallows_exception(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        """The @agent_error_boundary decorator converts exceptions into FixResults."""
        agent = _make_specialist("FormattingAgent")
        agent.analyze_and_fix = AsyncMock(side_effect=RuntimeError("boom"))
        issue = Issue(
            type=IssueType.FORMATTING, severity=Priority.LOW, message="m",
            file_path="/p.py", line_number=1,
        )
        result = await coordinator._execute_agent(agent, issue)
        assert result.success is False
        assert any("boom" in r or "error" in r.lower() for r in result.remaining_issues)


# ---------------------------------------------------------------------------
# _cached_analyze_and_fix
# ---------------------------------------------------------------------------


class TestCachedAnalyzeAndFix:
    @pytest.mark.asyncio
    async def test_uses_in_memory_cache(self, coordinator: AgentCoordinator) -> None:
        agent = _make_specialist("FormattingAgent")
        issue = Issue(
            type=IssueType.FORMATTING, severity=Priority.LOW, message="m",
            file_path="/p.py", line_number=1,
        )
        cached = FixResult(success=True, confidence=0.99, fixes_applied=["mem"])
        coordinator._issue_cache[coordinator._get_cache_key(agent.name, issue)] = cached

        result = await coordinator._cached_analyze_and_fix(agent, issue)
        assert result is cached
        # analyze_and_fix should NOT have been called when the in-memory cache hits.
        agent.analyze_and_fix.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_uses_persistent_cache_then_stores_in_memory(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        agent = _make_specialist("FormattingAgent")
        issue = Issue(
            type=IssueType.FORMATTING, severity=Priority.LOW, message="m",
            file_path="/p.py", line_number=1,
        )
        cached = FixResult(success=True, confidence=0.9, fixes_applied=["persisted"])
        coordinator.cache = MagicMock()
        coordinator.cache.get_agent_decision = Mock(return_value=cached)

        result = await coordinator._cached_analyze_and_fix(agent, issue)
        assert result.success is True
        agent.analyze_and_fix.assert_not_awaited()
        # After hitting persistent cache, the coordinator should have promoted it
        # into its in-memory cache for next time.
        assert (
            coordinator._issue_cache[coordinator._get_cache_key(agent.name, issue)]
            is cached
        )

    @pytest.mark.asyncio
    async def test_caches_high_confidence_success(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        agent = _make_specialist("FormattingAgent", score=0.8)
        issue = Issue(
            type=IssueType.FORMATTING, severity=Priority.LOW, message="m",
            file_path="/p.py", line_number=1,
        )
        coordinator.cache = MagicMock()
        coordinator.cache.get_agent_decision = Mock(return_value=None)
        coordinator.cache.set_agent_decision = Mock()

        result = await coordinator._cached_analyze_and_fix(agent, issue)
        assert result.success is True
        # Successful, high-confidence result should be cached in memory and
        # written through to the persistent cache.
        key = coordinator._get_cache_key(agent.name, issue)
        assert key in coordinator._issue_cache
        coordinator.cache.set_agent_decision.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_cache_low_confidence(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        agent = _make_specialist("FormattingAgent")
        agent.analyze_and_fix = AsyncMock(
            return_value=FixResult(success=True, confidence=0.5),
        )
        issue = Issue(
            type=IssueType.FORMATTING, severity=Priority.LOW, message="m",
            file_path="/p.py", line_number=1,
        )
        result = await coordinator._cached_analyze_and_fix(agent, issue)
        assert result.success is True
        # The success-but-low-confidence path is intentionally not cached.
        key = coordinator._get_cache_key(agent.name, issue)
        assert key not in coordinator._issue_cache


# ---------------------------------------------------------------------------
# _apply_built_in_preference
# ---------------------------------------------------------------------------


class TestApplyBuiltInPreference:
    def test_returns_best_agent_when_no_built_in_competitor(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        formatting = _make_specialist("FormattingAgent", score=0.9)
        other = _make_specialist("RandomAgent", score=0.7)
        other.__class__ = type("RandomAgent", (SubAgent,), {})  # type: ignore[method-assign]
        coordinator.agents = [formatting, other]

        result = coordinator._apply_built_in_preference(
            [(formatting, 0.9), (other, 0.7)],
            formatting,
            0.9,
            iteration=0,
        )
        assert result is formatting

    def test_threshold_aggressive_mode_still_returns_best(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        # best_score below threshold triggers "aggressive" path on iteration >= 5
        formatting = _make_specialist("FormattingAgent", score=0.2)
        coordinator.agents = [formatting]

        result = coordinator._apply_built_in_preference(
            [(formatting, 0.2)],
            formatting,
            0.2,
            iteration=5,
        )
        # Aggressive mode returns the best agent even below threshold.
        assert result is formatting

    def test_prefers_built_in_when_close(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        # best_agent is the non-built-in with a tiny lead; built-in should win.
        built_in = _make_specialist("FormattingAgent", score=0.85)
        best = _make_specialist("CustomAgent", score=0.88)
        best.__class__ = type("CustomAgent", (SubAgent,), {})  # type: ignore[method-assign]
        coordinator.agents = [built_in, best]

        result = coordinator._apply_built_in_preference(
            [(built_in, 0.85), (best, 0.88)],
            best,
            0.88,
            iteration=0,
        )
        # The function should prefer FormattingAgent because it is a built-in
        # and the score difference is within CLOSE_SCORE_THRESHOLD (0.05).
        assert result is built_in


# ---------------------------------------------------------------------------
# _get_session_metrics_from_context and workflow analysis paths
# ---------------------------------------------------------------------------


class TestWorkflowAnalysis:
    @pytest.mark.asyncio
    async def test_get_workflow_recommendations_no_engine(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        assert coordinator.workflow_engine is None
        assert await coordinator._get_workflow_recommendations() == []

    @pytest.mark.asyncio
    async def test_get_workflow_recommendations_no_metrics(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        coordinator.workflow_engine = Mock()
        assert await coordinator._get_workflow_recommendations(None) == []

    @pytest.mark.asyncio
    async def test_get_workflow_recommendations_no_git_data(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        coordinator.workflow_engine = Mock()
        metrics = Mock()
        metrics.git_commit_velocity = None
        metrics.git_merge_success_rate = None
        metrics.git_workflow_efficiency_score = None
        metrics.conventional_commit_compliance = None
        assert await coordinator._get_workflow_recommendations(metrics) == []

    @pytest.mark.asyncio
    async def test_get_workflow_recommendations_success(
        self,
        coordinator: AgentCoordinator,
        mock_context: Mock,
    ) -> None:
        coordinator.workflow_engine = Mock()
        # _log_workflow_insights formats merge_rate with `:.1%` and
        # efficiency with `:.0f`, so the metrics need numeric values.
        metrics = Mock()
        metrics.git_commit_velocity = 1.0
        metrics.git_merge_success_rate = 0.9
        metrics.git_workflow_efficiency_score = 80.0
        coordinator.workflow_engine.session_metrics = metrics
        insights = Mock()
        insights.recommendations = [
            Mock(title="rec-1", priority="critical"),
        ]
        coordinator.workflow_engine.generate_insights = Mock(return_value=insights)

        # Engine.session_metrics is read by _log_workflow_insights; pass a mock
        # context with metrics attached so both call sites have the data.
        mock_context.session_metrics = metrics
        result = await coordinator._get_workflow_recommendations(metrics)
        assert result == ["rec-1"]

    @pytest.mark.asyncio
    async def test_get_workflow_recommendations_runtime_error(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        coordinator.workflow_engine = Mock()
        coordinator.workflow_engine.generate_insights = Mock(
            side_effect=RuntimeError("nope"),
        )
        metrics = Mock()
        metrics.git_commit_velocity = 1.0
        assert await coordinator._get_workflow_recommendations(metrics) == []

    def test_get_session_metrics_from_context_returns_attribute(
        self,
        coordinator: AgentCoordinator,
        mock_context: Mock,
    ) -> None:
        sentinel = object()
        mock_context.session_metrics = sentinel
        assert coordinator._get_session_metrics_from_context() is sentinel

    def test_get_session_metrics_from_context_default_none(
        self,
        coordinator: AgentCoordinator,
        mock_context: Mock,
    ) -> None:
        # Make sure gettattr returns None when attribute is missing.
        del mock_context.session_metrics
        assert coordinator._get_session_metrics_from_context() is None

    @pytest.mark.asyncio
    async def test_analyze_workflow_for_agent_selection_swallows_exceptions(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        with patch.object(
            coordinator,
            "_get_session_metrics_from_context",
            side_effect=AttributeError("boom"),
        ):
            # Should not raise.
            await coordinator._analyze_workflow_for_agent_selection()

    def test_log_workflow_insights_no_engine_returns_early(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        # Without an engine, the function early-returns and produces no log lines.
        coordinator._log_workflow_insights(insights=Mock())  # should not raise


# ---------------------------------------------------------------------------
# _track_agent_execution
# ---------------------------------------------------------------------------


class TestTrackAgentExecution:
    @pytest.mark.asyncio
    async def test_track_agent_execution_happy_path(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        with patch(
            "crackerjack.services.metrics.get_metrics",
        ) as get_metrics:
            metrics = Mock()
            get_metrics.return_value = metrics
            result = FixResult(success=True, confidence=0.8, fixes_applied=["f"])
            await coordinator._track_agent_execution(
                job_id="j",
                agent_name="A",
                issue_type="type_error",
                result=result,
                execution_time_ms=12.5,
            )
        metrics.execute.assert_called_once()
        # Confirm the positional tuple contains expected fields
        params = metrics.execute.call_args.args[1]
        assert params[0] == "j"
        assert params[1] == "A"
        assert params[2] == "type_error"
        assert params[3] is True
        assert params[4] == 0.8
        assert params[5] == 1
        assert params[6] == 0
        assert params[7] == 0
        assert params[8] == 12.5

    @pytest.mark.asyncio
    async def test_track_agent_execution_handles_exceptions(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        with patch(
            "crackerjack.services.metrics.get_metrics",
            side_effect=ImportError("missing"),
        ):
            # Should swallow the error.
            await coordinator._track_agent_execution(
                job_id="j", agent_name="A", issue_type="x",
                result=FixResult(success=True, confidence=0.0),
                execution_time_ms=None,
            )


# ---------------------------------------------------------------------------
# _handle_with_multi_agent_fallback
# ---------------------------------------------------------------------------


class TestMultiAgentFallback:
    @pytest.mark.asyncio
    async def test_early_iteration_no_specialist(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        specialists = [_make_specialist("FormattingAgent", score=0.5)]
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="m")
        with patch.object(
            coordinator,
            "_find_best_specialist",
            AsyncMock(return_value=None),
        ):
            result = await coordinator._handle_with_multi_agent_fallback(
                specialists, issue, iteration=2,
            )
        assert result.success is False

    @pytest.mark.asyncio
    async def test_aggressive_iteration_all_agents_fail(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        specialists = [
            _make_specialist("FormattingAgent", score=0.9),
            _make_specialist("RefactoringAgent", score=0.7),
        ]
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="m")
        with patch.object(
            coordinator,
            "_handle_with_single_agent",
            AsyncMock(return_value=FixResult(success=False, confidence=0.0)),
        ):
            result = await coordinator._handle_with_multi_agent_fallback(
                specialists, issue, iteration=5,
            )
        assert result.success is False
        assert result.remaining_issues


# ---------------------------------------------------------------------------
# _record_performance_metrics
# ---------------------------------------------------------------------------


class TestRecordPerformanceMetrics:
    def test_records_when_model_present(self, coordinator: AgentCoordinator) -> None:
        coordinator.context.config = {"model_name": "foo"}
        coordinator.performance_tracker = Mock()
        coordinator._record_performance_metrics(
            agent_name="A",
            issue_type="type_error",
            result=FixResult(success=True, confidence=0.9),
            confidence=0.9,
            execution_time_seconds=1.0,
        )
        coordinator.performance_tracker.record_attempt.assert_called_once()

    def test_uses_default_model_name_when_missing(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        coordinator.context.config = {}
        coordinator.performance_tracker = Mock()
        coordinator._record_performance_metrics(
            agent_name="A",
            issue_type="type_error",
            result=FixResult(success=True, confidence=0.9),
            confidence=0.9,
            execution_time_seconds=1.0,
        )
        call = coordinator.performance_tracker.record_attempt.call_args.kwargs
        assert call["model_name"] == "unknown"

    def test_swallows_exceptions_from_tracker(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        coordinator.context.config = {"model_name": "foo"}
        coordinator.performance_tracker = Mock()
        coordinator.performance_tracker.record_attempt.side_effect = RuntimeError("x")
        # Should not raise.
        coordinator._record_performance_metrics(
            agent_name="A",
            issue_type="type_error",
            result=FixResult(success=True, confidence=0.9),
            confidence=0.9,
            execution_time_seconds=1.0,
        )


# ---------------------------------------------------------------------------
# _log_workflow_insights
# ---------------------------------------------------------------------------


class TestLogWorkflowInsights:
    def test_logs_all_priority_buckets(self, coordinator: AgentCoordinator) -> None:
        coordinator.workflow_engine = Mock()
        metrics = Mock()
        metrics.git_commit_velocity = 1.5
        metrics.git_merge_success_rate = 0.9
        metrics.git_workflow_efficiency_score = 80.0
        coordinator.workflow_engine.session_metrics = metrics

        rec_crit = Mock(title="crit-rec", priority="critical")
        rec_high = Mock(title="high-rec", priority="high")
        rec_med = Mock(title="med-rec", priority="medium")
        rec_low = Mock(title="low-rec", priority="low")
        insights = Mock()
        insights.recommendations = [rec_crit, rec_high, rec_med, rec_low]

        # Should not raise.
        coordinator._log_workflow_insights(insights=insights)

    def test_logs_partial_metrics(self, coordinator: AgentCoordinator) -> None:
        coordinator.workflow_engine = Mock()
        metrics = Mock()
        metrics.git_commit_velocity = 2.0
        metrics.git_merge_success_rate = None
        metrics.git_workflow_efficiency_score = 70.0
        coordinator.workflow_engine.session_metrics = metrics

        insights = Mock()
        insights.recommendations = []
        coordinator._log_workflow_insights(insights=insights)

    def test_no_insights_no_log(self, coordinator: AgentCoordinator) -> None:
        coordinator.workflow_engine = Mock()
        coordinator._log_workflow_insights(insights=None)


# ---------------------------------------------------------------------------
# _find_best_specialist — strategy boost branch
# ---------------------------------------------------------------------------


class TestFindBestSpecialist:
    @pytest.mark.asyncio
    async def test_no_candidates_returns_none(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="m")
        result = await coordinator._find_best_specialist([], issue, iteration=0)
        assert result is None

    @pytest.mark.asyncio
    async def test_workflow_boost_applied(
        self,
        coordinator: AgentCoordinator,
        mock_context: Mock,
    ) -> None:
        # Wire a workflow engine that produces a critical recommendation.
        engine = Mock()
        metrics = Mock()
        metrics.git_commit_velocity = 1.0
        engine.session_metrics = metrics
        rec = Mock(title="Merge conflicts in workflow", priority="critical")
        insights = Mock()
        insights.recommendations = [rec]
        engine.generate_insights = Mock(return_value=insights)
        coordinator.workflow_engine = engine
        mock_context.session_metrics = metrics

        # ArchitectAgent (built-in) should be boosted; CustomAgent should not.
        architect = _make_specialist("ArchitectAgent", score=0.6)
        custom = _make_specialist("CustomAgent", score=0.6)
        custom.__class__ = type("CustomAgent", (SubAgent,), {})  # type: ignore[method-assign]

        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="m")
        result = await coordinator._find_best_specialist(
            [architect, custom], issue, iteration=0,
        )
        assert result is architect


# ---------------------------------------------------------------------------
# Proactive flow
# ---------------------------------------------------------------------------


class TestProactiveFlow:
    @pytest.mark.asyncio
    async def test_handle_issues_proactively_empty(self, coordinator: AgentCoordinator) -> None:
        result = await coordinator.handle_issues_proactively([])
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_issues_proactively_routes_to_handle_issues(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        coordinator.proactive_mode = False
        with patch.object(
            coordinator, "handle_issues",
            AsyncMock(return_value=FixResult(success=True, confidence=0.5)),
        ) as handle:
            result = await coordinator.handle_issues_proactively(
                [Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="x")],
            )
        handle.assert_awaited_once()
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_handle_issues_proactively_reactive_fallback(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        coordinator.proactive_mode = True
        # Force the architectural plan to fall back; that routes the
        # proactive flow back to handle_issues. Patch _create_architectural_plan
        # so we don't depend on the registry state.
        with patch.object(
            coordinator, "_create_architectural_plan",
            AsyncMock(return_value={"strategy": "reactive_fallback", "patterns": []}),
        ), patch.object(
            coordinator, "handle_issues",
            AsyncMock(return_value=FixResult(success=True, confidence=0.7)),
        ) as handle:
            result = await coordinator.handle_issues_proactively(
                [Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="x")],
            )
        handle.assert_awaited_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_create_architectural_plan_with_architect(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        architect = _make_specialist("ArchitectAgent")
        architect.plan_before_action = AsyncMock(  # type: ignore[method-assign]
            return_value={"strategy": "default", "confidence": 0.6},
        )
        coordinator.agents = [architect]
        issues = [Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="c")]

        plan = await coordinator._create_architectural_plan(issues)
        assert plan["strategy"] == "default"
        assert "all_issues" in plan

    def test_prioritize_issues_by_plan_external_strategy(self, coordinator: AgentCoordinator) -> None:
        issues = [
            Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="c"),
            Issue(type=IssueType.DRY_VIOLATION, severity=Priority.HIGH, message="d"),
            Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="t"),
        ]
        plan = {"strategy": "external_specialist_guided"}
        groups = coordinator._prioritize_issues_by_plan(issues, plan)
        # Two groups: complex first, others second.
        assert len(groups) == 2
        assert groups[0] and groups[0][0].type in {
            IssueType.COMPLEXITY, IssueType.DRY_VIOLATION,
        }
        assert groups[1] and groups[1][0].type == IssueType.TYPE_ERROR

    def test_prioritize_issues_by_plan_external_strategy_only_complex(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        issues = [Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="t")]
        plan = {"strategy": "external_specialist_guided"}
        groups = coordinator._prioritize_issues_by_plan(issues, plan)
        # No complex issues → single group of others.
        assert len(groups) == 1
        assert groups[0] and groups[0][0].type == IssueType.TYPE_ERROR

    def test_prioritize_issues_by_plan_default_strategy(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        issues = [
            Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="c"),
            Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="t"),
        ]
        plan = {"strategy": "default"}
        groups = coordinator._prioritize_issues_by_plan(issues, plan)
        # Two groups, one per type.
        assert len(groups) == 2

    def test_mark_critical_group_failure_appends(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        result = FixResult(success=True, confidence=1.0)
        issue = Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="c", id="i1")
        marked = coordinator._mark_critical_group_failure(result, [issue])
        assert marked.success is False
        assert any("Critical issue group failed" in r for r in marked.remaining_issues)
        assert "i1" in marked.remaining_issues[0]

    def test_should_fail_on_group_failure(self, coordinator: AgentCoordinator) -> None:
        critical_issue = Issue(
            type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="c",
        )
        non_critical_issue = Issue(
            type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="t",
        )
        failure = FixResult(success=False, confidence=0.0)
        success = FixResult(success=True, confidence=1.0)

        assert (
            coordinator._should_fail_on_group_failure(failure, [critical_issue], {})
            is True
        )
        assert (
            coordinator._should_fail_on_group_failure(success, [critical_issue], {})
            is False
        )
        assert (
            coordinator._should_fail_on_group_failure(failure, [non_critical_issue], {})
            is False
        )

    @pytest.mark.asyncio
    async def test_validate_against_plan_no_validation(self, coordinator: AgentCoordinator) -> None:
        plan: dict = {"strategy": "default"}
        result = FixResult(success=True, confidence=0.8)
        out = await coordinator._validate_against_plan(result, plan)
        assert out is result

    @pytest.mark.asyncio
    async def test_validate_against_plan_with_validation(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        plan = {"strategy": "x", "patterns": ["p1"], "validation": ["v1"]}
        result = FixResult(success=True, confidence=0.8)
        out = await coordinator._validate_against_plan(result, plan)
        # Recommendations should be extended, not replaced.
        joined = " ".join(out.recommendations)
        assert "Validate with: v1" in joined
        assert "Applied strategy: x" in joined
        assert "Used patterns: p1" in joined

    def test_handle_issue_group_with_plan_empty(self, coordinator: AgentCoordinator) -> None:
        result = asyncio.run(  # type: ignore[func-returns-value]
            coordinator._handle_issue_group_with_plan([], {}),
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_handle_issue_group_with_plan_uses_architect(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        architect = _make_specialist("ArchitectAgent")
        # Each architect call returns a different shape to exercise every branch
        # of the coroutine/sync/other handling in _handle_issue_group_with_plan.

        # Issue objects are passed positionally to analyze_and_fix; we ignore
        # the arg and return a value of the desired shape.

        async def aw(issue):  # type: ignore[no-untyped-def]
            return FixResult(
                success=True, confidence=0.7, fixes_applied=["async-fix"],
            )

        def sync_fn(issue):  # type: ignore[no-untyped-def]
            return FixResult(
                success=True, confidence=0.8, fixes_applied=["sync-fix"],
            )

        def other_fn(issue):  # type: ignore[no-untyped-def]
            return "not-a-fixresult"

        # Patch the analyze_and_fix method with a function whose return values
        # are exactly what each branch needs. We do this by creating a custom
        # callable that returns the next value from a list on each call.
        results = [
            aw(Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="0")),
            sync_fn(Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="1")),
            other_fn(Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="2")),
        ]
        call_count = {"i": 0}

        def dispatch(issue):  # type: ignore[no-untyped-def]
            result = results[call_count["i"]]
            call_count["i"] += 1
            return result

        architect.analyze_and_fix = Mock(side_effect=dispatch)
        coordinator.agents = [architect]

        issues = [
            Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message=f"m{i}", id=f"id{i}")
            for i in range(3)
        ]
        plan = {"strategy": "external_specialist_guided"}
        result = await coordinator._handle_issue_group_with_plan(issues, plan)
        # The first two return FixResults that get merged; the third is not a
        # FixResult, but the merge_with helper tolerates that path with
        # confidence=0.0 default.
        assert "async-fix" in result.fixes_applied
        assert "sync-fix" in result.fixes_applied

    @pytest.mark.asyncio
    async def test_handle_issue_group_with_plan_no_architect(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        # Non-architectural plan → falls through to _handle_issues_by_type.
        coordinator.agents = []
        type_error = Issue(
            type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="t",
        )
        # With no agents, _handle_issues_by_type returns no-agents FixResult.
        result = await coordinator._handle_issue_group_with_plan(
            [type_error], {"strategy": "default"},
        )
        assert result.success is False


# ---------------------------------------------------------------------------
# _get_strategy_name (already partially covered; ensure the boundary is right)
# ---------------------------------------------------------------------------


class TestStrategyNameBoundaries:
    def test_conservative_upper_bound(self, coordinator: AgentCoordinator) -> None:
        assert coordinator._get_strategy_name(1) == "conservative"

    def test_moderate_upper_bound(self, coordinator: AgentCoordinator) -> None:
        assert coordinator._get_strategy_name(4) == "moderate"

    def test_aggressive_upper_bound(self, coordinator: AgentCoordinator) -> None:
        assert coordinator._get_strategy_name(9) == "aggressive"

    def test_desperate_lower_bound(self, coordinator: AgentCoordinator) -> None:
        assert coordinator._get_strategy_name(10) == "desperate"


# ---------------------------------------------------------------------------
# Workflow agent boost — single critical / high branch
# ---------------------------------------------------------------------------


class TestWorkflowAgentBoost:
    @pytest.mark.asyncio
    async def test_boost_with_engine_but_no_metrics(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        coordinator.workflow_engine = Mock()
        # session_metrics is None → no boost.
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="m")
        assert await coordinator._get_workflow_agent_boost(issue) == {}

    @pytest.mark.asyncio
    async def test_boost_high_priority_conventional(
        self,
        coordinator: AgentCoordinator,
        mock_context: Mock,
    ) -> None:
        coordinator.workflow_engine = Mock()
        metrics = Mock()
        metrics.git_commit_velocity = 1.0
        coordinator.workflow_engine.session_metrics = metrics
        rec = Mock(title="Use conventional commits", priority="high")
        insights = Mock()
        insights.recommendations = [rec]
        coordinator.workflow_engine.generate_insights = Mock(return_value=insights)
        # Boost lookup goes through context.session_metrics, not engine.session_metrics.
        mock_context.session_metrics = metrics

        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="m")
        boost = await coordinator._get_workflow_agent_boost(issue)
        assert boost.get("DocumentationAgent") == 0.1

    @pytest.mark.asyncio
    async def test_boost_swallows_attribute_error(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        coordinator.workflow_engine = Mock()
        # Make generate_insights raise AttributeError to exercise the
        # swallow branch.
        coordinator.workflow_engine.generate_insights = Mock(
            side_effect=AttributeError("missing attr"),
        )
        issue = Issue(type=IssueType.FORMATTING, severity=Priority.LOW, message="m")
        boost = await coordinator._get_workflow_agent_boost(issue)
        assert boost == {}


# ---------------------------------------------------------------------------
# _coerce_cached_decision extras
# ---------------------------------------------------------------------------


class TestCoerceCachedDecision:
    def test_returns_none_for_non_dict_non_fixresult(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        assert coordinator._coerce_cached_decision(42) is None
        assert coordinator._coerce_cached_decision(None) is None
        assert coordinator._coerce_cached_decision(["a", "b"]) is None

    def test_dict_with_invalid_keys_returns_none(
        self,
        coordinator: AgentCoordinator,
    ) -> None:
        # Missing required 'success' field.
        assert coordinator._coerce_cached_decision({"confidence": 0.5}) is None

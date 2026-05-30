"""Tests for AgentCoordinator."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, AsyncMock

from crackerjack.agents.base import AgentContext, Issue, IssueType, FixResult, Priority, SubAgent
from crackerjack.agents.coordinator import AgentCoordinator, ISSUE_TYPE_TO_AGENTS
from crackerjack.models.protocols import AgentTrackerProtocol, DebuggerProtocol
from crackerjack.services.cache import CrackerjackCache


@pytest.fixture
def mock_tracker():
    """Create mock tracker."""
    tracker = Mock(spec=AgentTrackerProtocol)
    tracker.register_agents = Mock()
    tracker.set_coordinator_status = Mock()
    tracker.track_agent_processing = Mock()
    tracker.track_agent_complete = Mock()
    return tracker


@pytest.fixture
def mock_debugger():
    """Create mock debugger."""
    debugger = Mock(spec=DebuggerProtocol)
    debugger.enabled = False
    debugger.debug_operation = Mock(return_value=iter(["test-id"]))
    debugger.log_agent_activity = Mock()
    return debugger


@pytest.fixture
def mock_context():
    """Create mock AgentContext."""
    context = Mock(spec=AgentContext)
    context.project_path = Path("/test/project")
    context.config = {"model_name": "test-model"}
    context.fix_strategy_memory = None
    return context


@pytest.fixture
def cache():
    """Create CrackerjackCache instance."""
    return CrackerjackCache()


@pytest.fixture
def coordinator(mock_context, mock_tracker, mock_debugger, cache):
    """Create AgentCoordinator instance."""
    return AgentCoordinator(
        context=mock_context,
        tracker=mock_tracker,
        debugger=mock_debugger,
        cache=cache,
        job_id="test-job-001",
    )


class TestAgentCoordinator:
    """Tests for AgentCoordinator."""

    def test_initialization(self, coordinator, mock_context, mock_tracker, mock_debugger):
        """Test coordinator initialization."""
        assert coordinator.context == mock_context
        assert coordinator.tracker == mock_tracker
        assert coordinator.debugger == mock_debugger
        assert coordinator.job_id == "test-job-001"
        assert coordinator.proactive_mode is True
        assert len(coordinator.agents) == 0

    def test_generate_job_id(self, coordinator):
        """Test _generate_job_id creates valid job ID."""
        job_id = coordinator._generate_job_id()
        assert job_id.startswith("job_")
        assert len(job_id) > 10

    def test_issue_type_to_agents_mapping(self):
        """Test ISSUE_TYPE_TO_AGENTS has correct structure."""
        assert IssueType.TYPE_ERROR in ISSUE_TYPE_TO_AGENTS
        assert "TypeErrorSpecialistAgent" in ISSUE_TYPE_TO_AGENTS[IssueType.TYPE_ERROR]
        assert IssueType.DEAD_CODE in ISSUE_TYPE_TO_AGENTS
        assert IssueType.IMPORT_ERROR in ISSUE_TYPE_TO_AGENTS

    def test_group_issues_by_type(self, coordinator):
        """Test _group_issues_by_type groups issues correctly."""
        issues = [
            Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Error 1"),
            Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Error 2"),
            Issue(type=IssueType.DEAD_CODE, severity=Priority.MEDIUM, message="Dead"),
        ]
        grouped = coordinator._group_issues_by_type(issues)
        assert len(grouped) == 2
        assert len(grouped[IssueType.TYPE_ERROR]) == 2
        assert len(grouped[IssueType.DEAD_CODE]) == 1

    def test_create_issue_hash(self, coordinator):
        """Test _create_issue_hash creates consistent hashes."""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test message",
            file_path="/test/file.py",
            line_number=10,
        )
        hash1 = coordinator._create_issue_hash(issue)
        hash2 = coordinator._create_issue_hash(issue)
        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hex length

    def test_get_cache_key(self, coordinator):
        """Test _get_cache_key creates correct keys."""
        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test",
            file_path="/test.py",
            line_number=1,
        )
        key = coordinator._get_cache_key("TestAgent", issue)
        assert "TestAgent:" in key

    def test_get_strategy_name(self, coordinator):
        """Test _get_strategy_name returns correct strategy for iteration."""
        assert coordinator._get_strategy_name(0) == "conservative"
        assert coordinator._get_strategy_name(1) == "conservative"
        assert coordinator._get_strategy_name(3) == "moderate"
        assert coordinator._get_strategy_name(7) == "aggressive"
        assert coordinator._get_strategy_name(15) == "desperate"

    def test_is_built_in_agent(self, coordinator):
        """Test _is_built_in_agent identifies built-in agents."""
        agent1 = Mock()
        agent1.__class__ = type("ArchitectAgent", (), {})
        agent2 = Mock()
        agent2.__class__ = type("FormattingAgent", (), {})
        agent3 = Mock()
        agent3.__class__ = type("CustomAgent", (), {})

        assert coordinator._is_built_in_agent(agent1)
        assert coordinator._is_built_in_agent(agent2)
        assert not coordinator._is_built_in_agent(agent3)

    def test_coerce_cached_decision_fix_result(self, coordinator):
        """Test _coerce_cached_decision returns FixResult directly."""
        fix_result = FixResult(success=True, confidence=0.8)
        result = coordinator._coerce_cached_decision(fix_result)
        assert result == fix_result

    def test_coerce_cached_decision_dict(self, coordinator):
        """Test _coerce_cached_decision converts dict to FixResult."""
        data = {"success": True, "confidence": 0.8, "fixes_applied": [], "remaining_issues": [], "files_modified": []}
        result = coordinator._coerce_cached_decision(data)
        assert isinstance(result, FixResult)
        assert result.success is True

    def test_coerce_cached_decision_invalid(self, coordinator):
        """Test _coerce_cached_decision returns None for invalid data."""
        result = coordinator._coerce_cached_decision("invalid")
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_issues_empty_list(self, coordinator):
        """Test handle_issues with empty list returns success."""
        result = await coordinator.handle_issues([])
        assert result.success is True
        assert result.confidence == 1.0

    def test_get_agent_capabilities(self, coordinator):
        """Test get_agent_capabilities returns agent info."""
        coordinator.initialize_agents()
        capabilities = coordinator.get_agent_capabilities()
        assert isinstance(capabilities, dict)

    def test_set_proactive_mode(self, coordinator):
        """Test set_proactive_mode enables/disables proactive mode."""
        coordinator.set_proactive_mode(False)
        assert coordinator.proactive_mode is False

        coordinator.set_proactive_mode(True)
        assert coordinator.proactive_mode is True

    def test_find_highest_scoring_agent(self, coordinator):
        """Test _find_highest_scoring_agent selects best agent."""
        mock_agent1 = Mock()
        mock_agent1.name = "Agent1"
        mock_agent2 = Mock()
        mock_agent2.name = "Agent2"

        candidates = [(mock_agent1, 0.6), (mock_agent2, 0.9)]

        best_agent, best_score = coordinator._find_highest_scoring_agent(candidates)
        assert best_agent == mock_agent2
        assert best_score == 0.9

    def test_find_highest_scoring_agent_empty(self, coordinator):
        """Test _find_highest_scoring_agent handles empty list."""
        best_agent, best_score = coordinator._find_highest_scoring_agent([])
        assert best_agent is None
        assert best_score == 0.0

    def test_merge_fix_results(self, coordinator):
        """Test _merge_fix_results combines results correctly."""
        results = [
            FixResult(success=True, confidence=0.8, fixes_applied=["Fix1"]),
            FixResult(success=True, confidence=0.9, fixes_applied=["Fix2"]),
        ]
        merged = coordinator._merge_fix_results(results)
        assert merged.success is True
        assert merged.confidence == 0.9
        assert "Fix1" in merged.fixes_applied
        assert "Fix2" in merged.fixes_applied

    def test_merge_fix_results_with_failure(self, coordinator):
        """Test _merge_fix_results handles failures."""
        results = [
            FixResult(success=True, confidence=0.8),
            FixResult(success=False, confidence=0.5),
        ]
        merged = coordinator._merge_fix_results(results)
        assert merged.success is False

    def test_should_prefer_built_in_agent(self, coordinator):
        """Test _should_prefer_built_in_agent logic."""
        agent1 = Mock(spec=SubAgent)
        agent1.__class__.__name__ = "ArchitectAgent"
        agent2 = Mock(spec=SubAgent)
        agent2.__class__.__name__ = "CustomAgent"

        # Built-in agent within threshold should be preferred
        result = coordinator._should_prefer_built_in_agent(agent1, agent2, 0.85, 0.88, 0.05)
        assert result is True

        # Non-built-in agent should not be preferred
        result = coordinator._should_prefer_built_in_agent(agent2, agent1, 0.85, 0.88, 0.05)
        assert result is False

    def test_filter_complex_issues(self, coordinator):
        """Test _filter_complex_issues identifies complex issues."""
        issues = [
            Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="Complex"),
            Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Error"),
            Issue(type=IssueType.DRY_VIOLATION, severity=Priority.MEDIUM, message="DRY"),
        ]
        filtered = coordinator._filter_complex_issues(issues)
        assert len(filtered) == 2
        assert all(i.type in {IssueType.COMPLEXITY, IssueType.DRY_VIOLATION} for i in filtered)

    def test_is_critical_group(self, coordinator):
        """Test _is_critical_group identifies critical issue groups."""
        critical_issues = [
            Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="Complex"),
        ]
        non_critical_issues = [
            Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Error"),
        ]
        assert coordinator._is_critical_group(critical_issues, {}) is True
        assert coordinator._is_critical_group(non_critical_issues, {}) is False

    def test_get_architect_agent_not_found(self, coordinator):
        """Test _get_architect_agent returns None when not available."""
        coordinator.agents = []
        architect = coordinator._get_architect_agent()
        assert architect is None

    def test_create_no_agents_result(self, coordinator):
        """Test _create_no_agents_result creates proper FixResult."""
        result = coordinator._create_no_agents_result(IssueType.TYPE_ERROR)
        assert result.success is False
        assert result.confidence == 0.0
        assert "No agents for type_error issues" in result.remaining_issues

    def test_create_fallback_plan(self, coordinator):
        """Test _create_fallback_plan creates fallback plan."""
        plan = coordinator._create_fallback_plan("No architect available")
        assert plan["strategy"] == "reactive_fallback"
        assert plan["patterns"] == []


class TestAgentCoordinatorScoring:
    """Tests for agent scoring and selection logic."""

    @pytest.mark.asyncio
    async def test_score_all_specialists(self, coordinator, mock_context):
        """Test _score_all_specialists scores all agents."""
        # Create mock specialists
        specialist1 = Mock(spec=SubAgent)
        specialist1.name = "Specialist1"
        specialist1.can_handle = AsyncMock(return_value=0.8)

        specialist2 = Mock(spec=SubAgent)
        specialist2.name = "Specialist2"
        specialist2.can_handle = AsyncMock(return_value=0.6)

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Type error test",
        )

        candidates = await coordinator._score_all_specialists(
            [specialist1, specialist2], issue
        )

        assert len(candidates) == 2
        assert candidates[0][1] == 0.8
        assert candidates[1][1] == 0.6

    @pytest.mark.asyncio
    async def test_score_all_specialists_handles_exception(self, coordinator):
        """Test _score_all_specialists handles exceptions gracefully."""
        specialist = Mock(spec=SubAgent)
        specialist.name = "Specialist1"
        specialist.can_handle = AsyncMock(side_effect=Exception("Error"))

        issue = Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Test")

        candidates = await coordinator._score_all_specialists([specialist], issue)
        assert len(candidates) == 0


class TestAgentCoordinatorWorkflowBoost:
    """Tests for workflow-based agent boosting."""

    @pytest.mark.asyncio
    async def test_get_workflow_agent_boost_no_engine(self, coordinator):
        """Test _get_workflow_agent_boost returns empty when no engine."""
        issue = Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Test")
        boost = await coordinator._get_workflow_agent_boost(issue)
        assert boost == {}

    @pytest.mark.asyncio
    async def test_get_workflow_agent_boost_with_engine(self, coordinator, mock_context):
        """Test _get_workflow_agent_boost with workflow engine."""
        # Create mock workflow engine
        mock_session_metrics = Mock()
        mock_session_metrics.git_commit_velocity = 5.0
        mock_session_metrics.git_merge_success_rate = 0.9
        mock_session_metrics.git_workflow_efficiency_score = 85.0
        mock_session_metrics.conventional_commit_compliance = 0.95

        mock_context.session_metrics = mock_session_metrics

        mock_engine = Mock()
        mock_engine.session_metrics = mock_session_metrics

        mock_insights = Mock()
        mock_insights.recommendations = [
            Mock(title="Workflow optimization needed", priority="critical"),
            Mock(title="Use conventional commits", priority="high"),
        ]
        mock_engine.generate_insights = Mock(return_value=mock_insights)

        coordinator.workflow_engine = mock_engine

        issue = Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Test")
        boost = await coordinator._get_workflow_agent_boost(issue)

        assert "ArchitectAgent" in boost
        assert "RefactoringAgent" in boost


class TestAgentCoordinatorMultiAgentFallback:
    """Tests for multi-agent fallback logic."""

    @pytest.mark.asyncio
    async def test_handle_with_multi_agent_fallback_early_iteration(self, coordinator):
        """Test multi-agent fallback uses single agent in early iterations."""
        specialists = [Mock(spec=SubAgent), Mock(spec=SubAgent)]
        specialists[0].name = "Agent1"
        specialists[1].name = "Agent2"

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test issue",
        )

        # Mock _find_best_specialist
        coordinator._find_best_specialist = AsyncMock(return_value=specialists[0])
        coordinator._handle_with_single_agent = AsyncMock(
            return_value=FixResult(success=True, confidence=0.8)
        )

        result = await coordinator._handle_with_multi_agent_fallback(
            specialists, issue, iteration=3
        )

        assert result.success is True
        coordinator._find_best_specialist.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_with_multi_agent_fallback_aggressive_iteration(self, coordinator):
        """Test multi-agent fallback tries multiple agents in aggressive mode."""
        specialists = [Mock(spec=SubAgent), Mock(spec=SubAgent)]
        specialists[0].name = "Agent1"
        specialists[1].name = "Agent2"

        specialists[0].can_handle = AsyncMock(return_value=0.7)
        specialists[1].can_handle = AsyncMock(return_value=0.5)

        issue = Issue(
            type=IssueType.TYPE_ERROR,
            severity=Priority.HIGH,
            message="Test issue",
        )

        # First agent fails, second succeeds
        coordinator._handle_with_single_agent = AsyncMock(
            side_effect=[
                FixResult(success=False, confidence=0.0),
                FixResult(success=True, confidence=0.7),
            ]
        )

        result = await coordinator._handle_with_multi_agent_fallback(
            specialists, issue, iteration=5
        )

        assert result.success is True
        assert coordinator._handle_with_single_agent.call_count == 2


class TestAgentCoordinatorPerformanceTracking:
    """Tests for performance tracking."""

    def test_record_performance_metrics(self, coordinator):
        """Test _record_performance_metrics records metrics."""
        result = FixResult(success=True, confidence=0.8, fixes_applied=["Fix1"])

        # Should not raise exception
        coordinator._record_performance_metrics(
            agent_name="TestAgent",
            issue_type="type_error",
            result=result,
            confidence=0.8,
            execution_time_seconds=1.5,
        )

    def test_record_performance_metrics_no_model(self, coordinator, mock_context):
        """Test _record_performance_metrics handles missing model config."""
        mock_context.config = {}
        result = FixResult(success=True, confidence=0.8)

        coordinator._record_performance_metrics(
            agent_name="TestAgent",
            issue_type="type_error",
            result=result,
            confidence=0.8,
            execution_time_seconds=1.0,
        )


class TestAgentCoordinatorArchitecturalPlan:
    """Tests for architectural planning."""

    @pytest.mark.asyncio
    async def test_create_architectural_plan_no_architect(self, coordinator):
        """Test _create_architectural_plan when no architect available."""
        coordinator.agents = []

        issues = [
            Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="Complex"),
        ]

        plan = await coordinator._create_architectural_plan(issues)
        assert plan["strategy"] == "reactive_fallback"

    @pytest.mark.asyncio
    async def test_create_architectural_plan_no_complex_issues(self, coordinator):
        """Test _create_architectural_plan with no complex issues."""
        coordinator.agents = [Mock(spec=SubAgent)]

        issues = [
            Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Error"),
        ]

        plan = await coordinator._create_architectural_plan(issues)
        assert plan["strategy"] == "simple_fixes"

    def test_enrich_architectural_plan(self, coordinator):
        """Test _enrich_architectural_plan adds issue metadata."""
        plan = {"strategy": "test"}
        issues = [
            Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Error", id="issue-1"),
            Issue(type=IssueType.DEAD_CODE, severity=Priority.MEDIUM, message="Dead", id="issue-2"),
        ]

        enriched = coordinator._enrich_architectural_plan(plan, issues)

        assert "all_issues" in enriched
        assert len(enriched["all_issues"]) == 2
        assert "issue_types" in enriched
        assert IssueType.TYPE_ERROR.value in enriched["issue_types"]
        assert IssueType.DEAD_CODE.value in enriched["issue_types"]


class TestAgentCoordinatorProactiveMode:
    """Tests for proactive mode handling."""

    @pytest.mark.asyncio
    async def test_handle_issues_proactively_disabled(self, coordinator):
        """Test handle_issues_proactively when disabled."""
        coordinator.proactive_mode = False

        with patch.object(coordinator, "handle_issues", new_callable=AsyncMock) as mock_handle:
            mock_handle.return_value = FixResult(success=True, confidence=0.9)
            result = await coordinator.handle_issues_proactively([])

        mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_issues_proactively_empty_issues(self, coordinator):
        """Test handle_issues_proactively with empty issues."""
        coordinator.proactive_mode = True

        result = await coordinator.handle_issues_proactively([])
        assert result.success is True

    def test_prioritize_issues_by_plan(self, coordinator):
        """Test _prioritize_issues_by_plan prioritizes correctly."""
        issues = [
            Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="Complex"),
            Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Error"),
            Issue(type=IssueType.DEAD_CODE, severity=Priority.MEDIUM, message="Dead"),
        ]

        plan = {"strategy": "external_specialist_guided"}

        grouped = coordinator._prioritize_issues_by_plan(issues, plan)
        assert len(grouped) == 2
        assert any(g[0].type == IssueType.COMPLEXITY for g in grouped if g)

    def test_should_use_architect_for_group(self, coordinator):
        """Test _should_use_architect_for_group logic."""
        issues = [
            Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="Complex"),
        ]
        plan = {"strategy": "external_specialist_guided"}

        assert coordinator._should_use_architect_for_group(issues, plan) is True

        plan = {"strategy": "other"}
        issues = [
            Issue(type=IssueType.COMPLEXITY, severity=Priority.HIGH, message="Complex"),
        ]
        assert coordinator._should_use_architect_for_group(issues, plan) is True

        issues = [
            Issue(type=IssueType.TYPE_ERROR, severity=Priority.HIGH, message="Error"),
        ]
        plan = {"strategy": "other"}
        assert coordinator._should_use_architect_for_group(issues, plan) is False

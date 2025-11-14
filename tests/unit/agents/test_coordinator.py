"""Unit tests for AgentCoordinator.

Tests agent coordination, issue handling, agent selection,
and collaborative fixing workflows.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
    SubAgent,
)
from crackerjack.agents.coordinator import AgentCoordinator, ISSUE_TYPE_TO_AGENTS


@pytest.mark.unit
class TestIssueTypeToAgentsMapping:
    """Test issue type to agent mapping."""

    def test_mapping_contains_all_issue_types(self):
        """Test mapping covers all common issue types."""
        assert IssueType.FORMATTING in ISSUE_TYPE_TO_AGENTS
        assert IssueType.SECURITY in ISSUE_TYPE_TO_AGENTS
        assert IssueType.COMPLEXITY in ISSUE_TYPE_TO_AGENTS
        assert IssueType.TEST_FAILURE in ISSUE_TYPE_TO_AGENTS
        assert IssueType.DRY_VIOLATION in ISSUE_TYPE_TO_AGENTS

    def test_formatting_maps_to_formatting_agent(self):
        """Test formatting issues map to FormattingAgent."""
        agents = ISSUE_TYPE_TO_AGENTS[IssueType.FORMATTING]

        assert "FormattingAgent" in agents

    def test_security_maps_to_security_agent(self):
        """Test security issues map to SecurityAgent."""
        agents = ISSUE_TYPE_TO_AGENTS[IssueType.SECURITY]

        assert "SecurityAgent" in agents

    def test_complexity_maps_to_refactoring_agent(self):
        """Test complexity issues map to RefactoringAgent."""
        agents = ISSUE_TYPE_TO_AGENTS[IssueType.COMPLEXITY]

        assert "RefactoringAgent" in agents

    def test_test_failure_maps_to_test_agents(self):
        """Test test failures map to test specialist agents."""
        agents = ISSUE_TYPE_TO_AGENTS[IssueType.TEST_FAILURE]

        assert "TestSpecialistAgent" in agents or "TestCreationAgent" in agents

    def test_dry_violation_maps_to_dry_agent(self):
        """Test DRY violations map to DRYAgent."""
        agents = ISSUE_TYPE_TO_AGENTS[IssueType.DRY_VIOLATION]

        assert "DRYAgent" in agents


@pytest.mark.unit
class TestAgentCoordinatorInitialization:
    """Test AgentCoordinator initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_coordinator_initialization(self, context):
        """Test coordinator initializes with context."""
        with patch("crackerjack.agents.coordinator.get_logger"):
            with patch("crackerjack.agents.coordinator.get_agent_tracker"):
                with patch("crackerjack.agents.coordinator.get_ai_agent_debugger"):
                    coordinator = AgentCoordinator(context)

                    assert coordinator.context == context
                    assert coordinator.agents == []
                    assert coordinator._issue_cache == {}
                    assert coordinator._collaboration_threshold == 0.7
                    assert coordinator.proactive_mode is True

    def test_coordinator_with_cache(self, context):
        """Test coordinator initialization with custom cache."""
        mock_cache = Mock()

        with patch("crackerjack.agents.coordinator.get_logger"):
            with patch("crackerjack.agents.coordinator.get_agent_tracker"):
                with patch("crackerjack.agents.coordinator.get_ai_agent_debugger"):
                    coordinator = AgentCoordinator(context, cache=mock_cache)

                    assert coordinator.cache == mock_cache

    def test_coordinator_creates_cache_if_none(self, context):
        """Test coordinator creates cache if none provided."""
        with patch("crackerjack.agents.coordinator.get_logger"):
            with patch("crackerjack.agents.coordinator.get_agent_tracker"):
                with patch("crackerjack.agents.coordinator.get_ai_agent_debugger"):
                    with patch("crackerjack.agents.coordinator.CrackerjackCache") as mock_cache_cls:
                        coordinator = AgentCoordinator(context)

                        mock_cache_cls.assert_called_once()


@pytest.mark.unit
class TestAgentCoordinatorAgentManagement:
    """Test agent initialization and management."""

    class MockAgent(SubAgent):
        """Mock agent for testing."""

        def __init__(self, context, name="MockAgent"):
            super().__init__(context)
            self.name = name

        async def can_handle(self, issue: Issue) -> float:
            return 0.8

        async def analyze_and_fix(self, issue: Issue) -> FixResult:
            return FixResult(success=True, confidence=0.8)

        def get_supported_types(self) -> set[IssueType]:
            return {IssueType.FORMATTING}

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    @pytest.fixture
    def coordinator(self, context):
        """Create coordinator with mocked dependencies."""
        with patch("crackerjack.agents.coordinator.get_logger"):
            with patch("crackerjack.agents.coordinator.get_agent_tracker") as mock_tracker:
                with patch("crackerjack.agents.coordinator.get_ai_agent_debugger") as mock_debugger:
                    mock_tracker.return_value = Mock()
                    mock_debugger.return_value = Mock()
                    return AgentCoordinator(context, cache=Mock())

    def test_initialize_agents(self, coordinator):
        """Test initializing agents from registry."""
        with patch("crackerjack.agents.coordinator.agent_registry") as mock_registry:
            mock_agent1 = self.MockAgent(coordinator.context, "Agent1")
            mock_agent2 = self.MockAgent(coordinator.context, "Agent2")
            mock_registry.create_all.return_value = [mock_agent1, mock_agent2]

            coordinator.initialize_agents()

            assert len(coordinator.agents) == 2
            assert coordinator.agents[0].name == "Agent1"
            assert coordinator.agents[1].name == "Agent2"
            coordinator.tracker.register_agents.assert_called_once()
            coordinator.tracker.set_coordinator_status.assert_called_with("active")

    def test_initialize_agents_logs_activity(self, coordinator):
        """Test agent initialization logs to debugger."""
        with patch("crackerjack.agents.coordinator.agent_registry") as mock_registry:
            mock_agent = self.MockAgent(coordinator.context)
            mock_registry.create_all.return_value = [mock_agent]

            coordinator.initialize_agents()

            coordinator.debugger.log_agent_activity.assert_called()
            call_args = coordinator.debugger.log_agent_activity.call_args
            assert call_args[1]["agent_name"] == "coordinator"
            assert call_args[1]["activity"] == "agents_initialized"


@pytest.mark.unit
@pytest.mark.asyncio
class TestAgentCoordinatorIssueHandling:
    """Test issue handling and routing."""

    class FormattingAgent(SubAgent):
        """Mock formatting agent."""

        async def can_handle(self, issue: Issue) -> float:
            return 0.9 if issue.type == IssueType.FORMATTING else 0.0

        async def analyze_and_fix(self, issue: Issue) -> FixResult:
            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=["Formatted code"],
                files_modified=["file.py"],
            )

        def get_supported_types(self) -> set[IssueType]:
            return {IssueType.FORMATTING}

    class SecurityAgent(SubAgent):
        """Mock security agent."""

        async def can_handle(self, issue: Issue) -> float:
            return 0.95 if issue.type == IssueType.SECURITY else 0.0

        async def analyze_and_fix(self, issue: Issue) -> FixResult:
            return FixResult(
                success=True,
                confidence=0.95,
                fixes_applied=["Fixed security issue"],
                files_modified=["secure.py"],
            )

        def get_supported_types(self) -> set[IssueType]:
            return {IssueType.SECURITY}

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context."""
        return AgentContext(project_path=tmp_path)

    @pytest.fixture
    def coordinator(self, context):
        """Create coordinator with mocked dependencies."""
        with patch("crackerjack.agents.coordinator.get_logger"):
            with patch("crackerjack.agents.coordinator.get_agent_tracker") as mock_tracker:
                with patch("crackerjack.agents.coordinator.get_ai_agent_debugger") as mock_debugger:
                    mock_tracker.return_value = Mock()
                    mock_debugger.return_value = Mock()
                    coordinator = AgentCoordinator(context, cache=Mock())
                    # Add mock agents
                    coordinator.agents = [
                        self.FormattingAgent(context),
                        self.SecurityAgent(context),
                    ]
                    return coordinator

    async def test_handle_empty_issues(self, coordinator):
        """Test handling empty issue list."""
        result = await coordinator.handle_issues([])

        assert result.success is True
        assert result.confidence == 1.0

    async def test_handle_single_formatting_issue(self, coordinator):
        """Test handling single formatting issue."""
        issue = Issue(
            id="fmt-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Code not formatted",
        )

        result = await coordinator.handle_issues([issue])

        assert result.success is True
        assert len(result.fixes_applied) > 0
        assert "Formatted code" in result.fixes_applied

    async def test_handle_single_security_issue(self, coordinator):
        """Test handling single security issue."""
        issue = Issue(
            id="sec-001",
            type=IssueType.SECURITY,
            severity=Priority.CRITICAL,
            message="SQL injection vulnerability",
        )

        result = await coordinator.handle_issues([issue])

        assert result.success is True
        assert len(result.fixes_applied) > 0
        assert "Fixed security issue" in result.fixes_applied

    async def test_handle_multiple_issues_of_same_type(self, coordinator):
        """Test handling multiple issues of same type."""
        issues = [
            Issue(
                id="fmt-001",
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message="Issue 1",
            ),
            Issue(
                id="fmt-002",
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message="Issue 2",
            ),
        ]

        result = await coordinator.handle_issues(issues)

        assert result.success is True
        # Should have applied fixes for both issues
        assert len(result.fixes_applied) >= 2

    async def test_handle_multiple_issues_of_different_types(self, coordinator):
        """Test handling issues of different types in parallel."""
        issues = [
            Issue(
                id="fmt-001",
                type=IssueType.FORMATTING,
                severity=Priority.LOW,
                message="Formatting issue",
            ),
            Issue(
                id="sec-001",
                type=IssueType.SECURITY,
                severity=Priority.CRITICAL,
                message="Security issue",
            ),
        ]

        result = await coordinator.handle_issues(issues)

        assert result.success is True
        # Should have fixes from both agent types
        assert len(result.fixes_applied) >= 2
        assert any("Formatted" in fix for fix in result.fixes_applied)
        assert any("security" in fix.lower() for fix in result.fixes_applied)

    async def test_handle_issues_initializes_agents_if_needed(self, context):
        """Test handle_issues initializes agents if not already done."""
        with patch("crackerjack.agents.coordinator.get_logger"):
            with patch("crackerjack.agents.coordinator.get_agent_tracker"):
                with patch("crackerjack.agents.coordinator.get_ai_agent_debugger"):
                    coordinator = AgentCoordinator(context, cache=Mock())
                    assert coordinator.agents == []

                    with patch.object(coordinator, "initialize_agents") as mock_init:
                        issue = Issue(
                            id="test-001",
                            type=IssueType.FORMATTING,
                            severity=Priority.LOW,
                            message="Test",
                        )
                        await coordinator.handle_issues([issue])

                        mock_init.assert_called_once()

    async def test_handle_issues_with_unsupported_type(self, coordinator):
        """Test handling issue with no supporting agents."""
        # Create an issue type that no agent supports
        issue = Issue(
            id="unknown-001",
            type=IssueType.DEAD_CODE,  # No agent supports this in our mocks
            severity=Priority.LOW,
            message="Dead code detected",
        )

        result = await coordinator.handle_issues([issue])

        # Should still return a result, but with failure indicated
        assert result.success is False
        assert len(result.remaining_issues) > 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestAgentCoordinatorIssueGrouping:
    """Test issue grouping and routing logic."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context."""
        return AgentContext(project_path=tmp_path)

    @pytest.fixture
    def coordinator(self, context):
        """Create coordinator."""
        with patch("crackerjack.agents.coordinator.get_logger"):
            with patch("crackerjack.agents.coordinator.get_agent_tracker"):
                with patch("crackerjack.agents.coordinator.get_ai_agent_debugger"):
                    return AgentCoordinator(context, cache=Mock())

    def test_group_issues_by_type(self, coordinator):
        """Test grouping issues by type."""
        issues = [
            Issue(id="1", type=IssueType.FORMATTING, severity=Priority.LOW, message="A"),
            Issue(id="2", type=IssueType.FORMATTING, severity=Priority.LOW, message="B"),
            Issue(id="3", type=IssueType.SECURITY, severity=Priority.HIGH, message="C"),
            Issue(id="4", type=IssueType.COMPLEXITY, severity=Priority.MEDIUM, message="D"),
        ]

        grouped = coordinator._group_issues_by_type(issues)

        assert IssueType.FORMATTING in grouped
        assert len(grouped[IssueType.FORMATTING]) == 2
        assert IssueType.SECURITY in grouped
        assert len(grouped[IssueType.SECURITY]) == 1
        assert IssueType.COMPLEXITY in grouped
        assert len(grouped[IssueType.COMPLEXITY]) == 1

    def test_group_issues_empty_list(self, coordinator):
        """Test grouping empty issue list."""
        grouped = coordinator._group_issues_by_type([])

        assert grouped == {}


@pytest.mark.unit
@pytest.mark.asyncio
class TestAgentCoordinatorAgentSelection:
    """Test agent selection logic."""

    class HighConfidenceAgent(SubAgent):
        """Agent with high confidence."""

        async def can_handle(self, issue: Issue) -> float:
            return 0.95

        async def analyze_and_fix(self, issue: Issue) -> FixResult:
            return FixResult(success=True, confidence=0.95)

        def get_supported_types(self) -> set[IssueType]:
            return {IssueType.FORMATTING}

    class LowConfidenceAgent(SubAgent):
        """Agent with low confidence."""

        async def can_handle(self, issue: Issue) -> float:
            return 0.3

        async def analyze_and_fix(self, issue: Issue) -> FixResult:
            return FixResult(success=True, confidence=0.3)

        def get_supported_types(self) -> set[IssueType]:
            return {IssueType.FORMATTING}

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context."""
        return AgentContext(project_path=tmp_path)

    @pytest.fixture
    def coordinator(self, context):
        """Create coordinator with test agents."""
        with patch("crackerjack.agents.coordinator.get_logger"):
            with patch("crackerjack.agents.coordinator.get_agent_tracker"):
                with patch("crackerjack.agents.coordinator.get_ai_agent_debugger"):
                    coordinator = AgentCoordinator(context, cache=Mock())
                    coordinator.agents = [
                        self.HighConfidenceAgent(context),
                        self.LowConfidenceAgent(context),
                    ]
                    return coordinator

    async def test_find_best_specialist_selects_highest_confidence(self, coordinator):
        """Test selecting agent with highest confidence."""
        issue = Issue(
            id="test-001",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Test",
        )

        agents = [coordinator.agents[0], coordinator.agents[1]]
        best = await coordinator._find_best_specialist(agents, issue)

        # Should select HighConfidenceAgent (0.95) over LowConfidenceAgent (0.3)
        assert isinstance(best, self.HighConfidenceAgent)


@pytest.mark.unit
class TestAgentCoordinatorConstants:
    """Test coordinator constants and configuration."""

    def test_collaboration_threshold_default(self, tmp_path):
        """Test default collaboration threshold."""
        context = AgentContext(project_path=tmp_path)

        with patch("crackerjack.agents.coordinator.get_logger"):
            with patch("crackerjack.agents.coordinator.get_agent_tracker"):
                with patch("crackerjack.agents.coordinator.get_ai_agent_debugger"):
                    coordinator = AgentCoordinator(context)

                    assert coordinator._collaboration_threshold == 0.7

    def test_proactive_mode_enabled_by_default(self, tmp_path):
        """Test proactive mode is enabled by default."""
        context = AgentContext(project_path=tmp_path)

        with patch("crackerjack.agents.coordinator.get_logger"):
            with patch("crackerjack.agents.coordinator.get_agent_tracker"):
                with patch("crackerjack.agents.coordinator.get_ai_agent_debugger"):
                    coordinator = AgentCoordinator(context)

                    assert coordinator.proactive_mode is True

"""Unit tests for EnhancedProactiveAgent.

Tests external agent consultation, result combination,
and enhanced proactive capabilities with Claude Code bridge.
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.enhanced_proactive_agent import (
    EnhancedProactiveAgent,
    enhance_agent_with_claude_code_bridge,
)


# Create a concrete test implementation since EnhancedProactiveAgent is abstract
class TestEnhancedProactiveAgentImpl(EnhancedProactiveAgent):
    """Concrete implementation for testing."""

    async def can_handle(self, issue: Issue) -> float:
        """Test implementation for can_handle."""
        return 0.5  # Default confidence

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Simple test implementation."""
        return FixResult(
            success=True,
            confidence=0.7,
            fixes_applied=["Internal fix applied"],
        )

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.COMPLEXITY}


@pytest.mark.unit
class TestEnhancedProactiveAgentInitialization:
    """Test EnhancedProactiveAgent initialization."""

    @pytest.fixture
    def context(self, tmp_path):
        """Create agent context for testing."""
        return AgentContext(project_path=tmp_path)

    def test_initialization(self, context):
        """Test EnhancedProactiveAgent initializes correctly."""
        with patch("crackerjack.agents.enhanced_proactive_agent.ClaudeCodeBridge"):
            agent = TestEnhancedProactiveAgentImpl(context)

            assert agent.context == context
            assert agent._external_consultation_enabled is True
            assert hasattr(agent, "claude_bridge")

    def test_enable_external_consultation(self, context):
        """Test enabling/disabling external consultation."""
        with patch("crackerjack.agents.enhanced_proactive_agent.ClaudeCodeBridge"):
            agent = TestEnhancedProactiveAgentImpl(context)

            # Initially enabled
            assert agent._external_consultation_enabled is True

            # Disable
            agent.enable_external_consultation(False)
            assert agent._external_consultation_enabled is False

            # Re-enable
            agent.enable_external_consultation(True)
            assert agent._external_consultation_enabled is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestEnhancedProactiveAgentExecution:
    """Test enhanced execution with external consultation."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create agent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.enhanced_proactive_agent.ClaudeCodeBridge"):
            return TestEnhancedProactiveAgentImpl(context)

    async def test_execute_with_plan_no_consultation_needed(self, agent):
        """Test execution when external consultation not needed."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test issue",
        )
        plan = {"strategy": "internal_pattern_based"}

        internal_result = FixResult(success=True, confidence=0.9)

        with patch.object(agent, "_execute_internal_fix", return_value=internal_result):
            with patch.object(agent, "_should_consult_external_agents", return_value=False):
                result = await agent._execute_with_plan(issue, plan)

                assert result == internal_result

    async def test_execute_with_plan_with_consultation(self, agent):
        """Test execution with external consultation."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Complex issue",
        )
        plan = {"strategy": "external_specialist_guided"}

        internal_result = FixResult(success=True, confidence=0.5)
        consultations = [{"status": "success", "recommendations": ["External advice"]}]
        enhanced_result = FixResult(success=True, confidence=0.85)

        with patch.object(agent, "_execute_internal_fix", return_value=internal_result):
            with patch.object(agent, "_should_consult_external_agents", return_value=True):
                with patch.object(agent, "_consult_external_agents", return_value=consultations):
                    with patch.object(
                        agent,
                        "_combine_internal_and_external_results",
                        return_value=enhanced_result,
                    ):
                        result = await agent._execute_with_plan(issue, plan)

                        assert result == enhanced_result

    async def test_execute_internal_fix(self, agent):
        """Test executing internal fix."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test issue",
        )
        plan = {"strategy": "internal"}

        result = await agent._execute_internal_fix(issue, plan)

        # Should call the agent's analyze_and_fix
        assert result.success is True
        assert "Internal fix" in result.fixes_applied[0]


@pytest.mark.unit
class TestEnhancedProactiveAgentConsultationDecision:
    """Test decision logic for external consultation."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create agent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.enhanced_proactive_agent.ClaudeCodeBridge"):
            return TestEnhancedProactiveAgentImpl(context)

    def test_should_consult_disabled(self, agent):
        """Test that consultation is skipped when disabled."""
        agent.enable_external_consultation(False)

        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test",
        )
        internal_result = FixResult(success=False, confidence=0.3)
        plan = {}

        result = agent._should_consult_external_agents(issue, internal_result, plan)

        assert result is False

    def test_should_consult_low_confidence(self, agent):
        """Test consultation for low confidence internal result."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test",
        )
        internal_result = FixResult(success=True, confidence=0.3)
        plan = {}

        agent.claude_bridge.should_consult_external_agent = Mock(return_value=True)

        result = agent._should_consult_external_agents(issue, internal_result, plan)

        assert result is True

    def test_should_consult_external_strategy(self, agent):
        """Test consultation when plan specifies external strategy."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test",
        )
        internal_result = FixResult(success=True, confidence=0.9)
        plan = {"strategy": "external_specialist_guided"}

        agent.claude_bridge.should_consult_external_agent = Mock(return_value=False)

        result = agent._should_consult_external_agents(issue, internal_result, plan)

        assert result is True

    def test_should_consult_internal_failure(self, agent):
        """Test consultation when internal fix fails."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test",
        )
        internal_result = FixResult(success=False, confidence=0.0)
        plan = {}

        agent.claude_bridge.should_consult_external_agent = Mock(return_value=False)

        result = agent._should_consult_external_agents(issue, internal_result, plan)

        assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
class TestEnhancedProactiveAgentExternalConsultation:
    """Test external agent consultation."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create agent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.enhanced_proactive_agent.ClaudeCodeBridge"):
            return TestEnhancedProactiveAgentImpl(context)

    async def test_consult_external_agents_success(self, agent):
        """Test successful external agent consultation."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test",
        )
        plan = {}

        agent.claude_bridge.get_recommended_external_agents = Mock(
            return_value=["architect", "python-pro"]
        )
        agent.claude_bridge.verify_agent_availability = Mock(return_value=True)
        agent.claude_bridge.consult_external_agent = AsyncMock(
            return_value={"status": "success", "recommendations": ["Advice"]}
        )

        consultations = await agent._consult_external_agents(issue, plan)

        assert len(consultations) == 2
        assert all(c["status"] == "success" for c in consultations)

    async def test_consult_external_agents_unavailable(self, agent):
        """Test consultation when agents unavailable."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test",
        )
        plan = {}

        agent.claude_bridge.get_recommended_external_agents = Mock(
            return_value=["architect"]
        )
        agent.claude_bridge.verify_agent_availability = Mock(return_value=False)

        consultations = await agent._consult_external_agents(issue, plan)

        assert len(consultations) == 0

    async def test_consult_external_agents_limited(self, agent):
        """Test consultation limits to top 2 agents."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.HIGH,
            message="Test",
        )
        plan = {}

        agent.claude_bridge.get_recommended_external_agents = Mock(
            return_value=["agent1", "agent2", "agent3", "agent4"]
        )
        agent.claude_bridge.verify_agent_availability = Mock(return_value=True)
        agent.claude_bridge.consult_external_agent = AsyncMock(
            return_value={"status": "success"}
        )

        consultations = await agent._consult_external_agents(issue, plan)

        # Should only consult top 2
        assert len(consultations) == 2


@pytest.mark.unit
class TestEnhancedProactiveAgentResultCombination:
    """Test combining internal and external results."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create agent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.enhanced_proactive_agent.ClaudeCodeBridge"):
            return TestEnhancedProactiveAgentImpl(context)

    def test_combine_results_no_consultations(self, agent):
        """Test combining when no external consultations."""
        internal_result = FixResult(success=True, confidence=0.7)
        consultations = []

        result = agent._combine_internal_and_external_results(
            internal_result, consultations
        )

        assert result == internal_result

    def test_combine_results_with_consultations(self, agent):
        """Test combining with external consultations."""
        internal_result = FixResult(
            success=True,
            confidence=0.6,
            recommendations=["Internal rec"],
        )
        consultations = [
            {"status": "success", "recommendations": ["External rec 1"]},
            {"status": "success", "recommendations": ["External rec 2"]},
        ]

        enhanced_result = FixResult(
            success=True,
            confidence=0.85,
            recommendations=["Combined rec"],
        )

        agent.claude_bridge.create_enhanced_fix_result = Mock(
            return_value=enhanced_result
        )

        result = agent._combine_internal_and_external_results(
            internal_result, consultations
        )

        # Should have consultation metadata
        assert "Enhanced with consultation" in result.recommendations[0]
        assert "2 Claude Code agents" in result.recommendations[0]


@pytest.mark.unit
@pytest.mark.asyncio
class TestEnhancedProactiveAgentPlanning:
    """Test planning with external capabilities."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create agent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.enhanced_proactive_agent.ClaudeCodeBridge"):
            return TestEnhancedProactiveAgentImpl(context)

    async def test_plan_before_action_external_strategy(self, agent):
        """Test planning that suggests external consultation."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.CRITICAL,
            message="Very complex issue",
        )

        agent.claude_bridge.should_consult_external_agent = Mock(return_value=True)

        plan = await agent.plan_before_action(issue)

        assert plan["strategy"] == "external_specialist_guided"
        assert "external_guidance" in plan["patterns"]

    async def test_plan_before_action_internal_strategy(self, agent):
        """Test planning that uses internal strategy."""
        issue = Issue(
            id="test-001",
            type=IssueType.COMPLEXITY,
            severity=Priority.LOW,
            message="Simple issue",
        )

        agent.claude_bridge.should_consult_external_agent = Mock(return_value=False)

        plan = await agent.plan_before_action(issue)

        assert plan["strategy"] == "internal_pattern_based"
        assert "standard_patterns" in plan["patterns"]


@pytest.mark.unit
class TestEnhanceAgentWithClaudeCodeBridge:
    """Test agent enhancement function."""

    def test_enhance_agent_with_bridge(self, tmp_path):
        """Test enhancing an agent class with Claude Code bridge."""
        from crackerjack.agents.proactive_agent import ProactiveAgent

        # Create a simple test agent
        class SimpleAgent(ProactiveAgent):
            def get_supported_types(self):
                return {IssueType.COMPLEXITY}

            async def analyze_and_fix(self, issue):
                return FixResult(success=True, confidence=0.8)

        context = AgentContext(project_path=tmp_path)

        with patch("crackerjack.agents.enhanced_proactive_agent.ClaudeCodeBridge"):
            # Enhance the agent
            EnhancedClass = enhance_agent_with_claude_code_bridge(SimpleAgent)

            # Create instance
            enhanced_agent = EnhancedClass(context)

            # Should have both capabilities
            assert hasattr(enhanced_agent, "claude_bridge")
            assert hasattr(enhanced_agent, "_external_consultation_enabled")
            assert "Enhanced" in EnhancedClass.__name__


@pytest.mark.unit
class TestEnhancedProactiveAgentIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def agent(self, tmp_path):
        """Create agent instance."""
        context = AgentContext(project_path=tmp_path)
        with patch("crackerjack.agents.enhanced_proactive_agent.ClaudeCodeBridge"):
            return TestEnhancedProactiveAgentImpl(context)

    def test_agent_maintains_consultation_state(self, agent):
        """Test that agent maintains consultation state across operations."""
        # Initially enabled
        assert agent._external_consultation_enabled is True

        # Disable and verify state persists
        agent.enable_external_consultation(False)
        assert agent._external_consultation_enabled is False

        # State should remain across multiple checks
        assert agent._external_consultation_enabled is False

    def test_agent_bridge_integration(self, agent):
        """Test that Claude Code bridge is properly integrated."""
        assert hasattr(agent, "claude_bridge")
        assert agent.claude_bridge is not None

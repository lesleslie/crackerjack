"""Tests for EnhancedAgentCoordinator with Claude Code integration."""

from unittest.mock import Mock, AsyncMock, patch
import typing as t

import pytest

from crackerjack.agents.enhanced_coordinator import EnhancedAgentCoordinator
from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.agents.base import AgentContext, Issue, FixResult, IssueType


def _make_context() -> Mock:
    context = Mock(spec=AgentContext)
    context.project_path = "/test/project"
    context.project_root = "/test/project"
    context.config = {}
    return context


class TestEnhancedAgentCoordinator:
    """Tests for EnhancedAgentCoordinator."""

    def test_enhanced_coordinator_initialization(self):
        """Test EnhancedAgentCoordinator initialization."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context)

        assert isinstance(coordinator, AgentCoordinator)
        assert hasattr(coordinator, 'claude_bridge')
        assert coordinator.external_agents_enabled is True
        assert hasattr(coordinator, '_external_consultation_stats')

    def test_enhanced_coordinator_with_external_agents_disabled(self):
        """Test EnhancedAgentCoordinator with external agents disabled."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context, enable_external_agents=False)

        assert coordinator.external_agents_enabled is False

    def test_enhanced_coordinator_enable_external_agents(self):
        """Test enabling/disabling external agents."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context)

        # Disable external agents
        coordinator.enable_external_agents(False)
        assert coordinator.external_agents_enabled is False

        # Enable external agents
        coordinator.enable_external_agents(True)
        assert coordinator.external_agents_enabled is True

    def test_enhanced_coordinator_get_stats(self):
        """Test getting external consultation statistics."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context)

        stats = coordinator.get_external_consultation_stats()
        assert isinstance(stats, dict)
        assert 'consultations_requested' in stats
        assert 'consultations_successful' in stats
        assert 'improvements_achieved' in stats

    @pytest.mark.asyncio
    async def test_enhanced_coordinator_handle_issues_no_issues(self):
        """Test handling empty issue list."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context)

        result = await coordinator.handle_issues_proactively([])

        assert result.success is True
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_enhanced_coordinator_handle_issues_external_disabled(self):
        """Test handling issues with external agents disabled."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context, enable_external_agents=False)

        issues = [Mock(spec=Issue)]

        # Mock the parent method
        mock_parent_result = FixResult(success=True, confidence=0.8)
        with patch.object(AgentCoordinator, 'handle_issues_proactively', new_callable=AsyncMock) as mock_parent:
            mock_parent.return_value = mock_parent_result

            result = await coordinator.handle_issues_proactively(issues)

        # Should call parent method when external agents disabled
        mock_parent.assert_called_once_with(issues)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_enhanced_coordinator_handle_issues_with_external_agents(self):
        """Test handling issues with external agents enabled."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context, enable_external_agents=True)

        issues = [Mock(spec=Issue), Mock(spec=Issue)]

        # Mock the various methods
        mock_strategic_consultations = {"strategy": "test"}
        mock_architectural_plan = {"plan": "test_plan"}
        mock_overall_result = FixResult(success=True, confidence=0.9)
        mock_validated_result = FixResult(success=True, confidence=0.95)

        with patch.object(coordinator, '_pre_consult_for_strategy', new_callable=AsyncMock) as mock_pre_consult, \
             patch.object(coordinator, '_create_enhanced_architectural_plan', new_callable=AsyncMock) as mock_create_plan, \
             patch.object(coordinator, '_apply_enhanced_fixes_with_plan', new_callable=AsyncMock) as mock_apply_fixes, \
             patch.object(coordinator, '_validate_with_external_agents', new_callable=AsyncMock) as mock_validate, \
             patch.object(coordinator, '_update_consultation_stats') as mock_update_stats:

            mock_pre_consult.return_value = mock_strategic_consultations
            mock_create_plan.return_value = mock_architectural_plan
            mock_apply_fixes.return_value = mock_overall_result
            mock_validate.return_value = mock_validated_result

            result = await coordinator.handle_issues_proactively(issues)

        # Verify all methods were called
        mock_pre_consult.assert_called_once_with(issues)
        mock_create_plan.assert_called_once_with(issues, mock_strategic_consultations)
        mock_apply_fixes.assert_called_once_with(issues, mock_architectural_plan, mock_strategic_consultations)
        mock_validate.assert_called_once_with(mock_overall_result, mock_architectural_plan)
        mock_update_stats.assert_called_once_with(mock_strategic_consultations, mock_validated_result)

        assert result.success is True
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_enhanced_coordinator_pre_consult_for_strategy(self):
        """Test pre-consultation for strategy."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context)

        issues = [Mock(spec=Issue)]

        coordinator.claude_bridge.should_consult_external_agent = Mock(
            return_value=True
        )
        coordinator.claude_bridge.verify_agent_availability = Mock(return_value=True)

        mock_consultation_result = {"status": "success", "recommendations": ["test"]}
        with patch.object(
            coordinator.claude_bridge,
            "consult_external_agent",
            new_callable=AsyncMock,
        ) as mock_consult:
            mock_consult.return_value = mock_consultation_result

            result = await coordinator._pre_consult_for_strategy(issues)

        mock_consult.assert_called_once()
        assert result["crackerjack_architect_guidance"] == mock_consultation_result

    def test_enhanced_coordinator_update_stats(self):
        """Test updating consultation statistics."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context)

        strategic_consultations = {
            "crackerjack_architect_guidance": "guidance",
            "specialist_recommendations": {"refactoring": "recommendation"}
        }

        validated_result = FixResult(success=True, confidence=0.9)

        # Initial stats should be zero
        initial_stats = coordinator.get_external_consultation_stats()
        assert initial_stats["consultations_requested"] == 0

        # Update stats
        coordinator._update_consultation_stats(strategic_consultations, validated_result)

        # Stats should be updated
        updated_stats = coordinator.get_external_consultation_stats()
        assert updated_stats["consultations_requested"] == 0
        assert updated_stats["consultations_successful"] == 0
        assert updated_stats["improvements_achieved"] == 1

    @pytest.mark.asyncio
    async def test_enhanced_coordinator_with_no_agents(self):
        """Test coordinator behavior when no agents are available."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context)

        # Ensure no agents
        coordinator.agents = []
        coordinator.claude_bridge.should_consult_external_agent = Mock(
            return_value=False
        )

        issue = Mock(spec=Issue)
        issue.type = IssueType.TEST_FAILURE
        issues = [issue]

        # Mock initialization
        with patch.object(coordinator, 'initialize_agents'):
            result = await coordinator.handle_issues_proactively(issues)

        assert result.success is False
        assert result.confidence == 1.0
        assert "No agents for test_failure issues" in result.remaining_issues

    def test_enhanced_coordinator_context_attributes(self):
        """Test that coordinator properly stores context."""
        context = _make_context()

        coordinator = EnhancedAgentCoordinator(context)

        assert coordinator.context == context
        assert coordinator.context.project_root == "/test/project"

    @pytest.mark.asyncio
    async def test_enhanced_coordinator_error_handling(self):
        """Test error handling in enhanced coordinator."""
        context = _make_context()
        coordinator = EnhancedAgentCoordinator(context)

        issues = [Mock(spec=Issue)]

        # Mock pre-consult to raise an exception
        with patch.object(coordinator, '_pre_consult_for_strategy', new_callable=AsyncMock) as mock_pre_consult, \
             patch.object(AgentCoordinator, 'handle_issues_proactively', new_callable=AsyncMock) as mock_parent:

            mock_pre_consult.side_effect = Exception("Consultation failed")
            mock_parent.return_value = FixResult(success=False, confidence=0.5)

            result = await coordinator.handle_issues_proactively(issues)

        # Should fall back to parent method on error
        mock_parent.assert_called_once_with(issues)
        assert result.success is False


def test_enhanced_coordinator_inheritance():
    """Test that EnhancedAgentCoordinator properly inherits from AgentCoordinator."""
    context = Mock(spec=AgentContext)
    coordinator = EnhancedAgentCoordinator(context)

    # Should have all parent attributes
    assert hasattr(coordinator, 'agents')
    assert hasattr(coordinator, 'initialize_agents')
    assert hasattr(coordinator, 'handle_issues_proactively')

    # Should have enhanced attributes
    assert hasattr(coordinator, 'claude_bridge')
    assert hasattr(coordinator, 'external_agents_enabled')
    assert hasattr(coordinator, 'enable_external_agents')

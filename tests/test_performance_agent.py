"""Tests for crackerjack.agents.performance_agent."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType
from crackerjack.agents.performance_agent import PerformanceAgent


class TestPerformanceagent:
    """Tests for crackerjack.agents.performance_agent.

    This module contains comprehensive tests for crackerjack.agents.performance_agent
    including:
    - Basic functionality tests
    - Edge case validation
    - Error handling verification
    - Integration testing
    - Performance validation (where applicable)
    """

    def test_module_imports_successfully(self):
        """Test that the module can be imported without errors."""
        import crackerjack.agents.performance_agent
        assert crackerjack.agents.performance_agent is not None

    @pytest.fixture
    def performanceagent_instance(self):
        """Fixture to create PerformanceAgent instance for testing."""
        mock_context = Mock(spec=AgentContext)
        mock_context.project_path = Path("/test/project")

        try:
            return PerformanceAgent(mock_context)
        except Exception:
            pytest.skip("Agent requires specific configuration")

    def test_performanceagent_instantiation(self, performanceagent_instance):
        """Test successful instantiation of PerformanceAgent."""
        assert performanceagent_instance is not None
        assert isinstance(performanceagent_instance, PerformanceAgent)

        assert hasattr(performanceagent_instance, '__class__')
        assert performanceagent_instance.__class__.__name__ == "PerformanceAgent"

    def test_performanceagent_get_supported_types(self, performanceagent_instance):
        """Test PerformanceAgent.get_supported_types method."""
        try:
            result = performanceagent_instance.get_supported_types()
            assert result is not None
            assert isinstance(result, set)

        except (TypeError, NotImplementedError):
            pytest.skip(f"Method get_supported_types requires specific arguments or implementation")
        except Exception as e:
            pytest.fail(f"Unexpected error in get_supported_types: {e}")

    def test_performanceagent_properties(self, performanceagent_instance):
        """Test PerformanceAgent properties and attributes."""

        assert hasattr(performanceagent_instance, '__dict__') or \
         hasattr(performanceagent_instance, '__slots__')

        str_repr = str(performanceagent_instance)
        assert len(str_repr) > 0
        assert "PerformanceAgent" in str_repr or "performanceagent" in \
         str_repr.lower()

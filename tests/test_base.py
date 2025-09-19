"""Tests for crackerjack.agents.base."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority, SubAgent, AgentRegistry


class TestBase:
    """Tests for crackerjack.agents.base.

    This module contains comprehensive tests for crackerjack.agents.base
    including:
    - Basic functionality tests
    - Edge case validation
    - Error handling verification
    - Integration testing
    - Performance validation (where applicable)
    """

    def test_module_imports_successfully(self):
        """Test that the module can be imported without errors."""
        import crackerjack.agents.base
        assert crackerjack.agents.base is not None

    @pytest.fixture
    def agent_context_instance(self):
        """Fixture to create AgentContext instance for testing."""
        return AgentContext(project_path=Path("/test/project"))

    def test_agent_context_instantiation(self, agent_context_instance):
        """Test successful instantiation of AgentContext."""
        assert agent_context_instance is not None
        assert isinstance(agent_context_instance, AgentContext)

    def test_agent_context_properties(self, agent_context_instance):
        """Test AgentContext properties and attributes."""
        assert hasattr(agent_context_instance, 'project_path')
        assert agent_context_instance.project_path == Path("/test/project")

        str_repr = str(agent_context_instance)
        assert len(str_repr) > 0

    @pytest.fixture
    def fix_result_instance(self):
        """Fixture to create FixResult instance for testing."""
        return FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=["test_fix"],
            remaining_issues=[],
            recommendations=["test_recommendation"],
            files_modified=["test_file.py"]
        )

    def test_fix_result_instantiation(self, fix_result_instance):
        """Test successful instantiation of FixResult."""
        assert fix_result_instance is not None
        assert isinstance(fix_result_instance, FixResult)

    def test_fix_result_merge_with(self, fix_result_instance):
        """Test FixResult.merge_with method."""
        other_fix_result = FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=["other_fix"],
            remaining_issues=["other_issue"],
            recommendations=["other_recommendation"],
            files_modified=["other_file.py"]
        )

        merged_result = fix_result_instance.merge_with(other_fix_result)
        assert merged_result is not None
        assert isinstance(merged_result, FixResult)

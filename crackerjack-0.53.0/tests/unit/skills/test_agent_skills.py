"""Tests for agent skills system."""

from __future__ import annotations

import typing as t
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import Issue, IssueType, SubAgent
from crackerjack.skills.agent_skills import (
    SkillCategory,
    SkillMetadata,
    SkillExecutionResult,
    AgentSkill,
)


class TestSkillCategory:
    """Tests for SkillCategory enum."""

    def test_category_values(self):
        """Test that all category values are correct."""
        assert SkillCategory.CODE_QUALITY.value == "code_quality"
        assert SkillCategory.TESTING.value == "testing"
        assert SkillCategory.SECURITY.value == "security"
        assert SkillCategory.PERFORMANCE.value == "performance"
        assert SkillCategory.DOCUMENTATION.value == "documentation"
        assert SkillCategory.ARCHITECTURE.value == "architecture"
        assert SkillCategory.SEMANTIC.value == "semantic"
        assert SkillCategory.PROACTIVE.value == "proactive"


class TestSkillMetadata:
    """Tests for SkillMetadata dataclass."""

    def test_create_skill_metadata(self):
        """Test creating SkillMetadata."""
        metadata = SkillMetadata(
            name="refactoring_skill",
            description="Refactors code for better structure",
            category=SkillCategory.CODE_QUALITY,
            supported_types={IssueType.COMPLEXITY, IssueType.CODE_SMELL},
            confidence_threshold=0.8,
            avg_confidence=0.85,
            execution_count=10,
            success_rate=0.95,
            tags={"refactoring", "optimization"},
        )

        assert metadata.name == "refactoring_skill"
        assert metadata.category == SkillCategory.CODE_QUALITY
        assert len(metadata.supported_types) == 2
        assert metadata.confidence_threshold == 0.8
        assert metadata.execution_count == 10
        assert metadata.success_rate == 0.95
        assert "refactoring" in metadata.tags

    def test_default_values(self):
        """Test default values for SkillMetadata."""
        metadata = SkillMetadata(
            name="test_skill",
            description="Test skill",
            category=SkillCategory.TESTING,
            supported_types={IssueType.TEST_FAILURE},
        )

        assert metadata.confidence_threshold == 0.7
        assert metadata.avg_confidence == 0.8
        assert metadata.execution_count == 0
        assert metadata.success_rate == 1.0
        assert len(metadata.tags) == 0

    def test_to_dict(self):
        """Test converting metadata to dictionary."""
        metadata = SkillMetadata(
            name="security_skill",
            description="Security analysis",
            category=SkillCategory.SECURITY,
            supported_types={IssueType.SECURITY},
            tags={"security", "sast"},
        )

        result = metadata.to_dict()

        assert isinstance(result, dict)
        assert result["name"] == "security_skill"
        assert result["category"] == "security"
        assert isinstance(result["supported_types"], list)
        assert "security" in result["tags"]
        assert result["confidence_threshold"] == 0.7


class TestSkillExecutionResult:
    """Tests for SkillExecutionResult dataclass."""

    def test_create_execution_result(self):
        """Test creating SkillExecutionResult."""
        result = SkillExecutionResult(
            skill_name="test_skill",
            success=True,
            confidence=0.9,
            issues_handled=5,
            fixes_applied=["fix1", "fix2"],
            recommendations=["rec1"],
            files_modified=["file1.py"],
            execution_time_ms=150,
        )

        assert result.skill_name == "test_skill"
        assert result.success is True
        assert result.confidence == 0.9
        assert result.issues_handled == 5
        assert len(result.fixes_applied) == 2
        assert len(result.recommendations) == 1
        assert result.execution_time_ms == 150

    def test_to_dict(self):
        """Test converting execution result to dictionary."""
        result = SkillExecutionResult(
            skill_name="formatting_skill",
            success=True,
            confidence=0.95,
            issues_handled=3,
            fixes_applied=["formatted_code"],
            recommendations=[],
            files_modified=["test.py"],
            execution_time_ms=50,
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["skill_name"] == "formatting_skill"
        assert result_dict["success"] is True
        assert result_dict["confidence"] == 0.95
        assert isinstance(result_dict["fixes_applied"], list)
        assert isinstance(result_dict["files_modified"], list)


class TestAgentSkill:
    """Tests for AgentSkill class."""

    @pytest.fixture
    def mock_agent(self):
        """Create a mock agent."""
        agent = MagicMock(spec=SubAgent)
        agent.can_handle = AsyncMock(return_value=0.85)
        agent.execute = AsyncMock(
            return_value={
                "success": True,
                "fixes_applied": ["fix1"],
                "recommendations": [],
            },
        )
        return agent

    @pytest.fixture
    def sample_metadata(self):
        """Create sample skill metadata."""
        return SkillMetadata(
            name="test_refactoring",
            description="Test refactoring skill",
            category=SkillCategory.CODE_QUALITY,
            supported_types={IssueType.COMPLEXITY, IssueType.CODE_SMELL},
            confidence_threshold=0.7,
        )

    @pytest.fixture
    def agent_skill(self, mock_agent, sample_metadata):
        """Create an AgentSkill instance."""
        return AgentSkill(agent=mock_agent, metadata=sample_metadata)

    def test_initialization(self, agent_skill):
        """Test AgentSkill initialization."""
        assert agent_skill.skill_id.startswith("skill_")
        assert len(agent_skill.skill_id) == len("skill_") + 8
        assert agent_skill.metadata.name == "test_refactoring"

    @pytest.mark.asyncio
    async def test_can_handle_supported_type(self, agent_skill):
        """Test can_handle with supported issue type."""
        issue = Issue(
            type=IssueType.COMPLEXITY,
            message="High complexity detected",
            file_path="test.py",
            line_number=10,
        )

        confidence = await agent_skill.can_handle(issue)

        assert confidence == 0.85
        agent_skill.agent.can_handle.assert_called_once_with(issue)

    @pytest.mark.asyncio
    async def test_can_handle_unsupported_type(self, agent_skill):
        """Test can_handle with unsupported issue type."""
        issue = Issue(
            type=IssueType.SECURITY,
            message="Security issue",
            file_path="test.py",
            line_number=10,
        )

        confidence = await agent_skill.can_handle(issue)

        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_can_handle_below_threshold(self, agent_skill):
        """Test can_handle when agent confidence is below threshold."""
        agent_skill.agent.can_handle = AsyncMock(return_value=0.5)

        issue = Issue(
            type=IssueType.COMPLEXITY,
            message="High complexity",
            file_path="test.py",
            line_number=10,
        )

        confidence = await agent_skill.can_handle(issue)

        assert confidence == 0.0

    @pytest.mark.asyncio
    async def test_execute_success(self, agent_skill):
        """Test successful skill execution."""
        issue = Issue(
            type=IssueType.CODE_SMELL,
            message="Code smell detected",
            file_path="test.py",
            line_number=5,
        )

        agent_skill.agent.execute = AsyncMock(
            return_value={
                "success": True,
                "fixes_applied": ["refactored_code"],
                "recommendations": ["add_tests"],
                "files_modified": ["test.py"],
            },
        )

        result = await agent_skill.execute(issue)

        assert result.success is True
        assert result.issues_handled == 1
        assert "refactored_code" in result.fixes_applied
        assert "add_tests" in result.recommendations
        assert "test.py" in result.files_modified

    @pytest.mark.asyncio
    async def test_execute_failure(self, agent_skill):
        """Test failed skill execution."""
        issue = Issue(
            type=IssueType.TEST_FAILURE,
            message="Test failed",
            file_path="test.py",
            line_number=1,
        )

        agent_skill.agent.execute = AsyncMock(
            return_value={
                "success": False,
                "fixes_applied": [],
                "recommendations": ["manual_review_required"],
                "files_modified": [],
            },
        )

        result = await agent_skill.execute(issue)

        assert result.success is False
        assert len(result.fixes_applied) == 0
        assert "manual_review_required" in result.recommendations

    @pytest.mark.asyncio
    async def test_execute_with_multiple_issues(self, agent_skill):
        """Test executing skill with multiple issues."""
        issues = [
            Issue(
                type=IssueType.COMPLEXITY,
                message="Complex function",
                file_path="test.py",
                line_number=10,
            ),
            Issue(
                type=IssueType.CODE_SMELL,
                message="Code smell",
                file_path="test.py",
                line_number=20,
            ),
        ]

        agent_skill.agent.execute = AsyncMock(
            return_value={
                "success": True,
                "fixes_applied": ["refactored"],
                "recommendations": [],
                "files_modified": ["test.py"],
            },
        )

        result = await agent_skill.execute(issues)

        assert result.issues_handled == 2


class TestAgentSkillIntegration:
    """Integration tests for agent skills."""

    @pytest.fixture
    def real_agent(self):
        """Create a real (non-mocked) agent for integration tests."""
        # This would be an actual SubAgent implementation
        # For now, we'll use a mock that behaves realistically
        agent = MagicMock(spec=SubAgent)
        agent.can_handle = AsyncMock(return_value=0.9)
        agent.execute = AsyncMock(
            return_value={
                "success": True,
                "fixes_applied": ["fix1"],
                "recommendations": [],
                "files_modified": ["test.py"],
            },
        )
        return agent

    def test_skill_workflow(self, real_agent):
        """Test complete skill workflow."""
        import asyncio

        metadata = SkillMetadata(
            name="integration_test_skill",
            description="Integration test",
            category=SkillCategory.TESTING,
            supported_types={IssueType.TEST_FAILURE},
        )

        skill = AgentSkill(agent=real_agent, metadata=metadata)

        async def run_workflow():
            issue = Issue(
                type=IssueType.TEST_FAILURE,
                message="Test failed",
                file_path="test.py",
                line_number=10,
            )

            # Check if can handle
            confidence = await skill.can_handle(issue)
            assert confidence > 0

            # Execute
            result = await skill.execute(issue)
            assert result.success

            # Verify metadata was updated
            assert skill.metadata.execution_count > 0

        asyncio.run(run_workflow())

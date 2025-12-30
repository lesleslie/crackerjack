"""
Tests for Agent Skills System (Option 1)

Tests the AgentSkill, AgentSkillRegistry, and related functionality.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock

from crackerjack.agents.base import (
    AgentContext,
    Issue,
    IssueType,
    Priority,
    SubAgent,
)
from crackerjack.skills.agent_skills import (
    AgentSkill,
    AgentSkillRegistry,
    SkillCategory,
    SkillExecutionResult,
    SkillMetadata,
)


# Fixtures


@pytest.fixture
def temp_project_path(tmp_path: Path) -> Path:
    """Create a temporary project path."""
    return tmp_path / "test_project"


@pytest.fixture
def agent_context(temp_project_path: Path) -> AgentContext:
    """Create an AgentContext for testing."""
    return AgentContext(
        project_path=temp_project_path,
        temp_dir=temp_project_path / "temp",
        subprocess_timeout=10,
    )


@pytest.fixture
def sample_issue() -> Issue:
    """Create a sample issue for testing."""
    return Issue(
        type=IssueType.COMPLEXITY,
        severity=Priority.HIGH,
        message="Function complexity too high",
        file_path="test.py",
        line_number=42,
        details=["Complexity score: 25"],
    )


@pytest.fixture
def mock_agent() -> SubAgent:
    """Create a mock agent for testing."""
    agent = MagicMock(spec=SubAgent)
    agent.name = "TestAgent"

    # Mock can_handle
    agent.can_handle = AsyncMock(return_value=0.9)

    # Mock analyze_and_fix
    from crackerjack.agents.base import FixResult

    agent.analyze_and_fix = AsyncMock(
        return_value=FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=["Simplified complex function"],
            recommendations=["Consider breaking into smaller functions"],
            files_modified=["test.py"],
        )
    )

    # Mock get_supported_types
    agent.get_supported_types = Mock(
        return_value={IssueType.COMPLEXITY, IssueType.DEAD_CODE}
    )

    return agent


# Tests


def test_skill_metadata_creation() -> None:
    """Test SkillMetadata creation and serialization."""
    metadata = SkillMetadata(
        name="RefactoringAgent",
        description="Handles code refactoring tasks",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY, IssueType.DEAD_CODE},
        confidence_threshold=0.7,
        tags={"refactor", "complexity"},
    )

    assert metadata.name == "RefactoringAgent"
    assert metadata.category == SkillCategory.CODE_QUALITY
    assert len(metadata.supported_types) == 2

    # Test to_dict conversion
    data = metadata.to_dict()
    assert data["name"] == "RefactoringAgent"
    assert data["category"] == "code_quality"
    assert len(data["supported_types"]) == 2


def test_skill_execution_result_creation() -> None:
    """Test SkillExecutionResult creation and serialization."""
    result = SkillExecutionResult(
        skill_name="TestSkill",
        success=True,
        confidence=0.9,
        issues_handled=1,
        fixes_applied=["Fix 1", "Fix 2"],
        recommendations=["Recommendation 1"],
        files_modified=["file1.py"],
        execution_time_ms=150,
    )

    assert result.skill_name == "TestSkill"
    assert result.success is True
    assert result.issues_handled == 1

    # Test to_dict conversion
    data = result.to_dict()
    assert data["skill_name"] == "TestSkill"
    assert data["success"] is True
    assert len(data["fixes_applied"]) == 2


@pytest.mark.asyncio
async def test_agent_skill_can_handle(
    mock_agent: SubAgent,
    sample_issue: Issue,
) -> None:
    """Test AgentSkill.can_handle method."""
    metadata = SkillMetadata(
        name="TestAgent",
        description="Test agent",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
        confidence_threshold=0.7,
    )

    skill = AgentSkill(mock_agent, metadata)

    # Test handleable issue
    confidence = await skill.can_handle(sample_issue)
    assert confidence == 0.9

    # Test non-handleable issue
    other_issue = Issue(
        type=IssueType.SECURITY,
        severity=Priority.MEDIUM,
        message="Security issue",
    )
    confidence = await skill.can_handle(other_issue)
    assert confidence == 0.0  # Not in supported types


@pytest.mark.asyncio
async def test_agent_skill_execute(
    mock_agent: SubAgent,
    sample_issue: Issue,
) -> None:
    """Test AgentSkill.execute method."""
    metadata = SkillMetadata(
        name="TestAgent",
        description="Test agent",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )

    skill = AgentSkill(mock_agent, metadata)

    result = await skill.execute(sample_issue)

    assert result.success is True
    assert result.confidence == 0.9
    assert result.issues_handled == 1
    assert len(result.fixes_applied) == 1
    assert "Simplified complex function" in result.fixes_applied
    assert result.execution_time_ms >= 0

    # Verify metadata was updated
    assert metadata.execution_count == 1
    assert metadata.success_rate > 0


@pytest.mark.asyncio
async def test_agent_skill_execute_with_timeout(
    mock_agent: SubAgent,
    sample_issue: Issue,
) -> None:
    """Test AgentSkill.execute with timeout."""
    metadata = SkillMetadata(
        name="TestAgent",
        description="Test agent",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )

    skill = AgentSkill(mock_agent, metadata)

    result = await skill.execute(sample_issue, timeout=5)

    assert result.success is True


@pytest.mark.asyncio
async def test_agent_skill_batch_execute(
    mock_agent: SubAgent,
    sample_issue: Issue,
) -> None:
    """Test AgentSkill.batch_execute method."""
    metadata = SkillMetadata(
        name="TestAgent",
        description="Test agent",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY, IssueType.DEAD_CODE},
    )

    skill = AgentSkill(mock_agent, metadata)

    issues = [
        sample_issue,
        Issue(
            type=IssueType.DEAD_CODE,
            severity=Priority.LOW,
            message="Dead code found",
        ),
    ]

    results = await skill.batch_execute(issues)

    assert len(results) == 2
    assert all(isinstance(r, SkillExecutionResult) for r in results)


def test_agent_skill_registry_initialization() -> None:
    """Test AgentSkillRegistry initialization."""
    registry = AgentSkillRegistry()

    assert len(registry._skills) == 0
    assert len(registry._category_index) == len(SkillCategory)
    assert len(registry._type_index) == len(IssueType)


def test_agent_skill_registry_register(
    agent_context: AgentContext,
    mock_agent: SubAgent,
) -> None:
    """Test registering a skill in the registry."""
    registry = AgentSkillRegistry()

    metadata = SkillMetadata(
        name="TestAgent",
        description="Test agent",
        category=SkillCategory.CODE_QUALITY,
        supported_types={IssueType.COMPLEXITY},
    )

    skill = AgentSkill(mock_agent, metadata)
    registry.register(skill)

    # Verify skill was registered
    assert len(registry._skills) == 0  # skill_id not generated yet

    # Test register_agent method
    mock_agent_class = Mock()
    mock_agent_class.return_value = mock_agent

    skill = registry.register_agent(mock_agent_class, agent_context)

    assert skill is not None
    assert len(registry._skills) > 0


def test_agent_skill_registry_get_by_category(
    agent_context: AgentContext,
) -> None:
    """Test getting skills by category."""
    registry = AgentSkillRegistry()

    # Register a few mock skills
    for i in range(3):
        mock_agent = MagicMock(spec=SubAgent)
        mock_agent.name = f"Agent{i}"
        mock_agent.can_handle = AsyncMock(return_value=0.8)
        mock_agent.analyze_and_fix = AsyncMock()
        mock_agent.get_supported_types = Mock(return_value=set())

        registry.register_agent(
            type(mock_agent),
            agent_context,
            metadata=SkillMetadata(
                name=f"Agent{i}",
                description=f"Test agent {i}",
                category=SkillCategory.CODE_QUALITY,
                supported_types=set(),
            ),
        )

    skills = registry.get_skills_by_category(SkillCategory.CODE_QUALITY)

    assert len(skills) == 3


def test_agent_skill_registry_get_by_type(
    agent_context: AgentContext,
) -> None:
    """Test getting skills by issue type."""
    registry = AgentSkillRegistry()

    mock_agent = MagicMock(spec=SubAgent)
    mock_agent.name = "ComplexityAgent"
    mock_agent.can_handle = AsyncMock(return_value=0.9)
    mock_agent.analyze_and_fix = AsyncMock()
    mock_agent.get_supported_types = Mock(
        return_value={IssueType.COMPLEXITY}
    )

    registry.register_agent(
        type(mock_agent),
        agent_context,
        metadata=SkillMetadata(
            name="ComplexityAgent",
            description="Handles complexity",
            category=SkillCategory.CODE_QUALITY,
            supported_types={IssueType.COMPLEXITY},
        ),
    )

    skills = registry.get_skills_for_type(IssueType.COMPLEXITY)

    assert len(skills) == 1
    assert skills[0].metadata.name == "ComplexityAgent"


@pytest.mark.asyncio
async def test_agent_skill_registry_find_best_skill(
    agent_context: AgentContext,
    sample_issue: Issue,
) -> None:
    """Test finding the best skill for an issue."""
    registry = AgentSkillRegistry()

    # Create two agents with different confidence scores
    high_conf_agent = MagicMock(spec=SubAgent)
    high_conf_agent.name = "HighConfidenceAgent"
    high_conf_agent.can_handle = AsyncMock(return_value=0.95)
    high_conf_agent.analyze_and_fix = AsyncMock()
    high_conf_agent.get_supported_types = Mock(
        return_value={IssueType.COMPLEXITY}
    )

    low_conf_agent = MagicMock(spec=SubAgent)
    low_conf_agent.name = "LowConfidenceAgent"
    low_conf_agent.can_handle = AsyncMock(return_value=0.6)
    low_conf_agent.analyze_and_fix = AsyncMock()
    low_conf_agent.get_supported_types = Mock(
        return_value={IssueType.COMPLEXITY}
    )

    registry.register_agent(
        type(high_conf_agent),
        agent_context,
        metadata=SkillMetadata(
            name="HighConfidenceAgent",
            description="High confidence",
            category=SkillCategory.CODE_QUALITY,
            supported_types={IssueType.COMPLEXITY},
            confidence_threshold=0.5,
        ),
    )

    registry.register_agent(
        type(low_conf_agent),
        agent_context,
        metadata=SkillMetadata(
            name="LowConfidenceAgent",
            description="Low confidence",
            category=SkillCategory.CODE_QUALITY,
            supported_types={IssueType.COMPLEXITY},
            confidence_threshold=0.5,
        ),
    )

    best_skill = await registry.find_best_skill(sample_issue)

    assert best_skill is not None
    assert best_skill.metadata.name == "HighConfidenceAgent"


def test_agent_skill_registry_statistics(
    agent_context: AgentContext,
) -> None:
    """Test getting registry statistics."""
    registry = AgentSkillRegistry()

    # Register a few skills
    for i in range(3):
        mock_agent = MagicMock(spec=SubAgent)
        mock_agent.name = f"Agent{i}"
        mock_agent.can_handle = AsyncMock(return_value=0.8)
        mock_agent.analyze_and_fix = AsyncMock()
        mock_agent.get_supported_types = Mock(return_value=set())

        registry.register_agent(
            type(mock_agent),
            agent_context,
            metadata=SkillMetadata(
                name=f"Agent{i}",
                description=f"Test agent {i}",
                category=SkillCategory.CODE_QUALITY,
                supported_types=set(),
            ),
        )

    stats = registry.get_statistics()

    assert stats["total_skills"] == 3
    assert "skills_by_category" in stats
    assert "skills_by_type" in stats

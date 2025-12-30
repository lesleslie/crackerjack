"""
Tests for MCP Skills System (Option 2)

Tests the MCPSkill, MCPSkillRegistry, and tool grouping functionality.
"""

import pytest

from crackerjack.skills.mcp_skills import (
    MCPSkill,
    MCPSkillRegistry,
    MCP_SKILL_GROUPS,
    SkillDomain,
    ToolReference,
)


# Tests


def test_tool_reference_creation() -> None:
    """Test ToolReference creation and serialization."""
    tool = ToolReference(
        name="test_tool",
        description="A test tool",
        required_params=["param1", "param2"],
        optional_params=["param3"],
    )

    assert tool.name == "test_tool"
    assert len(tool.required_params) == 2
    assert len(tool.optional_params) == 1

    # Test to_dict conversion
    data = tool.to_dict()
    assert data["name"] == "test_tool"
    assert len(data["required_params"]) == 2


def test_mcp_skill_creation() -> None:
    """Test MCPSkill creation and management."""
    skill = MCPSkill(
        skill_id="test_skill",
        name="Test Skill",
        description="A test skill for grouping tools",
        domain=SkillDomain.EXECUTION,
        tags={"test", "example"},
        examples=["Example usage"],
    )

    assert skill.skill_id == "test_skill"
    assert skill.domain == SkillDomain.EXECUTION
    assert len(skill.tags) == 2
    assert len(skill.examples) == 1

    # Add tools
    skill.add_tool(
        tool_name="tool1",
        tool_description="First tool",
        required_params=["input"],
        optional_params=["optional"],
    )

    skill.add_tool(
        tool_name="tool2",
        tool_description="Second tool",
        required_params=[],
        optional_params=[],
    )

    assert len(skill.tools) == 2

    # Test to_dict conversion
    data = skill.to_dict()
    assert data["skill_id"] == "test_skill"
    assert data["domain"] == "execution"
    assert len(data["tools"]) == 2


def test_mcp_skill_registry_initialization() -> None:
    """Test MCPSkillRegistry initialization."""
    registry = MCPSkillRegistry()

    assert len(registry._skills) == 0
    assert len(registry._domain_index) == len(SkillDomain)
    assert len(registry._tool_index) == 0


def test_mcp_skill_registry_register() -> None:
    """Test registering a skill in the registry."""
    registry = MCPSkillRegistry()

    skill = MCPSkill(
        skill_id="test_skill",
        name="Test Skill",
        description="Test",
        domain=SkillDomain.EXECUTION,
    )

    skill.add_tool(
        tool_name="test_tool",
        tool_description="Test tool",
        required_params=[],
    )

    registry.register(skill)

    # Verify registration
    assert len(registry._skills) == 1
    assert "test_skill" in registry._skills
    assert "test_tool" in registry._tool_index


def test_mcp_skill_registry_register_skill_group() -> None:
    """Test registering a skill from dictionary."""
    registry = MCPSkillRegistry()

    skill_data = {
        "skill_id": "test_group",
        "name": "Test Group",
        "description": "A test skill group",
        "domain": "execution",
        "tags": ["test"],
        "tools": [
            {
                "name": "tool1",
                "description": "First tool",
                "required_params": ["param1"],
                "optional_params": [],
            },
        ],
    }

    skill = registry.register_skill_group(skill_data)

    assert skill is not None
    assert skill.skill_id == "test_group"
    assert len(skill.tools) == 1
    assert skill.tools[0].name == "tool1"


def test_mcp_skill_registry_get_by_domain() -> None:
    """Test getting skills by domain."""
    registry = MCPSkillRegistry()

    # Register skills in different domains
    for i in range(3):
        skill = MCPSkill(
            skill_id=f"skill_{i}",
            name=f"Skill {i}",
            description="Test",
            domain=SkillDomain.EXECUTION,
        )
        registry.register(skill)

    skills = registry.get_skills_by_domain(SkillDomain.EXECUTION)

    assert len(skills) == 3


def test_mcp_skill_registry_get_by_tool() -> None:
    """Test getting skill that contains a specific tool."""
    registry = MCPSkillRegistry()

    skill = MCPSkill(
        skill_id="test_skill",
        name="Test",
        description="Test",
        domain=SkillDomain.EXECUTION,
    )

    skill.add_tool(
        tool_name="specific_tool",
        tool_description="A specific tool",
        required_params=[],
    )

    registry.register(skill)

    found_skill = registry.get_skill_by_tool("specific_tool")

    assert found_skill is not None
    assert found_skill.skill_id == "test_skill"

    # Test non-existent tool
    not_found = registry.get_skill_by_tool("non_existent_tool")
    assert not_found is None


def test_mcp_skill_registry_search() -> None:
    """Test searching for skills."""
    registry = MCPSkillRegistry()

    # Register skills with different attributes
    skill1 = MCPSkill(
        skill_id="quality_skill",
        name="Quality Checks",
        description="Quality checking tools",
        domain=SkillDomain.EXECUTION,
        tags={"quality", "testing"},
    )
    skill1.add_tool("quality_tool", "Quality tool", [])

    skill2 = MCPSkill(
        skill_id="search_skill",
        name="Semantic Search",
        description="Search tools",
        domain=SkillDomain.SEMANTIC,
        tags={"search", "semantic"},
    )
    skill2.add_tool("search_tool", "Search tool", [])

    registry.register(skill1)
    registry.register(skill2)

    # Search by domain
    results = registry.search_skills("execution")
    assert len(results) >= 1

    # Search by tag
    results = registry.search_skills("semantic")
    assert len(results) >= 1

    # Search by tool name
    results = registry.search_skills("quality_tool")
    assert len(results) >= 1


def test_mcp_skill_registry_get_all_tools() -> None:
    """Test getting all tool names across all skills."""
    registry = MCPSkillRegistry()

    # Register skills with tools
    for i in range(3):
        skill = MCPSkill(
            skill_id=f"skill_{i}",
            name=f"Skill {i}",
            description="Test",
            domain=SkillDomain.EXECUTION,
        )
        skill.add_tool(f"tool_{i}", f"Tool {i}", [])
        registry.register(skill)

    all_tools = registry.get_all_tools()

    assert len(all_tools) == 3
    assert "tool_0" in all_tools
    assert "tool_1" in all_tools
    assert "tool_2" in all_tools


def test_mcp_skill_registry_statistics() -> None:
    """Test getting registry statistics."""
    registry = MCPSkillRegistry()

    # Register skills
    for i in range(3):
        skill = MCPSkill(
            skill_id=f"skill_{i}",
            name=f"Skill {i}",
            description="Test",
            domain=SkillDomain.EXECUTION,
        )
        skill.add_tool(f"tool_{i}", f"Tool {i}", [])
        registry.register(skill)

    stats = registry.get_statistics()

    assert stats["total_skills"] == 3
    assert stats["total_tools"] == 3
    assert stats["avg_tools_per_skill"] == 1.0


def test_predefined_mcp_skill_groups() -> None:
    """Test that predefined MCP skill groups are valid."""
    assert len(MCP_SKILL_GROUPS) > 0

    for skill_id, skill_data in MCP_SKILL_GROUPS.items():
        # Verify required fields
        assert "skill_id" in skill_data
        assert "name" in skill_data
        assert "description" in skill_data
        assert "domain" in skill_data
        assert "tools" in skill_data

        # Verify skill_id matches
        assert skill_data["skill_id"] == skill_id

        # Verify domain is valid
        domain = skill_data["domain"]
        assert domain in ["execution", "monitoring", "intelligence", "semantic", "proactive", "utility"]


def test_register_all_predefined_skills() -> None:
    """Test registering all predefined MCP skill groups."""
    registry = MCPSkillRegistry()

    for skill_data in MCP_SKILL_GROUPS.values():
        skill = registry.register_skill_group(skill_data)
        assert skill is not None

    # Verify all were registered
    stats = registry.get_statistics()
    assert stats["total_skills"] == len(MCP_SKILL_GROUPS)


def test_mcp_skill_categories() -> None:
    """Test that MCP skills are properly categorized."""
    registry = MCPSkillRegistry()

    # Register all predefined skills
    for skill_data in MCP_SKILL_GROUPS.values():
        registry.register_skill_group(skill_data)

    # Check execution domain
    execution_skills = registry.get_skills_by_domain(SkillDomain.EXECUTION)
    assert len(execution_skills) > 0

    # Check monitoring domain
    monitoring_skills = registry.get_skills_by_domain(SkillDomain.MONITORING)
    assert len(monitoring_skills) > 0

    # Check semantic domain
    semantic_skills = registry.get_skills_by_domain(SkillDomain.SEMANTIC)
    assert len(semantic_skills) > 0

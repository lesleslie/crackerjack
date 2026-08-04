"""Tests for ``crackerjack.mcp.tools.skill_tools``."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_search_mcp_skills_does_not_raise_typeerror() -> None:
    """_search_mcp_skills must not raise TypeError when calling search_skills."""
    from crackerjack.mcp.tools import skill_tools

    # Build a fake registry whose search_skills accepts **only** the known kwargs.
    fake_registry = MagicMock()
    fake_skill = MagicMock()
    fake_skill.to_dict.return_value = {"name": "x", "tags": [], "description": "x"}
    fake_registry.search_skills.return_value = [fake_skill]

    with patch.object(skill_tools, "_skill_registries", {"mcp_skills": fake_registry}):
        result = skill_tools._search_mcp_skills("query", "names")

    assert result == [{"name": "x", "tags": [], "description": "x"}]
    fake_registry.search_skills.assert_called_once_with(
        "query",
        search_tool_names=True,
        search_tags=False,
        search_descriptions=False,
    )

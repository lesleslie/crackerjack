"""Tests for ``crackerjack.mcp.tools.discover_tools``.

Pins the contract surfaced by Contract 5.5 in
``docs/architecture/MEMORY_ARCHITECTURE.md`` (the discover_tools
meta-tool is no longer missing).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from crackerjack.mcp.tools.discover_tools import (
    DEFERRED_TOOLS,
    TOOL_REGISTRY,
    register_discover_tools,
)


class TestToolRegistryShape:
    """The static registry must be well-formed before the meta-tool can ship."""

    def test_registry_has_at_least_one_tool(self):
        assert len(TOOL_REGISTRY) > 0

    def test_registry_values_have_required_keys(self):
        for name, meta in TOOL_REGISTRY.items():
            assert "group" in meta, f"{name} missing 'group'"
            assert "description" in meta, f"{name} missing 'description'"
            assert meta["group"], f"{name} has empty group"
            assert meta["description"], f"{name} has empty description"

    def test_registry_tool_names_are_unique(self):
        # Defensive — dict keys are unique by construction, but if
        # anyone ever switches to a list-of-dicts, this guards.
        assert len(TOOL_REGISTRY) == len(set(TOOL_REGISTRY))

    def test_deferred_tools_are_not_in_active_registry(self):
        """A tool cannot be both active and deferred."""
        for name in DEFERRED_TOOLS:
            assert name not in TOOL_REGISTRY, (
                f"{name} is in both TOOL_REGISTRY (active) and "
                f"DEFERRED_TOOLS — pick one"
            )


class TestDiscoverToolsMetaTool:
    """Behavioral contract of the discover_tools FastMCP tool."""

    @pytest.fixture
    def captured_tool(self):
        """Register discover_tools against a mock mcp_app and capture
        the registered function for direct invocation.
        """
        app = MagicMock()
        registered: list = []

        def tool_decorator():
            def wrap(fn):
                registered.append(fn)
                return fn

            return wrap

        app.tool = tool_decorator
        register_discover_tools(app)
        assert len(registered) == 1
        return registered[0]

    @pytest.mark.asyncio
    async def test_no_query_returns_full_registry(self, captured_tool):
        result = await captured_tool(query=None)
        assert result["status"] == "success"
        assert result["query"] is None
        assert result["matched_count"] == len(TOOL_REGISTRY)
        assert result["total_count"] == len(TOOL_REGISTRY)
        assert result["matched"][0]["name"] in TOOL_REGISTRY

    @pytest.mark.asyncio
    async def test_query_filters_by_name_substring(self, captured_tool):
        result = await captured_tool(query="search")
        # Only tools whose name or description contains "search"
        for tool in result["matched"]:
            t = tool["name"].lower() + tool["description"].lower()
            assert "search" in t

    @pytest.mark.asyncio
    async def test_query_filters_by_description_substring(self, captured_tool):
        # "workspace" matches the deferred set description; active
        # registry has no workspace tools, so matched should be 0.
        result = await captured_tool(query="workspace")
        assert result["matched_count"] == 0

    @pytest.mark.asyncio
    async def test_query_is_case_insensitive(self, captured_tool):
        lower = await captured_tool(query="search")
        upper = await captured_tool(query="SEARCH")
        assert lower["matched_count"] == upper["matched_count"]

    @pytest.mark.asyncio
    async def test_response_includes_groups_summary(self, captured_tool):
        result = await captured_tool(query=None)
        assert "groups" in result
        group_names = {g["name"] for g in result["groups"]}
        # At least one known group
        assert "execution_tools" in group_names
        assert "monitoring_tools" in group_names

    @pytest.mark.asyncio
    async def test_response_includes_deferred_set(self, captured_tool):
        result = await captured_tool(query=None)
        assert "deferred" in result
        assert result["deferred_count"] == len(DEFERRED_TOOLS)
        deferred_names = {d["name"] for d in result["deferred"]}
        # workspace_tools deferred per Contract 5.7
        assert "create_workspace" in deferred_names
        assert "remove_workspace" in deferred_names

    @pytest.mark.asyncio
    async def test_response_includes_self(self, captured_tool):
        """discover_tools itself must appear in the registry."""
        result = await captured_tool(query=None)
        names = {t["name"] for t in result["matched"]}
        assert "discover_tools" in names

    @pytest.mark.asyncio
    async def test_no_query_returns_matched_list_sorted(self, captured_tool):
        result = await captured_tool(query=None)
        names = [t["name"] for t in result["matched"]]
        assert names == sorted(names)


class TestRegistrationWiring:
    """The meta-tool must be wired into create_mcp_server."""

    def test_discover_tools_importable_from_tools_package(self):
        # Mirrors how server_core.py imports other register_* tools.
        from crackerjack.mcp.tools import (
            register_discover_tools as imported_fn,
        )

        assert imported_fn is register_discover_tools

    def test_server_core_imports_register_discover_tools(self):
        # Mechanical check that the wiring edit landed.
        server_core = (
            __import__("pathlib").Path(__file__).resolve()
            .parents[3]
            / "crackerjack"
            / "mcp"
            / "server_core.py"
        )
        source = server_core.read_text(encoding="utf-8")
        assert "register_discover_tools" in source

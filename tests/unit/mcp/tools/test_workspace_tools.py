"""Tests for ``crackerjack.mcp.tools.workspace_tools``.

The module's import pulls in ``crackerjack.mahavishnu.workspace.get_manager``
at module-load time. That sibling module is not part of this repo, so we
inject a stub ``crackerjack.mahavishnu.workspace`` into ``sys.modules``
before the import lands. Each tool handler is then exercised in isolation
by patching ``get_manager`` (the bound name the module imported) and
replacing it with an object whose async manager methods return
deterministic dicts/lists — which matches the wrappers' asyncio.run(...)
contract.
"""

from __future__ import annotations

import sys
import types
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.server import FastMCP

# ---------------------------------------------------------------------------
# Bootstrap: inject a stub `crackerjack.mahavishnu.workspace` so the import
# of workspace_tools succeeds. The stub provides a get_manager() factory
# which we replace per-test.
# ---------------------------------------------------------------------------

_STUB_MANAGER = AsyncMock(name="stub_workspace_manager")


def _install_workspace_stub() -> None:
    pkg = types.ModuleType("crackerjack.mahavishnu")
    pkg.__path__ = []  # mark as a package so submodule imports work
    workspace_mod = types.ModuleType("crackerjack.mahavishnu.workspace")
    workspace_mod.get_manager = MagicMock(name="get_manager")
    sys.modules.setdefault("crackerjack.mahavishnu", pkg)
    sys.modules["crackerjack.mahavishnu.workspace"] = workspace_mod


_install_workspace_stub()

# Import after stub is installed so `from ... import get_manager` resolves.
from crackerjack.mcp.tools import workspace_tools
from crackerjack.mcp.tools.workspace_tools import (
    create_workspace,
    get_workspace_info,
    list_workspaces,
    register_workspace_tools,
    remove_workspace,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def manager() -> AsyncMock:
    """Return an AsyncMock stand-in for the workspace manager.

    The four tool handlers always call:
        manager.create_workspace(...)
        manager.list_workspaces(...)
        manager.get_workspace_info(...)
        manager.remove_workspace(...)

    Each test wires up the appropriate ``return_value`` or ``side_effect``
    on this mock.
    """
    return AsyncMock(name="workspace_manager")


@pytest.fixture(autouse=True)
def _patched_get_manager(manager: AsyncMock) -> None:
    """Rebind ``workspace_tools.get_manager`` to return ``manager``."""
    with patch.object(workspace_tools, "get_manager", return_value=manager):
        yield


# ---------------------------------------------------------------------------
# create_workspace
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateWorkspace:
    def test_happy_path_returns_manager_result(self, manager: AsyncMock) -> None:
        manager.create_workspace = AsyncMock(
            return_value={"name": "ws1", "branch": "ws1", "repos": ["/r/a"]}
        )

        result = create_workspace(
            name="ws1",
            repos=["/r/a"],
            branch="ws1",
            create_branch=True,
        )

        assert result == {"name": "ws1", "branch": "ws1", "repos": ["/r/a"]}
        manager.create_workspace.assert_awaited_once_with(
            name="ws1",
            repos=["/r/a"],
            branch="ws1",
            create_branch=True,
        )

    def test_optional_fields_default_to_none_and_true(
        self, manager: AsyncMock
    ) -> None:
        manager.create_workspace = AsyncMock(
            return_value={"name": "ws2", "branch": "ws2", "repos": []}
        )

        result = create_workspace(name="ws2")

        assert result["name"] == "ws2"
        manager.create_workspace.assert_awaited_once_with(
            name="ws2",
            repos=None,
            branch=None,
            create_branch=True,
        )

    def test_empty_repos_list_propagates(self, manager: AsyncMock) -> None:
        manager.create_workspace = AsyncMock(
            return_value={"name": "ws3", "branch": "ws3", "repos": []}
        )

        result = create_workspace(name="ws3", repos=[])

        assert result["repos"] == []
        manager.create_workspace.assert_awaited_once_with(
            name="ws3",
            repos=[],
            branch=None,
            create_branch=True,
        )

    def test_manager_error_propagates(self, manager: AsyncMock) -> None:
        manager.create_workspace = AsyncMock(
            side_effect=RuntimeError("workspace exists")
        )

        with pytest.raises(RuntimeError, match="workspace exists"):
            create_workspace(name="dup")

    def test_pydantic_rejects_invalid_branch_type(self) -> None:
        # branch is typed str; validate_call must reject non-string.
        with pytest.raises(Exception):
            create_workspace(name="ws", branch=123)


# ---------------------------------------------------------------------------
# list_workspaces
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListWorkspaces:
    def test_returns_workspaces_payload(self, manager: AsyncMock) -> None:
        manager.list_workspaces = AsyncMock(
            return_value=[
                {"name": "a", "branch": "a"},
                {"name": "b", "branch": "b"},
            ]
        )

        result = list_workspaces(active_only=True)

        assert isinstance(result, list)
        assert len(result) == 2
        assert [w["name"] for w in result] == ["a", "b"]
        manager.list_workspaces.assert_awaited_once_with(active_only=True)

    def test_active_only_defaults_to_false(self, manager: AsyncMock) -> None:
        manager.list_workspaces = AsyncMock(return_value=[])

        result = list_workspaces()

        assert result == []
        manager.list_workspaces.assert_awaited_once_with(active_only=False)

    def test_empty_list_returns_empty_list(self, manager: AsyncMock) -> None:
        manager.list_workspaces = AsyncMock(return_value=[])

        result = list_workspaces(active_only=False)

        assert result == []

    def test_manager_error_propagates(self, manager: AsyncMock) -> None:
        manager.list_workspaces = AsyncMock(
            side_effect=ValueError("invalid filter")
        )

        with pytest.raises(ValueError, match="invalid filter"):
            list_workspaces(active_only=True)


# ---------------------------------------------------------------------------
# get_workspace_info
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetWorkspaceInfo:
    def test_returns_info_dict(self, manager: AsyncMock) -> None:
        info = {
            "name": "ws-x",
            "branch": "ws-x",
            "repos": ["/r/1", "/r/2"],
            "uncommitted": False,
        }
        manager.get_workspace_info = AsyncMock(return_value=info)

        result = get_workspace_info(name="ws-x")

        assert result == info
        manager.get_workspace_info.assert_awaited_once_with("ws-x")

    def test_empty_name_still_calls_manager(self, manager: AsyncMock) -> None:
        # The handler does not enforce a non-empty name; the manager does.
        # We only confirm the wrapper forwards whatever it gets.
        manager.get_workspace_info = AsyncMock(
            return_value={"name": "", "error": "not found"}
        )

        result = get_workspace_info(name="")

        assert result["name"] == ""
        manager.get_workspace_info.assert_awaited_once_with("")

    def test_manager_error_propagates(self, manager: AsyncMock) -> None:
        manager.get_workspace_info = AsyncMock(
            side_effect=KeyError("ws-missing")
        )

        with pytest.raises(KeyError, match="ws-missing"):
            get_workspace_info(name="ws-missing")

    def test_pydantic_requires_string_name(self) -> None:
        with pytest.raises(Exception):
            get_workspace_info(name=None)


# ---------------------------------------------------------------------------
# remove_workspace
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRemoveWorkspace:
    def test_returns_removal_result(self, manager: AsyncMock) -> None:
        manager.remove_workspace = AsyncMock(
            return_value={"name": "ws-del", "removed": True}
        )

        result = remove_workspace(name="ws-del")

        assert result == {"name": "ws-del", "removed": True}
        manager.remove_workspace.assert_awaited_once_with("ws-del", force=False)

    def test_force_true_is_forwarded(self, manager: AsyncMock) -> None:
        manager.remove_workspace = AsyncMock(
            return_value={"name": "ws-del", "removed": True, "forced": True}
        )

        result = remove_workspace(name="ws-del", force=True)

        assert result["forced"] is True
        manager.remove_workspace.assert_awaited_once_with("ws-del", force=True)

    def test_uncommitted_changes_error_propagates(
        self, manager: AsyncMock
    ) -> None:
        manager.remove_workspace = AsyncMock(
            side_effect=RuntimeError("uncommitted changes")
        )

        with pytest.raises(RuntimeError, match="uncommitted changes"):
            remove_workspace(name="ws-dirty", force=False)

    def test_force_overrides_uncommitted(self, manager: AsyncMock) -> None:
        # When force=True and the manager accepts it, no error.
        manager.remove_workspace = AsyncMock(
            return_value={"name": "ws-dirty", "removed": True, "forced": True}
        )

        result = remove_workspace(name="ws-dirty", force=True)

        assert result["removed"] is True
        manager.remove_workspace.assert_awaited_once_with("ws-dirty", force=True)


# ---------------------------------------------------------------------------
# register_workspace_tools
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRegisterWorkspaceTools:
    def test_registers_all_four_tools(self) -> None:
        app = FastMCP("test-app")

        register_workspace_tools(app)

        # FastMCP stores tools in a manager; check that exactly the four
        # workspace handlers were registered.
        tool_manager = app._tool_manager
        names = {name for name in tool_manager._tools}
        assert {
            "create_workspace",
            "list_workspaces",
            "get_workspace_info",
            "remove_workspace",
        } <= names

    def test_registration_is_idempotent(self) -> None:
        # Registering twice should not raise (FastMCP re-registration
        # overwrites / warns but the call itself succeeds).
        app = FastMCP("test-app-2")

        register_workspace_tools(app)
        register_workspace_tools(app)

        tool_manager = app._tool_manager
        names = {name for name in tool_manager._tools}
        assert "create_workspace" in names
        assert "remove_workspace" in names


# ---------------------------------------------------------------------------
# Module surface
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestModuleSurface:
    def test_module_level_mcp_is_fastmcp(self) -> None:
        assert isinstance(workspace_tools.mcp, FastMCP)
        assert workspace_tools.mcp.name == "crackerjack-workspace"

    def test_tool_decorators_attached(self) -> None:
        # Each tool function should have a FastMCP-internal __wrapped__ or
        # similar attribute proving it was registered with the module's MCP.
        # FastMCP stores tool metadata in mcp._tool_manager._tools keyed by
        # function name.
        names = set(workspace_tools.mcp._tool_manager._tools)
        assert {
            "create_workspace",
            "list_workspaces",
            "get_workspace_info",
            "remove_workspace",
        } <= names

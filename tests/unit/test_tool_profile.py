"""Crackerjack tool profile wiring tests."""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path("/Users/les/Projects/crackerjack")


def test_profiles_py_defines() -> None:
    """profiles.py must export a PROFILE_REGISTRATIONS dict."""
    profiles = REPO_ROOT / "crackerjack/mcp/tools/profiles.py"
    tree = ast.parse(profiles.read_text())
    found = False
    for node in ast.walk(tree):
        # Plain assignment: ``PROFILE_REGISTRATIONS = {...}``
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PROFILE_REGISTRATIONS"
            for t in node.targets
        ):
            found = True
            break
        # Annotated assignment: ``PROFILE_REGISTRATIONS: dict[...] = {...}``
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "PROFILE_REGISTRATIONS":
                found = True
                break
    assert found, "PROFILE_REGISTRATIONS not defined in profiles.py"


def test_server_core_uses_crackerjack_tool_profile_env_var() -> None:
    """server_core.py must reference CRACKERJACK_TOOL_PROFILE env var."""
    server_core = REPO_ROOT / "crackerjack/mcp/server_core.py"
    tree = ast.parse(server_core.read_text())
    found = any(
        isinstance(node, ast.Constant) and node.value == "CRACKERJACK_TOOL_PROFILE"
        for node in ast.walk(tree)
    )
    assert found, "CRACKERJACK_TOOL_PROFILE not referenced in server_core.py"


def test_discover_fn_wired() -> None:
    """server_core.py must pass discovery_fn=crackerjack_discovery to apply_tool_profile."""
    server_core = REPO_ROOT / "crackerjack/mcp/server_core.py"
    tree = ast.parse(server_core.read_text())
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (
                    kw.arg == "discovery_fn"
                    and isinstance(kw.value, ast.Name)
                    and kw.value.id == "crackerjack_discovery"
                ):
                    found = True
    assert found, (
        "_apply_tool_profile call must pass discovery_fn=crackerjack_discovery"
    )


@pytest.mark.asyncio
async def test_full_matches_golden_fixture() -> None:
    """FULL profile must register the same tool names as the captured fixture."""
    fixture = REPO_ROOT / "tests/fixtures/full/tool_names.json"
    expected = set(json.loads(fixture.read_text()))

    from crackerjack.mcp.server_core import create_mcp_server

    server = await create_mcp_server({"http_port": 8676, "http_host": "127.0.0.1"})
    assert server is not None
    actual = {t.name for t in await server.list_tools()}
    assert expected.issubset(actual), (
        f"FULL missing from fixture: {sorted(expected - actual)}; "
        f"unexpected extras: {sorted(actual - expected)}"
    )


@pytest.mark.asyncio
async def test_minimal_has_health_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """At MINIMAL: health probes must be registered; non-essential groups dropped."""
    monkeypatch.setenv("CRACKERJACK_TOOL_PROFILE", "minimal")
    from crackerjack.mcp.server_core import create_mcp_server

    server = await create_mcp_server({"http_port": 8676, "http_host": "127.0.0.1"})
    assert server is not None
    names = {t.name for t in await server.list_tools()}
    # Health probes must always be present
    assert {"get_liveness", "get_readiness", "health_check_service"}.issubset(names)
    # Non-essential groups must NOT be present
    assert "execute_crackerjack" not in names
    assert "run_crackerjack_stage" not in names
    # discover_tools is always registered by the W0 helper
    assert "discover_tools" in names


@pytest.mark.asyncio
async def test_standard_has_core_execution_utility_doc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At STANDARD: core/execution/utility/doc tools present; eventbridge/progress dropped."""
    monkeypatch.setenv("CRACKERJACK_TOOL_PROFILE", "standard")
    from crackerjack.mcp.server_core import create_mcp_server

    server = await create_mcp_server({"http_port": 8676, "http_host": "127.0.0.1"})
    assert server is not None
    names = {t.name for t in await server.list_tools()}
    # STANDARD tools present
    assert "execute_crackerjack" in names
    assert "run_crackerjack_stage" in names
    assert "clean_crackerjack" in names
    assert "crackerjack_doc_frontmatter_validate" in names
    # FULL-only tools dropped
    assert "publish_to_eventbridge" not in names
    assert "session_management" not in names
    assert "pycharm_health" not in names
    assert "search_semantic" not in names
    # discover_tools is always registered by the W0 helper
    assert "discover_tools" in names

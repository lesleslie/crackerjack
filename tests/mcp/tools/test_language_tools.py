from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest import mock

import pytest
from fastmcp import FastMCP


async def _register() -> tuple[FastMCP, dict]:
    """Register language_tools and return (mcp_app, tools_dict)."""
    mcp_app = FastMCP("test")
    from crackerjack.mcp.tools.language_tools import register_language_tools

    register_language_tools(mcp_app)
    tools = {t.name: t for t in await mcp_app.list_tools()}
    return mcp_app, tools


def test_register_language_tools_registers_three_tools() -> None:
    async def _go() -> dict:
        _, tools = await _register()
        return tools

    tools = asyncio.run(_go())
    assert "swift_bump_version" in tools
    assert "swift_list_hooks" in tools
    assert "detect_languages" in tools


def test_swift_bump_version_requires_auth() -> None:
    """swift_bump_version is mutation — requires MAHAVISHNU_AUTH_ENABLED=true + MAHAVISHNU_JWT_SECRET."""
    with mock.patch.dict(os.environ, {}, clear=True):
        _, tools = asyncio.run(_register())
        tool = tools["swift_bump_version"]
        with pytest.raises(PermissionError, match="MAHAVISHNU_AUTH_ENABLED"):
            asyncio.run(tool.fn(project_root="/tmp/nonexistent", level="minor"))


def test_swift_bump_version_runs_with_auth(tmp_path: Path) -> None:
    """With auth set + valid project_root, swift_bump_version delegates to the lifecycle."""
    # Patch the lifecycle helper so we don't depend on real git push / gh.
    import crackerjack.mcp.tools.language_tools as mod

    fake_result = {
        "new_version": "1.1.0",
        "commit_sha": "abc123",
        "tag_name": "v1.1.0",
        "release_url": None,
    }

    env = {
        "MAHAVISHNU_AUTH_ENABLED": "true",
        "MAHAVISHNU_JWT_SECRET": "test-secret",
        "MAHAVISHNU_PROJECT_ROOTS": str(tmp_path),
    }
    with mock.patch.dict(os.environ, env, clear=True):
        _, tools = asyncio.run(_register())
        tool = tools["swift_bump_version"]
        with mock.patch.object(
            mod, "_run_swift_lifecycle_sync", return_value=fake_result,
        ) as fake_run:
            result = asyncio.run(tool.fn(project_root=str(tmp_path), level="minor"))
            fake_run.assert_called_once()
            args, _ = fake_run.call_args
            assert str(args[0]) == str(tmp_path.resolve())
            assert args[1] == "minor"

    assert result["new_version"] == "1.1.0"
    assert result["tag_name"] == "v1.1.0"


def test_swift_list_hooks_does_not_require_auth(tmp_path: Path) -> None:
    """swift_list_hooks is read-only — no auth required."""
    # Create a real Package.swift so swift_hooks() runs to completion.
    (tmp_path / "Package.swift").write_text(
        "// swift-tools-version:5.9\n"
        "import PackageDescription\n"
        "let package = Package(name: \"x\")\n",
    )
    with mock.patch.dict(os.environ, {}, clear=True):
        _, tools = asyncio.run(_register())
        tool = tools["swift_list_hooks"]
        result = asyncio.run(tool.fn(project_root=str(tmp_path)))
        assert isinstance(result, dict)
        assert "swift.test" in result
        assert "swift.build" in result


def test_swift_bump_version_rejects_path_traversal(tmp_path: Path) -> None:
    """Per Security F2: project_root outside the allowlist is rejected."""
    env = {
        "MAHAVISHNU_AUTH_ENABLED": "true",
        "MAHAVISHNU_JWT_SECRET": "test-secret",
        "MAHAVISHNU_PROJECT_ROOTS": str(tmp_path / "allowed"),  # different dir
    }
    with mock.patch.dict(os.environ, env, clear=True):
        _, tools = asyncio.run(_register())
        tool = tools["swift_bump_version"]
        # /tmp/nonexistent is real but not under the allowlist.
        with pytest.raises(PermissionError, match="not in the allowlist"):
            asyncio.run(tool.fn(project_root="/tmp/nonexistent", level="minor"))


def test_swift_bump_version_rejects_relative_path_traversal(tmp_path: Path) -> None:
    """Per Security F2: relative paths with .. are rejected after .resolve()."""
    env = {
        "MAHAVISHNU_AUTH_ENABLED": "true",
        "MAHAVISHNU_JWT_SECRET": "test-secret",
        "MAHAVISHNU_PROJECT_ROOTS": str(tmp_path),
    }
    with mock.patch.dict(os.environ, env, clear=True):
        _, tools = asyncio.run(_register())
        tool = tools["swift_bump_version"]
        with pytest.raises(PermissionError, match="traversal"):
            asyncio.run(tool.fn(project_root="../../etc", level="minor"))


def test_detect_languages_returns_adapter_names(tmp_path: Path) -> None:
    with mock.patch.dict(os.environ, {}, clear=True):
        _, tools = asyncio.run(_register())
        tool = tools["detect_languages"]
        result = asyncio.run(tool.fn(project_root=str(tmp_path)))
        # Both Python and Swift detect the empty tmp dir as neither.
        assert "python" in result
        assert "swift" in result
        assert isinstance(result, dict)
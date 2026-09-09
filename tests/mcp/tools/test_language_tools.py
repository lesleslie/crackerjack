from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest import mock

import pytest
from fastmcp import FastMCP

from crackerjack.adapters.kotlin.hooks import GradleTaskProbe


async def _register() -> tuple[FastMCP, dict]:
    """Register language_tools and return (mcp_app, tools_dict)."""
    mcp_app = FastMCP("test")
    from crackerjack.mcp.tools.language_tools import register_language_tools

    register_language_tools(mcp_app)
    tools = {t.name: t for t in await mcp_app.list_tools()}
    return mcp_app, tools


def test_register_language_tools_registers_seven_tools() -> None:
    async def _go() -> dict:
        _, tools = await _register()
        return tools

    tools = asyncio.run(_go())
    assert "swift_bump_version" in tools
    assert "swift_list_hooks" in tools
    assert "detect_languages" in tools
    assert "kotlin_bump_version" in tools
    assert "kotlin_list_hooks" in tools
    assert "check_web_lint" in tools
    assert "format_jinja_templates" in tools


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
    with mock.patch.dict(
        os.environ, {"MAHAVISHNU_PROJECT_ROOTS": str(tmp_path)}, clear=True,
    ):
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
    """All four adapters must register (Phase 3 carry-over: kotlin; Phase 4: web)."""
    with mock.patch.dict(
        os.environ, {"MAHAVISHNU_PROJECT_ROOTS": str(tmp_path)}, clear=True,
    ):
        _, tools = asyncio.run(_register())
        tool = tools["detect_languages"]
        result = asyncio.run(tool.fn(project_root=str(tmp_path)))
        # Both Python and Swift detect the empty tmp dir as neither.
        assert "python" in result
        assert "swift" in result
        assert "kotlin" in result  # Phase 3 carry-over
        assert "web" in result     # Phase 4
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Kotlin/Gradle tools (Phase 3 Task 7)
# ---------------------------------------------------------------------------


async def test_kotlin_list_hooks_returns_three_hook_names(tmp_path: Path) -> None:
    """Happy path: kotlin_list_hooks returns metadata for a valid Gradle project."""
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = await _register()
        tool = tools["kotlin_list_hooks"]
        # Stub the probe so we don't require gradlew on PATH
        with mock.patch.object(GradleTaskProbe, "has_task", return_value=True):
            result = await tool.fn(project_root=str(tmp_path))
    finally:
        monkeypatch.undo()
    assert isinstance(result, dict)
    names = set(result.keys())
    assert "kotlin.ktlint" in names
    assert "kotlin.detekt" in names
    assert "kotlin.test" in names
    assert result["kotlin.test"]["cli_command"][:2] == ["./gradlew", "test"]


async def test_kotlin_list_hooks_rejects_non_kotlin_directory(tmp_path: Path) -> None:
    """Per Security F-5: must raise if adapter.detect() is False (Phase 2 CF-4 analog)."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = await _register()
        tool = tools["kotlin_list_hooks"]
        with pytest.raises(ValueError, match="No build.gradle"):
            await tool.fn(project_root=str(tmp_path))
    finally:
        monkeypatch.undo()


async def test_kotlin_bump_version_requires_auth(tmp_path: Path) -> None:
    """Mutation tools require MAHAVISHNU_AUTH_ENABLED + MAHAVISHNU_JWT_SECRET."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.delenv("MAHAVISHNU_AUTH_ENABLED", raising=False)
        monkeypatch.delenv("MAHAVISHNU_JWT_SECRET", raising=False)
        _, tools = await _register()
        tool = tools["kotlin_bump_version"]
        with pytest.raises(PermissionError):
            await tool.fn(level="minor", project_root=str(tmp_path))
    finally:
        monkeypatch.undo()


async def test_kotlin_bump_version_runs_with_auth(tmp_path: Path) -> None:
    """Per MCP HIGH-3 / Testing HIGH-1 (Phase 2 CRITICAL-1 analog): happy-path
    test that exercises the real KotlinLifecycle + GradlePropertiesVersionSource.

    Without this test, future regressions (e.g. dry_run mutating gradle.properties,
    rollback contract breakage) would ship silently — exactly the Phase 2
    fake-green pattern that was caught at Task 7 review.

    Git operations are stubbed via ``make_git_backend`` patching (Phase 2 H7 +
    Security F4 constructor-injection pattern). The real
    ``GradlePropertiesVersionSource.write`` still runs, so we catch
    write-side regressions (read-back verification, snapshot/restore).
    """
    (tmp_path / "build.gradle.kts").write_text("")
    (tmp_path / "gradle.properties").write_text("version=1.2.3\n")
    # Init a real git repo so commits work (we mock git_backend but the
    # pre-flight git status check would otherwise block the bump write).
    import subprocess as sp

    sp.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    sp.run(
        ["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True,
    )
    sp.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("# test")
    sp.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
    sp.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

    # Patch make_git_backend to return mocks. Avoids the real git backend's
    # Security F6 uncommitted-changes check (which would otherwise reject
    # the bump write) AND avoids needing a real remote for `git push`.
    from crackerjack.adapters.kotlin import git_backend

    fake_commit = mock.Mock(return_value="abc123def456" + "0" * 32)
    fake_tag = mock.Mock(return_value="v1.3.0")
    fake_push = mock.Mock()
    fake_delete_tag = mock.Mock()
    fake_reset = mock.Mock()
    fake_gh_release = mock.Mock(return_value=None)
    fake_backend = (
        fake_commit, fake_tag, fake_push, fake_delete_tag, fake_reset, fake_gh_release,
    )

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
        monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "test-secret")
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = await _register()
        tool = tools["kotlin_bump_version"]
        with mock.patch.object(
            git_backend, "make_git_backend", return_value=fake_backend,
        ):
            result = await tool.fn(level="minor", project_root=str(tmp_path))
    finally:
        monkeypatch.undo()
    assert result["new_version"] == "1.3.0"
    # gradle.properties was rewritten (real write() called)
    assert (tmp_path / "gradle.properties").read_text() == "version=1.3.0\n"
    fake_commit.assert_called_once()


async def test_kotlin_bump_version_rejects_non_kotlin_directory(tmp_path: Path) -> None:
    """Per Security F-5: must raise if adapter.detect() is False."""
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
        monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "test-secret")
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = await _register()
        tool = tools["kotlin_bump_version"]
        with pytest.raises(ValueError, match="No build.gradle"):
            await tool.fn(level="minor", project_root=str(tmp_path))
    finally:
        monkeypatch.undo()


async def test_kotlin_bump_version_rejects_invalid_level(tmp_path: Path) -> None:
    """Per MCP HIGH-2: level must be one of major/minor/patch (Literal type)."""
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
        monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "test-secret")
        monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
        _, tools = await _register()
        tool = tools["kotlin_bump_version"]
        with pytest.raises(ValueError, match="level must be"):
            await tool.fn(level="epic", project_root=str(tmp_path))
    finally:
        monkeypatch.undo()


# ---------------------------------------------------------------------------
# Web tools (Phase 4 Task 6)
# ---------------------------------------------------------------------------


def test_check_web_lint_returns_four_hook_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 4: check_web_lint returns the 4-hook metadata for a Web project."""
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    _, tools = asyncio.run(_register())
    tool = tools["check_web_lint"]
    result = asyncio.run(tool.fn(project_root=str(tmp_path)))
    assert isinstance(result, dict)
    assert "hooks" in result
    names = {h["name"] for h in result["hooks"]}
    assert names == {
        "web.stylelint",
        "web.eslint",
        "web.tsc",
        "web.html_validate",
    }


def test_check_web_lint_rejects_python_project_no_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 4: check_web_lint raises ValueError on a Python project without opt-in (per Writing F3)."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'foo'\n")
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    _, tools = asyncio.run(_register())
    tool = tools["check_web_lint"]
    with pytest.raises(ValueError, match="Web adapter not enabled"):
        asyncio.run(tool.fn(project_root=str(tmp_path)))


def test_format_jinja_templates_requires_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 4: format_jinja_templates raises PermissionError when auth env vars unset."""
    (tmp_path / "package.json").write_text("{}")
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    monkeypatch.delenv("MAHAVISHNU_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("MAHAVISHNU_JWT_SECRET", raising=False)
    _, tools = asyncio.run(_register())
    tool = tools["format_jinja_templates"]
    with pytest.raises(PermissionError):
        asyncio.run(tool.fn(projects=[str(tmp_path)]))


def test_format_jinja_templates_runs_with_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Phase 4: format_jinja_templates actually rewrites the file on disk."""
    (tmp_path / "package.json").write_text("{}")
    test_file = tmp_path / "test.html"
    original = "{% if x %}A{% endif %}"
    test_file.write_text(original)

    monkeypatch.setenv("MAHAVISHNU_AUTH_ENABLED", "true")
    monkeypatch.setenv("MAHAVISHNU_JWT_SECRET", "x" * 64)
    monkeypatch.setenv("MAHAVISHNU_PROJECT_ROOTS", str(tmp_path))
    _, tools = asyncio.run(_register())
    tool = tools["format_jinja_templates"]
    result = asyncio.run(tool.fn(projects=[str(tmp_path)], dry_run=False))

    # Verify mutation actually happened (Phase 2 fake-green prevention).
    assert result["errors"] == []
    assert any("test.html" in f for f in result["files"])
    rewritten = test_file.read_text()
    assert rewritten != original
    assert rewritten.endswith("\n")  # Tier 1 trailing-newline rule

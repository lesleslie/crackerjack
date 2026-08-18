"""Verify discover_tools.py + TOOL_REGISTRY are gone post-W2a."""
from __future__ import annotations

import subprocess


def test_discover_tools_py_deleted() -> None:
    """discover_tools.py must be removed (W2a git rm)."""
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "crackerjack/mcp/tools/discover_tools.py"],
        capture_output=True,
        text=True,
        cwd="/Users/les/Projects/crackerjack",
    )
    assert result.returncode != 0, (
        "crackerjack/mcp/tools/discover_tools.py still tracked in git"
    )


def test_tool_registry_unreferenced_in_production() -> None:
    """No production code in crackerjack/ may import TOOL_REGISTRY after W2a.

    Docs may still mention the symbol as historical context (annotated in
    MEMORY_ARCHITECTURE.md Status 2026-08-18).
    """
    result = subprocess.run(
        ["git", "grep", "-l", "TOOL_REGISTRY", "crackerjack/"],
        capture_output=True,
        text=True,
        cwd="/Users/les/Projects/crackerjack",
    )
    assert not result.stdout.strip(), (
        f"TOOL_REGISTRY still referenced in production: {result.stdout}"
    )


def test_deferred_tools_unreferenced_in_production() -> None:
    """DEFERRED_TOOLS must not be imported in production code after W2a."""
    result = subprocess.run(
        ["git", "grep", "-l", "DEFERRED_TOOLS", "crackerjack/"],
        capture_output=True,
        text=True,
        cwd="/Users/les/Projects/crackerjack",
    )
    assert not result.stdout.strip(), (
        f"DEFERRED_TOOLS still referenced in production: {result.stdout}"
    )


def test_register_discover_tools_unreferenced_in_production() -> None:
    """register_discover_tools must not be called in production code after W2a."""
    result = subprocess.run(
        ["git", "grep", "-l", "register_discover_tools", "crackerjack/"],
        capture_output=True,
        text=True,
        cwd="/Users/les/Projects/crackerjack",
    )
    assert not result.stdout.strip(), (
        f"register_discover_tools still referenced in production: {result.stdout}"
    )

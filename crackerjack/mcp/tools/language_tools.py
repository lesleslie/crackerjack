from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

from crackerjack.adapters.registry import discover_adapters
from crackerjack.adapters.swift import SwiftAdapter
from crackerjack.adapters.swift.git_backend import make_git_backend
from crackerjack.adapters.swift.lifecycle import SwiftLifecycle
from crackerjack.adapters.swift.version_source import GitTagVersionSource

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Auth (config check only — JWT decoding is a future plan)
# ---------------------------------------------------------------------------


def _require_auth_config() -> None:
    """Per spec MCP F5: mutation tools require auth env vars set.

    This is a CONFIG CHECK only — it does NOT validate JWTs, decode tokens,
    or verify caller identity. A future plan should add real JWT decoding
    (e.g., ``jwt.decode(token, secret, algorithms=[...], audience=...)``)
    and bind the validated ``sub`` claim to the commit/tag message for audit.
    """
    if os.environ.get("MAHAVISHNU_AUTH_ENABLED") != "true":
        raise PermissionError(
            "MAHAVISHNU_AUTH_ENABLED=true required for mutation tools. "
            "Set this env var before invoking swift_bump_version.",
        )
    if not os.environ.get("MAHAVISHNU_JWT_SECRET"):
        raise PermissionError(
            "MAHAVISHNU_JWT_SECRET unset. Mutation tools require auth.",
        )


# ---------------------------------------------------------------------------
# project_root validation (per Security F2)
# ---------------------------------------------------------------------------


def _validate_project_root(project_root: str) -> Path:
    """Resolve project_root and validate against the allowlist.

    Per Security F2: rejects traversal patterns (``..``), NUL bytes, and
    paths outside the configured allowlist. Returns the resolved Path.

    When ``MAHAVISHNU_PROJECT_ROOTS`` is unset (common in dev), the
    allowlist check is skipped — the caller still gets NUL + traversal
    rejection. Production deployments MUST set this var.
    """
    if "\x00" in project_root:
        raise PermissionError(f"project_root contains NUL byte: {project_root!r}")

    # Normalize: reject obvious traversal patterns before .resolve()
    # (resolve() would normalize ``..`` away but we want to fail fast).
    if ".." in Path(project_root).parts:
        raise PermissionError(f"project_root contains '..' traversal: {project_root!r}")

    # ``strict=False`` so non-existent paths still resolve to their canonical
    # form — the allowlist check then reports the policy verdict.
    root = Path(project_root).resolve(strict=False)

    # Allowlist check: project_root must be under one of MAHAVISHNU_PROJECT_ROOTS
    allowed_env = os.environ.get("MAHAVISHNU_PROJECT_ROOTS", "")
    if not allowed_env:
        logger.debug(
            "MAHAVISHNU_PROJECT_ROOTS unset; allowlist check skipped. "
            "Production deployments MUST configure this env var.",
        )
        return root
    allowed = [Path(p).resolve() for p in allowed_env.split(":") if p.strip()]
    if not any(_is_within(root, a) for a in allowed):
        raise PermissionError(
            f"project_root {root} is not in the allowlist (MAHAVISHNU_PROJECT_ROOTS)",
        )
    return root


def _is_within(path: Path, root: Path) -> bool:
    """True if path is the same as or strictly under root."""
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


# ---------------------------------------------------------------------------
# Lifecycle helper (async-safe via asyncio.to_thread)
# ---------------------------------------------------------------------------


def _run_swift_lifecycle_sync(
    project_root: Path, level: str, release: bool,
) -> dict[str, str | None]:
    """Run the Swift lifecycle synchronously.

    Wrapped by async MCP handlers via ``asyncio.to_thread``.
    """
    from crackerjack.adapters.base import LifecycleOptions

    version_source = GitTagVersionSource(project_root)
    commit, tag, push, delete_tag, reset, gh_release = make_git_backend(project_root)
    lifecycle = SwiftLifecycle(
        version_source=version_source,
        project_root=project_root,
        commit=commit,
        tag=tag,
        push=push,
        delete_tag=delete_tag,
        reset=reset,
        gh_release=gh_release,
    )
    result = lifecycle.run(LifecycleOptions(level=level, release=release))
    return {
        "new_version": result.new_version,
        "commit_sha": result.commit_sha,
        "tag_name": result.tag_name,
        "release_url": result.release_url,
    }


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


def register_language_tools(mcp_app: FastMCP) -> None:
    """Register the language_tools MCP group (Phase 2: Swift).

    Per spec MCP F1 (4-step pipeline):
    1. CREATE — this module
    2. REGISTER — added to ``_build_registration_map()`` in profiles.py (Task 7.5)
    3. ASSIGN TIER — language_tools added to FULL_REGISTRATIONS (Task 7.6)
    4. TEST — verified via ``mcp_app.list_tools()`` in tests/mcp/tools/

    Mutation tools (``swift_bump_version``) require auth (per spec MCP F5).
    ``swift_list_hooks`` is renamed from Rev 1's ``swift_run_hooks``: it is a
    metadata tool that returns hook configs, not a runner.
    """

    @mcp_app.tool()
    async def swift_bump_version(
        project_root: str,
        level: Literal["major", "minor", "patch"] = "minor",
        release: bool = False,
    ) -> dict[str, str | None]:
        """Bump the Swift project's version (via git tags, no Package.swift mutation).

        Per spec Swift F1: tag is the version.
        Per spec MCP F5: requires auth env vars.
        Per Security F2: project_root is validated against MAHAVISHNU_PROJECT_ROOTS.
        Per MCP F7: sync subprocess runs in asyncio.to_thread to not block the event loop.
        """
        _require_auth_config()
        root = _validate_project_root(project_root)
        # Run the sync lifecycle in a thread so the MCP event loop isn't blocked.
        return await asyncio.to_thread(
            _run_swift_lifecycle_sync, root, level, release,
        )

    @mcp_app.tool()
    async def swift_list_hooks(project_root: str) -> dict[str, dict]:
        """Return the configured Swift hooks for the project.

        Renamed from Rev 1's ``swift_run_hooks``: this is a metadata tool that
        lists hook configs (cli_command, autofix, timeout). It does NOT
        execute hooks — see the spec's ``swift_bump_version`` for that.

        No auth required (read-only).
        """
        root = _validate_project_root(project_root)
        adapter = SwiftAdapter()
        caps = adapter.capabilities(root)
        return {
            h.name: {
                "cli_command": list(h.cli_command),
                "autofix": h.autofix,
                "timeout_seconds": h.timeout_seconds,
            }
            for h in caps.hooks
        }

    @mcp_app.tool()
    async def detect_languages(project_root: str) -> dict[str, bool]:
        """Return which language adapters detect the project at project_root.

        Phase 2: returns ``{'python': bool, 'swift': bool}``. Phase 3+ adds Kotlin,
        Phase 4+ adds Web.

        No auth required (read-only).
        """
        root = _validate_project_root(project_root)
        adapters = discover_adapters()
        # Registry may return either instances or classes (depends on entry-point
        # shape vs the runtime_checkable Protocol in base.py). Normalize so we
        # always call detect() on an instance.
        return {
            name: (
                adapter().detect(root)
                if isinstance(adapter, type)
                else adapter.detect(root)
            )
            for name, adapter in adapters.items()
        }
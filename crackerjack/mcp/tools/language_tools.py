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
    current = os.environ.get("MAHAVISHNU_AUTH_ENABLED")
    if current != "true":
        raise PermissionError(
            f"Mutation tools require MAHAVISHNU_AUTH_ENABLED=true; "
            f"current value: {current!r}",
        )
    secret = os.environ.get("MAHAVISHNU_JWT_SECRET")
    if not secret:
        raise PermissionError(
            f"Mutation tools require MAHAVISHNU_JWT_SECRET; "
            f"current length: {len(secret) if secret else 0} chars",
        )


# ---------------------------------------------------------------------------
# project_root validation (per Security F2)
# ---------------------------------------------------------------------------


def _validate_project_root(project_root: str) -> Path:
    """Resolve project_root and validate against the allowlist.

    Per Security F2: rejects traversal patterns (``..``), NUL bytes, and
    paths outside the configured allowlist. Returns the resolved Path.

    Per Phase 2 final-review IMPORTANT-1: fails closed when
    ``MAHAVISHNU_PROJECT_ROOTS`` is unset — previously this branch silently
    skipped the allowlist check, which was a latent privilege-escalation
    vector (any caller could target any path). Production deployments MUST
    set this var to colon-separated absolute paths.
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

    # Allowlist check: project_root must be under one of MAHAVISHNU_PROJECT_ROOTS.
    # Fail-closed: if the env var is unset, refuse ALL access.
    allowed_env = os.environ.get("MAHAVISHNU_PROJECT_ROOTS", "")
    if not allowed_env:
        raise PermissionError(
            "MAHAVISHNU_PROJECT_ROOTS unset. Configure with colon-separated "
            "absolute paths to allow.",
        )
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


def _run_kotlin_lifecycle_sync(
    root: Path,
    level: Literal["major", "minor", "patch"],
    dry_run: bool,
    release: bool,
) -> "LifecycleResult":
    """Run the Kotlin lifecycle synchronously.

    Wrapped by async MCP handlers via ``asyncio.to_thread``. Mirrors
    :func:`_run_swift_lifecycle_sync` (MCP MEDIUM 2 carry-over from Phase 2
    final-review) — keeps the tool function readable and matches the Phase 2
    precedent. Per Security F-5 (Phase 2 CF-4 analog), the caller MUST have
    already verified ``adapter.detect(root)`` is True before invoking this
    helper (lifecycle raises if gradle.properties is missing).
    """
    from crackerjack.adapters.base import LifecycleOptions, LifecycleResult
    from crackerjack.adapters.kotlin.git_backend import make_git_backend
    from crackerjack.adapters.kotlin.lifecycle import KotlinLifecycle
    from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource

    version_source = GradlePropertiesVersionSource(root)
    commit, tag, push, delete_tag, reset, gh_release = make_git_backend(root)
    lifecycle = KotlinLifecycle(
        version_source=version_source,
        project_root=root,
        commit=commit,
        tag=tag,
        push=push,
        delete_tag=delete_tag,
        reset=reset,
        gh_release=gh_release,
    )
    return lifecycle.run(LifecycleOptions(level=level, dry_run=dry_run, release=release))


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
        return {name: adapter.detect(root) for name, adapter in adapters.items()}

    @mcp_app.tool()
    async def kotlin_bump_version(
        level: Literal["major", "minor", "patch"],
        project_root: str,
        dry_run: bool = False,
        release: bool = False,
    ) -> dict:
        """Bump a Kotlin/Gradle project's version. Writes the new version to
        ``gradle.properties`` (NOT ``build.gradle.kts``), then commits, tags,
        pushes, and optionally creates a GitHub release. Rolls back all
        mutations on failure.

        Args:
            level: Semver component to bump — ``major``, ``minor``, or ``patch``.
                Pre-release qualifiers (e.g. ``-SNAPSHOT``, ``-RC1``) and build
                metadata (e.g. ``+build.5``) are preserved unchanged.
            project_root: Absolute path to the project root. Must contain
                ``build.gradle.kts`` (or ``build.gradle``) and
                ``gradle.properties``. Must be in ``MAHAVISHNU_PROJECT_ROOTS``
                allowlist.
            dry_run: If True, compute the new version but make NO mutations
                (no gradle.properties write, no commit, no tag, no push).
            release: If True, create a GitHub release via ``gh release create``
                after pushing the tag.

        Returns:
            dict with keys ``new_version``, ``commit_sha``, ``tag_name``,
            ``release_url``, ``skipped_steps`` (tuple of steps that were
            skipped, e.g. ``("dry_run",)`` when ``dry_run=True``).

        Raises:
            PermissionError: if ``MAHAVISHNU_AUTH_ENABLED`` is not ``true``,
                ``MAHAVISHNU_JWT_SECRET`` is unset, or ``project_root`` is
                not in ``MAHAVISHNU_PROJECT_ROOTS`` allowlist.
            ValueError: if ``build.gradle.kts`` is missing or ``level`` is
                not one of the literal values.
            FileNotFoundError: if ``gradle.properties`` is missing.
            RuntimeError: on git/gh subprocess failure (after rollback).
        """
        _require_auth_config()
        root = _validate_project_root(project_root)
        from crackerjack.adapters.kotlin import KotlinAdapter

        adapter = KotlinAdapter()
        if not adapter.detect(root):
            raise ValueError(
                f"No build.gradle(.kts) at {root}. "
                f"Run `gradle init --type kotlin-library` to scaffold.",
            )
        result = await asyncio.to_thread(
            _run_kotlin_lifecycle_sync, root, level, dry_run, release,
        )
        return {
            "new_version": result.new_version,
            "commit_sha": result.commit_sha,
            "tag_name": result.tag_name,
            "release_url": result.release_url,
            "skipped_steps": list(result.skipped_steps),
        }

    @mcp_app.tool()
    async def kotlin_list_hooks(project_root: str) -> dict[str, dict]:
        """Return Kotlin/Gradle hook metadata for the given project.

        Probes ``./gradlew tasks --all`` to detect which plugins are
        available. Hooks whose tasks are absent (e.g. ``ktlintCheck`` if no
        ktlint plugin) are filtered out with a logged warning.
        ``kotlin.test`` is always emitted (every Kotlin project has the
        ``test`` task).

        Args:
            project_root: Absolute path to the project root. Must contain
                ``build.gradle.kts`` (or ``build.gradle``). Must be in
                ``MAHAVISHNU_PROJECT_ROOTS`` allowlist (read-only access).

        Returns:
            dict mapping hook name to metadata: ``cli_command`` (argv list,
                e.g. ``["./gradlew", "ktlintCheck"]``), ``autofix``, and
                ``timeout_seconds``.

        Raises:
            PermissionError: if ``project_root`` is not in
                ``MAHAVISHNU_PROJECT_ROOTS`` allowlist.
            ValueError: if ``build.gradle.kts`` is missing.
        """
        root = _validate_project_root(project_root)
        from crackerjack.adapters.kotlin import KotlinAdapter

        adapter = KotlinAdapter()
        if not adapter.detect(root):
            raise ValueError(
                f"No build.gradle(.kts) at {root}. "
                f"Run `gradle init --type kotlin-library` to scaffold.",
            )
        caps = adapter.capabilities(root)
        return {
            h.name: {
                "cli_command": list(h.cli_command),
                "autofix": h.autofix,
                "timeout_seconds": h.timeout_seconds,
            }
            for h in caps.hooks
        }

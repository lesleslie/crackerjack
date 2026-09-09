from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from crackerjack.adapters.base import (
    Lifecycle,
    LifecycleOptions,
    LifecycleResult,
)
from crackerjack.adapters.swift.version_source import GitTagVersionSource

logger = logging.getLogger(__name__)


def _bump(version: str, level: str) -> str:
    """Bump a semver string. Pre-1.0 semantics: major bumps minor."""
    parts = version.split(".")
    while len(parts) < 3:
        parts.append("0")

    major, minor, patch = (int(p) for p in parts[:3])

    if level in ("major", "minor"):
        minor += 1
        patch = 0
    elif level == "patch":
        patch += 1
    else:
        raise ValueError(f"Unknown level: {level!r}")

    return f"{major}.{minor}.{patch}"


class SwiftLifecycle(Lifecycle):
    """Swift lifecycle: bump via git tags only.

    Per spec Swift F1: Package.swift is NOT mutated. The version is
    the latest matching git tag. The lifecycle:
    1. reads the current version from ``git describe --tags --match "v*"``
    2. computes the new version
    3. creates an annotated tag (``git tag -a v{new} -m "..."``)
    4. pushes the tag (``git push origin <tag>``)
    5. optionally creates a GitHub release (``gh release create``)
    On push failure: delete the tag, raise.
    On gh_release failure: delete the tag and reset (per MEDIUM M5).

    The 6 git/gh methods (commit, tag, push, delete_tag, reset, gh_release)
    are constructor-injected (per HIGH H7 + Security F4). Tests pass fakes
    directly to __init__; production wires real subprocess implementations
    via :func:`make_git_backend`.
    """

    def __init__(
        self,
        version_source: GitTagVersionSource,
        project_root: Path,
        *,
        commit: Callable[[str], str],
        tag: Callable[[str, str], None],
        push: Callable[[str, str], None],
        delete_tag: Callable[[str], None],
        reset: Callable[[str], None],
        gh_release: Callable[[str], str],
    ) -> None:
        self._version_source = version_source
        self._project_root = project_root
        self._commit = commit
        self._tag = tag
        self._push = push
        self._delete_tag = delete_tag
        self._reset = reset
        self._gh_release = gh_release

    def run(self, options: LifecycleOptions) -> LifecycleResult:
        current = self._version_source.read()
        new_version = _bump(current, options.level)

        if options.dry_run:
            return LifecycleResult(
                new_version=new_version,
                commit_sha=None,
                tag_name=None,
                release_url=None,
                skipped_steps=("dry_run",),
            )

        commit_sha = self._commit(
            message=f"bump: swift v{current} → v{new_version}",
        )

        tag_name = f"v{new_version}"
        self._tag(tag_name, message=f"Release v{new_version}")

        try:
            self._push(commit_sha, tag_name)
        except Exception:
            logger.exception("push failed; rolling back tag %s", tag_name)
            self._delete_tag(tag_name)
            self._reset(commit_sha)
            raise

        release_url: str | None = None
        if options.release:
            try:
                release_url = self._gh_release(tag_name)
            except Exception:
                logger.exception(
                    "gh_release failed; rolling back tag %s", tag_name,
                )
                self._delete_tag(tag_name)
                self._reset(commit_sha)
                raise

        return LifecycleResult(
            new_version=new_version,
            commit_sha=commit_sha,
            tag_name=tag_name,
            release_url=release_url,
        )

"""Kotlin/Gradle lifecycle: bump via gradle.properties + git tag.

Per spec Kotlin K1: the version lives in ``gradle.properties`` (with fallback
to ``build.gradle.kts``/``build.gradle`` and ``./gradlew properties``). The
lifecycle:

1. reads the current version from
   :class:`~crackerjack.adapters.kotlin.version_source.GradlePropertiesVersionSource`
2. computes the new version with real-semver :func:`_bump`
   (preserves pre-release qualifiers like ``-SNAPSHOT`` and build
   metadata like ``+build.5``)
3. writes the new version back to ``gradle.properties``
4. creates an empty git commit (``git commit --allow-empty -m "bump: ..."``)
5. creates an annotated tag (``git tag -a v{new} -m "..."``)
6. pushes the tag (``git push origin <tag>``)
7. optionally creates a GitHub release (``gh release create``)

On push failure: restore the original ``gradle.properties`` content, delete
the tag, hard-reset to the bump commit, raise. On ``_commit`` failure AFTER
``write()`` succeeded: also restore ``gradle.properties`` (because
``_reset(commit_sha)`` cannot undo an uncommitted file change). On
``gh_release`` failure: same rollback contract.

The 6 git/gh methods (``commit``, ``tag``, ``push``, ``delete_tag``, ``reset``,
``gh_release``) are constructor-injected (per HIGH H7 + Security F4 of the
Phase 2 multi-agent review). Tests pass fakes directly to ``__init__``;
production wires real subprocess implementations via
:func:`crackerjack.adapters.kotlin.git_backend.make_git_backend`.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

from crackerjack.adapters.base import (
    Lifecycle,
    LifecycleOptions,
    LifecycleResult,
)
from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource

logger = logging.getLogger(__name__)

# Real semver: MAJOR.MINOR.PATCH with optional pre-release (-SNAPSHOT, -RC1)
# and build metadata (+build.123). Matches PEP 440's notion loosely but
# follows semver.org. See :func:`_bump` for bump semantics.
_SEMVER_RE = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


def _bump(version: str, level: str) -> str:
    """Real-semver bump: major/minor/patch each bump the named component.

    Preserves the pre-release qualifier (e.g. ``-SNAPSHOT``, ``-RC1``, ``-M1``)
    and build metadata (e.g. ``+build.5``) unchanged. Real Kotlin/JVM projects
    use these between releases (Kotlin BLOCKER #1 from Phase 3 Kotlin review).

    Cross-adapter divergence: :func:`crackerjack.adapters.swift.lifecycle._bump`
    uses pre-1.0 semantics (major bumps minor) per its docstring. Kotlin uses
    real semver, matching :func:`crackerjack.adapters.python_lifecycle._bump`.
    See Spec Revision Notes §3 (cross-adapter ``_bump``).
    """
    m = _SEMVER_RE.match(version)
    if not m:
        raise ValueError(f"version is not valid semver: {version!r}")
    major, minor, patch = int(m["major"]), int(m["minor"]), int(m["patch"])
    prerelease = m["prerelease"]  # may be None
    build = m["build"]  # may be None
    if level == "major":
        major += 1
        minor = 0
        patch = 0
    elif level == "minor":
        minor += 1
        patch = 0
    elif level == "patch":
        patch += 1
    else:
        raise ValueError(
            f"level must be one of ('major', 'minor', 'patch'); got {level!r}"
        )
    bumped = f"{major}.{minor}.{patch}"
    if prerelease is not None:
        bumped += f"-{prerelease}"
    if build is not None:
        bumped += f"+{build}"
    return bumped


def _snapshot_gradle_properties(project_root: Path) -> str:
    """Read ``gradle.properties`` content for later restore on rollback."""
    return (project_root / "gradle.properties").read_text()


def _restore_gradle_properties(project_root: Path, content: str) -> None:
    """Write ``content`` back to ``gradle.properties`` during rollback."""
    (project_root / "gradle.properties").write_text(content)


class KotlinLifecycle(Lifecycle):
    """Kotlin/Gradle lifecycle: bump via gradle.properties + git tag.

    See module docstring for the full flow. Constructor-injected methods let
    tests substitute fakes; production uses
    :func:`~crackerjack.adapters.kotlin.git_backend.make_git_backend`.
    """

    def __init__(
        self,
        version_source: GradlePropertiesVersionSource,
        project_root: Path,
        *,
        commit: Callable[[str], str],
        tag: Callable[[str, str], str],
        push: Callable[[str, str], None],
        delete_tag: Callable[[str], None],
        reset: Callable[[str], None],
        gh_release: Callable[[str, str | None], str | None],
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

        # Per CRITICAL-1 (Security F-3 + API CRITICAL #1): dry_run=True MUST
        # skip ALL mutations. The gradle.properties file MUST NOT be rewritten.
        if options.dry_run:
            return LifecycleResult(
                new_version=new_version,
                commit_sha=None,
                tag_name=None,
                release_url=None,
                skipped_steps=("dry_run",),
            )

        # Per API CRITICAL #2: snapshot the file BEFORE write() so we can
        # restore it on any rollback branch. After write() succeeds but
        # before _commit() runs, the working tree has an uncommitted
        # gradle.properties change that _reset(commit_sha) cannot undo
        # (reset targets a prior commit, not working-tree files).
        original_content = _snapshot_gradle_properties(self._project_root)
        try:
            self._version_source.write(new_version)
        except Exception:
            # write() failed before any git side effect; nothing to roll back.
            raise

        try:
            commit_sha = self._commit(
                message=f"bump: kotlin v{current} → v{new_version}",
            )
        except Exception:
            logger.exception(
                "commit failed after write(); restoring gradle.properties",
            )
            _restore_gradle_properties(self._project_root, original_content)
            raise

        tag_name = f"v{new_version}"
        try:
            self._tag(tag_name, f"Release v{new_version}")
        except Exception:
            logger.exception(
                "tag failed after commit; restoring gradle.properties and reset",
            )
            _restore_gradle_properties(self._project_root, original_content)
            self._reset(commit_sha)
            raise

        try:
            self._push(commit_sha, tag_name)
        except Exception:
            logger.exception("push failed; rolling back tag %s", tag_name)
            _restore_gradle_properties(self._project_root, original_content)
            self._delete_tag(tag_name)
            self._reset(commit_sha)
            raise

        release_url: str | None = None
        if options.release:
            try:
                release_url = self._gh_release(tag_name, None)
            except Exception:
                logger.exception(
                    "gh_release failed; rolling back tag %s", tag_name,
                )
                _restore_gradle_properties(self._project_root, original_content)
                self._delete_tag(tag_name)
                self._reset(commit_sha)
                raise

        return LifecycleResult(
            new_version=new_version,
            commit_sha=commit_sha,
            tag_name=tag_name,
            release_url=release_url,
        )

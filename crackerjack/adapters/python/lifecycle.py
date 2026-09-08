from __future__ import annotations

import logging
import subprocess

from crackerjack.adapters.base import (
    Lifecycle,
    LifecycleOptions,
    LifecycleResult,
)
from crackerjack.adapters.python.version_source import PyprojectVersionSource

logger = logging.getLogger(__name__)


def _bump(version: str, level: str) -> str:
    """Bump a semver string. Pre-1.0 uses Python's crackerjack semantics.

    For pre-1.0: ``major`` changes the leftmost 0, ``minor`` increments
    the middle, ``patch`` increments the rightmost. For 1.0+: standard
    semver.
    """
    parts = version.split(".")
    while len(parts) < 3:
        parts.append("0")

    major, minor, patch = (int(p) for p in parts[:3])

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
        raise ValueError(f"Unknown level: {level!r}")

    return f"{major}.{minor}.{patch}"


class PythonLifecycle(Lifecycle):
    """Executes the crackerjack Python lifecycle.

    Phase 1 delegates to the existing ``PublishManager.bump_version``
    flow for the actual bump + commit + tag + push + twine publish
    (preserving all behavior). Phase 2+ may replace this delegation
    with a per-language lifecycle; Phase 1's job is to expose the
    existing flow under the new ``Lifecycle.run()`` contract.

    The five ``_commit`` / ``_tag`` / ``_push`` / ``_delete_tag`` /
    ``_reset`` / ``_publish_pypi`` methods are the integration seam.
    Tests mock them on the instance; the real implementation calls
    :mod:`crackerjack.services.git` and subprocess for tag/delete
    operations.
    """

    def __init__(self, version_source: PyprojectVersionSource) -> None:
        self._version_source = version_source

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

        # Persist the new version via the version source so the commit
        # captures the bumped value (the commit is then made via _commit
        # below).
        self._version_source.write(new_version)

        commit_sha: str | None = None
        tag_name: str | None = None

        if options.commit:
            commit_sha = self._commit(
                message=f"bump: python v{current} → v{new_version}",
            )

        if options.tag and commit_sha is not None:
            tag_name = self._tag(
                f"v{new_version}",
                message=f"Release v{new_version}",
            )

        if options.push and tag_name is not None and commit_sha is not None:
            try:
                self._push(commit_sha, tag_name)
            except Exception:
                logger.exception("push failed; rolling back tag %s", tag_name)
                self._delete_tag(tag_name)
                self._reset(commit_sha)
                raise

        release_url: str | None = None
        if options.release and tag_name is not None:
            release_url = self._publish_pypi(tag_name)

        return LifecycleResult(
            new_version=new_version,
            commit_sha=commit_sha,
            tag_name=tag_name,
            release_url=release_url,
        )

    # -- Hook methods (overridden in tests; real impl below) ----------

    def _commit(self, message: str) -> str:
        """Stage pyproject.toml and commit; return the resulting SHA.

        Uses :class:`crackerjack.services.git.GitService` for the
        underlying commands. Returns the SHA via ``rev-parse HEAD``
        after the commit succeeds.
        """
        from crackerjack.services.git import GitService

        git = GitService(pkg_path=self._version_source._project_root)
        if not git.add_files(["pyproject.toml"]):
            raise RuntimeError("Failed to stage pyproject.toml")
        if not git.commit(message):
            raise RuntimeError(f"git commit failed for: {message}")
        sha = git.get_current_commit_hash()
        if sha is None:
            raise RuntimeError("Could not read SHA after commit")
        return sha

    def _tag(self, name: str, message: str) -> str:
        """Create an annotated tag and return its name."""
        result = subprocess.run(
            ["git", "tag", "-a", name, "-m", message],
            cwd=self._version_source._project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git tag failed for {name}: {result.stderr.strip()}",
            )
        return name

    def _push(self, commit_sha: str, tag_name: str) -> None:
        """Push the commit and tag; raise on failure (triggers rollback)."""
        from crackerjack.services.git import GitService

        git = GitService(pkg_path=self._version_source._project_root)
        if not git.push_with_tags():
            raise RuntimeError(
                f"git push failed (commit={commit_sha[:8]}, tag={tag_name})",
            )

    def _delete_tag(self, name: str) -> None:
        """Delete a tag locally (rollback path). Best-effort."""
        result = subprocess.run(
            ["git", "tag", "-d", name],
            cwd=self._version_source._project_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            logger.warning("rollback: failed to delete tag %s: %s", name, result.stderr)

    def _reset(self, commit_sha: str) -> None:
        """Reset back to ``commit_sha`` (rollback path). Best-effort.

        Note: ``reset_hard`` keeps the bump commit but discards the tag,
        which preserves the version bump locally so the user can retry
        ``git push`` without re-running the lifecycle. If a full undo
        is needed, use ``reset_hard({commit_sha}^)`` from
        :class:`crackerjack.services.git.GitService`.
        """
        from crackerjack.services.git import GitService

        git = GitService(pkg_path=self._version_source._project_root)
        if not git.reset_hard(commit_sha):
            logger.warning("rollback: reset --hard %s failed", commit_sha)

    def _publish_pypi(self, tag_name: str) -> str | None:
        """Build and upload to PyPI; return the project URL.

        Delegates to :class:`crackerjack.managers.publish_manager.PublishManager`.
        Falls back to the PyPI project page URL on success.
        """
        from crackerjack.managers.publish_manager import PublishManager

        package_root = self._version_source._project_root
        manager = PublishManager(pkg_path=package_root)
        if not manager.publish_package():
            raise RuntimeError("PublishManager.publish_package failed")
        project_url = (
            f"https://pypi.org/project/{manager._get_package_name() or ''}/"
        )
        return project_url

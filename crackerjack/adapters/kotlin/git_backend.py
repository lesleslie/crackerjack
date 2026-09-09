"""Default subprocess implementations of the git/gh methods KotlinLifecycle needs.

These are constructor-injected into :class:`KotlinLifecycle`. Tests pass fakes
via the same constructor signature (per HIGH H7 + Security F4 of the Phase 2
multi-agent review).

Module-level ``commit``/``tag``/``push``/``delete_tag``/``reset``/``gh_release``
are convenience wrappers that operate on the active project root
(see :data:`_PROJECT_ROOT`). The factory :func:`make_git_backend` returns the
same six callables bound to an explicit ``project_root`` for production use.
"""
from __future__ import annotations

import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level active project root. Tests set this via
# ``tests.adapters.kotlin._gradle_helpers.init_git_repo`` so that the
# module-level functions below operate on the test's temporary git repo.
# Production code uses ``make_git_backend(project_root)`` instead.
_PROJECT_ROOT: Path | None = None


def _active_root() -> Path:
    """Return the module-level active project root (defaults to cwd)."""
    if _PROJECT_ROOT is None:
        return Path.cwd()
    return _PROJECT_ROOT


def commit(message: str) -> str:
    """Create an empty commit with ``message``. Returns the new HEAD SHA.

    Per Security F6: refuses if there are uncommitted changes.
    """
    root = _active_root()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    if status.stdout.strip():
        raise RuntimeError(
            f"Cannot commit: uncommitted changes in {root}.\n"
            f"Commit or stash them first, or pass force=True.\n"
            f"Status output:\n{status.stdout}",
        )
    # --allow-empty supports bumps that don't touch files (build.gradle.kts
    # is not mutated in v1).
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", message],
        cwd=root,
        check=True,
    )
    rev_parse = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return rev_parse.stdout.strip()


def tag(name: str, message: str) -> str:
    """Create an annotated ``name`` tag with ``message``. Returns ``name``.

    Per Security F7: ``--`` separator before user-influenced positional.
    Options must come BEFORE ``--`` so git parses ``-m message`` as the
    annotation flag rather than as positionals after ``--``.

    Per Phase 3 Rev 2 Ruling 11: returns the tag name (str) instead of None.
    """
    root = _active_root()
    if not name or name.startswith("-"):
        raise ValueError(f"Invalid tag name: {name!r}")
    subprocess.run(
        ["git", "tag", "-a", "-m", message, "--", name],
        cwd=root,
        check=True,
    )
    return name


def push(sha: str, tag_name: str) -> None:
    """Push ``tag_name`` to ``MAHAVISHNU_GIT_REMOTE`` (default: ``origin``).

    ``sha`` is accepted for symmetry with SwiftLifecycle; the current
    subprocess implementation does not need it.
    """
    root = _active_root()
    if not tag_name or tag_name.startswith("-"):
        raise ValueError(f"Invalid tag name: {tag_name!r}")
    remote = os.environ.get("MAHAVISHNU_GIT_REMOTE", "origin")
    subprocess.run(
        ["git", "push", "--", remote, tag_name],
        cwd=root,
        check=True,
    )


def delete_tag(name: str) -> None:
    """Delete the local tag ``name``."""
    root = _active_root()
    if not name or name.startswith("-"):
        raise ValueError(f"Invalid tag name: {name!r}")
    subprocess.run(
        ["git", "tag", "-d", "--", name],
        cwd=root,
        check=True,
    )


def reset(commit_sha: str) -> None:
    """Hard-reset to ``commit_sha``.

    Per Phase 1 ruling + Security F6: reset TO the bump commit (preserves
    the bump, drops the tag). Full undo (HEAD~1) would remove the bump
    commit entirely — wrong for Kotlin's tag-is-version model.
    """
    root = _active_root()
    subprocess.run(
        ["git", "reset", "--hard", commit_sha],
        cwd=root,
        check=True,
    )


def gh_release(tag_name: str, release_name: str | None = None) -> str | None:
    """Create a GitHub release for ``tag_name``. Returns the release URL.

    ``release_name`` (optional, Phase 3 Rev 2 Ruling 11) overrides the
    human-readable release title. Defaults to ``tag_name``.

    Per Security F3: raises on non-zero exit (no fabricated fallback URL).
    Per Security F5: uses --notes-file with explicit body (no
    --generate-notes which would leak commit messages).
    """
    root = _active_root()
    title = release_name if release_name else tag_name
    # Write a brief notes file to avoid --generate-notes commit-message leak.
    notes_file = root / ".crackerjack-release-notes.tmp"
    notes = (
        f"# Release {tag_name}\n\n"
        f"_Automated release by crackerjack Phase 3 (language_tools)._\n"
    )
    notes_file.write_text(notes)
    try:
        result = subprocess.run(
            [
                "gh",
                "release",
                "create",
                "--",
                tag_name,
                "--notes-file",
                str(notes_file),
                "--title",
                title,
            ],
            cwd=root,
            capture_output=True,
            text=True,
        )
    finally:
        notes_file.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"gh release create failed (exit {result.returncode}): "
            f"{result.stderr}",
        )
    return result.stdout.strip()


def make_git_backend(
    project_root: Path,
) -> tuple[
    Callable[[str], str],
    Callable[[str, str], str],
    Callable[[str, str], None],
    Callable[[str], None],
    Callable[[str], None],
    Callable[..., str | None],
]:
    """Return the six git/gh callables bound to ``project_root``.

    Returns a tuple of ``(commit, tag, push, delete_tag, reset, gh_release)``
    matching :class:`KotlinLifecycle`'s constructor signature. These are
    independent closures that operate on ``project_root`` regardless of the
    module-level :data:`_PROJECT_ROOT`.
    """

    def _commit(message: str) -> str:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        if status.stdout.strip():
            raise RuntimeError(
                f"Cannot commit: uncommitted changes in {project_root}.\n"
                f"Commit or stash them first, or pass force=True.\n"
                f"Status output:\n{status.stdout}",
            )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", message],
            cwd=project_root,
            check=True,
        )
        rev_parse = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return rev_parse.stdout.strip()

    def _tag(name: str, message: str) -> str:
        if not name or name.startswith("-"):
            raise ValueError(f"Invalid tag name: {name!r}")
        subprocess.run(
            ["git", "tag", "-a", "-m", message, "--", name],
            cwd=project_root,
            check=True,
        )
        return name

    def _push(sha: str, tag_name: str) -> None:
        if not tag_name or tag_name.startswith("-"):
            raise ValueError(f"Invalid tag name: {tag_name!r}")
        remote = os.environ.get("MAHAVISHNU_GIT_REMOTE", "origin")
        subprocess.run(
            ["git", "push", "--", remote, tag_name],
            cwd=project_root,
            check=True,
        )

    def _delete_tag(name: str) -> None:
        if not name or name.startswith("-"):
            raise ValueError(f"Invalid tag name: {name!r}")
        subprocess.run(
            ["git", "tag", "-d", "--", name],
            cwd=project_root,
            check=True,
        )

    def _reset(commit_sha: str) -> None:
        subprocess.run(
            ["git", "reset", "--hard", commit_sha],
            cwd=project_root,
            check=True,
        )

    def _gh_release(tag_name: str, release_name: str | None = None) -> str | None:
        title = release_name if release_name else tag_name
        notes_file = project_root / ".crackerjack-release-notes.tmp"
        notes = (
            f"# Release {tag_name}\n\n"
            f"_Automated release by crackerjack Phase 3 (language_tools)._\n"
        )
        notes_file.write_text(notes)
        try:
            result = subprocess.run(
                [
                    "gh",
                    "release",
                    "create",
                    "--",
                    tag_name,
                    "--notes-file",
                    str(notes_file),
                    "--title",
                    title,
                ],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
        finally:
            notes_file.unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"gh release create failed (exit {result.returncode}): "
                f"{result.stderr}",
            )
        return result.stdout.strip()

    return _commit, _tag, _push, _delete_tag, _reset, _gh_release

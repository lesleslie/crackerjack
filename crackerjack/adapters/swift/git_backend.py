"""Default subprocess implementations of the git/gh methods SwiftLifecycle needs.

These are constructor-injected into :class:`SwiftLifecycle`. Tests pass fakes
via the same constructor signature (per HIGH H7 + Security F4 of the Phase 2
multi-agent review).
"""
from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def make_git_backend(
    project_root: Path,
) -> tuple[
    Callable[[str], str],
    Callable[[str, str], None],
    Callable[[str, str], None],
    Callable[[str], None],
    Callable[[str], None],
    Callable[[str], str],
]:
    """Return the six git/gh callables bound to ``project_root``.

    Returns a tuple of ``(commit, tag, push, delete_tag, reset, gh_release)``
    matching :class:`SwiftLifecycle`'s constructor signature.
    """

    def commit(message: str) -> str:
        # Per Security F6: refuse if there are uncommitted changes.
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
        # --allow-empty supports bumps that don't touch files (Package.swift
        # is not mutated in v1).
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

    def tag(name: str, message: str) -> None:
        # Per Security F7: -- separator before user-influenced positional.
        if not name or name.startswith("-"):
            raise ValueError(f"Invalid tag name: {name!r}")
        subprocess.run(
            ["git", "tag", "-a", "--", name, "-m", message],
            cwd=project_root,
            check=True,
        )

    def push(_commit_sha: str, tag_name: str) -> None:
        if not tag_name or tag_name.startswith("-"):
            raise ValueError(f"Invalid tag name: {tag_name!r}")
        subprocess.run(
            ["git", "push", "origin", "--", tag_name],
            cwd=project_root,
            check=True,
        )

    def delete_tag(name: str) -> None:
        if not name or name.startswith("-"):
            raise ValueError(f"Invalid tag name: {name!r}")
        subprocess.run(
            ["git", "tag", "-d", "--", name],
            cwd=project_root,
            check=True,
        )

    def reset(commit_sha: str) -> None:
        # Per Phase 1 ruling + Security F6: reset TO the bump commit (preserves
        # the bump, drops the tag). Full undo (HEAD~1) would remove the bump
        # commit entirely — wrong for Swift's tag-is-version model.
        subprocess.run(
            ["git", "reset", "--hard", commit_sha],
            cwd=project_root,
            check=True,
        )

    def gh_release(tag_name: str) -> str:
        """Create a GitHub release for ``tag_name``. Returns the release URL.

        Per Security F3: raises on non-zero exit (no fabricated fallback URL).
        Per Security F5: uses --notes-file with explicit body (no
        --generate-notes which would leak commit messages).
        """
        # Write a brief notes file to avoid --generate-notes commit-message leak.
        notes_file = project_root / ".crackerjack-release-notes.tmp"
        notes = (
            f"# Release {tag_name}\n\n"
            f"_Automated release by crackerjack Phase 2 (language_tools)._\n"
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
                    tag_name,
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

    return commit, tag, push, delete_tag, reset, gh_release

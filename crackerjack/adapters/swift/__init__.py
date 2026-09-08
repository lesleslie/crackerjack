from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapterBase
from crackerjack.adapters.swift.hooks import swift_hooks
from crackerjack.adapters.swift.lifecycle import SwiftLifecycle
from crackerjack.adapters.swift.version_source import GitTagVersionSource

__all__ = ["SwiftAdapter", "SwiftLifecycle", "GitTagVersionSource", "swift_hooks"]


class SwiftAdapter(LanguageAdapterBase):
    """The Swift language adapter.

    Phase 2: detects Package.swift projects, exposes the Swift hook
    set + lifecycle. Lifecycle uses git tags primary (per spec Swift F1);
    Package.swift is NOT mutated in v1.
    """

    name = "swift"

    def detect(self, project_root: Path) -> bool:
        return (project_root / "Package.swift").is_file()

    def capabilities(self, project_root: Path) -> Capabilities:
        from crackerjack.adapters.swift.git_backend import make_git_backend

        version_source = GitTagVersionSource(project_root)
        commit, tag, push, delete_tag, reset, gh_release = make_git_backend(project_root)
        SwiftLifecycle(
            version_source=version_source,
            project_root=project_root,
            commit=commit,
            tag=tag,
            push=push,
            delete_tag=delete_tag,
            reset=reset,
            gh_release=gh_release,
        )
        return Capabilities(
            version_source=version_source,
            hooks=swift_hooks(project_root / "Package.swift"),
            has_lifecycle=True,
        )

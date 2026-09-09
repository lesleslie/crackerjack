from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapterBase
from crackerjack.adapters.swift.hooks import swift_hooks
from crackerjack.adapters.swift.lifecycle import SwiftLifecycle
from crackerjack.adapters.swift.version_source import GitTagVersionSource

__all__ = ["GitTagVersionSource", "SwiftAdapter", "SwiftLifecycle", "swift_hooks"]


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
        version_source = GitTagVersionSource(project_root)
        return Capabilities(
            version_source=version_source,
            hooks=swift_hooks(project_root / "Package.swift"),
            has_lifecycle=True,
        )

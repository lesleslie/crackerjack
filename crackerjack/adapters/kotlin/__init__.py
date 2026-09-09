"""Kotlin/Gradle language adapter for crackerjack.

Activates only when `build.gradle.kts` or `build.gradle` is present at
the project root. Provides Kotlin lifecycle (gradle.properties bump + git
tag/push), three Kotlin hooks with Gradle task probing (ktlint, detekt,
test), and version management via GradlePropertiesVersionSource.
"""

from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import Capabilities, LanguageAdapterBase
from crackerjack.adapters.kotlin.hooks import kotlin_hooks
from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource

__all__ = ["KotlinAdapter"]


class KotlinAdapter(LanguageAdapterBase):
    """Kotlin/Gradle language adapter — activates on build.gradle(.kts) presence."""

    name: str = "kotlin"

    def detect(self, project_root: Path) -> bool:
        return (project_root / "build.gradle.kts").is_file() or (project_root / "build.gradle").is_file()

    def capabilities(self, project_root: Path) -> Capabilities:
        # Per Phase 2 final-review CF-2 fix: do not construct KotlinLifecycle here.
        # The lifecycle is rebuilt inside the MCP handler (Task 7).
        return Capabilities(
            version_source=GradlePropertiesVersionSource(project_root),
            hooks=kotlin_hooks(project_root),
            has_lifecycle=True,
        )
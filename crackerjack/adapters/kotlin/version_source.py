"""Gradle properties version source for Kotlin/Gradle projects.

Probes ``gradle.properties`` for a version key, falls back to scanning
``build.gradle.kts`` / ``build.gradle``, and finally shells out to
``./gradlew properties`` as the authoritative source when neither file
matches.
"""
from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

from crackerjack.adapters.base import VersionNotFoundError, VersionSource

logger = logging.getLogger(__name__)


class GradlePropertiesVersionSource:
    """Probe gradle.properties for version, with multiple key conventions.

    Order (anchored with \\b): pluginVersion, projectVersion, version.
    Falls back to build.gradle.kts scan. Always verifies via Gradle
    (Gradle is source of truth) when neither file-probe tier matches.
    """

    _PROBE_KEYS = ("pluginVersion", "projectVersion", "version")

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root

    def read(self) -> str:
        properties_path = self._project_root / "gradle.properties"
        if properties_path.exists():
            content = properties_path.read_text()
            for key in self._PROBE_KEYS:
                m = re.search(rf"\b{re.escape(key)}\s*=\s*(\S+?)[,\s]*$", content, re.MULTILINE)
                if m:
                    return m.group(1)
        for gradle_file in ("build.gradle.kts", "build.gradle"):
            path = self._project_root / gradle_file
            if path.exists():
                content = path.read_text()
                m = re.search(r'^\s*version\s*=\s*"([^"]+)"', content, re.MULTILINE)
                if m:
                    return m.group(1)
        return self._read_via_gradle()

    def _read_via_gradle(self) -> str:
        try:
            result = subprocess.run(
                ["./gradlew", "properties", "-q", "--no-daemon", "--no-configuration-cache"],
                cwd=self._project_root, capture_output=True, text=True,
            )
        except FileNotFoundError as exc:
            raise VersionNotFoundError(
                f"`./gradlew` not found in {self._project_root}"
            ) from exc
        if result.returncode != 0:
            raise VersionNotFoundError(f"`gradlew properties` failed: {result.stderr}")
        m = re.search(r"^version:\s*(\S+)", result.stdout, re.MULTILINE)
        if not m:
            raise VersionNotFoundError("`gradlew properties` did not emit a `version:` line")
        return m.group(1)

    def write(self, new_version: str) -> None:
        properties_path = self._project_root / "gradle.properties"
        if not properties_path.exists():
            raise FileNotFoundError(
                f"gradle.properties not found at {properties_path}; cannot write version"
            )
        content = properties_path.read_text()
        written = False
        for key in self._PROBE_KEYS:
            pattern = rf"^(\s*)({re.escape(key)}\s*=\s*)(\S+?)([,\s]*)$"
            new_content, count = re.subn(pattern, rf"\1\2{new_version}\4", content, flags=re.MULTILINE)
            if count:
                content = new_content
                written = True
                break
        if not written:
            # No existing key — append at end of file
            content = content.rstrip("\n") + f"\nversion={new_version}\n"
        properties_path.write_text(content)
        verified = self.read()
        if verified != new_version:
            from crackerjack.adapters.base import VersionWriteError
            raise VersionWriteError(
                f"Write verification failed: wrote {new_version!r}, read back {verified!r}"
            )


def gradle_properties_version_source(project_root: Path) -> VersionSource:
    """Factory matching the Phase 1 VersionSource Protocol shape.

    Returns the underlying object typed as VersionSource; concrete class is
    `GradlePropertiesVersionSource`. Use this factory for parity with
    `git_tag_version_source()` (Phase 2).
    """
    return GradlePropertiesVersionSource(project_root)
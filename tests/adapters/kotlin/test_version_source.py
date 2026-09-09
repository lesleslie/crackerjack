from __future__ import annotations

from pathlib import Path
import pytest

from crackerjack.adapters.base import VersionNotFoundError
from crackerjack.adapters.kotlin.version_source import GradlePropertiesVersionSource


def test_read_from_gradle_properties_plugin_version(tmp_path: Path) -> None:
    (tmp_path / "gradle.properties").write_text("pluginVersion=1.2.3\n")
    src = GradlePropertiesVersionSource(tmp_path)
    assert src.read() == "1.2.3"


def test_read_from_gradle_properties_project_version(tmp_path: Path) -> None:
    (tmp_path / "gradle.properties").write_text("projectVersion=2.0.0\n")
    src = GradlePropertiesVersionSource(tmp_path)
    assert src.read() == "2.0.0"


def test_read_from_gradle_properties_version(tmp_path: Path) -> None:
    (tmp_path / "gradle.properties").write_text("version=0.1.0\n")
    src = GradlePropertiesVersionSource(tmp_path)
    assert src.read() == "0.1.0"


def test_read_falls_back_to_build_gradle_kts(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text('version = "1.5.0"\n')
    src = GradlePropertiesVersionSource(tmp_path)
    assert src.read() == "1.5.0"


def test_read_raises_version_not_found_when_nothing_matches(tmp_path: Path) -> None:
    src = GradlePropertiesVersionSource(tmp_path)
    with pytest.raises(VersionNotFoundError):
        src.read()
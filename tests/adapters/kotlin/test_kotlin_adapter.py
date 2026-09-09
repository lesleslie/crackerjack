"""Tests for the KotlinAdapter — detection, capabilities wiring, and protocol conformance."""

from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.base import LanguageAdapterBase
from crackerjack.adapters.kotlin import KotlinAdapter


def test_kotlin_adapter_extends_language_adapter_base() -> None:
    assert issubclass(KotlinAdapter, LanguageAdapterBase)


def test_kotlin_adapter_name_is_kotlin() -> None:
    assert KotlinAdapter.name == "kotlin"


def test_detect_returns_true_for_build_gradle_kts(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    assert KotlinAdapter().detect(tmp_path) is True


def test_detect_returns_true_for_build_gradle(tmp_path: Path) -> None:
    (tmp_path / "build.gradle").write_text("")
    assert KotlinAdapter().detect(tmp_path) is True


def test_detect_returns_false_when_neither_present(tmp_path: Path) -> None:
    assert KotlinAdapter().detect(tmp_path) is False


def test_capabilities_returns_three_hooks_and_has_lifecycle(tmp_path: Path) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    caps = KotlinAdapter().capabilities(tmp_path)
    assert caps.has_lifecycle is True
    assert caps.has_version is True
    names = {h.name for h in caps.hooks}
    assert names == {"kotlin.ktlint", "kotlin.detekt", "kotlin.test"}
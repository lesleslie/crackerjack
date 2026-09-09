"""Minimal fixture-reference test for tests/fixtures/gradle-vanilla/.

The fixture is a real Gradle Kotlin lib (kotlin/jvm + ktlint plugin +
gradle.properties with version=0.1.0). This test verifies the adapter
can detect it and produce expected capabilities, proving the fixture
is wired up. A full end-to-end smoke against `./gradlew properties` and
`./gradlew ktlintCheck` is out of Phase 3 scope (deferred to Phase 3.5
per the final-review follow-up).
"""
from __future__ import annotations

from pathlib import Path

from crackerjack.adapters.kotlin import KotlinAdapter


FIXTURE_ROOT = Path(__file__).parent.parent.parent / "fixtures" / "gradle-vanilla"


def test_fixture_is_reachable() -> None:
    assert FIXTURE_ROOT.is_dir(), f"Fixture not found at {FIXTURE_ROOT}"
    assert (FIXTURE_ROOT / "build.gradle.kts").is_file()
    assert (FIXTURE_ROOT / "settings.gradle.kts").is_file()
    assert (FIXTURE_ROOT / "gradle.properties").is_file()


def test_adapter_detects_fixture() -> None:
    assert KotlinAdapter().detect(FIXTURE_ROOT) is True


def test_adapter_capabilities_on_fixture() -> None:
    caps = KotlinAdapter().capabilities(FIXTURE_ROOT)
    assert caps.has_lifecycle is True
    assert caps.has_version is True
    names = {h.name for h in caps.hooks}
    assert "kotlin.test" in names  # always emitted

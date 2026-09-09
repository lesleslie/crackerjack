"""Tests for the Kotlin/Gradle hook factory and ``GradleTaskProbe``.

Per spec:
- Kotlin F2: probe with ``./gradlew tasks --all`` before emitting a hook.
- Kotlin HIGH-5: probe must distinguish gradlew failure from absent task.
- Testing F3: use ``monkeypatch.setattr(shutil, "which", ...)`` for shutil mocks.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest import mock

import pytest

from crackerjack.adapters.kotlin.hooks import GradleTaskProbe, kotlin_hooks


def test_kotlin_hooks_returns_three_hooks_when_all_tasks_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gradlew" if cmd == "shutil.which" else None)
    with mock.patch.object(GradleTaskProbe, "has_task", return_value=True):
        hooks = kotlin_hooks(tmp_path)
    names = {h.name for h in hooks}
    assert names == {"kotlin.ktlint", "kotlin.detekt", "kotlin.test"}


def test_kotlin_hooks_filters_absent_tasks_with_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Per spec Kotlin F2: skip-with-warning if task is absent."""
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gradlew" if cmd == "shutil.which" else None)

    # Probe returns False for ktlintCheck (simulating absent plugin)
    def fake_has_task(self, task_name: str) -> bool:
        return task_name == "detekt"  # ktlintCheck absent, detekt present

    with mock.patch.object(GradleTaskProbe, "has_task", fake_has_task):
        with caplog.at_level("WARNING"):
            hooks = kotlin_hooks(tmp_path)
    names = {h.name for h in hooks}
    assert "kotlin.detekt" in names
    assert "kotlin.ktlint" not in names  # filtered out
    assert "kotlin.test" in names  # always present
    assert any("Skipping kotlin.ktlint" in r.message for r in caplog.records)


def test_kotlin_hooks_uses_gradlew_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gradlew" if cmd == "shutil.which" else None)
    with mock.patch.object(GradleTaskProbe, "has_task", return_value=True):
        hooks = kotlin_hooks(tmp_path)
    ktlint = next(h for h in hooks if h.name == "kotlin.ktlint")
    assert ktlint.cli_command[:2] == ("./gradlew", "ktlintCheck")


def test_kotlin_detekt_uses_gradlew_detekt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gradlew" if cmd == "shutil.which" else None)
    with mock.patch.object(GradleTaskProbe, "has_task", return_value=True):
        hooks = kotlin_hooks(tmp_path)
    detekt = next(h for h in hooks if h.name == "kotlin.detekt")
    assert detekt.cli_command[:2] == ("./gradlew", "detekt")


def test_kotlin_test_uses_gradlew_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "build.gradle.kts").write_text("")
    monkeypatch.setattr(shutil, "which", lambda cmd: "/usr/bin/gradlew" if cmd == "shutil.which" else None)
    with mock.patch.object(GradleTaskProbe, "has_task", return_value=True):
        hooks = kotlin_hooks(tmp_path)
    test = next(h for h in hooks if h.name == "kotlin.test")
    assert test.cli_command[:2] == ("./gradlew", "test")


def test_gradle_task_probe_returns_true_when_task_present(tmp_path: Path) -> None:
    probe = GradleTaskProbe(tmp_path)
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "ktlintCheck - Run ktlint\ndetekt - Run detekt\n"
        mock_run.return_value.returncode = 0
        assert probe.has_task("ktlintCheck") is True


def test_gradle_task_probe_returns_false_when_task_absent(tmp_path: Path) -> None:
    probe = GradleTaskProbe(tmp_path)
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = "test - Run tests\n"
        mock_run.return_value.returncode = 0
        assert probe.has_task("ktlintCheck") is False


def test_gradle_task_probe_returns_false_when_gradlew_fails(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Per Kotlin HIGH #5: probe must distinguish gradlew failure from absent task."""
    probe = GradleTaskProbe(tmp_path)
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "gradlew not found"
        with caplog.at_level("WARNING"):
            result = probe.has_task("ktlintCheck")
    assert result is False
    assert any("gradlew tasks --all failed" in r.message for r in caplog.records)


def test_gradle_task_probe_passes_no_daemon_no_configuration_cache(tmp_path: Path) -> None:
    probe = GradleTaskProbe(tmp_path)
    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value.stdout = ""
        mock_run.return_value.returncode = 0
        probe.has_task("ktlintCheck")
    args = mock_run.call_args[0][0]
    assert "--no-daemon" in args
    assert "--no-configuration-cache" in args

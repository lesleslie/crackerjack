"""Tests for the auto-sync gitignore behavior in publish_manager.

Validates the contract documented in
`.claude/decisions/2026-10-12-publish-auto-sync-gitignore.md`:

  - snippet present, no missing patterns  -> PASS, no sync subprocess
  - snippet missing                       -> auto-sync attempt, PASS on success
  - snippet + patterns missing            -> auto-sync attempt, PASS on success
  - sync subprocess fails                 -> FAIL, abort publish
  - sync succeeds but drift persists      -> FAIL, abort publish
  - pre-flight: `.gitignore` has uncommitted edits -> refuse auto-sync
  - non-fleet member                      -> PASS silently (no sync)
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.checks.gitignore_conformance import GitignoreConformanceResult
from crackerjack.managers.publish_manager import PublishManagerImpl


def _completed(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    """Real CompletedProcess so .stdout.strip() returns the actual string."""
    return subprocess.CompletedProcess(
        args=[], returncode=returncode, stdout=stdout, stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_console() -> MagicMock:
    return MagicMock(spec=Console)


def _make_conform_result(
    *,
    is_fleet_member: bool = True,
    snippet_present: bool = True,
    missing_patterns: list[str] | None = None,
    repo_path: Path | None = None,
) -> GitignoreConformanceResult:
    return GitignoreConformanceResult(
        repo_path=repo_path or Path("/fake/repo"),
        is_fleet_member=is_fleet_member,
        snippet_present=snippet_present,
        missing_patterns=missing_patterns or [],
    )


def _make_publish_manager(
    pkg_path: Path,
    console: MagicMock,
) -> PublishManagerImpl:
    """Build a minimal PublishManagerImpl with mocked dependencies.

    We only exercise `_validate_gitignore_conformance`, which is an
    instance method that touches self.pkg_path and self.console. All
    other constructor args default to None, which auto-resolves via
    PublishManagerImpl._resolve_*().
    """
    return PublishManagerImpl(
        console=console,
        pkg_path=pkg_path,
    )


# ---------------------------------------------------------------------------
# Cases: gate behavior
# ---------------------------------------------------------------------------


def test_pass_when_conformant_no_sync_invoked(tmp_path: Path, mock_console: MagicMock) -> None:
    """Clean state: PASS, no subprocess, no error log."""
    pm = _make_publish_manager(tmp_path, mock_console)
    conform = _make_conform_result(is_fleet_member=True, snippet_present=True, missing_patterns=[])

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ) as check_mock,
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    check_mock.assert_called_once_with(tmp_path)
    run_mock.assert_not_called()


def test_non_fleet_repo_passes_silently(tmp_path: Path, mock_console: MagicMock) -> None:
    """Non-Bodai repos: PASS, no sync."""
    pm = _make_publish_manager(tmp_path, mock_console)
    conform = _make_conform_result(is_fleet_member=False)

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ) as check_mock,
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    check_mock.assert_called_once_with(tmp_path)
    run_mock.assert_not_called()


def test_snippet_missing_triggers_sync_and_passes(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift: snippet missing. Auto-sync succeeds, gate PASSES."""
    pm = _make_publish_manager(tmp_path, mock_console)
    pre = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*", "!.claude/decisions/"],
    )
    post = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[],
    )

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            side_effect=[pre, post],
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=_completed(),
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    assert run_mock.call_count == 1


def test_patterns_missing_triggers_sync_and_passes(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift: snippet present but patterns missing. Auto-sync succeeds."""
    pm = _make_publish_manager(tmp_path, mock_console)
    pre = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[".claude/*"],
    )
    post = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[],
    )

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            side_effect=[pre, post],
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=_completed(),
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    assert run_mock.call_count == 1


def test_sync_subprocess_failure_aborts(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift: sync subprocess returns nonzero. Gate ABORTS."""
    pm = _make_publish_manager(tmp_path, mock_console)
    conform = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=_completed(returncode=1, stderr="boom"),
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    assert run_mock.call_count == 1


def test_sync_subprocess_timeout_aborts(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift: sync subprocess hangs and times out. Gate ABORTS."""
    import subprocess

    pm = _make_publish_manager(tmp_path, mock_console)
    conform = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="gitignore sync", timeout=60),
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    assert run_mock.call_count == 1


def test_sync_succeeds_but_drift_persists_aborts(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift: sync subprocess returns 0 but re-check still shows missing.
    Gate ABORTS — likely a stale backup blocking the sync.
    """
    pm = _make_publish_manager(tmp_path, mock_console)
    pre = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )
    post = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[".claude/*", "!.claude/decisions/"],  # drift persists
    )

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            side_effect=[pre, post],
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            return_value=_completed(),
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    assert run_mock.call_count == 1


def test_uncommitted_gitignore_refuses_auto_sync(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift + dirty .gitignore working tree -> auto-sync REFUSED, gate ABORTS."""
    pm = _make_publish_manager(tmp_path, mock_console)
    (tmp_path / ".gitignore").write_text("# operator WIP\n")
    conform = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )

    fake_status = _completed(stdout=" M .gitignore\n")
    fake_sync = _completed()

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            return_value=conform,
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            side_effect=[fake_status, fake_sync],
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is False
    # Only the pre-flight `git status` ran; the sync subprocess did NOT.
    assert run_mock.call_count == 1


def test_clean_gitignore_proceeds_with_sync(tmp_path: Path, mock_console: MagicMock) -> None:
    """Drift + clean .gitignore working tree -> both pre-flight + sync execute."""
    pm = _make_publish_manager(tmp_path, mock_console)
    (tmp_path / ".gitignore").write_text("# clean\n")
    pre = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )
    post = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[],
    )

    fake_status_clean = _completed()
    fake_sync_ok = _completed()

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            side_effect=[pre, post],
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            side_effect=[fake_status_clean, fake_sync_ok],
        ) as run_mock,
    ):
        result = pm._validate_gitignore_conformance()

    assert result is True
    assert run_mock.call_count == 2  # git status + crackerjack gitignore sync


def test_sync_subprocess_uses_correct_args(tmp_path: Path, mock_console: MagicMock) -> None:
    """The subprocess invocation must use --pkg-path and the target."""
    import sys

    (tmp_path / ".gitignore").write_text("# clean\n")
    pm = _make_publish_manager(tmp_path, mock_console)
    pre = _make_conform_result(
        is_fleet_member=True,
        snippet_present=False,
        missing_patterns=[".claude/*"],
    )
    post = _make_conform_result(
        is_fleet_member=True,
        snippet_present=True,
        missing_patterns=[],
    )

    fake_status = _completed()

    captured_args: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured_args.append(cmd)
        # First call: git status (return clean). Second call: crackerjack sync.
        if cmd and cmd[0] == "git":
            return fake_status
        return _completed()

    with (
        patch(
            "crackerjack.managers.publish_manager.check_repo_gitignore",
            side_effect=[pre, post],
        ),
        patch(
            "crackerjack.managers.publish_manager.subprocess.run",
            side_effect=fake_run,
        ),
    ):
        pm._validate_gitignore_conformance()

    assert len(captured_args) == 2
    sync_call = captured_args[1]
    assert sync_call[0] == sys.executable
    assert sync_call[1] == "-m"
    assert sync_call[2] == "crackerjack"
    assert sync_call[3] == "gitignore"
    assert sync_call[4] == "sync"
    assert sync_call[5] == "--pkg-path"
    assert sync_call[6] == str(tmp_path)
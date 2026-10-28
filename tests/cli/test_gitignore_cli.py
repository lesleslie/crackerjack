"""Tests for ``crackerjack.cli.gitignore_cli``.

Covers the ``check`` and ``sync`` subcommands, with particular attention
to path disclosure: rendered paths are home-relative (``~/Projects/...``)
so the OS account name never reaches the terminal.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from crackerjack.checks.gitignore_conformance import GitignoreConformanceResult
from crackerjack.cli.gitignore_cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``Path.home()`` at a temporary directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _conform(
    repo: Path,
    *,
    is_fleet_member: bool = True,
    snippet_present: bool = True,
    missing_patterns: list[str] | None = None,
    backup_path: Path | None = None,
) -> GitignoreConformanceResult:
    return GitignoreConformanceResult(
        repo_path=repo,
        is_fleet_member=is_fleet_member,
        snippet_present=snippet_present,
        missing_patterns=missing_patterns or [],
        backup_path=backup_path,
    )


def test_check_pass_redacts_home_directory(
    runner: CliRunner, fake_home: Path,
) -> None:
    """The conforming-repo message renders a home-relative path."""
    repo = fake_home / "Projects" / "oneiric"
    repo.mkdir(parents=True)

    with patch(
        "crackerjack.cli.gitignore_cli.check_repo_gitignore",
        return_value=_conform(repo),
    ):
        outcome = runner.invoke(app, ["check", "--pkg-path", str(repo)])

    assert outcome.exit_code == 0
    assert "~/Projects/oneiric" in outcome.output
    assert str(fake_home) not in outcome.output


def test_check_non_fleet_redacts_home_directory(
    runner: CliRunner, fake_home: Path,
) -> None:
    """The non-Bodai skip message renders a home-relative path."""
    repo = fake_home / "Projects" / "other"
    repo.mkdir(parents=True)

    with patch(
        "crackerjack.cli.gitignore_cli.check_repo_gitignore",
        return_value=_conform(repo, is_fleet_member=False),
    ):
        outcome = runner.invoke(app, ["check", "--pkg-path", str(repo)])

    assert outcome.exit_code == 0
    assert "~/Projects/other" in outcome.output
    assert str(fake_home) not in outcome.output


def test_check_missing_redacts_home_directory(
    runner: CliRunner, fake_home: Path,
) -> None:
    """The missing-snippet message renders a home-relative path."""
    repo = fake_home / "Projects" / "oneiric"
    repo.mkdir(parents=True)

    with patch(
        "crackerjack.cli.gitignore_cli.check_repo_gitignore",
        return_value=_conform(repo, snippet_present=False),
    ):
        outcome = runner.invoke(app, ["check", "--pkg-path", str(repo)])

    assert outcome.exit_code == 1
    assert "~/Projects/oneiric" in outcome.output
    assert str(fake_home) not in outcome.output


def test_sync_redacts_home_directory(runner: CliRunner, fake_home: Path) -> None:
    """The sync message and its backup line render home-relative paths."""
    repo = fake_home / "Projects" / "oneiric"
    repo.mkdir(parents=True)
    backup = repo / ".gitignore.bak.20260101T000000Z"

    with patch(
        "crackerjack.cli.gitignore_cli.sync_repo_gitignore",
        return_value=_conform(repo, backup_path=backup),
    ):
        outcome = runner.invoke(app, ["sync", "--pkg-path", str(repo)])

    assert outcome.exit_code == 0
    assert "~/Projects/oneiric" in outcome.output
    assert str(fake_home) not in outcome.output

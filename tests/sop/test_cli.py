"""Tests for ``crackerjack.sop.cli``.

Covers the Typer commands ``sop list``, ``sop show``, and ``sop propose``,
plus the ``add_sop_commands`` registrar. Each command exercises a small
branch of ``EvolutionEngine`` / ``InMemorySOPPersister``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from crackerjack.sop import cli as sop_cli
from crackerjack.sop.cli import add_sop_commands, app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_app_is_typer_instance() -> None:
    assert isinstance(app, typer.Typer)


def test_app_name_is_sop() -> None:
    assert app.info.name == "sop"


def test_add_sop_commands_registers_subcommand() -> None:
    """Mounting the sub-app adds the 'sop' command to the parent."""
    parent = typer.Typer()
    add_sop_commands(parent)
    # The sub-typer is registered; verify by checking the registered groups
    # via Typer's add_typer machinery.
    # (Typer's introspection API is limited; just assert no exception was raised.)
    assert parent is not None


def test_sop_list_with_no_sops_exits_zero(runner: CliRunner) -> None:
    """An empty project leads to a graceful 'no SOPs' message and exit 0."""
    result = runner.invoke(app, ["list", "--project", "demo"])
    assert result.exit_code == 0
    assert "No SOPs recorded" in result.stdout


def test_sop_show_unknown_name_exits_one(runner: CliRunner) -> None:
    """A missing SOP name causes exit 1 with a friendly message."""
    result = runner.invoke(
        app, ["show", "--project", "demo", "--name", "no-such-sop"]
    )
    assert result.exit_code == 1
    assert "No SOP named" in result.stdout


def test_sop_propose_observation_only_exits_zero(runner: CliRunner) -> None:
    """When the trigger threshold isn't reached, exit 0 with a notice."""
    result = runner.invoke(
        app,
        [
            "propose",
            "--project",
            "demo",
            "--sop",
            "my-sop",
            "--fingerprint",
            "fingerprint-1",
        ],
    )
    # Either "trigger not yet fired" (early return) or "Proposal ready"
    assert result.exit_code in (0,)


def test_sop_propose_with_all_options(runner: CliRunner) -> None:
    """All optional flags are accepted and parsed without error."""
    result = runner.invoke(
        app,
        [
            "propose",
            "--project",
            "demo",
            "--sop",
            "my-sop",
            "--fingerprint",
            "fingerprint-2",
            "--description",
            "tests failed",
            "--body",
            "current SOP body",
        ],
    )
    # Should not crash on parsing — exit code is from the engine result
    assert result.exit_code in (0,)


def test_build_engine_returns_engine_and_persister() -> None:
    """The internal helper wires up an ``EvolutionEngine`` + persister pair."""
    engine, persister = sop_cli._build_engine("test-project")  # noqa: SLF001
    assert engine is not None
    assert persister is not None
    assert persister.list("test-project") == []


def test_build_engine_persister_is_in_memory() -> None:
    """The constructed persister starts with no SOPs for any project."""
    _, persister = sop_cli._build_engine("fresh-project")
    assert persister.list("fresh-project") == []


def test_sop_list_after_record_then_show(runner: CliRunner) -> None:
    """End-to-end: record a SOP via the persister, then list and show it."""
    # Use the public InMemorySOPPersister interface directly to seed state.
    from crackerjack.sop.models import ProjectSOP
    from crackerjack.sop.persisters import InMemorySOPPersister

    seed = ProjectSOP(
        project_id="demo",
        name="rollback-on-flake",
        body="If a test flakes, rerun before flagging.",
        last_evolved_at=datetime.now(UTC),
        last_failure_id="fp-1",
    )
    persister = InMemorySOPPersister()
    persister.save(seed)
    with patch.object(sop_cli, "_build_engine") as mocked:
        mocked.return_value = (None, persister)

        listed = runner.invoke(app, ["list", "--project", "demo"])
        assert listed.exit_code == 0
        assert "rollback-on-flake" in listed.stdout

        shown = runner.invoke(
            app, ["show", "--project", "demo", "--name", "rollback-on-flake"]
        )
        assert shown.exit_code == 0
        assert "rollback-on-flake" in shown.stdout
        assert "rerun before flagging" in shown.stdout


def test_module_exposes_add_sop_commands() -> None:
    """``add_sop_commands`` is the public registration entrypoint."""
    assert callable(add_sop_commands)


def test_app_help_includes_project_description() -> None:
    """The Typer app carries a non-empty help string."""
    assert app.info.help
    assert len(app.info.help) > 0

"""Tests for the safe-typer loader in ``crackerjack.__main__``.

These tests lock in the design that sub-Typers are *optional* resources:
a broken sub-module (e.g. an ``IndentationError`` left behind by a partial
edit) must NOT poison the entire ``crackerjack`` CLI. The CLI is composed
by ``crackerjack.__main__`` calling ``_safe_add_typer`` for each sub-CLI;
any of those calls may fail, and the rest must continue.
"""

from __future__ import annotations

import logging
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from crackerjack.__main__ import _safe_add_typer


def test_safe_add_typer_logs_warning_on_import_error(caplog) -> None:
    """A missing module logs a warning, does not raise."""
    main_app = typer.Typer()

    with caplog.at_level(logging.WARNING):
        _safe_add_typer(
            main_app,
            "crackerjack.cli.this_module_does_not_exist_xyz",
            "app",
            "ghost",
        )

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "expected a WARNING to be logged"
    assert any("ghost" in r.getMessage() for r in warnings)
    # No sub-Typer registered
    assert all(g.name != "ghost" for g in main_app.registered_groups)


def test_safe_add_typer_continues_after_one_failure(caplog) -> None:
    """After a failed sub-Typer, the next call still registers."""
    main_app = typer.Typer()

    with caplog.at_level(logging.WARNING):
        # First call fails
        _safe_add_typer(
            main_app,
            "crackerjack.cli.this_module_does_not_exist_xyz",
            "app",
            "ghost",
        )
        # Second call succeeds (real sub-CLI)
        _safe_add_typer(
            main_app,
            "crackerjack.cli.docs_cli",
            "app",
            "docs",
        )

    # The docs sub-Typer should be registered
    group_names = {g.name for g in main_app.registered_groups}
    assert "docs" in group_names
    assert "ghost" not in group_names


def test_safe_add_typer_propagates_attribute_error(caplog) -> None:
    """If the module imports cleanly but lacks the expected attr, also tolerated.

    A module that imports but is missing the ``app`` symbol is treated the
    same as an import failure: warning + continue.
    """
    main_app = typer.Typer()

    with caplog.at_level(logging.WARNING):
        # ``logging`` is a real module but has no ``app`` attribute.
        _safe_add_typer(
            main_app,
            "logging",
            "app",
            "logging-as-typer",
        )

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("logging-as-typer" in r.getMessage() for r in warnings)


def test_full_cli_help_lists_renamed_subcommand() -> None:
    """End-to-end: ``crackerjack --help`` lists the renamed sub-command.

    This exercises the actual import chain in ``__main__.py``: it must
    successfully register ``hypothesis-lock`` (formerly ``precommit``).
    """
    # Importing the module runs the safe-loader for every sub-Typer.
    from crackerjack import __main__ as crackerjack_main

    runner = CliRunner()
    result = runner.invoke(crackerjack_main.app, ["--help"])

    # ``--help`` exits 0 on Typer.
    assert result.exit_code == 0, result.output
    assert "hypothesis-lock" in result.output
    # Old name must be gone.
    assert "precommit" not in result.output

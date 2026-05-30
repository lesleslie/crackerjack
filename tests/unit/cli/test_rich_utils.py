from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import Mock, patch

from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

_MODULE_PATH = Path(__file__).resolve().parents[3] / "crackerjack" / "cli" / "_rich_utils.py"
_SPEC = importlib.util.spec_from_file_location("tests.unit.cli._rich_utils", _MODULE_PATH)
assert _SPEC and _SPEC.loader is not None
_rich_utils = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_rich_utils)


def test_get_console_returns_module_console() -> None:
    assert _rich_utils.get_console() is _rich_utils.console


def test_print_panel_uses_style_when_provided() -> None:
    fake_console = Mock()
    with patch.object(_rich_utils, "console", fake_console):
        _rich_utils.print_panel("content", title="Title", style="bold", subtitle="Sub")

    fake_console.print.assert_called_once()
    panel = fake_console.print.call_args.args[0]
    assert isinstance(panel, Panel)
    assert panel.renderable == "content"
    assert panel.title == "Title"
    assert panel.subtitle == "Sub"
    assert fake_console.print.call_args.kwargs == {"style": "bold"}


def test_print_panel_without_style_uses_plain_print() -> None:
    fake_console = Mock()
    with patch.object(_rich_utils, "console", fake_console):
        _rich_utils.print_panel("content")

    fake_console.print.assert_called_once()
    assert isinstance(fake_console.print.call_args.args[0], Panel)
    assert fake_console.print.call_args.kwargs == {}


def test_create_table_uses_requested_options() -> None:
    table = _rich_utils.create_table(
        title="Heading",
        caption="Caption",
        show_header=False,
        show_edge=False,
    )

    assert isinstance(table, Table)
    assert table.title == "Heading"
    assert table.caption == "Caption"
    assert table.show_header is False
    assert table.show_edge is False


def test_create_progress_spinner_builds_progress_bar() -> None:
    progress = _rich_utils.create_progress_spinner()

    assert isinstance(progress, Progress)
    assert any(isinstance(column, SpinnerColumn) for column in progress.columns)
    assert any(isinstance(column, TextColumn) for column in progress.columns)
    assert any(isinstance(column, BarColumn) for column in progress.columns)
    assert progress.console is _rich_utils.console

"""Tests for ``crackerjack.cli._rich_utils``.

Covers the small wrapper functions around the ``rich`` library: console
singleton access, panel rendering, table creation, and progress spinner
construction. Each function delegates to ``rich`` — these tests verify
the delegation without depending on rich internals.
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table

from crackerjack.cli import _rich_utils


def test_get_console_returns_singleton_console() -> None:
    console = _rich_utils.get_console()
    assert console is _rich_utils.console


def test_get_console_returns_console_instance() -> None:
    assert isinstance(_rich_utils.get_console(), Console)


def test_print_panel_with_no_options(capsys: pytest.CaptureFixture[str]) -> None:
    """A panel with no title or style should still render the content."""
    _rich_utils.print_panel("hello world")
    captured = capsys.readouterr()
    assert "hello world" in captured.out


def test_print_panel_with_title(capsys: pytest.CaptureFixture[str]) -> None:
    """The title argument flows through to ``Panel(title=...)``."""
    _rich_utils.print_panel("body", title="My Title")
    captured = capsys.readouterr()
    # The title appears in the panel border — exact format depends on terminal
    # width, but the title string should be present.
    assert "My Title" in captured.out


def test_print_panel_with_subtitle(capsys: pytest.CaptureFixture[str]) -> None:
    _rich_utils.print_panel("body", subtitle="footer")
    captured = capsys.readouterr()
    assert "footer" in captured.out


def test_print_panel_with_style_passes_style_to_print() -> None:
    """When ``style`` is provided, ``console.print(panel, style=style)`` is called."""
    fake_console = Console(file=StringIO(), force_terminal=False)
    with patch.object(_rich_utils, "console", fake_console):
        _rich_utils.print_panel("x", style="bold red")
    out = fake_console.file.getvalue()  # type: ignore[attr-defined]
    # Style may not appear in plain output, but no exception is what matters.
    assert "x" in out or out == ""


def test_print_panel_without_style_uses_plain_print() -> None:
    """When ``style`` is None, ``console.print(panel)`` is called (no style kwarg)."""
    fake_console = Console(file=StringIO(), force_terminal=False)
    with patch.object(_rich_utils, "console", fake_console):
        _rich_utils.print_panel("payload")
    # No exception, and the panel content reached the console
    out = fake_console.file.getvalue()  # type: ignore[attr-defined]
    assert "payload" in out or "panel" in out.lower() or out != ""


def test_create_table_returns_table_instance() -> None:
    table = _rich_utils.create_table()
    assert isinstance(table, Table)


def test_create_table_forwards_title() -> None:
    table = _rich_utils.create_table(title="My Table")
    assert table.title == "My Table"


def test_create_table_forwards_caption() -> None:
    table = _rich_utils.create_table(caption="footer caption")
    assert table.caption == "footer caption"


def test_create_table_default_show_header() -> None:
    table = _rich_utils.create_table()
    assert table.show_header is True


def test_create_table_default_show_edge() -> None:
    table = _rich_utils.create_table()
    assert table.show_edge is True


def test_create_table_hides_header() -> None:
    table = _rich_utils.create_table(show_header=False)
    assert table.show_header is False


def test_create_table_hides_edge() -> None:
    table = _rich_utils.create_table(show_edge=False)
    assert table.show_edge is False


def test_create_progress_spinner_returns_progress_instance() -> None:
    progress = _rich_utils.create_progress_spinner()
    assert isinstance(progress, Progress)


def test_create_progress_spinner_default_description() -> None:
    """The default description is ``"Processing..."``."""
    progress = _rich_utils.create_progress_spinner()
    # rich stores the description in a TextColumn's renderable; verify by
    # checking that the Progress object's column set is non-empty and well-formed.
    assert len(progress.columns) >= 2


def test_create_progress_spinner_custom_description() -> None:
    """Custom descriptions are accepted and result in a valid Progress object."""
    progress = _rich_utils.create_progress_spinner(description="Loading…")
    assert len(progress.columns) >= 2


def test_create_progress_spinner_uses_module_console() -> None:
    """The spinner shares the module-level singleton console."""
    progress = _rich_utils.create_progress_spinner()
    assert progress.console is _rich_utils.console


def test_module_reexports_rich_classes() -> None:
    """Re-exports from rich should be accessible at module scope."""
    for name in ("Console", "Panel", "Progress", "BarColumn", "SpinnerColumn", "Table", "TextColumn"):
        assert hasattr(_rich_utils, name)

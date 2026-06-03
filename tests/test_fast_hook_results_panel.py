"""Regression tests for the Fast Hook Results panel rendering.

These tests guard against the column-truncation regression where the
``Issues`` column header was rendered as ``Issu`` and the per-row issue
counts disappeared. The root cause was the inner rich ``Table`` being
sized at the panel's outer width while the panel subtracted border and
padding from the available content area, so rich silently shrank the
``Issues`` column below its ``min_width``.

Mirrors the pattern in ``tests/test_ai_fix_dashboard.py``: render with
a fixed-width recording ``Console`` and assert on ``export_text()``.
"""

from __future__ import annotations

from rich.console import Console

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.models.task import HookResult


def _build_results() -> list[HookResult]:
    return [
        HookResult(name="validate-regex-patterns", status="passed", duration=2.64),
        HookResult(name="trailing-whitespace", status="passed", duration=4.14),
        HookResult(name="end-of-file-fixer", status="passed", duration=3.24),
        HookResult(name="ruff-format", status="failed", duration=5.32, issues_count=12),
        HookResult(name="pip-audit", status="passed", duration=50.10),
    ]


def test_fast_hook_results_panel_renders_full_issues_header() -> None:
    """The Issues column header must render in full, not truncated to 'Issu'."""
    console = Console(record=True, width=80, highlight=False)
    coordinator = PhaseCoordinator()
    coordinator.console = console

    coordinator._render_rich_hook_results("fast", _build_results())

    rendered = console.export_text()
    assert "Issues" in rendered, (
        f"'Issues' header missing from rendered panel:\n{rendered}"
    )
    # The truncated form would appear as 'Issu ' or 'Issu' followed by a
    # column separator rather than the full 'Issues' word.
    assert "Issu " not in rendered, (
        f"'Issues' header is truncated to 'Issu' in rendered panel:\n{rendered}"
    )


def test_fast_hook_results_panel_renders_issue_counts() -> None:
    """The per-row issue counts (e.g., 12 for a failing hook) must be visible."""
    console = Console(record=True, width=80, highlight=False)
    coordinator = PhaseCoordinator()
    coordinator.console = console

    coordinator._render_rich_hook_results("fast", _build_results())

    rendered = console.export_text()
    # Footer must always show the total
    assert "Issues found: 12" in rendered, (
        f"Footer 'Issues found: 12' missing from panel:\n{rendered}"
    )
    # The '12' must also appear in the failing row, not just the footer
    rows_with_12 = [line for line in rendered.splitlines() if "12" in line]
    assert len(rows_with_12) >= 2, (
        f"Expected issue count '12' to appear in both the row and footer, "
        f"found it in {len(rows_with_12)} lines:\n{rendered}"
    )


def test_fast_hook_results_panel_footer_unchanged() -> None:
    """The summary footer must still report Total/Passed/Failed/Issues found."""
    console = Console(record=True, width=80, highlight=False)
    coordinator = PhaseCoordinator()
    coordinator.console = console

    coordinator._render_rich_hook_results("fast", _build_results())

    rendered = console.export_text()
    assert "Total: 5" in rendered, f"Footer total missing:\n{rendered}"
    assert "Passed: 4" in rendered, f"Footer passed count missing:\n{rendered}"
    assert "Failed: 1" in rendered, f"Footer failed count missing:\n{rendered}"
    assert "Issues found:" in rendered, f"Footer 'Issues found:' missing:\n{rendered}"


def test_fast_hook_results_panel_fits_within_console_width() -> None:
    """All rendered rows must fit within a standard 80-column console.

    With ``get_console_width()`` defaulting to 70, no rendered line should
    exceed 70 characters of content. The footer line is the panel subtitle
    and is allowed to span up to the panel width.
    """
    console = Console(record=True, width=80, highlight=False)
    coordinator = PhaseCoordinator()
    coordinator.console = console

    coordinator._render_rich_hook_results("fast", _build_results())

    rendered = console.export_text()
    # Filter to body lines (those starting with the table side border)
    body_lines = [line for line in rendered.splitlines() if line.startswith("│ ")]
    assert body_lines, f"No body rows found in rendered panel:\n{rendered}"
    for line in body_lines:
        # Strip trailing border characters
        content = line.rstrip("│ ")
        assert len(content) <= 80, (
            f"Rendered row exceeds 80 columns ({len(content)}):\n{line!r}"
        )

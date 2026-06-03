from __future__ import annotations

from crackerjack.services.ai_fix_progress import AIFixProgressManager
from rich.console import Console


def test_ai_fix_progress_header_panel_has_no_simple_box_dividers() -> None:
    """The header panel must not render ║ column dividers from a SIMPLE-box inner table."""
    console = Console(record=True, width=80, highlight=False)
    manager = AIFixProgressManager(console=console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=58)

    rendered = console.export_text()
    assert "║" not in rendered, (
        f"Header panel still contains SIMPLE-box ║ column dividers:\n{rendered}"
    )


def test_ai_fix_progress_full_session_renders_single_header_and_footer() -> None:
    """A full start_fix_session → finish_session cycle must not duplicate the AI-ENGINE panel."""
    console = Console(record=True, width=80, highlight=False)
    manager = AIFixProgressManager(console=console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=58)
    manager.finish_session(success=False, iteration_count=5)

    rendered = console.export_text()
    engine_panel_count = rendered.count("CRACKERJACK AI-ENGINE v2.0")
    assert engine_panel_count == 1, (
        f"Expected exactly 1 AI-ENGINE header panel, got {engine_panel_count}:\n{rendered}"
    )

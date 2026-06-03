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


def test_ai_fix_progress_footer_panel_has_no_simple_box_dividers() -> None:
    """The footer panel must not render ║ column dividers — mirrors the
    header test. The fix in commit 2f56ec2d rewrote both panels; a regression
    in only the footer would slip past the header-only test.
    """
    console = Console(record=True, width=80, highlight=False)
    manager = AIFixProgressManager(console=console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=58)
    manager.finish_session(success=False, iteration_count=5)

    rendered = console.export_text()
    assert "║" not in rendered, (
        f"Footer panel still contains SIMPLE-box ║ column dividers:\n{rendered}"
    )


def test_ai_fix_progress_full_session_renders_single_header_and_footer() -> None:
    """A full start_fix_session → finish_session cycle must not duplicate the
    AI-ENGINE panel — and re-entry from retry paths (a second
    start_fix_session call) must also be silently ignored.

    The bug this guards: prior to the _fix_session_started fix, retry paths
    would call start_fix_session a second time and render a duplicate header.
    Calling start_fix_session twice here exercises that guard — without the
    guard, the second call would render a second header and the assertion
    would catch the regression.
    """
    console = Console(record=True, width=80, highlight=False)
    manager = AIFixProgressManager(console=console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=58)
    # Second call simulates a retry path re-entering the session; the
    # _fix_session_started guard should make it a no-op.
    manager.start_fix_session(stage="comprehensive", initial_issue_count=58)
    manager.finish_session(success=False, iteration_count=5)

    rendered = console.export_text()
    engine_panel_count = rendered.count("CRACKERJACK AI-ENGINE v2.0")
    assert engine_panel_count == 1, (
        f"Expected exactly 1 AI-ENGINE header panel, got {engine_panel_count}:\n{rendered}"
    )

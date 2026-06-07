from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rich.console import Console

from crackerjack.services.ai_fix_progress import AIFixProgressManager


@pytest.fixture
def manager() -> AIFixProgressManager:
    return AIFixProgressManager(console=Mock(spec=Console), enabled=False)


def test_compute_hook_total_skips_config_error_results(
    manager: AIFixProgressManager,
) -> None:
    semgrep_config_error = SimpleNamespace(
        name="semgrep", status="error", issues_count=4, is_config_error=True
    )
    refurb_failed = SimpleNamespace(
        name="refurb", status="failed", issues_count=20, is_config_error=False
    )
    zuban_failed = SimpleNamespace(
        name="zuban", status="failed", issues_count=34, is_config_error=False
    )
    gitleaks_passed = SimpleNamespace(
        name="gitleaks", status="passed", issues_count=0, is_config_error=False
    )

    hook_results = [
        semgrep_config_error,
        refurb_failed,
        zuban_failed,
        gitleaks_passed,
    ]

    assert manager.compute_hook_total(hook_results) == 54


def test_compute_hook_total_skips_passed_hooks(manager: AIFixProgressManager) -> None:
    """Bug: compute_hook_total (used by the AI Engine header) was including
    passed hooks in its sum, while the comprehensive-hook results panel
    (via ``_calculate_hook_statistics``) skipped them. The result was a
    visible discrepancy: the panel's ``Issues found: 20`` footer did not
    match the AI Engine's ``Issues: 23`` header.

    In the user's case, three passed comprehensive hooks each had
    ``issues_count = 1`` (warning-level findings that did not fail the
    hook). The panel hardcoded ``0`` for passed-hook rows and skipped
    them in the footer; the AI Engine summed them and reported 23.

    Fix: ``compute_hook_total`` must skip passed hooks (and config
    errors) so the two display surfaces agree. Both numbers should
    represent the same thing — issues the AI Engine will work on.
    """
    zuban = SimpleNamespace(
        name="zuban", status="failed", issues_count=1, is_config_error=False
    )
    pyscn = SimpleNamespace(
        name="pyscn", status="failed", issues_count=18, is_config_error=False
    )
    refurb = SimpleNamespace(
        name="refurb", status="failed", issues_count=1, is_config_error=False
    )
    # Passed hooks with non-zero issues_count — these are exactly the
    # cases that produced the 20 vs 23 discrepancy.
    gitleaks = SimpleNamespace(
        name="gitleaks", status="passed", issues_count=1, is_config_error=False
    )
    semgrep = SimpleNamespace(
        name="semgrep", status="passed", issues_count=1, is_config_error=False
    )
    creosote = SimpleNamespace(
        name="creosote", status="passed", issues_count=1, is_config_error=False
    )

    hook_results = [zuban, pyscn, refurb, gitleaks, semgrep, creosote]

    # Panel footer logic sums ONLY failed (non-passed, non-config-error)
    # hooks: 1 + 18 + 1 = 20.
    panel_total = sum(
        r.issues_count
        for r in hook_results
        if r.status != "passed"
        and not (getattr(r, "is_config_error", False))
        and hasattr(r, "issues_count")
    )
    assert panel_total == 20

    # compute_hook_total must return the SAME number as the panel.
    assert manager.compute_hook_total(hook_results) == panel_total
    assert manager.compute_hook_total(hook_results) == 20


def test_compute_hook_total_matches_panel_for_realistic_results(
    manager: AIFixProgressManager,
) -> None:
    """Reproduces the exact 9-hook comprehensive output the user reported:
    6 passed, 3 failed, with 1+18+1 issues on the failed hooks. The AI
    Engine header and the panel footer must agree.
    """
    hook_results = [
        SimpleNamespace(
            name="gitleaks", status="passed", issues_count=0, is_config_error=False
        ),
        SimpleNamespace(
            name="zuban", status="failed", issues_count=1, is_config_error=False
        ),
        SimpleNamespace(
            name="check-jsonschema",
            status="passed",
            issues_count=0,
            is_config_error=False,
        ),
        SimpleNamespace(
            name="pyscn", status="failed", issues_count=18, is_config_error=False
        ),
        SimpleNamespace(
            name="lychee", status="passed", issues_count=0, is_config_error=False
        ),
        SimpleNamespace(
            name="linkcheckmd",
            status="passed",
            issues_count=0,
            is_config_error=False,
        ),
        SimpleNamespace(
            name="semgrep", status="passed", issues_count=0, is_config_error=False
        ),
        SimpleNamespace(
            name="creosote", status="passed", issues_count=0, is_config_error=False
        ),
        SimpleNamespace(
            name="refurb", status="failed", issues_count=1, is_config_error=False
        ),
    ]

    assert manager.compute_hook_total(hook_results) == 20


def test_compute_hook_total_still_includes_failed_with_zero_status(
    manager: AIFixProgressManager,
) -> None:
    """Defensive: a status other than 'passed'/'failed' (e.g. 'timeout',
    'error') must still contribute. The fix to skip passed hooks
    shouldn't over-skip.
    """
    timed_out = SimpleNamespace(
        name="slow-hook", status="timeout", issues_count=7, is_config_error=False
    )
    passed = SimpleNamespace(
        name="fast-hook", status="passed", issues_count=3, is_config_error=False
    )

    # 7 (timeout, not skipped) + 0 (passed, skipped) = 7
    assert manager.compute_hook_total([timed_out, passed]) == 7


def test_compute_hook_total_falls_back_to_issues_found(
    manager: AIFixProgressManager,
) -> None:
    """If ``issues_count`` is missing but ``issues_found`` is present,
    fall back to its length. Mirrors ``_calculate_hook_statistics``.
    """
    no_count = SimpleNamespace(
        name="ad-hoc",
        status="failed",
        is_config_error=False,
        issues_found=["a", "b", "c", "d", "e"],
    )
    assert manager.compute_hook_total([no_count]) == 5


def test_finish_session_uses_explicit_iteration_count() -> None:
    """Bug 3: footer must show the loop's actual iteration count, not len(issue_history).

    Uses a recording Console instead of the `manager` fixture (which uses
    `enabled=False` and a Mock console) so we can inspect the actual rendered
    text. The Mock-console approach is unsafe here because `console.print`
    receives Rich renderables, not strings — `"".join(call.args[0] for ...)`
    would crash with `TypeError: sequence item 0: expected str instance, ...`
    """
    record_console = Console(record=True, width=80, highlight=False)
    manager = AIFixProgressManager(console=record_console, enabled=True)
    manager.issue_history = [62, 62, 20, 20, 20, 20, 20]
    manager.start_fix_session(stage="comprehensive", initial_issue_count=62)
    manager.finish_session(success=False, iteration_count=5)

    rendered = record_console.export_text()
    assert "Iterations: 5" in rendered
    assert "Iterations: 7" not in rendered


def test_ai_engine_panel_is_70_wide_and_tracks_iterations() -> None:
    """Bug: the AI-ENGINE header panel was capped at min(42, console width)
    — too narrow to see iteration / last-iter-fixed / outstanding
    fields without wrapping. The user wanted the panel stretched to
    70 characters (matching the comprehensive-hook results panel) and
    enriched with live iteration progress that re-renders on every
    ``start_iteration`` call.
    """
    record_console = Console(record=True, width=120, highlight=False)
    manager = AIFixProgressManager(console=record_console, enabled=True)

    manager.start_fix_session(stage="comprehensive", initial_issue_count=20)

    # Re-rendering during iteration 0 is suppressed to avoid duplicating
    # the panel that start_fix_session already produced.
    manager.start_iteration(iteration=0, issue_count=20)
    manager.start_iteration(iteration=1, issue_count=12)  # fixed 8
    manager.start_iteration(iteration=2, issue_count=5)   # fixed 7

    rendered = record_console.export_text()

    # The initial panel shows: Stage, Iteration (1-indexed), Issues,
    # Outstanding — but no "Last iter fixed" line yet.
    assert "Stage: COMPREHENSIVE" in rendered
    assert "Iteration: 1" in rendered
    assert "Issues: 20" in rendered
    assert "Outstanding: 20" in rendered
    # The initial panel must NOT have a "Last iter fixed" line —
    # there is no prior iteration to compare against.
    first_panel = rendered.split("╰")[0]
    assert "Last iter fixed" not in first_panel

    # Iteration 2 panel (the second panel, after iter 0's 8 fixes):
    # Iteration: 2, Last iter fixed: 8, Outstanding: 12.
    assert "Iteration: 2" in rendered
    assert "Last iter fixed: 8" in rendered
    assert "Outstanding: 12" in rendered

    # Iteration 3 panel: Last iter fixed 7, Outstanding 5.
    assert "Iteration: 3" in rendered
    assert "Last iter fixed: 7" in rendered
    assert "Outstanding: 5" in rendered


def test_ai_engine_panel_iteration_uses_n_plus_one_numbering() -> None:
    """Bug: the panel showed ``Iteration: 0`` for the first iteration
    (0-indexed). The user wanted the first iteration to be called
    ``Iteration: 1`` (n+1) for a cleaner UI effect. The engine is
    still 0-indexed internally; only the display changes.
    """
    record_console = Console(record=True, width=120, highlight=False)
    manager = AIFixProgressManager(console=record_console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=10)
    manager.start_iteration(iteration=0, issue_count=10)
    manager.start_iteration(iteration=1, issue_count=8)
    manager.start_iteration(iteration=2, issue_count=5)

    rendered = record_console.export_text()

    # First panel: Iteration 1 (the engine is about to do "iteration 0
    # internally", which is the user's "Iteration 1").
    assert "Iteration: 1" in rendered
    # Second panel: Iteration 2.
    assert "Iteration: 2" in rendered
    # Third panel: Iteration 3.
    assert "Iteration: 3" in rendered
    # The 0-indexed display must NOT leak through.
    assert "Iteration: 0" not in rendered


def test_ai_engine_panel_last_iter_fixed_ignores_intra_iteration_updates() -> None:
    """Bug: ``update_iteration_progress`` was appending to
    ``issue_history``, polluting the per-iteration outstanding count
    used by the panel. With 20 → 15 → 5 → 3 (intra-iter progress)
    in iter 0, the iter-1 panel incorrectly reported
    ``Last iter fixed: 0`` (diff between the last two issue_history
    entries, both = 3) instead of 17.

    The fix uses a separate ``_iter_outstandings`` list that is
    only appended to in ``start_iteration``, so the per-iteration
    outstanding is the canonical value at the iteration boundary.
    """
    record_console = Console(record=True, width=120, highlight=False)
    manager = AIFixProgressManager(console=record_console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=20)

    # Iter 0: started with 20, intra-iter updates 15, 5, 3.
    manager.start_iteration(iteration=0, issue_count=20)
    manager.update_iteration_progress(iteration=0, issues_remaining=15)
    manager.update_iteration_progress(iteration=0, issues_remaining=5)
    manager.update_iteration_progress(iteration=0, issues_remaining=3)

    # Iter 1: started with 3 (the canonical end-of-iter-0 count).
    manager.start_iteration(iteration=1, issue_count=3)
    manager.update_iteration_progress(iteration=1, issues_remaining=2)

    rendered = record_console.export_text()

    # The iter-2 panel (rendered when iter 1 starts) must show the
    # CORRECT delta — 17, not 0.
    assert "Last iter fixed: 17" in rendered, (
        f"Expected 'Last iter fixed: 17' but rendered was:\n{rendered}"
    )
    assert "Outstanding: 3" in rendered


def test_ai_engine_panel_last_iter_fixed_clamps_negative_to_zero() -> None:
    """If the outstanding count INCREASES between iterations (e.g. a
    previous fix surfaced a new issue), ``Last iter fixed`` should
    clamp to 0 rather than show a negative number.
    """
    record_console = Console(record=True, width=120, highlight=False)
    manager = AIFixProgressManager(console=record_console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=5)
    manager.start_iteration(iteration=0, issue_count=5)
    # New issue surfaced, count went UP.
    manager.start_iteration(iteration=1, issue_count=7)

    rendered = record_console.export_text()
    assert "Last iter fixed: 0" in rendered
    assert "Outstanding: 7" in rendered


def test_ai_engine_panel_width_is_70() -> None:
    """The panel's declared width must be 70 to match the
    comprehensive-hook results panel. Rich's ``Panel(width=70)``
    produces a 70-character total rendered line (68 chars of
    content + 1 left border + 1 right border), so the longest
    line in the output should be exactly 70 chars (not the
    old narrow min(42, console width)).
    """
    record_console = Console(record=True, width=200, highlight=False)
    manager = AIFixProgressManager(console=record_console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=20)
    manager.start_iteration(iteration=1, issue_count=12)

    rendered = record_console.export_text()
    # Find the longest rendered line — it should be 70 chars
    # (panel content) + 2 (left/right borders) = 70 total.
    max_line_len = max(len(line) for line in rendered.splitlines())
    assert max_line_len == 70, (
        f"AI-ENGINE panel must be exactly 70 chars wide, got "
        f"{max_line_len} chars:\n{rendered}"
    )


def test_footer_hides_reduction_when_no_iterations_ran() -> None:
    """Bug #2: do not claim 'Reduction: X%' when iteration_count == 0.

    When the AI engine produces no fix plans (iteration 0 exits via the
    'no plans' early return), the apparent reduction from initial to
    current is purely the result of deduplication and filtering — not
    any actual fix. Showing 'Reduction: 53%' for what is really 'we
    deduped the raw count' misleads the user into thinking fixes were
    applied.

    The footer must instead show a status line that makes the lack of
    fixes obvious: 'Status: No fixes attempted' or equivalent.
    """
    record_console = Console(record=True, width=80, highlight=False)
    manager = AIFixProgressManager(console=record_console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=19)
    # Simulate the dhara flow: iteration 0 reports 9 issues (post-dedup
    # count, after _collect_fixable_issues ran). Empty plans cause
    # early return, so iteration_count=0 is passed to finish_session.
    manager.start_iteration(iteration=0, issue_count=9)
    manager.finish_session(success=False, iteration_count=0)

    rendered = record_console.export_text()
    assert "Reduction:" not in rendered, (
        f"Footer should not show 'Reduction:' when iteration_count=0. "
        f"Rendered output:\n{rendered}"
    )
    assert "No fixes attempted" in rendered, (
        f"Footer should explicitly state no fixes were attempted. "
        f"Rendered output:\n{rendered}"
    )
    # Sanity: the actual issue count is still shown so the user can see
    # what was queued and what remained.
    assert "Issues:" in rendered
    assert "19" in rendered
    assert "9" in rendered


def test_footer_shows_reduction_when_iteration_count_positive() -> None:
    """Bug #2: when iteration_count > 0, 'Reduction: X%' is appropriate.

    This is the legacy behaviour: if the AI engine actually iterated
    at least once and the issue count went down, the percentage tells
    the user how much progress was made. We must NOT regress this
    case.
    """
    record_console = Console(record=True, width=80, highlight=False)
    manager = AIFixProgressManager(console=record_console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=50)
    manager.start_iteration(iteration=0, issue_count=30)
    manager.start_iteration(iteration=1, issue_count=20)
    manager.start_iteration(iteration=2, issue_count=20)
    manager.start_iteration(iteration=3, issue_count=20)
    manager.finish_session(success=False, iteration_count=4)

    rendered = record_console.export_text()
    # 50 → 20 = 30/50 = 60% reduction
    assert "Reduction: 60%" in rendered
    assert "Iterations: 4" in rendered


def test_footer_hides_reduction_when_iterations_ran_but_count_unchanged() -> None:
    """Bug #2: edge case — iterations ran but no progress was made.

    If the loop iterated (iteration_count > 0) but the issue count did
    not decrease, the 'Reduction: 0%' line is technically true but
    useless noise. The user already sees 'Iterations: N' and the
    unchanged 'Issues: A → A' line. Hiding the reduction line keeps
    the footer tight.
    """
    record_console = Console(record=True, width=80, highlight=False)
    manager = AIFixProgressManager(console=record_console, enabled=True)
    manager.start_fix_session(stage="comprehensive", initial_issue_count=20)
    for i in range(4):
        manager.start_iteration(iteration=i, issue_count=20)
    manager.finish_session(success=False, iteration_count=4)

    rendered = record_console.export_text()
    # When no reduction happened, the line should be hidden (or show a
    # clear non-reduction status). We accept either: the legacy "Reduction:
    # 0%" or the new "No reduction" — but it must NOT claim a positive
    # reduction.
    assert "Reduction:" not in rendered or "Reduction: 0%" in rendered


def test_log_event_uses_rich_markup_not_raw_ansi() -> None:
    """Bug: _neon_print and log_warning used raw ANSI escape sequences
    (``\\033[96m``) instead of Rich markup. When the escape character
    was stripped by a downstream logger or terminal filter, the
    rendered output showed bare ``[96m…[0m`` fragments with missing
    closing brackets, breaking colour rendering and emitting literal
    noise into the user's console.

    The fix is to use Rich tags (e.g. ``[bright_cyan]…[/bright_cyan]``)
    which are valid markup that Rich can re-parse and that survives
    any downstream ANSI stripper that targets raw escape characters.

    We test the contract by stubbing the Neon constants with realistic
    raw-ANSI values (mimicking what a real terminal would see) and
    asserting the strings passed to ``console.print`` contain Rich
    markup, not bare escape codes.
    """
    from crackerjack.services import ai_fix_progress as progress_mod

    # Force colour-enabled state by patching the class attributes
    # directly. (The real Neon constants are evaluated at class-
    # definition time, so we can't flip the module-level flag and
    # expect the class to re-evaluate.)
    original_attrs = {
        "CYAN": progress_mod.Neon.CYAN,
        "GREEN": progress_mod.Neon.GREEN,
        "YELLOW": progress_mod.Neon.YELLOW,
        "RED": progress_mod.Neon.RED,
        "RESET": progress_mod.Neon.RESET,
    }
    progress_mod.Neon.CYAN = "\x1b[96m"
    progress_mod.Neon.GREEN = "\x1b[92m"
    progress_mod.Neon.YELLOW = "\x1b[93m"
    progress_mod.Neon.RED = "\x1b[91m"
    progress_mod.Neon.RESET = "\x1b[0m"
    try:
        record_console = Console(record=True, width=120, highlight=False)
        manager = AIFixProgressManager(console=record_console, enabled=True)

        # Exercise every severity branch in _neon_print, plus log_warning.
        manager.log_event(
            agent="RefactoringAgent",
            action="Executing plan",
            file="type_error_specialist.py",
        )
        manager.log_event(
            agent="ValidationCoordinator",
            action="Validated successfully",
            file="type_error_specialist.py",
            severity="success",
        )
        manager.log_event(
            agent="FixerCoordinator",
            action="Fix failed: missing import",
            file="foo.py",
            severity="warning",
        )
        manager.log_event(
            agent="SecurityAgent",
            action="Skip",
            file="bar.py",
            severity="error",
        )
        manager.log_warning("something looked off")

        rendered = record_console.export_text()
        # With the fix in place: no raw ANSI escape characters should
        # survive (Rich markup uses named tags like ``bright_cyan``).
        assert "\x1b[" not in rendered, (
            f"Output should not contain raw ANSI escape sequences. "
            f"Rendered output:\n{rendered}"
        )
        # The "bare [NNm" pattern the user reported must not appear.
        assert "[96m" not in rendered
        assert "[92m" not in rendered
        assert "[0m" not in rendered
        # The actual content should still be there.
        assert "Refactoring" in rendered
        assert "Executing plan" in rendered
        assert "ValidationCoordinator" in rendered
        assert "Validated successfully" in rendered
    finally:
        for name, value in original_attrs.items():
            setattr(progress_mod.Neon, name, value)


def test_log_warning_uses_rich_markup_not_raw_ansi() -> None:
    """Companion test for log_warning: it must also use Rich markup
    rather than raw ANSI codes.
    """
    from crackerjack.services import ai_fix_progress as progress_mod

    original_yellow = progress_mod.Neon.YELLOW
    original_reset = progress_mod.Neon.RESET
    progress_mod.Neon.YELLOW = "\x1b[93m"
    progress_mod.Neon.RESET = "\x1b[0m"
    try:
        record_console = Console(record=True, width=120, highlight=False)
        manager = AIFixProgressManager(console=record_console, enabled=True)
        manager.log_warning("oops")
        rendered = record_console.export_text()
        assert "\x1b[" not in rendered
        assert "[93m" not in rendered
        assert "[0m" not in rendered
        assert "oops" in rendered
    finally:
        progress_mod.Neon.YELLOW = original_yellow
        progress_mod.Neon.RESET = original_reset

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

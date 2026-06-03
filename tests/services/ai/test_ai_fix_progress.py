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

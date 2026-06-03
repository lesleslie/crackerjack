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

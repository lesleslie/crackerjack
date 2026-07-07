"""Backward-compat shim for ``AIFixProgressManager`` (PR 0 retirement).

Before PR 0, ``AutofixCoordinator`` carried both a rich ``AIFixProgressManager``
(neon-style panel) and an event-driven ``AIFixDashboard``. PR 0 collapses
the two surfaces to the dashboard alone.

This module preserves the public attribute surface (``progress_manager``,
``compute_hook_total``, ``is_in_progress``, etc.) so external callers and
tests don't need to change in one step. All methods are no-ops; the
behavioural replacement is now the event bus + dashboard + log lines.

The full 481-LOC implementation was retired; the new code is the
``_NoOpProgressShim`` below.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class _NoOpProgressShim:
    """Drop-in replacement for ``AIFixProgressManager`` after PR 0.

    All formatting/state methods are no-ops. The only methods that retain
    their pre-PR-0 behaviour are ``compute_hook_total`` (a pure function
    over hook results) and the ``enabled`` flag.
    """

    def __init__(
        self,
        console: Any | None = None,
        enabled: bool = True,
        enable_agent_bars: bool = True,
        max_agent_bars: int = 5,
        activity_feed_size: int = 5,
        refresh_per_second: int = 1,
    ) -> None:
        # ``enable_agent_bars`` etc. were consumed by the old visual
        # implementation; they're accepted here so legacy callers and
        # test fixtures that pass them keep working.
        self.console = console
        self.enabled = enabled
        self.enable_agent_bars = enable_agent_bars

    # --- counters / state ----------------------------------------------------

    def is_in_progress(self) -> bool:
        return False

    def is_enabled(self) -> bool:
        return self.enabled

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False

    def should_skip_console_print(self) -> bool:
        # Pre-PR-0: True when an iteration panel was active.
        # Post-PR-0: always False — the dashboard handles all TUI.
        return False

    # --- pure helpers (kept real) -------------------------------------------

    def compute_hook_total(self, hook_results: Sequence[object]) -> int:
        """Sum issues across non-passed, non-config-error hooks.

        Mirrors the pre-PR-0 contract used by the AI-fix header to size
        "initial issues". Lives here (not on the dashboard) because it's
        called before any event is emitted.
        """
        total = 0
        for result in hook_results:
            status = getattr(result, "status", "")
            if isinstance(status, str) and status.lower() in {"passed", "success"}:
                continue
            if getattr(result, "is_config_error", False):
                continue
            if hasattr(result, "issues_count"):
                total += getattr(result, "issues_count", 0) or 0
            elif getattr(result, "issues_found", None):
                total += len(getattr(result, "issues_found"))
        return total

    # --- formerly visual no-ops ----------------------------------------------

    def log_warning(self, message: str) -> None:
        return None

    def log_event(
        self,
        agent: str,
        action: str,
        file: str | object,
        severity: str = "info",
        issue_type: str = "",
    ) -> None:
        return None

    async def async_log_event(
        self,
        agent: str,
        action: str,
        file: str | object,
        severity: str = "info",
        issue_type: str = "",
    ) -> None:
        return None

    def start_fix_session(
        self,
        stage: str = "fast",
        initial_issue_count: int = 0,
    ) -> None:
        return None

    def start_iteration(self, iteration: int, issue_count: int) -> None:
        return None

    def update_iteration_progress(
        self,
        iteration: int,
        issues_remaining: int,
        no_progress_count: int = 0,
    ) -> None:
        return None

    def end_iteration(self) -> None:
        return None

    def finish_session(
        self,
        *,
        success: bool = True,
        message: str = "",
        iteration_count: int | None = None,
    ) -> None:
        return None

    def update_bar_text(self, text: str | object) -> None:
        return None

    def start_agent_bars(self, agent_names: list[str]) -> None:
        return None

    def update_agent_progress(
        self,
        agent_name: str,
        completed: int,
        total: int,
        current_file: str | None = None,
        current_issue_type: str | None = None,
    ) -> None:
        return None

    def end_agent_bars(self) -> None:
        return None

    def start_comprehensive_hooks_session(self, hook_names: list[str]) -> None:
        return None

    def update_hook_progress(
        self,
        hook_name: str,
        status: str,
        elapsed: float,
        issues_found: int = 0,
    ) -> None:
        return None

    def get_hook_summary(self) -> dict[str, Any]:
        return {"total": 0, "completed": 0, "progress": 0, "hooks": {}}

    def progress_context(self, total: int, title: str = "AI-FIX"):  # type: ignore[no-untyped-def]
        from contextlib import nullcontext

        return nullcontext()


# Public alias — kept so old tests that imported the name still load.
AIFixProgressManager = _NoOpProgressShim

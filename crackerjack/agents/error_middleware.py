"""Shared error-handling middleware helpers for agents."""

from __future__ import annotations

import typing as t
from functools import wraps

from rich.console import Console

from crackerjack.agents.base import FixResult, Issue, SubAgent

if t.TYPE_CHECKING:  # pragma: no cover - typing helpers
    from crackerjack.agents.coordinator import AgentCoordinator


def agent_error_boundary(
    func: t.Callable[..., t.Awaitable[FixResult]],
) -> t.Callable[..., t.Awaitable[FixResult]]:
    """Decorator that centralizes error handling for agent execution.

    Ensures all agent failures are logged consistently and converted into a
    ``FixResult`` that upstream orchestrators can reason about without custom
    ``try``/``except`` blocks.
    """

    @wraps(func)
    async def wrapper(
        self: AgentCoordinator,
        agent: SubAgent,
        issue: Issue,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> FixResult:
        try:
            return await func(self, agent, issue, *args, **kwargs)
        except Exception as exc:  # pragma: no cover - exercised via decorator tests
            console: Console | None = getattr(self.context, "console", None)
            message = f"{agent.name} encountered an error while processing issue {issue.id}: {exc}"
            self.logger.exception(message, exc_info=exc)
            if console is not None:
                console.print(f"[red]{message}[/red]")

            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[message],
                recommendations=[
                    "Review agent logs for stack trace",
                    "Re-run with --debug to capture additional context",
                ],
            )

    return wrapper

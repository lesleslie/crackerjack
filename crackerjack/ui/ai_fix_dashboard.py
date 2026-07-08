from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from crackerjack.core.ai_fix_events import (
    AgentDispatched,
    AIFixEvent,
    FixSessionFinished,
    FixSessionStarted,
    IssueFailed,
    IssueResolved,
    IterationFinished,
    IterationStarted,
    PreflightFinished,
    RunFinished,
    RunStarted,
    TierTransitioned,
)


@dataclass
class _AgentRow:
    issue_type: str
    dispatched: int = 0
    resolved: int = 0
    failed: int = 0
    active: list[str] = field(default_factory=list)


@dataclass
class _DashboardState:
    run_id: str = ""
    iteration: int = 0
    max_iterations: int = 10
    strategy: str = ""
    start_time: float = field(default_factory=time.monotonic)
    preflight_saved: int = 0
    last_activity: str = ""
    total_resolved: int = 0
    total_failed: int = 0
    agents: dict[str, _AgentRow] = field(default_factory=dict)
    finished: bool = False
    session_started_count: int = 0
    session_finished_count: int = 0
    total_no_op_count: int = 0

    def _row(self, issue_type: str) -> _AgentRow:
        if issue_type not in self.agents:
            self.agents[issue_type] = _AgentRow(issue_type=issue_type)
        return self.agents[issue_type]

    def elapsed_s(self) -> float:
        return time.monotonic() - self.start_time

    def elapsed_str(self) -> str:
        s = int(self.elapsed_s())
        return f"{s // 60:02d}:{s % 60:02d}"


def _build_renderable(state: _DashboardState) -> Panel:
    short_id = state.run_id[-6:] if len(state.run_id) >= 6 else state.run_id
    header = Text(
        f"iteration {state.iteration}/{state.max_iterations}"
        + (f" · {state.strategy}" if state.strategy else "")
        + f" · elapsed {state.elapsed_str()}"
        + (
            f" · preflight saved {state.preflight_saved}"
            if state.preflight_saved
            else ""
        ),
        style="dim",
    )

    table = Table.grid(padding=(0, 1))
    table.add_column("Agent", min_width=16)
    table.add_column("Dispatched", justify="right", min_width=10)
    table.add_column("Resolved", justify="right", min_width=9)
    table.add_column("Failed", justify="right", min_width=7)
    table.add_column("Bar", min_width=12)
    table.add_column("Status", min_width=20)

    for row in sorted(state.agents.values(), key=lambda r: r.dispatched, reverse=True):
        filled = row.resolved
        empty = max(0, row.dispatched - row.resolved - row.failed)
        bar = "█" * filled + "░" * empty
        if row.active:
            agent_label = f"⏵ {', '.join(row.active[:2])}"
            if len(row.active) > 2:
                agent_label += f" (+{len(row.active) - 2})"
            status_style = "yellow"
        elif row.resolved >= row.dispatched and row.dispatched > 0:
            agent_label = "✔"
            status_style = "green"
        else:
            agent_label = "queued" if row.dispatched == 0 else "—"
            status_style = "dim"

        table.add_row(
            Text(row.issue_type, style="bold"),
            str(row.dispatched),
            Text(str(row.resolved), style="green"),
            Text(str(row.failed), style="red" if row.failed else "dim"),
            Text(bar[:12], style="cyan"),
            Text(agent_label, style=status_style),
        )

    footer = Text(
        f"resolved {state.total_resolved} · failed {state.total_failed}",
        style="dim",
    )


    if state.session_started_count or state.total_no_op_count:
        footer.append(
            f" · sessions {state.session_finished_count}/{state.session_started_count}",
            style="dim",
        )
        if state.total_no_op_count:
            footer.append(
                f" · no-op {state.total_no_op_count}",
                style="yellow",
            )

    body = Table.grid()
    body.add_row(header)
    body.add_row(table)
    body.add_row(footer)
    if state.last_activity:
        body.add_row(Text(f"last: {state.last_activity}", style="dim italic"))

    return Panel(
        body,
        title=f"[bold cyan]Crackerjack · AI Fix · run {short_id}[/]",
        border_style="cyan",
        width=70,
    )


class AIFixDashboard:
    def __init__(
        self,
        console: Console | None = None,
        max_iterations: int = 10,
    ) -> None:
        self._console = console or Console()
        self._state = _DashboardState(max_iterations=max_iterations)
        self._live: Live | None = None

    def start(self) -> None:
        self._live = Live(
            _build_renderable(self._state),
            console=self._console,
            refresh_per_second=10,
            transient=True,
        )
        self._live.start()

    def stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    async def handle(self, event: AIFixEvent) -> None:
        self._update(event)
        if self._live is not None:
            self._live.update(_build_renderable(self._state))

    def _update(self, event: AIFixEvent) -> None:
        if isinstance(event, RunStarted):
            self._state.run_id = event.run_id
            self._state.strategy = event.stage
            self._state.start_time = time.monotonic()

        elif isinstance(event, IterationStarted):
            self._state.iteration = event.iteration
            self._state.strategy = event.strategy or self._state.strategy

        elif isinstance(event, AgentDispatched):
            row = self._state._row(event.agent)
            row.dispatched += 1
            if event.agent not in row.active:
                row.active.append(event.agent)

        elif isinstance(event, IssueResolved):
            row = self._state._row(event.agent)
            row.resolved += 1
            row.active = [a for a in row.active if a != event.agent]
            self._state.total_resolved += 1
            self._state.last_activity = (
                f"{event.agent} fixed {event.file} ({event.duration_s:.1f}s)"
            )

        elif isinstance(event, IssueFailed):
            row = self._state._row(event.agent)
            row.failed += 1
            row.active = [a for a in row.active if a != event.agent]
            self._state.total_failed += 1
            self._state.last_activity = (
                f"{event.agent} failed on {event.file}: {event.reason[:40]}"
            )

        elif isinstance(event, PreflightFinished):
            self._state.preflight_saved += event.issues_saved

        elif isinstance(event, IterationFinished):
            pass

        elif isinstance(event, RunFinished):
            self._state.finished = True

        elif isinstance(event, FixSessionStarted):
            self._state.session_started_count += 1
            self._state.last_activity = f"start {event.issue_type} in {event.file}"

        elif isinstance(event, FixSessionFinished):
            self._state.session_finished_count += 1
            self._state.total_no_op_count += event.no_op_count
            outcome = "resolved" if event.success else "failed"
            self._state.last_activity = (
                f"{outcome} {event.file} (no-ops={event.no_op_count})"
            )

        elif isinstance(event, TierTransitioned):


            self._state.last_activity = (
                f"tier {event.from_tier}→{event.to_tier} on {event.file}"
            )

    def render_text(self) -> str:
        console = Console(force_terminal=True, width=80, highlight=False)
        with console.capture() as cap:
            console.print(_build_renderable(self._state))
        return cap.get()


def should_activate(mode: str = "auto") -> bool:
    if mode == "on":
        return True
    if mode == "off":
        return False

    if os.environ.get("CRACKERJACK_NO_TUI"):
        return False
    if os.environ.get("CI"):
        return False
    return sys.stdout.isatty()


def attach_dashboard(
    bus: object, mode: str = "auto", max_iterations: int = 10
) -> AIFixDashboard | None:
    if not should_activate(mode):
        return None

    from crackerjack.core.ai_fix_event_bus import AIFixEventBus

    if not isinstance(bus, AIFixEventBus):
        return None

    dashboard = AIFixDashboard(max_iterations=max_iterations)
    bus.subscribe(dashboard)
    dashboard.start()
    return dashboard

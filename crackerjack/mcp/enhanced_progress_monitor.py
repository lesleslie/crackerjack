import asyncio
import time
import typing as t
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from acb.console import Console
from acb.depends import depends
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Label, ProgressBar

from .progress_components import (
    JobDataCollector,
    ServiceManager,
    TerminalRestorer,
)


class MetricCard(Widget):
    value = reactive(" --")
    label = reactive("Metric")
    trend = reactive("")
    color = reactive("white")

    def __init__(
        self,
        label: str,
        value: str = " --",
        trend: str = "",
        color: str = "white",
        **kwargs: t.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label = label
        self.value = value
        self.trend = trend
        self.color = color

    def render(self) -> str:
        trend_icon = self.trend or ""
        return f"[{self.color}]{self.label}[/]\n[bold {self.color}]{self.value}[/] {trend_icon}"


class AgentActivityWidget(Widget):
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self.border_title = "🤖 AI Agent Activity"
        self.border_title_align = "left"

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="agent-metrics"):
                yield MetricCard(
                    "Active Agents",
                    "0",
                    color="cyan",
                    id="active-agents-metric",
                )
                yield MetricCard(
                    "Issues Fixed",
                    "0",
                    "↑",
                    color="green",
                    id="issues-fixed-metric",
                )
                yield MetricCard(
                    "Confidence",
                    "0%",
                    color="yellow",
                    id="confidence-metric",
                )
                yield MetricCard(
                    "Cache Hits",
                    "0",
                    color="magenta",
                    id="cache-hits-metric",
                )

            yield DataTable(id="agents-detail-table")

            yield Label("⏸️ Coordinator: Idle", id="coordinator-status-bar")

    def on_mount(self) -> None:
        table = self.query_one("#agents-detail-table", DataTable)
        table.add_columns(
            "Agent",
            "Status",
            "Type",
            "Conf.",
            "Time",
        )
        # Setting widths for columns if needed would be done separately
        table.zebra_stripes = True
        table.styles.max_height = 6

    def update_metrics(self, data: dict[str, t.Any]) -> None:
        with suppress(Exception):
            activity = data.get("agent_activity", {})
            activity.get("agent_registry", {})
            active_agents = activity.get("active_agents", [])

            active_count = len(active_agents)
            self.query_one("#active-agents-metric", MetricCard).value = str(
                active_count,
            )

            total_fixed = sum(agent.get("issues_fixed", 0) for agent in active_agents)
            avg_confidence = sum(
                agent.get("confidence", 0) for agent in active_agents
            ) / max(active_count, 1)
            cache_hits = activity.get("cache_hits", 0)

            self.query_one("#issues-fixed-metric", MetricCard).value = str(
                total_fixed,
            )
            self.query_one(
                "#confidence-metric",
                MetricCard,
            ).value = f"{avg_confidence: .0%}"
            self.query_one("#cache-hits-metric", MetricCard).value = str(cache_hits)

            self._update_coordinator_status(activity)

            self._update_agent_table(active_agents)

    def _update_coordinator_status(self, activity: dict[str, t.Any]) -> None:
        status = activity.get("coordinator_status", "idle")
        total_agents = activity.get("agent_registry", {}).get("total_agents", 0)

        status_icons = {"active": "🟢", "processing": "🔄", "idle": "⏸️", "error": "🔴"}

        icon = status_icons.get(status) or "⏸️"
        status_bar = self.query_one("#coordinator-status-bar", Label)
        status_bar.update(
            f"{icon} Coordinator: {status.title()} ({total_agents} agents available)",
        )

    def _update_agent_table(self, agents: list[t.Any]) -> None:
        table = self.query_one("#agents-detail-table", DataTable)
        table.clear()

        if not agents:
            table.add_row("No active agents", "-", "-", "-", "-")
            return

        for agent in agents:
            name = agent.get("agent_type", "Unknown")
            status = agent.get("status", "idle")
            issue_type = agent.get("issue_type", "-")
            confidence = f"{agent.get('confidence', 0): .0%}"
            time_elapsed = f"{agent.get('processing_time', 0): .1f}s"

            status_emoji = {
                "processing": "🔄",
                "success": "✅",
                "failed": "❌",
                "idle": "⏸️",
            }.get(status, "❓")

            agent_emoji = {
                "FormattingAgent": "🎨",
                "SecurityAgent": "🛡️",
                "TestCreationAgent": "🧪",
                "TestSpecialistAgent": "🔬",
                "RefactoringAgent": "🔧",
                "ImportOptimizationAgent": "📦",
            }.get(name, "🤖")

            table.add_row(
                f"{agent_emoji} {name}",
                f"{status_emoji} {status}",
                issue_type,
                confidence,
                time_elapsed,
            )


class JobProgressPanel(Widget):
    def __init__(self, job_data: dict[str, t.Any], **kwargs) -> None:
        super().__init__(**kwargs)
        self.job_data = job_data
        self.start_time = time.time()

    def compose(self) -> ComposeResult:
        project = self.job_data.get("project", "unknown")
        job_id = self.job_data.get("job_id", "unknown")[:8]

        status = self.job_data.get("status", "").lower()
        status_emoji = {
            "running": "🔄",
            "completed": "✅",
            "failed": "❌",
            "pending": "⏳",
        }.get(status, "❓")

        self.border_title = f"{status_emoji} {project} [{job_id}]"
        self.border_title_align = "left"

        with Horizontal():
            with Vertical(id="job-progress-section"):
                for widget in self._compose_progress_section():
                    yield widget

            with Vertical(id="job-metrics-section"):
                for widget in self._compose_metrics_section():
                    yield widget

    def _compose_progress_section(self) -> ComposeResult:
        iteration = self.job_data.get("iteration", 1)
        max_iterations = self.job_data.get("max_iterations", 10)
        progress = self.job_data.get("progress", 0)

        stage = self.job_data.get("stage", "Unknown")
        status = self.job_data.get("status", "Unknown")

        yield Label(f"Stage: {stage}", classes="stage-label")
        yield Label(f"Status: {status}", classes="status-label")
        yield Label(f"Iteration: {iteration} / {max_iterations}")

        progress_bar = ProgressBar(
            total=100,
            id=f"job-progress-{self.job_data.get('job_id', 'unknown')}",
        )
        progress_bar.progress = progress  # Set progress after creating the widget
        yield progress_bar

        elapsed = time.time() - self.start_time
        yield Label(f"⏱️ Elapsed: {self._format_time(elapsed)}")

    def _compose_metrics_section(self) -> ComposeResult:
        total_issues = self.job_data.get("total_issues", 0)
        fixed = self.job_data.get("errors_fixed", 0)
        remaining = max(0, total_issues - fixed)

        with Horizontal(classes="metrics-grid"):
            yield MetricCard("Issues Found", str(total_issues), color="yellow")
            yield MetricCard(
                "Fixed",
                str(fixed),
                "↑" if fixed > 0 else "",
                color="green",
            )
            yield MetricCard(
                "Remaining",
                str(remaining),
                "↓" if fixed > 0 else "",
                color="red",
            )

        if total_issues > 0:
            success_rate = (fixed / total_issues) * 100
            yield Label(
                f"Success Rate: {success_rate: .1f}%",
                classes="success-rate",
            )

    def _format_time(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds: .0f}s"
        if seconds < 3600:
            return f"{seconds / 60: .0f}m {seconds % 60: .0f}s"
        return f"{seconds / 3600: .0f}h {(seconds % 3600) / 60: .0f}m"


class ServiceHealthPanel(Widget):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.border_title = "🏥 Service Health"
        self.border_title_align = "left"

    def compose(self) -> ComposeResult:
        yield DataTable(id="services-table")

    def on_mount(self) -> None:
        table = self.query_one("#services-table", DataTable)
        table.add_columns(
            "Service",
            "Status",
            "Health",
            "Uptime",
            "Last Check",
        )
        table.zebra_stripes = True

    def update_services(self, services: list[dict[str, t.Any]]) -> None:
        table = self.query_one("#services-table", DataTable)
        table.clear()

        for service in services:
            name = service.get("name", "Unknown")
            status = service.get("status", "unknown")
            health = service.get("health", "unknown")
            uptime = service.get("uptime", 0)
            last_check = service.get("last_check", "Never")

            status_indicator = {
                "running": "🟢 Running",
                "stopped": "🔴 Stopped",
                "starting": "🟡 Starting",
                "error": "❌ Error",
            }.get(status, "❓ Unknown")

            health_indicator = {
                "healthy": "✅",
                "unhealthy": "❌",
                "degraded": "⚠️",
                "unknown": "❓",
            }.get(health, "❓")

            uptime_str = self._format_uptime(uptime)

            if isinstance(last_check, int | float):
                last_check_str = datetime.fromtimestamp(last_check).strftime(
                    "%H: %M: %S",
                )
            else:
                last_check_str = str(last_check)

            table.add_row(
                f"🔧 {name}",
                status_indicator,
                health_indicator,
                uptime_str,
                last_check_str,
            )

    def _format_uptime(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds: .0f}s"
        if seconds < 3600:
            return f"{seconds / 60: .0f}m"
        if seconds < 86400:
            return f"{seconds / 3600: .1f}h"
        return f"{seconds / 86400: .1f}d"


class EnhancedCrackerjackDashboard(App):
    TITLE = "Crackerjack Progress Monitor"
    CSS_PATH = Path(__file__).parent / "enhanced_progress_monitor.tcss"

    def __init__(
        self, progress_dir: Path, websocket_url: str = "ws: //localhost: 8675"
    ) -> None:
        super().__init__()
        self.progress_dir = progress_dir
        self.websocket_url = websocket_url
        self.data_collector = JobDataCollector(progress_dir, websocket_url)
        self.service_manager = ServiceManager()
        self.update_timer: t.Any = None
        self.jobs_data: dict[str, t.Any] = {}

    def compose(self) -> ComposeResult:
        yield Label("🚀 Crackerjack Progress Monitor", id="header")

        with Container(id="main-content"):
            yield AgentActivityWidget(id="agent-panel")

            yield ServiceHealthPanel(id="service-panel")

            with Container(id="jobs-container"):
                yield Label("Loading jobs...", id="jobs-placeholder")

        yield Footer()

    def on_mount(self) -> None:
        self.update_timer = self.set_interval(1.0, self._update_dashboard_wrapper)

    def _update_dashboard_wrapper(self) -> None:
        """Wrapper to call the async update_dashboard method."""
        self.call_later(self.update_dashboard)

    async def update_dashboard(self) -> None:
        try:
            jobs_result = await self.data_collector.discover_jobs()
            jobs_data = jobs_result.get("data", {})

            services = self.service_manager.collect_services_data()
            service_panel = self.query_one("#service-panel", ServiceHealthPanel)
            typed_services: list[dict[str, t.Any]] = t.cast(
                list[dict[str, t.Any]], services
            )
            service_panel.update_services(typed_services)

            if jobs_data.get("individual_jobs"):
                aggregated_agent_data = self._aggregate_agent_data(
                    jobs_data["individual_jobs"],
                )
                self.query_one("#agent-panel", AgentActivityWidget).update_metrics(
                    aggregated_agent_data,
                )

            self._update_job_panels(jobs_data.get("individual_jobs", []))

        except Exception as e:
            self.console.print(f"[red]Dashboard update error: {e}[/]")

    def _aggregate_agent_data(self, jobs: list[dict[str, t.Any]]) -> dict[str, t.Any]:
        aggregated: dict[str, dict[str, t.Any]] = {
            "agent_activity": {
                "active_agents": [],
                "coordinator_status": "idle",
                "agent_registry": {"total_agents": 6},
                "cache_hits": 0,
            },
        }

        for job in jobs:
            if job.get("status", "").lower() == "running":
                agent_summary = job.get("agent_summary", {})
                if agent_summary:
                    aggregated["agent_activity"]["coordinator_status"] = "active"

                    aggregated["agent_activity"]["active_agents"].extend(
                        [
                            {
                                "agent_type": agent_type,
                                "status": "processing",
                                "confidence": 0.85,
                                "processing_time": 2.3,
                                "issue_type": "complexity"
                                if agent_type == "RefactoringAgent"
                                else "formatting",
                            }
                            for agent_type in ("RefactoringAgent", "FormattingAgent")
                        ],
                    )

        return aggregated

    def _update_job_panels(self, jobs: list[dict[str, t.Any]]) -> None:
        container = self.query_one("#jobs-container", Container)

        with suppress(Exception):
            container.remove_children("#jobs-placeholder")

        existing_job_ids = {panel.id for panel in container.query(".job-panel")}
        current_job_ids = {f"job-{job['job_id']}" for job in jobs}

        for panel_id in existing_job_ids - current_job_ids:
            with suppress(Exception):
                panel = container.query_one(f"#{panel_id}")
                panel.remove()

        for job in jobs:
            panel_id = f"job-{job['job_id']}"
            if panel_id not in existing_job_ids:
                panel = JobProgressPanel(job, id=panel_id, classes="job-panel")
                container.mount(panel)
            else:
                panel = container.query_one(f"#{panel_id}", JobProgressPanel)
                panel.job_data = job
                panel.refresh()


async def run_enhanced_progress_monitor(
    progress_dir: Path | None = None,
    websocket_url: str = "ws: //localhost: 8675",
    dev_mode: bool = False,
) -> None:
    if progress_dir is None:
        progress_dir = Path(tempfile.gettempdir()) / "crackerjack-mcp-progress"

    restorer = TerminalRestorer()
    if hasattr(restorer, "setup_handlers"):
        restorer.setup_handlers()

    try:
        app = EnhancedCrackerjackDashboard(progress_dir, websocket_url)

        if dev_mode:
            console = depends.get_sync(Console)
            console.print("[bold cyan]🛠️ Development Mode: Enabled[/bold cyan]")
            # Add dev attribute to the app instance if it doesn't exist
            app.dev = True  # type: ignore[attr-defined]

        await app.run_async()
    finally:
        if hasattr(restorer, "restore"):
            restorer.restore()


if __name__ == "__main__":
    import sys
    import tempfile

    progress_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    websocket_url = sys.argv[2] if len(sys.argv) > 2 else "ws: //localhost: 8675"

    asyncio.run(run_enhanced_progress_monitor(progress_dir, websocket_url))

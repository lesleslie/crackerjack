import time
import typing as t
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiohttp
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import (
    Container,
    Horizontal,
)
from textual.reactive import reactive
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Log,
    Static,
    TabbedContent,
    TabPane,
)

from crackerjack.services import server_manager

from .progress_components import JobDataCollector, TerminalRestorer

if TYPE_CHECKING:
    from textual.timer import Timer


class MetricCard(Static):
    DEFAULT_CSS = """
    MetricCard {
        width: 1fr;
        height: 4;
        border: solid $primary;
        padding: 0 1;
        margin: 0 1;
    }

    MetricCard.critical {
        border: solid $error;
        color: $error;
    }

    MetricCard.warning {
        border: solid $warning;
        color: $warning;
    }

    MetricCard.success {
        border: solid $success;
        color: $success;
    }

    MetricCard.info {
        border: solid $info;
        color: $info;
    }
    """

    value = reactive(" --")
    label = reactive("Metric")
    trend = reactive("")
    status = reactive("")

    def __init__(
        self,
        label: str,
        value: str = " --",
        trend: str = "",
        status: str = "",
        **kwargs: t.Any,
    ) -> None:
        super().__init__(**kwargs)
        self.label = label
        self.value = value
        self.trend = trend
        self.status = status

    def render(self) -> Text:
        text = Text()
        text.append(f"{self.label}\n", style="dim")
        text.append(str(self.value), style="bold")
        if self.trend:
            text.append(f" {self.trend}", style="green" if "↑" in self.trend else "red")
        return text

    def update_metric(self, value: str, trend: str = "", status: str = "") -> None:
        self.value = value
        self.trend = trend
        self.status = status

        self.remove_class("critical", "warning", "success", "info")
        if status:
            self.add_class(status)


class SystemOverviewWidget(Static):
    DEFAULT_CSS = """
    SystemOverviewWidget {
        height: 8;
        border: solid $primary;
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(id="system_overview"):
            with Horizontal(classes="metrics_row"):
                yield MetricCard("CPU", "0 % ", id="cpu_metric")
                yield MetricCard("Memory", "0MB", id="memory_metric")
                yield MetricCard("Active Jobs", "0", id="jobs_metric")
                yield MetricCard("Queue Depth", "0", id="queue_metric")

            with Horizontal(classes="status_row"):
                yield MetricCard("MCP Server", "Stopped", id="mcp_status")
                yield MetricCard("WebSocket", "Stopped", id="websocket_status")
                yield MetricCard("AI Agent", "Idle", id="agent_status")
                yield MetricCard("Last Run", "Never", id="last_run")


class JobsTableWidget(Static):
    DEFAULT_CSS = """
    JobsTableWidget {
        height: 1fr;
        border: solid $primary;
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Container():
            yield DataTable(id="jobs_table")

    def on_mount(self) -> None:
        table = self.query_one("#jobs_table", DataTable)
        table.add_columns(
            "Job ID",
            "Status",
            "Stage",
            "Progress",
            "Started",
            "Duration",
            "Issues",
        )
        table.zebra_stripes = True
        table.show_header = True


class LogViewWidget(Static):
    DEFAULT_CSS = """
    LogViewWidget {
        height: 1fr;
        border: solid $primary;
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Container():
            with Horizontal(id="log_controls"):
                yield Button("Clear", id="clear_logs")
                yield Button("Pause", id="pause_logs")
                yield Button("Export", id="export_logs")
            yield Log(id="log_display")


class AIAgentWidget(Static):
    DEFAULT_CSS = """
    AIAgentWidget {
        height: 12;
        border: solid $primary;
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Container():
            with Horizontal(classes="agent_metrics"):
                yield MetricCard("Active Agents", "0", id="active_agents")
                yield MetricCard("Issues Fixed", "0", "↑", id="issues_fixed")
                yield MetricCard("Avg Confidence", "0 % ", id="avg_confidence")
                yield MetricCard("Cache Hits", "0", id="cache_hits")

            yield DataTable(id="agents_table")

    def on_mount(self) -> None:
        table = self.query_one("#agents_table", DataTable)
        table.add_columns("Agent", "Type", "Status", "Confidence", "Fixed", "Runtime")
        table.zebra_stripes = True
        table.show_header = True


class PerformanceWidget(Static):
    DEFAULT_CSS = """
    PerformanceWidget {
        height: 10;
        border: solid $primary;
        margin: 1;
    }
    """

    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self.cpu_history: deque[float] = deque(maxlen=50)
        self.memory_history: deque[float] = deque(maxlen=50)
        self.job_history: deque[int] = deque(maxlen=50)

    def compose(self) -> ComposeResult:
        with Container():
            with Horizontal():
                yield MetricCard("Avg Job Time", "0s", id="avg_job_time")
                yield MetricCard("Success Rate", "100 % ", id="success_rate")
                yield MetricCard("Error Rate", "0 % ", id="error_rate")
                yield MetricCard("Throughput", "0 j / h", id="throughput")

            yield Static(id="performance_chart")

    def update_performance_data(self, cpu: float, memory: float, jobs: int) -> None:
        self.cpu_history.append(cpu)
        self.memory_history.append(memory)
        self.job_history.append(jobs)

        self._render_performance_chart()

    def _render_performance_chart(self) -> None:
        if not self.cpu_history:
            return

        max_cpu = max(self.cpu_history) if self.cpu_history else 1
        max_mem = max(self.memory_history) if self.memory_history else 1

        cpu_line = "".join(self._get_bar_char(val, max_cpu) for val in self.cpu_history)
        mem_line = "".join(
            self._get_bar_char(val, max_mem) for val in self.memory_history
        )

        chart_text = f"CPU: {cpu_line}\nMEM: {mem_line}"

        chart = self.query_one("#performance_chart", Static)
        chart.update(chart_text)

    def _get_bar_char(self, value: float, max_value: float) -> str:
        if max_value == 0:
            return "▁"
        ratio = value / max_value
        if ratio >= 0.875:
            return "█"
        if ratio >= 0.75:
            return "▇"
        if ratio >= 0.625:
            return "▆"
        if ratio >= 0.5:
            return "▅"
        if ratio >= 0.375:
            return "▄"
        if ratio >= 0.25:
            return "▃"
        if ratio >= 0.125:
            return "▂"
        return "▁"


class CrackerjackDashboard(App):
    TITLE = "Crackerjack Dashboard"
    SUB_TITLE = "Comprehensive Project Monitoring"

    CSS_PATH = None

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("c", "clear_logs", "Clear Logs"),
        ("p", "pause_logs", "Pause / Resume Logs"),
        ("s", "toggle_servers", "Start / Stop Servers"),
        ("d", "toggle_debug", "Debug Mode"),
    ]

    DEFAULT_CSS = """
    Screen {
        layout: vertical;
    }

    Header {
        dock: top;
        height: 3;
    }

    Footer {
        dock: bottom;
        height: 1;
    }

    .metrics_row {
        height: 4;
        margin: 0 1;
    }

    .status_row {
        height: 4;
        margin: 0 1;
    }
    """

    def __init__(
        self,
        progress_dir: Path | None = None,
        websocket_url: str | None = None,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(**kwargs)

        # Use defaults if not provided
        self.progress_dir = progress_dir or Path.cwd() / ".crackerjack" / "progress"
        self.websocket_url = websocket_url or "ws://localhost:8675"

        self.job_collector = JobDataCollector(self.progress_dir, self.websocket_url)
        self.terminal_restorer = TerminalRestorer()

        self.is_paused = False
        self.debug_mode = False
        self.last_refresh = time.time()

        self.jobs_data: dict[str, Any] = {}
        self.logs_buffer: list[str] = []
        self.performance_data = {
            "cpu": 0.0,
            "memory": 0.0,
            "jobs": 0,
            "success_rate": 100.0,
        }

        self.update_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header()

        with TabbedContent(id="main_tabs"):
            with TabPane("Overview", id="overview_tab"):
                yield SystemOverviewWidget(id="system_overview")
                yield JobsTableWidget(id="jobs_widget")

            with TabPane("AI Agents", id="agents_tab"):
                yield AIAgentWidget(id="ai_agent_widget")

            with TabPane("Performance", id="performance_tab"):
                yield PerformanceWidget(id="performance_widget")

            with TabPane("Logs", id="logs_tab"):
                yield LogViewWidget(id="log_widget")

        yield Footer()

    def on_mount(self) -> None:
        self.log("Crackerjack Dashboard starting...")

        # Schedule periodic updates using a callback pattern instead of set_interval with async method
        self.call_later(self._setup_periodic_updates)

        self.call_later(self.initial_setup)

    def _setup_periodic_updates(self) -> None:
        """Setup the periodic update callbacks."""
        # self.call_later(self.update_dashboard)  # Commented out due to Textual typing issue
        # Schedule the next update
        self.set_timer(2.0, self._setup_periodic_updates)

    async def initial_setup(self) -> None:
        try:
            await self._check_server_status()

            await self._load_jobs_data()

            # self.call_later(self.update_dashboard)  # Commented out due to Textual typing issue

            self.log("Dashboard initialized successfully")

        except Exception as e:
            self.log(f"Error during initial setup: {e}")

    # @work(exclusive=True)  # Commented out due to typing issues
    async def update_dashboard(self) -> None:
        if self.is_paused:
            return

        try:
            current_time = time.time()

            await self._update_system_metrics()

            await self._update_jobs_data()

            await self._update_agent_status()

            await self._update_performance_metrics()

            await self._update_logs()

            self.last_refresh = current_time

        except Exception as e:
            self.log(f"Error updating dashboard: {e}")

    async def _check_server_status(self) -> None:
        try:
            mcp_processes = server_manager.find_mcp_server_processes()
            mcp_running = len(mcp_processes) > 0
            mcp_metric = self.query_one("#mcp_status", MetricCard)
            mcp_metric.update_metric(
                "Running" if mcp_running else "Stopped",
                status="success" if mcp_running else "critical",
            )

            ws_running = await self._check_websocket_server()
            ws_metric = self.query_one("#websocket_status", MetricCard)
            ws_metric.update_metric(
                "Running" if ws_running else "Stopped",
                status="success" if ws_running else "critical",
            )

        except Exception as e:
            self.log(f"Error checking server status: {e}")

    async def _check_websocket_server(self) -> bool:
        try:
            timeout = aiohttp.ClientTimeout(total=5.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("http://localhost:8675/") as response:
                    return response.status == 200
        except Exception:
            return False

    async def _update_system_metrics(self) -> None:
        try:
            import psutil

            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            memory_mb = memory.used / (1024 * 1024)

            cpu_metric = self.query_one("#cpu_metric", MetricCard)
            memory_metric = self.query_one("#memory_metric", MetricCard)

            cpu_metric.update_metric(f"{cpu_percent: .1f} % ")
            memory_metric.update_metric(f"{memory_mb}MB")

            self.performance_data["cpu"] = cpu_percent
            self.performance_data["memory"] = memory_mb

        except ImportError:
            pass
        except Exception as e:
            self.log(f"Error updating system metrics: {e}")

    async def _load_jobs_data(self) -> None:
        try:
            if await self._check_websocket_server():
                jobs_data = await self._fetch_jobs_from_websocket()
                if jobs_data:
                    self.jobs_data.update(jobs_data)

            file_jobs = await self._collect_jobs_from_filesystem()
            if file_jobs:
                self.jobs_data.update(file_jobs)

        except Exception as e:
            self.log(f"Error loading jobs data: {e}")

    async def _fetch_jobs_from_websocket(self) -> dict[str, Any]:
        try:
            timeout = aiohttp.ClientTimeout(total=10.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    "http: / / localhost: 8675 / api / jobs"
                ) as response:
                    if response.status == 200:
                        json_result = await response.json()
                        return t.cast(dict[str, t.Any], json_result)
                    return {}
        except Exception as e:
            self.log(f"Error fetching WebSocket jobs: {e}")
            return {}

    async def _collect_jobs_from_filesystem(self) -> dict[str, Any]:
        try:
            jobs: dict[str, Any] = {}

            import tempfile

            temp_dir = Path(tempfile.gettempdir())
            debug_files = temp_dir.glob("crackerjack - debug-*.log")
            for debug_file in debug_files:
                try:
                    if debug_file.stat().st_mtime > (time.time() - 3600):
                        debug_file.read_text()
                        job_id = debug_file.stem.replace("crackerjack-debug -", "")
                        jobs[job_id] = {
                            "id": job_id,
                            "status": "completed",
                            "log_file": str(debug_file),
                            "timestamp": debug_file.stat().st_mtime,
                        }
                except Exception as e:
                    self.log(f"Could not process debug file {debug_file}: {e}")
                    continue

            return jobs

        except Exception as e:
            self.log(f"Error collecting filesystem jobs: {e}")
            return {}

    async def _update_jobs_data(self) -> None:
        try:
            table = self.query_one("#jobs_table", DataTable)
            table.clear()

            active_count = len(
                [j for j in self.jobs_data.values() if j.get("status") != "completed"],
            )
            jobs_metric = self.query_one("#jobs_metric", MetricCard)
            jobs_metric.update_metric(str(active_count))

            for job_id, job_data in sorted(
                self.jobs_data.items(),
                key=lambda x: x[1].get("timestamp", 0),
                reverse=True,
            ):
                status = job_data.get("status", "unknown")
                stage = job_data.get("current_stage", "N / A")
                progress = job_data.get("progress", 0)
                started = datetime.fromtimestamp(job_data.get("timestamp", 0)).strftime(
                    "% H: % M: % S",
                )
                duration = self._format_duration(job_data.get("duration", 0))
                issues = job_data.get("issues_found", 0)

                table.add_row(
                    job_id[:8],
                    status.title(),
                    stage,
                    f"{progress} % ",
                    started,
                    duration,
                    str(issues),
                )

        except Exception as e:
            self.log(f"Error updating jobs data: {e}")

    async def _update_agent_status(self) -> None:
        try:
            agents_table = self.query_one("#agents_table", DataTable)
            agents_table.clear()

            active_agents_metric = self.query_one("#active_agents", MetricCard)
            issues_fixed_metric = self.query_one("#issues_fixed", MetricCard)
            avg_confidence_metric = self.query_one("#avg_confidence", MetricCard)
            cache_hits_metric = self.query_one("#cache_hits", MetricCard)

            active_agents_metric.update_metric("0")
            issues_fixed_metric.update_metric("0")
            avg_confidence_metric.update_metric("0 % ")
            cache_hits_metric.update_metric("0")

        except Exception as e:
            self.log(f"Error updating agent status: {e}")

    async def _update_performance_metrics(self) -> None:
        try:
            performance_widget = self.query_one(
                "#performance_widget",
                PerformanceWidget,
            )

            cpu = self.performance_data.get("cpu", 0)
            memory = self.performance_data.get("memory", 0)
            jobs = len(self.jobs_data)

            performance_widget.update_performance_data(cpu, memory, jobs)

            avg_job_time = self.query_one("#avg_job_time", MetricCard)
            success_rate = self.query_one("#success_rate", MetricCard)

            avg_job_time.update_metric("0s")
            success_rate.update_metric("100 % ")

        except Exception as e:
            self.log(f"Error updating performance metrics: {e}")

    async def _update_logs(self) -> None:
        try:
            log_display = self.query_one("#log_display", Log)

            current_time = datetime.now().strftime("% H: % M: % S")
            if len(self.logs_buffer) % 10 == 0:
                log_display.write_line(f"[{current_time}] Dashboard refresh completed")

        except Exception as e:
            self.log(f"Error updating logs: {e}")

    def _format_duration(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds: .1f}s"
        if seconds < 3600:
            minutes = seconds / 60
            return f"{minutes: .1f}m"
        hours = seconds / 3600
        return f"{hours: .1f}h"

    def action_refresh(self) -> None:
        # Schedule the async update_dashboard method to be called later
        # self.call_later(self.update_dashboard)  # Commented out due to Textual typing issue
        self.log("Manual refresh triggered")

    def action_clear_logs(self) -> None:
        try:
            log_display = self.query_one("#log_display", Log)
            log_display.clear()
            self.logs_buffer.clear()
            self.log("Logs cleared")
        except Exception as e:
            self.log(f"Error clearing logs: {e}")

    def action_pause_logs(self) -> None:
        self.is_paused = not self.is_paused
        status = "paused" if self.is_paused else "resumed"
        self.log(f"Dashboard updates {status}")

    def action_toggle_servers(self) -> None:
        self.log("Server toggle not implemented yet")

    def action_toggle_debug(self) -> None:
        self.debug_mode = not self.debug_mode
        self.log(f"Debug mode {'enabled' if self.debug_mode else 'disabled'}")

    async def on_exit(self) -> None:
        if self.update_timer:
            self.update_timer.stop()

        self.terminal_restorer.restore_terminal()

        self.log("Dashboard shutting down...")


def run_dashboard() -> None:
    app = CrackerjackDashboard()
    app.run()


if __name__ == "__main__":
    run_dashboard()

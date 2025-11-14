import asyncio
import atexit
import signal
import subprocess
import sys
import tempfile
import time
import typing as t
from contextlib import suppress
from pathlib import Path

from acb import console
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import DataTable, Footer, Label, ProgressBar

from crackerjack.core.timeout_manager import TimeoutStrategy, get_timeout_manager

from .progress_components import (
    ErrorCollector,
    JobDataCollector,
    ServiceHealthChecker,
    ServiceManager,
    TerminalRestorer,
)


class AgentStatusPanel(Widget):
    def __init__(self, **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self.border_title = "🤖 AI Agents"
        self.border_title_align = "left"

    def compose(self) -> ComposeResult:
        yield DataTable(id="agents-table")
        yield Label("Coordinator: Loading...", id="coordinator-status")
        yield Label("Stats: Loading...", id="agent-stats")

    def on_mount(self) -> None:
        with suppress(Exception):
            agents_table = self.query_one("#agents-table", DataTable)
            agents_table.add_columns(
                "Agent",
                "Status",
                "Issue Type",
                "Confidence",
                "Time",
            )

            agents_table.styles.max_height = "8"

    def update_agent_data(self, agent_data: dict[str, t.Any]) -> None:
        with suppress(Exception):
            self._update_coordinator_status(agent_data)
            self._update_agents_table(agent_data)
            self._update_stats(agent_data)

    def _update_coordinator_status(self, data: dict[str, t.Any]) -> None:
        with suppress(Exception):
            activity = data.get("agent_activity", {})
            registry = activity.get("agent_registry", {})
            coordinator_status = activity.get("coordinator_status", "idle")
            total_agents = registry.get("total_agents", 6)

            status_emoji = "✅" if coordinator_status == "active" else "⏸️"
            status_label = self.query_one("#coordinator-status", Label)
            status_label.update(
                f"Coordinator: {status_emoji} {coordinator_status.title()} ({total_agents} agents)",
            )

    def _update_agents_table(self, data: dict[str, t.Any]) -> None:
        with suppress(Exception):
            agents_table = self.query_one("#agents-table", DataTable)
            agents_table.clear()

            activity = data.get("agent_activity", {})
            active_agents = activity.get("active_agents", [])

            if not active_agents:
                agents_table.add_row("No active agents", "-", "-", "-", "-")
                return

            for agent in active_agents:
                agent_type = agent.get("agent_type", "Unknown")
                status = agent.get("status", "unknown")
                confidence = agent.get("confidence", 0)
                processing_time = agent.get("processing_time", 0)

                emoji = self._get_agent_emoji(agent_type)

                current_issue = agent.get("current_issue", {})
                issue_type = (
                    current_issue.get("type", "-")
                    if current_issue
                    else agent.get("issue_type", "-")
                )

                status_display = f"{self._get_status_emoji(status)} {status.title()}"

                agents_table.add_row(
                    f"{emoji} {agent_type}",
                    status_display,
                    issue_type,
                    f"{confidence: .0 % }" if confidence > 0 else "-",
                    f"{processing_time: .1f}s" if processing_time > 0 else "-",
                )

    def _update_stats(self, data: dict[str, t.Any]) -> None:
        with suppress(Exception):
            performance = data.get("agent_performance", {})
            total_issues = performance.get("total_issues_processed", 0)
            success_rate = performance.get("success_rate", 0)
            avg_time = performance.get("average_processing_time", 0)
            cache_hits = performance.get("cache_hits", 0)

            stats_label = self.query_one("#agent-stats", Label)
            stats_text = f"Stats: {total_issues} issues | {success_rate: .0 % } success"
            if avg_time > 0:
                stats_text += f" | {avg_time: .1f}s avg"
            if cache_hits > 0:
                stats_text += f" | {cache_hits} cached"

            if success_rate >= 80:
                stats_text += " ↑🟢"
            elif success_rate >= 60:
                stats_text += " 🟡"
            elif total_issues > 0:
                stats_text += " ↓🔴"

            stats_label.update(stats_text)

    def _get_agent_emoji(self, agent_type: str) -> str:
        emojis = {
            "FormattingAgent": "🎨",
            "SecurityAgent": "🔒",
            "TestSpecialistAgent": "🧪",
            "TestCreationAgent": "➕",
            "RefactoringAgent": "🔧",
            "ImportOptimizationAgent": "📦",
        }
        return emojis.get(agent_type) or "🤖"

    def _get_status_emoji(self, status: str) -> str:
        emojis = {
            "evaluating": "🔍",
            "processing": "⏳",
            "completed": "✅",
            "failed": "❌",
            "idle": "⏸️",
        }
        return emojis.get(status.lower()) or "❓"


class JobPanel(Widget):
    def __init__(self, job_data: dict[str, t.Any], **kwargs: t.Any) -> None:
        super().__init__(**kwargs)
        self.job_data = job_data
        self.completion_time: float | None = None
        self.iteration_count = job_data.get("iteration", 0)
        self.max_iterations = job_data.get("max_iterations", 5)
        self.fade_timer: t.Any | None = None  # Timer object or None
        self.remove_timer: t.Any | None = None  # Timer object or None
        self.fade_level = 0
        self.border_style = self._calculate_border_style()

    def _calculate_border_style(self) -> str:
        status = self.job_data.get("status", "unknown").lower()

        if status == "completed":
            errors = self.job_data.get("errors", [])
            hook_failures = self.job_data.get("hook_failures", [])
            test_failures = self.job_data.get("test_failures", [])
            total_failures = (
                len(hook_failures)
                + len(test_failures)
                + len([e for e in errors if "failed" in str(e).lower()])
            )

            if total_failures == 0:
                return "round green"
            return "round red"
        if status == "failed" or self.iteration_count >= 10:
            return "round red"
        if status == "running":
            return "round blue"
        return "round white"

    def on_mount(self) -> None:
        project_name = self.job_data.get("project", "crackerjack")
        status = self.job_data.get("status", "").lower()
        if status == "running":
            self.border_title = f"📁 {project_name}"
            self.border_subtitle = "💓"
            self.border_subtitle_align = "right"
        else:
            self.border_title = f"📁 {project_name}"
        self.border_title_align = "left"

        self._setup_errors_table()

        self._update_progress_bar()

        status = self.job_data.get("status", "").lower()
        if status in ("completed", "failed") and self.completion_time is None:
            self.completion_time = time.time()

            self.fade_timer = self.set_timer(300.0, self._start_fade)

            self.remove_timer = self.set_timer(1200.0, self._remove_panel)

    def _setup_errors_table(self) -> None:
        with suppress(Exception):
            errors_container = self.query_one(".job-errors")
            errors_container.border_title = "❌ Errors"

            errors_table = self.query_one(
                f"#job-errors -{self.job_data.get('job_id', 'unknown')}",
                DataTable,
            )
            errors_table.add_columns("", "", "", "")

            self._update_errors_table()

    def _update_errors_table(self) -> None:
        with suppress(Exception):
            errors_table = self.query_one(
                f"#job-errors -{self.job_data.get('job_id', 'unknown')}",
                DataTable,
            )
            errors_table.clear()

            total_errors = self.job_data.get("total_issues", 0)
            fixed_errors = self.job_data.get("errors_fixed", 0)

            remaining_errors = max(0, total_errors - fixed_errors)

            progress_pct = 0
            if total_errors > 0:
                progress_pct = int((fixed_errors / total_errors) * 100)

            if total_errors == 0 and "errors" in self.job_data:
                errors = self.job_data.get("errors", [])
                hook_failures = self.job_data.get("hook_failures", [])
                test_failures = self.job_data.get("test_failures", [])
                total_errors = len(errors) + len(hook_failures) + len(test_failures)
                failed_errors = (
                    len(hook_failures)
                    + len(test_failures)
                    + len([e for e in errors if "failed" in str(e).lower()])
                )
                fixed_errors = max(0, total_errors - failed_errors)
                remaining_errors = failed_errors
                if total_errors > 0:
                    progress_pct = int((fixed_errors / total_errors) * 100)

            discovered_label = "🔍 Found"
            discovered_value = f"{total_errors: > 15}"
            resolved_label = "✅ Fixed"
            resolved_value = f"{fixed_errors: > 15}"

            remaining_label = "❌ Left"
            remaining_value = f"{remaining_errors: > 15}"
            progress_label = "📈 Done"
            progress_value = f"{progress_pct} % ".rjust(15)

            errors_table.add_rows(
                [
                    (
                        discovered_label,
                        discovered_value,
                        resolved_label,
                        resolved_value,
                    ),
                    (remaining_label, remaining_value, progress_label, progress_value),
                ],
            )

    def _update_progress_bar(self) -> None:
        with suppress(Exception):
            progress_bar = self.query_one(
                f"#job-progress -{self.job_data.get('job_id', 'unknown')}",
                ProgressBar,
            )
            progress_value = self.iteration_count / max(self.max_iterations, 1) * 100
            progress_bar.update(progress=progress_value)

    def _start_fade(self) -> None:
        self.fade_level += 1

        if self.fade_level == 1:
            self.add_class("fade-1")
        elif self.fade_level == 2:
            self.add_class("fade-2")
        elif self.fade_level == 3:
            self.add_class("fade-3")
        elif self.fade_level >= 4:
            self.add_class("fade-4")

        if self.fade_level < 4:
            self.fade_timer = self.set_timer(300.0, self._start_fade)

    def _remove_panel(self) -> None:
        if hasattr(self.app, "completed_jobs_stats"):
            job_id = self.job_data.get("job_id")

            total_errors = self.job_data.get("total_issues", 0)
            fixed_errors = self.job_data.get("errors_fixed", 0)
            remaining_errors = max(0, total_errors - fixed_errors)

            if total_errors == 0 and "errors" in self.job_data:
                errors = self.job_data.get("errors", [])
                hook_failures = self.job_data.get("hook_failures", [])
                test_failures = self.job_data.get("test_failures", [])

                total_errors = len(errors) + len(hook_failures) + len(test_failures)
                failed_errors = (
                    len(hook_failures)
                    + len(test_failures)
                    + len([e for e in errors if "failed" in str(e).lower()])
                )
                fixed_errors = max(0, total_errors - failed_errors)
                remaining_errors = failed_errors

            self.app.completed_jobs_stats[job_id] = {
                "status": self.job_data.get("status", "unknown"),
                "total_errors": total_errors,
                "fixed_errors": fixed_errors,
                "remaining_errors": remaining_errors,
                "completion_time": self.completion_time,
            }

        if hasattr(self.app, "active_jobs"):
            job_id = self.job_data.get("job_id")
            if job_id in self.app.active_jobs:
                del self.app.active_jobs[job_id]
        self.remove()

    def compose(self) -> ComposeResult:
        with Container(classes="job-panel"):
            yield from self._compose_status_column()
            yield from self._compose_errors_column()
            yield from self._compose_mcp_message()

    def _compose_mcp_message(self) -> ComposeResult:
        mcp_message = self.job_data.get("message", "Processing...")
        yield Label(f"💬 {mcp_message}", classes="mcp-message")

    def _compose_status_column(self) -> ComposeResult:
        with Container(classes="job-status"):
            yield from self._compose_job_identifiers()
            yield from self._compose_progress_info()
            yield from self._compose_stage_and_status()
            yield from self._compose_agent_info()
            yield from self._compose_warning_messages()

    def _compose_job_identifiers(self) -> ComposeResult:
        job_id = self.job_data.get(
            "full_job_id",
            self.job_data.get("job_id", "Unknown"),
        )
        yield Label(f"🆔 UUID: {job_id}")

    def _compose_progress_info(self) -> ComposeResult:
        progress_stage = f"{self.iteration_count} / {self.max_iterations}"
        yield Label(f"📊 Progress: {progress_stage}")
        yield ProgressBar(
            total=100,
            show_eta=False,
            show_percentage=False,
            id=f"job-progress -{self.job_data.get('job_id', 'unknown')}",
        )

    def _compose_stage_and_status(self) -> ComposeResult:
        yield Label(f"🎯 Stage: {self.job_data.get('stage', 'Unknown')}")
        yield Label(f"📝 Status: {self.job_data.get('status', 'Unknown')}")

    def _compose_agent_info(self) -> ComposeResult:
        agent_summary = self.job_data.get("agent_summary", {})
        if not agent_summary:
            return

        active_count = agent_summary.get("active_count", 0)
        cached_fixes = agent_summary.get("cached_fixes", 0)

        if active_count > 0 or cached_fixes > 0:
            agent_text = f"🤖 Agents: {active_count} active"
            if cached_fixes > 0:
                agent_text += f", {cached_fixes} cached"

            agents_data = agent_summary.get("agents", [])
            if agents_data:
                avg_confidence = sum(
                    agent.get("confidence", 0) for agent in agents_data
                ) / max(len(agents_data), 1)
                if avg_confidence > 0:
                    agent_text += f", {avg_confidence: .0 % } conf"
            yield Label(agent_text)

    def _compose_warning_messages(self) -> ComposeResult:
        if self.iteration_count >= 10:
            yield Label("⚠️ Max iterations reached")

    def _compose_errors_column(self) -> ComposeResult:
        with Container(classes="job-errors"):
            yield DataTable(
                id=f"job-errors -{self.job_data.get('job_id', 'unknown')}",
            )


class CrackerjackDashboard(App):
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = Path(__file__).parent / "progress_monitor.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.progress_dir = Path(tempfile.gettempdir()) / "crackerjack-mcp-progress"
        self.websocket_url = "ws://localhost:8675"
        self.refresh_timer: t.Any | None = None  # Timer object or None
        self._refresh_counter = 0
        self.dev = False
        self.active_jobs: dict[str, t.Any] = {}
        self.completed_jobs_stats: dict[str, t.Any] = {}
        self.current_polling_method = "File"
        self.timeout_manager = get_timeout_manager()

        self.job_collector = JobDataCollector(self.progress_dir, self.websocket_url)
        self.service_checker = ServiceHealthChecker()
        self.error_collector = ErrorCollector()
        self.service_manager = ServiceManager()
        self.terminal_restorer = TerminalRestorer()

    def compose(self) -> ComposeResult:
        with Container(id="main-container"):
            yield from self._compose_top_section()
            yield from self._compose_discovery_section()
        yield Footer()

    def _compose_top_section(self) -> ComposeResult:
        with Container(id="top-section"):
            yield from self._compose_left_column()
            yield from self._compose_right_column()

    def _compose_left_column(self) -> ComposeResult:
        with Container(id="left-column"):
            yield from self._compose_jobs_panel()
            yield AgentStatusPanel(id="agent - status-panel")

    def _compose_right_column(self) -> ComposeResult:
        with Container(id="right-column"):
            yield from self._compose_errors_panel()
            yield from self._compose_services_panel()

    def _compose_jobs_panel(self) -> ComposeResult:
        with Container(id="jobs-panel"):
            yield DataTable(
                id="jobs-table",
            )

    def _compose_errors_panel(self) -> ComposeResult:
        with Container(id="errors-panel"):
            yield DataTable(
                id="errors-table",
            )

    def _compose_services_panel(self) -> ComposeResult:
        with Container(id="services-panel"):
            yield DataTable(
                id="services-table",
                zebra_stripes=True,
            )

    def _compose_discovery_section(self) -> ComposeResult:
        with Container(id="discovery-section"):
            yield Container(id="job - discovery-container")

    def on_mount(self) -> None:
        self._setup_border_titles()
        self._setup_datatables()

        asyncio.create_task(self._ensure_services_running())
        self._start_refresh_timer()

        atexit.register(self._restore_terminal_fallback)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def on_unmount(self) -> None:
        with suppress(Exception):
            self._cleanup_started_services()

    def _setup_border_titles(self) -> None:
        self.query_one("#top-section").border_title = "🚀 Crackerjack Dashboard"
        self.query_one("#jobs-panel").border_title = "📊 Issue Metrics"
        self.query_one("#errors-panel").border_title = "❌ Error Tracking"
        self.query_one("#services-panel").border_title = "🔧 Service Health"
        self.query_one("#discovery-section").border_title = "🔍 Active Jobs"

    def _setup_datatables(self) -> None:
        jobs_table = self.query_one("#jobs-table", DataTable)
        jobs_table.add_columns("", "", "", "")

        services_table = self.query_one("#services-table", DataTable)
        services_table.add_columns("Service", "Status", "Restarts")

        errors_table = self.query_one("#errors-table", DataTable)
        errors_table.add_columns("", "", "", "")

        self._show_default_values()

        asyncio.create_task(self._refresh_data())

    def _show_default_values(self) -> None:
        default_jobs_data = {
            "active": 0,
            "completed": 0,
            "failed": 0,
            "total": 0,
            "individual_jobs": [],
        }
        self._update_jobs_table(default_jobs_data)

        self._update_errors_table([])

    async def _ensure_services_running(self) -> None:
        await self.service_manager.ensure_services_running()

    def _start_refresh_timer(self) -> None:
        self.refresh_timer = self.set_interval(0.5, self._refresh_data)

    async def _refresh_data(self) -> None:
        try:
            async with self.timeout_manager.timeout_context(
                "network_operations",
                timeout=10.0,
                strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
            ):
                self._refresh_counter += 1

                if self._refresh_counter % 20 == 0:
                    with suppress(Exception):
                        await self.timeout_manager.with_timeout(
                            "network_operations",
                            self._ensure_services_running(),
                            timeout=5.0,
                            strategy=TimeoutStrategy.FAIL_FAST,
                        )

                jobs_data = await self.timeout_manager.with_timeout(
                    "network_operations",
                    self._discover_jobs(),
                    timeout=3.0,
                    strategy=TimeoutStrategy.FAIL_FAST,
                )

                services_data = await self.timeout_manager.with_timeout(
                    "network_operations",
                    self._collect_services_data(),
                    timeout=2.0,
                    strategy=TimeoutStrategy.FAIL_FAST,
                )

                errors_data = await self.timeout_manager.with_timeout(
                    "file_operations",
                    self._collect_recent_errors(),
                    timeout=2.0,
                    strategy=TimeoutStrategy.FAIL_FAST,
                )

                self.query_one("#services-panel").border_title = "🔧 Services"

                self._update_jobs_table(jobs_data)
                self._update_services_table(services_data)
                self._update_errors_table(errors_data)
                self._update_job_panels(jobs_data)
                self._update_agent_panel(jobs_data)
                self._update_status_bars(jobs_data)

        except Exception as e:
            with suppress(Exception):
                console.print(f"[red]Dashboard refresh error: {e}[/red]")

    async def _discover_jobs(self) -> dict[str, t.Any]:
        try:
            result = await self.timeout_manager.with_timeout(
                "network_operations",
                self.job_collector.discover_jobs(),
                timeout=5.0,
                strategy=TimeoutStrategy.FAIL_FAST,
            )
            self.current_polling_method = result["method"]
            data_result = result["data"]
            return t.cast(dict[str, t.Any], data_result)
        except Exception:
            return {
                "active": 0,
                "completed": 0,
                "failed": 0,
                "total": 0,
                "individual_jobs": [],
                "total_issues": 0,
                "errors_fixed": 0,
                "errors_failed": 0,
                "current_errors": 0,
            }

    async def _collect_services_data(self) -> list[t.Any]:
        try:
            services_data = await self.timeout_manager.with_timeout(
                "network_operations",
                self.service_checker.collect_services_data(),
                timeout=3.0,
                strategy=TimeoutStrategy.FAIL_FAST,
            )
            return t.cast(list[t.Any], services_data)
        except Exception:
            return [("Services", "🔴 Timeout", "0")]

    async def _collect_recent_errors(self) -> list[t.Any]:
        try:
            errors_data = await self.timeout_manager.with_timeout(
                "file_operations",
                self.error_collector.collect_recent_errors(),
                timeout=2.0,
                strategy=TimeoutStrategy.FAIL_FAST,
            )
            return t.cast(list[t.Any], errors_data)
        except Exception:
            return []

    def _update_jobs_table(self, jobs_data: dict[str, t.Any]) -> None:
        with suppress(Exception):
            jobs_table = self.query_one("#jobs-table", DataTable)
            jobs_table.clear()

            total_issues = jobs_data.get("total_issues", 0)
            errors_fixed = jobs_data.get("errors_fixed", 0)
            errors_failed = jobs_data.get("errors_failed", 0)
            jobs_data.get("current_errors", 0)

            for job_stats in self.completed_jobs_stats.values():
                total_issues += job_stats.get("total_issues", 0)
                errors_fixed += job_stats.get("errors_fixed", 0)
                errors_failed += job_stats.get("errors_failed", 0)

            remaining_errors = max(0, total_issues - errors_fixed)

            discovered_label = "🔍 Found"
            discovered_value = f"{total_issues: > 12}"
            resolved_label = "✅ Fixed"
            resolved_value = f"{errors_fixed: > 12}"

            remaining_label = "❌ Left"
            remaining_value = f"{remaining_errors: > 12}"
            progress_label = "📈 Done"
            progress_pct = (
                int(errors_fixed / total_issues * 100) if total_issues > 0 else 0
            )
            progress_value = f"{progress_pct} % ".rjust(12)

            jobs_table.add_rows(
                [
                    (
                        discovered_label,
                        discovered_value,
                        resolved_label,
                        resolved_value,
                    ),
                    (remaining_label, remaining_value, progress_label, progress_value),
                ],
            )

    def _update_services_table(self, services_data: list[t.Any]) -> None:
        with suppress(Exception):
            services_table = self.query_one("#services-table", DataTable)
            services_table.clear()

            for service in services_data:
                service_name = (
                    service[0]
                    .replace("WebSocket Server", "WebSocket")
                    .replace(" Server", "")
                )

                status_text = service[1] or "❓ Unknown"
                restart_count = service[2] if len(service) > 2 else "0"
                restart_value = f"{restart_count: ^ 8}"
                services_table.add_row(service_name, status_text, restart_value)

            method_emoji = "🌐" if self.current_polling_method == "WebSocket" else "📁"
            polling_status = f"{method_emoji} {self.current_polling_method}"

            if self.current_polling_method == "WebSocket":
                polling_status += " 🟢"
            services_table.add_row("Polling", polling_status, "")

    def _update_errors_table(self, errors_data: list[t.Any]) -> None:
        with suppress(Exception):
            errors_table = self.query_one("#errors-table", DataTable)
            errors_table.clear()

            job_errors = (
                [
                    e
                    for e in errors_data
                    if "crackerjack" in str(e).lower() and "job" in str(e).lower()
                ]
                if errors_data
                else []
            )

            active_errors = 0
            fixed_errors = 0
            total_errors = 0

            if job_errors:
                total_errors = len(job_errors)
                active_errors = sum(
                    1
                    for e in job_errors
                    if "running" in str(e).lower() or "active" in str(e).lower()
                )
                sum(
                    1
                    for e in job_errors
                    if "failed" in str(e).lower() or "error" in str(e).lower()
                )
                fixed_errors = sum(
                    1
                    for e in job_errors
                    if "fixed" in str(e).lower() or "resolved" in str(e).lower()
                )

            discovered_label = "🔍 Found"
            discovered_value = f"{total_errors: > 12}"
            resolved_label = "✅ Fixed"
            resolved_value = f"{fixed_errors: > 12}"

            remaining_label = "❌ Left"
            remaining_value = f"{active_errors: > 12}"
            progress_label = "📈 Done"
            progress_pct = (
                int(fixed_errors / total_errors * 100) if total_errors > 0 else 0
            )
            progress_value = f"{progress_pct} % ".rjust(12)

            errors_table.add_rows(
                [
                    (
                        discovered_label,
                        discovered_value,
                        resolved_label,
                        resolved_value,
                    ),
                    (remaining_label, remaining_value, progress_label, progress_value),
                ],
            )

    def _update_agent_panel(self, jobs_data: dict[str, t.Any]) -> None:
        with suppress(Exception):
            agent_panel = self.query_one("#agent - status-panel", AgentStatusPanel)

            agent_data = {}
            for job in jobs_data.get("individual_jobs", []):
                if "agent_activity" in job or "agent_performance" in job:
                    agent_data = job
                    break

            if agent_data:
                agent_panel.update_agent_data(agent_data)

    def _update_job_panels(self, jobs_data: dict[str, t.Any]) -> None:
        with suppress(Exception):
            container = self.query_one("#job - discovery-container")
            current_job_ids = self._get_current_job_ids(jobs_data)

            self._remove_obsolete_panels(current_job_ids)
            self._update_or_create_panels(jobs_data, container)
            self._handle_placeholder_visibility(container)

    def _get_current_job_ids(self, jobs_data: dict[str, t.Any]) -> set[t.Any]:
        return (
            {job["job_id"] for job in jobs_data["individual_jobs"]}
            if jobs_data["individual_jobs"]
            else set()
        )

    def _remove_obsolete_panels(self, current_job_ids: set[t.Any]) -> None:
        jobs_to_remove = []
        for job_id, panel in self.active_jobs.items():
            panel_status = panel.job_data.get("status", "").lower()
            if (
                job_id not in current_job_ids
                and panel_status not in ("completed", "failed")
                and panel.completion_time is None
            ):
                jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            panel = self.active_jobs.pop(job_id)
            panel.remove()

    def _update_or_create_panels(
        self, jobs_data: dict[str, t.Any], container: t.Any
    ) -> None:
        if not jobs_data["individual_jobs"]:
            return

        for job in jobs_data["individual_jobs"]:
            job_id = job["job_id"]
            if job_id in self.active_jobs:
                self._update_existing_panel(job)
            else:
                self._create_new_panel(job, container)

    def _update_existing_panel(self, job: dict[str, t.Any]) -> None:
        existing_panel = self.active_jobs[job["job_id"]]
        existing_panel.job_data = job
        existing_panel.iteration_count = job.get("iteration", 0)

        self._update_panel_title(existing_panel, job)
        existing_panel._update_errors_table()
        existing_panel._update_progress_bar()
        self._handle_job_completion(existing_panel, job)
        self._update_panel_border(existing_panel)

    def _update_panel_title(self, panel: t.Any, job: dict[str, t.Any]) -> None:
        project_name = job.get("project", "crackerjack")
        status = job.get("status", "").lower()

        panel.border_title = f"📁 {project_name}"
        panel.border_title_align = "left"

        if status == "running":
            panel.border_subtitle = "💓"
            panel.border_subtitle_align = "right"
        else:
            panel.border_subtitle = ""

    def _handle_job_completion(self, panel: t.Any, job: dict[str, t.Any]) -> None:
        job_status = job.get("status", "").lower()
        if job_status in ("completed", "failed") and panel.completion_time is None:
            panel.completion_time = time.time()
            panel.fade_timer = panel.set_timer(300.0, panel._start_fade)
            panel.remove_timer = panel.set_timer(1200.0, panel._remove_panel)

    def _update_panel_border(self, panel: t.Any) -> None:
        new_border = panel._calculate_border_style()
        if new_border != panel.border_style:
            panel.border_style = new_border
            panel.refresh()

    def _create_new_panel(self, job: dict[str, t.Any], container: t.Any) -> None:
        job_panel = JobPanel(job)
        self.active_jobs[job["job_id"]] = job_panel
        container.mount(job_panel)

    def _handle_placeholder_visibility(self, container: t.Any) -> None:
        has_placeholder = bool(container.query("#no - jobs-label"))

        if not self.active_jobs and not has_placeholder:
            container.mount(
                Label(
                    "No active jobs detected. Start a Crackerjack job to see progress here.",
                    id="no - jobs-label",
                ),
            )
        elif self.active_jobs and has_placeholder:
            container.query("#no - jobs-label").remove()

    def _update_status_bars(self, jobs_data: dict[str, t.Any]) -> None:
        pass

    def action_refresh(self) -> None:
        asyncio.create_task(self._refresh_data())

    def action_clear(self) -> None:
        with suppress(Exception):
            for table_id in ("#jobs-table", "#services-table", "#errors-table"):
                table = self.query_one(table_id, DataTable)
                table.clear()

            container = self.query_one("#job - discovery-container")
            container.query("JobPanel").remove()
            container.query("Label").remove()
            self.active_jobs.clear()

    async def action_quit(self) -> None:
        with suppress(Exception):
            if self.refresh_timer:
                self.refresh_timer.stop()
            self._cleanup_started_services()
            self._restore_terminal()
        self.exit()

    def _restore_terminal(self) -> None:
        self.terminal_restorer.restore_terminal()

    def _restore_terminal_fallback(self) -> None:
        self.terminal_restorer.restore_terminal()

    def _signal_handler(self, _signum: t.Any, _frame: t.Any) -> None:
        with suppress(Exception):
            self._restore_terminal()
            self._cleanup_started_services()
        sys.exit(0)

    def _cleanup_started_services(self) -> None:
        self.service_manager.cleanup_services()

    def _format_time_metric(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds: .0f}s"
        if seconds < 3600:
            return f"{seconds / 60: .0f}m {seconds % 60: .0f}s"
        return f"{seconds / 3600: .0f}h {(seconds % 3600) / 60: .0f}m"

    def _format_metric_with_trend(self, value: int, trend: str = "") -> str:
        formatted = f"{value: , }"
        if trend:
            formatted += f" {trend}"
        return formatted


class JobMetrics:
    def __init__(self, job_id: str, project_path: str = "") -> None:
        self.job_id = job_id
        self.project_path = project_path
        self.project_name = Path(project_path).name if project_path else "crackerjack"
        self.start_time = time.time()
        self.last_update = time.time()
        self.completion_time: float | None = None

        self.iteration = 0
        self.max_iterations = 5
        self.current_stage = "Initializing"
        self.status = "running"
        self.message = ""

        self.stages_completed: set[str] = set()
        self.stages_failed: set[str] = set()

        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.hook_failures: list[str] = []
        self.test_failures: list[str] = []


async def run_progress_monitor(
    enable_watchdog: bool = True,
    dev_mode: bool = False,
) -> None:
    with suppress(Exception):
        console.print(
            "[bold green]🚀 Starting Crackerjack Progress Monitor[/ bold green]",
        )

        if enable_watchdog:
            console.print("[bold yellow]🐕 Service Watchdog: Enabled[/ bold yellow]")

        if dev_mode:
            console.print("[bold cyan]🛠️ Development Mode: Enabled[/ bold cyan]")

        app = CrackerjackDashboard()

        if dev_mode:
            app.dev = True

        await app.run_async()


async def run_crackerjack_with_progress(
    command: str = " / crackerjack: run",
) -> None:
    with suppress(Exception):
        console.print(
            "[bold green]🚀 Starting Crackerjack Progress Monitor[/ bold green]",
        )

        app = CrackerjackDashboard()
        await app.run_async()


def main() -> None:
    try:
        app = CrackerjackDashboard()
        app.run()
    except KeyboardInterrupt:
        with suppress(Exception):
            sys.stdout.write("\033[?25h\033[0m")
            sys.stdout.flush()
            subprocess.run(
                ["stty", "sane"],
                check=False,
                capture_output=True,
                timeout=1,
            )
    except Exception:
        with suppress(Exception):
            sys.stdout.write("\033[?25h\033[0m")
            sys.stdout.flush()
            subprocess.run(
                ["stty", "sane"],
                check=False,
                capture_output=True,
                timeout=1,
            )


if __name__ == "__main__":
    main()

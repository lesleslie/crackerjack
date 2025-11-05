import asyncio
import json
import typing as t
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from acb.console import Console
from acb.depends import depends
from rich.live import Live
from rich.table import Table

from crackerjack.agents.base import FixResult, Issue, IssueType, Priority
from crackerjack.agents.coordinator import AgentCoordinator


@dataclass
class AgentPerformanceMetrics:
    agent_name: str
    total_issues_handled: int = 0
    successful_fixes: int = 0
    failed_fixes: int = 0
    average_confidence: float = 0.0
    average_execution_time: float = 0.0
    issue_types_handled: dict[IssueType, int] = field(default_factory=dict)
    recent_failures: list[str] = field(default_factory=list)
    last_successful_fix: datetime | None = None
    regression_patterns: list[str] = field(default_factory=list)


@dataclass
class WatchdogAlert:
    level: str
    message: str
    agent_name: str | None = None
    issue_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    details: dict[str, t.Any] = field(default_factory=dict[str, t.Any])


class AIAgentWatchdog:
    def __init__(self, console: Console | None = None):
        self.console = console or depends.get_sync(Console)
        self.performance_metrics: dict[str, AgentPerformanceMetrics] = {}
        self.alerts: list[WatchdogAlert] = []
        self.known_regressions: set[str] = {
            "detect_agent_needs_complexity_22",
            "refactoring_agent_no_changes",
            "agent_coordination_infinite_loop",
        }
        self.monitoring_active = False
        self.execution_history: list[dict[str, t.Any]] = []

        self.max_execution_time = 30.0
        self.min_success_rate = 0.6
        self.max_recent_failures = 3

    async def start_monitoring(self, coordinator: AgentCoordinator) -> None:
        self.monitoring_active = True
        self.console.print("🔍 [bold green]AI Agent Watchdog Started[/bold green]")

        coordinator.initialize_agents()
        for agent in coordinator.agents:
            agent_name = agent.__class__.__name__
            if agent_name not in self.performance_metrics:
                self.performance_metrics[agent_name] = AgentPerformanceMetrics(
                    agent_name=agent_name
                )

        self.console.print(
            f"📊 Monitoring {len(coordinator.agents)} agents: {[a.__class__.__name__ for a in coordinator.agents]}"
        )

    def stop_monitoring(self) -> None:
        self.monitoring_active = False
        self.console.print("🔍 [bold yellow]AI Agent Watchdog Stopped[/bold yellow]")
        self._generate_final_report()

    async def monitor_issue_handling(
        self, agent_name: str, issue: Issue, result: FixResult, execution_time: float
    ) -> None:
        if not self.monitoring_active:
            return

        metrics = self.performance_metrics.get(agent_name)
        if not metrics:
            metrics = AgentPerformanceMetrics(agent_name=agent_name)
            self.performance_metrics[agent_name] = metrics

        metrics.total_issues_handled += 1
        if result.success:
            metrics.successful_fixes += 1
            metrics.last_successful_fix = datetime.now()
        else:
            metrics.failed_fixes += 1
            failure_key = f"{issue.type.value}_{issue.message[:50]}"
            metrics.recent_failures.append(failure_key)

            if len(metrics.recent_failures) > self.max_recent_failures:
                metrics.recent_failures.pop(0)

        total_fixes = metrics.successful_fixes + metrics.failed_fixes
        metrics.average_confidence = (
            metrics.average_confidence * (total_fixes - 1) + result.confidence
        ) / total_fixes
        metrics.average_execution_time = (
            metrics.average_execution_time * (total_fixes - 1) + execution_time
        ) / total_fixes

        metrics.issue_types_handled[issue.type] = (
            metrics.issue_types_handled.get(issue.type, 0) + 1
        )

        await self._check_for_alerts(agent_name, issue, result, execution_time, metrics)

        self.execution_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "agent": agent_name,
                "issue_type": issue.type.value,
                "issue_id": issue.id,
                "success": result.success,
                "confidence": result.confidence,
                "execution_time": execution_time,
            }
        )

        if len(self.execution_history) > 1000:
            self.execution_history = self.execution_history[-500:]

    async def _check_for_alerts(
        self,
        agent_name: str,
        issue: Issue,
        result: FixResult,
        execution_time: float,
        metrics: AgentPerformanceMetrics,
    ) -> None:
        alerts = []

        if execution_time > self.max_execution_time:
            alerts.append(
                WatchdogAlert(
                    level="warning",
                    message=f"Agent took {execution_time: .1f}s (>{self.max_execution_time}s threshold)",
                    agent_name=agent_name,
                    issue_id=issue.id,
                    details={
                        "execution_time": execution_time,
                        "threshold": self.max_execution_time,
                    },
                )
            )

        if metrics.total_issues_handled >= 5:
            success_rate = metrics.successful_fixes / metrics.total_issues_handled
            if success_rate < self.min_success_rate:
                alerts.append(
                    WatchdogAlert(
                        level="error",
                        message=f"Agent success rate {success_rate: .1 %} below {self.min_success_rate: .1 %} threshold",
                        agent_name=agent_name,
                        details={
                            "success_rate": success_rate,
                            "total_handled": metrics.total_issues_handled,
                        },
                    )
                )

        failure_signature = f"{agent_name}_{issue.type.value}_{issue.message[:30]}"
        if failure_signature in self.known_regressions and not result.success:
            alerts.append(
                WatchdogAlert(
                    level="critical",
                    message="REGRESSION DETECTED: Known failure pattern returned",
                    agent_name=agent_name,
                    issue_id=issue.id,
                    details={"regression_pattern": failure_signature},
                )
            )

        if len(metrics.recent_failures) >= self.max_recent_failures:
            unique_failures = set[t.Any](metrics.recent_failures)
            if len(unique_failures) == 1:
                alerts.append(
                    WatchdogAlert(
                        level="error",
                        message=f"Agent repeating same failure {len(metrics.recent_failures)} times",
                        agent_name=agent_name,
                        details={"repeated_failure": list[t.Any](unique_failures)[0]},
                    )
                )

        for alert in alerts:
            self.alerts.append(alert)
            await self._handle_alert(alert)

    async def _handle_alert(self, alert: WatchdogAlert) -> None:
        colors = {"warning": "yellow", "error": "red", "critical": "bold red"}
        color = colors.get(alert.level) or "white"

        icon = {"warning": "⚠️", "error": "🚨", "critical": "🔥"}[alert.level]

        self.console.print(
            f"{icon} [bold {color}]{alert.level.upper()}[/bold {color}]: {alert.message}"
        )
        if alert.agent_name:
            self.console.print(f" Agent: {alert.agent_name}")
        if alert.issue_id:
            self.console.print(f" Issue: {alert.issue_id}")

        if alert.level == "critical":
            self.console.print(" [bold red]IMMEDIATE ACTION REQUIRED[/bold red]")
            if "regression" in alert.message.lower():
                self.console.print(" → Run regression tests immediately")
                self.console.print(" → Check agent implementation for recent changes")

    def create_monitoring_dashboard(self) -> Table:
        table = Table(
            title="AI Agent Watchdog Dashboard",
            header_style="bold magenta",
        )

        table.add_column("Agent", style="cyan", width=20)
        table.add_column("Issues Handled", justify="center")
        table.add_column("Success Rate", justify="center")
        table.add_column("Avg Confidence", justify="center")
        table.add_column("Avg Time (s)", justify="center")
        table.add_column("Last Success", justify="center")
        table.add_column("Status", justify="center")

        for agent_name, metrics in self.performance_metrics.items():
            if metrics.total_issues_handled == 0:
                continue

            success_rate = metrics.successful_fixes / metrics.total_issues_handled

            status_color = "green"
            status_text = "✅ OK"

            if success_rate < self.min_success_rate:
                status_color = "red"
                status_text = "🚨 FAILING"
            elif len(metrics.recent_failures) >= 2:
                status_color = "yellow"
                status_text = "⚠️ WATCH"

            last_success = "Never"
            if metrics.last_successful_fix:
                delta = datetime.now() - metrics.last_successful_fix
                if delta.days > 0:
                    last_success = f"{delta.days}d ago"
                elif delta.seconds > 3600:
                    last_success = f"{delta.seconds / 3600}h ago"
                else:
                    last_success = f"{delta.seconds / 60}m ago"

            table.add_row(
                agent_name,
                str(metrics.total_issues_handled),
                f"{success_rate: .1 %}",
                f"{metrics.average_confidence: .2f}",
                f"{metrics.average_execution_time: .1f}",
                last_success,
                f"[{status_color}]{status_text}[/{status_color}]",
            )

        return table

    def get_recent_alerts(self, hours: int = 1) -> list[WatchdogAlert]:
        cutoff = datetime.now() - timedelta(hours=hours)
        return [alert for alert in self.alerts if alert.timestamp > cutoff]

    def _generate_final_report(self) -> None:
        self.console.print("\n📊 [bold]AI Agent Watchdog Final Report[/bold]")

        total_issues = sum(
            m.total_issues_handled for m in self.performance_metrics.values()
        )
        total_successes = sum(
            m.successful_fixes for m in self.performance_metrics.values()
        )

        if total_issues > 0:
            overall_success_rate = total_successes / total_issues
            self.console.print(
                f"Overall Success Rate: {overall_success_rate: .1 %} ({total_successes}/{total_issues})"
            )

        alert_counts = {"warning": 0, "error": 0, "critical": 0}
        for alert in self.alerts:
            alert_counts[alert.level] += 1

        self.console.print(
            f"Alerts: {alert_counts['critical']} Critical, {alert_counts['error']} Errors, {alert_counts['warning']} Warnings"
        )

        if self.performance_metrics:
            best_agent = max(
                (
                    m
                    for m in self.performance_metrics.values()
                    if m.total_issues_handled > 0
                ),
                key=lambda m: m.successful_fixes / m.total_issues_handled,
                default=None,
            )
            if best_agent:
                success_rate = (
                    best_agent.successful_fixes / best_agent.total_issues_handled
                )
                self.console.print(
                    f"Top Performer: {best_agent.agent_name} ({success_rate: .1 %} success rate)"
                )

        self._save_monitoring_report()

    def _save_monitoring_report(self) -> None:
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                name: {
                    "total_issues": m.total_issues_handled,
                    "successful_fixes": m.successful_fixes,
                    "failed_fixes": m.failed_fixes,
                    "success_rate": m.successful_fixes / m.total_issues_handled
                    if m.total_issues_handled > 0
                    else 0,
                    "average_confidence": m.average_confidence,
                    "average_execution_time": m.average_execution_time,
                    "issue_types": {
                        k.value: v for k, v in m.issue_types_handled.items()
                    },
                    "recent_failures": m.recent_failures,
                }
                for name, m in self.performance_metrics.items()
            },
            "alerts": [
                {
                    "level": a.level,
                    "message": a.message,
                    "agent": a.agent_name,
                    "issue_id": a.issue_id,
                    "timestamp": a.timestamp.isoformat(),
                    "details": a.details,
                }
                for a in self.alerts
            ],
            "execution_history": self.execution_history,
        }

        report_file = Path(".crackerjack") / "ai_agent_monitoring_report.json"
        report_file.parent.mkdir(exist_ok=True)

        with report_file.open("w") as f:
            json.dump(report_data, f, indent=2)

        self.console.print(f"📄 Detailed report saved: {report_file}")


async def run_agent_monitoring_demo() -> None:
    console = depends.get_sync(Console)
    watchdog = AIAgentWatchdog(console)

    from crackerjack.agents.base import AgentContext

    context = AgentContext(project_path=Path.cwd())
    coordinator = AgentCoordinator(context)

    await watchdog.start_monitoring(coordinator)

    with Live(
        watchdog.create_monitoring_dashboard(), refresh_per_second=1, console=console
    ) as live:
        for i in range(10):
            issue = Issue(
                id=f"demo_{i}",
                type=IssueType.COMPLEXITY if i % 2 == 0 else IssueType.FORMATTING,
                severity=Priority.HIGH,
                message=f"Demo issue {i}",
                file_path="demo.py",
            )

            success = i % 3 != 0
            result = FixResult(
                success=success,
                confidence=0.8 if success else 0.3,
                fixes_applied=["Demo fix"] if success else [],
                remaining_issues=[] if success else ["Demo failure"],
            )

            execution_time = 2.0 + (i % 5) * 0.5

            await watchdog.monitor_issue_handling(
                "DemoAgent", issue, result, execution_time
            )
            live.update(watchdog.create_monitoring_dashboard())

            await asyncio.sleep(0.5)

    watchdog.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(run_agent_monitoring_demo())

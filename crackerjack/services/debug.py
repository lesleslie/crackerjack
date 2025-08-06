import json
import logging
import os
import time
import typing as t
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .log_manager import get_log_manager
from .logging import get_logger


class AIAgentDebugger:
    def __init__(self, enabled: bool = False, verbose: bool = False) -> None:
        self.enabled = enabled
        self.verbose = verbose
        self.console = Console(force_terminal=True, stderr=True)
        self.logger = get_logger("crackerjack.ai_agent.debug")
        self.session_id = f"debug_{int(time.time())}"

        if self.enabled:
            log_manager = get_log_manager()
            self.debug_log_path = log_manager.create_debug_log_file(
                f"ai-agent-{self.session_id}"
            )
        else:
            self.debug_log_path = None

        self.mcp_operations: list[dict[str, Any]] = []
        self.agent_activities: list[dict[str, Any]] = []
        self.workflow_phases: list[dict[str, Any]] = []
        self.error_events: list[dict[str, Any]] = []

        self._debug_logging_setup = False

        if self.enabled:
            self._print_debug_header()

    def _ensure_debug_logging_setup(self) -> None:
        if not self._debug_logging_setup and self.enabled:
            self._setup_debug_logging()
            self._debug_logging_setup = True

    def _setup_debug_logging(self) -> None:
        if not self.debug_log_path:
            return

        debug_handler = logging.FileHandler(self.debug_log_path)
        debug_handler.setLevel(logging.DEBUG)
        debug_formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        )
        debug_handler.setFormatter(debug_formatter)

        loggers = [
            "crackerjack.ai_agent",
            "crackerjack.mcp",
            "crackerjack.agents",
            "crackerjack.workflow",
        ]

        for logger_name in loggers:
            logger = logging.getLogger(logger_name)
            logger.addHandler(debug_handler)
            logger.setLevel(logging.DEBUG)

    def _print_debug_header(self) -> None:
        debug_log_info = (
            f"Debug Log: {self.debug_log_path}"
            if self.debug_log_path
            else "Debug Log: None (disabled)"
        )
        header = Panel(
            f"[bold cyan]🐛 AI Agent Debug Mode Active[/bold cyan]\n"
            f"Session ID: {self.session_id}\n"
            f"{debug_log_info}\n"
            f"Verbose Mode: {'✅' if self.verbose else '❌'}",
            title="Debug Session",
            border_style="cyan",
        )
        self.console.print(header)

    @contextmanager
    def debug_operation(self, operation: str, **kwargs: Any) -> t.Iterator[str]:
        if not self.enabled:
            yield ""
            return

        self._ensure_debug_logging_setup()
        op_id = f"{operation}_{int(time.time() * 1000)}"
        start_time = time.time()

        self.logger.debug(f"Starting operation: {operation}", extra=kwargs)

        if self.verbose:
            self.console.print(f"[dim]🔍 {operation} starting...[/dim]")

        try:
            yield op_id
            duration = time.time() - start_time
            self.logger.debug(
                f"Operation completed: {operation}",
                extra={"duration": duration, **kwargs},
            )

            if self.verbose:
                self.console.print(
                    f"[dim green]✅ {operation} completed ({duration: .2f}s)[/dim green]"
                )

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(
                f"Operation failed: {operation}",
                extra={"error": str(e), "duration": duration, **kwargs},
            )

            if self.verbose:
                self.console.print(
                    f"[dim red]❌ {operation} failed ({duration: .2f}s): {e}[/dim red]"
                )
            raise

    def log_mcp_operation(
        self,
        operation_type: str,
        tool_name: str,
        params: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        duration: float | None = None,
    ) -> None:
        if not self.enabled:
            return

        self._ensure_debug_logging_setup()

        event = {
            "timestamp": datetime.now().isoformat(),
            "type": "mcp_operation",
            "operation": operation_type,
            "tool": tool_name,
            "params": params or {},
            "result": result,
            "error": error,
            "duration": duration,
        }

        self.mcp_operations.append(event)

        self.logger.info(
            f"MCP {operation_type}: {tool_name}",
            extra={
                "tool": tool_name,
                "params_count": len(params) if params else 0,
                "success": error is None,
                "duration": duration,
            },
        )

        if self.verbose:
            status_color = "green" if error is None else "red"
            status_icon = "✅" if error is None else "❌"

            self.console.print(
                f"[{status_color}]{status_icon} MCP {operation_type}[/{status_color}]: "
                f"[bold]{tool_name}[/bold]"
                + (f" ({duration: .2f}s)" if duration else "")
            )

            if error and self.verbose:
                self.console.print(f" [red]Error: {error}[/red]")

    def log_agent_activity(
        self,
        agent_name: str,
        activity: str,
        issue_id: str | None = None,
        confidence: float | None = None,
        result: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self.enabled:
            return

        self._ensure_debug_logging_setup()

        event = {
            "timestamp": datetime.now().isoformat(),
            "type": "agent_activity",
            "agent": agent_name,
            "activity": activity,
            "issue_id": issue_id,
            "confidence": confidence,
            "result": result,
            "metadata": metadata or {},
        }

        self.agent_activities.append(event)

        self.logger.info(
            f"Agent {activity}: {agent_name}",
            extra={
                "agent": agent_name,
                "activity": activity,
                "issue_id": issue_id,
                "confidence": confidence,
            },
        )

        if self.verbose:
            confidence_text = f" (confidence: {confidence: .2f})" if confidence else ""
            issue_text = f" [issue: {issue_id}]" if issue_id else ""

            self.console.print(
                f"[blue]🤖 {agent_name}[/blue]: {activity}{confidence_text}{issue_text}"
            )

    def log_workflow_phase(
        self,
        phase: str,
        status: str,
        details: dict[str, Any] | None = None,
        duration: float | None = None,
    ) -> None:
        if not self.enabled:
            return

        self._ensure_debug_logging_setup()

        event = {
            "timestamp": datetime.now().isoformat(),
            "type": "workflow_phase",
            "phase": phase,
            "status": status,
            "details": details or {},
            "duration": duration,
        }

        self.workflow_phases.append(event)

        self.logger.info(
            f"Workflow {status}: {phase}",
            extra={"phase": phase, "status": status, "duration": duration},
        )

        if self.verbose:
            status_colors = {
                "started": "yellow",
                "completed": "green",
                "failed": "red",
                "skipped": "dim",
            }

            color = status_colors.get(status, "white")
            duration_text = f" ({duration: .2f}s)" if duration else ""

            self.console.print(
                f"[{color}]📋 Workflow {status}: {phase}{duration_text}[/{color}]"
            )

    def log_error_event(
        self,
        error_type: str,
        message: str,
        context: dict[str, Any] | None = None,
        traceback_info: str | None = None,
    ) -> None:
        if not self.enabled:
            return

        self._ensure_debug_logging_setup()

        event = {
            "timestamp": datetime.now().isoformat(),
            "type": "error_event",
            "error_type": error_type,
            "message": message,
            "context": context or {},
            "traceback": traceback_info,
        }

        self.error_events.append(event)

        self.logger.error(
            f"Error: {error_type}",
            extra={"error_type": error_type, "message": message, "context": context},
        )

        if self.verbose:
            self.console.print(f"[red]💥 {error_type}: {message}[/red]")

    def print_debug_summary(self) -> None:
        if not self.enabled:
            return

        table = Table(title="AI Agent Debug Summary", show_header=True)
        table.add_column("Category", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Details", style="dim")

        table.add_row(
            "MCP Operations",
            str(len(self.mcp_operations)),
            f"Tools used: {len(set(op['tool'] for op in self.mcp_operations))}",
        )

        table.add_row(
            "Agent Activities",
            str(len(self.agent_activities)),
            f"Agents active: {len(set(act['agent'] for act in self.agent_activities))}",
        )

        table.add_row(
            "Workflow Phases",
            str(len(self.workflow_phases)),
            f"Completed: {len([p for p in self.workflow_phases if p['status'] == 'completed'])}",
        )

        table.add_row(
            "Error Events",
            str(len(self.error_events)),
            f"Types: {len(set(err['error_type'] for err in self.error_events))}",
        )

        self.console.print(table)

        if self.verbose and self.agent_activities:
            self._print_agent_activity_breakdown()

        if self.verbose and self.mcp_operations:
            self._print_mcp_operation_breakdown()

        self.console.print(
            f"\n[dim]📝 Full debug log available at: {self.debug_log_path}[/dim]"
            if self.debug_log_path
            else ""
        )

    def _print_agent_activity_breakdown(self) -> None:
        agent_stats = {}
        for activity in self.agent_activities:
            agent = activity["agent"]
            if agent not in agent_stats:
                agent_stats[agent] = {
                    "activities": 0,
                    "avg_confidence": 0.0,
                    "confidences": [],
                }

            agent_stats[agent]["activities"] += 1
            if activity.get("confidence"):
                agent_stats[agent]["confidences"].append(activity["confidence"])

        for agent, stats in agent_stats.items():
            if stats["confidences"]:
                stats["avg_confidence"] = sum(stats["confidences"]) / len(
                    stats["confidences"]
                )

        table = Table(title="Agent Activity Breakdown", show_header=True)
        table.add_column("Agent", style="blue")
        table.add_column("Activities", justify="right", style="green")
        table.add_column("Avg Confidence", justify="right", style="yellow")

        for agent, stats in sorted(agent_stats.items()):
            confidence_text = (
                f"{stats['avg_confidence']: .2f}"
                if stats["avg_confidence"] > 0
                else "N / A"
            )
            table.add_row(agent, str(stats["activities"]), confidence_text)

        self.console.print(table)

    def _print_mcp_operation_breakdown(self) -> None:
        tool_stats = {}
        for op in self.mcp_operations:
            tool = op["tool"]
            if tool not in tool_stats:
                tool_stats[tool] = {"calls": 0, "errors": 0, "total_duration": 0.0}

            tool_stats[tool]["calls"] += 1
            if op.get("error"):
                tool_stats[tool]["errors"] += 1
            if op.get("duration"):
                tool_stats[tool]["total_duration"] += op["duration"]

        table = Table(title="MCP Tool Usage", show_header=True)
        table.add_column("Tool", style="cyan")
        table.add_column("Calls", justify="right", style="green")
        table.add_column("Errors", justify="right", style="red")
        table.add_column("Avg Duration", justify="right", style="yellow")

        for tool, stats in sorted(tool_stats.items()):
            avg_duration = (
                stats["total_duration"] / stats["calls"] if stats["calls"] > 0 else 0
            )
            table.add_row(
                tool,
                str(stats["calls"]),
                str(stats["errors"]),
                f"{avg_duration: .2f}s" if avg_duration > 0 else "N / A",
            )

        self.console.print(table)

    def export_debug_data(self, output_path: Path | None = None) -> Path:
        if not self.enabled:
            return Path("debug_not_enabled.json")

        if output_path is None:
            output_path = Path(f"crackerjack-debug-export-{self.session_id}.json")

        debug_data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "mcp_operations": self.mcp_operations,
            "agent_activities": self.agent_activities,
            "workflow_phases": self.workflow_phases,
            "error_events": self.error_events,
        }

        with output_path.open("w") as f:
            json.dump(debug_data, f, indent=2, default=str)

        self.logger.info(f"Debug data exported to {output_path}")
        return output_path


class NoOpDebugger:
    def __init__(self) -> None:
        self.enabled = False
        self.verbose = False
        self.debug_log_path = None
        self.session_id = "disabled"

    def debug_operation(self, operation: str, **kwargs: Any) -> t.Iterator[str]:
        yield ""

    def log_mcp_operation(
        self,
        operation_type: str,
        tool_name: str,
        params: dict[str, Any] | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        duration: float | None = None,
    ) -> None:
        pass

    def log_agent_activity(
        self,
        agent_name: str,
        activity: str,
        issue_id: str | None = None,
        confidence: float | None = None,
        result: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        pass

    def log_workflow_phase(
        self,
        phase: str,
        status: str,
        details: dict[str, Any] | None = None,
        duration: float | None = None,
    ) -> None:
        pass

    def log_error_event(
        self,
        error_type: str,
        message: str,
        context: dict[str, Any] | None = None,
        traceback_info: str | None = None,
    ) -> None:
        pass

    def print_debug_summary(self) -> None:
        pass

    def export_debug_data(self, output_path: Path | None = None) -> Path:
        return Path("debug_not_enabled.json")


_ai_agent_debugger: AIAgentDebugger | NoOpDebugger | None = None


def get_ai_agent_debugger() -> AIAgentDebugger | NoOpDebugger:
    global _ai_agent_debugger
    if _ai_agent_debugger is None:
        debug_enabled = os.environ.get("AI_AGENT_DEBUG", "0") == "1"
        verbose_mode = os.environ.get("AI_AGENT_VERBOSE", "0") == "1"

        if debug_enabled:
            _ai_agent_debugger = AIAgentDebugger(
                enabled=debug_enabled, verbose=verbose_mode
            )
        else:
            _ai_agent_debugger = NoOpDebugger()
    return _ai_agent_debugger


def enable_ai_agent_debugging(verbose: bool = False) -> AIAgentDebugger:
    global _ai_agent_debugger
    _ai_agent_debugger = AIAgentDebugger(enabled=True, verbose=verbose)
    return _ai_agent_debugger


def disable_ai_agent_debugging() -> None:
    global _ai_agent_debugger
    if _ai_agent_debugger:
        _ai_agent_debugger.enabled = False

from __future__ import annotations

import logging
import re
import typing as t
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

from crackerjack.cli.formatting import separator as make_separator
from crackerjack.code_cleaner import CodeCleaner
from crackerjack.config import get_console_width
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.decorators import handle_errors
from crackerjack.models.protocols import (
    ConfigMergeServiceProtocol,
    FileSystemInterface,
    GitInterface,
    HookManager,
    MemoryOptimizerProtocol,
    OptionsProtocol,
    PublishManager,
    TestManagerProtocol,
)
from crackerjack.models.task import HookResult
from crackerjack.services.memory_optimizer import create_lazy_service

try:
    from crackerjack.services.monitoring.performance_cache import (
        FileSystemCache,
        GitOperationCache,
    )
except Exception:  # pragma: no cover - optional legacy module
    FileSystemCache = t.Any  # type: ignore[assignment]
    GitOperationCache = t.Any  # type: ignore[assignment]
from crackerjack.services.parallel_executor import (
    AsyncCommandExecutor,
    ParallelHookExecutor,
)

if t.TYPE_CHECKING:
    pass  # All imports moved to top-level for runtime availability


class PhaseCoordinator:
    def __init__(
        self,
        *,
        console: Console | None = None,
        pkg_path: Path | None = None,
        session: SessionCoordinator | None = None,
        filesystem: FileSystemInterface | None = None,
        git_service: GitInterface | None = None,
        hook_manager: HookManager | None = None,
        test_manager: TestManagerProtocol | None = None,
        publish_manager: PublishManager | None = None,
        config_merge_service: ConfigMergeServiceProtocol | None = None,
        logger: logging.Logger | None = None,
        memory_optimizer: MemoryOptimizerProtocol | None = None,
        parallel_executor: ParallelHookExecutor | None = None,
        async_executor: AsyncCommandExecutor | None = None,
        git_cache: GitOperationCache | None = None,
        filesystem_cache: FileSystemCache | None = None,
        settings: t.Any | None = None,
    ) -> None:
        from crackerjack.config import load_settings
        from crackerjack.config.settings import CrackerjackSettings
        from crackerjack.managers.hook_manager import HookManagerImpl
        from crackerjack.managers.publish_manager import PublishManagerImpl
        from crackerjack.managers.test_manager import TestManagementImpl
        from crackerjack.services.filesystem import FileSystemService
        from crackerjack.services.git import GitService

        self.console = console or Console()
        self.pkg_path = pkg_path or Path.cwd()
        self.session = session or SessionCoordinator(
            console=self.console, pkg_path=self.pkg_path
        )

        self._settings = settings or load_settings(CrackerjackSettings)

        self.filesystem = filesystem or FileSystemService()
        self.git_service = git_service or GitService(
            console=self.console, pkg_path=self.pkg_path
        )
        self.hook_manager = hook_manager or HookManagerImpl(
            pkg_path=self.pkg_path,
            verbose=getattr(self._settings.execution, "verbose", False),
            quiet=False,
            console=self.console,
            settings=self._settings,
        )
        self.test_manager = test_manager or TestManagementImpl(
            console=self.console, pkg_path=self.pkg_path
        )
        self.publish_manager = publish_manager or PublishManagerImpl(
            console=self.console, pkg_path=self.pkg_path
        )
        self.config_merge_service = config_merge_service

        self.code_cleaner = CodeCleaner(
            console=self.console,
            base_directory=self.pkg_path,
            file_processor=None,
            error_handler=None,
            pipeline=None,
            logger=None,
            security_logger=None,
            backup_service=None,
        )

        self._logger = logger or logging.getLogger(__name__)

        self._memory_optimizer = memory_optimizer
        self._parallel_executor = parallel_executor
        self._async_executor = async_executor
        self._git_cache = git_cache
        self._filesystem_cache = filesystem_cache

        self._last_hook_summary: dict[str, t.Any] | None = None
        self._last_hook_results: list[HookResult] = []

        self._lazy_autofix = create_lazy_service(
            lambda: AutofixCoordinator(pkg_path=pkg_path),
            "autofix_coordinator",
        )
        self.console.print()

        # Track if fast hooks have already started in this session to prevent duplicates
        self._fast_hooks_started: bool = False

    @property
    def logger(self) -> logging.Logger:
        return self._logger

    @logger.setter
    def logger(self, value: logging.Logger) -> None:
        self._logger = value

    # --- Output/formatting helpers -------------------------------------------------
    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Remove ANSI escape sequences (SGR and cursor controls).

        This is more comprehensive than stripping only color codes ending with 'm'.
        """
        ansi_re = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_re.sub("", text)

    def _is_plain_output(self) -> bool:
        """Detect if we should avoid rich formatting entirely.

        Leverages ACB Console's plain-mode flag when available and falls back
        to Rich Console properties when not.
        """
        try:
            if bool(getattr(self.console, "_plain_mode", False)):
                return True
            # Fallback on Rich Console capabilities
            is_tty = bool(getattr(self.console, "is_terminal", True))
            color_system = getattr(self.console, "color_system", None)
            return (not is_tty) or (color_system in (None, "null"))
        except Exception:
            # Prefer plain in ambiguous environments
            return True

    @handle_errors
    def run_cleaning_phase(self, options: OptionsProtocol) -> bool:
        if not getattr(options, "clean", False):
            return True

        self.session.track_task("cleaning", "Code cleaning")
        self._display_cleaning_header()
        return self._execute_cleaning_process()

    @handle_errors
    def run_configuration_phase(self, options: OptionsProtocol) -> bool:
        if options.no_config_updates:
            return True
        self.session.track_task("configuration", "Configuration updates")
        self.console.print(
            "[dim]⚙️ Configuration phase skipped (no automated updates defined).[/dim]"
        )
        self.session.complete_task(
            "configuration", "No configuration updates were required."
        )
        return True

    @handle_errors
    def run_hooks_phase(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            return True

        if not self.run_fast_hooks_only(options):
            return False

        return self.run_comprehensive_hooks_only(options)

    def run_fast_hooks_only(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            self.console.print("[yellow]⚠️[/yellow] Skipping fast hooks (--skip-hooks)")
            return True

        # Prevent multiple fast-hook runs in a single workflow session unless
        # explicitly reset by post-cleaning sanity check.
        if getattr(self, "_fast_hooks_started", False):
            self.logger.debug("Duplicate fast hooks invocation detected; skipping")
            return True

        # Mark fast hooks as started immediately to prevent duplicate calls in case of failures
        self._fast_hooks_started = True
        self.session.track_task("hooks_fast", "Fast quality checks")

        # Fast hooks get 2 attempts (auto-fix on failure), comprehensive hooks run once
        max_attempts = 2
        attempt = 0

        while attempt < max_attempts:
            attempt += 1

            # Display stage header for each attempt
            if attempt > 1:
                self.console.print(
                    f"\n[yellow]♻️[/yellow]  Verification Retry {attempt}/{max_attempts}\n"
                )

            self._display_hook_phase_header(
                "FAST HOOKS",
                "Formatters, import sorting, and quick static analysis",
            )

            # Run hooks (now configured to run in fix mode by default)
            success = self._execute_hooks_once(
                "fast", self.hook_manager.run_fast_hooks, options, attempt
            )

            if success:
                break

            # Fast iteration mode intentionally avoids retries
            if getattr(options, "fast_iteration", False):
                break

            # If we have more attempts, continue to retry to verify fixes worked
            if attempt < max_attempts:
                self._display_hook_failures("fast", self._last_hook_results, options)

        summary = self._last_hook_summary or {}
        details = self._format_hook_summary(summary)

        if success:
            self.session.complete_task("hooks_fast", details=details)
        else:
            self.session.fail_task("hooks_fast", "Fast hook failures detected")

        # Ensure fast hooks output is fully rendered before comprehensive hooks start
        self.console.print()

        return success

    def run_comprehensive_hooks_only(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            self.console.print(
                "[yellow]⚠️[/yellow] Skipping comprehensive hooks (--skip-hooks)"
            )
            return True

        self.session.track_task("hooks_comprehensive", "Comprehensive quality checks")
        self._display_hook_phase_header(
            "COMPREHENSIVE HOOKS",
            "Type, security, and complexity checking",
        )

        # Comprehensive hooks run once (no retry)
        success = self._execute_hooks_once(
            "comprehensive",
            self.hook_manager.run_comprehensive_hooks,
            options,
            attempt=1,
        )

        if not success:
            self._display_hook_failures(
                "comprehensive", self._last_hook_results, options
            )

        summary = self._last_hook_summary or {}
        details = self._format_hook_summary(summary)

        if success:
            self.session.complete_task("hooks_comprehensive", details=details)
        else:
            self.session.fail_task(
                "hooks_comprehensive", "Comprehensive hook failures detected"
            )

        return success

    @handle_errors
    def run_testing_phase(self, options: OptionsProtocol) -> bool:
        if not getattr(options, "test", False) and not getattr(
            options, "run_tests", False
        ):
            return True
        self.session.track_task("testing", "Test execution")
        self.console.print("\n" + make_separator("-"))
        self.console.print(
            "[bold bright_blue]🧪 TESTS[/bold bright_blue] [bold bright_white]Running test suite[/bold bright_white]",
        )
        self.console.print(make_separator("-") + "\n")
        if not self.test_manager.validate_test_environment():
            self.session.fail_task("testing", "Test environment validation failed")
            return False
        test_success = self.test_manager.run_tests(options)
        if test_success:
            coverage_info = self.test_manager.get_coverage()
            self.session.complete_task(
                "testing",
                f"Tests passed, coverage: {coverage_info.get('total_coverage', 0):.1f}%",
            )
        else:
            self.session.fail_task("testing", "Tests failed")

        return test_success

    @handle_errors
    def run_publishing_phase(self, options: OptionsProtocol) -> bool:
        version_type = self._determine_version_type(options)
        if not version_type:
            return True

        self.session.track_task("publishing", f"Publishing ({version_type})")
        return self._execute_publishing_workflow(options, version_type)

    @handle_errors
    def run_commit_phase(self, options: OptionsProtocol) -> bool:
        if not options.commit:
            return True

        # Skip if publishing phase already handled commits
        # (Publishing phase handles both pre-publish and version-bump commits when -c is used)
        version_type = self._determine_version_type(options)
        if version_type:
            # Publishing workflow already committed everything
            self.console.print(
                "[dim]ℹ️ Commit phase skipped (handled by publish workflow)[/dim]"
            )
            return True

        # Display commit & push header
        self._display_commit_push_header()
        self.session.track_task("commit", "Git commit and push")
        changed_files = self.git_service.get_changed_files()
        if not changed_files:
            return self._handle_no_changes_to_commit()
        commit_message = self._get_commit_message(changed_files, options)
        return self._execute_commit_and_push(changed_files, commit_message)

    def _execute_hooks_once(
        self,
        suite_name: str,
        hook_runner: t.Callable[[], list[HookResult]],
        options: OptionsProtocol,
        attempt: int,
    ) -> bool:
        """Execute a hook suite once with progress bar (no retry logic - retry is handled at stage level)."""
        self._last_hook_summary = None
        self._last_hook_results = []

        hook_count = self.hook_manager.get_hook_count(suite_name)
        progress = self._create_progress_bar()

        callbacks = self._setup_progress_callbacks(progress)
        elapsed_time = self._run_hooks_with_progress(
            suite_name, hook_runner, progress, hook_count, attempt, callbacks
        )

        if elapsed_time is None:
            return False

        return self._process_hook_results(suite_name, elapsed_time, attempt)

    def _create_progress_bar(self) -> Progress:
        """Create compact progress bar for hook execution."""
        return Progress(
            SpinnerColumn(spinner_name="dots"),
            TextColumn("[cyan]{task.description}[/cyan]"),
            BarColumn(bar_width=20),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=self.console,
            transient=True,
        )

    def _setup_progress_callbacks(
        self, progress: Progress
    ) -> dict[str, t.Callable[[int, int], None] | None | dict[str, t.Any]]:
        """Setup progress callbacks and store originals for restoration."""
        task_id_holder = {"task_id": None}

        def update_progress(completed: int, total: int) -> None:
            if task_id_holder["task_id"] is not None:
                progress.update(task_id_holder["task_id"], completed=completed)

        def update_progress_started(started: int, total: int) -> None:
            if task_id_holder["task_id"] is not None:
                progress.update(task_id_holder["task_id"], completed=started)

        original_callback = getattr(self.hook_manager, "_progress_callback", None)
        original_start_callback = getattr(
            self.hook_manager, "_progress_start_callback", None
        )

        self.hook_manager._progress_callback = update_progress
        self.hook_manager._progress_start_callback = update_progress_started

        return {
            "update": update_progress,
            "update_started": update_progress_started,
            "original": original_callback,
            "original_started": original_start_callback,
            "task_id_holder": task_id_holder,
        }

    def _run_hooks_with_progress(
        self,
        suite_name: str,
        hook_runner: t.Callable[[], list[HookResult]],
        progress: Progress,
        hook_count: int,
        attempt: int,
        callbacks: dict[str, t.Any],
    ) -> float | None:
        """Run hooks with progress tracking, return elapsed time or None on error."""
        try:
            with progress:
                task_id = progress.add_task(
                    f"Running {suite_name} hooks:",
                    total=hook_count,
                )
                callbacks["task_id_holder"]["task_id"] = task_id

                import time

                start_time = time.time()
                hook_results = hook_runner()
                self._last_hook_results = hook_results
                elapsed_time = time.time() - start_time

                return elapsed_time

        except Exception as exc:
            self._handle_hook_execution_error(suite_name, exc, attempt)
            return None
        finally:
            self._restore_progress_callbacks(callbacks)

    def _handle_hook_execution_error(
        self, suite_name: str, exc: Exception, attempt: int
    ) -> None:
        """Handle errors during hook execution."""
        self.console.print(
            f"[red]❌[/red] {suite_name.title()} hooks encountered an unexpected error: {exc}"
        )
        self.logger.exception(
            "Hook execution raised exception",
            extra={"suite": suite_name, "attempt": attempt},
        )

    def _restore_progress_callbacks(self, callbacks: dict[str, t.Any]) -> None:
        """Restore original progress callbacks."""
        self.hook_manager._progress_callback = callbacks["original"]
        self.hook_manager._progress_start_callback = callbacks["original_started"]

    def _process_hook_results(
        self, suite_name: str, elapsed_time: float, attempt: int
    ) -> bool:
        """Process hook results and determine success."""
        summary = self.hook_manager.get_hook_summary(
            self._last_hook_results, elapsed_time=elapsed_time
        )
        self._last_hook_summary = summary
        self._report_hook_results(suite_name, self._last_hook_results, summary, attempt)

        if summary.get("failed", 0) == 0 == summary.get("errors", 0):
            return True

        self.logger.warning(
            "Hook suite reported failures",
            extra={
                "suite": suite_name,
                "attempt": attempt,
                "failed": summary.get("failed", 0),
                "errors": summary.get("errors", 0),
            },
        )
        return False

    def _display_hook_phase_header(self, title: str, description: str) -> None:
        sep = make_separator("-")
        self.console.print("\n" + sep)
        # Combine title and description into a single line with leading icon
        pretty_title = title.title()
        message = (
            f"[bold bright_cyan]🔍 {pretty_title}[/bold bright_cyan][bold bright_white]"
            f" - {description}[/bold bright_white]"
        )
        self.console.print(message)
        self.console.print(sep + "\n")

    def _report_hook_results(
        self,
        suite_name: str,
        results: list[HookResult],
        summary: dict[str, t.Any],
        attempt: int,
    ) -> None:
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        errors = summary.get("errors", 0)
        duration = summary.get("total_duration", 0.0)

        if total == 0:
            self.console.print(
                f"[yellow]⚠️[/yellow] No {suite_name} hooks are configured for this project."
            )
            return

        base_message = (
            f"{suite_name.title()} hooks attempt {attempt}: "
            f"{passed}/{total} passed in {duration:.2f}s"
        )

        if failed or errors:
            self.console.print(f"\n[red]❌[/red] {base_message}\n")
            # Always show a results table to aid debugging when there are failures
            self._render_hook_results_table(suite_name, results)
        else:
            self.console.print(f"\n[green]✅[/green] {base_message}\n")
            self._render_hook_results_table(suite_name, results)

    def _render_hook_results_table(
        self,
        suite_name: str,
        results: list[HookResult],
    ) -> None:
        if not results:
            return

        if self._is_plain_output():
            self._render_plain_hook_results(suite_name, results)
        else:
            self._render_rich_hook_results(suite_name, results)

    def _render_plain_hook_results(
        self, suite_name: str, results: list[HookResult]
    ) -> None:
        """Render hook results in plain text format."""
        self.console.print(f"{suite_name.title()} Hook Results:", highlight=False)

        stats = self._calculate_hook_statistics(results)
        hooks_to_show = stats["failed_hooks"] or results

        for result in hooks_to_show:
            self._print_plain_hook_result(result)

        if not stats["failed_hooks"] and results:
            self._print_plain_summary(stats)

        self.console.print()

    def _calculate_hook_statistics(self, results: list[HookResult]) -> dict[str, t.Any]:
        """Calculate statistics from hook results."""
        passed_hooks = [r for r in results if r.status.lower() in {"passed", "success"}]
        failed_hooks = [
            r for r in results if r.status.lower() in {"failed", "error", "timeout"}
        ]
        other_hooks = [
            r
            for r in results
            if r.status.lower()
            not in {"passed", "success", "failed", "error", "timeout"}
        ]

        # Calculate total issues using issues_count (which may be larger than len(issues_found))
        # Passed hooks always contribute 0 issues
        # Config errors (is_config_error=True) are counted separately
        total_issues = 0
        config_errors = 0
        for r in results:
            if r.status == "passed":
                continue
            # Count config errors separately - they're not code quality issues
            if hasattr(r, "is_config_error") and r.is_config_error:
                config_errors += 1
                continue
            # Use issues_count directly (don't fall back to len(issues_found))
            # because issues_found may contain error detail lines, not actual issues
            if hasattr(r, "issues_count"):
                total_issues += r.issues_count
            elif r.issues_found:
                # Legacy fallback for old HookResults without issues_count
                total_issues += len(r.issues_found)

        return {
            "total_hooks": len(results),
            "passed_hooks": passed_hooks,
            "failed_hooks": failed_hooks,
            "other_hooks": other_hooks,
            "total_passed": len(passed_hooks),
            "total_failed": len(failed_hooks),
            "total_other": len(other_hooks),
            "total_issues_found": total_issues,
            "config_errors": config_errors,
        }

    def _print_plain_hook_result(self, result: HookResult) -> None:
        """Print a single hook result in plain format."""
        name = self._strip_ansi(result.name)
        status = result.status.upper()
        duration = f"{result.duration:.2f}s"

        # Determine issues display (matches Rich table logic)
        if result.status == "passed":
            issues = "0"
        elif hasattr(result, "is_config_error") and result.is_config_error:
            # Config/tool error - show simple symbol instead of misleading count
            issues = "[yellow]![/yellow]"
        else:
            # For failed hooks with code violations, use issues_count
            # Don't fall back to len(issues_found) - it may contain error detail lines
            issues = str(result.issues_count if hasattr(result, "issues_count") else 0)

        self.console.print(
            f"  - {name} :: {status} | {duration} | issues={issues}",
        )

    def _print_plain_summary(self, stats: dict[str, t.Any]) -> None:
        """Print summary statistics in plain format."""
        issues_text = f"{stats['total_issues_found']} issues found"
        if stats.get("config_errors", 0) > 0:
            issues_text += f" ({stats['config_errors']} config)"

        self.console.print(
            f"  Summary: {stats['total_passed']}/{stats['total_hooks']} hooks passed, {issues_text}",
            highlight=False,
        )

    def _render_rich_hook_results(
        self, suite_name: str, results: list[HookResult]
    ) -> None:
        """Render hook results in Rich format."""
        stats = self._calculate_hook_statistics(results)
        summary_text = self._build_summary_text(stats)
        table = self._build_results_table(results)
        panel = self._build_results_panel(suite_name, table, summary_text)

        self.console.print(panel)

        # Add legend if any config errors are present
        has_config_errors = any(
            hasattr(r, "is_config_error") and r.is_config_error for r in results
        )
        if has_config_errors:
            self.console.print(
                "  [dim][yellow]![/yellow] = Configuration or tool error (not code "
                "issues)[/dim]"
            )

        self.console.print()

    @staticmethod
    def _build_summary_text(stats: dict[str, t.Any]) -> str:
        """Build summary text for Rich display."""
        summary_text = (
            f"Total: [white]{stats['total_hooks']}[/white] | Passed:"
            f" [green]{stats['total_passed']}[/green] | Failed: [red]{stats['total_failed']}[/red]"
        )
        if stats["total_other"] > 0:
            summary_text += f" | Other: [yellow]{stats['total_other']}[/yellow]"

        # Show issues found with config count in parentheses if present
        issues_text = f"[white]{stats['total_issues_found']}[/white]"
        if stats.get("config_errors", 0) > 0:
            issues_text += f" [dim]({stats['config_errors']} config)[/dim]"
        summary_text += f" | Issues found: {issues_text}"
        return summary_text

    def _build_results_table(self, results: list[HookResult]) -> Table:
        """Build Rich table from hook results."""
        table = Table(
            box=box.SIMPLE,
            header_style="bold bright_white",
            expand=True,
        )
        table.add_column("Hook", style="cyan", overflow="fold", min_width=20)
        table.add_column("Status", style="bright_white", min_width=8)
        table.add_column("Duration", justify="right", style="magenta", min_width=10)
        table.add_column("Issues", justify="right", style="bright_white", min_width=8)

        for result in results:
            status_style = self._status_style(result.status)
            # Passed hooks always show 0 issues (files processed != issues found)
            if result.status == "passed":
                issues_display = "0"
            elif hasattr(result, "is_config_error") and result.is_config_error:
                # Config/tool error - show simple symbol instead of misleading count
                # Using "!" instead of emoji to avoid width issues in terminal
                issues_display = "[yellow]![/yellow]"
            else:
                # For failed hooks with code violations, use issues_count
                # IMPORTANT: Use issues_count directly, don't fall back to len(issues_found)
                # because issues_found may contain display messages that aren't actual issues
                issues_display = str(
                    result.issues_count if hasattr(result, "issues_count") else 0
                )
            table.add_row(
                self._strip_ansi(result.name),
                f"[{status_style}]{result.status.upper()}[/{status_style}]",
                f"{result.duration:.2f}s",
                issues_display,
            )

        return table

    def _format_issues(self, issues: list[str]) -> list[dict[str, str | int | None]]:
        """Format hook issues into structured dictionaries."""

        def _format_single_issue(issue):
            if hasattr(issue, "file_path") and hasattr(issue, "line_number"):
                return {
                    "file": str(getattr(issue, "file_path", "unknown")),
                    "line": getattr(issue, "line_number", 0),
                    "message": getattr(issue, "message", str(issue)),
                    "code": getattr(issue, "code", None),
                    "severity": getattr(issue, "severity", "warning"),
                    "suggestion": getattr(issue, "suggestion", None),
                }

            return {
                "file": "unknown",
                "line": 0,
                "message": str(issue),
                "code": None,
                "severity": "warning",
                "suggestion": None,
            }

        return [_format_single_issue(issue) for issue in issues]

    def to_json(self, results: list[HookResult], suite_name: str = "") -> dict:
        """Export hook results as structured JSON for automation.

        Args:
            results: List of HookResult objects to export
            suite_name: Optional suite name (fast/comprehensive)

        Returns:
            Dictionary with structured results data

        Example:
            >>> json_data = coordinator.to_json(results, "comprehensive")
            >>> print(json.dumps(json_data, indent=2))
        """
        return {
            "suite": suite_name,
            "summary": self._calculate_hook_statistics(results),
            "hooks": [
                {
                    "name": result.name,
                    "status": result.status,
                    "duration": round(result.duration, 2),
                    "issues_count": len(result.issues_found)
                    if result.issues_found
                    else 0,
                    "issues": self._format_issues(result.issues_found)
                    if result.issues_found
                    else [],
                }
                for result in results
            ],
        }

    def _build_results_panel(
        self, suite_name: str, table: Table, summary_text: str
    ) -> Panel:
        """Build Rich panel containing results table."""
        return Panel(
            table,
            title=f"[bold]{suite_name.title()} Hook Results[/bold]",
            subtitle=summary_text,
            border_style="cyan" if suite_name == "fast" else "magenta",
            padding=(0, 1),
            width=get_console_width(),
            expand=True,
        )

    def _format_failing_hooks(
        self, suite_name: str, results: list[HookResult]
    ) -> list[HookResult]:
        """Get list of failing hooks and print header.

        Returns:
            List of failing hook results
        """
        failing = [
            result
            for result in results
            if result.status.lower() in {"failed", "error", "timeout"}
        ]

        if failing:
            self.console.print(
                f"[red]Details for failing {suite_name} hooks:[/red]", highlight=False
            )

        return failing

    def _display_issue_details(self, result: HookResult) -> None:
        """Display specific issue details if found."""
        if not result.issues_found:
            return

        for issue in result.issues_found:
            self.console.print(f"      - {self._strip_ansi(issue)}", highlight=False)

    def _display_timeout_info(self, result: HookResult) -> None:
        """Display timeout information."""
        if result.is_timeout:
            self.console.print(
                "      - Hook timed out during execution", highlight=False
            )

    def _display_exit_code_info(self, result: HookResult) -> None:
        """Display exit code with helpful context."""
        if result.exit_code is not None and result.exit_code != 0:
            exit_msg = f"Exit code: {result.exit_code}"
            # Add helpful context for common exit codes
            if result.exit_code == 137:
                exit_msg += " (killed - possibly timeout or out of memory)"
            elif result.exit_code == 139:
                exit_msg += " (segmentation fault)"
            elif result.exit_code in {126, 127}:
                exit_msg += " (command not found or not executable)"
            self.console.print(f"      - {exit_msg}", highlight=False)

    def _display_error_message(self, result: HookResult) -> None:
        """Display error message preview."""
        if result.error_message:
            # Show first line or first 200 chars of error
            error_preview = result.error_message.split("\n")[0][:200]
            self.console.print(f"      - Error: {error_preview}", highlight=False)

    def _display_generic_failure(self, result: HookResult) -> None:
        """Display generic failure message if no specific details available."""
        if not result.is_timeout and not result.exit_code and not result.error_message:
            self.console.print(
                "      - Hook failed with no detailed error information",
                highlight=False,
            )

    def _display_hook_failures(
        self,
        suite_name: str,
        results: list[HookResult],
        options: OptionsProtocol,
    ) -> None:
        # Show detailed failures if --verbose or --ai-debug flag is set
        if not (options.verbose or getattr(options, "ai_debug", False)):
            return

        failing = self._format_failing_hooks(suite_name, results)
        if not failing:
            return

        # Process each failing hook
        for result in failing:
            self._print_single_hook_failure(result)

        self.console.print()

    def _print_single_hook_failure(self, result: HookResult) -> None:
        """Print details of a single hook failure."""
        self.console.print(
            f"  - [red]{self._strip_ansi(result.name)}[/red] ({result.status})",
            highlight=False,
        )

        if result.issues_found:
            self._print_hook_issues(result)
        else:
            self._display_failure_reasons(result)

    def _print_hook_issues(self, result: HookResult) -> None:
        """Print issues found for a hook."""
        # Type assertion: issues_found is never None after __post_init__
        assert result.issues_found is not None
        for issue in result.issues_found:
            # Show the issue with consistent formatting
            self.console.print(f"      - {self._strip_ansi(issue)}", highlight=False)

    def _display_failure_reasons(self, result: HookResult) -> None:
        """Display reasons why a hook failed."""
        self._display_timeout_info(result)
        self._display_exit_code_info(result)
        self._display_error_message(result)
        self._display_generic_failure(result)

    def _display_cleaning_header(self) -> None:
        sep = make_separator("-")
        self.console.print("\n" + sep)
        self.console.print("[bold bright_green]🧹 CLEANING[/bold bright_green]")
        self.console.print(sep + "\n")

    def _execute_cleaning_process(self) -> bool:
        py_files = list(self.pkg_path.rglob("*.py"))
        if not py_files:
            return self._handle_no_files_to_clean()

        cleaned_files = self._clean_python_files(py_files)
        self._report_cleaning_results(cleaned_files)
        return True

    def _handle_no_files_to_clean(self) -> bool:
        self.console.print("No Python files found to clean")
        self.session.complete_task("cleaning", "No files to clean")
        return True

    def _clean_python_files(self, files: list[Path]) -> list[str]:
        cleaned_files = []
        for file in files:
            if self.code_cleaner.should_process_file(file):
                result = self.code_cleaner.clean_file(file)
                if result.success:
                    cleaned_files.append(str(file))
        return cleaned_files

    def _report_cleaning_results(self, cleaned_files: list[str]) -> None:
        if cleaned_files:
            self.console.print(f"Cleaned {len(cleaned_files)} files")
            self.session.complete_task(
                "cleaning", f"Cleaned {len(cleaned_files)} files"
            )
        else:
            self.console.print("No cleaning needed for any files")
            self.session.complete_task("cleaning", "No cleaning needed")

    @staticmethod
    def _determine_version_type(options: OptionsProtocol) -> str | None:
        return options.publish or options.all or options.bump

    def _execute_publishing_workflow(
        self, options: OptionsProtocol, version_type: str
    ) -> bool:
        # Store reference to current HEAD to allow rollback if needed
        original_head = (
            self.git_service.get_current_commit_hash()
            if hasattr(self.git_service, "get_current_commit_hash")
            else None
        )

        # STAGE 0: Pre-publish commit if needed
        if not self._handle_pre_publish_commit(options):
            return False

        # STAGE 1: Version bump
        new_version = self._perform_version_bump(version_type)
        if not new_version:
            return False

        # STAGE 2: Commit, tag, and push changes
        current_commit_hash = self._commit_version_changes(new_version)
        if not current_commit_hash:
            return False

        # STAGE 3: Publish to PyPI
        if not self._publish_to_pypi(
            options, new_version, original_head, current_commit_hash
        ):
            return False

        # Finalize publishing
        self._finalize_publishing(options, new_version)

        self.session.complete_task("publishing", f"Published version {new_version}")
        return True

    def _handle_pre_publish_commit(self, options: OptionsProtocol) -> bool:
        """Handle committing existing changes before version bump if needed."""
        if not options.commit:
            return True

        existing_changes = self.git_service.get_changed_files()
        if not existing_changes:
            return True

        self._display_commit_push_header()
        self.console.print(
            "[cyan]ℹ️[/cyan] Committing existing changes before version bump..."
        )
        commit_message = self._get_commit_message(existing_changes, options)
        if not self._execute_commit_and_push(existing_changes, commit_message):
            self.session.fail_task("publishing", "Failed to commit pre-publish changes")
            return False
        self.console.print(
            "[green]✅[/green] Pre-publish changes committed and pushed\n"
        )
        return True

    def _perform_version_bump(self, version_type: str) -> str | None:
        """Perform the version bump operation."""
        self._display_version_bump_header()

        new_version = self.publish_manager.bump_version(version_type)
        if not new_version:
            self.session.fail_task("publishing", "Version bumping failed")
            return None

        self.console.print(f"[green]✅[/green] Version bumped to {new_version}")
        self.console.print(
            f"[green]✅[/green] Changelog updated for version {new_version}"
        )
        return new_version

    def _commit_version_changes(self, new_version: str) -> str | None:
        """Commit the version changes to git."""
        self._display_commit_push_header()

        # Stage changes
        changed_files = self.git_service.get_changed_files()
        if not changed_files:
            self.console.print("[yellow]⚠️[/yellow] No changes to stage")
            self.session.fail_task("publishing", "No changes to commit")
            return None

        if not self.git_service.add_files(changed_files):
            self.session.fail_task("publishing", "Failed to stage files")
            return None
        self.console.print(f"[green]✅[/green] Staged {len(changed_files)} files")

        # Commit
        commit_message = f"chore: bump version to {new_version}"
        if not self.git_service.commit(commit_message):
            self.session.fail_task("publishing", "Failed to commit changes")
            return None
        current_commit_hash = (
            self.git_service.get_current_commit_hash()
            if hasattr(self.git_service, "get_current_commit_hash")
            else None
        )
        return current_commit_hash

    def _publish_to_pypi(
        self,
        options: OptionsProtocol,
        new_version: str,
        original_head: str | None,
        current_commit_hash: str | None,
    ) -> bool:
        """Publish the package to PyPI."""
        self._display_publish_header()

        # Build and publish package
        if not self.publish_manager.publish_package():
            self.session.fail_task("publishing", "Package publishing failed")
            # Attempt to rollback the version bump commit if publishing fails
            if current_commit_hash and original_head:
                self._attempt_rollback_version_bump(original_head, current_commit_hash)
            return False
        return True

    def _finalize_publishing(self, options: OptionsProtocol, new_version: str) -> None:
        """Finalize the publishing process after successful PyPI publishing."""
        # Create git tag and push only after successful PyPI publishing
        if not options.no_git_tags:
            if not self.publish_manager.create_git_tag_local(new_version):
                self.console.print(
                    f"[yellow]⚠️[/yellow] Failed to create git tag v{new_version}"
                )

        # Push commit and tag together in single operation only after successful PyPI publishing
        if not self.git_service.push_with_tags():
            self.console.print("[yellow]⚠️[/yellow] Push failed. Please push manually")
            # Not failing the whole workflow for a push failure

    def _attempt_rollback_version_bump(
        self, original_head: str, current_commit_hash: str
    ) -> bool:
        """Attempt to undo the version bump commit if publishing fails."""
        try:
            self.console.print(
                "[yellow]🔄 Attempting to rollback version bump commit...[/yellow]"
            )

            # Reset to the original HEAD (before version bump commit)
            result = self.git_service.reset_hard(original_head)

            if result:
                self.console.print(
                    f"[green]✅ Version bump commit ({current_commit_hash[:8]}...) reverted[/green]"
                )
                return True
            else:
                self.console.print("[red]❌ Failed to revert version bump commit[/red]")
                return False
        except Exception as e:
            self.console.print(f"[red]❌ Error during version rollback: {e}[/red]")
            return False

    def _display_version_bump_header(self) -> None:
        sep = make_separator("-")
        self.console.print("\n" + sep)
        self.console.print("[bold bright_cyan]📝 VERSION BUMP[/bold bright_cyan]")
        self.console.print(sep + "\n")

    def _display_commit_push_header(self) -> None:
        sep = make_separator("-")
        self.console.print("\n" + sep)
        self.console.print("[bold bright_blue]📦 COMMIT & PUSH[/bold bright_blue]")
        self.console.print(sep + "\n")

    def _display_publish_header(self) -> None:
        sep = make_separator("-")
        self.console.print("\n" + sep)
        self.console.print("[bold bright_green]🚀 PUBLISH TO PYPI[/bold bright_green]")
        self.console.print(sep + "\n")

    def _handle_no_changes_to_commit(self) -> bool:
        self.console.print("No changes to commit")
        self.session.complete_task("commit", "No changes to commit")
        return True

    def _get_commit_message(
        self, changed_files: list[str], options: OptionsProtocol
    ) -> str:
        suggestions = self.git_service.get_commit_message_suggestions(changed_files)
        if not suggestions:
            return "Update project files"

        if not options.interactive:
            return suggestions[0]

        return self._interactive_commit_message_selection(suggestions)

    def _interactive_commit_message_selection(self, suggestions: list[str]) -> str:
        self._display_commit_suggestions(suggestions)
        choice = self.console.input(
            "\nEnter number, custom message, or press Enter for default: "
        ).strip()
        return self._process_commit_choice(choice, suggestions)

    def _display_commit_suggestions(self, suggestions: list[str]) -> None:
        self.console.print("\n[bold]Commit message suggestions:[/bold]")
        for i, suggestion in enumerate(suggestions, 1):
            self.console.print(f"  [cyan]{i}[/cyan]: {suggestion}")

    @staticmethod
    def _process_commit_choice(choice: str, suggestions: list[str]) -> str:
        if not choice:
            return suggestions[0]
        if choice.isdigit() and 1 <= int(choice) <= len(suggestions):
            return suggestions[int(choice) - 1]
        return choice

    def _execute_commit_and_push(
        self, changed_files: list[str], commit_message: str
    ) -> bool:
        if not self.git_service.add_files(changed_files):
            self.session.fail_task("commit", "Failed to add files to git")
            return False
        if not self.git_service.commit(commit_message):
            self.session.fail_task("commit", "Failed to commit files")
            return False
        if not self.git_service.push():
            self.console.print("[yellow]⚠️[/yellow] Push failed. Please push manually")
            # Not failing the whole workflow for a push failure
        self.session.complete_task("commit", "Committed and pushed changes")
        return True

    @staticmethod
    def _format_hook_summary(summary: dict[str, t.Any]) -> str:
        if not summary:
            return "No hooks executed"

        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        errors = summary.get("errors", 0)
        duration = summary.get("total_duration", 0.0)

        parts = [f"{passed}/{total} passed"]
        if failed:
            parts.append(f"{failed} failed")
        if errors:
            parts.append(f"{errors} errors")

        summary_str = ", ".join(parts)
        return f"{summary_str} in {duration:.2f}s"

    @staticmethod
    def _status_style(status: str) -> str:
        normalized = status.lower()
        if normalized == "passed":
            return "green"
        if normalized in {"failed", "error"}:
            return "red"
        if normalized == "timeout":
            return "yellow"
        return "bright_white"

    # (All printing is handled by acb.console.Console which supports robust I/O.)

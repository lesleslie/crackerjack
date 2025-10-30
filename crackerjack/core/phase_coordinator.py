from __future__ import annotations

import logging
import typing as t
from pathlib import Path

from acb.depends import Inject, depends
from rich import box
from rich.console import Console
from rich.table import Table

from crackerjack.code_cleaner import CodeCleaner
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
from crackerjack.services.monitoring.performance_cache import (
    FileSystemCache,
    GitOperationCache,
)
from crackerjack.services.parallel_executor import (
    AsyncCommandExecutor,
    ParallelHookExecutor,
)

if t.TYPE_CHECKING:
    pass  # All imports moved to top-level for runtime availability


class PhaseCoordinator:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        memory_optimizer: Inject[MemoryOptimizerProtocol],
        parallel_executor: Inject[ParallelHookExecutor],
        async_executor: Inject[AsyncCommandExecutor],
        git_cache: Inject[GitOperationCache],
        filesystem_cache: Inject[FileSystemCache],
        pkg_path: Path = depends(),
        session: SessionCoordinator = depends(),
        # Dependencies provided by WorkflowOrchestrator via depends.get()
        filesystem: FileSystemInterface = depends(),
        git_service: GitInterface = depends(),
        hook_manager: HookManager = depends(),
        test_manager: TestManagerProtocol = depends(),
        publish_manager: PublishManager = depends(),
        config_merge_service: ConfigMergeServiceProtocol = depends(),
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.session = session

        # Dependencies injected via ACB's depends.get() from WorkflowOrchestrator
        self.filesystem = filesystem
        self.git_service = git_service
        self.hook_manager = hook_manager
        self.test_manager = test_manager
        self.publish_manager = publish_manager
        self.config_merge_service = config_merge_service

        self.code_cleaner = CodeCleaner(
            console=console,
            base_directory=pkg_path,
            file_processor=None,
            error_handler=None,
            pipeline=None,
            logger=None,
            security_logger=None,
            backup_service=None,
        )

        self.logger = logging.getLogger("crackerjack.phases")

        # Services injected via ACB DI
        self._memory_optimizer = memory_optimizer
        self._parallel_executor = parallel_executor
        self._async_executor = async_executor
        self._git_cache = git_cache
        self._filesystem_cache = filesystem_cache

        self._last_hook_summary: dict[str, t.Any] | None = None

        self._lazy_autofix = create_lazy_service(
            lambda: AutofixCoordinator(pkg_path=pkg_path),
            "autofix_coordinator",
        )

    @handle_errors
    def run_cleaning_phase(self, options: OptionsProtocol) -> bool:
        if not options.clean:
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

    @handle_errors
    def run_fast_hooks_only(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            self.console.print("[yellow]⚠️[/yellow] Skipping fast hooks (--skip-hooks).")
            return True

        self.session.track_task("hooks_fast", "Fast quality checks")
        self._display_hook_phase_header(
            "FAST HOOKS",
            "Formatters, import sorting, and quick static analysis",
        )

        success = self._execute_hooks_with_retry(
            "fast", self.hook_manager.run_fast_hooks, options
        )

        summary = self._last_hook_summary or {}
        details = self._format_hook_summary(summary)

        if success:
            self.session.complete_task("hooks_fast", details=details)
        else:
            self.session.fail_task("hooks_fast", "Fast hook failures detected")

        return success

    @handle_errors
    def run_comprehensive_hooks_only(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            self.console.print(
                "[yellow]⚠️[/yellow] Skipping comprehensive hooks (--skip-hooks)."
            )
            return True

        self.session.track_task("hooks_comprehensive", "Comprehensive quality checks")
        self._display_hook_phase_header(
            "COMPREHENSIVE HOOKS",
            "Type checking, security scans, and complexity analysis",
        )

        success = self._execute_hooks_with_retry(
            "comprehensive",
            self.hook_manager.run_comprehensive_hooks,
            options,
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
        if not options.test:
            return True
        self.session.track_task("testing", "Test execution")
        self.console.print("\n" + "-" * 74)
        self.console.print(
            "[bold bright_blue]🧪 TESTS[/ bold bright_blue] [bold bright_white]Running test suite[/ bold bright_white]",
        )
        self.console.print("-" * 74 + "\n")
        if not self.test_manager.validate_test_environment():
            self.session.fail_task("testing", "Test environment validation failed")
            return False
        test_success = self.test_manager.run_tests(options)
        if test_success:
            coverage_info = self.test_manager.get_coverage()
            self.session.complete_task(
                "testing",
                f"Tests passed, coverage: {coverage_info.get('total_coverage', 0): .1f}%",
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

        # Display commit & push header
        self._display_commit_push_header()
        self.session.track_task("commit", "Git commit and push")
        changed_files = self.git_service.get_changed_files()
        if not changed_files:
            return self._handle_no_changes_to_commit()
        commit_message = self._get_commit_message(changed_files, options)
        return self._execute_commit_and_push(changed_files, commit_message)

    def _execute_hooks_with_retry(
        self,
        suite_name: str,
        hook_runner: t.Callable[[], list[HookResult]],
        options: OptionsProtocol,
    ) -> bool:
        """Execute a hook suite with lightweight retry handling."""
        attempt = 0
        max_attempts = 1  # Placeholder for future intelligent retries
        self._last_hook_summary = None

        while attempt < max_attempts:
            attempt += 1
            try:
                hook_results = hook_runner() or []
            except Exception as exc:
                self.console.print(
                    f"[red]❌[/red] {suite_name.title()} hooks encountered an unexpected error: {exc}"
                )
                self.logger.exception(
                    "Hook execution raised exception",
                    extra={"suite": suite_name, "attempt": attempt},
                )
                return False

            summary = self.hook_manager.get_hook_summary(hook_results)
            self._last_hook_summary = summary
            self._report_hook_results(suite_name, hook_results, summary, attempt)

            if summary.get("failed", 0) == 0 and summary.get("errors", 0) == 0:
                return True

            self._display_hook_failures(suite_name, hook_results)

            # Fast iteration mode intentionally avoids retries
            if getattr(options, "fast_iteration", False):
                break

            break

        self.logger.warning(
            "Hook suite reported failures",
            extra={
                "suite": suite_name,
                "attempts": attempt,
                "failed": self._last_hook_summary.get("failed", 0)
                if self._last_hook_summary
                else None,
                "errors": self._last_hook_summary.get("errors", 0)
                if self._last_hook_summary
                else None,
            },
        )
        return False

    def _display_hook_phase_header(self, title: str, description: str) -> None:
        separator = "-" * 74
        self.console.print("\n" + separator)
        self.console.print(f"[bold bright_blue]{title}[/bold bright_blue]")
        self.console.print(f"[bright_white]{description}[/bright_white]")
        self.console.print(separator + "\n")

    def _report_hook_results(
        self,
        suite_name: str,
        results: list[HookResult],
        summary: dict[str, t.Any],
        attempt: int,
    ) -> None:
        self._render_hook_results_table(suite_name, results)

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
            self.console.print(
                f"[red]❌[/red] {base_message} ({failed} failed, {errors} errors)."
            )
        else:
            self.console.print(f"[green]✅[/green] {base_message}.")

    def _render_hook_results_table(
        self,
        suite_name: str,
        results: list[HookResult],
    ) -> None:
        if not results:
            return

        table = Table(
            title=f"{suite_name.title()} Hook Results",
            box=box.SIMPLE,
            header_style="bold bright_white",
        )
        table.add_column("Hook", style="cyan", overflow="fold")
        table.add_column("Status", style="bright_white")
        table.add_column("Duration", justify="right", style="magenta")
        table.add_column("Files", justify="right", style="bright_white")

        for result in results:
            status_style = self._status_style(result.status)
            table.add_row(
                result.name,
                f"[{status_style}]{result.status.upper()}[/{status_style}]",
                f"{result.duration:.2f}s",
                str(result.files_processed),
            )

        self.console.print(table)

    def _display_hook_failures(
        self,
        suite_name: str,
        results: list[HookResult],
    ) -> None:
        failing = [
            result
            for result in results
            if result.status.lower() in {"failed", "error", "timeout"}
        ]

        if not failing:
            return

        self.console.print(
            f"[red]Details for failing {suite_name} hooks:[/red]", highlight=False
        )
        for result in failing:
            self.console.print(
                f"  - [red]{result.name}[/red] ({result.status})", highlight=False
            )
            for issue in result.issues_found or []:
                self.console.print(f"      - {issue}", highlight=False)

    def _format_hook_summary(self, summary: dict[str, t.Any]) -> str:
        if not summary:
            return "No hooks executed"

        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        errors = summary.get("errors", 0)
        duration = summary.get("total_duration", 0.0)

        return (
            f"{passed}/{total} passed"
            f"{f', {failed} failed' if failed else ''}"
            f"{f', {errors} errors' if errors else ''}"
            f" in {duration:.2f}s"
        )

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

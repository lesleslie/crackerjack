from __future__ import annotations

import re
import typing as t
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends
from acb.logger import Logger
from rich import box
from rich.panel import Panel
from rich.table import Table

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
from crackerjack.services.monitoring.performance_cache import (
    FileSystemCache,
    GitOperationCache,
)
from crackerjack.services.parallel_executor import (
    AsyncCommandExecutor,
    ParallelHookExecutor,
)
from crackerjack.utils.console_utils import separator as make_separator

if t.TYPE_CHECKING:
    pass  # All imports moved to top-level for runtime availability


class PhaseCoordinator:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        logger: Inject[Logger],
        memory_optimizer: Inject[MemoryOptimizerProtocol],
        parallel_executor: Inject[ParallelHookExecutor],
        async_executor: Inject[AsyncCommandExecutor],
        git_cache: Inject[GitOperationCache],
        filesystem_cache: Inject[FileSystemCache],
        pkg_path: Inject[Path],
        session: Inject[SessionCoordinator],
        filesystem: Inject[FileSystemInterface],
        git_service: Inject[GitInterface],
        hook_manager: Inject[HookManager],
        test_manager: Inject[TestManagerProtocol],
        publish_manager: Inject[PublishManager],
        config_merge_service: Inject[ConfigMergeServiceProtocol],
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

        self.logger = logger

        # Services injected via ACB DI
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

    def run_fast_hooks_only(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            self.console.print("[yellow]⚠️[/yellow] Skipping fast hooks (--skip-hooks).")
            return True

        self.session.track_task("hooks_fast", "Fast quality checks")

        # Fast hooks get 2 attempts (auto-fix on failure), comprehensive hooks run once
        max_attempts = 2
        attempt = 0

        while attempt < max_attempts:
            attempt += 1

            # Display stage header for each attempt
            if attempt > 1:
                self.console.print(
                    f"\n[yellow]♻️  Retry Attempt {attempt}/{max_attempts}[/yellow]\n"
                )

            self._display_hook_phase_header(
                "FAST HOOKS",
                "Formatters, import sorting, and quick static analysis",
            )

            success = self._execute_hooks_once(
                "fast", self.hook_manager.run_fast_hooks, options, attempt
            )

            if success:
                break

            # Fast iteration mode intentionally avoids retries
            if getattr(options, "fast_iteration", False):
                break

            # If we have more attempts, continue to retry
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
                "[yellow]⚠️[/yellow] Skipping comprehensive hooks (--skip-hooks)."
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
        if not options.test:
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
        """Execute a hook suite once (no retry logic - retry is handled at stage level)."""
        self._last_hook_summary = None
        self._last_hook_results = []

        try:
            hook_results = hook_runner() or []
            self._last_hook_results = hook_results
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
            self.console.print(
                f"\n[red]❌ {base_message}[/red] ({failed} failed, {errors} errors).\n"
            )
        else:
            self.console.print(f"\n[green]✅[/green] {base_message}.\n")
            self._render_hook_results_table(suite_name, results)

    def _render_hook_results_table(
        self,
        suite_name: str,
        results: list[HookResult],
    ) -> None:
        if not results:
            return

        if self._is_plain_output():
            # Plain, log-friendly rendering without Rich structures
            self.console.print(f"{suite_name.title()} Hook Results:", highlight=False)
            for result in results:
                name = self._strip_ansi(str(result.name))
                status = result.status.upper()
                duration = f"{result.duration:.2f}s"
                files = str(result.files_processed)
                self.console.print(
                    f"  - {name} :: {status} | {duration} | files={files}",
                    highlight=False,
                )
            self.console.print()
            return

        table = Table(box=box.SIMPLE, header_style="bold bright_white")
        table.add_column("Hook", style="cyan", overflow="fold")
        table.add_column("Status", style="bright_white")
        table.add_column("Duration", justify="right", style="magenta")
        table.add_column("Files", justify="right", style="bright_white")

        for result in results:
            status_style = self._status_style(result.status)
            table.add_row(
                self._strip_ansi(result.name),
                f"[{status_style}]{result.status.upper()}[/{status_style}]",
                f"{result.duration:.2f}s",
                str(result.files_processed),
            )

        panel = Panel(
            table,
            title=f"[bold]{suite_name.title()} Hook Results[/bold]",
            border_style="cyan" if suite_name == "fast" else "magenta",
            padding=(0, 1),
            width=get_console_width(),
        )
        self.console.print(panel)
        self.console.print()

    def _display_hook_failures(
        self,
        suite_name: str,
        results: list[HookResult],
        options: OptionsProtocol,
    ) -> None:
        # Show detailed failures if --verbose or --ai-debug flag is set
        if not (options.verbose or getattr(options, "ai_debug", False)):
            return

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
                f"  - [red]{self._strip_ansi(result.name)}[/red] ({result.status})",
                highlight=False,
            )
            for issue in result.issues_found or []:
                self.console.print(
                    f"      - {self._strip_ansi(issue)}", highlight=False
                )
        self.console.print()

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
        self.console.print("No Python files found to clean.")
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
            self.console.print(f"Cleaned {len(cleaned_files)} files.")
            self.session.complete_task(
                "cleaning", f"Cleaned {len(cleaned_files)} files"
            )
        else:
            self.console.print("No cleaning needed for any files.")
            self.session.complete_task("cleaning", "No cleaning needed")

    @staticmethod
    def _determine_version_type(options: OptionsProtocol) -> str | None:
        return options.publish or options.all or options.bump

    def _execute_publishing_workflow(
        self, options: OptionsProtocol, version_type: str
    ) -> bool:
        # ========================================
        # STAGE 0: PRE-PUBLISH COMMIT (if -c flag)
        # ========================================
        # If user specified --commit, commit any existing changes BEFORE version bump
        if options.commit:
            existing_changes = self.git_service.get_changed_files()
            if existing_changes:
                self._display_commit_push_header()
                self.console.print(
                    "[cyan]ℹ️[/cyan] Committing existing changes before version bump..."
                )
                commit_message = self._get_commit_message(existing_changes, options)
                if not self._execute_commit_and_push(existing_changes, commit_message):
                    self.session.fail_task(
                        "publishing", "Failed to commit pre-publish changes"
                    )
                    return False
                self.console.print(
                    "[green]✅[/green] Pre-publish changes committed and pushed\n"
                )

        # ========================================
        # STAGE 1: VERSION BUMP
        # ========================================
        self._display_version_bump_header()

        new_version = self.publish_manager.bump_version(version_type)
        if not new_version:
            self.session.fail_task("publishing", "Version bumping failed")
            return False

        self.console.print(f"[green]✅[/green] Version bumped to {new_version}")
        self.console.print(
            f"[green]✅[/green] Changelog updated for version {new_version}"
        )

        # ========================================
        # STAGE 2: COMMIT, TAG & PUSH
        # ========================================
        self._display_commit_push_header()

        # Stage changes
        changed_files = self.git_service.get_changed_files()
        if not changed_files:
            self.console.print("[yellow]⚠️[/yellow] No changes to stage")
            self.session.fail_task("publishing", "No changes to commit")
            return False

        if not self.git_service.add_files(changed_files):
            self.session.fail_task("publishing", "Failed to stage files")
            return False
        self.console.print(f"[green]✅[/green] Staged {len(changed_files)} files")

        # Commit
        commit_message = f"chore: bump version to {new_version}"
        if not self.git_service.commit(commit_message):
            self.session.fail_task("publishing", "Failed to commit changes")
            return False
        self.console.print(f"[green]✅[/green] Committed: {commit_message}")

        # Create git tag locally (before push, so both commit and tag go together)
        if not options.no_git_tags:
            if not self.publish_manager.create_git_tag_local(new_version):
                self.console.print(
                    f"[yellow]⚠️[/yellow] Failed to create git tag v{new_version}"
                )

        # Push commit and tag together in single operation
        if not self.git_service.push_with_tags():
            self.console.print("[yellow]⚠️[/yellow] Push failed. Please push manually.")
            # Not failing the whole workflow for a push failure
        else:
            self.console.print("[green]✅[/green] Pushed to remote (commit + tag)")

        # ========================================
        # STAGE 3: PUBLISH TO PYPI
        # ========================================
        self._display_publish_header()

        # Build and publish package
        if not self.publish_manager.publish_package():
            self.session.fail_task("publishing", "Package publishing failed")
            return False

        self.session.complete_task("publishing", f"Published version {new_version}")
        return True

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
        self.console.print("No changes to commit.")
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
            self.console.print("[yellow]⚠️[/yellow] Push failed. Please push manually.")
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

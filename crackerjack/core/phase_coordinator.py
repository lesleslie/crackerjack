import logging
import time
import typing as t
from pathlib import Path

from rich.console import Console

from crackerjack.code_cleaner import CodeCleaner, PackageCleaningResult
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.mixins import ErrorHandlingMixin
from crackerjack.models.protocols import (
    ConfigMergeServiceProtocol,
    FileSystemInterface,
    GitInterface,
    HookManager,
    OptionsProtocol,
    PublishManager,
    TestManagerProtocol,
)
from crackerjack.services.memory_optimizer import (
    create_lazy_service,
    get_memory_optimizer,
)
from crackerjack.services.parallel_executor import (
    get_async_executor,
    get_parallel_executor,
)
from crackerjack.services.performance_cache import get_filesystem_cache, get_git_cache

from .session_coordinator import SessionCoordinator


class PhaseCoordinator(ErrorHandlingMixin):
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        session: SessionCoordinator,
        filesystem: FileSystemInterface,
        git_service: GitInterface,
        hook_manager: HookManager,
        test_manager: TestManagerProtocol,
        publish_manager: PublishManager,
        config_merge_service: ConfigMergeServiceProtocol,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.session = session

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

        from crackerjack.services.config import ConfigurationService

        self.config_service = ConfigurationService(console=console, pkg_path=pkg_path)

        self.logger = logging.getLogger("crackerjack.phases")

        self._memory_optimizer = get_memory_optimizer()
        self._parallel_executor = get_parallel_executor()
        self._async_executor = get_async_executor()
        self._git_cache = get_git_cache()
        self._filesystem_cache = get_filesystem_cache()

        self._lazy_autofix = create_lazy_service(
            lambda: AutofixCoordinator(console=console, pkg_path=pkg_path),
            "autofix_coordinator",
        )

        super().__init__()

    def run_cleaning_phase(self, options: OptionsProtocol) -> bool:
        if not options.clean:
            return True

        self.session.track_task("cleaning", "Code cleaning")
        try:
            self._display_cleaning_header()
            return self._execute_cleaning_process()
        except Exception as e:
            self.handle_subprocess_error(e, [], "Code cleaning", critical=False)
            self.session.fail_task("cleaning", str(e))
            return False

    def _display_cleaning_header(self) -> None:
        self.console.print("\n" + "-" * 40)
        self.console.print(
            "[bold bright_magenta]🛠️ SETUP[/bold bright_magenta] [bold bright_white]Initializing project structure[/bold bright_white]",
        )
        self.console.print("-" * 40 + "\n")
        self.console.print("[yellow]🧹[/yellow] Starting code cleaning...")

    def _display_version_bump_header(self, version_type: str) -> None:
        self.console.print("\n" + "-" * 74)
        self.console.print(
            f"[bold bright_magenta]📦 BUMP VERSION[/bold bright_magenta] [bold bright_white]Updating package version ({version_type})[/bold bright_white]",
        )
        self.console.print("-" * 74 + "\n")

    def _display_publish_header(self) -> None:
        self.console.print("\n" + "-" * 74)
        self.console.print(
            "[bold bright_yellow]🚀 PUBLISH[/bold bright_yellow] [bold bright_white]Publishing to PyPI[/bold bright_white]",
        )
        self.console.print("-" * 74 + "\n")

    def _display_git_staging_header(self) -> None:
        self.console.print("\n" + "-" * 74)
        self.console.print(
            "[bold bright_cyan]🏷️ GIT OPERATIONS[/bold bright_cyan] [bold bright_white]Staging files and creating tags[/bold bright_white]",
        )
        self.console.print("-" * 74 + "\n")

    def _display_commit_push_header(self) -> None:
        self.console.print("\n" + "-" * 74)
        self.console.print(
            "[bold bright_green]📤 COMMIT & PUSH[/bold bright_green] [bold bright_white]Committing and pushing changes[/bold bright_white]",
        )
        self.console.print("-" * 74 + "\n")

    def _execute_cleaning_process(self) -> bool:
        cleaning_result = self.code_cleaner.clean_files(self.pkg_path, use_backup=True)

        if isinstance(cleaning_result, list):
            cleaned_files = [str(r.file_path) for r in cleaning_result if r.success]
            self._report_cleaning_results(cleaned_files)
            return all(r.success for r in cleaning_result) if cleaning_result else True
        else:
            self._report_package_cleaning_results(cleaning_result)
            return cleaning_result.overall_success

    def _handle_no_files_to_clean(self) -> bool:
        self.console.print("[yellow]⚠️[/ yellow] No Python files found to clean")
        self.session.complete_task("cleaning", "No files to clean")
        return True

    def _report_cleaning_results(self, cleaned_files: list[str]) -> None:
        if cleaned_files:
            self.console.print(f"[green]✅[/ green] Cleaned {len(cleaned_files)} files")
            self.session.complete_task(
                "cleaning",
                f"Cleaned {len(cleaned_files)} files",
            )
        else:
            self.console.print("[green]✅[/ green] No cleaning needed")
            self.session.complete_task("cleaning", "No cleaning needed")

    def _report_package_cleaning_results(self, result: PackageCleaningResult) -> None:
        if result.overall_success:
            self.console.print(
                f"[green]✅[/ green] Package cleaning completed successfully! "
                f"({result.successful_files}/{result.total_files} files cleaned)"
            )
            self.session.complete_task(
                "cleaning",
                f"Cleaned {result.successful_files}/{result.total_files} files with backup protection",
            )
        else:
            self.console.print(
                f"[red]❌[/ red] Package cleaning failed! "
                f"({result.failed_files}/{result.total_files} files failed)"
            )

            if result.backup_restored:
                self.console.print(
                    "[yellow]⚠️[/ yellow] Files were automatically restored from backup"
                )
                self.session.complete_task(
                    "cleaning", "Failed with automatic backup restoration"
                )
            else:
                self.session.fail_task(
                    "cleaning", f"Failed to clean {result.failed_files} files"
                )

            if result.backup_metadata:
                self.console.print(
                    f"[blue]📦[/ blue] Backup available at: {result.backup_metadata.backup_directory}"
                )

    def run_configuration_phase(self, options: OptionsProtocol) -> bool:
        if options.no_config_updates:
            return True
        self.session.track_task("configuration", "Configuration updates")
        try:
            success = self._execute_configuration_steps(options)
            self._complete_configuration_task(success)
            return success
        except Exception as e:
            self.handle_subprocess_error(e, [], "Configuration phase", critical=False)
            self.session.fail_task("configuration", str(e))
            return False

    def _execute_configuration_steps(self, options: OptionsProtocol) -> bool:
        success = True

        success &= self._update_configuration_files(options)

        return success

    def _update_configuration_files(self, options: OptionsProtocol) -> bool:
        success = True
        if not self.config_service.update_precommit_config(options):
            success = False
        if not self.config_service.update_pyproject_config(options):
            success = False
        return success

    def _complete_configuration_task(self, success: bool) -> None:
        message = (
            "Configuration updated successfully"
            if success
            else "Some configuration updates failed"
        )
        self.session.complete_task("configuration", message)

    def _is_crackerjack_project(self) -> bool:
        pyproject_path = self.pkg_path / "pyproject.toml"
        if not pyproject_path.exists():
            return False

        try:
            import tomllib

            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)

            project_name: str = data.get("project", {}).get("name", "")
            return project_name == "crackerjack"
        except Exception:
            return False

    def run_hooks_phase(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            return True

        temp_config = self.config_service.get_temp_config_path()
        if temp_config:
            self.hook_manager.set_config_path(temp_config)

        if not self.run_fast_hooks_only(options):
            return False

        return self.run_comprehensive_hooks_only(options)

    def run_fast_hooks_only(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            return True

        hook_results = self.hook_manager.run_fast_hooks()
        return all(r.status == "passed" for r in hook_results)

    def run_comprehensive_hooks_only(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            return True

        hook_results = self.hook_manager.run_comprehensive_hooks()
        return all(r.status == "passed" for r in hook_results)

    def run_testing_phase(self, options: OptionsProtocol) -> bool:
        if not options.test:
            return True
        self.session.track_task("testing", "Test execution")
        try:
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
        except Exception as e:
            self.console.print(f"Testing error: {e}")
            self.session.fail_task("testing", str(e))
            return False

    def run_publishing_phase(self, options: OptionsProtocol) -> bool:
        version_type = self._determine_version_type(options)
        if not version_type:
            return True

        self.session.track_task("publishing", f"Publishing ({version_type})")
        try:
            return self._execute_publishing_workflow(options, version_type)
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Publishing failed: {e}")
            self.session.fail_task("publishing", str(e))
            return False

    def _determine_version_type(self, options: OptionsProtocol) -> str | None:
        if options.publish:
            publish_value: str | None = (
                options.publish if isinstance(options.publish, str) else None
            )
            return publish_value
        if options.all:
            all_value: str | None = (
                options.all if isinstance(options.all, str) else None
            )
            return all_value
        if options.bump:
            self._handle_version_bump_only(options.bump)
            return None
        return None

    def _execute_publishing_workflow(
        self,
        options: OptionsProtocol,
        version_type: str,
    ) -> bool:
        # Display version bump header
        self._display_version_bump_header(version_type)
        new_version = self.publish_manager.bump_version(version_type)

        # Display git operations header for staging and tagging
        self._display_git_staging_header()
        self.console.print("[blue]📂[/ blue] Staging all changes for publishing...")
        if not self.git_service.add_all_files():
            self.console.print(
                "[yellow]⚠️[/ yellow] Failed to stage files, continuing with publish..."
            )

        if not options.no_git_tags:
            self.publish_manager.create_git_tag(new_version)

        # Display publish header
        self._display_publish_header()
        if self.publish_manager.publish_package():
            self._handle_successful_publish(options, new_version)
            return True
        self.session.fail_task("publishing", "Package publishing failed")
        return False

    def _handle_successful_publish(
        self,
        options: OptionsProtocol,
        new_version: str,
    ) -> None:
        self.console.print(f"[green]🚀[/ green] Successfully published {new_version}!")

        if options.cleanup_pypi:
            self.publish_manager.cleanup_old_releases(options.keep_releases)

        self.session.complete_task("publishing", f"Published {new_version}")

    def run_commit_phase(self, options: OptionsProtocol) -> bool:
        if not options.commit:
            return True

        # Display commit & push header
        self._display_commit_push_header()
        self.session.track_task("commit", "Git commit and push")
        try:
            changed_files = self.git_service.get_changed_files()
            if not changed_files:
                return self._handle_no_changes_to_commit()
            commit_message = self._get_commit_message(changed_files, options)
            return self._execute_commit_and_push(changed_files, commit_message)
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Commit failed: {e}")
            self.session.fail_task("commit", str(e))
            return False

    def _handle_no_changes_to_commit(self) -> bool:
        self.console.print("[yellow]ℹ️[/ yellow] No changes to commit")

        from contextlib import suppress

        with suppress(ValueError, Exception):
            commit_count = self.git_service.get_unpushed_commit_count()
            if commit_count > 0:
                self.console.print(
                    f"[blue]📤[/ blue] Found {commit_count} unpushed commit(s), attempting push..."
                )
                if self.git_service.push():
                    self.session.complete_task(
                        "commit",
                        f"No new changes, pushed {commit_count} existing commit(s)",
                    )
                    return True
                else:
                    self.console.print(
                        "[yellow]⚠️[/ yellow] Push failed for existing commits"
                    )

        self.session.complete_task("commit", "No changes to commit")
        return True

    def _execute_commit_and_push(
        self,
        changed_files: list[str],
        commit_message: str,
    ) -> bool:
        if not self.git_service.add_files(changed_files):
            self.session.fail_task("commit", "Failed to stage files")
            return False

        if not self.git_service.commit(commit_message):
            self.session.fail_task("commit", "Commit failed")
            return False

        return self._handle_push_result(commit_message)

    def _handle_push_result(self, commit_message: str) -> bool:
        if self.git_service.push():
            self.console.print(
                f"[green]🎉[/ green] Committed and pushed: {commit_message}",
            )
            self.session.complete_task(
                "commit",
                f"Committed and pushed: {commit_message}",
            )
        else:
            self.console.print(
                f"[yellow]⚠️[/ yellow] Committed but push failed: {commit_message}",
            )
            self.session.complete_task(
                "commit",
                f"Committed (push failed): {commit_message}",
            )
        return True

    def execute_hooks_with_retry(
        self,
        hook_type: str,
        hook_runner: t.Callable[[], list[t.Any]],
        options: OptionsProtocol,
    ) -> bool:
        return self._execute_hooks_with_retry(hook_type, hook_runner, options)

    def _handle_version_bump_only(self, bump_type: str) -> bool:
        self.session.track_task("version_bump", f"Version bump ({bump_type})")
        try:
            # Display version bump header
            self._display_version_bump_header(bump_type)
            new_version = self.publish_manager.bump_version(bump_type)
            self.console.print(f"[green]🎯[/ green] Version bumped to {new_version}")
            self.session.complete_task("version_bump", f"Bumped to {new_version}")
            return True
        except Exception as e:
            self.console.print(f"[red]❌[/ red] Version bump failed: {e}")
            self.session.fail_task("version_bump", str(e))
            return False

    def _get_commit_message(
        self,
        changed_files: list[str],
        options: OptionsProtocol,
    ) -> str:
        # Smart commit is now enabled by default for all commit operations
        # Use basic commit messages only if explicitly disabled
        use_smart_commit = getattr(options, "smart_commit", True)
        disable_smart_commit = getattr(options, "basic_commit", False)

        if use_smart_commit and not disable_smart_commit:
            try:
                from crackerjack.services.intelligent_commit import (
                    CommitMessageGenerator,
                )

                self.console.print(
                    "[cyan]🤖[/cyan] Generating intelligent commit message..."
                )
                commit_generator = CommitMessageGenerator(
                    console=self.console, git_service=self.git_service
                )

                intelligent_message = commit_generator.generate_commit_message(
                    include_body=False,
                    conventional_commits=True,
                )

                if not options.interactive:
                    self.console.print(
                        f"[green]✨[/green] Generated: {intelligent_message}"
                    )
                    return intelligent_message

                # In interactive mode, offer the intelligent message plus fallback suggestions
                suggestions = [intelligent_message]
                fallback_suggestions = self.git_service.get_commit_message_suggestions(
                    changed_files
                )
                suggestions.extend(
                    fallback_suggestions[:3]
                )  # Add up to 3 fallback options

                return self._interactive_commit_message_selection(suggestions)

            except Exception as e:
                self.console.print(
                    f"[yellow]⚠️[/yellow] Intelligent commit generation failed: {e}"
                )
                # Fallback to original logic

        # Original logic for non-smart commits
        suggestions = self.git_service.get_commit_message_suggestions(changed_files)

        if not suggestions:
            return "Update project files"

        if not options.interactive:
            return suggestions[0]

        return self._interactive_commit_message_selection(suggestions)

    def _interactive_commit_message_selection(self, suggestions: list[str]) -> str:
        self._display_commit_suggestions(suggestions)

        try:
            choice = self.console.input(
                f"\nSelect message (1-{len(suggestions)}) or enter custom: ",
            )
            return self._process_commit_choice(choice, suggestions)
        except (KeyboardInterrupt, EOFError):
            return suggestions[0]

    def _display_commit_suggestions(self, suggestions: list[str]) -> None:
        self.console.print("[cyan]📝[/ cyan] Commit message suggestions: ")
        for i, suggestion in enumerate(suggestions, 1):
            self.console.print(f" {i}. {suggestion}")

    def _process_commit_choice(self, choice: str, suggestions: list[str]) -> str:
        if choice.isdigit() and 1 <= int(choice) <= len(suggestions):
            return suggestions[int(choice) - 1]
        return choice or suggestions[0]

    def _execute_hooks_with_retry(
        self,
        hook_type: str,
        hook_runner: t.Callable[[], list[t.Any]],
        options: OptionsProtocol,
    ) -> bool:
        self._initialize_hook_execution(hook_type)
        max_retries = self._get_max_retries(hook_type)

        for attempt in range(max_retries):
            try:
                execution_result = self._execute_single_hook_attempt(hook_runner)
                if execution_result is None:
                    return False

                results, summary = execution_result
                should_continue = self._process_hook_results(
                    hook_type, options, summary, results, attempt, max_retries
                )

                if should_continue == "continue":
                    continue
                elif should_continue == "success":
                    return True
                else:
                    return False

            except Exception as e:
                return self._handle_hook_exception(hook_type, e)

        return False

    def _execute_single_hook_attempt(
        self, hook_runner: t.Callable[[], list[t.Any]]
    ) -> tuple[list[t.Any], dict[str, t.Any]] | None:
        try:
            results = hook_runner()
            summary = self.hook_manager.get_hook_summary(results)
            return results, summary
        except Exception:
            return None

    def _process_hook_results(
        self,
        hook_type: str,
        options: OptionsProtocol,
        summary: dict[str, t.Any],
        results: list[t.Any],
        attempt: int,
        max_retries: int,
    ) -> str:
        if not self._has_hook_failures(summary):
            self._handle_hook_success(hook_type, summary)
            return "success"

        if self._should_retry_hooks(hook_type, attempt, max_retries, results):
            return "continue"

        self._handle_hook_failures(
            hook_type, options, summary, results, attempt, max_retries
        )
        return "failure"

    def _initialize_hook_execution(self, hook_type: str) -> None:
        self.logger.info(f"Starting {hook_type} hooks execution")
        self.session.track_task(
            f"{hook_type}_hooks",
            f"{hook_type.title()} hooks execution",
        )

    def _get_max_retries(self, hook_type: str) -> int:
        return 2 if hook_type == "fast" else 1

    def _has_hook_failures(self, summary: dict[str, t.Any]) -> bool:
        return summary["failed"] > 0 or summary["errors"] > 0

    def _should_retry_hooks(
        self,
        hook_type: str,
        attempt: int,
        max_retries: int,
        results: list[t.Any],
    ) -> bool:
        if hook_type == "fast" and attempt < max_retries - 1:
            if self._should_retry_fast_hooks(results):
                self.console.print(
                    "[yellow]🔄[/ yellow] Fast hooks modified files, retrying all fast hooks...",
                )
                return True
        return False

    def _attempt_autofix_for_fast_hooks(self, results: list[t.Any]) -> bool:
        try:
            self.logger.info("Attempting autofix for fast hook failures")

            autofix_coordinator = self._lazy_autofix.get()
            fix_result: bool = autofix_coordinator.apply_fast_stage_fixes()
            return fix_result
        except Exception as e:
            self.logger.warning(f"Autofix attempt failed: {e}")
            return False

    def _handle_hook_failures(
        self,
        hook_type: str,
        options: OptionsProtocol,
        summary: dict[str, t.Any],
        results: list[t.Any],
        attempt: int,
        max_retries: int,
    ) -> bool:
        self.logger.debug(
            f"{hook_type} hooks failed: {summary['failed']} failed, {summary['errors']} errors",
        )

        self.console.print(
            f"[red]❌[/ red] {hook_type.title()} hooks failed: {summary['failed']} failed, {summary['errors']} errors",
        )

        if hook_type == "fast" and attempt < max_retries - 1:
            if self._attempt_autofix_for_fast_hooks(results):
                self.console.print(
                    "[yellow]🔧[/ yellow] Applied autofixes for fast hooks, retrying...",
                )
                return True

        if getattr(options, "verbose", False):
            self._display_verbose_hook_errors(results, hook_type)

        detailed_error_msg = self._build_detailed_hook_error_message(results, summary)

        self.session.fail_task(
            f"{hook_type}_hooks",
            detailed_error_msg,
        )
        return False

    def _display_verbose_hook_errors(
        self, results: list[t.Any], hook_type: str
    ) -> None:
        self.console.print(
            f"\n[bold yellow]📋 Detailed {hook_type} hook errors: [/bold yellow]"
        )

        for result in results:
            status = getattr(result, "status", "")
            if status not in ("failed", "error", "timeout"):
                continue

            hook_name = getattr(result, "name", "unknown")
            issues = getattr(result, "issues_found", [])

            self.console.print(f"\n[red]❌ {hook_name}[/red]")

            if issues:
                for issue in issues:
                    if isinstance(issue, str) and issue.strip():
                        cleaned_issue = issue.strip()
                        self.console.print(f" {cleaned_issue}")
            else:
                self.console.print(f" Hook failed with exit code (status: {status})")

    def _build_detailed_hook_error_message(
        self, results: list[t.Any], summary: dict[str, t.Any]
    ) -> str:
        error_parts = [f"{summary['failed']} failed, {summary['errors']} errors"]

        failed_hooks = []
        for result in results:
            if hasattr(result, "failed") and result.failed:
                hook_name = getattr(result, "hook_id", "") or getattr(
                    result, "name", "unknown"
                )
                failed_hooks.append(hook_name.lower())

        if failed_hooks:
            error_parts.append(f"Failed hooks: {', '.join(failed_hooks)}")

        return " | ".join(error_parts)

    def _should_retry_fast_hooks(self, results: list[t.Any]) -> bool:
        for result in results:
            if hasattr(result, "failed") and result.failed:
                return True

            status = getattr(result, "status", "")
            if status in ("failed", "error", "timeout"):
                return True
        return False

    def _apply_retry_backoff(self, attempt: int) -> None:
        if attempt > 0:
            backoff_delay = 2 ** (attempt - 1)
            self.logger.debug(f"Applying exponential backoff: {backoff_delay}s")
            self.console.print(f"[dim]Waiting {backoff_delay}s before retry...[/ dim]")
            time.sleep(backoff_delay)

    def _handle_hook_success(self, hook_type: str, summary: dict[str, t.Any]) -> bool:
        self.logger.info(
            f"{hook_type} hooks passed: {summary['passed']} / {summary['total']}",
        )
        self.console.print(
            f"[green]✅[/ green] {hook_type.title()} hooks passed: {summary['passed']} / {summary['total']}",
        )
        self.session.complete_task(
            f"{hook_type}_hooks",
            f"{summary['passed']} / {summary['total']} passed",
        )
        return True

    def _handle_hook_exception(self, hook_type: str, e: Exception) -> bool:
        self.console.print(f"[red]❌[/ red] {hook_type.title()} hooks error: {e}")
        self.session.fail_task(f"{hook_type}_hooks", str(e))
        return False

    async def _execute_hooks_with_parallel_support(
        self,
        hook_type: str,
        hook_runner: t.Callable[[], list[t.Any]],
        options: OptionsProtocol,
    ) -> bool:
        self._initialize_hook_execution(hook_type)

        try:
            return await self._process_parallel_hook_execution(
                hook_type, hook_runner, options
            )

        except Exception as e:
            return self._handle_hook_exception(hook_type, e)

    async def _process_parallel_hook_execution(
        self,
        hook_type: str,
        hook_runner: t.Callable[[], list[t.Any]],
        options: OptionsProtocol,
    ) -> bool:
        results = hook_runner()
        summary = self.hook_manager.get_hook_summary(results)

        if not self._has_hook_failures(summary):
            return self._handle_hook_success(hook_type, summary)

        return self._handle_parallel_hook_failures(
            hook_type, hook_runner, options, results, summary
        )

    def _handle_parallel_hook_failures(
        self,
        hook_type: str,
        hook_runner: t.Callable[[], list[t.Any]],
        options: OptionsProtocol,
        results: list[t.Any],
        summary: dict[str, t.Any],
    ) -> bool:
        if hook_type != "fast":
            return self._handle_hook_failures(
                hook_type, options, summary, results, 0, 1
            )

        if not self._attempt_autofix_for_fast_hooks(results):
            return self._handle_hook_failures(
                hook_type, options, summary, results, 0, 1
            )

        return self._retry_hooks_after_autofix(hook_type, hook_runner, options)

    def _retry_hooks_after_autofix(
        self,
        hook_type: str,
        hook_runner: t.Callable[[], list[t.Any]],
        options: OptionsProtocol,
    ) -> bool:
        self.console.print(
            "[yellow]🔧[/ yellow] Applied autofixes for fast hooks, retrying..."
        )

        results = hook_runner()
        summary = self.hook_manager.get_hook_summary(results)

        if not self._has_hook_failures(summary):
            return self._handle_hook_success(hook_type, summary)

        return self._handle_hook_failures(hook_type, options, summary, results, 0, 1)

    @property
    def autofix_coordinator(self) -> AutofixCoordinator:
        coordinator: AutofixCoordinator = self._lazy_autofix.get()
        return coordinator

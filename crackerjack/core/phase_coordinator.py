import logging
import time
import typing as t
from pathlib import Path

from rich.console import Console

from crackerjack.code_cleaner import CodeCleaner
from crackerjack.models.protocols import (
    FileSystemInterface,
    GitInterface,
    HookManager,
    OptionsProtocol,
    PublishManager,
    TestManagerProtocol,
)
from crackerjack.services.config import ConfigurationService

from .session_coordinator import SessionCoordinator


class PhaseCoordinator:
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
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.session = session

        self.filesystem = filesystem
        self.git_service = git_service
        self.hook_manager = hook_manager
        self.test_manager = test_manager
        self.publish_manager = publish_manager

        self.code_cleaner = CodeCleaner(console=console)
        self.config_service = ConfigurationService(console=console, pkg_path=pkg_path)

        self.logger = logging.getLogger("crackerjack.phases")

    def run_cleaning_phase(self, options: OptionsProtocol) -> bool:
        if not options.clean:
            return True

        self.session.track_task("cleaning", "Code cleaning")
        try:
            self._display_cleaning_header()
            return self._execute_cleaning_process()
        except Exception as e:
            self.console.print(f"[red]❌[/red] Cleaning failed: {e}")
            self.session.fail_task("cleaning", str(e))
            return False

    def _display_cleaning_header(self) -> None:
        self.console.print("\n" + " - " * 80)
        self.console.print(
            "[bold bright_magenta]🛠️ SETUP[/bold bright_magenta] [bold bright_white]Initializing project structure[/bold bright_white]",
        )
        self.console.print(" - " * 80 + "\n")
        self.console.print("[yellow]🧹[/yellow] Starting code cleaning...")

    def _execute_cleaning_process(self) -> bool:
        python_files = list(self.pkg_path.rglob("*.py"))

        if not python_files:
            return self._handle_no_files_to_clean()

        cleaned_files = self._clean_python_files(python_files)
        self._report_cleaning_results(cleaned_files)
        return True

    def _handle_no_files_to_clean(self) -> bool:
        self.console.print("[yellow]⚠️[/yellow] No Python files found to clean")
        self.session.complete_task("cleaning", "No files to clean")
        return True

    def _clean_python_files(self, python_files: list[Path]) -> list[str]:
        cleaned_files: list[str] = []
        for file_path in python_files:
            if self.code_cleaner.should_process_file(file_path):
                if self.code_cleaner.clean_file(file_path):
                    cleaned_files.append(str(file_path))
        return cleaned_files

    def _report_cleaning_results(self, cleaned_files: list[str]) -> None:
        if cleaned_files:
            self.console.print(f"[green]✅[/green] Cleaned {len(cleaned_files)} files")
            self.session.complete_task(
                "cleaning",
                f"Cleaned {len(cleaned_files)} files",
            )
        else:
            self.console.print("[green]✅[/green] No cleaning needed")
            self.session.complete_task("cleaning", "No cleaning needed")

    def run_configuration_phase(self, options: OptionsProtocol) -> bool:
        if options.no_config_updates:
            return True
        self.session.track_task("configuration", "Configuration updates")
        try:
            success = True

            # Check if we're running from the crackerjack project root
            if self._is_crackerjack_project():
                if not self._copy_config_files_to_package():
                    success = False

            if not self.config_service.update_precommit_config(options):
                success = False
            if not self.config_service.update_pyproject_config(options):
                success = False
            self.session.complete_task(
                "configuration",
                "Configuration updated successfully"
                if success
                else "Some configuration updates failed",
            )
            return success
        except Exception as e:
            self.session.fail_task("configuration", str(e))
            return False

    def _is_crackerjack_project(self) -> bool:
        """Check if we're running from the crackerjack project root."""
        # Check for crackerjack-specific markers
        pyproject_path = self.pkg_path / "pyproject.toml"
        if not pyproject_path.exists():
            return False

        try:
            import tomllib

            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)

            # Check if this is the crackerjack project
            project_name = data.get("project", {}).get("name", "")
            return project_name == "crackerjack"
        except Exception:
            return False

    def _copy_config_files_to_package(self) -> bool:
        """Copy configuration files from project root to package root."""
        try:
            # Files to copy from project root to package root
            files_to_copy = [
                "pyproject.toml",
                ".pre-commit-config.yaml",
                "CLAUDE.md",
                "RULES.md",
                ".gitignore",
                "example.mcp.json",
                "uv.lock",
            ]

            package_dir = self.pkg_path / "crackerjack"
            if not package_dir.exists():
                self.console.print(
                    "[yellow]⚠️[/yellow] Package directory not found: crackerjack/",
                )
                return False

            copied_count = 0
            for filename in files_to_copy:
                src_path = self.pkg_path / filename
                if src_path.exists():
                    dst_path = package_dir / filename
                    try:
                        import shutil

                        shutil.copy2(src_path, dst_path)
                        copied_count += 1
                        self.logger.debug(f"Copied {filename} to package directory")
                    except Exception as e:
                        self.console.print(
                            f"[yellow]⚠️[/yellow] Failed to copy {filename}: {e}",
                        )

            if copied_count > 0:
                self.console.print(
                    f"[green]✅[/green] Copied {copied_count} config files to package directory",
                )

            return True
        except Exception as e:
            self.console.print(
                f"[red]❌[/red] Failed to copy config files to package: {e}",
            )
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

        return self._execute_hooks_with_retry(
            "fast",
            self.hook_manager.run_fast_hooks,
            options,
        )

    def run_comprehensive_hooks_only(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            return True

        return self._execute_hooks_with_retry(
            "comprehensive",
            self.hook_manager.run_comprehensive_hooks,
            options,
        )

    def run_testing_phase(self, options: OptionsProtocol) -> bool:
        if not options.test:
            return True
        self.session.track_task("testing", "Test execution")
        try:
            self.console.print("\n" + "-" * 80)
            self.console.print(
                "[bold bright_blue]🧪 TESTS[/bold bright_blue] [bold bright_white]Running test suite[/bold bright_white]",
            )
            self.console.print("-" * 80 + "\n")
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
            self.console.print(f"[red]❌[/red] Publishing failed: {e}")
            self.session.fail_task("publishing", str(e))
            return False

    def _determine_version_type(self, options: OptionsProtocol) -> str | None:
        if options.publish:
            return options.publish
        if options.all:
            return options.all
        if options.bump:
            self._handle_version_bump_only(options.bump)
            return None
        return None

    def _execute_publishing_workflow(
        self,
        options: OptionsProtocol,
        version_type: str,
    ) -> bool:
        new_version = self.publish_manager.bump_version(version_type)

        if not options.no_git_tags:
            self.publish_manager.create_git_tag(new_version)

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
        self.console.print(f"[green]🚀[/green] Successfully published {new_version}!")

        if options.cleanup_pypi:
            self.publish_manager.cleanup_old_releases(options.keep_releases)

        self.session.complete_task("publishing", f"Published {new_version}")

    def run_commit_phase(self, options: OptionsProtocol) -> bool:
        if not options.commit:
            return True
        self.session.track_task("commit", "Git commit and push")
        try:
            changed_files = self.git_service.get_changed_files()
            if not changed_files:
                return self._handle_no_changes_to_commit()
            commit_message = self._get_commit_message(changed_files, options)
            return self._execute_commit_and_push(changed_files, commit_message)
        except Exception as e:
            self.console.print(f"[red]❌[/red] Commit failed: {e}")
            self.session.fail_task("commit", str(e))
            return False

    def _handle_no_changes_to_commit(self) -> bool:
        self.console.print("[yellow]ℹ️[/yellow] No changes to commit")
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
                f"[green]🎉[/green] Committed and pushed: {commit_message}",
            )
            self.session.complete_task(
                "commit",
                f"Committed and pushed: {commit_message}",
            )
        else:
            self.console.print(
                f"[yellow]⚠️[/yellow] Committed but push failed: {commit_message}",
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
            new_version = self.publish_manager.bump_version(bump_type)
            self.console.print(f"[green]🎯[/green] Version bumped to {new_version}")
            self.session.complete_task("version_bump", f"Bumped to {new_version}")
            return True
        except Exception as e:
            self.console.print(f"[red]❌[/red] Version bump failed: {e}")
            self.session.fail_task("version_bump", str(e))
            return False

    def _get_commit_message(
        self,
        changed_files: list[str],
        options: OptionsProtocol,
    ) -> str:
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
                f"\nSelect message (1 - {len(suggestions)}) or enter custom: ",
            )
            return self._process_commit_choice(choice, suggestions)
        except (KeyboardInterrupt, EOFError):
            return suggestions[0]

    def _display_commit_suggestions(self, suggestions: list[str]) -> None:
        self.console.print("[cyan]📝[/cyan] Commit message suggestions: ")
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
                results = hook_runner()
                summary = self.hook_manager.get_hook_summary(results)

                if self._has_hook_failures(summary):
                    if self._should_retry_hooks(
                        hook_type,
                        attempt,
                        max_retries,
                        results,
                    ):
                        continue

                    return self._handle_hook_failures(
                        hook_type,
                        options,
                        summary,
                        results,
                        attempt,
                        max_retries,
                    )
                return self._handle_hook_success(hook_type, summary)

            except Exception as e:
                return self._handle_hook_exception(hook_type, e)

        return False

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
                    "[yellow]🔄[/yellow] Fast hooks modified files, retrying all fast hooks...",
                )
                return True
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
        self.logger.warning(
            f"{hook_type} hooks failed: {summary['failed']} failed, {summary['errors']} errors",
        )

        self.console.print(
            f"[red]❌[/red] {hook_type.title()} hooks failed: {summary['failed']} failed, {summary['errors']} errors",
        )

        # Collect detailed hook failure information for AI agent processing
        detailed_error_msg = self._build_detailed_hook_error_message(results, summary)

        self.session.fail_task(
            f"{hook_type}_hooks",
            detailed_error_msg,
        )
        return False

    def _build_detailed_hook_error_message(
        self, results: list[t.Any], summary: dict[str, t.Any]
    ) -> str:
        """Build detailed error message with specific hook failure information."""
        error_parts = [f"{summary['failed']} failed, {summary['errors']} errors"]

        # Extract specific hook failures
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
        formatting_hooks = {
            "ruff-format",
            "ruff-check",
            "trailing-whitespace",
            "end-of-file-fixer",
        }

        for result in results:
            hook_id = getattr(result, "hook_id", "") or getattr(result, "name", "")
            if (
                hook_id in formatting_hooks
                and hasattr(result, "failed")
                and result.failed
            ):
                output = getattr(result, "output", "") or getattr(result, "stdout", "")
                if any(
                    phrase in output.lower()
                    for phrase in (
                        "files were modified",
                        "fixed",
                        "reformatted",
                        "fixing",
                    )
                ):
                    return True
        return False

    def _apply_retry_backoff(self, attempt: int) -> None:
        if attempt > 0:
            backoff_delay = 2 ** (attempt - 1)
            self.logger.debug(f"Applying exponential backoff: {backoff_delay}s")
            self.console.print(f"[dim]Waiting {backoff_delay}s before retry...[/dim]")
            time.sleep(backoff_delay)

    def _handle_hook_success(self, hook_type: str, summary: dict[str, t.Any]) -> bool:
        self.logger.info(
            f"{hook_type} hooks passed: {summary['passed']} / {summary['total']}",
        )
        self.console.print(
            f"[green]✅[/green] {hook_type.title()} hooks passed: {summary['passed']} / {summary['total']}",
        )
        self.session.complete_task(
            f"{hook_type}_hooks",
            f"{summary['passed']} / {summary['total']} passed",
        )
        return True

    def _handle_hook_exception(self, hook_type: str, e: Exception) -> bool:
        self.console.print(f"[red]❌[/red] {hook_type.title()} hooks error: {e}")
        self.session.fail_task(f"{hook_type}_hooks", str(e))
        return False

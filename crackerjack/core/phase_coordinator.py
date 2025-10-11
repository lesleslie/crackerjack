import logging
import time
import typing as t
from pathlib import Path

from rich.console import Console

from acb.depends import depends
from crackerjack.code_cleaner import CodeCleaner, PackageCleaningResult
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from acb.decorators import handle_errors

class PhaseCoordinator:
    @depends.inject
    def __init__(
        self,
        console: Console = depends(),
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

        from crackerjack.services.config import ConfigurationService

        self.config_service = ConfigurationService(console=console, pkg_path=pkg_path)

        self.logger = logging.getLogger("crackerjack.phases")

        self._memory_optimizer: MemoryOptimizerProtocol = get_memory_optimizer()
        self._parallel_executor: ParallelHookExecutor = get_parallel_executor()
        self._async_executor: AsyncCommandExecutor = get_async_executor()
        self._git_cache: PerformanceCacheProtocol = get_git_cache()
        self._filesystem_cache: PerformanceCacheProtocol = get_filesystem_cache()

        self._lazy_autofix = create_lazy_service(
            lambda: AutofixCoordinator(console=console, pkg_path=pkg_path),
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
        success = self._execute_configuration_steps(options)
        self._complete_configuration_task(success)
        return success

    @handle_errors
    def run_hooks_phase(self, options: OptionsProtocol) -> bool:
        if options.skip_hooks:
            return True

        temp_config = self.config_service.get_temp_config_path()
        if temp_config:
            self.hook_manager.set_config_path(temp_config)

        if not self.run_fast_hooks_only(options):
            return False

        return self.run_comprehensive_hooks_only(options)

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

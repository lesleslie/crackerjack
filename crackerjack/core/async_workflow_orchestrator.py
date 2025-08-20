import asyncio
import logging
import time
import typing as t
from pathlib import Path

from rich.console import Console

from ..models.protocols import OptionsProtocol
from .phase_coordinator import PhaseCoordinator
from .session_coordinator import SessionCoordinator


class AsyncWorkflowPipeline:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        session: SessionCoordinator,
        phases: PhaseCoordinator,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.session = session
        self.phases = phases
        self.logger = logging.getLogger("crackerjack.async_pipeline")

    async def run_complete_workflow_async(self, options: OptionsProtocol) -> bool:
        start_time = time.time()
        self.session.initialize_session_tracking(options)
        self.session.track_task("workflow", "Complete async crackerjack workflow")

        try:
            success = await self._execute_workflow_phases_async(options)
            self.session.finalize_session(start_time, success)
            return success
        except KeyboardInterrupt:
            self.console.print("Interrupted by user")
            self.session.fail_task("workflow", "Interrupted by user")
            return False
        except Exception as e:
            self.console.print(f"Error: {e}")
            self.session.fail_task("workflow", f"Unexpected error: {e}")
            return False
        finally:
            self.session.cleanup_resources()

    async def _execute_workflow_phases_async(self, options: OptionsProtocol) -> bool:
        success = True

        self.phases.run_configuration_phase(options)

        if not await self._execute_cleaning_phase_async(options):
            success = False

            self.session.fail_task("workflow", "Cleaning phase failed")
            return False

        if not await self._execute_quality_phase_async(options):
            success = False

            return False

        if not self.phases.run_publishing_phase(options):
            success = False
            self.session.fail_task("workflow", "Publishing failed")
            return False

        if not self.phases.run_commit_phase(options):
            success = False

        return success

    async def _execute_cleaning_phase_async(self, options: OptionsProtocol) -> bool:
        if not options.clean:
            return True

        return await asyncio.to_thread(self.phases.run_cleaning_phase, options)

    async def _execute_quality_phase_async(self, options: OptionsProtocol) -> bool:
        if hasattr(options, "fast") and options.fast:
            return await self._run_fast_hooks_async(options)
        elif hasattr(options, "comp") and options.comp:
            return await self._run_comprehensive_hooks_async(options)
        elif options.test:
            return await self._execute_test_workflow_async(options)
        return await self._execute_standard_hooks_workflow_async(options)

    async def _execute_test_workflow_async(self, options: OptionsProtocol) -> bool:
        overall_success = True

        if not await self._run_fast_hooks_async(options):
            overall_success = False

            self.session.fail_task("workflow", "Fast hooks failed")
            return False

        test_task = asyncio.create_task(self._run_testing_phase_async(options))
        hooks_task = asyncio.create_task(self._run_comprehensive_hooks_async(options))

        test_success, hooks_success = await asyncio.gather(
            test_task, hooks_task, return_exceptions=True
        )

        if isinstance(test_success, Exception):
            self.logger.error(f"Test execution error: {test_success}")
            test_success = False

        if isinstance(hooks_success, Exception):
            self.logger.error(f"Hooks execution error: {hooks_success}")
            hooks_success = False

        if not test_success:
            overall_success = False

            self.session.fail_task("workflow", "Testing failed")
            return False

        if not hooks_success:
            overall_success = False

            self.session.fail_task("workflow", "Comprehensive hooks failed")
            return False

        return overall_success

    async def _execute_standard_hooks_workflow_async(
        self, options: OptionsProtocol
    ) -> bool:
        hooks_success = await self._run_hooks_phase_async(options)
        if not hooks_success:
            self.session.fail_task("workflow", "Hooks failed")
            return False
        return True

    async def _run_fast_hooks_async(self, options: OptionsProtocol) -> bool:
        return await asyncio.to_thread(self.phases.run_fast_hooks_only, options)

    async def _run_comprehensive_hooks_async(self, options: OptionsProtocol) -> bool:
        return await asyncio.to_thread(
            self.phases.run_comprehensive_hooks_only, options
        )

    async def _run_hooks_phase_async(self, options: OptionsProtocol) -> bool:
        return await asyncio.to_thread(self.phases.run_hooks_phase, options)

    async def _run_testing_phase_async(self, options: OptionsProtocol) -> bool:
        return await asyncio.to_thread(self.phases.run_testing_phase, options)


class AsyncWorkflowOrchestrator:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        dry_run: bool = False,
        web_job_id: str | None = None,
    ) -> None:
        self.console = console or Console(force_terminal=True)
        self.pkg_path = pkg_path or Path.cwd()
        self.dry_run = dry_run
        self.web_job_id = web_job_id

        from ..models.protocols import (
            FileSystemInterface,
            GitInterface,
            HookManager,
            PublishManager,
            TestManager,
        )
        from .container import create_container

        self.container = create_container(
            console=self.console, pkg_path=self.pkg_path, dry_run=self.dry_run
        )

        self.session = SessionCoordinator(self.console, self.pkg_path, self.web_job_id)
        self.phases = PhaseCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            filesystem=self.container.get(FileSystemInterface),
            git_service=self.container.get(GitInterface),
            hook_manager=self.container.get(HookManager),
            test_manager=self.container.get(TestManager),
            publish_manager=self.container.get(PublishManager),
        )

        self.async_pipeline = AsyncWorkflowPipeline(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            phases=self.phases,
        )

        self.logger = logging.getLogger("crackerjack.async_orchestrator")

    async def run_complete_workflow_async(self, options: OptionsProtocol) -> bool:
        return await self.async_pipeline.run_complete_workflow_async(options)

    def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        return asyncio.run(self.run_complete_workflow_async(options))

    def run_cleaning_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_cleaning_phase(options)

    def run_fast_hooks_only(self, options: OptionsProtocol) -> bool:
        return self.phases.run_fast_hooks_only(options)

    def run_comprehensive_hooks_only(self, options: OptionsProtocol) -> bool:
        return self.phases.run_comprehensive_hooks_only(options)

    def run_hooks_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_hooks_phase(options)

    def run_testing_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_testing_phase(options)

    def run_publishing_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_publishing_phase(options)

    def run_commit_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_commit_phase(options)

    def run_configuration_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_configuration_phase(options)

    def _cleanup_resources(self) -> None:
        self.session.cleanup_resources()

    def _register_cleanup(self, cleanup_handler: t.Callable[[], None]) -> None:
        self.session.register_cleanup(cleanup_handler)

    def _track_lock_file(self, lock_file_path: Path) -> None:
        self.session.track_lock_file(lock_file_path)

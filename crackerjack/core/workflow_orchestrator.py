import time
import typing as t
from pathlib import Path

from rich.console import Console

from ..models.protocols import OptionsProtocol
from ..services.debug import get_ai_agent_debugger
from ..services.logging import LoggingContext, get_logger, setup_structured_logging
from .phase_coordinator import PhaseCoordinator
from .session_coordinator import SessionCoordinator


def version() -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version("crackerjack")
    except Exception:
        return "unknown"


class WorkflowPipeline:
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
        self._mcp_state_manager: t.Any = None

        self.logger = get_logger("crackerjack.pipeline")
        self._debugger = None

    @property
    def debugger(self):
        if self._debugger is None:
            self._debugger = get_ai_agent_debugger()
        return self._debugger

    def _should_debug(self) -> bool:
        import os

        return os.environ.get("AI_AGENT_DEBUG", "0") == "1"

    def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        with LoggingContext(
            "workflow_execution",
            testing=getattr(options, "testing", False),
            skip_hooks=getattr(options, "skip_hooks", False),
        ):
            start_time = time.time()
            self.session.initialize_session_tracking(options)
            self.session.track_task("workflow", "Complete crackerjack workflow")

            if self._should_debug():
                self.debugger.log_workflow_phase(
                    "workflow_execution",
                    "started",
                    details={
                        "testing": getattr(options, "testing", False),
                        "skip_hooks": getattr(options, "skip_hooks", False),
                        "ai_agent": getattr(options, "ai_agent", False),
                    },
                )

            if hasattr(options, "cleanup"):
                self.session.set_cleanup_config(options.cleanup)

            self.logger.info(
                "Starting complete workflow execution",
                testing=getattr(options, "testing", False),
                skip_hooks=getattr(options, "skip_hooks", False),
                package_path=str(self.pkg_path),
            )

            try:
                success = self._execute_workflow_phases(options)
                self.session.finalize_session(start_time, success)

                duration = time.time() - start_time
                self.logger.info(
                    "Workflow execution completed",
                    success=success,
                    duration_seconds=round(duration, 2),
                )

                if self._should_debug():
                    self.debugger.log_workflow_phase(
                        "workflow_execution",
                        "completed" if success else "failed",
                        duration=duration,
                    )
                    if self.debugger.enabled:
                        self.debugger.print_debug_summary()

                return success

            except KeyboardInterrupt:
                self.console.print("Interrupted by user")
                self.session.fail_task("workflow", "Interrupted by user")
                self.logger.warning("Workflow interrupted by user")
                return False

            except Exception as e:
                self.console.print(f"Error: {e}")
                self.session.fail_task("workflow", f"Unexpected error: {e}")
                self.logger.error(
                    "Workflow execution failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return False

            finally:
                self.session.cleanup_resources()

    def _execute_workflow_phases(self, options: OptionsProtocol) -> bool:
        success = True
        self.phases.run_configuration_phase(options)
        if not self.phases.run_cleaning_phase(options):
            success = False
            self.session.fail_task("workflow", "Cleaning phase failed")
            return False
        if not self._execute_quality_phase(options):
            success = False
            return False
        if not self.phases.run_publishing_phase(options):
            success = False
            self.session.fail_task("workflow", "Publishing failed")
            return False
        if not self.phases.run_commit_phase(options):
            success = False

        return success

    def _execute_quality_phase(self, options: OptionsProtocol) -> bool:
        if options.test:
            return self._execute_test_workflow(options)
        return self._execute_standard_hooks_workflow(options)

    def _execute_test_workflow(self, options: OptionsProtocol) -> bool:
        if not self._run_fast_hooks_phase(options):
            return False

        if not self._run_testing_phase(options):
            return False

        if not self._run_comprehensive_hooks_phase(options):
            return False

        return True

    def _run_fast_hooks_phase(self, options: OptionsProtocol) -> bool:
        self._update_mcp_status("fast", "running")

        if not self.phases.run_fast_hooks_only(options):
            self.session.fail_task("workflow", "Fast hooks failed")
            self._update_mcp_status("fast", "failed")
            return False

        self._update_mcp_status("fast", "completed")
        return True

    def _run_testing_phase(self, options: OptionsProtocol) -> bool:
        self._update_mcp_status("tests", "running")

        if not self.phases.run_testing_phase(options):
            self.session.fail_task("workflow", "Testing failed")
            self._handle_test_failures()
            self._update_mcp_status("tests", "failed")
            return False

        self._update_mcp_status("tests", "completed")
        return True

    def _run_comprehensive_hooks_phase(self, options: OptionsProtocol) -> bool:
        self._update_mcp_status("comprehensive", "running")

        if not self.phases.run_comprehensive_hooks_only(options):
            self.session.fail_task("workflow", "Comprehensive hooks failed")
            self._update_mcp_status("comprehensive", "failed")
            return False

        self._update_mcp_status("comprehensive", "completed")
        return True

    def _update_mcp_status(self, stage: str, status: str) -> None:
        if hasattr(self, "_mcp_state_manager") and self._mcp_state_manager:
            self._mcp_state_manager.update_stage_status(stage, status)

        self.session.update_stage(stage, status)

    def _handle_test_failures(self) -> None:
        if not (hasattr(self, "_mcp_state_manager") and self._mcp_state_manager):
            return

        test_manager = self.phases.test_manager
        if not hasattr(test_manager, "get_test_failures"):
            return

        failures = test_manager.get_test_failures()
        from ..mcp.state import Issue, Priority

        for i, failure in enumerate(failures[:10]):
            issue = Issue(
                id=f"test_failure_{i}",
                type="test_failure",
                message=failure.strip(),
                file_path="tests/",
                priority=Priority.HIGH,
                stage="tests",
                auto_fixable=False,
            )
            self._mcp_state_manager.add_issue(issue)

    def _execute_standard_hooks_workflow(self, options: OptionsProtocol) -> bool:
        if hasattr(self, "_mcp_state_manager") and self._mcp_state_manager:
            self._mcp_state_manager.update_stage_status("fast", "running")
            self._mcp_state_manager.update_stage_status("comprehensive", "running")

        hooks_success = self.phases.run_hooks_phase(options)
        if not hooks_success:
            self.session.fail_task("workflow", "Hooks failed")
            if hasattr(self, "_mcp_state_manager") and self._mcp_state_manager:
                self._mcp_state_manager.update_stage_status("fast", "failed")
                self._mcp_state_manager.update_stage_status("comprehensive", "failed")
            return False
        else:
            if hasattr(self, "_mcp_state_manager") and self._mcp_state_manager:
                self._mcp_state_manager.update_stage_status("fast", "completed")
                self._mcp_state_manager.update_stage_status(
                    "comprehensive", "completed"
                )
        return True


class WorkflowOrchestrator:
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

        self.pipeline = WorkflowPipeline(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            phases=self.phases,
        )

        self.logger = get_logger("crackerjack.orchestrator")

        self._initialize_logging()

    def _initialize_logging(self) -> None:
        from crackerjack.services.log_manager import get_log_manager

        log_manager = get_log_manager()
        session_id = getattr(self, "web_job_id", None) or str(int(time.time()))[:8]
        debug_log_file = log_manager.create_debug_log_file(session_id)

        setup_structured_logging(log_file=debug_log_file)

        self.logger.info(
            "Structured logging initialized",
            log_file=str(debug_log_file),
            log_directory=str(log_manager.log_dir),
            package_path=str(self.pkg_path),
            dry_run=self.dry_run,
        )

    def _initialize_session_tracking(self, options: OptionsProtocol) -> None:
        self.session.initialize_session_tracking(options)

    def _track_task(self, task_id: str, task_name: str) -> None:
        self.session.track_task(task_id, task_name)

    def _complete_task(self, task_id: str, details: str | None = None) -> None:
        self.session.complete_task(task_id, details)

    def _fail_task(self, task_id: str, error: str) -> None:
        self.session.fail_task(task_id, error)

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

    def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        return self.pipeline.run_complete_workflow(options)

    def _cleanup_resources(self) -> None:
        self.session.cleanup_resources()

    def _register_cleanup(self, cleanup_handler: t.Callable[[], None]) -> None:
        self.session.register_cleanup(cleanup_handler)

    def _track_lock_file(self, lock_file_path: Path) -> None:
        self.session.track_lock_file(lock_file_path)

    def _get_version(self) -> str:
        try:
            return version()
        except Exception:
            return "unknown"

    def process(self, options: OptionsProtocol) -> bool:
        self.session.start_session("process_workflow")

        try:
            result = self.run_complete_workflow(options)
            self.session.end_session(success=result)
            return result
        except Exception:
            self.session.end_session(success=False)
            return False

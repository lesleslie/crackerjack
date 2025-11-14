"""Security and quality gates for workflow publishing.

Ensures security standards are met before allowing publishing operations.
Extracted from WorkflowPipeline to improve modularity and maintainability.

This module handles:
- Security gate validation for publishing workflows
- Critical security failure detection (bandit, pyright, gitleaks)
- AI-assisted security issue resolution
- Hook result extraction and validation
- Security audit warnings and recommendations
"""

from __future__ import annotations

import typing as t

from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.models.protocols import LoggerProtocol

if t.TYPE_CHECKING:
    from crackerjack.core.session_coordinator import SessionCoordinator
    from crackerjack.core.workflow_orchestrator import WorkflowPipeline
    from crackerjack.models.protocols import OptionsProtocol


class WorkflowSecurityGates:
    """Manages security and quality gates for workflow operations.

    This class encapsulates all security-related validation logic for workflow
    publishing, including:
    - Pre-publishing security checks
    - Critical security failure detection
    - AI-assisted security remediation
    - Security audit reporting

    The class uses protocol-based dependency injection following ACB patterns
    and maintains a reference to the workflow orchestrator for AI fixing callbacks.
    """

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        logger: Inject[LoggerProtocol],
        pipeline: WorkflowPipeline | None = None,
    ) -> None:
        """Initialize security gates with injected dependencies.

        Args:
            console: Console for user output
            logger: Logger for diagnostic messages
            pipeline: Workflow orchestrator for AI fixing callbacks (set after init)
        """
        self.console = console
        self.logger = logger
        self._pipeline = pipeline
        self._last_security_audit: t.Any = None

    @property
    def session(self) -> SessionCoordinator:
        """Get session coordinator from pipeline."""
        if self._pipeline is None:
            raise RuntimeError("Pipeline not set - call set_pipeline() first")
        return self._pipeline.session

    def set_pipeline(self, pipeline: WorkflowPipeline) -> None:
        """Set the workflow pipeline reference.

        This is called after initialization to avoid circular dependencies.

        Args:
            pipeline: The workflow orchestrator instance
        """
        self._pipeline = pipeline

    def _show_partial_success_warning_if_needed(
        self,
        publishing_requested: bool,
        final_success: bool,
        testing_passed: bool,
        comprehensive_passed: bool,
    ) -> None:
        """Show security audit warning if publishing with partial success.

        Args:
            publishing_requested: Whether publishing was requested
            final_success: Whether the workflow succeeded overall
            testing_passed: Whether tests passed
            comprehensive_passed: Whether comprehensive hooks passed
        """
        should_show_warning = (
            publishing_requested
            and final_success
            and not (testing_passed and comprehensive_passed)
        )

        if should_show_warning:
            self._show_security_audit_warning()

    def _check_security_gates_for_publishing(
        self, options: OptionsProtocol
    ) -> tuple[bool, bool]:
        """Check if security gates allow publishing.

        Args:
            options: Workflow configuration options

        Returns:
            Tuple of (publishing_requested, security_blocks_publishing)
        """
        publishing_requested = bool(options.publish or options.all)

        if not publishing_requested:
            return False, False

        try:
            security_blocks_publishing = self._check_security_critical_failures()
            return publishing_requested, security_blocks_publishing
        except Exception as e:
            self.logger.warning(f"Security check failed: {e} - blocking publishing")
            self.console.print(
                "[red]🔒 SECURITY CHECK FAILED: Unable to verify security status - publishing BLOCKED[/red]"
            )

            return publishing_requested, True

    async def _handle_security_gate_failure(
        self, options: OptionsProtocol, allow_ai_fixing: bool = False
    ) -> bool:
        """Handle security gate failure with optional AI assistance.

        Args:
            options: Workflow configuration options
            allow_ai_fixing: Whether to attempt AI-assisted fixing

        Returns:
            True if security issues were resolved, False otherwise
        """
        self._display_security_gate_failure_message()

        if allow_ai_fixing:
            return await self._attempt_ai_assisted_security_fix(options)
        return self._handle_manual_security_fix()

    def _display_security_gate_failure_message(self) -> None:
        """Display initial security gate failure message."""
        self.console.print(
            "[red]🔒 SECURITY GATE: Critical security checks failed[/red]"
        )

    async def _attempt_ai_assisted_security_fix(self, options: OptionsProtocol) -> bool:
        """Attempt to fix security issues using AI assistance.

        Args:
            options: Configuration options

        Returns:
            True if security issues were resolved, False otherwise
        """
        if self._pipeline is None:
            raise RuntimeError("Pipeline not set - cannot perform AI fixing")

        self._display_ai_fixing_messages()

        ai_fix_success = await self._pipeline._run_ai_agent_fixing_phase(options)
        if ai_fix_success:
            return self._verify_security_fix_success()

        return False

    def _display_ai_fixing_messages(self) -> None:
        """Display messages about AI-assisted security fixing."""
        self.console.print(
            "[red]Security-critical hooks (bandit, pyright, gitleaks) must pass before publishing[/red]"
        )
        self.console.print(
            "[yellow]🤖 Attempting AI-assisted security issue resolution...[/yellow]"
        )

    def _verify_security_fix_success(self) -> bool:
        """Verify that AI fixes resolved the security issues.

        Returns:
            True if security issues were resolved, False otherwise
        """
        try:
            security_still_blocks = self._check_security_critical_failures()
            if not security_still_blocks:
                self.console.print(
                    "[green]✅ AI agents resolved security issues - publishing allowed[/green]"
                )
                return True
            else:
                self.console.print(
                    "[red]🔒 Security issues persist after AI fixing - publishing still BLOCKED[/red]"
                )
                return False
        except Exception as e:
            self.logger.warning(f"Security re-check failed: {e} - blocking publishing")
            return False

    def _handle_manual_security_fix(self) -> bool:
        """Handle security fix when AI assistance is not allowed.

        Returns:
            Always False since manual intervention is required
        """
        self.console.print(
            "[red]Security-critical hooks (bandit, pyright, gitleaks) must pass before publishing[/red]"
        )
        return False

    def _check_security_critical_failures(self) -> bool:
        """Check for critical security failures in hook results.

        Returns:
            True if critical security failures exist, False otherwise

        Raises:
            Exception: If security audit fails (fail securely)
        """
        try:
            from crackerjack.security.audit import SecurityAuditor

            auditor = SecurityAuditor()

            fast_results = self._get_recent_fast_hook_results()
            comprehensive_results = self._get_recent_comprehensive_hook_results()

            audit_report = auditor.audit_hook_results(
                fast_results, comprehensive_results
            )

            self._last_security_audit = audit_report

            return audit_report.has_critical_failures

        except Exception as e:
            self.logger.warning(f"Security audit failed: {e} - failing securely")

            raise

    def _get_recent_fast_hook_results(self) -> list[t.Any]:
        """Get recent fast hook results from session.

        Returns:
            List of fast hook results, or mock results if unavailable
        """
        results = self._extract_hook_results_from_session("fast_hooks")

        if not results:
            results = self._create_mock_hook_results(["gitleaks"])

        return results

    def _extract_hook_results_from_session(self, hook_type: str) -> list[t.Any]:
        """Extract hook results from session tracker.

        Args:
            hook_type: Type of hooks to extract (e.g., "fast_hooks", "comprehensive_hooks")

        Returns:
            List of hook results
        """
        results: list[t.Any] = []

        session_tracker = self._get_session_tracker()
        if not session_tracker:
            return results

        for task_id, task_data in session_tracker.tasks.items():
            if task_id == hook_type and hasattr(task_data, "hook_results"):
                if task_data.hook_results:
                    results.extend(task_data.hook_results)

        return results

    def _get_session_tracker(self) -> t.Any | None:
        """Get session tracker from session coordinator.

        Returns:
            Session tracker if available, None otherwise
        """
        return (
            getattr(self.session, "session_tracker", None)
            if hasattr(self.session, "session_tracker")
            else None
        )

    def _create_mock_hook_results(self, critical_hooks: list[str]) -> list[t.Any]:
        """Create mock hook results for critical hooks.

        Args:
            critical_hooks: List of critical hook names

        Returns:
            List of mock hook result objects
        """
        results: list[t.Any] = []

        for hook_name in critical_hooks:
            mock_result = self._create_mock_hook_result(hook_name)
            results.append(mock_result)

        return results

    def _create_mock_hook_result(self, hook_name: str) -> t.Any:
        """Create a mock hook result object.

        Args:
            hook_name: Name of the hook

        Returns:
            Mock result object with name, status, and output attributes
        """
        return type(
            "MockResult",
            (),
            {
                "name": hook_name,
                "status": "unknown",
                "output": "Unable to determine hook status",
            },
        )()

    def _get_recent_comprehensive_hook_results(self) -> list[t.Any]:
        """Get recent comprehensive hook results from session.

        Returns:
            List of comprehensive hook results, or mock results if unavailable
        """
        results = self._extract_hook_results_from_session("comprehensive_hooks")

        if not results:
            results = self._create_mock_hook_results(["bandit", "pyright"])

        return results

    def _is_security_critical_failure(self, result: t.Any) -> bool:
        """Check if a hook result represents a critical security failure.

        Args:
            result: Hook result object

        Returns:
            True if result is a critical security failure, False otherwise
        """
        security_critical_hooks = {
            "bandit",
            "pyright",
            "gitleaks",
        }

        hook_name = getattr(result, "name", "").lower()
        is_failed = getattr(result, "status", "unknown") in (
            "failed",
            "error",
            "timeout",
        )

        return hook_name in security_critical_hooks and is_failed

    def _show_security_audit_warning(self) -> None:
        """Display security audit warning with recommendations.

        Shows detailed security warnings and recommendations if an audit
        report is available, otherwise shows generic security status.
        """
        audit_report = getattr(self, "_last_security_audit", None)

        if audit_report:
            self.console.print(
                "[yellow]⚠️ SECURITY AUDIT: Proceeding with partial quality success[/yellow]"
            )

            for warning in audit_report.security_warnings:
                if "CRITICAL" in warning:
                    self.console.print(f"[red]{warning}[/red]")
                elif "HIGH" in warning:
                    self.console.print(f"[yellow]{warning}[/yellow]")
                else:
                    self.console.print(f"[blue]{warning}[/blue]")

            if audit_report.recommendations:
                self.console.print("[bold]Security Recommendations: [/bold]")
                for rec in audit_report.recommendations[:3]:
                    self.console.print(f"[dim]{rec}[/dim]")
        else:
            self.console.print(
                "[yellow]⚠️ SECURITY AUDIT: Proceeding with partial quality success[/yellow]"
            )
            self.console.print(
                "[yellow]✅ Security-critical checks (bandit, pyright, gitleaks) have passed[/yellow]"
            )
            self.console.print(
                "[yellow]⚠️ Some non-critical quality checks failed - consider reviewing before production deployment[/yellow]"
            )

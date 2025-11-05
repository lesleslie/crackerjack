"""
Iterative auto-fix workflow for crackerjack.

This module implements the AutoFixWorkflow class that runs an iterative
loop to detect issues via pre-commit hooks, apply AI-powered fixes, and
verify the fixes until convergence or max iterations is reached.
"""

import asyncio
import logging
import typing as t
from dataclasses import dataclass, field
from pathlib import Path

from acb import console as acb_console
from acb.console import Console

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.enhanced_coordinator import EnhancedAgentCoordinator
from crackerjack.managers.async_hook_manager import AsyncHookManager
from crackerjack.models.task import HookResult


@dataclass
class FixIteration:
    """Records data from a single iteration of the fix cycle."""

    iteration_num: int
    hooks_run: list[str]
    issues_found: int
    fixes_applied: int
    fixes_successful: int
    hooks_passing: list[str]
    hooks_failing: list[str]
    duration: float = 0.0
    convergence_status: str = "incomplete"

    def to_dict(self) -> dict[str, t.Any]:
        """Convert iteration to dictionary for serialization."""
        return {
            "iteration_num": self.iteration_num,
            "hooks_run": self.hooks_run,
            "issues_found": self.issues_found,
            "fixes_applied": self.fixes_applied,
            "fixes_successful": self.fixes_successful,
            "hooks_passing": self.hooks_passing,
            "hooks_failing": self.hooks_failing,
            "duration": self.duration,
            "convergence_status": self.convergence_status,
        }


@dataclass
class WorkflowResult:
    """Results from the complete auto-fix workflow."""

    success: bool
    iterations: list[FixIteration] = field(default_factory=list)
    total_fixes: int = 0
    total_issues_found: int = 0
    final_status: str = "incomplete"
    total_duration: float = 0.0
    convergence_achieved: bool = False
    exit_reason: str = "unknown"

    def to_dict(self) -> dict[str, t.Any]:
        """Convert result to dictionary for serialization."""
        return {
            "success": self.success,
            "iterations": [it.to_dict() for it in self.iterations],
            "total_fixes": self.total_fixes,
            "total_issues_found": self.total_issues_found,
            "final_status": self.final_status,
            "total_duration": self.total_duration,
            "convergence_achieved": self.convergence_achieved,
            "exit_reason": self.exit_reason,
        }


class AutoFixWorkflow:
    """Iterative auto-fix workflow with convergence detection."""

    MAX_ITERATIONS = 10
    CONVERGENCE_THRESHOLD = 0  # No new fixes needed

    def __init__(
        self,
        project_path: Path | None = None,
        console: Console | None = None,
        enable_external_agents: bool = True,
    ) -> None:
        """Initialize the auto-fix workflow.

        Args:
            project_path: Path to project root (defaults to cwd)
            console: Rich console for output (creates default if None)
            enable_external_agents: Enable Claude Code external agent integration
        """
        self.project_path = project_path or Path.cwd()
        self.console = console or acb_console
        self.logger = logging.getLogger(__name__)

        # Initialize agent context
        self.context = AgentContext(
            project_path=self.project_path,
            temp_dir=self.project_path / ".crackerjack" / "temp",
        )

        # Initialize agent coordinator with external agent support
        self.coordinator = EnhancedAgentCoordinator(
            context=self.context,
            enable_external_agents=enable_external_agents,
        )

        # Initialize hook manager
        self.hook_manager = AsyncHookManager(
            console=self.console,
            pkg_path=self.project_path,
            max_concurrent=3,
        )

    async def run(
        self, command: str = "check", max_iterations: int | None = None
    ) -> WorkflowResult:
        """Run iterative auto-fix workflow.

        Args:
            command: Semantic command (test, lint, check, etc.)
            max_iterations: Max fix iterations (default: 10)

        Returns:
            WorkflowResult with iteration history and final status
        """
        max_iter = max_iterations or self.MAX_ITERATIONS
        iterations: list[FixIteration] = []
        workflow_start_time = asyncio.get_event_loop().time()

        self.logger.info(
            f"Starting auto-fix workflow: {command} (max {max_iter} iterations)"
        )
        self.console.print("[bold cyan]🔄 Auto-Fix Workflow Started[/bold cyan]")
        self.console.print(
            f"[dim]Command: {command} | Max iterations: {max_iter}[/dim]\n"
        )

        exit_reason = "unknown"
        all_passing = False

        for i in range(1, max_iter + 1):
            iteration_start_time = asyncio.get_event_loop().time()

            self.logger.info(f"Iteration {i}/{max_iter}")
            self.console.print(f"[bold]━━━ Iteration {i}/{max_iter} ━━━[/bold]")

            # Step 1: Run hooks and collect failures
            hook_results = await self._run_hooks(command)

            # Step 2: Check for convergence (all passing)
            if hook_results["all_passing"]:
                all_passing = True
                exit_reason = "convergence"

                iteration_duration = (
                    asyncio.get_event_loop().time() - iteration_start_time
                )

                iteration = FixIteration(
                    iteration_num=i,
                    hooks_run=hook_results["hooks_run"],
                    issues_found=0,
                    fixes_applied=0,
                    fixes_successful=0,
                    hooks_passing=hook_results["passing"],
                    hooks_failing=[],
                    duration=iteration_duration,
                    convergence_status="converged",
                )
                iterations.append(iteration)

                self.logger.info("✅ All hooks passing - convergence achieved!")
                self.console.print(
                    "[bold green]✅ All hooks passing - convergence achieved![/bold green]\n"
                )
                break

            # Step 3: Apply AI fixes for failures
            fix_results = await self._apply_fixes(hook_results["failures"])

            iteration_duration = asyncio.get_event_loop().time() - iteration_start_time

            # Step 4: Record iteration
            iteration = FixIteration(
                iteration_num=i,
                hooks_run=hook_results["hooks_run"],
                issues_found=len(hook_results["failures"]),
                fixes_applied=fix_results["fixes_applied"],
                fixes_successful=fix_results["fixes_successful"],
                hooks_passing=hook_results["passing"],
                hooks_failing=hook_results["failing"],
                duration=iteration_duration,
                convergence_status="in_progress",
            )
            iterations.append(iteration)

            self.console.print(
                f"[dim]Issues found: {iteration.issues_found} | "
                f"Fixes applied: {iteration.fixes_applied} | "
                f"Successful: {iteration.fixes_successful}[/dim]\n"
            )

            # Step 5: Check for convergence (no fixes possible)
            if fix_results["fixes_applied"] == 0:
                exit_reason = "no_progress"
                self.logger.warning("⚠️  No fixes applied - cannot make progress")
                self.console.print(
                    "[bold yellow]⚠️  No fixes applied - cannot make progress[/bold yellow]\n"
                )
                break

        # Handle max iterations reached
        if not all_passing and exit_reason == "unknown":
            exit_reason = "max_iterations"
            self.logger.warning(
                f"⚠️  Max iterations ({max_iter}) reached without full convergence"
            )
            self.console.print(
                f"[bold yellow]⚠️  Max iterations ({max_iter}) reached[/bold yellow]\n"
            )

        # Calculate final statistics
        total_duration = asyncio.get_event_loop().time() - workflow_start_time
        total_fixes = sum(it.fixes_successful for it in iterations)
        total_issues = sum(it.issues_found for it in iterations)

        result = WorkflowResult(
            success=all_passing,
            iterations=iterations,
            total_fixes=total_fixes,
            total_issues_found=total_issues,
            final_status="converged" if all_passing else "incomplete",
            total_duration=total_duration,
            convergence_achieved=all_passing,
            exit_reason=exit_reason,
        )

        # Print summary
        self._print_summary(result)

        return result

    async def _run_hooks(self, command: str) -> dict[str, t.Any]:
        """Run pre-commit hooks and collect results.

        Args:
            command: Semantic command (determines which hooks to run)

        Returns:
            Dictionary with hook results and status
        """
        self.logger.debug(f"Running hooks for command: {command}")

        # Choose hook strategy based on command
        if command in ("test", "check", "all"):
            results = await self.hook_manager.run_comprehensive_hooks_async()
        else:
            results = await self.hook_manager.run_fast_hooks_async()

        # Parse results
        hooks_run = [r.name for r in results]
        passing = [r.name for r in results if r.status == "passed"]
        failing = [r.name for r in results if r.status != "passed"]
        all_passing = len(failing) == 0

        self.logger.debug(
            f"Hook results: {len(passing)} passing, {len(failing)} failing"
        )

        return {
            "hooks_run": hooks_run,
            "passing": passing,
            "failing": failing,
            "failures": [r for r in results if r.status != "passed"],
            "all_passing": all_passing,
        }

    async def _apply_fixes(self, failures: list[HookResult]) -> dict[str, int]:
        """Apply AI fixes for all failures.

        Args:
            failures: List of failed HookResults

        Returns:
            Dictionary with fix statistics
        """
        fixes_applied = 0
        fixes_successful = 0

        self.logger.info(f"Applying fixes for {len(failures)} failures")

        for failure in failures:
            try:
                # Convert HookResult to Issue for agent system
                issue = self._hook_result_to_issue(failure)

                self.logger.debug(f"Fixing {failure.name}: {issue.message}")

                # Coordinate fix via enhanced agent coordinator
                result = await self.coordinator.handle_issues_proactively([issue])

                if result.fixes_applied:
                    fixes_applied += len(result.fixes_applied)

                    if result.success:
                        fixes_successful += len(result.fixes_applied)
                        self.logger.info(
                            f"✅ Successfully fixed {failure.name} ({result.confidence:.2f} confidence)"
                        )
                    else:
                        self.logger.warning(
                            f"⚠️  Partial fix for {failure.name} ({result.confidence:.2f} confidence)"
                        )
                else:
                    self.logger.debug(f"No fixes applied for {failure.name}")

            except Exception as e:
                self.logger.exception(f"Fix failed for {failure.name}: {e}")
                self.console.print(f"[red]❌ Error fixing {failure.name}: {e}[/red]")

        return {
            "fixes_applied": fixes_applied,
            "fixes_successful": fixes_successful,
        }

    def _hook_result_to_issue(self, hook_result: HookResult) -> Issue:
        """Convert a HookResult to an Issue for the agent system.

        Args:
            hook_result: Hook execution result

        Returns:
            Issue object for agent processing
        """
        # Map hook names to issue types
        issue_type_mapping: dict[str, IssueType] = {
            "refurb": IssueType.DRY_VIOLATION,
            "pyright": IssueType.TYPE_ERROR,
            "bandit": IssueType.SECURITY,
            "ruff": IssueType.FORMATTING,
            "pytest": IssueType.TEST_FAILURE,
            "complexipy": IssueType.COMPLEXITY,
            "vulture": IssueType.DEAD_CODE,
            "creosote": IssueType.DEPENDENCY,
        }

        # Determine issue type from hook name
        issue_type = IssueType.FORMATTING  # Default
        for hook_prefix, mapped_type in issue_type_mapping.items():
            if hook_result.name.lower().startswith(hook_prefix):
                issue_type = mapped_type
                break

        # Determine severity based on hook status
        severity = Priority.HIGH if hook_result.status == "failed" else Priority.MEDIUM

        # Create issue
        issue = Issue(
            id=f"{hook_result.id}_{hook_result.name}",
            type=issue_type,
            severity=severity,
            message=f"Hook {hook_result.name} failed",
            details=hook_result.issues_found or [],
            stage=hook_result.stage,
        )

        return issue

    def _check_convergence(self, hook_results: dict[str, t.Any]) -> bool:
        """Determine if workflow has converged.

        Args:
            hook_results: Results from _run_hooks

        Returns:
            True if converged (all hooks passing)
        """
        return bool(hook_results["all_passing"])

    def _print_summary(self, result: WorkflowResult) -> None:
        """Print workflow summary to console.

        Args:
            result: Final workflow result
        """
        self.console.print("\n[bold cyan]━━━ Auto-Fix Summary ━━━[/bold cyan]")

        # Status
        status_color = "green" if result.success else "yellow"
        status_icon = "✅" if result.success else "⚠️"
        self.console.print(
            f"{status_icon} [bold {status_color}]Status:[/bold {status_color}] {result.final_status}"
        )

        # Statistics
        self.console.print("📊 [bold]Statistics:[/bold]")
        self.console.print(f"  • Iterations: {len(result.iterations)}")
        self.console.print(f"  • Total issues found: {result.total_issues_found}")
        self.console.print(f"  • Total fixes applied: {result.total_fixes}")
        self.console.print(f"  • Total duration: {result.total_duration:.2f}s")
        self.console.print(f"  • Exit reason: {result.exit_reason}")

        # Iteration breakdown
        if result.iterations:
            self.console.print("\n📋 [bold]Iteration Breakdown:[/bold]")
            for iteration in result.iterations:
                status_symbol = "✅" if not iteration.hooks_failing else "❌"
                self.console.print(
                    f"  {status_symbol} Iteration {iteration.iteration_num}: "
                    f"{iteration.fixes_successful}/{iteration.fixes_applied} fixes successful "
                    f"({iteration.duration:.2f}s)"
                )

        self.console.print()


def create_auto_fix_workflow(
    project_path: Path | None = None,
    console: Console | None = None,
    enable_external_agents: bool = True,
) -> AutoFixWorkflow:
    """Factory function to create an AutoFixWorkflow.

    Args:
        project_path: Path to project root (defaults to cwd)
        console: Rich console for output (creates default if None)
        enable_external_agents: Enable Claude Code external agent integration

    Returns:
        Configured AutoFixWorkflow instance
    """
    return AutoFixWorkflow(
        project_path=project_path,
        console=console,
        enable_external_agents=enable_external_agents,
    )

from __future__ import annotations

import asyncio
import logging
import typing as t
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from crackerjack.agents.base import (
    AgentContext,
    Issue,
    SubAgent,
)

_AGENT_REGISTRY: dict[str, t.Callable[[AgentContext], SubAgent]] = {
    "TestEnvironmentAgent": lambda ctx: __import__(
        "crackerjack.agents.test_environment_agent", fromlist=["TestEnvironmentAgent"]
    ).TestEnvironmentAgent(ctx),
    "DeadCodeRemovalAgent": lambda ctx: __import__(
        "crackerjack.agents.dead_code_removal_agent", fromlist=["DeadCodeRemovalAgent"]
    ).DeadCodeRemovalAgent(ctx),
    "FormattingAgent": lambda ctx: __import__(
        "crackerjack.agents.formatting_agent", fromlist=["FormattingAgent"]
    ).FormattingAgent(ctx),
    "ImportOptimizationAgent": lambda ctx: __import__(
        "crackerjack.agents.import_optimization_agent",
        fromlist=["ImportOptimizationAgent"],
    ).ImportOptimizationAgent(ctx),
    "RefactoringAgent": lambda ctx: __import__(
        "crackerjack.agents.refactoring_agent", fromlist=["RefactoringAgent"]
    ).RefactoringAgent(ctx),
    "SecurityAgent": lambda ctx: __import__(
        "crackerjack.agents.security_agent", fromlist=["SecurityAgent"]
    ).SecurityAgent(ctx),
    "TestSpecialistAgent": lambda ctx: __import__(
        "crackerjack.agents.test_specialist_agent", fromlist=["TestSpecialistAgent"]
    ).TestSpecialistAgent(ctx),
    "TestCreationAgent": lambda ctx: __import__(
        "crackerjack.agents.test_creation_agent", fromlist=["TestCreationAgent"]
    ).TestCreationAgent(ctx),
    "DRYAgent": lambda ctx: __import__(
        "crackerjack.agents.dry_agent", fromlist=["DRYAgent"]
    ).DRYAgent(ctx),
    "PerformanceAgent": lambda ctx: __import__(
        "crackerjack.agents.performance_agent", fromlist=["PerformanceAgent"]
    ).PerformanceAgent(ctx),
    "DocumentationAgent": lambda ctx: __import__(
        "crackerjack.agents.documentation_agent", fromlist=["DocumentationAgent"]
    ).DocumentationAgent(ctx),
    "SemanticAgent": lambda ctx: __import__(
        "crackerjack.agents.semantic_agent", fromlist=["SemanticAgent"]
    ).SemanticAgent(ctx),
    "ArchitectAgent": lambda ctx: __import__(
        "crackerjack.agents.architect_agent", fromlist=["ArchitectAgent"]
    ).ArchitectAgent(ctx),
    "DependencyAgent": lambda ctx: __import__(
        "crackerjack.agents.dependency_agent", fromlist=["DependencyAgent"]
    ).DependencyAgent(ctx),
}

if t.TYPE_CHECKING:
    from rich.console import Console


logger = logging.getLogger(__name__)


class BatchStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class BatchIssueResult:
    issue: Issue
    success: bool
    confidence: float = 0.0
    attempted: bool = False
    error: str | None = None
    files_modified: list[str] = field(default_factory=list)
    retry_count: int = 0
    agent_used: str | None = None


@dataclass
class BatchProcessingResult:
    batch_id: str
    status: BatchStatus
    total_issues: int
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    success_rate: float = 0.0
    results: list[BatchIssueResult] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_seconds: float = 0.0

    @property
    def completion_percentage(self) -> float:
        if self.total_issues == 0:
            return 100.0
        completed = self.successful + self.failed + self.skipped
        return (completed / self.total_issues) * 100


class BatchProcessor:
    def __init__(
        self,
        context: AgentContext,
        console: Console,
        max_parallel: int = 3,
    ) -> None:
        from rich.console import Console as RichConsole

        self.context: AgentContext = context
        self.console: RichConsole = console
        self.max_parallel = max_parallel

        self._agents: dict[str, SubAgent] = {}

    def _get_agent(self, agent_name: str) -> SubAgent:
        if agent_name not in self._agents:
            if agent_name not in _AGENT_REGISTRY:
                logger.warning(f"Unknown agent: {agent_name}")
                raise ValueError(f"Unknown agent: {agent_name}")

            agent_factory = _AGENT_REGISTRY[agent_name]
            self._agents[agent_name] = agent_factory(self.context)

        return self._agents[agent_name]

    async def process_batch(
        self,
        issues: list[Issue],
        batch_id: str | None = None,
        max_retries: int = 2,
        parallel: bool = True,
    ) -> BatchProcessingResult:
        """Process a batch of issues with retry logic and parallel execution support."""
        batch_id = self._generate_batch_id(batch_id)
        result = self._initialize_batch_result(batch_id, len(issues))
        self._print_batch_header(batch_id, issues, max_retries, parallel)

        # Execute batch (parallel or sequential)
        issue_results = await self._execute_batch_processing(
            issues, max_retries, parallel
        )

        # Aggregate results and update metrics
        self._aggregate_results(result, issue_results)
        self._finalize_batch_metrics(result)

        self._print_summary(result)
        return result

    def _generate_batch_id(self, batch_id: str | None) -> str:
        """Generate batch ID if not provided."""
        if batch_id is None:
            return f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return batch_id

    def _initialize_batch_result(
        self, batch_id: str, total_issues: int
    ) -> BatchProcessingResult:
        """Initialize batch result object."""
        return BatchProcessingResult(
            batch_id=batch_id,
            status=BatchStatus.IN_PROGRESS,
            total_issues=total_issues,
            start_time=datetime.now(),
        )

    def _print_batch_header(
        self,
        batch_id: str,
        issues: list[Issue],
        max_retries: int,
        parallel: bool,
    ) -> None:
        """Print batch processing header information."""
        self.console.print(f"\n[bold cyan]🔄 Batch Processing: {batch_id}[/bold cyan]")
        self.console.print(f"Total issues: {len(issues)}")
        self.console.print(f"Max retries: {max_retries}")
        self.console.print(f"Parallel: {parallel}")
        self.console.print("")

    async def _execute_batch_processing(
        self,
        issues: list[Issue],
        max_retries: int,
        parallel: bool,
    ) -> list[t.Any]:
        """Execute batch processing in parallel or sequential mode.

        Strategy pattern: Different execution strategies based on parallel flag.
        """
        if parallel and len(issues) > 1:
            return await self._execute_parallel_batch(issues, max_retries)
        return await self._execute_sequential_batch(issues, max_retries)

    async def _execute_parallel_batch(
        self, issues: list[Issue], max_retries: int
    ) -> list[t.Any]:
        """Execute issues in parallel using asyncio.gather."""
        tasks = [self._process_single_issue(issue, max_retries) for issue in issues]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_sequential_batch(
        self, issues: list[Issue], max_retries: int
    ) -> list[t.Any]:
        """Execute issues sequentially with error handling."""
        issue_results: list[t.Any] = []
        for issue in issues:
            try:
                issue_result = await self._process_single_issue(issue, max_retries)
                issue_results.append(issue_result)
            except Exception as e:
                logger.error(f"Error processing issue: {e}")
                issue_results.append(
                    BatchIssueResult(
                        issue=issue,
                        success=False,
                        attempted=False,
                        error=str(e),
                    )
                )
        return issue_results

    def _aggregate_results(
        self, result: BatchProcessingResult, issue_results: list[t.Any]
    ) -> None:
        """Aggregate issue results into batch result.

        Guard clause pattern: Skip invalid results with early continue.
        """
        for issue_result in issue_results:
            if not self._is_valid_result(issue_result):
                continue

            result.results.append(issue_result)
            self._update_batch_counters(result, issue_result)

    def _is_valid_result(self, issue_result: t.Any) -> bool:
        """Check if result is valid BatchIssueResult."""
        if isinstance(issue_result, Exception):
            logger.error(f"Exception during processing: {issue_result}")
            return False

        if not isinstance(issue_result, BatchIssueResult):
            logger.warning(f"Unexpected result type: {type(issue_result)}")
            return False

        return True

    def _update_batch_counters(
        self, result: BatchProcessingResult, issue_result: BatchIssueResult
    ) -> None:
        """Update batch counters based on issue result."""
        if issue_result.attempted:
            if issue_result.success:
                result.successful += 1
            else:
                result.failed += 1
        else:
            result.skipped += 1

    def _finalize_batch_metrics(self, result: BatchProcessingResult) -> None:
        """Finalize batch metrics (duration, status, success rate)."""
        result.end_time = datetime.now()
        result.duration_seconds = self._calculate_duration(result)
        result.status = self._determine_batch_status(result)
        result.success_rate = self._calculate_success_rate(result)

    def _calculate_duration(self, result: BatchProcessingResult) -> float:
        """Calculate batch processing duration."""
        if result.end_time and result.start_time:
            return (result.end_time - result.start_time).total_seconds()
        return 0

    def _determine_batch_status(self, result: BatchProcessingResult) -> BatchStatus:
        """Determine final batch status based on results.

        Guard clause pattern: Return early for complete success.
        """
        if result.successful == result.total_issues:
            return BatchStatus.COMPLETED
        if result.successful > 0:
            return BatchStatus.PARTIAL
        return BatchStatus.FAILED

    def _calculate_success_rate(self, result: BatchProcessingResult) -> float:
        """Calculate batch success rate."""
        if result.total_issues > 0:
            return result.successful / result.total_issues
        return 0.0

    def _print_summary(self, result: BatchProcessingResult) -> None:
        self.console.print("\n" + "=" * 80)
        self.console.print(f"[bold]Batch Processing Summary: {result.batch_id}[/bold]")
        self.console.print("=" * 80)

        status_emoji = {
            BatchStatus.COMPLETED: "✅",
            BatchStatus.PARTIAL: "⚠️",
            BatchStatus.FAILED: "❌",
            BatchStatus.IN_PROGRESS: "🔄",
        }.get(result.status, "❓")

        self.console.print(
            f"\n[bold]Status:[/bold] {result.status.value} {status_emoji}"
        )

        self.console.print("\n[bold]Metrics:[/bold]")
        self.console.print(f"  Total issues: {result.total_issues}")
        self.console.print(f"  [green]Successful:[/green] {result.successful}")
        self.console.print(f"  [red]Failed:[/red] {result.failed}")
        self.console.print(f"  [dim]Skipped:[/dim] {result.skipped}")
        self.console.print(f"  Success rate: [bold]{result.success_rate:.1%}[/bold]")

        if result.duration_seconds > 0:
            duration_str = f"{result.duration_seconds:.1f}s"
            self.console.print(f"  Duration: {duration_str}")

        if result.failed > 0:
            self.console.print("\n[bold]Failed Issues:[/bold]")
            for r in result.results:
                if not r.success and r.attempted:
                    self.console.print(
                        f"  [red]✗[/red] {r.issue.message} ({r.error or 'Unknown error'})"
                    )

        self.console.print("\n" + "=" * 80 + "\n")

    async def _process_single_issue(
        self,
        issue: Issue,
        max_retries: int,
    ) -> BatchIssueResult:
        """Process a single issue with retry logic and agent fallback.

        Strategy pattern: Try multiple agents with confidence-based selection.
        """
        issue_result = BatchIssueResult(issue=issue, success=False, attempted=False)

        for attempt in range(max_retries + 1):
            try:
                # Try to fix with available agents
                fix_success = await self._try_fix_with_agents(issue, issue_result)

                if fix_success or issue_result.error:
                    # Either succeeded or no agents available
                    return issue_result

                # All agents failed, check if we should retry
                if not self._should_retry(issue_result, attempt, max_retries):
                    issue_result.error = "No agent could successfully fix this issue"
                    return issue_result

            except Exception as e:
                logger.error(f"Error in attempt {attempt + 1}: {e}")
                if not self._handle_retry_error(issue_result, attempt, max_retries, e):
                    return issue_result

        return issue_result

    async def _try_fix_with_agents(
        self, issue: Issue, issue_result: BatchIssueResult
    ) -> bool:
        """Try to fix issue with available agents.

        Returns True if issue was fixed or no agents available.
        """
        from crackerjack.agents.coordinator import ISSUE_TYPE_TO_AGENTS

        agent_names = ISSUE_TYPE_TO_AGENTS.get(issue.type, [])

        if not agent_names:
            issue_result.error = f"No agents available for issue type: {issue.type}"
            return True  # No agents, stop trying

        # Try each agent in priority order
        for agent_name in agent_names:
            if await self._attempt_agent_fix(issue, agent_name, issue_result):
                return True  # Issue fixed successfully

        return False  # All agents failed

    async def _attempt_agent_fix(
        self,
        issue: Issue,
        agent_name: str,
        issue_result: BatchIssueResult,
    ) -> bool:
        """Attempt to fix issue with a single agent.

        Returns True if issue was fixed, False otherwise.

        Guard clause pattern: Early return on low confidence or exceptions.
        """
        try:
            agent = self._get_agent(agent_name)
            confidence = await agent.can_handle(issue)

            if confidence < 0.7:
                return False  # Agent not confident, try next

            self.console.print(
                f"[dim]→ Attempting {agent_name} (confidence: {confidence:.2f})[/dim]"
            )

            fix_result = await agent.analyze_and_fix(issue)

            # Update issue result metadata
            issue_result.attempted = True
            issue_result.agent_used = agent_name
            issue_result.confidence = fix_result.confidence
            issue_result.success = fix_result.success
            issue_result.files_modified = fix_result.files_modified

            if fix_result.success:
                self.console.print(f"[green]✓ Fixed by {agent_name}[/green]")
                return True
            else:
                self.console.print(
                    f"[yellow]{agent_name} declined: {fix_result.remaining_issues}[/yellow]"
                )
                return False

        except Exception as e:
            logger.warning(f"Agent {agent_name} failed: {e}")
            return False

    def _should_retry(
        self, issue_result: BatchIssueResult, attempt: int, max_retries: int
    ) -> bool:
        """Check if we should retry the issue processing."""
        if attempt < max_retries:
            issue_result.retry_count += 1
            return True
        return False

    def _handle_retry_error(
        self,
        issue_result: BatchIssueResult,
        attempt: int,
        max_retries: int,
        error: Exception,
    ) -> bool:
        """Handle error during retry attempt.

        Returns True if should continue retrying, False if should stop.
        """
        if attempt == max_retries:
            issue_result.error = f"Failed after {max_retries} attempts: {error}"
            return False  # Stop retrying

        issue_result.retry_count += 1
        return True  # Continue retrying


def get_batch_processor(
    context: AgentContext,
    console: Console,
    max_parallel: int = 3,
) -> BatchProcessor:
    return BatchProcessor(context, console, max_parallel)


__all__ = [
    "BatchProcessor",
    "BatchProcessingResult",
    "BatchIssueResult",
    "BatchStatus",
    "get_batch_processor",
]

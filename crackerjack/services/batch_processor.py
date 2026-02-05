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

# Agent registry: maps agent names to factory functions
# This avoids repetitive if/elif chains and enables O(1) lookup
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
        """Get or create agent instance by name.

        Uses registry pattern for O(1) lookup and easy extensibility.
        Complexity: 3 (was 14 before refactoring).

        Args:
            agent_name: Name of agent to retrieve

        Returns:
            Agent instance

        Raises:
            ValueError: If agent_name is not in registry
        """
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

        if batch_id is None:
            batch_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        result = BatchProcessingResult(
            batch_id=batch_id,
            status=BatchStatus.IN_PROGRESS,
            total_issues=len(issues),
            start_time=datetime.now(),
        )

        self.console.print(f"\n[bold cyan]🔄 Batch Processing: {batch_id}[/bold cyan]")
        self.console.print(f"Total issues: {len(issues)}")
        self.console.print(f"Max retries: {max_retries}")
        self.console.print(f"Parallel: {parallel}")
        self.console.print("")

        if parallel and len(issues) > 1:
            tasks = [self._process_single_issue(issue, max_retries) for issue in issues]
            issue_results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            issue_results = []
            for issue in issues:
                try:
                    result = await self._process_single_issue(issue, max_retries)
                    issue_results.append(result)
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

        for issue_result in issue_results:
            if isinstance(issue_result, Exception):
                logger.error(f"Exception during processing: {issue_result}")
                continue

            if not isinstance(issue_result, BatchIssueResult):
                logger.warning(f"Unexpected result type: {type(issue_result)}")
                continue

            result.results.append(issue_result)

            if issue_result.attempted:
                if issue_result.success:
                    result.successful += 1
                else:
                    result.failed += 1
            else:
                result.skipped += 1

        result.end_time = datetime.now()
        result.duration_seconds = (
            (result.end_time - result.start_time).total_seconds()
            if result.end_time and result.start_time
            else 0
        )

        if result.successful == result.total_issues:
            result.status = BatchStatus.COMPLETED
        elif result.successful > 0:
            result.status = BatchStatus.PARTIAL
        else:
            result.status = BatchStatus.FAILED

        result.success_rate = (
            result.successful / result.total_issues if result.total_issues > 0 else 0.0
        )

        self._print_summary(result)

        return result

    async def _process_single_issue(
        self,
        issue: Issue,
        max_retries: int,
    ) -> BatchIssueResult:
        issue_result = BatchIssueResult(issue=issue, success=False, attempted=False)

        for attempt in range(max_retries + 1):
            try:
                from crackerjack.agents.coordinator import ISSUE_TYPE_TO_AGENTS

                agent_names = ISSUE_TYPE_TO_AGENTS.get(issue.type, [])

                if not agent_names:
                    issue_result.error = (
                        f"No agents available for issue type: {issue.type}"
                    )
                    return issue_result

                for agent_name in agent_names:
                    try:
                        agent = self._get_agent(agent_name)
                        confidence = await agent.can_handle(issue)

                        if confidence < 0.7:
                            continue

                        self.console.print(
                            f"[dim]→ Attempting {agent_name} (confidence: {confidence:.2f})[/dim]"
                        )

                        fix_result = await agent.analyze_and_fix(issue)

                        issue_result.attempted = True
                        issue_result.agent_used = agent_name
                        issue_result.confidence = fix_result.confidence
                        issue_result.success = fix_result.success
                        issue_result.files_modified = fix_result.files_modified

                        if fix_result.success:
                            self.console.print(
                                f"[green]✓ Fixed by {agent_name}[/green]"
                            )
                            return issue_result
                        else:
                            self.console.print(
                                f"[yellow]{agent_name} declined: {fix_result.remaining_issues}[/yellow]"
                            )
                            continue

                    except Exception as e:
                        logger.warning(f"Agent {agent_name} failed: {e}")
                        continue

                issue_result.error = "No agent could successfully fix this issue"
                return issue_result

            except Exception as e:
                logger.error(f"Error in attempt {attempt + 1}: {e}")
                if attempt == max_retries:
                    issue_result.error = f"Failed after {max_retries} attempts: {e}"
                    return issue_result

                issue_result.retry_count += 1
                await asyncio.sleep(1)
                continue

        return issue_result

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

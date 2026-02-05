#!/usr/bin/env python3

import asyncio
import cProfile
import pstats
import time
from io import StringIO
from pathlib import Path
from pstats import SortKey

from rich.console import Console

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.services.batch_processor import get_batch_processor


def create_test_issues(count: int = 10) -> list[Issue]:
    issues = []


    issue_templates = [
        (IssueType.IMPORT_ERROR, "ModuleNotFoundError: No module named 'test_mod'", "test.py"),
        (IssueType.IMPORT_ERROR, "ImportError: cannot import 'utils'", "app.py"),
        (IssueType.TEST_FAILURE, "fixture 'tmp_path' not found", "conftest.py"),
        (IssueType.FORMATTING, "Line too long (120 > 100 characters)", "module.py"),
        (IssueType.DEPENDENCY, "Unused dependency: requests", "pyproject.toml"),
    ]

    for i in range(count):
        issue_type, message, file_path = issue_templates[i % len(issue_templates)]
        issues.append(
            Issue(
                type=issue_type,
                severity=Priority.MEDIUM,
                message=message,
                file_path=f"tests/{file_path}",
                line_number=10 + i,
                id=f"issue_{i: 04d}",
            )
        )

    return issues


async def profile_batch_processing(
    issue_count: int = 10,
    parallel: bool = True,
    use_profiler: bool = True,
) -> float:
    console = Console()
    context = AgentContext(Path.cwd())
    processor = get_batch_processor(context, console, max_parallel=3)

    issues = create_test_issues(issue_count)

    console.print("\n[bold cyan]Profiling BatchProcessor[/bold cyan]")
    console.print(f"Issues: {issue_count}")
    console.print(f"Parallel: {parallel}")
    console.print("")

    if use_profiler:

        profiler = cProfile.Profile()
        profiler.enable()

    start_time = time.time()

    await processor.process_batch(
        issues=issues,
        batch_id=f"profile_{issue_count}",
        max_retries=1,
        parallel=parallel,
    )

    duration = time.time() - start_time

    if use_profiler:
        profiler.disable()


        console.print("\n[bold]Profiler Results[/bold]")

        s = StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats(SortKey.CUMULATIVE)
        ps.print_stats(20)

        console.print(s.getvalue())


    console.print("\n[bold]Performance Summary[/bold]")
    console.print(f"Duration: {duration:.2f}s")
    console.print(f"Throughput: {issue_count / duration:.2f} issues/second")
    console.print(f"Avg per issue: {duration / issue_count:.2f}s")

    return duration


async def compare_parallel_vs_sequential(issue_count: int = 10) -> None:
    console = Console()

    console.print("\n" + "=" * 80)
    console.print("[bold cyan]Performance Comparison: Parallel vs Sequential[/bold cyan]")
    console.print("=" * 80)


    console.print("\n[bold]Testing Parallel Processing...[/bold]")
    parallel_time = await profile_batch_processing(
        issue_count=issue_count, parallel=True, use_profiler=False
    )


    console.print("\n[bold]Testing Sequential Processing...[/bold]")
    sequential_time = await profile_batch_processing(
        issue_count=issue_count, parallel=False, use_profiler=False
    )


    speedup = sequential_time / parallel_time

    console.print("\n" + "=" * 80)
    console.print("[bold]Comparison Results[/bold]")
    console.print("=" * 80)
    console.print(f"Parallel: {parallel_time:.2f}s")
    console.print(f"Sequential: {sequential_time:.2f}s")
    console.print(f"Speedup: {speedup:.2f}x")

    if speedup > 1:
        console.print(f"[green]✓ Parallel processing is {speedup:.2f}x faster[/green]")
    else:
        console.print("[yellow]⚠ Sequential processing is faster (overhead?)[/yellow]")


async def identify_bottlenecks() -> None:
    console = Console()

    console.print("\n" + "=" * 80)
    console.print("[bold cyan]Bottleneck Analysis[/bold cyan]")
    console.print("=" * 80)


    await profile_batch_processing(issue_count=5, parallel=True, use_profiler=True)

    console.print("\n[bold]Key Areas to Investigate:[/bold]")
    console.print("1. Agent initialization time (lazy loading)")
    console.print("2. File I/O operations (read/write)")
    console.print("3. Agent.can_handle() calls (confidence checking)")
    console.print("4. Agent.analyze_and_fix() execution time")
    console.print("5. Backup creation overhead")


async def main() -> None:
    console = Console()

    console.print("\n" + "=" * 80)
    console.print("[bold cyan]BatchProcessor Performance Profiling[/bold cyan]")
    console.print("=" * 80)


    console.print("\n[bold]Running Baseline Test (5 issues)...[/bold]")
    baseline_time = await profile_batch_processing(
        issue_count=5, parallel=True, use_profiler=False
    )


    await identify_bottlenecks()


    await compare_parallel_vs_sequential(issue_count=10)


    console.print("\n" + "=" * 80)
    console.print("[bold]Performance Optimization Recommendations[/bold]")
    console.print("=" * 80)

    if baseline_time < 15:
        console.print("[green]✓ Performance is excellent (<15s for 5 issues)[/green]")
    elif baseline_time < 30:
        console.print("[yellow]⚠ Performance is acceptable (<30s for 5 issues)[/yellow]")
    else:
        console.print("[red]✗ Performance needs improvement (>{:0f}s for 5 issues)[/red]")

    console.print("\n[bold]Potential Optimizations:[/bold]")
    console.print("1. Agent pooling (reuse initialized agents)")
    console.print("2. Parallel file I/O (async read/write)")
    console.print("3. Caching agent.can_handle() results")
    console.print("4. Batch backup operations")
    console.print("5. Optimize SafeCodeModifier validation")


if __name__ == "__main__":
    asyncio.run(main())

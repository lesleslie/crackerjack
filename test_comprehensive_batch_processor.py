#!/usr/bin/env python3

from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.services.batch_processor import get_batch_processor
from crackerjack.services.testing.test_result_parser import get_test_result_parser
from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)


class TestOutcome(str, Enum):

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestResult:

    test_name: str
    outcome: TestOutcome
    duration: float
    message: str | None = None
    traceback: str | None = None


@dataclass
class BatchTestResult:

    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0


    issues_detected: int = 0
    issues_fixed: int = 0
    fix_rate: float = 0.0


    test_duration: float = 0.0
    fix_duration: float = 0.0
    total_duration: float = 0.0


    test_results: list[TestResult] = field(default_factory=list)
    fix_results: list = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.passed / self.total_tests) * 100


async def run_pytest_tests(
    test_path: str | Path = "tests/",
    verbose: bool = False,
) -> tuple[subprocess.CompletedProcess, float]:
    console = Console()
    console.print(f"\n[bold cyan]Running pytest on {test_path}[/bold cyan]")

    start_time = datetime.now()

    cmd = ["python", "-m", "pytest", str(test_path), "-v", "--tb=short"]
    if not verbose:
        cmd.append("-q")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        console.print("[red]✗ Pytest timed out after 5 minutes[/red]")
        raise

    duration = (datetime.now() - start_time).total_seconds()

    return result, duration


def parse_pytest_output(output: str) -> list[TestResult]:
    results = []
    lines = output.split("\n")

    for line in lines:

        if "::test_" in line and any(
            x in line for x in ["PASSED", "FAILED", "SKIPPED", "ERROR"]
        ):
            parts = line.split()
            if len(parts) >= 3:
                test_name = parts[0]
                outcome_str = parts[1]


                outcome_map = {
                    "PASSED": TestOutcome.PASSED,
                    "FAILED": TestOutcome.FAILED,
                    "SKIPPED": TestOutcome.SKIPPED,
                    "ERROR": TestOutcome.ERROR,
                    "XFAILED": TestOutcome.SKIPPED,
                    "XPASS": TestOutcome.PASSED,
                }

                outcome = outcome_map.get(outcome_str, TestOutcome.ERROR)

                results.append(
                    TestResult(
                        test_name=test_name,
                        outcome=outcome,
                        duration=0.0,
                        message=None,
                    )
                )

    return results


async def comprehensive_test_batch_processor(
    test_count: int = 20,
    parallel: bool = True,
) -> BatchTestResult:
    console = Console()
    result = BatchTestResult()

    console.print("\n" + "=" * 80)
    console.print("[bold cyan]Comprehensive BatchProcessor Testing[/bold cyan]")
    console.print("=" * 80)


    console.print("\n[bold]Phase 1: Running pytest to detect failures[/bold]")

    try:
        pytest_result, test_duration = await run_pytest_tests("tests/")
        result.test_duration = test_duration


        test_results = parse_pytest_output(pytest_result.stdout)
        result.test_results = test_results
        result.total_tests = len(test_results)
        result.passed = sum(1 for t in test_results if t.outcome == TestOutcome.PASSED)
        result.failed = sum(1 for t in test_results if t.outcome == TestOutcome.FAILED)
        result.skipped = sum(1 for t in test_results if t.outcome == TestOutcome.SKIPPED)
        result.errors = sum(1 for t in test_results if t.outcome == TestOutcome.ERROR)

        console.print(f"\nTests run: {result.total_tests}")
        console.print(f"  [green]Passed:[/green] {result.passed}")
        console.print(f"  [red]Failed:[/red] {result.failed}")
        console.print(f"  [dim]Skipped:[/dim] {result.skipped}")

    except Exception as e:
        console.print(f"[red]Error running pytest: {e}[/red]")
        result.errors = 1
        return result


    console.print("\n[bold]Phase 2: Parsing test failures into Issues[/bold]")

    parser = get_test_result_parser()

    try:

        issues = parser.parse_text_output(pytest_result.stdout)
        result.issues_detected = len(issues)

        console.print(f"Detected {len(issues)} issues from test failures")


        if len(issues) > test_count:
            console.print(f"[dim]Limiting to {test_count} issues for testing[/dim]")
            issues = issues[:test_count]

    except Exception as e:
        console.print(f"[red]Error parsing failures: {e}[/red]")
        return result

    if not issues:
        console.print("[green]✓ No test failures detected![/green]")
        return result


    console.print("\n[bold]Phase 3: Running BatchProcessor on detected issues[/bold]")

    context = AgentContext(Path.cwd())
    processor = get_batch_processor(context, console)

    start_time = datetime.now()

    try:
        batch_result = await processor.process_batch(
            issues=issues,
            batch_id=f"comprehensive_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            max_retries=1,
            parallel=parallel,
        )

        result.fix_duration = (datetime.now() - start_time).total_seconds()
        result.total_duration = result.test_duration + result.fix_duration
        result.fix_results = batch_result.results


        result.issues_fixed = batch_result.successful
        result.fix_rate = batch_result.success_rate

        console.print(f"\n[bold]Fix Results:[/bold]")
        console.print(f"  Issues processed: {len(issues)}")
        console.print(f"  [green]Fixed:[/green] {result.issues_fixed}")
        console.print(f"  [red]Failed:[/red] {batch_result.failed}")
        console.print(f"  [dim]Skipped:[/dim] {batch_result.skipped}")
        console.print(f"  Fix rate: [bold]{result.fix_rate:.1%}[/bold]")

    except Exception as e:
        console.print(f"[red]Error running BatchProcessor: {e}[/red]")
        logger.exception("BatchProcessor failed")


    console.print("\n" + "=" * 80)
    console.print("[bold]Comprehensive Test Summary[/bold]")
    console.print("=" * 80)


    test_table = Table(title="Test Metrics")
    test_table.add_column("Metric", style="cyan")
    test_table.add_column("Value", style="green")

    test_table.add_row("Total tests", str(result.total_tests))
    test_table.add_row("Passed", f"{result.passed} ({result.success_rate:.1f}%)")
    test_table.add_row("Failed", str(result.failed))
    test_table.add_row("Skipped", str(result.failed))

    console.print(test_table)


    fix_table = Table(title="AI-Fix Metrics")
    fix_table.add_column("Metric", style="cyan")
    fix_table.add_column("Value", style="green")

    fix_table.add_row("Issues detected", str(result.issues_detected))
    fix_table.add_row("Issues fixed", f"{result.issues_fixed} ({result.fix_rate:.1%})")
    fix_table.add_row("Fix rate", f"{result.fix_rate:.1%}")

    console.print(fix_table)


    perf_table = Table(title="Performance Metrics")
    perf_table.add_column("Phase", style="cyan")
    perf_table.add_column("Duration", style="green")

    perf_table.add_row("Test execution", f"{result.test_duration:.1f}s")
    perf_table.add_row("Batch processing", f"{result.fix_duration:.1f}s")
    perf_table.add_row("Total", f"{result.total_duration:.1f}s")

    console.print(perf_table)


    console.print("\n[bold]Success Criteria:[/bold]")

    if result.fix_rate >= 0.8:
        console.print("[green]✓ Fix rate ≥80%: EXCELLENT[/green]")
    elif result.fix_rate >= 0.6:
        console.print("[yellow]⚠ Fix rate ≥60%: GOOD[/yellow]")
    else:
        console.print("[red]✗ Fix rate <60%: NEEDS IMPROVEMENT[/red]")

    if result.fix_duration < 30:
        console.print("[green]✓ Batch processing <30s: EXCELLENT[/green]")
    elif result.fix_duration < 60:
        console.print("[yellow]⚠ Batch processing <60s: ACCEPTABLE[/yellow]")
    else:
        console.print("[red]✗ Batch processing >60s: TOO SLOW[/red]")

    console.print("\n" + "=" * 80)

    return result


async def main() -> None:
    console = Console()

    console.print("\n" + "=" * 80)
    console.print("[bold cyan]Comprehensive BatchProcessor Testing[/bold cyan]")
    console.print("=" * 80)

    console.print("\nThis will:")
    console.print("1. Run pytest on crackerjack tests")
    console.print("2. Parse failures into Issues")
    console.print("3. Run BatchProcessor on detected issues")
    console.print("4. Measure real-world fix rate and performance")

    console.print("\n[bold yellow]⚠ This will take several minutes...[/bold yellow]")

    result = await comprehensive_test_batch_processor(test_count=20, parallel=True)


    if result.fix_rate >= 0.6:
        console.print("\n[green]✓ Comprehensive test PASSED[/green]")
        return 0
    else:
        console.print("\n[red]✗ Comprehensive test FAILED[/red]")
        return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    exit_code = asyncio.run(main())
    exit(exit_code)

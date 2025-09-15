#!/usr/bin/env python3
"""Test script for AgentCoordinator performance optimizations."""

import asyncio
import sys
import time
from pathlib import Path

# Add the project to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.services.cache import CrackerjackCache


async def create_test_issues(count: int = 20) -> list[Issue]:
    """Create test issues across different types."""
    issues = []
    issue_types = [
        IssueType.COMPLEXITY,
        IssueType.SECURITY,
        IssueType.PERFORMANCE,
        IssueType.FORMATTING,
        IssueType.TEST_FAILURE,
    ]

    for i in range(count):
        issue_type = issue_types[i % len(issue_types)]
        issues.append(
            Issue(
                id=f"test_{i}",
                type=issue_type,
                severity=Priority.MEDIUM,
                message=f"Test {issue_type.value} issue {i}",
                file_path=f"test_file_{i % 3}.py",
                line_number=i * 10,
            )
        )

    return issues


async def test_coordinator_performance():
    """Test the performance of the optimized coordinator."""
    console = Console()
    console.print(
        "🚀 [bold blue]Testing AgentCoordinator Performance Optimizations[/bold blue]\n"
    )

    # Setup
    context = AgentContext(
        project_path=Path("."),
        config={},
    )
    cache = CrackerjackCache()
    coordinator = AgentCoordinator(context, cache)

    # Test with different issue counts
    test_counts = [5, 10, 20]

    for count in test_counts:
        console.print(f"[cyan]📊 Testing with {count} issues[/cyan]")

        issues = await create_test_issues(count)

        # Measure performance
        start_time = time.time()
        result = await coordinator.handle_issues(issues)
        end_time = time.time()

        execution_time = end_time - start_time

        console.print(f"  • Execution time: {execution_time:.3f}s")
        console.print(f"  • Success rate: {result.success}")
        console.print(f"  • Confidence: {result.confidence:.2f}")
        console.print(f"  • Issues per second: {count / execution_time:.1f}")

        # Test caching benefit
        console.print("  • Testing cache performance...")
        start_time = time.time()
        await coordinator.handle_issues(issues)  # Same issues should hit cache
        end_time = time.time()

        cached_time = end_time - start_time
        speedup = execution_time / cached_time if cached_time > 0 else float("inf")

        console.print(f"  • Cached execution time: {cached_time:.3f}s")
        console.print(f"  • Speedup from caching: {speedup:.1f}x")
        console.print()

    console.print("✅ [bold green]Performance testing completed![/bold green]")


if __name__ == "__main__":
    asyncio.run(test_coordinator_performance())

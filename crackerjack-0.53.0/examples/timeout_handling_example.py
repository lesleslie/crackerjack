#!/usr/bin/env python3
"""
Comprehensive example of async timeout handling and performance monitoring.

This example demonstrates all the timeout handling features implemented
in crackerjack, including circuit breakers, performance monitoring,
and graceful degradation strategies.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add crackerjack to path for standalone execution
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console

from crackerjack.core.performance_monitor import get_performance_monitor
from crackerjack.core.service_watchdog import ServiceConfig, ServiceWatchdog
from crackerjack.core.timeout_manager import (
    TimeoutConfig,
    TimeoutStrategy,
    configure_timeouts,
    get_performance_report,
    get_timeout_manager,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
console = Console()


async def simulate_fast_operation() -> str:
    """Simulate a fast operation that usually succeeds."""
    await asyncio.sleep(0.5)  # 500ms operation
    current_task = asyncio.current_task()
    if current_task is not None and current_task.get_name() == "failing_task":
        raise RuntimeError("Simulated failure")
    return "Fast operation completed"


async def simulate_slow_operation() -> str:
    """Simulate a slow operation that might timeout."""
    await asyncio.sleep(3.0)  # 3 second operation
    return "Slow operation completed"


async def simulate_hanging_operation() -> str:
    """Simulate an operation that hangs indefinitely."""
    await asyncio.sleep(3600)  # 1 hour - will definitely timeout
    return "This should never complete"


async def simulate_network_operation() -> dict:
    """Simulate a network operation with potential failures."""
    import random

    # Simulate network delay
    delay = random.uniform(0.1, 2.0)
    await asyncio.sleep(delay)

    # Simulate occasional failures
    if random.random() < 0.2:  # 20% failure rate
        raise ConnectionError("Simulated network failure")

    return {"status": "success", "data": "Network response", "delay": delay}


async def demonstrate_basic_timeout_handling():
    """Demonstrate basic timeout handling with different strategies."""
    console.print("\n[bold blue]🔧 Basic Timeout Handling[/bold blue]")

    timeout_manager = get_timeout_manager()

    # 1. FAIL_FAST strategy - immediate failure on timeout
    console.print("\n1. FAIL_FAST Strategy:")
    try:
        result = await timeout_manager.with_timeout(
            "fast_operation",
            simulate_fast_operation(),
            timeout=2.0,
            strategy=TimeoutStrategy.FAIL_FAST,
        )
        console.print(f"[green]✅ {result}[/green]")
    except Exception as e:
        console.print(f"[red]❌ Failed: {e}[/red]")

    # 2. RETRY_WITH_BACKOFF strategy
    console.print("\n2. RETRY_WITH_BACKOFF Strategy:")
    try:
        # This will timeout but retry with exponential backoff
        result = await timeout_manager.with_timeout(
            "slow_operation",
            simulate_slow_operation(),
            timeout=1.0,  # Short timeout to trigger retries
            strategy=TimeoutStrategy.RETRY_WITH_BACKOFF,
        )
        console.print(f"[green]✅ {result}[/green]")
    except Exception as e:
        console.print(f"[red]❌ Failed after retries: {e}[/red]")

    # 3. GRACEFUL_DEGRADATION strategy
    console.print("\n3. GRACEFUL_DEGRADATION Strategy:")
    try:
        result = await timeout_manager.with_timeout(
            "hanging_operation",
            simulate_hanging_operation(),
            timeout=2.0,
            strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
        )
        console.print(f"[green]✅ {result}[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠️ Graceful failure: {e}[/yellow]")


async def demonstrate_circuit_breaker():
    """Demonstrate circuit breaker functionality."""
    console.print("\n[bold blue]⚡ Circuit Breaker Pattern[/bold blue]")

    timeout_manager = get_timeout_manager()

    # Configure circuit breaker with low threshold for demo
    timeout_manager.config.failure_threshold = 3

    console.print("\nGenerating failures to trigger circuit breaker...")

    for i in range(8):  # Try 8 operations to trigger circuit breaker
        try:
            # Create a failing task
            task = asyncio.create_task(
                simulate_fast_operation(),
                name="failing_task" if i < 5 else "normal_task",  # First 5 fail
            )

            await timeout_manager.with_timeout(
                "circuit_breaker_test",
                task,
                timeout=1.0,
                strategy=TimeoutStrategy.CIRCUIT_BREAKER,
            )
            console.print(f"[green]✅ Attempt {i + 1}: Success[/green]")

        except Exception as e:
            console.print(f"[red]❌ Attempt {i + 1}: {type(e).__name__}[/red]")

        await asyncio.sleep(0.1)  # Brief pause between attempts


async def demonstrate_performance_monitoring():
    """Demonstrate performance monitoring capabilities."""
    console.print("\n[bold blue]📊 Performance Monitoring[/bold blue]")

    timeout_manager = get_timeout_manager()
    performance_monitor = get_performance_monitor()

    # Run various operations to generate metrics
    console.print("\nExecuting operations to generate metrics...")

    operations = [
        ("network_operations", simulate_network_operation, 1.0),
        ("fast_operations", simulate_fast_operation, 2.0),
        ("slow_operations", simulate_slow_operation, 4.0),  # Will succeed
        ("timeout_operations", simulate_hanging_operation, 1.0),  # Will timeout
    ]

    for op_name, op_func, timeout in operations:
        console.print(f"\nTesting {op_name}...")

        # Run operation multiple times to build statistics
        for i in range(5):
            try:
                await timeout_manager.with_timeout(
                    op_name,
                    op_func(),
                    timeout=timeout,
                    strategy=TimeoutStrategy.FAIL_FAST,
                )
                console.print(f"[green]  ✅ Attempt {i + 1}: Success[/green]")
            except Exception as e:
                console.print(f"[red]  ❌ Attempt {i + 1}: {type(e).__name__}[/red]")

            await asyncio.sleep(0.1)

    # Display performance report
    console.print("\n" + "=" * 60)
    performance_monitor.print_performance_report(console)

    # Get performance alerts
    alerts = performance_monitor.get_performance_alerts()
    if alerts:
        console.print("\n[bold red]⚠️ Performance Alerts:[/bold red]")
        for alert in alerts:
            console.print(f"  • {alert['operation']}: {alert['type']} alert")

    # Export metrics to file
    metrics_file = Path("timeout_metrics.json")
    performance_monitor.export_metrics_json(metrics_file)
    console.print(f"\n[blue]📄 Metrics exported to {metrics_file}[/blue]")


async def demonstrate_service_watchdog():
    """Demonstrate service watchdog capabilities."""
    console.print("\n[bold blue]🐕 Service Watchdog[/bold blue]")

    # Create a watchdog instance
    watchdog = ServiceWatchdog(console)

    # Add a custom test service
    test_service_config = ServiceConfig(
        name="Test Service",
        command=[
            "python",
            "-c",
            "import time; time.sleep(10); print('Test service running')",
        ],
        startup_timeout=5.0,
        shutdown_timeout=3.0,
        max_restarts=2,
    )

    watchdog.add_service("test_service", test_service_config)

    try:
        # Start the watchdog
        await watchdog.start_watchdog()

        console.print("\nWatchdog started, monitoring services for 15 seconds...")

        # Let it run for a bit
        await asyncio.sleep(15)

        # Print status report
        watchdog.print_status_report()

    finally:
        # Clean shutdown
        await watchdog.stop_watchdog()


async def demonstrate_timeout_context():
    """Demonstrate timeout context manager usage."""
    console.print("\n[bold blue]🔧 Timeout Context Manager[/bold blue]")

    timeout_manager = get_timeout_manager()

    # Example 1: Successful operation with context manager
    console.print("\n1. Successful operation:")
    try:
        async with timeout_manager.timeout_context(
            "context_success", timeout=3.0, strategy=TimeoutStrategy.FAIL_FAST
        ):
            result = await simulate_fast_operation()
            console.print(f"[green]✅ {result}[/green]")
    except Exception as e:
        console.print(f"[red]❌ {e}[/red]")

    # Example 2: Operation that times out
    console.print("\n2. Operation that times out:")
    try:
        async with timeout_manager.timeout_context(
            "context_timeout", timeout=1.0, strategy=TimeoutStrategy.FAIL_FAST
        ):
            result = await simulate_hanging_operation()
            console.print(f"[green]✅ {result}[/green]")
    except Exception as e:
        console.print(f"[red]❌ {e}[/red]")


def demonstrate_configuration():
    """Demonstrate timeout configuration."""
    console.print("\n[bold blue]⚙️ Timeout Configuration[/bold blue]")

    # Create custom timeout configuration
    custom_config = TimeoutConfig(
        default_timeout=10.0,
        operation_timeouts={
            "database_query": 5.0,
            "api_request": 15.0,
            "file_upload": 60.0,
            "ai_processing": 120.0,
        },
        max_retries=5,
        base_retry_delay=2.0,
        failure_threshold=10,  # Higher threshold for production
        recovery_timeout=300.0,  # 5 minutes
    )

    # Configure the global timeout manager
    configure_timeouts(custom_config)

    console.print("✅ Configured custom timeouts:")
    console.print(f"  • Default timeout: {custom_config.default_timeout}s")
    console.print(f"  • Max retries: {custom_config.max_retries}")
    console.print(f"  • Circuit breaker threshold: {custom_config.failure_threshold}")

    # Show operation-specific timeouts
    console.print("  • Operation timeouts:")
    for operation, timeout in custom_config.operation_timeouts.items():
        console.print(f"    - {operation}: {timeout}s")


async def main():
    """Run all timeout handling demonstrations."""
    console.print("[bold green]🚀 Crackerjack Timeout Handling Examples[/bold green]")
    console.print("=" * 60)

    try:
        # 1. Configuration
        demonstrate_configuration()

        # 2. Basic timeout handling
        await demonstrate_basic_timeout_handling()

        # 3. Context manager usage
        await demonstrate_timeout_context()

        # 4. Circuit breaker
        await demonstrate_circuit_breaker()

        # 5. Performance monitoring
        await demonstrate_performance_monitoring()

        # 6. Service watchdog (comment out if you don't want processes started)
        # await demonstrate_service_watchdog()

        # Final performance report
        console.print("\n" + "=" * 60)
        console.print("[bold blue]📊 Final Performance Report[/bold blue]")
        report = get_performance_report()

        summary = report["summary"]
        console.print(f"Total operations: {summary['total_operations']}")
        console.print(f"Success rate: {summary['overall_success_rate']:.1f}%")
        console.print(f"Timeout rate: {summary['timeout_rate']:.1f}%")
        console.print(f"Operations per minute: {summary['operations_per_minute']:.1f}")

        if report["alerts"]:
            console.print("\n[yellow]⚠️ Active alerts:[/yellow]")
            for alert in report["alerts"]:
                console.print(f"  • {alert['operation']}: {alert['type']}")

        console.print("\n[green]✅ All demonstrations completed successfully![/green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⏹️ Interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]💥 Demonstration failed: {e}[/red]")
        logger.exception("Demonstration error")


if __name__ == "__main__":
    asyncio.run(main())

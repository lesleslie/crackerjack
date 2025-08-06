# !/ usr / bin / env python3

import asyncio
from pathlib import Path
from unittest.mock import Mock

from rich.console import Console

from crackerjack.config.hooks import HookConfigLoader
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.orchestration.advanced_orchestrator import AdvancedWorkflowOrchestrator
from crackerjack.orchestration.execution_strategies import (
    OrchestrationConfig,
    ExecutionStrategy,
    ProgressLevel,
    AIMode,
)


class MockOptions:

    def __init__(self):
        self.tests = True
        self.coverage = True
        self.test_timeout = 300
        self.test_workers = 4
        self.verbose = True


async def demonstrate_orchestrated_workflow():

    console = Console()
    pkg_path = Path.cwd()
    session = SessionCoordinator(console, pkg_path)


    config = OrchestrationConfig(
        execution_strategy = ExecutionStrategy.INDIVIDUAL,
        progress_level = ProgressLevel.GRANULAR,
        ai_mode = AIMode.SINGLE_AGENT,
        correlation_tracking = True,
        failure_analysis = True,
        intelligent_retry = True,
        debug_level = "verbose",
        log_individual_outputs = True,
    )


    orchestrator = AdvancedWorkflowOrchestrator(
        console = console,
        pkg_path = pkg_path,
        session = session,
        config = config,
    )

    console.print("\n[bold bright_cyan]🎯 ORCHESTRATED WORKFLOW DEMONSTRATION[ / bold bright_cyan]")
    console.print("This demo shows the enhanced / crackerjack: run capabilities: \n")

    console.print("[bold]✨ New Features: [ / bold]")
    console.print(" 🔍 Individual hook execution with real - time streaming")
    console.print(" 🧪 Granular test progress tracking")
    console.print(" 📊 Cross - iteration correlation analysis")
    console.print(" 🤖 Intelligent AI coordination")
    console.print(" 📈 Advanced progress streaming")
    console.print(" 🎯 Adaptive execution strategies")


    options = MockOptions()

    try:

        console.print(f"\n[bold yellow]⚡ Starting orchestrated execution...[ / bold yellow]")

        success = await orchestrator.execute_orchestrated_workflow(
            options = options,
            max_iterations = 3,
        )

        if success:
            console.print(f"\n[bold green]🎉 Workflow completed successfully ! [ / bold green]")
        else:
            console.print(f"\n[bold yellow]⚠️ Workflow incomplete (demo mode)[ / bold yellow]")

    except Exception as e:
        console.print(f"\n[bold red]❌ Demo error: {e}[ / bold red]")
        console.print("[dim]This is expected in demo mode without a full project setup[ / dim]")


def demonstrate_execution_strategies():

    console = Console()

    console.print("\n[bold bright_magenta]🎯 EXECUTION STRATEGIES[ / bold bright_magenta]")
    console.print("The orchestrated system supports multiple execution modes: \n")

    strategies = [
        ("BATCH", "Fast execution using current fast→comprehensive grouping"),
        ("INDIVIDUAL", "Run each hook separately with real - time streaming"),
        ("ADAPTIVE", "AI selects best strategy based on context and failures"),
        ("SELECTIVE", "Run only specific hooks based on file changes"),
    ]

    for name, description in strategies:
        console.print(f"[bold cyan]{name: 12}[ / bold cyan] - {description}")

    console.print("\n[bold]Progress Levels: [ / bold]")
    levels = [
        ("BASIC", "Stage - level progress only"),
        ("DETAILED", "Hook and test level progress"),
        ("GRANULAR", "Real - time output streaming"),
        ("STREAMING", "WebSocket real - time streaming"),
    ]

    for name, description in levels:
        console.print(f"[bold green]{name: 12}[ / bold green] - {description}")

    console.print("\n[bold]AI Coordination Modes: [ / bold]")
    modes = [
        ("SINGLE_AGENT", "Current single AI agent"),
        ("MULTI_AGENT", "Multiple specialized agents (future)"),
        ("COORDINATOR", "AI coordinator with sub - agents (future)"),
    ]

    for name, description in modes:
        console.print(f"[bold magenta]{name: 14}[ / bold magenta] - {description}")


def main():

    console = Console()

    console.print("[bold bright_blue]🚀 CRACKERJACK ORCHESTRATED WORKFLOW DEMO[ / bold bright_blue]")
    console.print(" = " * 60)


    demonstrate_execution_strategies()


    console.print("\n[bold yellow]Press Enter to run orchestrated workflow demo...[ / bold yellow]")
    input()

    try:
        asyncio.run(demonstrate_orchestrated_workflow())
    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted by user[ / yellow]")
    except Exception as e:
        console.print(f"\n[red]Demo error: {e}[ / red]")

    console.print("\n[bold green]Demo completed ! [ / bold green]")
    console.print("\n[dim]To use the orchestrated workflow in practice: [ / dim]")
    console.print("[dim] python - m crackerjack -- orchestrated - t[ / dim]")
    console.print("[dim] / crackerjack: run (with enhanced MCP support)[ / dim]")


if __name__ == "__main__":
    main()

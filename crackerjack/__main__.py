"""Crackerjack CLI entry point with Oneiric integration.

Phase 6 Implementation: MCPServerCLIFactory integration (226→120 lines, 47% reduction)
"""

import subprocess

import typer
from mcp_common.cli import MCPServerCLIFactory
from rich.console import Console

from crackerjack.cli.lifecycle_handlers import (
    health_probe_handler,
    start_handler,
    stop_handler,
)
from crackerjack.config import CrackerjackSettings, load_settings
from crackerjack.config.mcp_settings_adapter import CrackerjackMCPSettings
from crackerjack.server import CrackerjackServer

# ============================================================================
# MCP Server Lifecycle (Oneiric Factory Pattern)
# ============================================================================

# Load settings for CLI factory
mcp_settings = CrackerjackMCPSettings.load_for_crackerjack()

factory = MCPServerCLIFactory(
    server_name="crackerjack",
    settings=mcp_settings,
    start_handler=start_handler,
    stop_handler=stop_handler,
    health_probe_handler=health_probe_handler,
)

app = factory.create_app()

console = Console()


# ============================================================================
# QA Commands (Domain-Specific, Preserved from Original CLI)
# ============================================================================


@app.command()
def run_tests(
    workers: int = typer.Option(
        0, "--workers", "-n", help="Test workers (0=auto-detect)"
    ),
    timeout: int = typer.Option(300, "--timeout", help="Test timeout in seconds"),
    coverage: bool = typer.Option(
        True, "--coverage/--no-coverage", help="Run with coverage tracking"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    benchmark: bool = typer.Option(
        False, "--benchmark", help="Run performance benchmarks"
    ),
):
    """Run test suite with pytest.

    Supports parallel execution via pytest-xdist with automatic worker detection.
    Coverage is tracked with pytest-cov and stored in htmlcov/ directory.
    """
    cmd = ["pytest"]

    # Worker configuration (pytest-xdist)
    if workers != 1:
        cmd.extend(["-n", str(workers) if workers > 0 else "auto"])

    # Coverage tracking
    if coverage:
        cmd.extend(["--cov=crackerjack", "--cov-report=html", "--cov-report=term"])

    # Timeout protection
    cmd.append(f"--timeout={timeout}")

    # Verbosity
    if verbose:
        cmd.append("-vv")

    # Benchmarks
    if benchmark:
        cmd.append("--benchmark-only")

    console.print(f"[blue]Running: {' '.join(cmd)}[/blue]")
    result = subprocess.run(cmd)
    raise typer.Exit(result.returncode)


@app.command()
def qa_health():
    """Check health of QA adapters.

    Displays enabled/disabled adapter flags and health status.
    """
    settings = load_settings(CrackerjackSettings)
    server = CrackerjackServer(settings)
    health = server.get_health_snapshot()

    qa_status = health.lifecycle_state.get("qa_adapters", {})
    enabled_flags = qa_status.get("enabled_flags", {})

    console.print("\n[bold]QA Adapter Health[/bold]")
    console.print(f"Total adapters: {qa_status.get('total', 0)}")
    console.print(f"Healthy adapters: {qa_status.get('healthy', 0)}")

    console.print("\n[bold]Enabled Adapters:[/bold]")
    for adapter_name, enabled in enabled_flags.items():
        status = "✅" if enabled else "❌"
        console.print(f"  {status} {adapter_name}")

    if qa_status.get("total", 0) == qa_status.get("healthy", 0):
        console.print("\n[green]✅ All adapters healthy[/green]")
        raise typer.Exit(0)
    else:
        console.print("\n[yellow]⚠️  Some adapters unhealthy[/yellow]")
        raise typer.Exit(1)


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()

"""Crackerjack CLI entry point with Oneiric integration.

Phase 3 Implementation: Streamlined CLI (648→180 lines, 72% reduction)
"""

import logging
import subprocess

import typer
from rich.console import Console

from crackerjack.config import CrackerjackSettings, load_settings
from crackerjack.server import CrackerjackServer

app = typer.Typer(
    name="crackerjack",
    help="Python QA tooling with AI integration and Oneiric runtime management",
    no_args_is_help=True,
)

console = Console()
logger = logging.getLogger(__name__)


# ============================================================================
# Server Lifecycle Commands (Oneiric Integration)
# ============================================================================


@app.command()
def start(
    instance_id: str | None = typer.Option(
        None, "--instance-id", help="Server instance ID for multi-instance support"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    http_mode: bool = typer.Option(
        False, "--http", help="Start server in HTTP mode instead of STDIO"
    ),
    http_port: int = typer.Option(
        8676, "--http-port", help="HTTP port for the server (default: 8676)"
    ),
):
    """Start Crackerjack MCP server.

    The server manages QA adapter lifecycle and provides MCP tool endpoints.
    Use Ctrl+C to stop the server gracefully.
    """
    # Apply CLI overrides
    if instance_id:
        # TODO(Phase 4): Implement instance_id support
        console.print(
            "[yellow]Instance ID support not yet implemented (Phase 4)[/yellow]"
        )

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
        console.print("[blue]Verbose logging enabled[/blue]")

    try:
        console.print("[green]Starting Crackerjack MCP server...[/green]")
        # Start the actual MCP server with mcp-common and Oneiric integration
        from crackerjack.mcp.server_core import main as mcp_main

        mcp_main(".", http_mode=http_mode, http_port=http_port if http_mode else None)
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down server...[/yellow]")
        raise typer.Exit(0)


@app.command()
def stop(
    instance_id: str | None = typer.Option(
        None, "--instance-id", help="Server instance ID to stop"
    ),
):
    """Stop running Crackerjack MCP server.

    TODO(Phase 4): Integrate with Oneiric graceful shutdown via runtime cache.
    """
    console.print("[yellow]Stop command not yet implemented (Phase 4)[/yellow]")
    console.print("[dim]Use Ctrl+C to stop the server for now[/dim]")
    raise typer.Exit(1)


@app.command()
def restart(
    instance_id: str | None = typer.Option(
        None, "--instance-id", help="Server instance ID to restart"
    ),
):
    """Restart Crackerjack MCP server.

    TODO(Phase 4): Integrate with Oneiric restart logic.
    """
    console.print("[yellow]Restart command not yet implemented (Phase 4)[/yellow]")
    raise typer.Exit(1)


@app.command()
def status(
    instance_id: str | None = typer.Option(
        None, "--instance-id", help="Server instance ID to check"
    ),
):
    """Show server status.

    TODO(Phase 4): Read from Oneiric runtime cache (.oneiric_cache/runtime_health.json).
    """
    console.print("[yellow]Status command not yet implemented (Phase 4)[/yellow]")
    console.print("[dim]TODO: Read from .oneiric_cache/runtime_health.json[/dim]")
    raise typer.Exit(1)


@app.command()
def health(
    probe: bool = typer.Option(
        False, "--probe", help="Health probe for systemd/monitoring integration"
    ),
    instance_id: str | None = typer.Option(
        None, "--instance-id", help="Server instance ID to check"
    ),
):
    """Check server health.

    When --probe is used, exits with code 0 if healthy, 1 if unhealthy.
    Suitable for systemd liveness/readiness checks.

    TODO(Phase 4): Integrate with Oneiric health snapshot.
    """
    if probe:
        # Systemd/monitoring integration
        console.print("[yellow]Health probe not yet implemented (Phase 4)[/yellow]")
        raise typer.Exit(1)
    else:
        console.print("[yellow]Health check not yet implemented (Phase 4)[/yellow]")
        raise typer.Exit(1)


# ============================================================================
# QA Commands (Preserved from Original CLI)
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

    qa_status = health.get("qa_adapters", {})
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

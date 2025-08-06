import asyncio
from enum import Enum

import typer
from pydantic import BaseModel, field_validator
from rich.console import Console

from .crackerjack import create_crackerjack_runner

console = Console(force_terminal=True)
app = typer.Typer(
    help="Crackerjack: Your Python project setup and style enforcement tool."
)


class BumpOption(str, Enum):
    patch = "patch"
    minor = "minor"
    major = "major"
    interactive = "interactive"

    def __str__(self) -> str:
        return self.value


class Options(BaseModel):
    commit: bool = False
    interactive: bool = False
    no_config_updates: bool = False
    publish: BumpOption | None = None
    bump: BumpOption | None = None
    verbose: bool = False
    update_precommit: bool = False
    update_docs: bool = False
    force_update_docs: bool = False
    compress_docs: bool = False
    clean: bool = False
    test: bool = False
    benchmark: bool = False
    benchmark_regression: bool = False
    benchmark_regression_threshold: float = 5.0
    test_workers: int = 0
    test_timeout: int = 0
    all: BumpOption | None = None
    ai_agent: bool = False
    create_pr: bool = False
    skip_hooks: bool = False
    comprehensive: bool = False
    async_mode: bool = False
    track_progress: bool = False
    resume_from: str | None = None
    progress_file: str | None = None
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    no_git_tags: bool = False
    skip_version_check: bool = False
    start_mcp_server: bool = False
    stop_mcp_server: bool = False
    restart_mcp_server: bool = False
    start_websocket_server: bool = False
    stop_websocket_server: bool = False
    restart_websocket_server: bool = False
    websocket_port: int = 8675
    watchdog: bool = False
    monitor: bool = False
    enhanced_monitor: bool = False

    @classmethod
    @field_validator("publish", "bump", mode="before")
    def validate_bump_options(cls, value: str | None) -> BumpOption | None:
        if value is None:
            return None
        if value == "":
            return BumpOption.interactive
        try:
            return BumpOption(value.lower())
        except ValueError:
            valid_options = ", ".join([o.value for o in BumpOption])
            raise ValueError(
                f"Invalid bump option: {value}. Must be one of: {valid_options}"
            )


cli_options = {
    "commit": typer.Option(False, "-c", "--commit", help="Commit changes to Git."),
    "interactive": typer.Option(
        False,
        "-i",
        "--interactive",
        help="Use the interactive Rich UI for a better experience.",
    ),
    "no_config_updates": typer.Option(
        False, "-n", "--no-config-updates", help="Do not update configuration files."
    ),
    "update_precommit": typer.Option(
        False,
        "-u",
        "--update-precommit",
        help="[DEPRECATED] Pre-commit hooks are now updated automatically weekly.",
    ),
    "update_docs": typer.Option(
        False,
        "--update-docs",
        help="Update CLAUDE.md and RULES.md with latest quality standards.",
    ),
    "force_update_docs": typer.Option(
        False,
        "--force-update-docs",
        help="Force update CLAUDE.md and RULES.md even if they exist.",
    ),
    "compress_docs": typer.Option(
        False,
        "--compress-docs",
        help="Automatically compress CLAUDE.md to optimize for Claude Code (enabled by default for other projects).",
    ),
    "verbose": typer.Option(False, "-v", "--verbose", help="Enable verbose output."),
    "publish": typer.Option(
        None,
        "-p",
        "--publish",
        help="Bump version and publish to PyPI (patch, minor, major). Use 'interactive' to be prompted for version selection.",
        case_sensitive=False,
    ),
    "bump": typer.Option(
        None,
        "-b",
        "--bump",
        help="Bump version (patch, minor, major).",
        case_sensitive=False,
    ),
    "clean": typer.Option(
        False,
        "-x",
        "--clean",
        help="Remove docstrings, line comments, and unnecessary whitespace from source code (doesn't affect test files).",
    ),
    "test": typer.Option(False, "-t", "--test", help="Run tests."),
    "benchmark": typer.Option(
        False,
        "--benchmark",
        help="Run tests in benchmark mode (disables parallel execution).",
    ),
    "benchmark_regression": typer.Option(
        False,
        "--benchmark-regression",
        help="Fail tests if benchmarks regress beyond threshold.",
    ),
    "benchmark_regression_threshold": typer.Option(
        5.0,
        "--benchmark-regression-threshold",
        help="Maximum allowed performance regression percentage (default: 5.0%).",
    ),
    "test_workers": typer.Option(
        0,
        "--test-workers",
        help="Number of parallel workers for running tests (0 = auto-detect, 1 = disable parallelization).",
    ),
    "test_timeout": typer.Option(
        0,
        "--test-timeout",
        help="Timeout in seconds for individual tests (0 = use default based on project size).",
    ),
    "skip_hooks": typer.Option(
        False,
        "-s",
        "--skip-hooks",
        help="Skip running pre-commit hooks (useful with -t).",
    ),
    "all": typer.Option(
        None,
        "-a",
        "--all",
        help="Run with `-x -t -p <patch|minor|major> -c` development options).",
        case_sensitive=False,
    ),
    "create_pr": typer.Option(
        False, "-r", "--pr", help="Create a pull request to the upstream repository."
    ),
    "ai_agent": typer.Option(
        False,
        "--ai-agent",
        help="Enable AI agent mode with structured output.",
        hidden=True,
    ),
    "comprehensive": typer.Option(
        False,
        "--comprehensive",
        help="Use comprehensive pre-commit hooks (slower but thorough).",
    ),
    "async_mode": typer.Option(
        False,
        "--async",
        help="Enable async mode for faster file operations (experimental).",
        hidden=True,
    ),
    "track_progress": typer.Option(
        False,
        "--track-progress",
        help="Enable session progress tracking with detailed markdown output.",
    ),
    "resume_from": typer.Option(
        None,
        "--resume-from",
        help="Resume session from existing progress file.",
    ),
    "progress_file": typer.Option(
        None,
        "--progress-file",
        help="Custom path for progress file (default: SESSION-PROGRESS-{timestamp}.md).",
    ),
    "experimental_hooks": typer.Option(
        False,
        "--experimental-hooks",
        help="Enable experimental pre-commit hooks (includes pyrefly and ty).",
    ),
    "enable_pyrefly": typer.Option(
        False,
        "--enable-pyrefly",
        help="Enable pyrefly experimental type checking (requires experimental hooks mode).",
    ),
    "enable_ty": typer.Option(
        False,
        "--enable-ty",
        help="Enable ty experimental type verification (requires experimental hooks mode).",
    ),
    "no_git_tags": typer.Option(
        False,
        "--no-git-tags",
        help="Skip creating git tags during version bumping (tags are created by default).",
    ),
    "skip_version_check": typer.Option(
        False,
        "--skip-version-check",
        help="Skip version consistency verification between pyproject.toml and git tags.",
    ),
    "start_mcp_server": typer.Option(
        False,
        "--start-mcp-server",
        help="Start MCP server for AI agent integration.",
    ),
    "stop_mcp_server": typer.Option(
        False,
        "--stop-mcp-server",
        help="Stop all running MCP servers.",
    ),
    "restart_mcp_server": typer.Option(
        False,
        "--restart-mcp-server",
        help="Restart MCP server (stop and start again).",
    ),
    "start_websocket_server": typer.Option(
        False,
        "--start-websocket-server",
        help="Start dedicated WebSocket progress server (runs on localhost:8675).",
    ),
    "stop_websocket_server": typer.Option(
        False,
        "--stop-websocket-server",
        help="Stop all running WebSocket servers.",
    ),
    "restart_websocket_server": typer.Option(
        False,
        "--restart-websocket-server",
        help="Restart WebSocket server (stop and start again).",
    ),
    "websocket_port": typer.Option(
        8675,
        "--websocket-port",
        help="Custom port for WebSocket server (default: 8675).",
    ),
    "watchdog": typer.Option(
        False,
        "--watchdog",
        help="Start service watchdog to monitor and auto-restart MCP and WebSocket servers.",
    ),
    "monitor": typer.Option(
        False,
        "--monitor",
        help="Start enhanced multi-project progress monitor with Textual TUI.",
    ),
    "enhanced_monitor": typer.Option(
        False,
        "--enhanced-monitor",
        help="Start advanced dashboard monitor with MetricCard widgets.",
    ),
}


@app.command()
def main(
    commit: bool = cli_options["commit"],
    interactive: bool = cli_options["interactive"],
    no_config_updates: bool = cli_options["no_config_updates"],
    update_precommit: bool = cli_options["update_precommit"],
    update_docs: bool = cli_options["update_docs"],
    force_update_docs: bool = cli_options["force_update_docs"],
    compress_docs: bool = cli_options["compress_docs"],
    verbose: bool = cli_options["verbose"],
    publish: BumpOption | None = cli_options["publish"],
    all: BumpOption | None = cli_options["all"],
    bump: BumpOption | None = cli_options["bump"],
    clean: bool = cli_options["clean"],
    test: bool = cli_options["test"],
    benchmark: bool = cli_options["benchmark"],
    benchmark_regression: bool = cli_options["benchmark_regression"],
    benchmark_regression_threshold: float = cli_options[
        "benchmark_regression_threshold"
    ],
    test_workers: int = cli_options["test_workers"],
    test_timeout: int = cli_options["test_timeout"],
    skip_hooks: bool = cli_options["skip_hooks"],
    create_pr: bool = cli_options["create_pr"],
    ai_agent: bool = cli_options["ai_agent"],
    comprehensive: bool = cli_options["comprehensive"],
    async_mode: bool = cli_options["async_mode"],
    track_progress: bool = cli_options["track_progress"],
    resume_from: str | None = cli_options["resume_from"],
    progress_file: str | None = cli_options["progress_file"],
    experimental_hooks: bool = cli_options["experimental_hooks"],
    enable_pyrefly: bool = cli_options["enable_pyrefly"],
    enable_ty: bool = cli_options["enable_ty"],
    no_git_tags: bool = cli_options["no_git_tags"],
    skip_version_check: bool = cli_options["skip_version_check"],
    start_mcp_server: bool = cli_options["start_mcp_server"],
    stop_mcp_server: bool = cli_options["stop_mcp_server"],
    restart_mcp_server: bool = cli_options["restart_mcp_server"],
    start_websocket_server: bool = cli_options["start_websocket_server"],
    stop_websocket_server: bool = cli_options["stop_websocket_server"],
    restart_websocket_server: bool = cli_options["restart_websocket_server"],
    websocket_port: int = cli_options["websocket_port"],
    watchdog: bool = cli_options["watchdog"],
    monitor: bool = cli_options["monitor"],
    enhanced_monitor: bool = cli_options["enhanced_monitor"],
) -> None:
    options = Options(
        commit=commit,
        interactive=interactive,
        no_config_updates=no_config_updates,
        update_precommit=update_precommit,
        update_docs=update_docs,
        force_update_docs=force_update_docs,
        compress_docs=compress_docs,
        verbose=verbose,
        publish=publish,
        bump=bump,
        clean=clean,
        test=test,
        benchmark=benchmark,
        benchmark_regression=benchmark_regression,
        benchmark_regression_threshold=benchmark_regression_threshold,
        test_workers=test_workers,
        test_timeout=test_timeout,
        skip_hooks=skip_hooks,
        all=all,
        ai_agent=ai_agent,
        comprehensive=comprehensive,
        create_pr=create_pr,
        async_mode=async_mode,
        track_progress=track_progress,
        resume_from=resume_from,
        progress_file=progress_file,
        experimental_hooks=experimental_hooks,
        enable_pyrefly=enable_pyrefly,
        enable_ty=enable_ty,
        no_git_tags=no_git_tags,
        skip_version_check=skip_version_check,
        start_mcp_server=start_mcp_server,
        stop_mcp_server=stop_mcp_server,
        restart_mcp_server=restart_mcp_server,
        start_websocket_server=start_websocket_server,
        stop_websocket_server=stop_websocket_server,
        restart_websocket_server=restart_websocket_server,
        websocket_port=websocket_port,
        watchdog=watchdog,
        monitor=monitor,
        enhanced_monitor=enhanced_monitor,
    )
    
    # Handle server operations first - these are standalone operations
    if start_mcp_server or stop_mcp_server or restart_mcp_server:
        from .mcp.server_core import handle_mcp_server_command
        handle_mcp_server_command(
            start=start_mcp_server,
            stop=stop_mcp_server, 
            restart=restart_mcp_server,
            websocket_port=websocket_port if start_mcp_server or restart_mcp_server else None
        )
        return
    
    if start_websocket_server or stop_websocket_server or restart_websocket_server:
        from .mcp.websocket.server import handle_websocket_server_command
        handle_websocket_server_command(
            start=start_websocket_server,
            stop=stop_websocket_server,
            restart=restart_websocket_server,
            port=websocket_port
        )
        return
    
    if watchdog:
        from .services.server_manager import start_service_watchdog
        start_service_watchdog()
        return
        
    if monitor:
        from .mcp.progress_monitor import run_progress_monitor
        asyncio.run(run_progress_monitor(enable_watchdog=True))
        return
        
    if enhanced_monitor:
        from .mcp.enhanced_progress_monitor import run_enhanced_progress_monitor
        asyncio.run(run_enhanced_progress_monitor())
        return
    
    if ai_agent:
        import os

        os.environ["AI_AGENT"] = "1"
    if interactive:
        from .interactive import launch_interactive_cli

        try:
            from importlib.metadata import version

            pkg_version = version("crackerjack")
        except (ImportError, ModuleNotFoundError):
            pkg_version = "0.19.8"
        launch_interactive_cli(pkg_version)
    else:
        runner = create_crackerjack_runner(console=console)
        if async_mode:
            asyncio.run(runner.process_async(options))
        else:
            runner.process(options)


if __name__ == "__main__":
    app()

from enum import Enum

import typer
from pydantic import BaseModel, field_validator
from rich.console import Console
from crackerjack import create_crackerjack_runner

console = Console(force_terminal=True)
app = typer.Typer(
    help="Crackerjack: Your Python project setup and style enforcement tool."
)


class BumpOption(str, Enum):
    micro = "micro"
    minor = "minor"
    major = "major"

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

    @classmethod
    @field_validator("publish", "bump", mode="before")
    def validate_bump_options(cls, value: str | None) -> BumpOption | None:
        if value is None:
            return None
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
        False, "-u", "--update-precommit", help="Update pre-commit hooks."
    ),
    "verbose": typer.Option(False, "-v", "--verbose", help="Enable verbose output."),
    "publish": typer.Option(
        None,
        "-p",
        "--publish",
        help="Bump version and publish to PyPI (micro, minor, major).",
        case_sensitive=False,
    ),
    "bump": typer.Option(
        None,
        "-b",
        "--bump",
        help="Bump version (micro, minor, major).",
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
        help="Run with `-x -t -p <micro|minor|major> -c` development options).",
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
}


@app.command()
def main(
    commit: bool = cli_options["commit"],
    interactive: bool = cli_options["interactive"],
    no_config_updates: bool = cli_options["no_config_updates"],
    update_precommit: bool = cli_options["update_precommit"],
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
) -> None:
    options = Options(
        commit=commit,
        interactive=interactive,
        no_config_updates=no_config_updates,
        update_precommit=update_precommit,
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
        create_pr=create_pr,
    )
    if ai_agent:
        import os

        os.environ["AI_AGENT"] = "1"
    if interactive:
        from crackerjack.interactive import launch_interactive_cli

        try:
            from importlib.metadata import version

            pkg_version = version("crackerjack")
        except (ImportError, ModuleNotFoundError):
            pkg_version = "0.19.8"
        launch_interactive_cli(pkg_version)
    else:
        runner = create_crackerjack_runner(console=console)
        runner.process(options)


if __name__ == "__main__":
    app()

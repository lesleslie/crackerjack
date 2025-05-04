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
    doc: bool = False
    no_config_updates: bool = False
    publish: BumpOption | None = None
    bump: BumpOption | None = None
    verbose: bool = False
    update_precommit: bool = False
    clean: bool = False
    test: bool = False
    all: BumpOption | None = None
    ai_agent: bool = False
    create_pr: bool = False

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
        False, "-i", "--interactive", help="Run pre-commit hooks interactively."
    ),
    "doc": typer.Option(False, "-d", "--doc", help="Generate documentation."),
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
        help="Remove docstrings, line comments, and unnecessary whitespace.",
    ),
    "test": typer.Option(False, "-t", "--test", help="Run tests."),
    "all": typer.Option(
        None,
        "-a",
        "--all",
        help="Run with `-x -t -p <micro|minor|major> -c` development options).",
        case_sensitive=False,
    ),
    "create_pr": typer.Option(
        False,
        "-r",
        "--pr",
        help="Create a pull request to the upstream repository.",
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
    doc: bool = cli_options["doc"],
    no_config_updates: bool = cli_options["no_config_updates"],
    update_precommit: bool = cli_options["update_precommit"],
    verbose: bool = cli_options["verbose"],
    publish: BumpOption | None = cli_options["publish"],
    all: BumpOption | None = cli_options["all"],
    bump: BumpOption | None = cli_options["bump"],
    clean: bool = cli_options["clean"],
    test: bool = cli_options["test"],
    create_pr: bool = cli_options["create_pr"],
    ai_agent: bool = cli_options["ai_agent"],
) -> None:
    options = Options(
        commit=commit,
        interactive=interactive,
        doc=doc,
        no_config_updates=no_config_updates,
        update_precommit=update_precommit,
        verbose=verbose,
        publish=publish,
        bump=bump,
        clean=clean,
        test=test,
        all=all,
        ai_agent=ai_agent,
        create_pr=create_pr,
    )

    if ai_agent:
        import os

        os.environ["AI_AGENT"] = "1"

    runner = create_crackerjack_runner(console=console)
    runner.process(options)


if __name__ == "__main__":
    app()

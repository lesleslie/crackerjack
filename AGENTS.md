# Repository Guidelines

## Project Structure & Module Organization

Crackerjack's agent runtime lives in `crackerjack/`, housing orchestrator logic, agent classes, and CLI entrypoints. Automation scripts reside in `scripts/` and `tools/`, while documentation is maintained in `docs/`, `README.md`, and `CLAUDE.md`. Tests mirror the package in `tests/`, with documentation fixtures under `test_docs_site/`, and integration examples available in `examples/` alongside `example.mcp.json`.

## Build, Test, and Development Commands

`uv sync --group dev` installs runtime, testing, and MCP dependencies. `uv run pre-commit run --all-files` enforces formatting, linting, and security hooks before pushing. `/crackerjack:run --debug` executes the full multi-agent workflow locally and should precede manual Python invocations. `uv run python -m crackerjack --help` enumerates CLI entrypoints when adjusting interface behavior.

## Coding Style & Naming Conventions

Target Python 3.13 with 4-space indentation and explicit type annotations. Keep identifiers concise yet descriptive, and maintain Ruff's cognitive complexity guidance of ≤15. Run `uv run ruff check --fix` for linting and `uv run ruff format` to enforce 88-character lines and import order. Name tests `test_<feature>.py`, fixtures descriptively, and finish agent class names with `*Agent`.

## Testing Guidelines

Execute `uv run pytest` for the default suite, adding `--maxfail=1` during iteration. Follow with `/crackerjack:run` to confirm the agent loop converges. Preserve ≥42% coverage by reviewing `coverage.json` or `htmlcov/` and expanding tests when metrics drop. Use markers `chaos`, `ai_generated`, and `breakthrough` to isolate expensive scenarios, and share fixtures via `tests/conftest.py`.

## Commit & Pull Request Guidelines

Adopt the `type(scope): summary` message pattern (e.g., `fix(agents): guard iteration retry`). Keep commits tight, reference tickets or MCP jobs, and note agent or workflow impacts. PRs should state motivation, implementation notes, validation evidence (commands run, screenshots for docs/UI changes), link issues, and flag follow-up tasks.

## Agent-Aware Workflow

Rely on MCP tooling where possible: kick off quality sweeps with `/crackerjack:run`, monitor progress through `get_job_progress`, and verify readiness with `/crackerjack:status`. Update `.mcp.json` whenever wiring new servers, document fresh agent capabilities here, and keep structured outputs (`test-results.xml`, `coverage.json`) current after major changes.

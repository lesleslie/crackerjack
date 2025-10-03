______________________________________________________________________

## id: 01K6K1ATWK012TB0ND8A2YZD8F

# Repository Guidelines

## Project Structure & Module Organization

Crackerjack's core package lives under `crackerjack/`, where agents, the orchestrator, and CLI entrypoints are defined. Documentation and public guides sit in `docs/`, `README.md`, and `CLAUDE.md`, while reusable automation lives in `scripts/` and `tools/`. Tests mirror the package layout in `tests/` and leverage `test_docs_site/` for documentation fixtures. Use `examples/` and `example.mcp.json` when demonstrating integrations, and keep contributions aligned with the DRY/KISS/YAGNI philosophy.

## Build, Test, and Development Commands

- `uv sync --group dev` installs runtime, testing, and MCP dependencies.
- `uv run pre-commit run --all-files` validates formatting, linting, and security hooks before you push.
- `/crackerjack:run --debug` executes the full agent workflow locally; prefer this over raw `python -m` invocations.
- `uv run python -m crackerjack --help` observes CLI entrypoints when adjusting commands or docs.

## Coding Style & Naming Conventions

Target Python 3.13 with 4-space indentation, full type annotations, and descriptive but concise identifiers. `ruff` owns style, import order, and formatting (`uv run ruff check --fix` and `uv run ruff format`), holding line length to 88 and cognitive complexity to ≤15. Favor self-documenting code; reserve comments for intent or non-obvious trade-offs. Name test files `test_<feature>.py`, fixtures descriptively, and end agent classes with `*Agent` to match the architecture.

## Testing Guidelines

Run `uv run pytest` for the default suite and add `--maxfail=1` while iterating. Follow up with `/crackerjack:run` to ensure the multi-agent iteration protocol still converges. Maintain ≥42% coverage; audit `coverage.json` or `htmlcov/` when adding modules and expand tests if thresholds slip. Leverage existing markers (`chaos`, `ai_generated`, `breakthrough`) to isolate heavyweight scenarios, and keep shared fixtures in `tests/conftest.py`.

## Commit & Pull Request Guidelines

Adopt the `type(scope): summary` convention from history—examples include `fix(agents): guard iteration retry` or `test(tests): update scenarios`. Keep commits tightly scoped, reference tickets or MCP jobs when relevant, and note any agent or workflow impacts. Pull requests need a concise motivation, implementation notes, and validation proof (commands run, test outcomes, screenshots for docs/UI tweaks). Link issues and flag required follow-up work.

## Agent-Aware Workflow

Favor MCP tooling in day-to-day work: start quality sweeps with `/crackerjack:run`, monitor progress via `get_job_progress`, and sanity-check the environment with `/crackerjack:status`. Document new agents or capabilities here, update `.mcp.json` when wiring servers, and ensure structured outputs (`test-results.xml`, `coverage.json`) stay current after changes.

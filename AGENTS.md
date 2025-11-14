# Repository Guidelines

## Project Structure & Module Organization

- Core runtime and CLI entrypoints live in `crackerjack/`; agent orchestration, prompts, and CLI commands sit in subpackages noted by their role.
- Automation helpers are split between `scripts/` and `tools/` for reproducible workflows, with shared fixtures living in `tests/conftest.py`.
- Documentation resides in `docs/`, `README.md`, and `CLAUDE.md`; additional examples and mock configuration are under `examples/` and `example.mcp.json`.
- Tests mirror the package layout in `tests/`, while the documentation site fixtures live in `test_docs_site/` for isolated snapshot coverage.

## Build, Test, and Development Commands

- `uv sync --group dev`: install runtime, testing, and MCP dependencies into the active environment.
- `/crackerjack:run --debug`: execute the end-to-end multi-agent workflow locally before running isolated modules.
- `uv run python -m crackerjack --help`: list available CLI entrypoints when adjusting invocation behavior.
- `uv run pytest --maxfail=1`: run the default test suite, stopping on the first failure during iteration.
- `uv run ruff check --fix && uv run ruff format`: apply lint fixes and enforce formatting, including import ordering.

## Coding Style & Naming Conventions

- Target Python 3.13 with 4-space indentation; annotate public functions and complex helpers with explicit types.
- Keep identifiers concise yet descriptive, using `*Agent` suffixes for agent classes and `test_<feature>.py` naming for tests.
- Respect Ruff complexity guidance (≤15) and rely on `ruff check` to guard style, security, and dead code concerns.

## Testing Guidelines

- Prefer `pytest` fixtures from `tests/conftest.py` and reuse documentation assets from `test_docs_site/` when validating rendered output.
- Work toward 42% milestone (current: 21.6%, baseline: 19.6%); consult `coverage.json` or `htmlcov/` after changes. See [COVERAGE_POLICY.md](<./COVERAGE_POLICY.md>).
- Use markers `chaos`, `ai_generated`, and `breakthrough` to isolate expensive suites; document new fixtures and markers alongside the relevant tests.

## Commit & Pull Request Guidelines

- Write commits as `type(scope): summary`, referencing tickets or MCP jobs where relevant and grouping related changes tightly.
- PRs should state motivation, implementation notes, validation evidence (commands run, screenshots for docs/UI tweaks), linked issues, and follow-up tasks.
- Run `uv run pre-commit run --all-files` before opening PRs to align formatting, linting, and security expectations.

## Agent-Aware Workflow

- Trigger quality sweeps with `/crackerjack:run`, monitor using `get_job_progress`, and verify readiness via `/crackerjack:status`.
- Update `.mcp.json` when wiring new servers, and document fresh agent capabilities in `docs/` plus the MCP manifest.
- Keep structured outputs (`test-results.xml`, `coverage.json`) current to support downstream dashboards and release gates.

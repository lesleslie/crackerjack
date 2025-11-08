# Crackerjack Documentation

Concise, current documentation for working with Crackerjack. Legacy plans and deep-dive writeups have been archived to keep this focused and fresh. For full project introduction and narrative, see `README.md` at the repository root.

— Last updated: 2025-11-07

## Quick Start

Install tooling and list CLI entrypoints:

```bash
uv sync --group dev
uv run python -m crackerjack --help
```

Run the end-to-end multi-agent workflow locally:

```bash
/crackerjack:run --debug
```

Common development flows:

```bash
# Lint and format
uv run ruff check --fix && uv run ruff format

# Run tests
uv run pytest --maxfail=1
```

## Project Structure

- `crackerjack/` — Core runtime and CLI entrypoints (agents, prompts, orchestration).
- `scripts/` and `tools/` — Automation helpers; fixtures in `tests/conftest.py`.
- `docs/` — Current documentation. Historical implementation docs archived in `docs/archive/`.
- `examples/`, `example.mcp.json` — Examples and mock configuration.
- `test_docs_site/` — Fixtures for docs site snapshots (isolated from this docs/).

## Coding Standards

- Python 3.13, 4-space indentation.
- Add explicit types for public functions and non-trivial helpers.
- Naming: use `*Agent` for agent classes; tests as `tests/test_<feature>.py`.
- Keep complexity reasonable (Ruff guidance ≤ 15). Use `ruff check` to guard style, security, and dead code.

## Testing

- Prefer shared fixtures from `tests/conftest.py`.
- Reuse documentation assets from `test_docs_site/` for rendered output validation.
- Maintain ≥ 42% coverage; consult `coverage.json` or `htmlcov/` after significant changes.
- Use markers `chaos`, `ai_generated`, `breakthrough` for expensive suites and document new fixtures/markers in tests.

## Agent-Aware Workflow

- Trigger quality sweeps: `/crackerjack:run`.
- Monitor progress: `get_job_progress`.
- Verify readiness: `/crackerjack:status`.
- Update `.mcp.json` for new servers and document new capabilities in `docs/` and the MCP manifest.

## Key References

- Root overview and usage: `README.md`
- Agent/developer guide: `CLAUDE.md`
- Security policy: `SECURITY.md`
- Coding rules and constraints: `RULES.md`
- Model-specific notes: `GEMINI.md`, `QWEN.md`
- Changelog and releases: `CHANGELOG.md`

## Migration Notes

- 0.41.0 — Dependency groups modernization: removed self-reference from `[dependency-groups]` (no functional impact; improves UV/PEP 735 compatibility).

## Contributing

- Commits: `type(scope): summary` with related tickets or MCP jobs.
- PRs include motivation, implementation notes, validation evidence (commands run, screenshots for docs/UI), linked issues, and follow-ups.
- Run `uv run pre-commit run --all-files` before opening PRs.

## Documentation Organization

- **Active Docs**: This file contains current, actionable information for development.
- **Archived Docs**: Historical implementation plans and phase completions in `docs/archive/`.
- **Root Docs**: `README.md`, `CLAUDE.md`, `SECURITY.md` remain the source of truth for detailed guidance.
- **Package READMEs**: Each crackerjack/ subdirectory has a README explaining its purpose and architecture.

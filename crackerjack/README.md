> Crackerjack Docs: [Main](../README.md) | [Crackerjack Package](./README.md)

# Crackerjack Package

Core runtime and CLI entrypoints for the Crackerjack platform. Agent orchestration, prompts, and command implementations live in subpackages named for their role.

- Entry points: `uv run python -m crackerjack --help`
- End‑to‑end run: `/crackerjack:run --debug`
- Tests mirror structure under `tests/`

See project root `README.md` and `docs/` for details.

## Related

- [Main Documentation](../README.md) - Project overview and getting started
- [CLAUDE.md](../CLAUDE.md) - Architecture and development guidelines
- [Agents](./agents/README.md) - AI agent system
- [CLI](./cli/README.md) - Command-line interface
- [MCP](./mcp/README.md) - Model Context Protocol server

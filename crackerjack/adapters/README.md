# Adapters

Interfaces and adapters to external tools/services or subsystems. Each adapter follows ACB-style patterns with typed settings, async initialization, and standardized results.

## Index

- [AI](./ai/README.md) — Claude-powered code fixing and AI helpers
- [Complexity](./complexity/README.md) — Code complexity analysis (Complexipy)
- [Format](./format/README.md) — Code and docs formatting (Ruff, Mdformat)
- [Lint](./lint/README.md) — Spelling and simple linters (Codespell)
- [LSP](./lsp/README.md) — Rust tools with LSP (Zuban, Skylos)
- [Refactor](./refactor/README.md) — Modernization and dead-code (Refurb, Creosote, Skylos)
- [SAST](./sast/README.md) — Static application security testing (Semgrep, Bandit, Pyscn)
- [Security](./security/README.md) — Secret leak prevention and credential detection (Gitleaks)
- [Type](./type/README.md) — Static type checking (Zuban, Pyrefly, Ty)
- [Utility](./utility/README.md) — Small config-driven checks (EOF newline, regex, size)

See `crackerjack/models/qa_config.py` and `crackerjack/models/qa_results.py` for configuration and result schemas used across adapters.

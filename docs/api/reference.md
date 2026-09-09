---
status: active
role: canonical
date: 2026-07-17
last_reviewed: 2026-07-17
superseded_by: null
blocks_on: []
topic: mcp-design
---

# API Reference

Complete API documentation for Crackerjack.

## Protocols

<details>
<summary>Core Protocols</summary>

### ConsoleInterface

Console output protocol with methods for printing, progress bars, and status updates.

### TestManagerProtocol

Test execution protocol managing pytest integration and coverage tracking.

### AgentTrackerProtocol

Agent invocation tracking for skills metrics and recommendations.

</details>

## Services

<details>
<summary>Service Layer</summary>

### VectorStore

Semantic vector storage for AI-powered code search and fix strategies.

**Key Features**:

- SQLite-based vector storage
- FAISS-like similarity search
- Temporary database support

### SessionCoordinator

Session lifecycle management coordinating quality gates, tests, and cleanup.

**Key Features**:

- Lock file management
- Cleanup handler registration
- Thread-safe operations

### DocumentationGenerator

Markdown documentation generation from docstrings and templates.

**Key Features**:

- Template-based rendering
- Docstring extraction
- Multi-format support

</details>

## Managers

<details>
<summary>Manager Layer</summary>

### HookManager

Orchestrates quality tool execution (fast → comprehensive).

### TestManager

Manages pytest execution with parallel workers and coverage tracking.

### WorkflowOrchestrator

Coordinates multi-phase workflows with dependency management.

</details>

## Language Adapters

Language adapters extend Crackerjack to non-Python projects. All four
ship under the `crackerjack.language_adapters` entry-point group declared
in `pyproject.toml` (`PythonAdapter`, `SwiftAdapter`, `KotlinAdapter`,
`WebAdapter`). Each implements `LanguageAdapterBase` from
`crackerjack/adapters/base.py`.

### `WebAdapter`

```python
from crackerjack.adapters.web import WebAdapter, web_enabled
```

| Member | Signature | Notes |
| --- | --- | --- |
| `WebAdapter.name` | `str` (class attribute) | Always `"web"`. |
| `WebAdapter.detect(project_root)` | `Path -> bool` | `True` iff `web_enabled(project_root)` is `True`. |
| `WebAdapter.capabilities(project_root)` | `Path -> Capabilities` | Returns four `Hook`s: `web.stylelint`, `web.eslint`, `web.tsc` (with `tsc --noEmit`, 600 s timeout), `web.html_validate`. `version_source=None`, `has_lifecycle=False` (CLI-only Phase 4 surface). |
| `web_enabled(project_root)` | `Path -> bool` | Returns `True` when `package.json` exists at root, **or** `pyproject.toml` has `[tool.crackerjack.web] enabled = true`. |
| `package_json_present(project_root)` | `Path -> bool` | Helper that reports whether `package.json` is at the root. |
| `web_hooks(project_root)` | `Path -> tuple[Hook, ...]` | Resolves the four Web hooks. Raises `crackerjack.adapters.web.hooks.WebHookError` when a CLI tool cannot be located. |

### `format_template`

```python
from crackerjack.adapters.web.jinja_formatter import format_template
```

| Parameter | Type | Default | Notes |
| --- | --- | --- | --- |
| `source` | `str` | — | Raw Jinja source. |
| `delimiters` | `Mapping[str, str] \| None` | `None` (`DEFAULT_DELIMITERS`) | Six-key mapping: `block_start`, `block_end`, `variable_start`, `variable_end`, `comment_start`, `comment_end`. When omitted, the project's `[tool.crackerjack.jinja]` table (if any) is **not** consulted; pass the loaded mapping explicitly. |

Returns `str`. Tier 1 canonicalization only:

1. Trailing newline at EOF.
1. Strip trailing whitespace from every line.
1. Preserve `{%-` / `-%}` / `{{-` / `-}}` whitespace markers (untouched by construction).

The function calls `jinja2.Environment.lex(source)` as a syntax-validation
gate. On `TemplateSyntaxError`, or when the configured delimiters
mismatch the source's markers, the original `source` is returned
unchanged (with a `logger.warning`). Tier 2 normalization (`normalize`
parameter) is **not** present in Rev 1 — deferred to a future phase.

### Related constants

- `JINJA_SUFFIXES = frozenset({".html", ".j2", ".jinja"})` —
  extensions considered "Jinja" by the MCP `format_jinja_templates` tool.
- `DEFAULT_DELIMITERS` — the standard six-key delimiter mapping; pass
  `delimiters=DEFAULT_DELIMITERS` to `format_template` to opt out of
  per-project overrides.

### MCP exposure

Both surfaces are also exposed as MCP tools:

- `check_web_lint(project_root) -> dict` — read-only; returns
  `{adapter: "web", enabled: bool, hooks: [{name, cli_command, timeout_seconds}]}`.
  See [`MCP_TOOLS_SPECIFICATION.md` §3.6](../MCP_TOOLS_SPECIFICATION.md).
- `format_jinja_templates(projects, dry_run=True) -> dict` — mutation;
  `dry_run` defaults to `True`. Returns `{files, errors, mode}`.

## See Also

- [Protocol-Based Design](../architecture/protocols.md)

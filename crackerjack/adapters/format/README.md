> Crackerjack Docs: [Main](../../../README.md) | [Adapters](../README.md) | [Format](./README.md)

# Format Adapter

Formatting for Python and Markdown with fast tooling and structured results. Ruff also supports lint mode; see mode selection below.

## Overview

- Unified interface for code and docs formatting
- Safe check-only modes and optional auto-fix
- JSON parsing where supported (Ruff check)

## Built-in Implementations

| Module | Description | Mode(s) | Status |
| ------ | ----------- | ------- | ------ |
| `ruff.py` | Fast Python linter/formatter | `check`, `format` | Stable |
| `mdformat.py` | Opinionated Markdown formatter | check-only or fix | Stable |

## Ruff Settings

Settings class: `RuffSettings`

- `mode` ("check" or "format")
- `fix_enabled` (bool; auto-fix in check; apply format in format mode)
- `select_rules` / `ignore_rules` (list[str])
- `line_length` (int; format mode)
- `preview` (bool)

Example:

```python
from pathlib import Path
from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings


async def run_ruff() -> None:
    adapter = RuffAdapter(settings=RuffSettings(mode="check", fix_enabled=True))
    await adapter.init()
    result = await adapter.check(files=[Path("src/")])
```

## Mdformat Settings

Settings class: `MdformatSettings`

- `fix_enabled` (bool; write changes)
- `line_length` (int)
- `wrap_mode` ("keep", "no", or number)

Example:

```python
from pathlib import Path
from crackerjack.adapters.format.mdformat import MdformatAdapter, MdformatSettings


async def format_md() -> None:
    adapter = MdformatAdapter(settings=MdformatSettings(fix_enabled=False))
    await adapter.init()
    result = await adapter.check(files=[Path("README.md"), Path("docs/")])
```

## Notes

- Ruff lint mode emits JSON for precise diagnostics; format mode reports files needing changes
- Combine with pre-commit or run via `python -m crackerjack` as part of workflows

## Related

- [Lint](../lint/README.md) — Codespell for spelling and text issues
- [Type](../type/README.md) — Type safety complements style enforcement

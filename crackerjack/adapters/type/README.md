> Crackerjack Docs: [Main](<../../../README.md>) | [Adapters](<../README.md>) | [Type](<./README.md>)

# Type Adapters

Static type checking with fast Rust-backed options and experimental tools.

## Overview

- Ultra-fast checks with Zuban (Rust), supports incremental caching and LSP
- Additional checkers (Pyrefly, Ty) for experimentation
- JSON output parsing where available for precise diagnostics

## Built-in Implementations

| Module | Description | Status |
| ------ | ----------- | ------ |
| `zuban.py` | Rust-based type checking, 20–200x faster than traditional tools | Stable |
| `pyrefly.py` | Python type checker with incremental mode | Experimental |
| `ty.py` | Python type verification tooling | Experimental |

## Zuban Settings

Settings class: `ZubanSettings`

- `strict_mode` (bool)
- `ignore_missing_imports` (bool)
- `follow_imports` ("normal"/"skip"/"silent")
- `incremental` (bool)
- `cache_dir` (Path)
- `warn_unused_ignores` (bool)

Example:

```python
from pathlib import Path
from crackerjack.adapters.type.zuban import ZubanAdapter, ZubanSettings


async def run_zuban() -> None:
    adapter = ZubanAdapter(settings=ZubanSettings(strict_mode=True, incremental=True))
    await adapter.init()
    result = await adapter.check(files=[Path("src/")])
```

## LSP Integration

For editor-like performance, see [LSP adapters](<../lsp/README.md>) to run Zuban diagnostics via LSP with automatic CLI fallback.

## Related

- [AI](<../ai/README.md>) — AI-assisted fixes frequently target type issues
- [Format](<../format/README.md>) — Consistent style improves type readability

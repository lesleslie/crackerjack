> Crackerjack Docs: [Main](<../../../README.md>) | [Adapters](<../README.md>) | [LSP](<./README.md>)

# LSP Adapters

Rust-backed tools with Language Server Protocol integration for fast, incremental diagnostics.

## Overview

- Shared base (`_base.py`) defines `Issue`/`ToolResult` and adapter protocol
- Optional LSP paths for low-latency diagnostics, with CLI fallback
- Useful for continuous analysis in editors and orchestrated runs

## Built-in Implementations

| Module | Description | LSP | Status |
| ------ | ----------- | --- | ------ |
| `zuban.py` | Ultra-fast Python type checking with LSP and CLI fallback | Yes | Stable |
| `skylos.py` | Dead code detection with JSON/text parsing | N/A | Stable |

Support modules:

- `_client.py` — Optimized Zuban LSP client wrapper
- `_manager.py` — LSP process and workspace lifecycle helpers
- `_base.py` — Common protocol types and base adapter

## Zuban (LSP) Usage

```python
from pathlib import Path
from crackerjack.adapters.lsp.zuban import ZubanAdapter


async def typecheck_with_lsp(ctx) -> None:
    adapter = ZubanAdapter(context=ctx, strict_mode=True, use_lsp=True)
    result = await adapter.check_with_lsp_or_fallback([Path("src/")])
    print("errors:", result.error_count, "warnings:", result.warning_count)
```

CLI helpers are available to manage Zuban LSP via `python -m crackerjack` options (start/stop/restart).

## Notes

- LSP improves iteration speed; adapters transparently fall back to CLI
- Some Zuban builds may have TOML parsing issues; health checks guard usage

## Related

- [Type](<../type/README.md>) — Non-LSP type checkers and settings
- [Refactor](<../refactor/README.md>) — Skylos-based dead code detection

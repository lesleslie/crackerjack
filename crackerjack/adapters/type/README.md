> Crackerjack Docs: [Main](../../../README.md) | [Adapters](../README.md) | [Type](./README.md)

# Type Adapters

Static type checking with a stable Rust-backed default and two opt-in experimental tools.

## Overview

- Zuban is the default comprehensive checker and remains the safest baseline
- Ty is opt-in and can apply limited native fixes with `ty check --fix`
- Pyrefly is opt-in and speaks JSON with `pyrefly check --output-format=json`

## Built-in Implementations

| Module | Description | Status |
| ------ | ----------- | ------ |
| `zuban.py` | Rust-based type checking, current default baseline | Stable |
| `pyrefly.py` | Python type checker with JSON diagnostics, baseline/suppress support | Experimental |
| `ty.py` | Python type checker with concise output and native fix support | Experimental |

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

For editor-like performance, see [LSP adapters](../lsp/README.md) to run Zuban diagnostics via LSP with automatic CLI fallback.

## Ty Settings

Settings class: `TySettings`

- `output_format` (`concise`, `full`, `gitlab`, `github`, `junit`)
- `fix_enabled` (bool)
- `add_ignore_enabled` (bool)
- `no_progress` (bool)

Ty is opt-in only and is best used as a canary or AI-fix pre-pass.
When enabled in comprehensive mode, Ty stays additive: it does not replace Zuban as the default baseline.

## Pyrefly Settings

Settings class: `PyreflySettings`

- `output_format` (`json`, `min-text`, `full-text`, `github`, `omit-errors`)
- `summary` (`none` by default)
- `no_progress_bar` (bool)
- `baseline_file` (Path)
- `update_baseline` (bool)
- `suppress_errors` (bool)
- `remove_unused_ignores` (bool)

Pyrefly is opt-in only and works well when you want JSON diagnostics plus baselines or suppressions.
When enabled in comprehensive mode, Pyrefly is additive and does not replace Zuban as the default baseline.

## AI-Fix Workflow Notes

- `ty` can run a native `--fix` pre-pass before AI analysis.
- `pyrefly` is used for diagnostics, suppressions, and baselines rather than native code rewriting.
- `zuban` remains the default type-checking baseline for comprehensive runs.

## Related

- [AI](../ai/README.md) — AI-assisted fixes frequently target type issues
- [Format](../format/README.md) — Consistent style improves type readability

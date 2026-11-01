> Crackerjack Docs: [Main](../../../README.md) | [Adapters](../README.md) | [Type](./README.md)

# Type Adapters

Static type checking with a stable Rust-backed default and one opt-in experimental tool.

## Overview

- Ty is the active default type checker (active by default via `settings.hooks.enable_ty`)
- Pyrefly is opt-in and speaks JSON with `pyrefly check --output-format=json`

## Built-in Implementations

| Module | Description | Status |
| ------ | ----------- | ------ |
| `pyrefly.py` | Python type checker with JSON diagnostics, baseline/suppress support | Experimental |
| `ty_adapter.py` | Python type checker with concise output and native fix support | Experimental |

## Ty Settings

Settings class: `TySettings`

- `output_format` (`concise`, `full`, `gitlab`, `github`, `junit`)
- `fix_enabled` (bool)
- `add_ignore_enabled` (bool)
- `no_progress` (bool)

Ty is the active default. It runs automatically in comprehensive mode whenever `settings.hooks.enable_ty` is true (default) and is best used as the primary type checker.

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
When enabled in comprehensive mode, Pyrefly is additive and does not replace Ty as the default baseline.

## AI-Fix Workflow Notes

- `ty` can run a native `--fix` pre-pass before AI analysis.
- `pyrefly` is used for diagnostics, suppressions, and baselines rather than native code rewriting.
- `ty` is the default type-checking baseline for comprehensive runs (active by default).

## Related

- [AI](../ai/README.md) — AI-assisted fixes frequently target type issues
- [Format](../format/README.md) — Consistent style improves type readability

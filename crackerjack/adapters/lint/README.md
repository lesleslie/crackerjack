> Crackerjack Docs: [Main](<../../../README.md>) | [Adapters](<../README.md>) | [Lint](<./README.md>)

# Lint Adapter

Lightweight linters focused on spelling and text quality. Ruff lint is available under the Format adapter’s “check” mode.

## Overview

- Catch common spelling mistakes in code, docs, and filenames
- Optional write-back for automatic typo fixes
- Ignore lists and skip rules for noisy terms

## Built-in Implementation

| Module | Description | Status |
| ------ | ----------- | ------ |
| `codespell.py` | Spelling and typo detection with optional auto-fix | Stable |

## Codespell Settings

Settings class: `CodespellSettings`

- `fix_enabled` (bool; write changes)
- `skip_hidden` (bool)
- `ignore_words` (list[str]) and/or `ignore_words_file` (Path)
- `check_filenames` (bool)
- `quiet_level` (int; default 2)

## Basic Usage

```python
from pathlib import Path
from crackerjack.adapters.lint.codespell import CodespellAdapter, CodespellSettings


async def run_codespell() -> None:
    adapter = CodespellAdapter(
        settings=CodespellSettings(fix_enabled=False, ignore_words=["acb", "pydantic"])
    )
    await adapter.init()
    result = await adapter.check(files=[Path("src/"), Path("docs/")])
```

## Notes

- Use a shared `ignore_words_file` to standardize noisy tokens across repos
- For Ruff linting, see [Format](<../format/README.md>)

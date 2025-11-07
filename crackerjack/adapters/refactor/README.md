> Crackerjack Docs: [Main](<../../../README.md>) | [Adapters](<../README.md>) | [Refactor](<./README.md>)

# Refactor Adapters

Modernization and dead-code tooling to simplify code and reduce risk.

## Overview

- Suggest idiomatic patterns and cleanups (Refurb)
- Identify unused dependencies (Creosote)
- Detect dead code for deletion (Skylos)

## Built-in Implementations

| Module | Description | Status |
| ------ | ----------- | ------ |
| `refurb.py` | Refactoring suggestions for modern Python idioms | Stable |
| `creosote.py` | Detects unused dependencies in `pyproject.toml`/`requirements*.txt` | Stable |
| `skylos.py` | Dead code detection (text/JSON parsing) | Stable |

## Examples

Refurb:

```python
from pathlib import Path
from crackerjack.adapters.refactor.refurb import RefurbAdapter, RefurbSettings


async def suggest_refactors() -> None:
    adapter = RefurbAdapter(settings=RefurbSettings(explain=True))
    await adapter.init()
    result = await adapter.check(files=[Path("src/")])
```

Creosote:

```python
from pathlib import Path
from crackerjack.adapters.refactor.creosote import CreosoteAdapter, CreosoteSettings


async def find_unused_deps() -> None:
    adapter = CreosoteAdapter(
        settings=CreosoteSettings(config_file=Path("pyproject.toml"))
    )
    await adapter.init()
    result = await adapter.check()
```

## Notes

- Treat Refurb suggestions as warnings; human review recommended
- Exclude dev/build tools in Creosote to avoid false positives

## Related

- [Complexity](<../complexity/README.md>) — Use complexity reports to target refactors
- [Format](<../format/README.md>) — Formatting changes often enable simpler refactors

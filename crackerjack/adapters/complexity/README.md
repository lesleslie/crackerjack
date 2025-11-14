> Crackerjack Docs: [Main](../../../README.md) | [Adapters](../README.md) | [Complexity](./README.md)

# Complexity Adapter

Code complexity analysis with thresholds and structured results. Uses a standardized interface built on the QA adapter base.

## Overview

- Reports cyclomatic and cognitive complexity, maintainability index, and LOC
- Threshold-driven warnings/errors for actionable feedback
- JSON parsing for precise per-function metrics

## Built-in Implementation

| Module | Description | Status |
| ------ | ----------- | ------ |
| `complexipy.py` | Complexity analysis with configurable thresholds and metrics | Stable |

## Settings

Settings class: `ComplexipySettings`

- `max_complexity` (int; default 15)
- `include_cognitive` (bool; default True)
- `include_maintainability` (bool; default True)
- `sort_by` (str; `complexity`/`cognitive`/`name`)

## Basic Usage

```python
from pathlib import Path
from crackerjack.adapters.complexity.complexipy import (
    ComplexipyAdapter,
    ComplexipySettings,
)


async def analyze_complexity() -> None:
    adapter = ComplexipyAdapter(settings=ComplexipySettings(max_complexity=15))
    await adapter.init()
    result = await adapter.check(files=[Path("src/")])
    print(result.status, result.issues_found)
```

## Tips

- Start with `max_complexity=15` (Crackerjack standard), tighten as code matures
- Use results to prioritize refactors (high complexity or low maintainability)

## Related

- [Refactor](../refactor/README.md) — Tools to modernize and reduce complexity
- [Format](../format/README.md) — Formatting often improves readability and maintainability

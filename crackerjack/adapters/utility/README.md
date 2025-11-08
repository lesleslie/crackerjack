> Crackerjack Docs: [Main](<../../../README.md>) | [Adapters](<../README.md>) | [Utility](<./README.md>)

# Utility Adapter

Configuration-driven utility checks for small, high-signal fixes without external tools.

## Overview

- Enforce EOF newlines, trim trailing whitespace, validate YAML/TOML/JSON
- Simple file-size limits and dependency lock checks
- Typed settings and consistent QA results

## Supported Check Types

- `TEXT_PATTERN` — Regex search (e.g., trailing whitespace), optional auto-fix
- `EOF_NEWLINE` — Ensure files end with a newline
- `SYNTAX_VALIDATION` — Parse `yaml`/`toml`/`json` safely
- `SIZE_CHECK` — Enforce `max_size_bytes`
- `DEPENDENCY_LOCK` — Run lock command and verify success

## Basic Usage

```python
from pathlib import Path
from crackerjack.adapters.utility.checks import (
    UtilityCheckAdapter,
    UtilityCheckSettings,
    UtilityCheckType,
)


async def enforce_whitespace() -> None:
    settings = UtilityCheckSettings(
        check_type=UtilityCheckType.TEXT_PATTERN,
        pattern=r"\s+$",
        auto_fix=True,
    )
    adapter = UtilityCheckAdapter(settings=settings)
    await adapter.init()
    result = await adapter.check(files=[Path("src/file.py")])
```

## Tips

- Prefer `CompiledPatternCache`-friendly regexes; settings validate patterns
- Target specific file globs via `QACheckConfig.file_patterns`

## Related

- [Format](<../format/README.md>) — For comprehensive Python/Markdown formatting
- [Lint](<../lint/README.md>) — Codespell for typos and naming issues

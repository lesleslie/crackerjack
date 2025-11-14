> Crackerjack Docs: [Main](../../../README.md) | [Adapters](../README.md) | [AI](./README.md)

# AI Adapter

Claude-powered code fixing and AI helpers following ACB adapter patterns. The built-in adapter focuses on safe, validated code fixes using Anthropic’s Claude models.

## Overview

- Secure AI integration: validates generated code (regex + AST), sanitizes errors, enforces file-size and key format limits
- ACB-style initialization: async `init()`, typed settings, metadata, and DI via `depends`
- Designed to fit end-to-end QA flows and orchestrations

## Built-in Implementation

| Module | Description | Status |
| ------ | ----------- | ------ |
| `claude.py` | Claude AI code fixer with robust validation and retry logic | Stable |

## Settings

Settings class: `ClaudeCodeFixerSettings`

- `anthropic_api_key` (SecretStr, required; must start with `sk-ant-`)
- `model` (str; default `claude-sonnet-4-5-20250929`)
- `max_tokens` (int; default 4096)
- `temperature` (float; default 0.1)
- `confidence_threshold` (float; default 0.7)
- `max_retries` (int; default 3)
- `max_file_size_bytes` (int; default 10MB)

Values are typically sourced from `Config` via `depends.get(Config)` during `init()`.

## Basic Usage

```python
from acb.depends import depends
from crackerjack.adapters.ai.claude import ClaudeCodeFixer


async def fix_with_ai() -> None:
    fixer = ClaudeCodeFixer()
    await fixer.init()

    result = await fixer.fix_code_issue(
        file_path="path/to/file.py",
        issue_description="Line too long",
        code_context="x = 1\n",
        fix_type="ruff",
    )

    if result["success"]:
        print("Confidence:", result["confidence"])
        print(result["fixed_code"])
```

## Best Practices

- Keep `temperature` low for predictable refactors
- Gate changes by `confidence_threshold` and validate diffs in CI
- Rotate and scope API keys; never log secrets

## Related

- [Type](../type/README.md) — Type checking that often informs fix prompts
- [Refactor](../refactor/README.md) — Refactoring tools that pair well with AI fixes

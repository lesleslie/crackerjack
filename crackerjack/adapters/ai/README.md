> Crackerjack Docs: [Main](../../../README.md) | [Adapters](../README.md) | [AI](./README.md)

# AI Adapter

AI-powered code fixing helpers following the crackerjack adapter pattern. The built-in adapter focuses on safe, validated code fixes using the `mcp_common.FallbackChain` LLM gateway (defaults to MiniMax → llama_server → ollama).

> **Note**: This README was rewritten 2026-09-09 to drop the obsolete `ClaudeCodeFixer` / `ClaudeCodeFixerSettings` references — those classes lived in the deleted `crackerjack.adapters.ai.claude` module and the pre-2026-08-06 multi-provider AI-fix chain. The current public surface is `BaseCodeFixer`, `FallbackChainCodeFixer`, `BaseCodeFixerSettings`, and `FallbackChainSettings` exported from `crackerjack.adapters.ai`.

## Overview

- Async `init()` lifecycle (inherited from `BaseCodeFixer`)
- Validates generated code (regex + AST), sanitizes errors, enforces file-size limits
- Uses the `mcp_common.FallbackChain` provider gateway — provider config flows through `settings/llms.yaml`, not this adapter
- Designed to fit end-to-end QA flows and orchestrations

## Built-in Implementation

| Module | Description | Status |
| ------ | ----------- | ------ |
| `base.py` | `BaseCodeFixer` ABC + `BaseCodeFixerSettings` (validation, retry, AST security checks) | Stable |
| `unified.py` | `FallbackChainCodeFixer` concrete implementation + `FallbackChainSettings` | Stable |
| `registry.py` | Provider registry helpers (`get_code_fixer`, `list_providers`, `ProviderID`) | Stable |

## Settings

Settings class: `FallbackChainSettings`

- `model` (str; default `MiniMax-M2.7`)
- `task_type` (str; default `code_generation`)
- `llama_server_url` (str; default `http://localhost:8081`)
- Inherited from `BaseCodeFixerSettings`: `max_tokens`, `temperature`, `confidence_threshold`, `max_retries`, `max_file_size_bytes`

Provider routing (`minimax` → `llama_server` → `ollama`) lives in `settings/llms.yaml`; the `FallbackChainCodeFixer` reads from `mcp_common.llm_settings` at `init()` time.

## Basic Usage

```python
from crackerjack.adapters.ai import FallbackChainCodeFixer


async def fix_with_ai() -> None:
    fixer = FallbackChainCodeFixer()
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
- Provider keys live in env vars (`MINIMAX_API_KEY`, etc.) — never log secrets
- The provider chain (MiniMax → llama_server → ollama) is configured in `settings/llms.yaml`, not in this adapter

## Related

- [Type](../type/README.md) — Type checking that often informs fix prompts
- [Refactor](../refactor/README.md) — Refactoring tools that pair well with AI fixes

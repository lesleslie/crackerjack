# AI-fix ruff E501 line-length post-processor — design

**Date:** 2026-07-11
**Status:** Approved (hybrid chosen: prompt + post-processor, refined below after code exploration)
**Scope:** 1 new file, 1 modified file
**Cluster:** 2 (ruff E501 line-length in model output — 5 of 20 failures in latest AI-fix log)

## Problem

The `--ai-fix` loop's plan execution fails when the model emits Python code with lines exceeding the 88-char ruff limit. Error signature from `crackerjack/logs/ai-fix-errors-20260711-025727.json`:

```
ruff E501 (line 246): Line too long (106 > 88)
ruff E501 (line 255): Line too long (99 > 88)
ruff E501 (line 292): Line too long (130 > 88)
... [10+ lines per file] ...
```

Affected files in latest log:
- `crackerjack/core/autofix_coordinator.py` (10 long lines across the file)
- `crackerjack/ai_fix/llm_codegen.py` (1 long line at line 8)

**All 20 retries for `autofix_coordinator.py` regenerate the same long-line content** — the model isn't learning to wrap lines on retry. The fix must catch these at the write boundary.

## Exploration findings (refined approach)

I initially planned to update prompts in `crackerjack/agents/planning_agent.py:90` (`create_fix_plan`) and the delegator chain. After exploring:

- The prompt construction site is dispersed: `_generate_changes` → `_dispatch_fix` → handler methods (`_refactor_for_clarity`, `_fix_type_annotation`, etc.) → optional `delegator.delegate_to_*` calls (`TypeErrorSpecialistAgent`, `DeadCodeRemovalAgent`, `RefurbTransformer`, etc.).
- There is **no single shared prompt template** to update. Each agent owns its own prompt string.
- 6+ agents call `self.context.write_file_content(file_path, content)` to commit fixes — all converge at this single write boundary.

**Refined hybrid approach:**
- **Primary fix (post-processor):** wrap `AgentContext.write_file_content` so every code write passes through `wrap_long_lines` before hitting disk. This catches 100% of code-emitting agents regardless of which prompt constructed the content.
- **Secondary fix (prompt engineering):** OPTIONAL — defer to a follow-up cycle. Updating every agent's prompt is broad and risky; the post-processor alone solves the immediate cluster-2 failure.

## Goals

1. Stop cluster-2 failures at the write boundary.
2. Preserve code semantics (don't break valid code that happens to be long but legitimate).
3. Log warnings when wrapping occurs (so we can measure how often it's needed).
4. Fail open: if the post-processor can't parse the code, pass through unchanged.

## Non-goals

- Bumping ruff's line-length config (88 stays — matches the rest of the codebase).
- Replacing the OutputValidator (which only checks syntax/import/ruff-runtime; E501 isn't a runtime rule).
- Fixing every agent's individual prompt (deferred — the post-processor is the universal defense).
- Reformatting multi-line strings, f-strings, or comments in ways that change semantics.

## Architecture

### New file: `crackerjack/ai_fix/code_post_processor.py`

Single function (not a class — pure utility):

```python
def wrap_long_lines(code: str, max_length: int = 88) -> str:
    """Best-effort Python code reformat to wrap lines exceeding max_length.
    
    Uses libcst to parse the code, walk statements, and reformat any line
    exceeding the limit via libcst's layout-preserving visitor. Returns
    the input unchanged on parse failure (with a logged warning).
    """
```

Algorithm:
1. Parse `code` with `libcst.parse_module(code)`.
2. Walk the CST, accumulating `(line_no, line_text)` for statements (not string literals, not comments — those are tracked separately and never modified).
3. For each statement-line > `max_length`, collect the statement node.
4. Use libcst's `CodeRange` and `whitespace_before` mechanics to wrap the statement at safe boundaries (commas, operators, opening brackets).
5. Serialize the modified CST and return.

For initial scope: we DON'T need full libcst rewrites. The simpler approach: use libcst's `Parser` + `DefaultStyle` codegen with `lines_to_noqa=True` off, and `MaximumLineLength=88` — but libcst's defaults respect the configured line length. **If `code` was originally valid Python and was emitted by the model, running it through libcst's parser with `lines_to_wrap_long_lines=True` should be enough.**

Simplest implementation:
```python
import libcst as cst
from libcst.codemod import VisitorBasedCodeTransformer

def wrap_long_lines(code: str, max_length: int = 88) -> str:
    try:
        module = cst.parse_module(code)
    except cst.ParserSyntaxError as exc:
        logger.warning(f"code_post_processor: parse failed, passing through: {exc}")
        return code
    # libcst's CodeGenerator respects max_line_length
    return module.code_for_maximum_line_length(max_length)
```

This uses libcst's built-in line-length formatter, which already wraps lines at safe boundaries. No custom visitor needed.

**Note:** `module.code_for_maximum_line_length(N)` is a real libcst API as of 1.x.

### Wiring: `crackerjack/agents/base.py` — `AgentContext.write_file_content`

Add the wrap at the write boundary. The existing method:

```python
def write_file_content(self, file_path: str | Path, content: str) -> bool:
    # ... existing body that writes content to disk ...
```

Modified to wrap first:

```python
def write_file_content(self, file_path: str | Path, content: str) -> bool:
    from crackerjack.ai_fix.code_post_processor import wrap_long_lines
    path = self._resolve_project_file_path(file_path)
    if path.suffix == ".py":  # only post-process Python files
        wrapped = wrap_long_lines(content)
        if wrapped != content:
            logger.debug(f"write_file_content: wrapped long lines for {file_path}")
        return self._write_resolved(path, wrapped)
    return self._write_resolved(path, content)
```

**Note:** this only kicks in when called from a real `AgentContext` instance. The post-processor is OPT-IN at the boundary — code that constructs an AgentContext elsewhere (tests, scripts) gets the new behavior automatically.

### Tests: `tests/unit/ai_fix/test_code_post_processor.py`

Test cases (8 unit tests):

1. `test_wrap_short_code_unchanged` — input with all lines ≤ 88 chars → output == input.
2. `test_wrap_simple_long_line` — single line > 88 chars → wraps at a safe boundary.
3. `test_wrap_multiple_long_lines` — multiple long lines → all wrapped.
4. `test_wrap_mixed_long_and_short` — mix of long and short → only long ones wrapped.
5. `test_wrap_parse_failure_returns_unchanged` — invalid Python (e.g. `def foo(:`) → returns input unchanged, logs warning.
6. `test_wrap_non_python_input_unchanged` — non-Python string (e.g. `"hello world"`) → returns input unchanged.
7. `test_wrap_preserves_semantics` — wrapped code still parses to equivalent AST (round-trip via libcst).
8. `test_wrap_respects_max_length_parameter` — passing `max_length=50` wraps more aggressively than `max_length=88`.

Plus an integration test (1):
9. `test_write_file_content_wraps_python` — call `AgentContext.write_file_content` with content containing long lines; verify the file on disk has wrapped content.

## Error handling

- **Parse failure (invalid Python from model):** log warning, return input unchanged. The downstream ruff check will fail the fix, but we don't make it worse.
- **Non-Python file (e.g. `.md`, `.yaml`):** skip wrapping (gate on `.py` suffix in `write_file_content`).
- **libcst import failure (unlikely, libcst is a main dep):** wrap in try/except at module level; log error and return input.

## Testing strategy

- 9 tests above (8 unit + 1 integration).
- Coverage: `wrap_long_lines` should have ≥90% coverage. Integration test exercises the AgentContext wiring.

## Success criteria

- `wrap_long_lines` exists in `crackerjack/ai_fix/code_post_processor.py`.
- `AgentContext.write_file_content` calls it for `.py` files.
- 9 tests pass.
- ruff clean on the new file and `crackerjack/agents/base.py`.
- Manual verification: feed a known long-line snippet through `wrap_long_lines` and verify the output passes `ruff check --select E501`.

## Rollback signal

If wrapping breaks valid code (e.g., corrupts f-strings, breaks decorators), the post-processor is a single function in one file — `git revert` the commit. Wrapping is also a no-op for code that's already within the line limit.

## Open questions

None.
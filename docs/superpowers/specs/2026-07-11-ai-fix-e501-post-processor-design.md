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
def wrap_long_lines(code: str, max_length: int = 88, file_path: Path | None = None) -> str:
    """Best-effort Python code reformat to wrap lines exceeding max_length.
    
    Delegates to `ruff format --line-length N --stdin-filename <name> -` via
    subprocess. Ruff is already a main dependency and is the project's
    canonical formatter — using it guarantees correctness on Python source
    (handles f-strings, comments, multi-line strings, decorators, async).
    Returns input unchanged if ruff is unavailable, if the subprocess
    fails, or if the input isn't Python (no `.py` suffix when file_path
    is provided).
    """
```

Implementation (subprocess-based, simplest correct approach):

```python
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

RUFF_FORMAT_TIMEOUT_S: int = 30


def wrap_long_lines(
    code: str, max_length: int = 88, file_path: Path | None = None
) -> str:
    """Best-effort wrap of long lines in `code` using ruff format."""
    # Gate: only wrap Python files (or files where we don't know the type)
    if file_path is not None and file_path.suffix != ".py":
        return code
    
    # Gate: short-circuit if no line exceeds the limit
    if not any(len(line) > max_length for line in code.splitlines()):
        return code
    
    # Gate: ruff must be on PATH
    if shutil.which("ruff") is None:
        logger.debug("wrap_long_lines: ruff not on PATH; passing through")
        return code
    
    # Run ruff format via subprocess
    cmd = ["ruff", "format", "--line-length", str(max_length), "--stdin-filename", "<post_processor>", "-"]
    try:
        proc = subprocess.run(
            cmd,
            input=code,
            capture_output=True,
            text=True,
            timeout=RUFF_FORMAT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(f"wrap_long_lines: ruff format failed: {exc}; passing through")
        return code
    
    if proc.returncode != 0:
        logger.warning(
            f"wrap_long_lines: ruff format exited {proc.returncode}; passing through. "
            f"stderr: {proc.stderr[:200]}"
        )
        return code
    
    return proc.stdout
```

**Why subprocess over libcst:** libcst does NOT expose a public line-wrap API as of 1.x (only `Module.code` and `code_for_node`). Building a custom wrap transformer is fragile (must handle f-strings, comments, async/await, decorators, line continuations correctly). Ruff is the project's canonical formatter, is already a main dependency, and guarantees correctness.

**Performance:** `ruff format` on a single <200-line file is typically <50ms. Only invoked when a line exceeds the limit (short-circuit gate at step 2), so the common path is a no-op.

**Timeout:** 30s — matches existing `RUFF_CHECK_TIMEOUT_S` constant pattern in `crackerjack/ai_fix/output_validator.py`.

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

1. `test_wrap_short_code_unchanged` — input with all lines ≤ 88 chars → output == input (no subprocess call).
2. `test_wrap_simple_long_line` — single line > 88 chars → ruff format subprocess wraps it; output parses as Python; no line > 88 chars.
3. `test_wrap_multiple_long_lines` — multiple long lines → all wrapped.
4. `test_wrap_mixed_long_and_short` — mix of long and short → only long ones wrapped; short lines preserved.
5. `test_wrap_ruff_unavailable_returns_unchanged` — patch `shutil.which` to return None → returns input unchanged, logs debug message.
6. `test_wrap_non_python_file_path_unchanged` — pass `file_path=Path("foo.md")` with long "lines" in the content → returns input unchanged (gate at file_path suffix).
7. `test_wrap_preserves_semantics` — wrapped output parses successfully via `ast.parse` (smoke check that ruff didn't corrupt the AST).
8. `test_wrap_respects_max_length_parameter` — passing `max_length=50` produces output with no line > 50 chars.

Plus an integration test (1):
9. `test_write_file_content_wraps_python` — call `AgentContext.write_file_content` with content containing long lines; read the file from disk and verify all lines ≤ 88 chars.

## Error handling

- **Ruff not on PATH:** log debug, return input unchanged (graceful degradation — post-processor is best-effort).
- **Ruff subprocess timeout (>30s):** log warning, return input unchanged. Downstream ruff check will catch the long line.
- **Ruff subprocess non-zero exit:** log warning with stderr snippet, return input unchanged.
- **OSError spawning ruff:** log warning, return input unchanged.
- **Non-Python file (e.g. `.md`, `.yaml`):** skip wrapping via `file_path.suffix` gate in `write_file_content`.

## Testing strategy

- 9 tests above (8 unit + 1 integration).
- Coverage: `wrap_long_lines` should have ≥90% coverage. Integration test exercises the AgentContext wiring.
- Ruff format tests verify behavior, not exact output (formatter may evolve); assertion is "no line exceeds max_length" + "still parses".

## Success criteria

- `wrap_long_lines` exists in `crackerjack/ai_fix/code_post_processor.py`.
- `AgentContext.write_file_content` calls it for `.py` files.
- 9 tests pass.
- ruff clean on the new file and `crackerjack/agents/base.py`.
- Manual verification: feed a known long-line snippet through `wrap_long_lines` and verify the output passes `ruff check --select E501`.
- AI-fix error log shows cluster-2 failures dropping to ≤ 1 on next run (was 5 of 20).

## Rollback signal

If wrapping breaks valid code (e.g., corrupts f-strings, breaks decorators), the post-processor is a single function in one file — `git revert` the commit. Wrapping is also a no-op for code that's already within the line limit.

## Open questions

None.
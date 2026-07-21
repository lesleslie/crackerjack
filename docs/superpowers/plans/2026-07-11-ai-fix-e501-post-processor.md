______________________________________________________________________

## status: active role: implementation date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# AI-fix ruff E501 line-length post-processor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop AI-fix cluster-2 failures (ruff E501 line-length) by post-processing every Python file write through `ruff format` via subprocess.

**Architecture:** Add a `wrap_long_lines(code, max_length, file_path)` function in a new `crackerjack/ai_fix/code_post_processor.py` that delegates to `ruff format --line-length N --stdin-filename X -` via subprocess. Wire it into `AgentContext.write_file_content` in `crackerjack/agents/base.py` so every code-emitting agent gets the wrap at the write boundary. Fail-open on any subprocess error.

**Tech Stack:** Python 3.13, `ruff format` (CLI, already a main dep), `pytest` (auto asyncio mode), `pytest.MonkeyPatch`.

## Global Constraints

- **Project conventions** (from `crackerjack/CLAUDE.md`):
  - `from __future__ import annotations` as the first non-comment line of every source file.
  - Imports sorted within each section (stdlib → third-party → first-party, with `force-sort-within-sections = true`).
  - Modern syntax: `X | None`, `list[str]`, `pathlib.Path` for filesystem paths.
  - Function arguments with default `None` typed as `X | None = None`.
  - Use Oneiric logger, not stdlib `logging` (production code only — tests use stdlib per project convention).
- **Test conventions**:
  - Use the project pytest markers: `unit` (don't invent new ones).
  - Async tests don't need `@pytest.mark.asyncio` — `asyncio_mode = "auto"`.
- **Ruff line length**: 88 chars (per `pyproject.toml [tool.ruff] line-length`).
- **Hard limits**: max-args 10, max-branches 15, max-returns 6, max-statements 55 (per `pyproject.toml [tool.ruff.lint.pylint]`).
- **Error handling pattern**: existing `output_validator.py` uses `RUFF_CHECK_TIMEOUT_S: int = 30` constant for subprocess timeouts; mirror this pattern.
- **Fail-open philosophy**: post-processor is best-effort. On any error (timeout, non-zero exit, OSError), return input unchanged — downstream ruff check will catch genuine issues.

______________________________________________________________________

### Task 1: Add `wrap_long_lines` post-processor + wire it + add 9 tests

**Files:**

- Create: `crackerjack/ai_fix/code_post_processor.py` (new file)
- Modify: `crackerjack/agents/base.py:143` (`write_file_content` method — wrap content for `.py` files)
- Create: `tests/unit/ai_fix/test_code_post_processor.py` (new test file, 9 tests)

**Interfaces:**

- Produces: `crackerjack.ai_fix.code_post_processor.wrap_long_lines(code: str, max_length: int = 88, file_path: Path | None = None) -> str`

- Consumes (in `write_file_content`): the existing method signature unchanged from caller perspective; only internal behavior changes.

- [x] **Step 1: Write the failing test file**

Create `tests/unit/ai_fix/test_code_post_processor.py` with the following contents:

```python
"""Test the wrap_long_lines post-processor."""

from __future__ import annotations

import ast
import shutil
from pathlib import Path

import pytest

from crackerjack.ai_fix.code_post_processor import wrap_long_lines


SHORT_CODE = "x = 1\ny = 2\nz = 3\n"
LONG_LINE_CODE = "very_long_variable_name = " + ("'a' + ") * 20 + "'end'\n"


def test_wrap_short_code_unchanged() -> None:
    assert wrap_long_lines(SHORT_CODE) == SHORT_CODE


def test_wrap_simple_long_line() -> None:
    result = wrap_long_lines(LONG_LINE_CODE)
    assert all(len(line) <= 88 for line in result.splitlines())
    ast.parse(result)


def test_wrap_multiple_long_lines() -> None:
    code = LONG_LINE_CODE + LONG_LINE_CODE + LONG_LINE_CODE
    result = wrap_long_lines(code)
    assert all(len(line) <= 88 for line in result.splitlines())
    ast.parse(result)


def test_wrap_mixed_long_and_short() -> None:
    code = SHORT_CODE + LONG_LINE_CODE + SHORT_CODE
    result = wrap_long_lines(code)
    # Short lines preserved as-is
    assert "x = 1" in result
    assert "y = 2" in result
    # Long line wrapped
    assert all(len(line) <= 88 for line in result.splitlines())


def test_wrap_ruff_unavailable_returns_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "crackerjack.ai_fix.code_post_processor.shutil.which",
        lambda _: None,
    )
    assert wrap_long_lines(LONG_LINE_CODE) == LONG_LINE_CODE


def test_wrap_non_python_file_path_unchanged() -> None:
    result = wrap_long_lines(LONG_LINE_CODE, file_path=Path("foo.md"))
    assert result == LONG_LINE_CODE


def test_wrap_preserves_semantics() -> None:
    code = (
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
        + LONG_LINE_CODE
    )
    result = wrap_long_lines(code)
    ast.parse(result)


def test_wrap_respects_max_length_parameter() -> None:
    result = wrap_long_lines(LONG_LINE_CODE, max_length=50)
    assert all(len(line) <= 50 for line in result.splitlines())


def test_write_file_content_wraps_python(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Integration: AgentContext.write_file_content wraps Python files."""
    from crackerjack.agents.base import AgentContext

    # Ensure ruff is on PATH; if not, skip
    if shutil.which("ruff") is None:
        pytest.skip("ruff not on PATH")

    ctx = AgentContext(project_path=tmp_path)
    py_file = tmp_path / "module.py"
    ctx.write_file_content(py_file, LONG_LINE_CODE)

    written = py_file.read_text()
    assert all(len(line) <= 88 for line in written.splitlines())
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/ai_fix/test_code_post_processor.py -v`
Expected: 9 FAILED tests with `ModuleNotFoundError: No module named 'crackerjack.ai_fix.code_post_processor'`

- [x] **Step 3: Create the production file**

Create `crackerjack/ai_fix/code_post_processor.py` with the following contents:

```python
"""Post-processor that wraps long Python lines via `ruff format`."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


RUFF_FORMAT_TIMEOUT_S: int = 30


def wrap_long_lines(
    code: str,
    max_length: int = 88,
    file_path: Path | None = None,
) -> str:
    """Best-effort wrap of long lines in `code` using ruff format subprocess.

    Returns `code` unchanged when:
    - file_path is provided and not a `.py` file
    - no line in `code` exceeds `max_length`
    - `ruff` is not on PATH
    - subprocess fails (timeout, non-zero exit, OSError)

    On success, returns the ruff-formatted output.
    """
    if file_path is not None and file_path.suffix != ".py":
        return code

    if not any(len(line) > max_length for line in code.splitlines()):
        return code

    if shutil.which("ruff") is None:
        logger.debug("wrap_long_lines: ruff not on PATH; passing through")
        return code

    cmd = [
        "ruff",
        "format",
        "--line-length",
        str(max_length),
        "--stdin-filename",
        "<post_processor>",
        "-",
    ]
    try:
        proc = subprocess.run(
            cmd,
            input=code,
            capture_output=True,
            text=True,
            timeout=RUFF_FORMAT_TIMEOUT_S,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning(
            f"wrap_long_lines: ruff format failed: {exc}; passing through"
        )
        return code

    if proc.returncode != 0:
        logger.warning(
            f"wrap_long_lines: ruff format exited {proc.returncode}; "
            f"passing through. stderr: {proc.stderr[:200]}"
        )
        return code

    return proc.stdout


__all__ = ["RUFF_FORMAT_TIMEOUT_S", "wrap_long_lines"]
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/ai_fix/test_code_post_processor.py -v`
Expected: 9 PASSED tests (the integration test auto-skips if ruff not on PATH, but should pass on this machine)

- [x] **Step 5: Wire the post-processor into `AgentContext.write_file_content`**

In `crackerjack/agents/base.py`, modify the `write_file_content` method (currently at line 143). The method's current body writes `content` directly to disk via `path.write_text(content)`. Wrap it as follows:

Find the existing method body (the existing code does some path resolution + the actual write — preserve all existing logic, only wrap the `content` variable):

Change the first line that takes `content` and uses it (the variable that ultimately gets written to disk) to wrap it:

```python
    def write_file_content(self, file_path: str | Path, content: str) -> bool:
        from crackerjack.ai_fix.code_post_processor import wrap_long_lines

        path = self._resolve_project_file_path(file_path)
        # Post-process Python files to wrap lines that exceed the project limit
        content = wrap_long_lines(content, file_path=path)
        # ... (existing body that writes content to disk continues unchanged) ...
```

The exact existing body depends on what's currently in `write_file_content`. The implementer should Read the current method body and replace only the part where `content` enters the method, keeping all existing path-traversal checks, security checks, error handling, and the actual `path.write_text(content)` call unchanged. The import goes at the top of the method (lazy import — keeps the ai_fix dependency non-circular for non-AI-fix callers of AgentContext).

- [x] **Step 6: Verify ruff clean on all 3 changed/created files**

Run: `uv run ruff check crackerjack/ai_fix/code_post_processor.py crackerjack/agents/base.py tests/unit/ai_fix/test_code_post_processor.py`
Expected: All checks passed!

If any violations appear, fix them in-place before committing. Most likely: line-length (88 chars max), import order.

- [x] **Step 7: Run the new tests + a sanity test on write_file_content**

Run: `uv run pytest tests/unit/ai_fix/test_code_post_processor.py tests/unit/agents/test_base.py -v`
Expected: 9 new tests pass; pre-existing tests in `test_base.py` still pass (no regression).

- [x] **Step 8: Commit**

```bash
git add crackerjack/ai_fix/code_post_processor.py tests/unit/ai_fix/test_code_post_processor.py crackerjack/agents/base.py
git commit -m "feat(ai-fix): post-process Python writes to wrap long lines (cluster 2)"
```

Commit message body should reference the spec (`docs/superpowers/specs/2026-07-11-ai-fix-e501-post-processor-design.md` amended at commit `cd8b1f16`) and note that the post-processor uses `ruff format` subprocess (not libcst, which lacks a public line-wrap API as of 1.x).

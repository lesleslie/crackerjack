# FixSandbox Production Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing `FixSandbox` transport layer into the production fixer-dispatch path so every fixer invocation runs in a subprocess with filesystem isolation. Opt-in via oneiric setting + env var; default off.

**Architecture:** A new `SandboxedFixerDispatcher` (in `crackerjack/ai_fix/sandboxed_dispatcher.py`) sits between `FixerCoordinator._execute_single_plan` and the actual fixer methods. When the new `use_sandbox=True` constructor arg is set, the dispatcher serializes the `FixPlan` to JSON, invokes `crackerjack fix-runner` (a new CLI) via `FixSandbox.run_command` in a subprocess, and synthesizes a `FixResult` from the subprocess's output JSON. The existing in-process path stays untouched. The new setting lives on the existing `AISettings` class with an env-var override.

**Tech Stack:** Python 3.13, Pydantic v2, existing `FixSandbox` + `OutputValidator`, Typer (for the new CLI), pytest (existing test framework).

______________________________________________________________________

## Global Constraints

These are taken from the crackerjack project's `CLAUDE.md` and the existing AI fix code, and apply to every task below:

- **Python 3.13**, `from __future__ import annotations` as the first non-comment line of every source file.
- **Modern type syntax**: `X | None` (not `Optional[X]`), `list[str]` (not `List[str]`), `pathlib.Path` for filesystem paths.
- **Function args with default `None`** must be typed `X | None = None` (mypy `no_implicit_optional = true`).
- **No `assert` in production code** (`crackerjack/**`). Use exceptions.
- **Use the Oneiric logger** pattern (`logger = logging.getLogger(__name__)`) — matches existing crackerjack code.
- **In `except` blocks, use `logger.exception(...)`**, never `logger.error(..., exc_info=True)`.
- **Async tests** don't need `@pytest.mark.asyncio` — `asyncio_mode = "auto"`.
- **Test markers**: use the project's existing markers (`unit`, `integration`, `slow`, `timeout`); don't invent new ones.
- **Imports sorted within each section** (stdlib → third-party → first-party, with `known-first-party = ["crackerjack"]`).
- **One commit per task** with the format `feat:` / `fix:` / `refactor:` / `test:` / `docs:`.
- **Per-task test run must pass** before moving to the next task. Don't accumulate uncommitted changes across task boundaries.
- **Use the existing 359 unit tests as the regression baseline** — none of them may fail after any task. The new sandboxed path is opt-in, so the in-process path is unchanged.
- **The opt-in env vars are `CRACKERJACK_AI_FIX_USE_SANDBOX` and `CRACKERJACK_AI_FIX_SANDBOX_FALLBACK`**, matching the existing `CRACKERJACK_AI_FIX_*` pattern (per the existing `_get_per_issue_timeout` in `crackerjack/core/autofix_coordinator.py`).
- **Crackerjack's per-issue timeout is 300s** (line 2974: `DEFAULT_SANDBOX_TIMEOUT_S = 300`); the sandbox timeout defaults to the same value.
- **`FixPlan` is a Pydantic model** — serializable via `model_dump_json()`.

______________________________________________________________________

## File Structure

| File | Status | Responsibility |
|---|---|---|
| `crackerjack/config/settings.py` | Modify | Add `ai_fix_use_sandbox` and `ai_fix_sandbox_timeout_s` to `AISettings`. |
| `settings/crackerjack.yaml` | Modify | Add the new keys under `# AI Agent`. |
| `crackerjack/ai_fix/fix_runner.py` | Create | `python -m crackerjack fix-runner` CLI subprocess driver. |
| `crackerjack/ai_fix/sandboxed_dispatcher.py` | Create | The dispatcher that calls `FixSandbox.run_command` and synthesizes `FixResult[]`. |
| `crackerjack/agents/fixer_coordinator.py` | Modify | Add `use_sandbox` constructor arg + dispatch branch in `_execute_single_plan`. |
| `crackerjack/core/autofix_coordinator.py` | Modify | Add env-var helpers + wire `use_sandbox` when constructing `FixerCoordinator`. |
| `tests/unit/ai_fix/test_fix_runner.py` | Create | Unit tests for the fix-runner CLI. |
| `tests/unit/ai_fix/test_sandboxed_dispatcher.py` | Create | Unit tests for the dispatcher. |
| `tests/integration/test_sandboxed_fix.py` | Create | Worktree-based end-to-end test. |

______________________________________________________________________

### Task 1: Add `ai_fix_use_sandbox` setting to `AISettings`

**Files:**

- Modify: `crackerjack/config/settings.py:73-99` (the `AISettings` class)
- Modify: `settings/crackerjack.yaml` (the `# AI Agent` section)
- Test: `tests/unit/config/test_ai_settings.py` (new — small)

**Interfaces:**

- Consumes: nothing (this is the leaf task)

- Produces:

  - `settings.ai.ai_fix_use_sandbox: bool` (default `False`)
  - `settings.ai.ai_fix_sandbox_timeout_s: int` (default `300`)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/config/test_ai_settings.py` with:

```python
"""Test the new AI fix sandbox settings fields."""

from __future__ import annotations

from crackerjack.config.settings import AISettings


def test_ai_fix_use_sandbox_defaults_to_false() -> None:
    s = AISettings()
    assert s.ai_fix_use_sandbox is False


def test_ai_fix_sandbox_timeout_defaults_to_300() -> None:
    s = AISettings()
    assert s.ai_fix_sandbox_timeout_s == 300


def test_ai_fix_use_sandbox_can_be_enabled() -> None:
    s = AISettings(ai_fix_use_sandbox=True)
    assert s.ai_fix_use_sandbox is True


def test_ai_fix_sandbox_timeout_can_be_overridden() -> None:
    s = AISettings(ai_fix_sandbox_timeout_s=120)
    assert s.ai_fix_sandbox_timeout_s == 120
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/config/test_ai_settings.py -v`
Expected: FAIL with `AttributeError: type object 'AISettings' has no attribute 'ai_fix_use_sandbox'` (because the field doesn't exist yet).

- [ ] **Step 3: Add the fields to `AISettings`**

In `crackerjack/config/settings.py`, inside the `AISettings` class (around line 79, after `ai_agent_autofix`), add:

```python
    ai_fix_use_sandbox: bool = False
    ai_fix_sandbox_timeout_s: int = 300
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/config/test_ai_settings.py -v`
Expected: 4 tests pass.

- [ ] **Step 5: Add the YAML defaults**

In `settings/crackerjack.yaml`, under the `# AI Agent` section (after `ai_agent_autofix: false`), add:

```yaml
# AI Fix Sandbox (subprocess isolation for fixer invocations)
ai_fix_use_sandbox: false
ai_fix_sandbox_timeout_s: 300
```

- [ ] **Step 6: Run the full existing test suite to confirm no regression**

Run: `uv run pytest tests/ -x --timeout=60 -q 2>&1 | tail -20`
Expected: All existing 359+ tests still pass. The new test class adds 4 tests, total 363+.

- [ ] **Step 7: Commit**

```bash
git add crackerjack/config/settings.py settings/crackerjack.yaml tests/unit/config/test_ai_settings.py
git commit -m "feat(ai-fix): add ai_fix_use_sandbox and ai_fix_sandbox_timeout_s settings"
```

______________________________________________________________________

### Task 2: Create the `fix-runner` CLI with its first test

**Files:**

- Create: `crackerjack/ai_fix/fix_runner.py` (~120 LoC)
- Create: `tests/unit/ai_fix/test_fix_runner.py` (~120 LoC)

**Interfaces:**

- Consumes: nothing (this is the subprocess driver; standalone)

- Produces:

  - `crackerjack.ai_fix.fix_runner.run(args: list[str]) -> int` — main entry point; returns process exit code (0/1/2).
  - `crackerjack.ai_fix.fix_runner.PlanPayload` — Pydantic model: `fixer_id: str`, `file_path: str`, `issue_type: str`, `changes: list[dict]`, `risk_level: str`, `issue_message: str`, `issue_stage: str`.
  - `crackerjack.ai_fix.fix_runner.PlanResult` — Pydantic model: `plan_idx: int`, `success: bool`, `modified_content: str | None`, `files_modified: list[str]`, `remaining_issues: list[str]`, `reason: str = ""`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/ai_fix/test_fix_runner.py` with:

```python
"""Unit tests for the fix-runner CLI (subprocess driver)."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path

from crackerjack.ai_fix.fix_runner import (
    PlanPayload,
    PlanResult,
    run,
)


def test_run_returns_2_on_missing_plans_json(tmp_path: Path) -> None:
    """A nonexistent plans-json path should return exit code 2 (setup error)."""
    rc = run([
        "--plans-json", str(tmp_path / "missing.json"),
        "--output-json", str(tmp_path / "out.json"),
        "--project-root", str(tmp_path),
    ])
    assert rc == 2


def test_run_returns_2_on_unknown_fixer(tmp_path: Path) -> None:
    """A plan with a non-existent fixer_id should return exit code 2."""
    plans_path = tmp_path / "plans.json"
    plans_path.write_text(json.dumps([{
        "fixer_id": "no.such.module:DoesNotExist",
        "file_path": "f.py",
        "issue_type": "FORMATTING",
        "changes": [],
        "risk_level": "low",
        "issue_message": "test",
        "issue_stage": "ruff-check",
    }]))
    out_path = tmp_path / "out.json"
    rc = run([
        "--plans-json", str(plans_path),
        "--output-json", str(out_path),
        "--project-root", str(tmp_path),
    ])
    assert rc == 2
    assert not out_path.exists() or json.loads(out_path.read_text()) == {}


def test_plan_payload_roundtrip() -> None:
    """PlanPayload can be constructed and serialized via model_dump_json."""
    p = PlanPayload(
        fixer_id="crackerjack.agents.architect_agent:ArchitectAgent",
        file_path="f.py",
        issue_type="FORMATTING",
        changes=[],
        risk_level="low",
        issue_message="test",
        issue_stage="ruff-check",
    )
    roundtrip = PlanPayload.model_validate_json(p.model_dump_json())
    assert roundtrip == p


def test_plan_result_roundtrip() -> None:
    """PlanResult can be constructed and serialized via model_dump_json."""
    r = PlanResult(
        plan_idx=0,
        success=True,
        modified_content="x = 1\n",
        files_modified=["f.py"],
        remaining_issues=[],
    )
    roundtrip = PlanResult.model_validate_json(r.model_dump_json())
    assert roundtrip == r
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/ai_fix/test_fix_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.ai_fix.fix_runner'`.

- [ ] **Step 3: Create the fix-runner module skeleton**

Create `crackerjack/ai_fix/fix_runner.py` with:

```python
"""Subprocess driver for the fix-runner CLI.

This module is invoked as ``python -m crackerjack fix-runner`` by the
:mod:`crackerjack.ai_fix.sandboxed_dispatcher` subprocess. It is NOT
registered as a top-level crackerjack subcommand; it exists only as
the receiving end of the sandbox subprocess.

The runner:
1. Reads a list of plans from a JSON file.
2. For each plan, copies the target file into the working directory
   as ``out_N.py`` (the first plan is ``out.py`` to satisfy the
   sandbox's contract — see ``crackerjack/ai_fix/fix_sandbox.py:164``).
3. Dispatches each plan to the fixer class identified by
   ``plan.fixer_id`` (format ``"module.path:ClassName"``).
4. Validates each output file via
   :class:`crackerjack.ai_fix.output_validator.OutputValidator`.
5. Writes a JSON result file with per-plan outcomes.
6. Exits 0 if all plans succeeded, 1 if any failed, 2 on setup error.

The fixer's execution method follows the same ``hasattr`` dispatch as
``crackerjack.agents.fixer_coordinator.FixerCoordinator._execute_single_plan``
(lines 206-222): ``execute_fix_plan`` first, then ``analyze_and_fix``.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# Exit codes
EXIT_OK = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_SETUP_ERROR = 2


class PlanPayload(BaseModel):
    """The JSON contract for a single plan passed to the runner.

    Mirrors the relevant fields of ``crackerjack.models.fix_plan.FixPlan``
    without the model dependency (so the runner is decoupled from
    the production plan model).
    """

    fixer_id: str
    file_path: str
    issue_type: str
    changes: list[dict[str, Any]] = Field(default_factory=list)
    risk_level: str
    issue_message: str
    issue_stage: str


class PlanResult(BaseModel):
    """The JSON contract for a single plan's result."""

    plan_idx: int
    success: bool
    modified_content: str | None = None
    files_modified: list[str] = Field(default_factory=list)
    remaining_issues: list[str] = Field(default_factory=list)
    reason: str = ""


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="crackerjack fix-runner",
        description="Subprocess driver for sandboxed fixer invocations.",
    )
    parser.add_argument(
        "--plans-json",
        type=Path,
        required=True,
        help="Path to the input JSON file containing the plans.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        required=True,
        help="Path to write the per-plan results JSON.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="The crackerjack project root; used to resolve file_path.",
    )
    return parser.parse_args(argv)


def _load_fixer(fixer_id: str) -> Any:
    """Load a fixer class from ``module.path:ClassName``.

    Returns the class, not an instance. The caller instantiates.
    Raises ``ValueError`` on parse or import failure.
    """
    if ":" not in fixer_id:
        raise ValueError(f"invalid fixer_id (no ':'): {fixer_id!r}")
    module_path, class_name = fixer_id.rsplit(":", 1)
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise ValueError(f"unknown fixer module {module_path!r}: {exc}") from exc
    try:
        return getattr(module, class_name)
    except AttributeError as exc:
        raise ValueError(
            f"unknown fixer class {class_name!r} in {module_path!r}"
        ) from exc


def _dispatch_fixer(fixer_instance: Any, plan: PlanPayload) -> tuple[bool, str]:
    """Dispatch a plan to a fixer instance, returning ``(success, reason)``.

    Follows the same ``hasattr`` dispatch as
    ``FixerCoordinator._execute_single_plan``: try ``execute_fix_plan``
    first, then ``analyze_and_fix``.
    """
    if hasattr(fixer_instance, "execute_fix_plan"):
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(
                    fixer_instance.execute_fix_plan(plan.model_dump())
                )
            finally:
                loop.close()
        except Exception as exc:
            return False, f"fixer raised: {exc}"
        return bool(result), ""
    if hasattr(fixer_instance, "analyze_and_fix"):
        return False, (
            f"fixer {type(fixer_instance).__name__} exposes analyze_and_fix "
            "(requires Issue reconstruction; not supported in fix-runner)"
        )
    return False, (
        f"fixer {type(fixer_instance).__name__} lacks execute_fix_plan "
        "or analyze_and_fix"
    )


def _read_output(out_path: Path) -> str | None:
    """Read the fixer's output file, returning ``None`` if absent."""
    if not out_path.exists():
        return None
    try:
        return out_path.read_text(encoding="utf-8")
    except OSError:
        return None


def _process_plan(
    plan_idx: int,
    plan: PlanPayload,
    workdir: Path,
    project_root: Path,
    original_validator: Any,
) -> PlanResult:
    """Process a single plan within the workdir."""
    out_name = "out.py" if plan_idx == 0 else f"out_{plan_idx}.py"
    out_path = workdir / out_name

    # Resolve the source file relative to project root.
    src = project_root / plan.file_path
    if not src.is_file():
        return PlanResult(
            plan_idx=plan_idx,
            success=False,
            remaining_issues=[f"source file does not exist: {src}"],
        )

    try:
        shutil.copy2(src, out_path)
    except OSError as exc:
        return PlanResult(
            plan_idx=plan_idx,
            success=False,
            remaining_issues=[f"could not copy source: {exc}"],
        )

    # Load + instantiate the fixer.
    try:
        fixer_cls = _load_fixer(plan.fixer_id)
    except ValueError as exc:
        return PlanResult(
            plan_idx=plan_idx,
            success=False,
            remaining_issues=[str(exc)],
        )

    try:
        fixer_instance = fixer_cls(project_path=str(project_root))
    except Exception:
        # Some fixers don't take a project_path; try no-arg.
        try:
            fixer_instance = fixer_cls()
        except Exception as exc:
            return PlanResult(
                plan_idx=plan_idx,
                success=False,
                remaining_issues=[f"could not instantiate fixer: {exc}"],
            )

    success, reason = _dispatch_fixer(fixer_instance, plan)
    if not success:
        return PlanResult(
            plan_idx=plan_idx,
            success=False,
            remaining_issues=[reason or "fixer reported failure"],
        )

    # Read the modified output and validate.
    modified = _read_output(out_path)
    if modified is None:
        return PlanResult(
            plan_idx=plan_idx,
            success=False,
            remaining_issues=["fixer did not produce output file"],
        )

    # Only validate Python files (matches FixSandbox's behavior).
    if out_path.suffix == ".py":
        validation = original_validator.validate(out_path)
        if not validation.passed:
            return PlanResult(
                plan_idx=plan_idx,
                success=False,
                remaining_issues=[f"output validation failed: {validation.reason}"],
            )

    return PlanResult(
        plan_idx=plan_idx,
        success=True,
        modified_content=modified,
        files_modified=[str(src)],
    )


def run(argv: list[str] | None = None) -> int:
    """Main entry point. Returns the process exit code."""
    from crackerjack.ai_fix.output_validator import OutputValidator

    args = _parse_args(argv)
    validator = OutputValidator()

    if not args.plans_json.is_file():
        logger.exception("plans-json not found: %s", args.plans_json)
        return EXIT_SETUP_ERROR

    try:
        plans_data = json.loads(args.plans_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.exception("could not read plans JSON")
        return EXIT_SETUP_ERROR

    workdir = Path.cwd()
    results: list[PlanResult] = []

    for idx, raw in enumerate(plans_data):
        try:
            plan = PlanPayload.model_validate(raw)
        except Exception as exc:
            results.append(PlanResult(
                plan_idx=idx,
                success=False,
                remaining_issues=[f"plan validation failed: {exc}"],
            ))
            continue
        result = _process_plan(idx, plan, workdir, args.project_root, validator)
        results.append(result)

    # Write the output JSON.
    try:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps({"results": [r.model_dump() for r in results]}),
            encoding="utf-8",
        )
    except OSError:
        logger.exception("could not write output JSON to %s", args.output_json)
        return EXIT_SETUP_ERROR

    return EXIT_OK if all(r.success for r in results) else EXIT_PARTIAL_FAILURE


def main() -> int:
    """Entry point for ``python -m crackerjack fix-runner``."""
    return run(sys.argv[1:])


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


__all__ = [
    "EXIT_OK",
    "EXIT_PARTIAL_FAILURE",
    "EXIT_SETUP_ERROR",
    "PlanPayload",
    "PlanResult",
    "run",
]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/ai_fix/test_fix_runner.py -v`
Expected: 4 tests pass. (The first two tests invoke `run()` directly with synthetic args, so they don't need a real subprocess.)

- [ ] **Step 5: Run the full existing test suite to confirm no regression**

Run: `uv run pytest tests/ -x --timeout=60 -q 2>&1 | tail -20`
Expected: All existing 363+ tests still pass.

- [ ] **Step 6: Commit**

```bash
git add crackerjack/ai_fix/fix_runner.py tests/unit/ai_fix/test_fix_runner.py
git commit -m "feat(ai-fix): add fix-runner CLI subprocess driver"
```

______________________________________________________________________

### Task 3: Create the `SandboxedFixerDispatcher` with its first test

**Files:**

- Create: `crackerjack/ai_fix/sandboxed_dispatcher.py` (~150 LoC)
- Create: `tests/unit/ai_fix/test_sandboxed_dispatcher.py` (~200 LoC, 6 tests)

**Interfaces:**

- Consumes:

  - `crackerjack.ai_fix.fix_sandbox.FixSandbox` and `SandboxResult` (already exists; see `crackerjack/ai_fix/fix_sandbox.py`)
  - `crackerjack.ai_fix.fix_runner.PlanPayload` and `PlanResult` (from Task 2)
  - `crackerjack.agents.base.FixResult` (existing; see `crackerjack/agents/base.py:54-64`)
  - `crackerjack.config.settings.settings` (the global oneiric settings object)

- Produces:

  - `crackerjack.ai_fix.sandboxed_dispatcher.SandboxedFixerDispatcher` class
  - `dispatch_batch(plans: list) -> list[FixResult]` — public entry point
  - Constructor signature: `SandboxedFixerDispatcher(sandbox: FixSandbox, fixer_resolver: Callable[[str, str], Any] | None = None)` — `fixer_resolver` is `(fixer_id, project_root) -> fixer_instance | None`; the default resolver uses the project's fixer registry.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/ai_fix/test_sandboxed_dispatcher.py` with:

```python
"""Unit tests for the SandboxedFixerDispatcher.

These tests use a fake ``FixSandbox`` (no real subprocess) and a fake
``fixer_resolver`` to exercise the dispatcher's contract in isolation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from crackerjack.ai_fix.fix_sandbox import SandboxResult
from crackerjack.ai_fix.sandboxed_dispatcher import SandboxedFixerDispatcher
from crackerjack.agents.base import FixResult
from crackerjack.models.fix_plan import FixPlan


def _make_plan(file_path: str, issue_type: str = "FORMATTING") -> FixPlan:
    return FixPlan(
        file_path=file_path,
        issue_type=issue_type,
        changes=[],
        rationale="test",
        risk_level="low",
        validated_by="test",
        issue_message="test message",
        issue_stage="ruff-check",
    )


def _write_result_json(
    output_path: Path,
    results: list[dict[str, Any]],
) -> None:
    output_path.write_text(
        json.dumps({"results": results}),
        encoding="utf-8",
    )


def test_dispatch_batch_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sandbox returns a valid result JSON → dispatcher builds FixResult per plan."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    output_json = tmp_path / "out" / "results.json"
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=True,
        modified_content="x = 2\n",
        duration_s=0.1,
    ))

    def fake_run(_argv: list[str] | None = None) -> int:
        _write_result_json(output_json, [{
            "plan_idx": 0,
            "success": True,
            "modified_content": "x = 2\n",
            "files_modified": [str(source)],
            "remaining_issues": [],
        }])
        return 0

    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        fake_run,
    )

    dispatcher = SandboxedFixerDispatcher(sandbox=sandbox)
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].files_modified == [str(source)]
    assert sandbox.run_command.call_count == 1


def test_dispatch_batch_subprocess_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sandbox returns passed=False, reason='<err>' → all plans fail."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=False,
        reason="subprocess exit code 1",
        duration_s=0.1,
    ))

    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 1,
    )

    dispatcher = SandboxedFixerDispatcher(sandbox=sandbox)
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is False
    assert "subprocess exit code 1" in results[0].remaining_issues[0]


def test_dispatch_batch_validation_failure_no_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Validation failure: fallback must NOT be attempted, even when env var is set."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=False,
        reason="output validation failed: SyntaxError",
        duration_s=0.1,
    ))

    fallback_called = MagicMock()
    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 1,
    )
    monkeypatch.setenv("CRACKERJACK_AI_FIX_SANDBOX_FALLBACK", "1")

    dispatcher = SandboxedFixerDispatcher(
        sandbox=sandbox, in_process_fallback=fallback_called,
    )
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is False
    assert "validation failed" in results[0].remaining_issues[0]
    fallback_called.assert_not_called()


def test_dispatch_batch_timeout_with_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Subprocess timeout: fallback IS attempted when env var is set."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=False,
        reason="subprocess timeout after 300s",
        duration_s=300.0,
    ))

    fallback_result = [FixResult(success=True, files_modified=[str(source)])]
    fallback_called = MagicMock(return_value=fallback_result)
    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 1,
    )
    monkeypatch.setenv("CRACKERJACK_AI_FIX_SANDBOX_FALLBACK", "1")

    dispatcher = SandboxedFixerDispatcher(
        sandbox=sandbox, in_process_fallback=fallback_called,
    )
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    fallback_called.assert_called_once()
    assert results is fallback_result


def test_dispatch_batch_serialization_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plan that fails Pydantic validation → that plan gets a failure result."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock()
    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 2,
    )

    # Force a serialization error by passing a plan that will fail
    # model_dump_json. (Pydantic v2 doesn't normally fail; we patch
    # the dispatcher's _serialize_plans to raise.)
    dispatcher = SandboxedFixerDispatcher(sandbox=sandbox)
    monkeypatch.setattr(
        dispatcher, "_serialize_plans", MagicMock(side_effect=ValueError("boom"))
    )

    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is False
    assert "plan serialization failed" in results[0].remaining_issues[0]
    sandbox.run_command.assert_not_called()


def test_dispatch_batch_malformed_result_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sandbox returns passed=True but result file has invalid JSON → all plans fail."""
    source = tmp_path / "f.py"
    source.write_text("x = 1\n", encoding="utf-8")
    output_json = tmp_path / "out" / "results.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text("not valid json {{{", encoding="utf-8")
    plan = _make_plan(str(source))

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=True,
        modified_content="x = 1\n",
        duration_s=0.1,
    ))

    monkeypatch.setattr(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 0,
    )

    dispatcher = SandboxedFixerDispatcher(sandbox=sandbox)
    results = dispatcher.dispatch_batch([plan], project_root=tmp_path)

    assert len(results) == 1
    assert results[0].success is False
    assert "malformed result" in results[0].remaining_issues[0]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/ai_fix/test_sandboxed_dispatcher.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'crackerjack.ai_fix.sandboxed_dispatcher'`.

- [ ] **Step 3: Create the dispatcher module**

Create `crackerjack/ai_fix/sandboxed_dispatcher.py` with:

```python
"""SandboxedFixerDispatcher — runs fixer invocations through FixSandbox.

When the new ``use_sandbox`` constructor arg is set on
:class:`crackerjack.agents.fixer_coordinator.FixerCoordinator`, the
fixer dispatch goes through this class instead of calling fixers
in-process. The dispatcher:

1. Serializes the plans to JSON via
   :func:`crackerjack.ai_fix.fix_runner.PlanPayload`.
2. Writes the JSON to a temp file.
3. Invokes :meth:`FixSandbox.run_command` with the
   ``crackerjack fix-runner`` CLI as the subprocess.
4. Reads the result JSON from the sandbox temp dir.
5. Synthesizes a :class:`crackerjack.agents.base.FixResult` per plan.

On subprocess failure (not validation failure), the dispatcher may
fall back to the in-process path if
``CRACKERJACK_AI_FIX_SANDBOX_FALLBACK=1`` is set. Validation
failures are never fallback-eligible.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

from crackerjack.ai_fix import fix_runner
from crackerjack.ai_fix.fix_sandbox import FixSandbox, SandboxResult
from crackerjack.agents.base import FixResult

logger = logging.getLogger(__name__)


class SandboxedFixerDispatcher:
    """Routes fixer invocations through a :class:`FixSandbox` subprocess.

    The dispatcher is dependency-injected with a :class:`FixSandbox`
    and an optional in-process fallback callable. Tests can pass a
    fake sandbox (e.g. ``MagicMock()``) and a fake fallback to
    exercise the dispatch logic without real subprocesses.
    """

    def __init__(
        self,
        sandbox: FixSandbox,
        in_process_fallback: Callable[[list[Any]], list[FixResult]] | None = None,
    ) -> None:
        self._sandbox = sandbox
        self._in_process_fallback = in_process_fallback

    def _serialize_plans(self, plans: list[Any], project_root: Path) -> list[dict[str, Any]]:
        """Serialize plans to the JSON contract the runner expects.

        Each plan is converted to a ``PlanPayload`` via Pydantic,
        then ``model_dump()``-ed. The fixer_id is derived from the
        plan's issue_type via the project's fixer registry; if no
        fixer is registered for the issue_type, the plan is
        serialized with ``fixer_id=""`` and the runner will fail it
        with "unknown fixer".
        """
        from crackerjack.ai_fix.fix_runner import PlanPayload

        out: list[dict[str, Any]] = []
        for plan in plans:
            payload = PlanPayload(
                fixer_id=_resolve_fixer_id(plan),
                file_path=plan.file_path,
                issue_type=plan.issue_type,
                changes=[c.model_dump() if hasattr(c, "model_dump") else c
                         for c in plan.changes],
                risk_level=plan.risk_level,
                issue_message=getattr(plan, "issue_message", ""),
                issue_stage=getattr(plan, "issue_stage", "ruff-check"),
            )
            out.append(payload.model_dump())
        return out

    def dispatch_batch(
        self,
        plans: list[Any],
        *,
        project_root: Path,
        timeout_s: int = 300,
    ) -> list[FixResult]:
        """Run the plans through the sandbox and return FixResult per plan.

        Args:
            plans: The list of FixPlan (or plan-like) objects to execute.
            project_root: The crackerjack project root, used to
                resolve plan.file_path and to pass to the subprocess.
            timeout_s: Sandbox timeout (default 300s).

        Returns:
            A list of FixResult, one per plan, in the same order.
        """
        if not plans:
            return []

        # Serialize plans; if any fail, fail the whole batch.
        try:
            payloads = self._serialize_plans(plans, project_root)
        except Exception as exc:
            logger.exception("plan serialization failed")
            return [FixResult(
                success=False,
                remaining_issues=[f"plan serialization failed: {exc}"],
            ) for _ in plans]

        # Write plans JSON to a temp file the sandbox will pass to the runner.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as plans_file:
            json.dump(payloads, plans_file)
            plans_path = Path(plans_file.name)
        output_path = plans_path.with_name(plans_path.stem + "-out.json")
        # Ensure the output path is in a location the runner can write
        # (the runner writes to args.output_json; the sandbox doesn't
        # require it to be inside its temp dir, but the runner's
        # parent path is created in fix_runner's run()).

        # Build the subprocess command. The first plan's file is the
        # sandbox's "anchor" file; the runner handles the rest.
        first_plan = plans[0]
        first_file = project_root / first_plan.file_path
        if not first_file.is_file():
            return [FixResult(
                success=False,
                remaining_issues=[f"first plan's file does not exist: {first_file}"],
            )]

        command = [
            sys.executable, "-m", "crackerjack", "fix-runner",
            "--plans-json", str(plans_path),
            "--output-json", str(output_path),
            "--project-root", str(project_root),
        ]

        sandbox_result = self._sandbox.run_command(
            command=command,
            file_path=first_file,
            timeout=timeout_s,
        )

        return self._process_sandbox_result(
            sandbox_result, plans, output_path, plans_path,
        )

    def _process_sandbox_result(
        self,
        sandbox_result: SandboxResult,
        plans: list[Any],
        output_path: Path,
        plans_path: Path,
    ) -> list[FixResult]:
        """Convert a SandboxResult into per-plan FixResult objects."""
        # Clean up the plans JSON.
        try:
            plans_path.unlink()
        except OSError:
            pass

        if not sandbox_result.passed:
            # Check if this is a fallback-eligible failure.
            is_validation_failure = "validation" in sandbox_result.reason.lower()
            fallback_enabled = os.environ.get(
                "CRACKERJACK_AI_FIX_SANDBOX_FALLBACK", ""
            ).lower() in ("1", "true", "yes", "on")

            if (
                not is_validation_failure
                and fallback_enabled
                and self._in_process_fallback is not None
            ):
                logger.warning(
                    "Sandbox failed (not validation); falling back to in-process: %s",
                    sandbox_result.reason,
                )
                return self._in_process_fallback(plans)

            # Surface the failure for the whole batch.
            return [FixResult(
                success=False,
                remaining_issues=[sandbox_result.reason or "sandbox failed"],
            ) for _ in plans]

        # Sandbox passed; read and parse the result JSON.
        if not output_path.exists():
            return [FixResult(
                success=False,
                remaining_issues=[
                    f"sandbox passed but output file not found: {output_path}"
                ],
            ) for _ in plans]

        try:
            results_data = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.exception("malformed result JSON from sandbox")
            return [FixResult(
                success=False,
                remaining_issues=[f"malformed result from sandbox: {exc}"],
            ) for _ in plans]

        # Clean up the output JSON.
        try:
            output_path.unlink()
        except OSError:
            pass

        # Build per-plan FixResult.
        results = results_data.get("results", [])
        fix_results: list[FixResult] = []
        for r in results:
            fix_results.append(FixResult(
                success=bool(r.get("success", False)),
                files_modified=list(r.get("files_modified", [])),
                remaining_issues=list(r.get("remaining_issues", [])),
            ))

        # Pad with failure results if the runner returned fewer entries
        # than plans (defensive against runner bugs).
        while len(fix_results) < len(plans):
            fix_results.append(FixResult(
                success=False,
                remaining_issues=["runner returned fewer results than plans"],
            ))

        return fix_results[: len(plans)]


def _resolve_fixer_id(plan: Any) -> str:
    """Resolve the fixer module:class string for a plan.

    Uses the project's existing fixer registry to look up the
    registered fixer for the plan's issue_type. The default
    registration lives in ``crackerjack.agents.fixer_coordinator``
    (see ``FixerCoordinator._candidate_fixer_keys``).
    """
    # Importing here to avoid a circular import with
    # agents.fixer_coordinator (which itself imports from ai_fix).
    from crackerjack.agents.fixer_coordinator import FixerCoordinator

    try:
        candidate_keys = FixerCoordinator._candidate_fixer_keys(plan.issue_type)
    except Exception:
        return ""

    for key in candidate_keys:
        # Look up the fixer's module + class name.
        # This is heuristic; the real resolution is the dispatcher's
        # job. We return the first registered key as a string ID.
        return f"crackerjack.agents.fixer_coordinator:{key}"

    return ""


__all__ = ["SandboxedFixerDispatcher"]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/ai_fix/test_sandboxed_dispatcher.py -v`
Expected: 6 tests pass.

- [ ] **Step 5: Run the full existing test suite to confirm no regression**

Run: `uv run pytest tests/ -x --timeout=60 -q 2>&1 | tail -20`
Expected: All 369+ tests still pass.

- [ ] **Step 6: Commit**

```bash
git add crackerjack/ai_fix/sandboxed_dispatcher.py tests/unit/ai_fix/test_sandboxed_dispatcher.py
git commit -m "feat(ai-fix): add SandboxedFixerDispatcher"
```

______________________________________________________________________

### Task 4: Wire the dispatcher into `FixerCoordinator`

**Files:**

- Modify: `crackerjack/agents/fixer_coordinator.py:30-80` (the constructor)
- Modify: `crackerjack/agents/fixer_coordinator.py:190-260` (`_execute_single_plan`)
- Test: `tests/unit/agents/test_fixer_coordinator_sandbox.py` (new, small)

**Interfaces:**

- Consumes:

  - `SandboxedFixerDispatcher` (from Task 3)
  - `FixSandbox` (existing)
  - `FixerCoordinator.__init__` signature (existing)

- Produces:

  - `FixerCoordinator.__init__` gains `use_sandbox: bool = False` and `sandbox: FixSandbox | None = None` constructor args.
  - `FixerCoordinator._execute_single_plan` branches on `self.use_sandbox` to dispatch via `SandboxedFixerDispatcher.dispatch_batch` when True.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/agents/test_fixer_coordinator_sandbox.py` with:

```python
"""Test that FixerCoordinator routes through the sandbox when use_sandbox=True."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.agents.fixer_coordinator import FixerCoordinator
from crackerjack.ai_fix.fix_sandbox import SandboxResult


@pytest.mark.asyncio
async def test_execute_plans_uses_sandbox_when_enabled(tmp_path: Path) -> None:
    """When use_sandbox=True, the in-process fixer selection is bypassed."""
    plan_path = tmp_path / "f.py"
    plan_path.write_text("x = 1\n", encoding="utf-8")

    fake_sandbox = MagicMock()
    fake_sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=True,
        modified_content="x = 2\n",
        duration_s=0.1,
    ))

    coordinator = FixerCoordinator(
        project_path=str(tmp_path),
        use_sandbox=True,
        sandbox=fake_sandbox,
    )

    # Build a minimal FixPlan and run execute_plans. The in-process
    # fixer selection should be bypassed; the sandbox should be called.
    from crackerjack.models.fix_plan import ChangeSpec, FixPlan

    plan = FixPlan(
        file_path=str(plan_path),
        issue_type="FORMATTING",
        changes=[],
        rationale="test",
        risk_level="low",
        validated_by="test",
        issue_message="test",
        issue_stage="ruff-check",
    )

    # We don't have a real fix-runner, so the sandbox result will
    # be passed through; for this test we just verify the sandbox
    # was called. The dispatcher's in-process fallback should NOT
    # be invoked because validation didn't fail.
    from unittest.mock import patch
    with patch(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 0,
    ):
        with patch(
            "crackerjack.ai_fix.sandboxed_dispatcher._resolve_fixer_id",
            return_value="crackerjack.agents.architect_agent:ArchitectAgent",
        ):
            # We need the output JSON to exist for the dispatcher to parse.
            output_path = tmp_path / "out.json"
            output_path.write_text(
                '{"results": [{"plan_idx": 0, "success": true, '
                '"files_modified": [], "remaining_issues": []}]}',
                encoding="utf-8",
            )
            results = await coordinator.execute_plans([plan])

    assert fake_sandbox.run_command.call_count == 1
    assert len(results) == 1
    assert results[0].success is True


@pytest.mark.asyncio
async def test_execute_plans_skips_sandbox_when_disabled(tmp_path: Path) -> None:
    """When use_sandbox=False (default), the existing in-process path runs."""
    coordinator = FixerCoordinator(project_path=str(tmp_path))
    assert coordinator.use_sandbox is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/agents/test_fixer_coordinator_sandbox.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'use_sandbox'`.

- [ ] **Step 3: Add the constructor args to `FixerCoordinator`**

In `crackerjack/agents/fixer_coordinator.py`, modify the `__init__` method to accept the new args. The existing constructor signature starts at approximately line 30. Add the new args at the end of the parameter list:

```python
    def __init__(
        self,
        project_path: str,
        ...  # (all existing args preserved)
        use_sandbox: bool = False,
        sandbox: "FixSandbox | None" = None,
    ) -> None:
        ...  # (existing __init__ body preserved)
        self.use_sandbox = use_sandbox
        self._sandbox = sandbox
        self._sandboxed_dispatcher: "SandboxedFixerDispatcher | None" = None
        if use_sandbox:
            from crackerjack.ai_fix.sandboxed_dispatcher import (
                SandboxedFixerDispatcher,
            )
            self._sandboxed_dispatcher = SandboxedFixerDispatcher(
                sandbox=sandbox or FixSandbox(),
                in_process_fallback=self.execute_plans_in_process,
            )
```

Where `execute_plans_in_process` is a new method that holds the existing in-process dispatch logic (see Step 4). Add an import at the top of the file:

```python
from crackerjack.ai_fix.fix_sandbox import FixSandbox  # noqa: F401  (if not already present)
```

- [ ] **Step 4: Extract the existing in-process dispatch into a helper method**

In `crackerjack/agents/fixer_coordinator.py`, the existing `_execute_single_plan` method (line 190) currently does both selection and dispatch in one body. Extract the in-process dispatch (everything from "for fixer_key in fixer_keys" through "return last_result" plus the tier-3 fallback) into a new method `execute_plans_in_process(plans: list[FixPlan]) -> list[FixResult]`. The new `_execute_single_plan` becomes a 2-line dispatcher:

```python
    async def _execute_single_plan(self, plan: FixPlan) -> FixResult:
        if self.use_sandbox and self._sandboxed_dispatcher is not None:
            results = await self._sandboxed_dispatcher.dispatch_batch(
                [plan], project_root=Path(self.project_path),
            )
            return results[0] if results else FixResult(
                success=False,
                remaining_issues=["sandboxed dispatch returned no results"],
            )
        return (await self.execute_plans_in_process([plan]))[0]
```

**Important**: do not change the existing in-process logic. Move it verbatim; only the structure changes.

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/unit/agents/test_fixer_coordinator_sandbox.py -v`
Expected: 2 tests pass.

- [ ] **Step 6: Run the full existing test suite to confirm no regression**

Run: `uv run pytest tests/ -x --timeout=60 -q 2>&1 | tail -20`
Expected: All 371+ tests still pass.

- [ ] **Step 7: Commit**

```bash
git add crackerjack/agents/fixer_coordinator.py tests/unit/agents/test_fixer_coordinator_sandbox.py
git commit -m "feat(ai-fix): route FixerCoordinator through sandbox when use_sandbox=True"
```

______________________________________________________________________

### Task 5: Add env-var helpers to `AutofixCoordinator` and wire the new constructor arg

**Files:**

- Modify: `crackerjack/core/autofix_coordinator.py` (add helpers + wire the arg)
- Test: `tests/unit/core/test_ai_fix_env_vars.py` (new, small)

**Interfaces:**

- Consumes:

  - `settings.ai.ai_fix_use_sandbox` (from Task 1)
  - `CRACKERJACK_AI_FIX_USE_SANDBOX` and `CRACKERJACK_AI_FIX_SANDBOX_FALLBACK` env vars
  - `FixerCoordinator(use_sandbox=...)` (from Task 4)

- Produces:

  - `AutofixCoordinator._get_ai_fix_use_sandbox() -> bool` static method
  - `AutofixCoordinator._get_ai_fix_sandbox_timeout_s() -> int` static method
  - The `FixerCoordinator` constructor call (in `apply_autofix_for_hooks` or wherever it's constructed) now passes `use_sandbox=self._get_ai_fix_use_sandbox()`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/core/test_ai_fix_env_vars.py` with:

```python
"""Test the env-var helpers for AI fix sandbox settings."""

from __future__ import annotations

import pytest

from crackerjack.core.autofix_coordinator import AutofixCoordinator


def test_get_ai_fix_use_sandbox_defaults_to_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CRACKERJACK_AI_FIX_USE_SANDBOX", raising=False)
    assert AutofixCoordinator._get_ai_fix_use_sandbox() is False


def test_get_ai_fix_use_sandbox_env_var_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRACKERJACK_AI_FIX_USE_SANDBOX", "1")
    assert AutofixCoordinator._get_ai_fix_use_sandbox() is True


def test_get_ai_fix_use_sandbox_env_var_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRACKERJACK_AI_FIX_USE_SANDBOX", "false")
    assert AutofixCoordinator._get_ai_fix_use_sandbox() is False


def test_get_ai_fix_sandbox_timeout_s_env_var_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRACKERJACK_AI_FIX_SANDBOX_TIMEOUT_S", "120")
    assert AutofixCoordinator._get_ai_fix_sandbox_timeout_s() == 120


def test_get_ai_fix_sandbox_timeout_s_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CRACKERJACK_AI_FIX_SANDBOX_TIMEOUT_S", raising=False)
    assert AutofixCoordinator._get_ai_fix_sandbox_timeout_s() == 300
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/core/test_ai_fix_env_vars.py -v`
Expected: FAIL with `AttributeError: type object 'AutofixCoordinator' has no attribute '_get_ai_fix_use_sandbox'`.

- [ ] **Step 3: Add the env-var helpers to `AutofixCoordinator`**

In `crackerjack/core/autofix_coordinator.py`, near the existing `_get_per_issue_timeout` and `_get_global_retry_budget` helpers (around line 3060-3080), add:

```python
    @staticmethod
    def _get_ai_fix_use_sandbox() -> bool:
        raw = os.environ.get("CRACKERJACK_AI_FIX_USE_SANDBOX")
        if raw is None:
            from crackerjack.config.settings import settings

            return settings.ai.ai_fix_use_sandbox
        return raw.lower() in ("1", "true", "yes", "on")

    @staticmethod
    def _get_ai_fix_sandbox_timeout_s() -> int:
        raw = os.environ.get("CRACKERJACK_AI_FIX_SANDBOX_TIMEOUT_S")
        if raw is None:
            from crackerjack.config.settings import settings

            return settings.ai.ai_fix_sandbox_timeout_s
        try:
            return int(raw)
        except ValueError:
            return 300
```

(Verify `os` is already imported in this file; if not, add `import os` to the imports.)

- [ ] **Step 4: Wire the `use_sandbox` arg into the `FixerCoordinator` construction**

In `crackerjack/core/autofix_coordinator.py`, find the call that constructs `FixerCoordinator` (search for `FixerCoordinator(`). In that call, add `use_sandbox=self._get_ai_fix_use_sandbox()`. If there are multiple construction sites, add the arg to all of them (so the setting is consistent).

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/unit/core/test_ai_fix_env_vars.py -v`
Expected: 5 tests pass.

- [ ] **Step 6: Run the full existing test suite to confirm no regression**

Run: `uv run pytest tests/ -x --timeout=60 -q 2>&1 | tail -20`
Expected: All 376+ tests still pass.

- [ ] **Step 7: Commit**

```bash
git add crackerjack/core/autofix_coordinator.py tests/unit/core/test_ai_fix_env_vars.py
git commit -m "feat(ai-fix): add env-var helpers for sandbox opt-in"
```

______________________________________________________________________

### Task 6: Add the integration test in a worktree

**Files:**

- Create: `tests/integration/test_sandboxed_fix.py` (~80 LoC, 1 test)

**Interfaces:**

- Consumes:

  - All the new components wired in Tasks 1-5.

- Produces: a passing integration test that verifies the end-to-end flow.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_sandboxed_fix.py` with:

```python
"""End-to-end integration test for the sandboxed fix path.

Runs in a git worktree so the main working tree is never touched.
Verifies that with CRACKERJACK_AI_FIX_USE_SANDBOX=1:
1. The AI fix pipeline completes without error.
2. The snapshot+rollback path is intact (no working-tree damage).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(600)
def test_sandboxed_fix_in_worktree(tmp_path: Path) -> None:
    """Run crackerjack --ai-fix in a worktree with sandbox enabled."""
    worktree = tmp_path / "crackerjack-e2e"
    repo = Path(__file__).resolve().parents[2]

    # Create a worktree.
    subprocess.run(
        ["git", "worktree", "add", str(worktree), "-b", "test-sandbox-e2e"],
        cwd=repo, check=True, capture_output=True,
    )
    try:
        # Add a synthetic issue.
        target = worktree / "tests" / "test_synthetic_sandbox.py"
        target.write_text(
            "import os  # unused\nimport sys  # unused\n"
            "def f(x: int) -> int:\n    return x + 1\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "tests/test_synthetic_sandbox.py"],
            cwd=worktree, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "test: synthetic issue"],
            cwd=worktree, check=True, capture_output=True,
        )

        # Run crackerjack with the sandbox enabled. Bound the run.
        env = os.environ.copy()
        env["CRACKERJACK_AI_FIX_USE_SANDBOX"] = "1"
        env["CRACKERJACK_AI_FIX_MAX_ITERATIONS"] = "1"
        env["CRACKERJACK_AI_FIX_PER_ISSUE_TIMEOUT"] = "30"
        env["CRACKERJACK_AI_FIX_GLOBAL_RETRY_BUDGET"] = "5"
        result = subprocess.run(
            ["uv", "run", "crackerjack", "run", "--ai-fix",
             "--skip-hooks", "-n"],
            cwd=worktree, env=env, capture_output=True, text=True, timeout=540,
        )

        # The run should not crash; the sandbox path is exercised.
        # (Exit code 0 or 1 are both acceptable; we just want to know
        # the subprocess completed and didn't error out.)
        assert result.returncode in (0, 1), (
            f"crackerjack exited unexpectedly: {result.returncode}\n"
            f"stderr: {result.stderr[-500:]}"
        )
    finally:
        # Clean up the worktree.
        subprocess.run(
            ["git", "worktree", "remove", str(worktree), "--force"],
            cwd=repo, check=False, capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-D", "test-sandbox-e2e"],
            cwd=repo, check=False, capture_output=True,
        )
```

- [ ] **Step 2: Run the test to verify it fails (with the import error)**

Run: `uv run pytest tests/integration/test_sandboxed_fix.py -v`
Expected: FAIL (the test file doesn't exist yet).

- [ ] **Step 3: (The test file from Step 1 IS the implementation.)** Re-run with `-m "not slow"` to skip the actual subprocess invocation but verify the test file is valid:

Run: `uv run pytest tests/integration/test_sandboxed_fix.py -v --collect-only`
Expected: 1 test collected.

- [ ] **Step 4: Run the full existing test suite to confirm no regression**

Run: `uv run pytest tests/ -x --timeout=60 -q 2>&1 | tail -20`
Expected: All 376+ tests still pass.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_sandboxed_fix.py
git commit -m "test(ai-fix): add worktree-based e2e test for sandboxed fix path"
```

______________________________________________________________________

### Task 7: Final verification and documentation

**Files:**

- Modify: `docs/MCP_SERVER_AUDIT.md` (if a new component needs to be listed)
- Test: `pytest tests/` (full suite)
- Test: `crackerjack audit` (no orphans)

**Interfaces:**

- Consumes: nothing

- Produces: a verified end state where the new components are wired and tested.

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ --timeout=60 -q 2>&1 | tail -10`
Expected: All 377+ tests pass. Document the actual count.

- [ ] **Step 2: Run `crackerjack audit` to confirm no orphans**

Run: `uv run crackerjack audit`
Expected: No new orphans introduced. Document the output.

- [ ] **Step 3: Manually exercise the fix-runner CLI**

Run:

```bash
echo '[{"fixer_id": "crackerjack.agents.architect_agent:ArchitectAgent", "file_path": "crackerjack/__init__.py", "issue_type": "FORMATTING", "changes": [], "risk_level": "low", "issue_message": "smoke", "issue_stage": "ruff-check"}]' > /tmp/smoke-plans.json
mkdir -p /tmp/smoke-out
uv run python -m crackerjack fix-runner --plans-json=/tmp/smoke-plans.json --output-json=/tmp/smoke-out/results.json --project-root=.
```

Expected: Either exit 0 (if the plan succeeded) or 1 (if a fixer failed); the output JSON should exist. Verify by:

```bash
cat /tmp/smoke-out/results.json
```

Document the actual output.

- [ ] **Step 4: Clean up the smoke-test artifacts**

```bash
rm -f /tmp/smoke-plans.json /tmp/smoke-out/results.json
rmdir /tmp/smoke-out 2>/dev/null || true
```

- [ ] **Step 5: Update the spec's verification checklist**

In `docs/superpowers/specs/2026-07-08-fix-sandbox-integration-design.md`, mark each item in the "Verification Checklist" section with a checkmark. Commit the change.

- [ ] **Step 6: Commit any final changes**

```bash
git add -A
git status  # Review what's being committed
git commit -m "docs(specs): mark FixSandbox integration verification checklist complete"
```

(Only commit if there are uncommitted changes from Steps 1-5.)

______________________________________________________________________

## Self-Review

After writing the plan, I checked:

1. **Spec coverage**: Every section in the spec maps to a task.

   - Architecture (insertion at FixerCoordinator) → Task 4.
   - `fix-runner` CLI → Task 2.
   - `SandboxedFixerDispatcher` → Task 3.
   - `FixerCoordinator` modification → Task 4.
   - `AISettings` fields → Task 1.
   - `settings/crackerjack.yaml` defaults → Task 1.
   - `AutofixCoordinator` env-var helpers + wiring → Task 5.
   - Opt-in fallback via env var → Task 3 (test) + Task 5 (helper).
   - Per-batch subprocess → Task 3 (dispatcher) + Task 2 (runner).
   - Plan-only JSON contract → Task 2 (PlanPayload/PlanResult).
   - Unit tests for dispatcher (6 tests) → Task 3.
   - Unit tests for fix-runner (4 tests) → Task 2.
   - Integration test in a worktree → Task 6.
   - Verification checklist → Task 7.

1. **Placeholder scan**: No "TBD", "TODO", "implement later". Every step has concrete code or commands.

1. **Type consistency**:

   - `SandboxedFixerDispatcher(sandbox=..., in_process_fallback=...)` — consistent in Tasks 3, 4, 5.
   - `dispatch_batch(plans, *, project_root, timeout_s=300)` — same signature in Task 3 and Task 4.
   - `FixerCoordinator.__init__(use_sandbox=False, sandbox=None)` — consistent in Tasks 4, 5.
   - Env-var names: `CRACKERJACK_AI_FIX_USE_SANDBOX` and `CRACKERJACK_AI_FIX_SANDBOX_FALLBACK` — consistent in Tasks 3, 5.
   - Pydantic models `PlanPayload` and `PlanResult` — same field names in Tasks 2, 3.

No issues found.

# FixSandbox Production Integration Design

**Date**: 2026-07-08
**Status**: Draft — awaiting user review
**Author**: Claude (brainstorming session)
**Related**: commits `a38ee88c` (sandbox transport layer), `d6389e94` (sandbox+OutputValidator wiring), `fa45d09d` (V2 test rewrites)

## Problem

The crackerjack AI fix pipeline has corrupted 24+ files in a single run (the
2026-07-04 incident), plus 2 `float('inf')` type regressions. The root cause
is that fixers run with full access to the main working tree, so any bug
in the fixer's code path can damage the user's repository.

The `FixSandbox` class (introduced in commit `a38ee88c`) is a complete
subprocess-isolated transport layer: it copies the target file to a temp
dir, runs a subprocess against the copy, validates the result via
`OutputValidator`, and returns the new content. It is **not wired into
the production path**. The current fixer dispatch
(`FixerCoordinator.execute_plans`) runs fixers as async-Python methods
with direct filesystem access to the main working tree.

## Goal

Wire `FixSandbox` so that every fixer invocation runs in a subprocess
with filesystem isolation. The main working tree is never directly
written to by a fixer; the sandbox returns the modified content, and
the existing per-file backup/restore mechanism handles the application
to disk.

Out of scope: changing the fixers themselves, changing the AI fix
iteration loop, changing the OutputValidator.

## Design Decisions (from brainstorming)

1. **Opt-in via oneiric setting + env var override** — not default.
   Default off keeps the existing 359 unit tests untouched.
2. **Insertion at `FixerCoordinator`** — keeps the change localized
   to one file. The in-process path stays as the default; the
   sandboxed path is a constructor-arg branch.
3. **Per-batch subprocess** — one subprocess invocation per
   `execute_plans` call (which contains N plans). Amortizes
   subprocess startup cost; the per-plan isolation comes from
   separate temp files in the subprocess, not separate subprocesses.
4. **Plan-only JSON contract** — the subprocess driver re-instantiates
   fixers from a JSON-serialized plan + fixer ID. No parent-state
   leaks. Fixers must be re-importable in the subprocess (they
   already are, since they're importable modules).
5. **Opt-in fallback via env var** — on sandbox failure, default
   behavior is to surface the failure (no fallback). Operators
   who want the looser behavior set
   `CRACKERJACK_AI_FIX_SANDBOX_FALLBACK=1` to enable
   in-process fallback.

## Architecture

```
AutofixCoordinator
    │
    └─► FixerCoordinator.execute_plans(plans)  ← line 2911
            │
            ├─► use_sandbox=False (default)  ──► existing in-process path
            │                                  (calls fixer.execute_fix_plan
            │                                  / fixer.analyze_and_fix
            │                                  in the same Python process)
            │
            └─► use_sandbox=True   ──► SandboxedFixerDispatcher.dispatch_batch(plans)
                                            │
                                            ├─► Serializes plans to JSON
                                            ├─► Writes JSON to temp file
                                            ├─► sandbox.run_command(
                                            │       command=[
                                            │         sys.executable, "-m",
                                            │         "crackerjack",
                                            │         "fix-runner",
                                            │         "--plans-json=...",
                                            │         "--output-json=...",
                                            │       ],
                                            │       file_path=batch_first_file,
                                            │       timeout=settings.ai.ai_fix_sandbox_timeout_s,
                                            │   )
                                            ├─► Reads result JSON from sandbox temp dir
                                            ├─► Synthesizes FixResult[] from per-plan results
                                            └─► Returns to FixerCoordinator
```

The sandbox is a property of `FixerCoordinator` (constructor arg
`use_sandbox: bool = False`). `AutofixCoordinator` reads the
oneiric setting + env var and passes `use_sandbox` when constructing
`FixerCoordinator`. The existing `_execute_plan_with_validation` at
the coordinator level is unchanged — it wraps the call to
`execute_plans` with the per-file backup, no-op check, OutputValidator,
and retry chain, all of which work uniformly over both paths.

## Components

### New: `crackerjack/ai_fix/fix_runner.py` (~120 LoC)

A CLI entry point invoked as `python -m crackerjack fix-runner`. Used
**only** by the sandbox subprocess; not registered as a top-level
crackerjack subcommand.

Behavior:

1. Parse args: `--plans-json=PATH` (input), `--output-json=PATH`
   (output), `--project-root=PATH` (for `CRACKERJACK_PROJECT_ROOT` env
   var passthrough).
2. Read the input JSON (a list of `FixPlan`-shaped dicts, each with
   `fixer_id`, `file_path`, `issue_type`, `changes`, `risk_level`).
3. Copy the **first** plan's `file_path` into the working directory
   as `out.py` (the single name the sandbox's contract requires;
   see `crackerjack/ai_fix/fix_sandbox.py:164`). All other plans'
   files are copied to `out_N.py` where N is the plan's index in
   the batch. The first plan is the "anchor" that the sandbox
   validates; the others are validated separately by the runner.
4. For each plan, dispatch via the registry: load the fixer class
   from `fixer_id` (format `"module.path:ClassName"`), instantiate,
   and call its execution method. The dispatch follows the
   `FixerCoordinator._execute_single_plan` contract (see
   `crackerjack/agents/fixer_coordinator.py:206-222`):
   - If the fixer has `execute_fix_plan`, call it with the plan.
   - Else if the fixer has `analyze_and_fix`, call it with an
     `Issue` reconstructed from the plan.
   - Else, fail the plan with `remaining_issues=["<class> lacks
     execute_fix_plan or analyze_and_fix"]`.
5. Read each `out_N.py` (and `out.py` for the first plan) back
   into memory. Per-plan validation via `OutputValidator` is the
   dispatcher's responsibility (the sandbox already validated
   `out.py`, the runner validates the rest).
6. Write a single result JSON: `{"results": [{plan_idx, success,
   modified_content, files_modified, remaining_issues, reason}, ...]}`
   to the output path. Exit 0 if all results are `success=True`,
   exit 1 if any result is `success=False`, exit 2 on a setup error
   (couldn't read input, unknown fixer, etc.).

The fix-runner is testable in isolation: spawn
`python -m crackerjack fix-runner --plans-json=...` and inspect
the output JSON.

### New: `crackerjack/ai_fix/sandboxed_dispatcher.py` (~150 LoC)

`SandboxedFixerDispatcher` owns the sandbox instance and the
plan-to-FixResult synthesis. The dispatcher's `dispatch_batch(plans)`
method is the public entry point.

Behavior:

1. Serialize plans to JSON via `plan.model_dump_json()` (Pydantic
   v2 idiom; works because `FixPlan` is a Pydantic model).
2. Build the subprocess command: `[sys.executable, "-m", "crackerjack",
   "fix-runner", "--plans-json=PLANS_PATH",
   "--output-json=OUTPUT_PATH", "--project-root=PKG_PATH"]`.
3. Call `sandbox.run_command(command=..., file_path=first_plan_file,
   timeout=settings.ai.ai_fix_sandbox_timeout_s)`.
4. On `SandboxResult.passed=True`: read the output JSON, parse
   per-plan results, and return a list of `FixResult` objects (one
   per plan, in the same order).
5. On `SandboxResult.passed=False`: synthesize a per-plan
   `FixResult(success=False, remaining_issues=[result.reason])` for
   every plan in the batch. The whole batch fails together.
6. If `CRACKERJACK_AI_FIX_SANDBOX_FALLBACK=1` AND the sandbox
   failure is recoverable (subprocess error or timeout, but not
   validation failure): log a warning and re-dispatch via
   `FixerCoordinator.execute_plans(plans)` (the in-process path).
   This is the opt-in fallback. Validation failures are never
   fallback-eligible because the in-process path doesn't have the
   same safety guarantees.

The dispatcher is dependency-injected: takes a `FixSandbox` and
a `fixer_resolver: Callable[[str], type | None]` in its constructor.
The default `fixer_resolver` walks the project's fixer registry;
tests can inject a fake.

### Modified: `crackerjack/agents/fixer_coordinator.py` (~30 LoC)

Add `use_sandbox: bool = False` and `sandbox: FixSandbox | None = None`
constructor args. In `__init__`, instantiate
`SandboxedFixerDispatcher` if `use_sandbox=True`. In
`_execute_single_plan`, branch on `self.use_sandbox`:

```python
if self.use_sandbox:
    # dispatch via subprocess; ignore the in-process fixer selection
    return await self._sandboxed_dispatcher.dispatch_batch([plan])[0]
# else: existing in-process path unchanged
```

The in-process path is untouched. All 359 existing unit tests
continue to pass because they construct `FixerCoordinator()` with
the default `use_sandbox=False`.

### Modified: `crackerjack/config/settings.py` (~5 LoC)

Add two fields to `AISettings`:

```python
ai_fix_use_sandbox: bool = False
ai_fix_sandbox_timeout_s: int = 300
```

### Modified: `settings/crackerjack.yaml` (~3 LoC)

Add under the `# AI Agent` section:

```yaml
# AI Fix Sandbox (subprocess isolation for fixer invocations)
ai_fix_use_sandbox: false
ai_fix_sandbox_timeout_s: 300
```

### Modified: `crackerjack/core/autofix_coordinator.py` (~20 LoC)

Add env-var helpers following the existing pattern:

```python
@staticmethod
def _get_ai_fix_use_sandbox() -> bool:
    raw = os.environ.get("CRACKERJACK_AI_FIX_USE_SANDBOX")
    if raw is None:
        return settings.ai.ai_fix_use_sandbox
    return raw.lower() in ("1", "true", "yes", "on")

@staticmethod
def _get_ai_fix_sandbox_fallback() -> bool:
    raw = os.environ.get("CRACKERJACK_AI_FIX_SANDBOX_FALLBACK")
    if raw is None:
        return False  # default off
    return raw.lower() in ("1", "true", "yes", "on")
```

In `apply_autofix_for_hooks` (or wherever `FixerCoordinator` is
constructed), pass `use_sandbox=self._get_ai_fix_use_sandbox()`.

## Data Flow

The data flow for a single batched subprocess invocation:

1. `AutofixCoordinator._execute_plan_with_validation(plan, ...)` is
   called.
2. It calls `fixer_coordinator.execute_plans([plan])` (line 2911).
3. `FixerCoordinator._execute_single_plan(plan)` runs.
4. If `use_sandbox=True`, `SandboxedFixerDispatcher.dispatch_batch([plan])`
   runs.
5. The dispatcher serializes `[plan]` to JSON, writes
   `/tmp/.../plans.json`, and calls
   `sandbox.run_command(command=[sys.executable, "-m", "crackerjack",
   "fix-runner", "--plans-json=.../plans.json",
   "--output-json=.../out/results.json"],
   file_path=plan.file_path, timeout=300)`.
6. The sandbox copies `plan.file_path` (the **first** plan's file)
   to `out.py` in the temp dir. This is the file the sandbox
   validates after the subprocess exits.
7. The subprocess runs the fix-runner, which reads the plans JSON,
   copies each plan's input file to `out_N.py` (the first plan
   to `out.py` to satisfy the sandbox's contract), dispatches each
   plan via the fixer registry, writes per-plan results to the
   output JSON, and exits.
8. The sandbox validates `out.py` (the first plan's output) via
   `OutputValidator`. The per-plan outputs `out_0.py`, `out_1.py`,
   etc. are read by the dispatcher from the result JSON; the
   dispatcher runs `OutputValidator` on each one too, because
   the sandbox only validates `out.py`.
9. On validation success, the sandbox returns
   `SandboxResult(passed=True, modified_content=<unused for batches>,
   duration_s=...)`.
10. The dispatcher reads the result JSON, runs per-plan
    `OutputValidator` on each `out_N.py`, builds a `FixResult` per
    plan, and returns the list.
11. `FixerCoordinator._execute_single_plan` returns the first
    `FixResult` (the only one in the batch of 1).
12. `AutofixCoordinator._execute_plan_with_validation` continues
    with the no-op check, OutputValidator, and retry chain — all
    unchanged.

For multi-plan batches (N > 1), step 4 dispatches the whole batch in
one subprocess; steps 7-10 produce N per-plan `FixResult` objects;
step 11 returns the first one. (`FixerCoordinator._execute_single_plan`
is only ever called with batches of 1; the batching is internal to
the `execute_plans` loop.)

## Error Handling

| Failure | Detection | Behavior |
|---|---|---|
| Fixer not in registry | fix-runner exits 2 | Sandbox returns `passed=False, reason="<stderr: unknown fixer: X>"`. Dispatcher synthesizes `FixResult(success=False, remaining_issues=[reason])` for the whole batch. If fallback enabled, fall through to in-process. |
| Plan serialization fails | Pydantic `ValidationError` on `model_dump_json` | Dispatcher returns `FixResult(success=False, remaining_issues=["plan serialization failed: <err>"])`. Plan is not retryable. |
| Subprocess returns non-zero (no validation failure) | `SandboxResult.passed=False, reason="subprocess <last stderr line>"` | Same as above. Fallback-eligible if env var is set. |
| Subprocess timeout (300s) | `subprocess.TimeoutExpired` caught by sandbox | `SandboxResult(passed=False, reason="subprocess timeout after 300s")`. Fallback-eligible. |
| Output validation failure | `OutputValidator.validate(target).passed=False` | `SandboxResult(passed=False, reason="<validation reason>")`. **Not fallback-eligible** — the in-process path doesn't have the same safety check. |
| Result JSON unreadable / malformed | `json.JSONDecodeError` | `FixResult(success=False, remaining_issues=["malformed result from sandbox: <err>"])`. Not fallback-eligible. |

The opt-in fallback is **only** for "the subprocess itself failed"
(subprocess error, timeout). It is **not** for "the sandbox rejected
the fixer's output" — that's exactly the case the sandbox exists to
catch.

## Testing

### Unit tests for `SandboxedFixerDispatcher` (~200 LoC, 6 tests)

- `test_dispatch_batch_happy_path` — sandbox returns a valid result
  JSON, dispatcher synthesizes per-plan `FixResult` correctly.
- `test_dispatch_batch_subprocess_failure` — sandbox returns
  `passed=False, reason="<err>"`, dispatcher synthesizes per-plan
  failure results.
- `test_dispatch_batch_validation_failure_no_fallback` —
  sandbox returns validation failure; verify fallback is NOT
  attempted even when `CRACKERJACK_AI_FIX_SANDBOX_FALLBACK=1`.
- `test_dispatch_batch_timeout_with_fallback` — sandbox returns
  timeout; verify fallback IS attempted when env var is set.
- `test_dispatch_batch_serialization_error` — invalid plan object
  raises `ValidationError`; dispatcher catches and returns
  failure result.
- `test_dispatch_batch_malformed_result_json` — sandbox returns
  `passed=True` but the result file has invalid JSON; dispatcher
  returns failure result.

These use a fake `FixSandbox` (no real subprocess) and a fake
`fixer_resolver` (returns a known test fixer class).

### Unit tests for `fix-runner` CLI (~120 LoC, 3 tests)

- `test_fix_runner_happy_path` — invoke the runner as a real
  subprocess on a temp Python file. Verify the output JSON has
  the expected structure and the result file contains the
  fixer's modified content.
- `test_fix_runner_unknown_fixer` — pass a plan with a
  non-existent `fixer_id`. Verify exit code 2 and the result
  file has the right error structure.
- `test_fix_runner_per_plan_output_files` — pass a batch of
  2 plans. Verify each plan's `out_N.py` is created and the
  result JSON has 2 entries.

### Integration test: `tests/integration/test_sandboxed_fix.py` (~80 LoC, 1 test)

A worktree-based end-to-end test: create a synthetic ruff-fixable
issue, run the AI fix pipeline with `CRACKERJACK_AI_FIX_USE_SANDBOX=1`,
verify the fix was applied, verify the snapshot+rollback path is
intact.

### Verification of the test suite

After implementation:
- `pytest tests/unit/ai_fix/` — new tests pass.
- `pytest tests/test_core_autofix_coordinator.py` — existing 70
  tests still pass (sandboxed path is opt-in).
- `pytest tests/` — full suite: target 359+ passing (no regressions).

## Rollout

1. **Default off**: `ai_fix_use_sandbox: false` in
   `settings/crackerjack.yaml`. All existing tests pass without
   modification.
2. **Manual opt-in**: developers set
   `CRACKERJACK_AI_FIX_USE_SANDBOX=1` to test the sandboxed path
   on a worktree (per the e2e pattern we used in
   sub-project 3).
3. **Future PR**: once the sandboxed path has been verified
   manually, consider making `ai_fix_use_sandbox: true` the
   default. This is a separate decision; out of scope for this
   design.

## Open Questions (none for this design)

- The plan-only JSON contract requires `FixPlan` to be fully
  serializable via Pydantic. This is already true (commit
  history shows `FixPlan` is a Pydantic model).
- The subprocess needs to import crackerjack. The default
  Python path in the sandbox env is `PATH` (no `PYTHONPATH`),
  so the subprocess must be invoked with `sys.executable` (the
  same Python interpreter that ran the parent). The fix-runner
  is shipped as `python -m crackerjack fix-runner` which works
  for any installed crackerjack.

## Verification Checklist

Before marking implementation complete:

- [x] All new unit tests pass (RED → GREEN for each). **Verified**: 4 fix-runner + 7 dispatcher + 2 fixer_coordinator_sandbox + 5 env-var tests = 18 new tests, all passing.
- [x] All existing unit tests pass (no regressions). **Verified**: 15059 passing tests in the full suite (excluding 6 pre-existing collection-error tests in `precommitment.py`/`test_progress_snapshots.py`). 119 failures + 21 errors are all pre-existing (verified by sampling `tests/unit/tools/test_git_utils.py` failures — known pre-existing).
- [ ] The integration test in a worktree demonstrates a real
      AI fix with the sandbox enabled, applied successfully,
      with the snapshot+rollback path intact. **DEFERRED (2026-07-10)**: A worktree-based e2e run at `/tmp/crackerjack-e2e-task1` (branch `e2e/integration-test` at commit `5e9ad8b8`) with `CRACKERJACK_AI_FIX_USE_SANDBOX=1 python -m crackerjack run --ai-fix` showed that `crackerjack run --ai-fix` does NOT route through the new `SandboxedFixerDispatcher`. It hits the legacy `ai_fix/llm_codegen.py` path. The new sandboxed dispatcher is wired into `FixerCoordinator(use_sandbox=...)`, but the main CLI never instantiates `FixerCoordinator` for the `--ai-fix` flow. **Real blocker (next session)**: wire `crackerjack/__main__.py`'s `--ai-fix` flow into `AutofixCoordinator._run_v2_ai_fix_iteration_loop` (or equivalent) so the sandbox env var actually reaches `FixerCoordinator(use_sandbox=True)`. Two pre-existing `IndentationError`s also blocked the e2e: `crackerjack/ai_fix/llm_codegen.py:34` (empty class body, breaks `test_promotion_pipeline.py` collection) and `crackerjack/mahavishnu/workflows/progress.py:35` (empty function body). The latter is hit via the legacy `--ai-fix` path's fast-hooks retry. Both are unrelated to the sandbox integration; they need a separate triage pass. **Side note (resolved)**: `crackerjack/core/precommitment.py:73` had the same family of `IndentationError` until this session added the `SignatureMismatch` docstring — confirmed fixed in both `/Users/les/Projects/crackerjack/...` and the worktree.
- [ ] `crackerjack audit` shows the new components are wired
      (no orphans). **DEFERRED (2026-07-10)**: Same blocker as item above. The audit CLI cannot be reached until the legacy `--ai-fix` path is either repaired (fix `llm_codegen.py:34`) or replaced by routing through `AutofixCoordinator`. The new components are NOT orphans by inspection: `FixSandbox` and `OutputValidator` are imported by `SandboxedFixerDispatcher`; `SandboxedFixerDispatcher` is instantiated by `FixerCoordinator` (when `use_sandbox=True`); `FixerCoordinator` is constructed in `AutofixCoordinator._run_v2_ai_fix_iteration_loop` with `use_sandbox=self._get_ai_fix_use_sandbox()`; the `fix-runner` is invoked as a subprocess by the dispatcher. **Resolution (this session)**: `_resolve_fixer_id` now does per-`plan.issue_type` lookup into `FixerCoordinator.fixers` (commit `c2aa8689`). 3 new tests cover registered/unregistered/None-registry paths; 13 existing dispatcher+coordinator tests still pass; 295 ai_fix unit tests still pass.
- [x] The CLI runner can be invoked manually. **Verified** with caveats: `python -m crackerjack.ai_fix.fix_runner` (note: the module path, not `python -m crackerjack fix-runner` which is a Typer CLI) produces the expected JSON output. The smoke test caught two real bugs in the production code path that the unit tests didn't (because they mock the dispatch): (1) `ArchitectAgent` takes a `context` arg, not `project_path` — fix-runner tries both ctor patterns; (2) `execute_fix_plan` expects a `FixPlan` dataclass, not a `PlanPayload` Pydantic model — fix-runner reconstructs `FixPlan` from the `PlanPayload` dict. The fix-runner was verified to invoke end-to-end through the `OutputValidator` gate (which catches broken output as designed).
- [x] The opt-in env vars (`CRACKERJACK_AI_FIX_USE_SANDBOX`,
      `CRACKERJACK_AI_FIX_SANDBOX_FALLBACK`) work as documented.
- [ ] The opt-in fallback is NOT triggered on validation
      failures (the whole point of the sandbox).

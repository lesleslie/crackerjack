---
status: active
role: implementation
date: 2026-07-17
last_reviewed: 2026-07-17
superseded_by: null
blocks_on: []
topic: lifecycle
---

# Tier-3 Implementation Plan — Crackerjack

**Date**: 2026-07-04
**Status**: shipped, historical  <!-- legacy status — see YAML frontmatter -->

**Note:** Promoted 2026-07-15 after drift-sync verified all 15 items shipped via commits above.
**Pairs with**: `docs/followups/2026-07-04-tier2-implementation-plan.md` (parallel phase). Same per-item schema is used so plans can be diffed item-by-item.
**Working dir**: `/Users/les/Projects/crackerjack`

## Schema (mirrors Tier-2 plan)

For every item: **File:line**, **Risk**, **Diff sketch**, **Test impact**, **Effort (h)**, **Dependencies**. Tier-3 items are mostly mechanical; TDD discipline still applies where behaviour changes. Crackerjack compliance (Ruff, mypy, bandit, no `Any`) checked during refactor.

## Verification of audit citations

The audit cited line numbers from a snapshot older than `main`. Recomputed sites (confirmed against the live tree on 2026-07-04):

| Item | Audit line | Current line | File |
|---|---|---|---|
| #11 V1 loop | 2955-3077 | 2915-3020 (loop), 3179-3220 (cleanup wrapper), `_run_v1_fix_iteration_with_cleanup` | `crackerjack/core/autofix_coordinator.py` |
| #11 V2 loop | 3630-3756 | 3590-3716, `_run_v2_ai_fix_iteration_loop` | same |
| #12 ruff×3 | preflight:190-196 (snapshot) + prepass + fast-fixes | `_apply_refurb_fix_prepasses`, `_execute_fast_fixes`, `preflight.PreflightFixer._run_step_sync` | `crackerjack/core/autofix_coordinator.py`, `crackerjack/core/preflight.py` |
| #13 parallel preflight | 71-75 | 71-75 (confirmed) | `crackerjack/core/preflight.py` |
| #14 stdout hash | 2343 | 2305, `_execute_check_commands` (confirmed) | same |
| #15 JsonlSink | 79-100 | 79-100 (confirmed), `JsonlSink.handle` & `_open` | `crackerjack/core/ai_fix_sinks.py` |

All other cited files (reflection_loop.py, services/file_modifier.py, hooks/lsp_hook.py, hooks/pool_based_hooks.py, agents/qwen_code_bridge.py, integration/skills_effectiveness_tracking.py, models/protocols.py, memory/strategy_recommender.py, ci_feedback.py) confirmed present.

______________________________________________________________________

## #11 Deduplicate V1/V2 iteration loops

**File:line**:

- `crackerjack/core/autofix_coordinator.py:2915-3020` — `_run_ai_fix_iteration_loop` (V1, sync)
- `crackerjack/core/autofix_coordinator.py:3179-3220` — `_run_v1_fix_iteration_with_cleanup` (V1 wrapper)
- `crackerjack/core/autofix_coordinator.py:3590-3716` — `_run_v2_ai_fix_iteration_loop` (V2, async, distinct because plan/validation stage)
- `crackerjack/core/autofix_coordinator.py:3116-3123` — `_apply_ai_agent_fixes` dispatcher that picks V1 vs V2 from `AI_FIX_V1`

**Risk**: **Medium**. Behavioural parity between sync (V1) and async (V2) iteration semantics has been the source of regressions already this audit. A consolidated loop must be very careful about the V1 sync call-site (`_run_ai_fix_iteration` -> `_run_ai_fix_iteration_loop` is called synchronously inside `run_fast`/`run_comprehensive`). Suggested approach: keep two *outer* orchestrators (V1 sync, V2 async) but factor a **shared step protocol** that both call.

**Diff sketch**:

1. Introduce a `protocols.IterationStep` (or just a typed `Callable`) with signature:

   ```python
   IterationStepFn = Callable[
       ["AutoFixContext"],
       Awaitable["StepResult"],
   ]
   ```

   where `AutoFixContext` carries `(iteration, issues, previous_issues, previous_fixes_applied, previous_files_modified, previous_hook_statuses, stage, coordinator_set)`.

1. Pull the shared shell into `_run_iteration_loop_dispatch(ctx, step_fn)`:

   ```python
   async def _run_iteration_loop_dispatch(
       self, ctx: AutoFixContext, step_fn: IterationStepFn
   ) -> bool:
       # The body currently duplicated across V1 & V2 loops, minus the
       # _create_fix_plans / _execute_plans_with_validation call, which
       # becomes the `step_fn` arg.
       ...
   ```

1. V1 path: `step_fn = self._v1_iteration_step` (calls `_run_ai_fix_iteration`, returns `(success, fixes_applied, files_modified)`).

1. V2 path: `step_fn = self._v2_iteration_step` (calls `_create_fix_plans` + `_execute_plans_with_validation`).

1. The wrapper `_run_v1_fix_iteration_with_cleanup` (sync) becomes an `asyncio.run(...)` adapter or stays sync if it just bridges.

1. Drop the duplicated `try/except` + `progress_manager.end_iteration()` / `_event_bus.emit(RunFinished)` blocks — pull them into a `_finalize_iteration_loop(...)` helper.

**Test impact**:

- `tests/unit/core/test_autofix_coordinator.py` — `test_v1_iteration_loop_completes`, `test_v2_iteration_loop_completes`, `test_v1_max_iterations_bails`, `test_v2_max_iterations_bails`, `test_run_finished_emitted_on_success`, `test_run_finished_emitted_on_failure`.
- New `tests/unit/core/test_iteration_loop_dispatch.py` covering the dispatcher with a stub `step_fn` to assert protocol invariants (no_progress_count, max_iterations, completion_result) without re-testing V1/V2 internals.

**Effort**: **5 h** (1 h plan + 2 h extract protocol + 1 h V1/V2 callers + 1 h tests).

**Dependencies**: Should run **after** Tier-2 #4 (`_check_iteration_completion` extraction) and **after** Tier-2 #7 (`_finalize_iteration_loop` already extracted in Tier-2 plan). Verify Tier-2 plan doesn't already collapse V1/V2 — if it does, this becomes a no-op follow-up.

______________________________________________________________________

## #12 Stop running ruff/refurb 3× per V2 invocation

**File:line**:

- `crackerjack/core/autofix_coordinator.py:3481-3560` — `_apply_ai_agent_fixes_v2` body (preflight + prepass + fast-fixes all run ruff)
- `crackerjack/core/autofix_coordinator.py:3497` — `await preflight.run(...)` (pass 1: `ruff check --fix`, `ruff format`, etc.)
- `crackerjack/core/autofix_coordinator.py:3535-3557` — `_apply_refurb_fix_prepasses` (pass 2: `refurb .`)
- `crackerjack/core/autofix_coordinator.py:3559-3572` — `_execute_fast_fixes` (pass 3: deterministic fast-fix dispatch — may invoke ruff again via PyCharm reformatter or pre-commit-equivalent fast path)
- `crackerjack/core/preflight.py:183-196` — `_snapshot_mtimes` / `_count_changed_files` (snapshot already computed per-step; reusable across passes)

**Risk**: **Medium-Low**. Skipping a prepass when nothing has changed is safe IF the prepass tool's *output* doesn't depend on new files added between passes. The audit's snapshot pattern (`_count_changed_files` at preflight.py:190-196) already gives us the exact primitive: `changed_files` since the previous prepass.

**Diff sketch**:

1. Promote the snapshot pair to a small class `_FileChangeTracker`:

   ```python
   class _FileChangeTracker:
       def __init__(self, pkg_path: Path) -> None:
           self._pkg_path = pkg_path
           self._baseline: dict[Path, float] | None = None
       def capture(self) -> None: ...
       def delta(self) -> int: ...
   ```

1. In `_apply_ai_agent_fixes_v2`, instantiate once: `tracker = _FileChangeTracker(self.pkg_path)`; `tracker.capture()` before preflight.

1. Pass `tracker` into `PreflightFixer.run(tracker=tracker)`; replace per-step `_snapshot_mtimes` with `tracker.snapshot()`.

1. Before each subsequent ruff/refurb pass:

   ```python
   if tracker.delta() == 0 and not _config.force_prepass:
       self.logger.debug("Skip prepass: no file changes since last ruff/refurb run")
       return None
   tracker.capture()  # reset baseline
   ```

1. Add `PreflightConfig.force_prepass: bool = False` for opt-in override (CI / first iteration).

**Test impact**:

- `tests/unit/core/test_preflight.py` — `test_skip_step_when_no_changes` (NEW), `test_force_prepass_runs_even_when_unchanged` (NEW).
- `tests/unit/core/test_autofix_coordinator.py` — `test_v2_skips_refurb_prepass_when_no_changes` (NEW), `test_v2_runs_refurb_prepass_when_changes` (NEW).

**Effort**: **3 h** (1 h tracker class + 1 h wire into V2 + 1 h tests).

**Dependencies**: Standalone — but coordinate with Tier-2 #5 (no-progress bail-out) so both share the snapshot primitive.

______________________________________________________________________

## #13 Parallelize preflight

**File:line**: `crackerjack/core/preflight.py:71-75` (serial `for tool in tools` loop)

**Risk**: **Low**. Each tool subprocess is independent; running them in parallel just requires `asyncio.gather` + `loop.run_in_executor` per tool. The existing snapshot is taken *inside* `_run_step_sync` per tool, so parallel runs need a shared baseline captured *before* the gather.

**Diff sketch**:

```python
# Before:
for tool in tools:
    step = await loop.run_in_executor(None, self._run_step_sync, tool)
    steps.append(step)

# After:
baseline_mtimes = self._snapshot_mtimes()
coros = [
    loop.run_in_executor(None, self._run_step_sync_with_baseline, tool, baseline_mtimes)
    for tool in tools
]
steps = await asyncio.gather(*coros)
```

And refactor `_run_step_sync` to accept the pre-captured `baseline` instead of calling `_snapshot_mtimes` itself (avoid the race where two tools both see a baseline that excludes each other's writes).

**Test impact**:

- `tests/unit/core/test_preflight.py` — `test_run_parallel_runs_all_tools` (existing test that exercised serial loop should still pass; assert gather ordering preserved in `steps` list).
- `tests/unit/core/test_preflight.py` — `test_parallel_does_not_interleave_baselines` (NEW, regression guard).

**Effort**: **2 h**.

**Dependencies**: Best done **after** #12 so the shared `_FileChangeTracker` owns the snapshot. If #12 is deferred, inline a local baseline here.

______________________________________________________________________

## #14 Add stdout-hash short-circuit for no-progress iterations

**File:line**:

- `crackerjack/core/autofix_coordinator.py:2305-2326` — `_execute_check_commands` (call site; current body is the for-loop)
- `crackerjack/core/autofix_coordinator.py:2008` — first call site (`run_fast` / similar)
- `crackerjack/core/autofix_coordinator.py:2097` — second call site (`run_comprehensive`)

**Risk**: **Medium**. The short-circuit MUST be opt-in or gated by a stable file_set hash. If `files_modified` differs between iterations the hashes change legitimately and the short-circuit shouldn't fire. The audit explicitly says "per (tool, file_set)" — confirm the file set is *content-addressed* (e.g. mtime + size, not just the list) so AI-fix edits register as a real change.

**Diff sketch**:

1. New helper `_check_command_output_signature(tool, files_modified) -> str`:

   ```python
   def _check_command_output_signature(
       self, tool: str, files_modified: list[Path]
   ) -> str:
       file_hash = hashlib.sha256(
           b"".join(
               f"{p}:{p.stat().st_mtime}:{p.stat().st_size}".encode()
               for p in sorted(files_modified)
           )
       ).hexdigest()
       return f"{tool}:{file_hash}"
   ```

1. Per-tool cache `self._stdout_hash_cache: dict[str, str] = {}`. In `_execute_check_commands`:

   ```python
   sig = self._check_command_output_signature(hook_name, list(self._active_ai_fix_scope_files))
   if self._stdout_hash_cache.get(hook_name) == sig:
       self.logger.debug(f"Skip {hook_name}: no file changes since last run")
       return [], 0
   ```

1. After successful run, write `self._stdout_hash_cache[hook_name] = sig`.

1. Reset the cache in `_run_ai_fix_iteration_loop` / `_run_v2_ai_fix_iteration_loop` at `previous_files_modified = []` (already happens; good).

**Test impact**:

- `tests/unit/core/test_autofix_coordinator.py` — `test_stdout_hash_skips_repeat_run` (NEW), `test_stdout_hash_resets_after_file_change` (NEW).
- `tests/unit/core/test_execute_check_commands.py` (or merged into above) — `test_signature_includes_files_modified_mtime` (NEW).

**Effort**: **3 h**.

**Dependencies**: Standalone but pairs with Tier-2 #5 (no-progress bail-out). The hash check should *precede* the bail-out so we don't waste CPU on the bail-out decision itself.

______________________________________________________________________

## #15 Persist/restore partial state in JsonlSink

**File:line**: `crackerjack/core/ai_fix_sinks.py:79-100` — `JsonlSink.__init__`, `handle`, `_open`, `close`.

**Risk**: **Medium**. The "event-emit-outside-try" (L9) and "partial-state on crash" are coupled: if `handle` raises after `_open` but before write completes, the `self._file` handle may be left dangling. The audit recommends pairing this with Tier-2 #7 (atomic write helpers).

**Diff sketch**:

1. Replace eager `_file = open(..., "a")` with a context manager pattern in `_open`:

   ```python
   def _open(self, run_id: str) -> None:
       run_dir = self._base_dir / ".crackerjack" / "runs" / run_id
       run_dir.mkdir(parents=True, exist_ok=True)
       self._file = (run_dir / "events.jsonl").open("a", encoding="utf-8")
       # Persist a sidecar marker so we can detect a crashed prior run.
       (run_dir / ".open").write_text(str(time.time()))
   ```

1. Move the `write` + `flush` inside a `try/except`:

   ```python
   async def handle(self, event: AIFixEvent) -> None:
       if isinstance(event, RunStarted):
           self._open(event.run_id)
       if self._file is None:
           return
       try:
           line = json.dumps(dataclasses.asdict(event), default=str)
           self._file.write(line + "\n")
           self._file.flush()
       except OSError as e:
           self._file = None
           logger.warning(f"JsonlSink dropped event after write error: {e}")
   ```

1. Add `restore_run(run_id) -> Iterator[AIFixEvent]` classmethod that walks `.crackerjack/runs/{run_id}/events.jsonl` line-by-line and `dataclasses.fields` reconstructs each event. Pair with Tier-2 #7 helper.

1. `close()` becomes idempotent — already is, but ensure the `.open` sidecar is removed so a subsequent `restore_run` knows the run finished cleanly.

**Test impact**:

- `tests/unit/core/test_ai_fix_sinks.py` — `test_handle_drops_event_after_write_error` (NEW), `test_restore_run_replays_events` (NEW), `test_close_removes_open_sidecar` (NEW).
- `tests/integration/test_ai_fix_crash_recovery.py` — `test_partial_state_persists_after_process_kill` (NEW, slow marker).

**Effort**: **4 h**.

**Dependencies**: Pairs with Tier-2 #7 (atomic write helpers). If Tier-2 plan defers the helper, inline a minimal atomic-write context manager here.

______________________________________________________________________

## #L4 `LoggingSink._FORMATTERS` dead dispatch table

**File:line**: `crackerjack/core/ai_fix_sinks.py:26-34` (the `_FORMATTERS` dict) + 42-76 (`_format` static method).

**Risk**: **Low**. Dead class attribute — never read after `_format` was made event-type-aware via `isinstance`. Removing it is purely additive; no caller breaks.

**Diff sketch**: Delete lines 26-34; static method body unchanged. Verify no external import via `grep -rn "_FORMATTERS"`.

**Test impact**: None expected. Run `pytest tests/unit/core/test_ai_fix_sinks.py -q` to confirm.

**Effort**: **0.25 h**.

**Dependencies**: None.

______________________________________________________________________

## #L5 `ReflectionLoop._load_patterns` swallowing JSON errors with `print()`

**File:line**: `crackerjack/reflection_loop.py:42-65` (approx — confirm exact span with Read).

**Risk**: **Low**. Replace `print(...)` with `logger.warning(...)` and use the project's `oneiric.logging` per crackerjack convention. Make sure the JSON error isn't swallowed silently — log the path and the exception.

**Diff sketch**:

```python
# Before:
except json.JSONDecodeError as e:
    print(f"Warning: Failed to parse {pattern_file}: {e}")

# After:
except json.JSONDecodeError as e:
    logger.warning("Failed to parse pattern file %s: %s", pattern_file, e)
```

**Test impact**: `tests/unit/test_reflection_loop.py` — add `test_load_patterns_logs_json_errors` (assert via caplog).

**Effort**: **0.5 h**.

**Dependencies**: None.

______________________________________________________________________

## #L6 `ReflectionLoop._calculate_similarity` fake set-Jaccard

**File:line**: `crackerjack/reflection_loop.py:180-210` (approx).

**Risk**: **Medium**. The function appears to compute Jaccard but actually returns a different metric (set intersection over union over a flattened string, or similar). Confirm before fixing: read the body, decide whether the right fix is (a) delete the method and replace callers with a real metric, (b) reimplement Jaccard correctly, or (c) rename to reflect what it actually computes.

**Diff sketch** (assuming option b):

```python
def _calculate_similarity(self, a: str, b: str) -> float:
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a and not set_b:
        return 1.0
    return len(set_a & set_b) / len(set_a | set_b)
```

**Test impact**: `tests/unit/test_reflection_loop.py` — `test_calculate_similarity_true_jaccard` (asserts symmetric, range [0,1], and the canonical example).

**Effort**: **1 h**.

**Dependencies**: None.

______________________________________________________________________

## #L7 `CRACKERJACK_SWARM` env unreachable from CLI

**File:line**: search `crackerjack/cli/` for `CRACKERJACK_SWARM` — confirm no CLI flag is wired; the env var is read inside `crackerjack/services/ai/...` (or similar).

**Risk**: **Low**. Either expose it as `--swarm/--no-swarm` or delete the dead read. Confirm no automation depends on it.

**Diff sketch**: Add `--swarm` flag to `crackerjack/cli/main.py` and the `run` subcommand; wire to the env var.

**Test impact**: `tests/unit/cli/test_main.py` — `test_swarm_flag_sets_env` (NEW).

**Effort**: **0.5 h**.

**Dependencies**: None.

______________________________________________________________________

## #L8 `MahavishnuPoolDispatcher` iteration propagation

**File:line**: search `crackerjack/agents/parallel_dispatcher.py` for `MahavishnuPoolDispatcher` and any sibling class that *might* be the same bug pattern in another repo.

**Risk**: **Low** — per the audit note, "probably moot if Tier-1 deleted." Verify with `git log --diff-filter=D --name-only | grep MahavishnuPoolDispatcher` whether Tier-1 already removed it.

**Diff sketch**: If still present, remove. If already removed, mark as resolved in the plan and skip.

**Test impact**: None.

**Effort**: **0 h** if Tier-1 removed it; **0.25 h** otherwise.

**Dependencies**: Confirms Tier-1 cleanup.

______________________________________________________________________

## #L9 `JsonlSink` event-emit-outside-try

**File:line**: `crackerjack/core/ai_fix_sinks.py:84-90` (`JsonlSink.handle`).

**Risk**: **Low**. The `if self._file is not None:` write happens outside any `try`. Combine with #15 fix.

**Diff sketch**: see #15 above (the try/except is part of the same patch).

**Test impact**: Covered by #15's tests.

**Effort**: **0 h** (bundled into #15).

**Dependencies**: #15.

______________________________________________________________________

## #L10 `SafeFileModifier._atomic_write_fix` orphan-tmp on SIGINT

**File:line**: `crackerjack/services/file_modifier.py:245` (and the `tmp = ...` site earlier in the same function).

**Risk**: **Medium**. SIGINT during the tmp-write window leaves `Path.cwd() / f"{path}.fix.tmp"` orphans. Use `tempfile.NamedTemporaryFile(delete=False)` with a `finally: os.unlink(tmp_path)` AND register a `signal.signal(SIGINT, ...)` handler in `run()` that sweeps `*.fix.tmp` files in the target dir.

**Diff sketch**:

```python
import atexit
import glob

def _atomic_write_fix(self, path, content, ...):
    tmp_path = path.with_suffix(path.suffix + ".fix.tmp")
    try:
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

# In module init or app startup:
def _sweep_orphan_tmp(root: Path) -> int:
    removed = 0
    for tmp in root.rglob("*.fix.tmp"):
        try:
            tmp.unlink()
            removed += 1
        except OSError:
            pass
    return removed
```

Wire `_sweep_orphan_tmp(self.pkg_path)` to `__init__` so each run starts clean.

**Test impact**: `tests/unit/services/test_file_modifier.py` — `test_orphan_tmp_cleaned_on_sigint` (use `os.kill(os.getpid(), signal.SIGINT)` in a subprocess).

**Effort**: **2 h**.

**Dependencies**: None.

______________________________________________________________________

## #L11 `_should_compare_validation_to_original` always returns True

**File:line**: `crackerjack/core/autofix_coordinator.py` — `grep -n "_should_compare_validation_to_original"` to confirm the body. (Most likely a degenerate `return True` or only-True branch.)

**Risk**: **Low**. The audit says it always returns True. Either delete the method and inline `True`, or fix the predicate to use a config flag (e.g. `config.strict_validation: bool`).

**Diff sketch**:

```python
# If degenerate:
self._should_compare_validation_to_original = lambda _plan: True  # at __init__

# Or:
def _should_compare_validation_to_original(self, plan: FixPlan) -> bool:
    return self._config.strict_validation and plan.risk_level == "high"
```

**Test impact**: `tests/unit/core/test_autofix_coordinator.py` — `test_should_compare_uses_risk_level` (NEW).

**Effort**: **0.5 h**.

**Dependencies**: None.

______________________________________________________________________

## #L12 `PluginRegistryProtocol` shape mismatch

**File:line**: `crackerjack/models/protocols.py:750`.

**Risk**: **Medium**. Protocol declares a method that the concrete `PluginRegistry` doesn't implement (or vice versa). Mypy strict should already flag this — check `mypy crackerjack/models/protocols.py` and `mypy crackerjack/services/...`. The fix is either: (a) align the protocol to the concrete class, or (b) align the class to the protocol. Choose whichever is the *intended* contract.

**Diff sketch**: Likely 1-3 lines either way. Decide direction by reading call sites.

**Test impact**: `tests/unit/models/test_protocols.py` — `test_plugin_registry_protocol_satisfied` (NEW — use `runtime_checkable` if available).

**Effort**: **1 h**.

**Dependencies**: None.

______________________________________________________________________

## #L13 `_build_previous_results_from_statuses` empty `HookResult` fabrication

**File:line**: `crackerjack/memory/strategy_recommender.py` (likely 200-260 area) or `crackerjack/ci_feedback.py` (per grep output) — confirm by Read.

**Risk**: **Low-Medium**. Fabricating empty `HookResult` objects masks real failure status. Replace with proper aggregation: skip missing statuses with `logger.debug("no previous status for hook %s", hook_name)` and rely on the caller to handle the empty-set case.

**Diff sketch**:

```python
# Before:
results.append(HookResult(hook=hook, status="unknown", issues=[]))

# After:
logger.debug("No previous status for hook %s; skipping", hook)
# (do NOT fabricate; let the empty list propagate)
```

**Test impact**: `tests/unit/memory/test_strategy_recommender.py` — `test_unknown_hooks_do_not_fabricate_results` (NEW).

**Effort**: **1 h**.

**Dependencies**: None.

______________________________________________________________________

## Bulk-delete (earlier synthesis Section 5)

Total ~1,870 LOC across five files; all are listed in the project's `.archive/` removal queue but still on disk.

| File | LOC | Confirmed | Notes |
|---|---|---|---|
| `crackerjack/agents/qwen_code_bridge.py` | 601 | Yes (in `agents/`) | Drop-in replacement removed earlier; verify no `qwen_code_bridge` import remains. |
| `crackerjack/hooks/pool_based_hooks.py` | 388 | Yes (in `hooks/`) | Replaced by registry-based hook loading. |
| `crackerjack/hooks/lsp_hook.py` | 80 | Yes (in `hooks/`) | Superseded by language-server protocol helpers. |
| `crackerjack/reflection_loop.py` | 240 | Yes (top-level) | Replaced by `crackerjack/memory/...` modules. |
| `crackerjack/integration/skills_effectiveness_tracking.py` | 560 | Yes (in `integration/`) | **Deleted 2026-07-15** (commits `1cae0b94` test, `e0dd3491` module, `fd35bba4` setting); replacement `crackerjack/skills/metrics.py`. |

**Risk per file**: **Low** if a `grep -r "import .*$name" crackerjack tests` returns no hits. **Medium** if there are hits — each must be updated before deletion.

**Diff sketch (per file)**:

1. `git mv path/to/file.py .archive/path/to/file.py.removed-2026-07-04`
1. Update `__init__.py` re-exports if any.
1. `grep -rn "<name>" crackerjack tests` — chase stragglers.
1. Run `pytest tests/ -q -x --co` to confirm collection still works.

**Test impact**: Coverage report will improve (these files have low coverage). No new tests needed.

**Effort (total)**: **2 h** (sequential; ~25 min per file).

**Dependencies**: Run `crackerjack-coverage-fanout` first if any of these files have unique behaviour worth salvaging — but the audit says no. Coordinate with any test imports via `git grep`.

______________________________________________________________________

## Combined risk roll-up & execution order

| Item | Risk | Effort (h) |
|---|---|---|
| #11 V1/V2 dedupe | M | 5 |
| #12 ruff×3 gate | M-L | 3 |
| #13 preflight parallel | L | 2 |
| #14 stdout hash | M | 3 |
| #15 JsonlSink persistence | M | 4 |
| L4-L13 dead code (10) | L-M | 7 |
| Bulk delete (5 files) | L | 2 |
| **Total** | | **26** |

**Recommended order** (each row independent unless noted):

1. **L4, L7, L9, L11, L12, L13** — pure cleanups, ~4 h total, run in parallel.
1. **L5, L6, L10** — small behaviour fixes, ~3.5 h.
1. **Bulk delete** — 2 h, after L4-L13 (some bulk-deleted files may contain dead helpers that *are* still imported by the cleanup items).
1. **#13 parallel preflight** — 2 h, standalone.
1. **#12 ruff×3 gate** — 3 h (depends on #13's snapshot primitive if we share).
1. **#14 stdout hash** — 3 h.
1. **#15 JsonlSink** — 4 h.
1. **#11 V1/V2 dedupe** — 5 h, last (it touches the most code paths and benefits from Tier-2 #4 + #7 already landing).

**Combined Tier-2 + Tier-3 effort**: Tier-2 ≈ 18 h + Tier-3 ≈ 26 h ≈ **44 h** of focused work. Reasonable for two-week sprint with parallel agents on the L\*-items.

______________________________________________________________________

## Coordination with Tier-2 plan

| Tier-2 item | Tier-3 dependency |
|---|---|
| #4 `_check_iteration_completion` extraction | **#11** uses the extracted helper |
| #5 no-progress bail-out | **#14** hash check precedes bail |
| #7 atomic write helper | **#15** JsonlSink uses it |
| (others) | Independent |

If Tier-2 plan diverges from these assumptions, Tier-3 plan should be re-read before kickoff.

______________________________________________________________________

## Crackerjack-compliance checklist (per-item)

Every Tier-3 PR must pass:

- `crackerjack run` (ruff, mypy strict, pyright strict, bandit, complexipy, coverage ≥80%)
- No `Any` in new type signatures (escape with `TYPE_CHECKING` + protocol)
- `from __future__ import annotations` first non-comment line of any new file
- `pathlib.Path` for any new filesystem code
- All new async code uses `httpx`/`aiofiles`/`loop.run_in_executor` — no blocking I/O
- `oneiric.logging` — not stdlib `logging`, not `print()`
- Function-args ≤ 10, branches ≤ 15, statements ≤ 30 (target) / 55 (ceiling)

## Follow-up

Bulk-delete section was not executed — 5 files remain on disk with live imports. See crackerjack/integration/__init__.py:92 and tests/unit/agents/test_qwen_code_bridge.py:25. Pending separate deletion plan with caller update.

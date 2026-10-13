---
name: checkpoint-disabled
description: "Crackerjack's oneiric workflow has persistent task checkpointing and execution tracing disabled at the orchestrator level (enable_workflow_checkpoints=False). Quality-gate workflows re-execute every phase every run; the persistent cache was a write-then-wipe no-op with a concurrent-process TOCTOU and no serverless durability."
status: active
role: canonical
date: 2026-10-13
last_reviewed: 2026-10-13
topic: workflow-architecture
---

## Context

Oneiric's `RuntimeOrchestrator` constructs two persistent SQLite stores by
default:

1. **`WorkflowCheckpointStore`** — task-completion state for cross-run
   resume. The DAG executor in `oneiric/runtime/dag.py` consults this
   store via `_load_from_checkpoint` (line 272) to skip already-done
   tasks. The `WorkflowBridge._execute_with_checkpoint` (line 221) does
   `save` on failure and `clear` on success.
2. **`WorkflowExecutionStore`** — durable execution tracing. Every run
   and node has a recorded start/end timestamp, status, attempts, and
   error. Surfaced for observability.

Both stores are gated by the same boolean: `enable_workflow_checkpoints`
(passed to `RuntimeOrchestrator.__init__`, default `True`).

Crackerjack's previous session landed a workaround: `_clear_oneiric_cache`
reached into the private `runtime.workflow_bridge._checkpoint_store` to
wipe the cache at the start of every run. The comment on the method
correctly noted that this was a workaround for a path-mismatch bug (a
hardcoded sqlite path under `pkg_path/.oneiric_cache/` that oneiric
never actually read). The fix was correct but treated the symptom, not
the cause.

## Why the cache is wrong for crackerjack

A quality-gate workflow whose job is to verify state should re-run every
phase every time. "Already passed" is a function of the previous input,
not the current input. The persistent cache was operating in three
distinctly bad ways:

1. **Write-then-wipe no-op.** `_clear_oneiric_cache` was called at the
   start of every run, the cache filled during the run, and the next
   run wiped it. The cache was a state file that got created and
   immediately cleared on every cycle. It served no functional
   purpose.
2. **Concurrent-process TOCTOU.** Two agents on the same repo, both
   running crackerjack, share the cache directory. Agent A's
   `_clear_oneiric_cache` and Agent B's `_clear_oneiric_cache` are
   interleaved; one agent's mid-run state is visible to the other
   agent's run start. The previous-session fix made this less bad but
   did not eliminate the hazard.
3. **No serverless durability.** `WorkflowCheckpointStore` is
   file-based SQLite (`sqlite3.connect(self.path)` at
   `oneiric/runtime/checkpoints.py:60`). In Lambda/Cloud Function
   contexts, the file is in ephemeral `/tmp` and disappears on
   container recycle. Cross-invocation state is impossible. The cache
   is dead-on-arrival for serverless.

The KISS argument is load-bearing: a state file that exists only to be
cleared is worse than no state file at all. The previous-session fix
correctly identified the path-mismatch bug but stopped at "make the
clear work"; the deeper fix is "stop needing to clear."

## Decision rule

Crackerjack's `build_oneiric_runtime` constructs `RuntimeOrchestrator`
with `enable_workflow_checkpoints=False`. Both stores become `None` and
all load/save/clear paths in `oneiric/domains/workflows.py:205-245`
short-circuit. The in-memory DAG checkpoint in
`oneiric/runtime/dag.py` (the `checkpoint` MutableMapping passed
through the run) is preserved — it carries within-run task
information and is not persisted.

The previous workaround (`_clear_oneiric_cache`,
`_resolve_workflow_checkpoints_path`, the `pipeline.phases.phases.
runtime_paths.workflow_checkpoints_path` setting override) is deleted.

The previous-session follow-up note in
`2026-10-12-hook-stage-documentary-vs-enforced.md` (which proposed
adding a public `WorkflowBridge.clear_checkpoint(workflow_key)` to
oneiric) is **resolved differently**: instead of adding a public
clear API, the consumer opted out of the cache entirely. This is the
better outcome — one less API surface to maintain, and a class of
bugs (path mismatch, concurrent-process TOCTOU, serverless
incompatibility) goes away rather than being patched.

## Implementation

1. `crackerjack/runtime/oneiric_workflow.py:build_oneiric_runtime`:
   added `enable_workflow_checkpoints=False` to the `RuntimeOrchestrator`
   constructor. Removed the `workflow_checkpoints_path` setting
   override (no longer needed). Removed the
   `_resolve_workflow_checkpoints_path` helper (no callers). Removed
   the now-unused `import tempfile` and `from pathlib import Path`.
2. `crackerjack/core/workflow_orchestrator.py:run_complete_workflow`:
   removed the `_clear_oneiric_cache(runtime)` call. Replaced the
   comment block with a one-line note pointing at this decision.
3. `crackerjack/core/workflow_orchestrator.py`: deleted the
   `_clear_oneiric_cache` method (the entire 30-line block).
4. `tests/core/test_workflow_orchestrator.py`: deleted the 5
   ratchet-regression tests (which tested the now-removed workaround)
   and replaced them with a single policy test,
   `test_build_oneiric_runtime_disables_workflow_checkpointing`,
   that pins the runtime attribute (both `_checkpoint_store` and
   `_execution_store` must be `None`).
5. `tests/unit/core/test_workflow_pipeline_eventbridge_wiring.py`:
   removed the 4 dead `pipeline._clear_oneiric_cache = MagicMock()`
   patches.
6. `tests/unit/runtime/test_oneiric_workflow.py`: replaced the
   `_resolve_workflow_checkpoints_path` test with a marker comment
   explaining the policy lives elsewhere.

## Verification

| Check | Result |
|---|---|
| `build_oneiric_runtime().orchestrator._checkpoint_store` | `None` |
| `build_oneiric_runtime().orchestrator._execution_store` | `None` |
| `crackerjack run -f` in worktree | 17/17 fast hooks in 39s; ratchet phase correctly skipped |
| `pytest tests/core/test_workflow_orchestrator.py` | New policy test passes; the `class AsyncMock` fallback for older Python is preserved because other tests use it |
| `_clear_oneiric_cache` references in crackerjack | 0 |
| `_resolve_workflow_checkpoints_path` references in crackerjack | 0 |
| `workflow_checkpoints_path` references in crackerjack | 0 |

## Follow-ups filed as part of this work

1. **Store 1 / Store 2 split in oneiric (high priority, next PR):** the
   user has flagged that `WorkflowExecutionStore` (Store 2) is very
   useful and should be available for crackerjack without
   `WorkflowCheckpointStore` (Store 1). The clean design: oneiric
   splits the unified `enable_workflow_checkpoints` flag into
   `enable_task_resume` (Store 1) and `enable_execution_tracing`
   (Store 2), each independently togglable. Crackerjack opts in to
   Store 2 only.
2. **Serverless-friendly Store 2 backends:** for the Store 2 split,
   the tracing backend should pluggable via existing oneiric adapters
   (Redis, Postgres, S3) — not a fresh storage abstraction. The
   `AdapterProtocol` and `AdapterBridge` already provide this surface;
   the new store should accept an adapter and serialize tracing
   records through it. Serverless consumers (Lambda, Cloud Functions)
   configure their preferred adapter at startup.
3. **Fleet policy doc:** codify this decision for the rest of the
   Bodai ecosystem in `oneiric/docs/state-policy.md`. The four rules
   (no checkpointing for quality-gate workflows; invalidate at start;
   self-describing staleness; concurrent-process isolation) are
   framed around this case as the reference implementation.

## Status

Active. The orchestrator is built with `enable_workflow_checkpoints=False`
in `build_oneiric_runtime`. The pin test
`test_build_oneiric_runtime_disables_workflow_checkpointing` will fail
if a future contributor re-enables the cache without updating this
decision note.

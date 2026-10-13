---
name: hook-stage-documentary-vs-enforced
description: "HookDefinition.stage is documentary-only for built-in entries (FAST_HOOKS, COMPREHENSIVE_HOOKS). Drift between list and field is a silent inconsistency. The ratchet bug (2026-10-12) and the plan-index-sync promotion sidestepped the issue; the underlying problem remains for future hooks."
status: active
role: canonical
date: 2026-10-12
last_reviewed: 2026-10-12
topic: hook-architecture
---

## Context

`crackerjack/config/hooks.py:30-67` (the `HookDefinition` dataclass) carries a `stage:
HookStage` field, but the docstring at line 32-51 explicitly notes:

> drift between list and field is a silent inconsistency

For built-in entries (the constants `FAST_HOOKS` at line 107 and `COMPREHENSIVE_HOOKS` at line 263), execution is driven by **which list the entry lives in**, not by the field. The convention is to set `stage` to match the list placement, but no runtime check enforces this. A new entry added to `FAST_HOOKS` with `stage=HookStage.COMPREHENSIVE` will execute during the fast phase with no warning.

The same risk exists for any setting field that is documented but not enforced (e.g. `auto_run`, `disabled`, `is_formatting`).

## Why now

Two changes on 2026-10-12 surfaced the issue indirectly:

1. **Ratchet bug fix** — `crackerjack/core/workflow_orchestrator.py:_clear_oneiric_cache` reached into oneiric's private `workflow_bridge._checkpoint_store` because the bridge has no public `clear_checkpoint` method (oneiric's `WorkflowBridge` exposes only `__init__`, `update_settings`, `refresh_dags`, `dag_specs`, `execute_dag`, `enqueue_workflow`). The fix works but is fragile — if oneiric renames the attribute, crackerjack breaks silently.

2. **plan-index-sync promotion** — moving `plan-index-sync` from `FAST_HOOKS` to its own workflow phase sidestepped the documentary-vs-enforced issue entirely (the new phase lives outside the hook system). The fix is the right shape for the future, but the underlying hook-list/field-drift hazard remains for any hook added to `FAST_HOOKS` or `COMPREHENSIVE_HOOKS`.

## Decision rule

Treat undocumented `stage` field values on built-in hook entries as a maintenance hazard to be eliminated, not preserved. The fix has two acceptable shapes:

1. **Runtime check** — in `HookDefinition.__post_init__`, raise `ValueError` when a built-in entry's `stage` field disagrees with the list it's placed in. Use a marker like `HookDefinition._builtin: bool = False` (init=False, repr=False) to distinguish "placed by the framework" from "defined by a plugin caller." For the `is_formatting`, `auto_run`, and `disabled` fields, the same pattern applies where the value is meant to be authoritative.

2. **Test pin** — a single test that walks `FAST_HOOKS` and `COMPREHENSIVE_HOOKS` and asserts every entry's `stage` field matches the list it lives in, plus the same for `auto_run`/`disabled` consistency.

Option 1 catches drift at definition time (faster feedback, but requires care to preserve the plugin-defined-entries exemption). Option 2 is a one-shot guard. The crackerjack convention (per the in-code docstring) prefers the runtime check, but a test pin is the minimum acceptable.

## Follow-ups filed as part of this work

- **Resolved 2026-10-13** (not by adding a public `clear_checkpoint` to
  oneiric, but by opting the consumer out of the cache entirely):
  `crackerjack/runtime/oneiric_workflow.py:build_oneiric_runtime` now
  constructs the `RuntimeOrchestrator` with
  `enable_workflow_checkpoints=False`. The
  `_clear_oneiric_cache(runtime)` workaround and the
  `_resolve_workflow_checkpoints_path` helper are both deleted. The
  bridge's `_checkpoint_store` and `_execution_store` are both `None`
  and all load/save/clear paths in
  `oneiric/domains/workflows.py:205-245` short-circuit. See
  `.claude/decisions/2026-10-13-checkpoint-disabled.md` for the policy
  rationale. This is a better outcome than the originally proposed
  upstream public API: one less surface to maintain, and a class of
  bugs (path mismatch, concurrent-process TOCTOU, serverless
  incompatibility) goes away rather than being patched.

## Status

Active. No automated enforcement exists yet. Every new hook added to `FAST_HOOKS` or `COMPREHENSIVE_HOOKS` requires the contributor to manually set `stage` correctly; this is fragile and the next contributor to forget is one line away from a silent inconsistency.

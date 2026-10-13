## Context

Oneiric's `RuntimeOrchestrator` previously exposed a single
`enable_workflow_checkpoints` flag that gated BOTH
`WorkflowCheckpointStore` (Store 1) AND `WorkflowExecutionStore`
(Store 2). Crackerjack disabled both via that single flag because:

1. Crackerjack is a quality-gate workflow — every run re-executes every
   phase from a known-fresh state. Persistent task-resume state would
   create a "write-then-wipe" no-op hazard, a concurrent-process
   TOCTOU, and is not serverless-durable.
2. The file-based SQLite store backing Store 1 is not durable on
   serverless runtimes, which the Bodai ecosystem is moving toward.

In practice, however, Store 2 (execution tracing) IS useful to crackerjack
for observability: it surfaces per-phase timing, status, error context,
and per-node start/finish events, which makes post-mortem analysis of
failed runs much faster.

Oneiric's flag split
(`enable_task_resume` for Store 1, `enable_execution_tracing` for
Store 2) makes the per-store intent expressible at the call site.

## Decision rule

`build_oneiric_runtime` constructs `RuntimeOrchestrator` with:

- `enable_task_resume=False` — Store 1 remains disabled (legacy behavior).
- `enable_execution_tracing=True` — Store 2 is wired so per-phase
  observability is captured.

This replaces the previous `enable_workflow_checkpoints=False` call.
The legacy keyword is no longer passed; both new flags are set
explicitly to make the per-store intent visible to code reviewers and
to the policy-pinning test in
`tests/core/test_workflow_orchestrator.py::test_build_oneiric_runtime_disables_workflow_checkpointing`.

The crackerjack-specific rationale for Store 2 being serverless-safe
is: Store 2 is adapter-pluggable in oneiric (Redis, Postgres, S3
adapters are already in the substrate). When deployed to serverless
runtimes, the resolver selects an adapter that talks to a remote
backend. Locally (dev/CI), Store 2 falls back to SQLite at the same
path Store 1 used to occupy, which is fine for short-lived local runs.

## Status

Implemented on branch `feat/store-2-only`. Oneiric-side support lives
on `feat/store-2-split` (one PR per repo, per the pre-1.0 merge policy).
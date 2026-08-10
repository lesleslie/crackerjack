// AI-Fix External Loop — Workflow script skeleton (Task 2).
//
// Runs `crackerjack run -v` to surface residual quality issues,
// dispatches them to a fix agent, re-verifies, repeats until clean
// or capped. Full design: docs/superpowers/plans/2026-08-06-ai-fix-external-loop.md
//
// Status: skeleton. Tasks 3-6 fill in the Verify/Snapshot/Fix/Stop phases.
// This skeleton completes a single iteration of `log()` calls and returns
// `iteration-cap` — useful only as a syntax smoke test.

export const meta = {
  name: 'ai-fix-loop',
  description: 'Run crackerjack, dispatch residual issues to an agent, loop until clean or capped',
  phases: [
    { title: 'Verify' },
    { title: 'Snapshot' },
    { title: 'Fix' },
  ],
}

// NOTE on `args` global: the Workflow tool's contract for `args` as a
// script-level global is not formally documented; existing reference
// workflows template values into prompts at call sites rather than
// reading `args` at module scope. If `args` is not in fact available
// here, replace with hard-coded defaults or pass values via the prompt
// string from the caller. Verify before relying on this.
const REQUESTED_MAX = (args && args.maxIterations) || 10

// Issue-count-proportional cap: never fewer than 10, but allow up to
// 1.5x the initial issue count for genuinely large fix surfaces.
// Adjusted in Task 3 after the first Verify pass.
const DEFAULT_MAX_ITERATIONS = REQUESTED_MAX
let MAX_ITERATIONS = Math.max(REQUESTED_MAX, 10)

// Initial-issue-count guard. A repo with >200 baseline issues is not a
// fix-loop candidate — it's a triage problem. Surfaced as the
// `initial-issue-count-too-high` stop reason in Task 3, not silently
// kicked into a multi-hour loop. Threshold chosen to keep one run
// under the Mahavishnu pool's default 300s timeout (200 iters × ~1s
// per iter cap ≈ budget). Tune via `args.initialIssueGuard` if needed.
const INITIAL_ISSUE_GUARD = 200

let previousIssueCount = Number.POSITIVE_INFINITY
let consecutiveFlat = 0
const FLAT_THRESHOLD = 2  // require 2 flat iters before declaring 'progress-stalled'
const auditLog = []
let initialIssueCount = null  // set after the first Verify pass

// Audit log persistence path. On script start, check for an existing
// state file and either resume, archive-and-start-fresh, or abort —
// decided by the operator. Per-iteration appends happen in Task 6.
const AUDIT_LOG_PATH = '.crackerjack/audit/ai-fix-loop.jsonl'

for (let iteration = 1; iteration <= MAX_ITERATIONS; iteration++) {
  log(`Iteration ${iteration}/${MAX_ITERATIONS}`)
  // Task 3 fills in the Verify phase here.
  // Task 4 fills in the Snapshot phase here.
  // Task 5 fills in the Fix phase here.
  // Task 6 fills in the stop-condition checks here.
}

log(`Iteration cap (${MAX_ITERATIONS}) reached with issues still remaining.`)
return { stopReason: 'iteration-cap', iterations: MAX_ITERATIONS, auditLog }
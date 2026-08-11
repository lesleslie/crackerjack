// AI-Fix External Loop — Workflow script (Task 3: Verify phase).
//
// Runs `crackerjack run -v` to surface residual quality issues,
// dispatches them to a fix agent, re-verifies, repeats until clean
// or capped. Full design: docs/superpowers/plans/2026-08-06-ai-fix-external-loop.md
//
// Status: Task 3 complete (Verify phase implemented). Tasks 4-6 still pending:
//   - Task 4: Snapshot phase (git stash/clean-tree invariant)
//   - Task 5: Fix phase (dispatch issues to fix agent)
//   - Task 6: Stop-condition checks, rollback, audit log persistence

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

// parseVerifyText helper (Task 3, module scope).
// Parses the agent's text response into { cleanExit, issueCount, issuesSummary }.
// Returns null if any of the three labeled lines is missing or malformed — the
// caller (Task 3 Step 1) treats null as `verify-error` and aborts.
//
// Expected agent response shape:
//   cleanExit: <true-or-false>
//   issueCount: <integer-or--1>
//   issuesSummary: <one-paragraph-plain-text-summary>
//
// Loose parsing — uses multiline regex rather than full-line matching,
// tolerates trailing whitespace, accepts the `issuesSummary` value as
// anything on its line (including internal punctuation).
function parseVerifyText(text) {
  if (typeof text !== 'string' || !text.trim()) return null
  // Tolerate leading whitespace on each line — LLM agents sometimes
  // indent their responses with spaces or tabs.
  const cleanMatch = text.match(/^\s*cleanExit:\s*(true|false)\s*$/m)
  const countMatch = text.match(/^\s*issueCount:\s*(-?\d+)\s*$/m)
  const summaryMatch = text.match(/^\s*issuesSummary:\s*(.+?)\s*$/m)
  if (!cleanMatch || !countMatch || !summaryMatch) return null
  const issueCount = parseInt(countMatch[1], 10)
  if (!Number.isFinite(issueCount)) return null
  return {
    cleanExit: cleanMatch[1] === 'true',
    issueCount,
    issuesSummary: summaryMatch[1],
  }
}

// parseSnapshotText helper (Task 4, module scope).
// Parses the snapshot agent's text response into a snapshot object:
//   { dirty, stashed, stashRef, stashSha, stashMessage, reason }
// Returns null if required fields (dirty, stashed) are missing or malformed.
//
// Expected agent response shape:
//   dirty: <true-or-false>                         [required]
//   stashed: <true-or-false>                       [required]
//   stashSha: <sha-string>                         [required when stashed=true]
//   [stashMessage: <message>]                      [optional, only when stashed=true]
//   [reason: <description>]                        [optional, only when dirty=true, stashed=false]
//
// stashRef is derived from stashed: when stashed=true the positional ref
// is `stash@{0}`; when stashed=false it's null. The durable handle is
// stashSha (the git rev-parse output), which Task 6's rollback uses to
// re-resolve the stash even if its positional index has shifted.
//
// Loose parsing — multiline regex tolerates leading whitespace, surrounding
// prose, and missing optional fields. Required: dirty and stashed. When
// stashed=true the SHA and message are also required; when stashed=false
// they may be absent (the agent omits them in the "no-op" and "concurrent
// change" branches of the prompt).
function parseSnapshotText(text) {
  if (typeof text !== 'string' || !text.trim()) return null
  const dirtyMatch = text.match(/^\s*dirty:\s*(true|false)\s*$/m)
  const stashedMatch = text.match(/^\s*stashed:\s*(true|false)\s*$/m)
  if (!dirtyMatch || !stashedMatch) return null
  const dirty = dirtyMatch[1] === 'true'
  const stashed = stashedMatch[1] === 'true'
  // SHA is only meaningful when stashed=true; required in that case.
  let stashSha = null
  let stashMessage = null
  if (stashed) {
    const shaMatch = text.match(/^\s*stashSha:\s*(\S+)\s*$/m)
    if (!shaMatch) return null
    stashSha = shaMatch[1].trim()
    const messageMatch = text.match(/^\s*stashMessage:\s*(.+?)\s*$/m)
    if (messageMatch) stashMessage = messageMatch[1].trim()
  }
  const reasonMatch = text.match(/^\s*reason:\s*(.+?)\s*$/m)
  const reason = reasonMatch ? reasonMatch[1].trim() : null
  // stashRef is hardcoded to the most-recent positional ref; the durable
  // SHA-anchored ref (stashSha) handles the shift case at rollback time.
  const stashRef = stashed ? 'stash@{0}' : null
  return {
    dirty,
    stashed,
    stashRef,
    stashSha,
    stashMessage,
    reason,
  }
}

for (let iteration = 1; iteration <= MAX_ITERATIONS; iteration++) {
  log(`Iteration ${iteration}/${MAX_ITERATIONS}`)

  // === Task 3: Verify phase ===
  phase('Verify')
  // Loose-text parsing is used instead of `agent({schema})` because the
  // Workflow tool has a documented infinite-loop bug when schema
  // validation repeatedly fails (see `~/.claude/cache/changelog.md`).
  // The fix agent returns plain text; we parse it ourselves.
  const verifyText = await agent(
    `Run this exact command in the crackerjack repo: \`python -m crackerjack run -v\`. ` +
    `This prints Rich-formatted, human-readable quality-check results (not JSON) — for example a "Fast Hook Results" section ` +
    `listing each hook with a FAILED/PASSED marker and an issue count, e.g. "- ruff-check :: FAILED | issues=1250". ` +
    `Read the full output and respond with EXACTLY this format (three lines, nothing else):\n` +
    `cleanExit: <true-or-false>\n` +
    `issueCount: <integer-or--1>\n` +
    `issuesSummary: <one-paragraph-plain-text-summary>\n` +
    `Set cleanExit=true only if every hook/check passed with zero issues. ` +
    `Set issueCount to the total number of issues across all failed hooks/checks (sum the counts; if a hook fails with no explicit count, count it as 1 issue). ` +
    `If the command crashes or produces no usable output (distinct from "hooks failed" — a crash means the tool itself errored), set cleanExit=false, issueCount=-1, and put the crash description in issuesSummary. ` +
    `Distinguishing rule for "crashed" vs "issues found": presence of a "Fast Hook Results" summary line in the output = "issues found" (informative failure, normal exit 1); absence of that summary + presence of a "Workflow failed: Task tests failed" or stack-trace marker = "crashed" (use cleanExit=false, issueCount=-1).`,
    { label: `verify-iter-${iteration}`, phase: 'Verify' }
  )

  // Per-hook count delta (verified 2026-08-10): crackerjack's reported
  // `issues=N` for ruff-check was 999 in the clean-tree run, but
  // independent `ruff check --output-format=json .` reported 1093 issues
  // — a delta of ~9%. The likely causes are: (a) crackerjack filters or
  // caps reported counts, (b) different --select/--ignore sets,
  // (c) per-file-ignores applied differently. The verify-agent sums
  // crackerjack's per-hook counts as-is and reports that as the loop's
  // baseline; do NOT have it reconcile against `ruff check` directly —
  // that would create two competing sources of truth. The 9% delta is
  // acceptable because the loop's convergence check is on delta-relative-
  // to-previous-iteration, not on absolute count parity with `ruff`.

  const verify = parseVerifyText(verifyText)
  // Defensive validation: NaN/null/-1 etc. must abort, not silently loop.
  if (!verify || !Number.isFinite(verify.issueCount) || verify.issueCount < -1) {
    log(`Verify agent returned malformed result on iteration ${iteration} — aborting.`)
    return { stopReason: 'verify-error', iterations: iteration - 1, auditLog }
  }
  if (verify.issueCount === -1) {
    log(`Verify agent reported crackerjack crash on iteration ${iteration} — aborting.`)
    return { stopReason: 'verify-error', iterations: iteration - 1, auditLog }
  }
  if (verify.cleanExit) {
    log(`Clean after ${iteration - 1} fix iteration(s).`)
    return { stopReason: 'clean', iterations: iteration - 1, auditLog }
  }
  // After the first Verify, scale MAX_ITERATIONS by initial issue count.
  if (initialIssueCount === null) {
    initialIssueCount = verify.issueCount
    // Initial-issue-count guard: a repo with too many baseline issues is
    // a triage problem, not a fix-loop candidate. Surface to operator
    // rather than silently kicking off a multi-hour run.
    if (!Number.isFinite(initialIssueCount) || initialIssueCount > INITIAL_ISSUE_GUARD) {
      log(`Initial issue count ${initialIssueCount} exceeds guard ${INITIAL_ISSUE_GUARD} — aborting.`)
      return {
        stopReason: 'initial-issue-count-too-high',
        iterations: 0,
        initialIssueCount,
        guard: INITIAL_ISSUE_GUARD,
        message: `Repo has ${initialIssueCount} baseline issues (guard: ${INITIAL_ISSUE_GUARD}). ` +
                 `Run \`crackerjack run -v\` manually, triage the largest-bucket failures first, ` +
                 `then re-run this workflow.`,
        auditLog,
      }
    }
    MAX_ITERATIONS = Math.max(REQUESTED_MAX, Math.ceil(initialIssueCount * 1.5), 10)
    log(`Initial issue count: ${initialIssueCount}. Adjusted MAX_ITERATIONS to ${MAX_ITERATIONS}.`)
  }

  // === Task 4: Snapshot phase ===
  phase('Snapshot')
  // Snapshot captures BOTH the positional ref AND a durable SHA handle.
  // The positional ref (`stash@{0}`) can shift if the user adds their
  // own stash between iterations; the SHA (`<rev>^3`) survives any
  // positional reshuffling and is used at rollback time.
  const snapshotText = await agent(
    `In the crackerjack repo, perform a snapshot before this iteration's fix attempt:\n` +
    `1. Run \`git status --short\` and verify the dirty set matches what this loop expects to snapshot.\n` +
    `   If there are unexpected changes (e.g., user edits, an unrelated file change), DO NOT stash — instead respond with these three lines:\n` +
    `   dirty: true\n` +
    `   stashed: false\n` +
    `   reason: <describe the unexpected changes>\n` +
    `2. If the tree is already clean (no fix applied yet, or last iteration rolled back), respond with:\n` +
    `   dirty: false\n` +
    `   stashed: false\n` +
    `3. Otherwise run \`git stash push -u -m "ai-fix-loop-iter-${iteration}"\` and then run \`git rev-parse "stash@{0}^3"\` to get the commit SHA the stash represents.\n` +
    `   Respond with EXACTLY these lines (nothing else):\n` +
    `   dirty: false\n` +
    `   stashed: true\n` +
    `   stashSha: <the-rev-parse-output>\n` +
    `   stashMessage: ai-fix-loop-iter-${iteration}\n` +
    `The stashSha value MUST be the full SHA printed by \`git rev-parse "stash@{0}^3"\` — do not abbreviate. The stashMessage MUST exactly match the \`-m\` argument used in the git stash push command.`,
    { label: `snapshot-iter-${iteration}`, phase: 'Snapshot' }
  )
  const snapshot = parseSnapshotText(snapshotText)
  if (!snapshot) {
    log(`Snapshot agent returned malformed result on iteration ${iteration} — aborting.`)
    return { stopReason: 'snapshot-error', iterations: iteration - 1, auditLog }
  }
  if (snapshot.dirty && !snapshot.stashed) {
    const reason = snapshot.reason || 'unspecified'
    log(`Unexpected dirty state detected on iteration ${iteration}: ${reason} — aborting to avoid clobbering user changes.`)
    return {
      stopReason: 'concurrent-change-detected',
      iterations: iteration - 1,
      reason,
      auditLog,
    }
  }
  // Task 5 fills in the Fix phase here.
  // Task 6 fills in the stop-condition checks here.
}

log(`Iteration cap (${MAX_ITERATIONS}) reached with issues still remaining.`)
return { stopReason: 'iteration-cap', iterations: MAX_ITERATIONS, auditLog }
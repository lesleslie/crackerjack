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

// Audit log persistence path. Override via `args.auditLogPath` from the
// Workflow tool caller. The default is hardcoded here for the standalone
// case; the operator-facing knob lives in crackerjack's Oneiric settings
// (`ai_fix_loop.audit_log_path`) which the Mahavishnu dispatch layer reads
// and forwards as `args.auditLogPath`. Followup work: add the field to
// `crackerjack.config.settings.CrackerjackSettings` and the corresponding
// `settings/crackerjack.yaml` entry.
const AUDIT_LOG_PATH = (args && args.auditLogPath) || '.crackerjack/audit/ai-fix-loop.jsonl'

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
  // indent their responses with spaces or tabs. Inline whitespace uses
  // [ \t]* (not \s*) to prevent capturing content from subsequent lines
  // when the field is empty.
  const cleanMatch = text.match(/^\s*cleanExit:\s*(true|false)\s*$/m)
  const countMatch = text.match(/^\s*issueCount:\s*(-?\d+)\s*$/m)
  const summaryMatch = text.match(/^\s*issuesSummary:[ \t]*([^\n]*?)[ \t]*$/m)
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
    const messageMatch = text.match(/^\s*stashMessage:[ \t]*([^\n]*?)[ \t]*$/m)
    if (messageMatch) stashMessage = messageMatch[1].trim()
  }
  const reasonMatch = text.match(/^\s*reason:[ \t]*([^\n]*?)[ \t]*$/m)
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

// parseFixText helper (Task 5, module scope).
// Parses the fix agent's text response into a fix object:
//   { changes: Array<{ file, description }> }
// Returns null if the CHANGES: marker is missing entirely — the caller
// (Task 5 Step 1) treats null as `fix-agent-error` and aborts.
//
// Expected agent response shapes:
//   (a) Empty list — agent made no changes:
//       CHANGES: (empty list)
//   (b) One or more changes — agent lists each with `file:` and
//       `description:` lines, separated by `---`:
//       CHANGES:
//       file: crackerjack/foo.py
//       description: unused import cleanup
//       ---
//       file: crackerjack/bar.py
//       description: typing fix
//       ---
//
// Loose parsing: leading whitespace, surrounding prose, and tab indents
// are tolerated. The empty-list marker accepts "(empty list)", "empty list",
// or just whitespace on the inline portion after `CHANGES:`. Blocks without
// valid file/description pairs are silently skipped (the agent may emit
// trailing noise after the last `---` separator).
function parseFixText(text) {
  if (typeof text !== 'string' || !text.trim()) return null
  // Locate the CHANGES: marker; bail out if absent.
  const markerMatch = text.match(/^\s*CHANGES:/m)
  if (!markerMatch) return null
  const markerStart = text.indexOf(markerMatch[0])
  const markerEnd = markerStart + markerMatch[0].length
  // Inline portion after CHANGES: (up to next newline) — used for empty-list check.
  const inlineSlice = text.slice(markerEnd)
  const inlineMatch = inlineSlice.match(/^(.*?)(?:\n|$)/)
  const inline = inlineMatch ? inlineMatch[1].trim() : ''
  if (/^\(?empty\s+list\)?$/i.test(inline)) {
    return { changes: [] }
  }
  // Split remainder on `---` separator and extract file/description pairs.
  const blocks = inlineSlice.split(/^\s*---\s*$/m)
  const changes = []
  for (const block of blocks) {
    const fileMatch = block.match(/^\s*file:\s*(.+?)\s*$/m)
    const descMatch = block.match(/^\s*description:\s*(.+?)\s*$/m)
    if (fileMatch && descMatch) {
      changes.push({
        file: fileMatch[1].trim(),
        description: descMatch[1].trim(),
      })
    }
  }
  return { changes }
}

// parseDiffStatText helper (Task 6, module scope).
// Parses the diff-sanity agent's text response into a diff-sanity object:
//   { filesChanged: int, linesChanged: int, forbiddenTouched: string[] }
// Returns null if any required field is missing or non-integer.
//
// Expected agent response shape:
//   filesChanged: <integer>
//   linesChanged: <integer>
//   forbiddenTouched: <comma-separated-paths-or-empty>
//
// The forbiddenTouched value may be empty (means "no forbidden paths were
// touched") — returns an empty array in that case. Otherwise splits on
// comma and trims each entry.
function parseDiffStatText(text) {
  if (typeof text !== 'string' || !text.trim()) return null
  const filesMatch = text.match(/^\s*filesChanged:\s*(\d+)\s*$/m)
  const linesMatch = text.match(/^\s*linesChanged:\s*(\d+)\s*$/m)
  const forbiddenMatch = text.match(/^\s*forbiddenTouched:[ \t]*([^\n]*?)[ \t]*$/m)
  if (!filesMatch || !linesMatch || !forbiddenMatch) return null
  const filesChanged = parseInt(filesMatch[1], 10)
  const linesChanged = parseInt(linesMatch[1], 10)
  if (!Number.isFinite(filesChanged) || !Number.isFinite(linesChanged)) return null
  const forbiddenRaw = forbiddenMatch[1]
  const forbiddenTouched = forbiddenRaw === ''
    ? []
    : forbiddenRaw.split(',').map(s => s.trim()).filter(Boolean)
  return { filesChanged, linesChanged, forbiddenTouched }
}

// attemptRollback helper (Task 6, module scope, async).
// Looks up the previous iteration's stash by message, verifies the SHA,
// pops it, and drops it. Returns { success, reason, details } parsed
// from the agent's response, or null if the response is malformed.
//
// The plan documents that the positional `stash@{N}` ref MUST NOT be
// used — only message-based lookup + SHA verification. This handles the
// case where the user adds their own stash between iterations and the
// positional index shifts.
//
// Pre-condition: auditLog has at least one entry with stashSha and
// stashMessage. Caller (Step 1 in the loop body) reads
// auditLog[auditLog.length - 1] for the most recent snapshot.
async function attemptRollback(auditLog, iteration) {
  const lastEntry = auditLog[auditLog.length - 1]
  if (!lastEntry || !lastEntry.stashSha || !lastEntry.stashMessage) {
    log(`No snapshot to roll back to on iteration ${iteration}.`)
    return { success: false, reason: 'no-snapshot' }
  }
  const result = await agent(
    `In the crackerjack repo, perform a SHA-anchored stash rollback:\n` +
    `1. Run \`git stash list --grep '^${lastEntry.stashMessage}$'\` to find the stash entry by message.\n` +
    `   If multiple entries match, pick the one whose commit SHA matches the captured SHA below.\n` +
    `2. Run \`git rev-parse "<entry>^3"\` and verify the result matches this expected SHA: ${lastEntry.stashSha}\n` +
    `3. If SHA matches: run \`git stash pop "<entry>"\` then \`git stash drop "<entry>"\` to remove the entry.\n` +
    `4. If SHA does NOT match: do NOT pop. Return success=false with reason "sha-mismatch".\n` +
    `5. If pop fails (merge conflict, etc.): return success=false with reason "pop-failed".\n\n` +
    `Respond with EXACTLY these lines:\n` +
    `success: <true-or-false>\n` +
    `reason: <"sha-mismatch"|"pop-failed"|empty-when-success>\n` +
    `details: <mismatch-or-conflict-details-or-empty>\n` +
    `The positional \`stash@{N}\` ref MUST NOT be used.`,
    { label: `rollback-iter-${iteration}`, phase: 'Snapshot' }
  )
  return parseRollbackText(result)
}

// parseRollbackText helper (Task 6, module scope).
// Parses the rollback agent's text response.
// Returns null if the success field is missing or invalid.
function parseRollbackText(text) {
  if (typeof text !== 'string' || !text.trim()) return null
  const successMatch = text.match(/^\s*success:\s*(true|false)\s*$/m)
  if (!successMatch) return null
  const reasonMatch = text.match(/^\s*reason:[ \t]*([^\n]*?)[ \t]*$/m)
  const detailsMatch = text.match(/^\s*details:[ \t]*([^\n]*?)[ \t]*$/m)
  const reason = reasonMatch ? reasonMatch[1] : null
  const details = detailsMatch ? detailsMatch[1] : null
  return { success: successMatch[1] === 'true', reason, details }
}

// persistAuditLog helper (Task 6, module scope, async).
// Appends a single JSONL entry to AUDIT_LOG_PATH via agent(). Returns
// { success, error } or null if the response is malformed.
//
// Failure triggers the `audit-log-error` stop reason — the loop can't
// continue without an audit trail. The agent MUST NOT overwrite or read
// existing content; it must atomically append a single line.
async function persistAuditLog(entry) {
  const line = JSON.stringify(entry)
  const result = await agent(
    `Append a single JSON line to the file \`${AUDIT_LOG_PATH}\` in the crackerjack repo. ` +
    `Create the parent directory \`.crackerjack/audit/\` if missing. ` +
    `Do NOT overwrite or read existing content — just append atomically.\n` +
    `If the append fails (disk full, permission denied, etc.), return success=false with the error description.\n\n` +
    `Line content (write exactly this, escaped as a JSON string):\n` +
    `${JSON.stringify(line)}`,
    { label: `audit-persist-iter-${entry.iteration}`, phase: 'Snapshot' }
  )
  return parsePersistText(result)
}

// parsePersistText helper (Task 6, module scope).
// Parses the audit-persist agent's text response.
// Returns null if the success field is missing or invalid.
function parsePersistText(text) {
  if (typeof text !== 'string' || !text.trim()) return null
  const successMatch = text.match(/^\s*success:\s*(true|false)\s*$/m)
  if (!successMatch) return null
  const errorMatch = text.match(/^\s*error:[ \t]*([^\n]*?)[ \t]*$/m)
  const error = errorMatch ? errorMatch[1] : null
  return { success: successMatch[1] === 'true', error }
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

  // === Task 6 Step 1: No-improvement / regressed / progress-stalled check ===
  // Evaluates whether the PREVIOUS iteration's fix was effective. Runs after
  // Verify and before Snapshot so a regressed/stalled loop can roll back
  // the previous iteration's stash BEFORE taking a new snapshot.
  const countDelta = verify.issueCount - previousIssueCount
  if (!Number.isFinite(countDelta)) {
    log(`Non-finite count delta on iteration ${iteration} — aborting to avoid silent infinite loop.`)
    return { stopReason: 'verify-error', iterations: iteration - 1, auditLog }
  }
  if (countDelta > 0) {
    log(`Issue count increased (was ${previousIssueCount}, now ${verify.issueCount}) — rolling back.`)
    const rollbackResult = await attemptRollback(auditLog, iteration)
    if (!rollbackResult || !rollbackResult.success) {
      const reason = (rollbackResult && rollbackResult.reason) || 'unknown'
      const details = (rollbackResult && rollbackResult.details) || null
      log(`Rollback failed after regression on iteration ${iteration}: reason=${reason}`)
      return {
        stopReason: 'rollback-error',
        iterations: iteration - 1,
        rollbackReason: reason,
        rollbackDetails: details,
        auditLog,
      }
    }
    return { stopReason: 'regressed', iterations: iteration - 1, auditLog }
  }
  if (countDelta === 0) {
    consecutiveFlat += 1
    if (consecutiveFlat >= FLAT_THRESHOLD) {
      log(`No progress for ${consecutiveFlat} consecutive iterations — rolling back and stopping.`)
      const rollbackResult = await attemptRollback(auditLog, iteration)
      if (!rollbackResult || !rollbackResult.success) {
        const reason = (rollbackResult && rollbackResult.reason) || 'unknown'
        const details = (rollbackResult && rollbackResult.details) || null
        log(`Rollback failed after progress-stalled on iteration ${iteration}: reason=${reason}`)
        return {
          stopReason: 'rollback-error',
          iterations: iteration - 1,
          rollbackReason: reason,
          rollbackDetails: details,
          auditLog,
        }
      }
      return { stopReason: 'progress-stalled', iterations: iteration - 1, auditLog }
    }
    log(`Flat iteration ${consecutiveFlat}/${FLAT_THRESHOLD} — continuing.`)
  } else {
    consecutiveFlat = 0
  }
  previousIssueCount = verify.issueCount

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
  // === Task 5: Fix phase ===
  phase('Fix')
  // Loose-text parsing — `agent({schema})` has the infinite-loop bug noted in Task 3.
  // The fix agent returns plain text in the CHANGES:/file:/description: format;
  // parseFixText (module scope) extracts the structured list.
  const fixText = await agent(
    `You are fixing quality issues in the crackerjack repo reported by \`crackerjack run -v\`. ` +
    `Here is a summary of the current issues: ${verify.issuesSummary}\n\n` +
    `Fix as many of these issues as you directly can by editing the affected files.\n\n` +
    `Hard constraints on your edits:\n` +
    `- Prefer minimal, targeted edits — do not refactor unrelated code.\n` +
    `- DO NOT modify files under \`tests/\`, \`docs/\`, or any \`*.toml\`/\`*.yml\`/\`*.txt\` config file.\n` +
    `- DO NOT delete test files.\n` +
    `- DO NOT touch \`pyproject.toml\`, \`setup.py\`, \`requirements*.txt\`, or \`Dockerfile\`.\n` +
    `- Maximum: 5 files changed, 100 lines changed. If a fix needs more, describe it and skip — the loop driver will dispatch a fresh attempt on the next iteration.\n` +
    `- Do not run \`crackerjack run\` yourself; the loop driving you will re-verify after you finish.\n\n` +
    `When done, respond with EXACTLY this format (one block per file you changed, nothing else):\n` +
    `CHANGES:\n` +
    `file: <path>\n` +
    `description: <one-sentence-description>\n` +
    `---\n` +
    `file: <path>\n` +
    `description: <one-sentence-description>\n` +
    `---\n` +
    `If you made no changes at all, respond with just: CHANGES: (empty list)`,
    { label: `fix-iter-${iteration}`, phase: 'Fix' }
  )
  const fix = parseFixText(fixText)
  if (!fix) {
    log(`Fix agent returned malformed result on iteration ${iteration} — aborting.`)
    return { stopReason: 'fix-agent-error', iterations: iteration - 1, auditLog }
  }

  // === Task 6 Step 3: Post-fix diff sanity check ===
  // The fix agent's hard constraints in the prompt are advisory; this
  // enforcement is the actual guardrail. Cap scope at 5 files / 100 lines
  // and blocklist `tests/`, `docs/`, `*.toml/*.yml/*.txt`, build configs.
  // Reference point: snapshot SHA when available (so the diff shows only
  // the fix's net effect against the pre-fix dirty tree), else HEAD.
  const diffRef = (snapshot && snapshot.stashed && snapshot.stashSha) ? snapshot.stashSha : 'HEAD'
  const diffStatText = await agent(
    `Run \`git diff --stat ${diffRef}\` and \`git diff --name-only ${diffRef}\` in the crackerjack repo. ` +
    `Respond with EXACTLY these lines:\n` +
    `filesChanged: <integer>\n` +
    `linesChanged: <integer>\n` +
    `forbiddenTouched: <comma-separated-paths-or-empty>\n` +
    `Forbidden paths are: anything under \`tests/\`, \`docs/\`, or matching \`*.toml\`, \`*.yml\`, \`*.txt\`, \`pyproject.toml\`, \`setup.py\`, \`requirements*.txt\`, \`Dockerfile\`.`,
    { label: `diff-sanity-iter-${iteration}`, phase: 'Snapshot' }
  )
  const diffSanity = parseDiffStatText(diffStatText)
  if (!diffSanity) {
    log(`Diff-sanity agent returned malformed result on iteration ${iteration} — aborting.`)
    return { stopReason: 'fix-agent-error', iterations: iteration - 1, auditLog }
  }
  if (diffSanity.filesChanged > 5 || diffSanity.linesChanged > 100 || diffSanity.forbiddenTouched.length > 0) {
    log(`Fix exceeded limits on iteration ${iteration}: files=${diffSanity.filesChanged}, lines=${diffSanity.linesChanged}, forbidden=${diffSanity.forbiddenTouched.join(',')} — rolling back.`)
    const rollbackResult = await attemptRollback(auditLog, iteration)
    if (!rollbackResult || !rollbackResult.success) {
      const reason = (rollbackResult && rollbackResult.reason) || 'unknown'
      const details = (rollbackResult && rollbackResult.details) || null
      log(`Rollback failed after diff-too-large on iteration ${iteration}: reason=${reason}`)
      return {
        stopReason: 'rollback-error',
        iterations: iteration - 1,
        rollbackReason: reason,
        rollbackDetails: details,
        auditLog,
      }
    }
    return { stopReason: 'diff-too-large', iterations: iteration - 1, auditLog }
  }

  // === Task 6 Step 4: Audit log entry (in-memory + on-disk) ===
  // Persist immediately so a harness crash mid-iteration doesn't lose
  // the audit trail. The script can't write files directly; the agent()
  // call below writes via Bash.
  const entry = {
    iteration,
    issuesBefore: verify.issueCount,
    issuesAfter: null,  // filled in by next iter's Verify pass
    stashSha: (snapshot && snapshot.stashed) ? snapshot.stashSha : null,
    stashMessage: (snapshot && snapshot.stashed) ? snapshot.stashMessage : null,
    changes: fix.changes,
    diffStat: diffSanity,
    // Note: no explicit timestamp field here. The persistAuditLog agent
    // captures the file mtime via the OS at write time, which is the
    // canonical timestamp. Workflow scripts cannot call wall-clock APIs.
  }
  auditLog.push(entry)
  const persistResult = await persistAuditLog(entry)
  if (!persistResult || !persistResult.success) {
    const error = (persistResult && persistResult.error) || 'unknown'
    log(`Audit log persistence failed on iteration ${iteration}: ${error}`)
    return {
      stopReason: 'audit-log-error',
      iterations: iteration - 1,
      auditLogError: error,
      auditLog,
    }
  }
  // Task 6 fills in the stop-condition checks here.
}

log(`Iteration cap (${MAX_ITERATIONS}) reached with issues still remaining.`)
return { stopReason: 'iteration-cap', iterations: MAX_ITERATIONS, auditLog }
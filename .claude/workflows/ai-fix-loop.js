// AI-Fix External Loop — Workflow script (post-review fixes applied).
//
// Runs `crackerjack run -v` to surface residual quality issues,
// dispatches them to a fix agent, re-verifies, repeats until clean
// or capped. After each successful fix iteration, ships the fix
// outcome to Akosha via generate_embedding → store_memory. Full
// design: docs/superpowers/plans/2026-08-06-ai-fix-external-loop.md
//
// Status: All 9 plan tasks complete. Post-implementation multi-agent
// review (code, mcp-integration, workflow-contract, documentation)
// applied: 1 CRITICAL fix (iteration-1 sentinel interaction), 7 HIGH
// fixes (audit-log JSONL, rollback signature, fix-agent-error stash
// leak, issuesAfter back-patch, args.initialIssueGuard, runbook
// baseline correction, Akosha partial-success surfacing), and several
// MEDIUM fixes (phase labels, diff-sanity-error stop reason, audit-
// log-error rollback, etc.). See commit message for full list.

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
let MAX_ITERATIONS = Math.max(REQUESTED_MAX, 10)

// Initial-issue-count guard. A repo with >200 baseline issues is not a
// fix-loop candidate — it's a triage problem. Surfaced as the
// `initial-issue-count-too-high` stop reason in Task 3, not silently
// kicked into a multi-hour loop. Threshold chosen to keep one run
// under the Mahavishnu pool's default 300s timeout (200 iters × ~1s
// per iter cap ≈ budget). Override via `args.initialIssueGuard`.
const INITIAL_ISSUE_GUARD = (args && args.initialIssueGuard) || 200

// `previousIssueCount` starts as `null` to signal "no previous value".
// Earlier revisions used `Number.POSITIVE_INFINITY` as the sentinel,
// but that interacted badly with the `Number.isFinite(countDelta)`
// guard added in Task 6 — on iteration 1 the delta was -Infinity and
// the guard tripped, aborting the loop before any work ran. `null`
// is the correct sentinel because the countDelta block is gated on
// `previousIssueCount !== null`.
let previousIssueCount = null
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
//   { dirty, stashed, stashSha, stashMessage, reason }
// Returns null if required fields are missing or malformed.
//
// Expected agent response shape:
//   dirty: <true-or-false>                         [required]
//   stashed: <true-or-false>                       [required]
//   stashSha: <sha-string>                         [required when stashed=true]
//   stashMessage: <message>                        [required when stashed=true]
//   [reason: <description>]                        [optional, only when dirty=true, stashed=false]
//
// stashMessage is REQUIRED when stashed=true — attemptRollback uses it
// for the `git stash list --grep '^<message>$'` lookup. A null message
// would make the grep anchor to `^$` and match nothing, returning
// 'sha-mismatch' and failing the rollback. Required: dirty, stashed,
// and (when stashed=true) stashSha + stashMessage.
//
// Loose parsing — multiline regex tolerates leading whitespace, surrounding
// prose, and missing optional fields. The hybrid state
// `dirty=true && stashed=true` is rejected as malformed (the agent
// prompt forbids it; the parser enforces the invariant).
function parseSnapshotText(text) {
  if (typeof text !== 'string' || !text.trim()) return null
  const dirtyMatch = text.match(/^\s*dirty:\s*(true|false)\s*$/m)
  const stashedMatch = text.match(/^\s*stashed:\s*(true|false)\s*$/m)
  if (!dirtyMatch || !stashedMatch) return null
  const dirty = dirtyMatch[1] === 'true'
  const stashed = stashedMatch[1] === 'true'
  // Reject the dirty+stashed hybrid: the agent prompt explicitly forbids
  // it, and accepting it would cause the diff-sanity check to compute
  // diffs against a baseline that includes pre-existing dirt.
  if (dirty && stashed) return null
  let stashSha = null
  let stashMessage = null
  if (stashed) {
    const shaMatch = text.match(/^\s*stashSha:\s*(\S+)\s*$/m)
    if (!shaMatch) return null
    stashSha = shaMatch[1].trim()
    const messageMatch = text.match(/^\s*stashMessage:[ \t]*([^\n]*?)[ \t]*$/m)
    if (!messageMatch) return null  // required when stashed=true
    stashMessage = messageMatch[1].trim()
  }
  const reasonMatch = text.match(/^\s*reason:[ \t]*([^\n]*?)[ \t]*$/m)
  const reason = reasonMatch ? reasonMatch[1].trim() : null
  return {
    dirty,
    stashed,
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

// attemptRollback helper (Task 6 + post-review fixes, module scope, async).
// Looks up the iteration's snapshot stash by message, verifies the SHA,
// pops it, and drops it. Returns { success, reason, details } parsed
// from the agent's response, or null if the response is malformed.
//
// The plan documents that the positional `stash@{N}` ref MUST NOT be
// used — only message-based lookup + SHA verification. This handles the
// case where the user adds their own stash between iterations and the
// positional index shifts.
//
// Post-review fix: signature is `(stashSha, stashMessage, iteration, phase)`.
// Earlier revisions took the auditLog and read `auditLog[length-1]`,
// which by the time the diff-sanity rollback fired was the PREVIOUS
// iteration's stash (because `auditLog.push(entry)` runs AFTER fix and
// AFTER diff-sanity, so length-1 was stale). Passing the snapshot
// directly eliminates the wrong-stash bug. `phase` is the script's
// currently-active phase label, used for the agent dispatch's `phase:`
// metadata so logs correlate rollback events to the triggering phase
// ('Verify' for regressed/progress-stalled, 'Fix' for diff-too-large).
async function attemptRollback(stashSha, stashMessage, iteration, phase) {
  if (!stashSha || !stashMessage) {
    log(`No snapshot to roll back to on iteration ${iteration}.`)
    return { success: false, reason: 'no-snapshot' }
  }
  const activePhase = phase || 'Snapshot'
  const result = await agent(
    `In the crackerjack repo, perform a SHA-anchored stash rollback:\n` +
    `1. Run \`git stash list --grep '^${stashMessage}$'\` to find the stash entry by message.\n` +
    `   If multiple entries match, pick the one whose commit SHA matches the captured SHA below.\n` +
    `2. Run \`git rev-parse "<entry>^3"\` and verify the result matches this expected SHA: ${stashSha}\n` +
    `3. If SHA matches: run \`git stash pop "<entry>"\` then \`git stash drop "<entry>"\` to remove the entry.\n` +
    `4. If SHA does NOT match: do NOT pop. Return success=false with reason "sha-mismatch".\n` +
    `5. If pop fails (merge conflict, etc.): return success=false with reason "pop-failed".\n\n` +
    `Respond with EXACTLY these lines:\n` +
    `success: <true-or-false>\n` +
    `reason: <"sha-mismatch"|"pop-failed"|empty-when-success>\n` +
    `details: <mismatch-or-conflict-details-or-empty>\n` +
    `The positional \`stash@{N}\` ref MUST NOT be used.`,
    { label: `rollback-iter-${iteration}`, phase: activePhase }
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

// persistAuditLog helper (Task 6 + post-review fixes, module scope, async).
// Appends a single JSONL entry to AUDIT_LOG_PATH via agent(). Returns
// { success, error } or null if the response is malformed.
//
// Failure triggers the `audit-log-error` stop reason — the loop can't
// continue without an audit trail. The agent MUST NOT overwrite or read
// existing content; it must atomically append a single line.
//
// Post-review fix: line content passed to the prompt is the already-
// JSON-stringified entry (a single `JSON.stringify` call). Earlier
// revisions wrapped the line in a second `JSON.stringify`, producing a
// JSON-escaped string the agent would write verbatim — that put the
// JSONL file into an unparseable state where every line was a string
// instead of an object. The runbook's Step 10 would fail to parse the
// audit log without this fix.
async function persistAuditLog(entry) {
  const line = JSON.stringify(entry)
  const result = await agent(
    `Append a single JSON line to the file \`${AUDIT_LOG_PATH}\` in the crackerjack repo. ` +
    `Create the parent directory \`.crackerjack/audit/\` if missing. ` +
    `Do NOT overwrite or read existing content — just append atomically.\n` +
    `If the append fails (disk full, permission denied, etc.), return success=false with the error description.\n\n` +
    `Line content (write exactly this string as the JSONL record):\n` +
    `${line}`,
    { label: `audit-persist-iter-${entry.iteration}`, phase: 'Fix' }
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

// logAkoshaFixes helper (Task 7 + post-review fixes, module scope, async).
// Best-effort write-only logging of one successful iteration's fixes
// to Akosha. Per Akosha contract compliance:
//   1. generate_embedding(text) → 384-dim vector
//   2. store_memory(memory_id, text, embedding, metadata)
// Custom metadata keys (repo, file, outcome, iteration) are NOT
// preserved by Akosha's metadata normalizer — only `correlation_id`
// round-trips. Fix context is packed into the `text` payload instead.
//
// Deterministic, non-empty memory_id: "ai-fix-loop:iter-<N>:change-<i>:<file>"
// (index `<i>` is the 0-based position in entry.changes; ensures
// memory_id is unique even when the same file appears twice in one
// iteration's changes list. Post-review fix mcp#1.)
//
// The text payload includes the iteration's `outcome` (fixed, regressed,
// etc.) so downstream queries can distinguish clean fixes from rolled-
// back ones. (Post-review fix mcp#4.)
//
// No-op when entry.changes is empty — the empty-CHANGES case from
// parseFixText represents "agent touched nothing this iteration",
// and there's nothing fix-related to log.
//
// The Workflow script cannot call Akosha MCP tools directly, so the
// actual MCP dispatch happens inside an agent() call. The agent
// iterates over entry.changes, building text/memory_id/metadata for
// each, then issues generate_embedding → store_memory sequentially
// per change. Per-change failures are logged and skipped; the agent
// never aborts the whole operation.
//
// Post-review fix mcp#6: the agent MUST emit a structured summary line
// at the end (`STORED: <n>/<total> | FAILED: <k>`) so the script can
// surface partial-failure visibility. `try/catch` only catches sync
// throws; silent agent failures (zero-vector embeddings, agent that
// "succeeds" but logs nothing) were invisible before. The summary
// closes that observability gap.
//
// The caller wraps this in try/catch so any thrown error (agent
// failure, MCP timeout, etc.) does not propagate to the loop. This
// helper is observability infrastructure, not control flow.
async function logAkoshaFixes(entry) {
  if (!entry || !entry.changes || entry.changes.length === 0) {
    return  // nothing to log; intentional no-op
  }
  const outcome = entry.outcome || 'fixed'
  const changesJson = JSON.stringify(entry.changes)
  await agent(
    `In the crackerjack repo, log a memory to Akosha for each fix in this iteration's audit entry. ` +
    `The audit entry's iteration is ${entry.iteration}, the outcome is ${outcome}, and the changes array has ${entry.changes.length} item(s):\n\n` +
    `  ${changesJson}\n\n` +
    `For EACH change (index 0-based, position in the array above), perform the following sequence (Akosha contract — store_memory requires both a non-empty memory_id and a 384-dim embedding):\n` +
    `1. Build the text payload. Pack fix context into text because custom metadata keys don't round-trip:\n` +
    `   text = "Crackerjack ai-fix-loop iter=${entry.iteration} | outcome=${outcome} | file=<change.file> | <change.description>"\n` +
    `2. Build a deterministic, non-empty memory_id. The `<i>` index ensures uniqueness even if the same file appears twice:\n` +
    `   memory_id = "ai-fix-loop:iter-${entry.iteration}:change-<i>:<change.file>"\n` +
    `   If `<change.file>` is empty, use a placeholder like "(no-file)" so memory_id remains non-empty.\n` +
    `3. Build metadata. CRITICAL: only `correlation_id` and `type` are preserved by Akosha's metadata normalizer — do NOT add repo/file/outcome/iteration keys; those go in text only. Any other key is silently dropped:\n` +
    `   metadata = { correlation_id: "ai-fix-loop:iter-${entry.iteration}", type: "session_memory" }\n` +
    `4. Call the MCP tool \`mcp__akosha__generate_embedding\` with the text. The result is a dict with an "embedding" key whose value is the 384-dim float vector — extract result["embedding"] before passing to store_memory.\n` +
    `5. If the embedding succeeded, call \`mcp__akosha__store_memory\` with memory_id, text, embedding, and metadata. Pass them as named arguments matching the tool's schema.\n` +
    `6. If the embedding call returns an error OR store_memory returns an error for a specific change, log a warning but CONTINUE with the next change. Do NOT abort the whole operation. Skip the change silently — do not retry.\n` +
    `7. After processing all ${entry.changes.length} changes, respond with EXACTLY this one summary line (the workflow script reads this for observability):\n` +
    `   STORED: <successful-count>/${entry.changes.length} | FAILED: <failed-count>\n\n` +
    `This is best-effort write-only observability. Do NOT query Akosha for prior fixes. ` +
    `Do NOT abort the workflow on any failure — log and continue.`,
    { label: `akosha-log-iter-${entry.iteration}`, phase: 'Fix' }
  )
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

  // === Task 6 Step 1 + post-review fixes: No-improvement / regressed / progress-stalled check ===
  // Evaluates whether the PREVIOUS iteration's fix was effective. Runs after
  // Verify and before Snapshot so a regressed/stalled loop can roll back
  // the previous iteration's stash BEFORE taking a new snapshot.
  //
  // Post-review fix: gate the countDelta block on `previousIssueCount !== null`.
  // Iteration 1 has no previous value; computing a delta against null would
  // yield NaN and trip the `Number.isFinite` guard below, aborting the loop
  // before any work runs. The null-sentinel handles this correctly.
  //
  // Post-review fix: rollback uses the snapshot directly from the previous
  // iteration's auditLog entry (the regressed/stalled case is rolling back
  // the PREVIOUS iter's fix), with `phase: 'Verify'` so log correlation
  // matches the triggering phase.
  if (previousIssueCount !== null) {
    const countDelta = verify.issueCount - previousIssueCount
    if (!Number.isFinite(countDelta)) {
      log(`Non-finite count delta on iteration ${iteration} — aborting to avoid silent infinite loop.`)
      return { stopReason: 'verify-error', iterations: iteration - 1, auditLog }
    }
    if (countDelta > 0) {
      log(`Issue count increased (was ${previousIssueCount}, now ${verify.issueCount}) — rolling back.`)
      const prevEntry = auditLog[auditLog.length - 1]
      if (prevEntry && prevEntry.stashSha && prevEntry.stashMessage) {
        const rollbackResult = await attemptRollback(
          prevEntry.stashSha, prevEntry.stashMessage, iteration, 'Verify'
        )
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
      } else {
        log(`Regression detected on iteration ${iteration} but no previous snapshot to roll back to.`)
      }
      return { stopReason: 'regressed', iterations: iteration - 1, auditLog }
    }
    if (countDelta === 0) {
      consecutiveFlat += 1
      if (consecutiveFlat >= FLAT_THRESHOLD) {
        log(`No progress for ${consecutiveFlat} consecutive iterations — rolling back and stopping.`)
        const prevEntry = auditLog[auditLog.length - 1]
        if (prevEntry && prevEntry.stashSha && prevEntry.stashMessage) {
          const rollbackResult = await attemptRollback(
            prevEntry.stashSha, prevEntry.stashMessage, iteration, 'Verify'
          )
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
        } else {
          log(`Progress-stalled on iteration ${iteration} but no previous snapshot to roll back to.`)
        }
        return { stopReason: 'progress-stalled', iterations: iteration - 1, auditLog }
      }
      log(`Flat iteration ${consecutiveFlat}/${FLAT_THRESHOLD} — continuing.`)
    } else {
      consecutiveFlat = 0
    }
  }
  // Back-patch the previous iteration's `issuesAfter`. Each entry stores
  // `issuesAfter: null` at write time; this overwrites it with the current
  // Verify pass's count, so the persisted JSONL has the full before/after
  // per-iter delta available for postmortem review. (Post-review fix 3.2.)
  if (auditLog.length > 0) {
    auditLog[auditLog.length - 1].issuesAfter = verify.issueCount
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
    // Post-review fix 2.2: roll back the just-applied fix so the
    // snapshot stash doesn't leak onto the stack. Without this, the
    // runbook's Step 9 expectation ("no leftover ai-fix-loop-iter-*
    // entries") is violated by every malformed-fix-agent-error path.
    if (snapshot && snapshot.stashSha && snapshot.stashMessage) {
      await attemptRollback(
        snapshot.stashSha, snapshot.stashMessage, iteration, 'Fix'
      )
    }
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
    { label: `diff-sanity-iter-${iteration}`, phase: 'Fix' }
  )
  const diffSanity = parseDiffStatText(diffStatText)
  if (!diffSanity) {
    log(`Diff-sanity agent returned malformed result on iteration ${iteration} — aborting.`)
    // Post-review fix 2.2 + claude#4: roll back the just-applied fix so
    // the snapshot stash doesn't leak onto the stack, AND emit a
    // dedicated `diff-sanity-error` stop reason (not the misclassified
    // `fix-agent-error`) so operators can grep for the right agent's
    // label when investigating.
    if (snapshot && snapshot.stashSha && snapshot.stashMessage) {
      await attemptRollback(
        snapshot.stashSha, snapshot.stashMessage, iteration, 'Fix'
      )
    }
    return { stopReason: 'diff-sanity-error', iterations: iteration - 1, auditLog }
  }
  if (diffSanity.filesChanged > 5 || diffSanity.linesChanged > 100 || diffSanity.forbiddenTouched.length > 0) {
    log(`Fix exceeded limits on iteration ${iteration}: files=${diffSanity.filesChanged}, lines=${diffSanity.linesChanged}, forbidden=${diffSanity.forbiddenTouched.join(',')} — rolling back.`)
    // Post-review fix 2.1: pass the CURRENT iteration's snapshot
    // directly (the previous auditLog-based lookup would have read
    // auditLog[length-1] which is the PREVIOUS iter's entry at this
    // point, undoing both iters' fixes).
    const rollbackResult = await attemptRollback(
      snapshot.stashSha, snapshot.stashMessage, iteration, 'Fix'
    )
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
  //
  // Post-review fix mcp#4: include `outcome` in the entry so Akosha can
  // distinguish "fixed cleanly" from "fixed then rolled back". The
  // outcome is packed into the Akosha text payload (per the contract,
  // custom metadata keys don't round-trip).
  const entry = {
    iteration,
    issuesBefore: verify.issueCount,
    issuesAfter: null,  // back-patched at top of next iter's Verify (see countDelta block)
    outcome: 'fixed',  // the loop only reaches here if diff-sanity passed
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
    // Post-review fix claude#5: roll back the just-applied fix before
    // returning so the working tree doesn't end up in an unrecorded-
    // modified state. The fix was applied (snapshot stash popped),
    // and without this the audit log has no record of which iteration
    // produced the modified files.
    if (snapshot && snapshot.stashSha && snapshot.stashMessage) {
      await attemptRollback(
        snapshot.stashSha, snapshot.stashMessage, iteration, 'Fix'
      )
    }
    return {
      stopReason: 'audit-log-error',
      iterations: iteration - 1,
      auditLogError: error,
      auditLog,
    }
  }

  // === Task 7: Akosha passive fix-outcome logging (best-effort) ===
  // Per Akosha contract: generate_embedding(text) → store_memory(...).
  // Custom metadata keys don't round-trip; fix context is packed into
  // text. Best-effort: a failure here MUST NOT abort the loop. The
  // outer try/catch absorbs any thrown error from the agent call; the
  // agent prompt itself also instructs per-change skip-and-continue.
  try {
    await logAkoshaFixes(entry)
  } catch (err) {
    log(`Akosha logging failed for iteration ${iteration}: ${err} — continuing.`)
  }
}

log(`Iteration cap (${MAX_ITERATIONS}) reached with issues still remaining.`)
return { stopReason: 'iteration-cap', iterations: MAX_ITERATIONS, auditLog }
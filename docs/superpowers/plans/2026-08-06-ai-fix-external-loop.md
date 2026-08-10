# AI-Fix External Loop + Akosha Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the external, agent-driven replacement for crackerjack's deleted `--ai-fix` capability: a `Workflow` script that runs `crackerjack run -v`, dispatches residual issues to an agent for fixing, re-verifies, and repeats until clean or capped — with git snapshot/rollback safety, a durable audit log, and a passive fix-outcome log to Akosha.

**Architecture:** A named `Workflow` script (`.claude/workflows/ai-fix-loop.js`, checked into the crackerjack repo for durability/review) drives the loop entirely through `agent()` calls with structured schemas — Workflow scripts have no direct Bash/filesystem access, so every external action (running crackerjack, git snapshot/rollback, editing files, querying Akosha) happens inside an `agent()` invocation, while the script's own JS control flow owns the loop invariants (iteration count, no-improvement detection, stop reasons) deterministically rather than relying on agent judgment for safety-critical decisions.

**Note on `-v` vs `--json` (revised 2026-08-06, mid-implementation):** This plan originally assumed `crackerjack run --json` existed and depended on it. Investigation during the sibling plan's Task 3 found this is false — `run` has no `--json` flag today, and building one requires real design work (suite aggregation, Issue classification) that isn't a prerequisite for this plan. Since the Verify step below was always going to hand output to an `agent()` call for interpretation rather than `JSON.parse()` it directly in the script body, an LLM agent can interpret `crackerjack run -v`'s existing human-readable Rich-formatted output equally well. This plan uses `-v` throughout; `CrackerjackRunResult` (delivered in the sibling plan) remains available as an internal model but is not a dependency of this plan.

**Tech Stack:** Claude Code `Workflow` tool (JS, no TypeScript, no `Date.now()`/`Math.random()`), `crackerjack run -v`'s existing human-readable output (interpreted per-iteration by an `agent()` call, not machine-parsed), Akosha MCP tools (exact tool names TBD via `ToolSearch` — see Task 7).

**Reference spec:** [docs/superpowers/specs/2026-08-06-ai-fix-removal-external-loop-design.md](../specs/2026-08-06-ai-fix-removal-external-loop-design.md), sections 5-6.

## Review Findings Addressed (2026-08-10)

This plan was revised in response to a multi-agent review (CLI assumptions, loop architecture, Workflow/Akosha contracts). The critical issues addressed:

- **SHA-anchored stash refs** (Task 4, Task 6) — positional `stash@{N}` is unsafe when a user adds their own stash between iterations; using `git rev-parse stash@{N}^3` + grep-by-message for re-resolution.
- **Akosha contract compliance** (Task 7) — `store_memory` requires non-empty `memory_id` and a 384-dim embedding; the call sequence `generate_embedding(text)` → `store_memory(...)` is mandatory.
- **Audit log persistence** (Task 2, Task 6) — in-memory `auditLog` is lost on crash; per-iteration append to `.crackerjack/audit/ai-fix-loop.jsonl` enables resume/recovery.
- **`Number.isFinite` guard** (Task 6) — `NaN >= previousIssueCount` is `false`, silently infinite-looping on malformed upstream JSON.
- **Consecutive-flat counter** (Task 6) — single-iter plateau is noise; require 2-3 flat iterations before declaring `progress-stalled`.
- **Clean-tree invariant** (Task 4) — snapshot phase must detect concurrent user edits/pulls before stashing.
- **Post-fix diff sanity** (Task 6) — fix-agent prompts are advisory only; cap `filesChanged`/`linesChanged` and blocklist `tests/`, `*.toml`, etc.
- **Expanded stop-reason taxonomy** (Task 6) — `fixer-error` was conflating verify/snapshot/fix/rollback failures; split into `verify-error`, `snapshot-error`, `fix-agent-error`, `rollback-error`, `concurrent-change-detected`, `diff-too-large`.
- **Scaled iteration cap** (Task 2) — `max(10, ceil(initialIssueCount * 1.5))`.
- **Loose JSON parsing** (Task 3, 5) — `agent({schema})` has a documented infinite-loop bug; avoid schema validation, parse returned text loosely.

## Global Constraints

- No `Date.now()`/`Math.random()`/argless `new Date()` anywhere — **not in code, comments, or prompt strings**. The validator rejects all three (per `~/.claude/cache/changelog.md`), not just executable code. Audit every prompt and comment before saving.
- The script must not fabricate or predict `agent()` results — every loop decision reads a real returned value.
- No placeholders, TODOs, or dummy data (CLAUDE.md rule #3).
- Every git-mutating action (snapshot, rollback, fix) happens through an `agent()` call, since the Workflow script itself cannot run Bash directly.
- Wall-clock timeout is enforced by the **caller** (use `dispatch_to_pool(timeout=N)` from Mahavishnu, or a cron wrapper with the `timeout` command), not by the script itself — `Date.now()` is unavailable.
- The script requires a **clean working tree** at start. Concurrent edits, pulls, or other agent runs during the loop are unsupported (see Task 4 Step 1's clean-tree invariant).

## Precondition

This plan depends only on `crackerjack run -v` producing informative output — no new crackerjack CLI wiring is required. **Task 1 below verifies this precondition before any other work starts** — do not proceed past Task 1 if it fails.

## File Structure

**New files:**
- `.claude/workflows/ai-fix-loop.js` — the Workflow script itself.
- `tests/integration/test_ai_fix_loop_acceptance.md` — a manual acceptance-test runbook (this is agent-orchestration code, not a pytest-testable unit — see Task 9 for why).
- `.crackerjack/audit/` — created at runtime; holds the per-iteration `ai-fix-loop.jsonl` log (Task 6 Step 4). The directory should be `.gitignore`d — it's a per-run artifact, not source.

**Modified files:**
- `CLAUDE.md` — replace the removed `--ai-fix` usage in "Most Common Commands" with the new workflow invocation.
- `.gitignore` — required changes (discovered 2026-08-10 during Task 2 commit):
  - Add `.claude/*` rule (replace existing `.claude/` rule if present) so files inside `.claude/` are ignored WITHOUT ignoring the directory itself.
  - Add `!.claude/workflows/` exception to re-include the canonical Workflow scripts directory. Note: per gitignore semantics, you CANNOT re-include a file if its parent directory is excluded — that is why we use `.claude/*` (file-pattern) instead of `.claude/` (dir-pattern).
  - `.crackerjack/audit/` is already covered by the existing `.crackerjack/` rule; no additional line needed.

---

### Task 1: Verify the `run -v` precondition

**Files:** None modified — verification task.

**Interfaces:**
- Consumes: `crackerjack run -v`'s existing human-readable output (no new crackerjack code required).

- [ ] **Step 1: Confirm `run -v` produces informative output on both a dirty and a clean repo state**

Run: `uv run python -m crackerjack run -v 2>&1 | tail -40`
Expected: a per-hook results section similar to:
```
Fast Hook Results:
 - codespell        :: FAILED | issues=1
 - ruff-check       :: FAILED | issues=999
```

**Definition of "clean" (clarified 2026-08-10 from Task 1 verification):** A "clean repo state" means a **clean working tree** — no uncommitted modifications, no untracked files — NOT "zero issues in committed code". At the time of Task 1 verification, the crackerjack HEAD had a clean working tree but still exhibited 1014 baseline issues across 5 hooks (codespell=1, ruff-check=999, check-local-links=10, skill-coverage=2, pip-audit=2). The fix loop must therefore handle `initialIssueCount > 0` even on a "clean" working tree — this is exactly what the `INITIAL_ISSUE_GUARD` constant (Task 2) protects against.
Record the actual current output shape (hook names, status markers, issue counts) — this is what Task 3's `agent()` prompt will describe to the verify-agent as the expected shape to interpret. If `run -v` produces no usable per-hook detail at all (e.g., only a bare pass/fail with zero information about what failed), stop and report back — the whole Verify-phase design depends on there being *something* informative to interpret, even if it isn't JSON.

**Output normalization note for Task 3's agent prompt:** The `-v` output uses Rich-formatted markup — ANSI escape codes (colors, bold), UTF-8 emoji (`✅`, `❌`, `⏳`, `🔍`), and Unicode box-drawing characters (`─`, `│`, `╭`, `╰`) — plus alignment whitespace (`name............... ❌`). When describing the expected shape to the verify-agent in Task 3, explicitly call out these markers (the agent reads the raw bytes; do not assume it strips them) and tell it to look for the structured `name :: FAILED | duration | issues=N` summary lines and the Ruff-style `path:line: CODE message` per-issue lines. The Task 3 agent prompt below includes this guidance.

- [ ] **Step 2: Confirm the command's exit code is a reliable clean/dirty signal**

Run: `uv run python -m crackerjack run -v; echo "exit=$?"` on the current (post-extraction-work) repo state, and separately reason about what the exit code would be on a genuinely clean run (0) vs. any failure (non-zero). The Verify agent will use both the exit code and the printed hook summary together, not exit code alone, since a non-zero exit could mean either "hooks found issues" or "the command itself crashed" (per the sibling plan's Task 1 finding that `--skip-hooks --run-tests` has a pre-existing crash bug unrelated to hook findings) — note in your report which failure mode is distinguishable from the output alone and which isn't.

**Exit-code semantics verified 2026-08-10:** Both the dirty-tree and clean-tree runs exited with code 1 (failure with informative `Fast Hook Results` summary present). The crash-mode test (`crackerjack run --skip-hooks --run-tests`) also exited 1 but with **no `Fast Hook Results` header** — instead it printed `💥 Test execution error after 0.3s: 'PosixPath' object has no attribute 'startswith'`. Distinguishing rule: presence of a `Fast Hook Results` summary line = "issues found" (informative failure); absence of that summary + presence of a `💥` or `Workflow failed: Task tests failed` marker = "crashed". The verify-agent prompt in Task 3 must encode this rule.

---

### Task 2: Write the Workflow script skeleton with loop scaffolding

**Files:**
- Create: `.claude/workflows/ai-fix-loop.js`

**Interfaces:**
- Produces: a `meta` export and the top-level loop shape that later tasks fill in. `args` accepted: `{ maxIterations?: number }` (default 10).

- [ ] **Step 1: Write the skeleton**

```js
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
```

- [ ] **Step 2: Validate the script parses**

Run the Workflow tool with this script and no real loop body executed yet (it will immediately hit the iteration-cap return on iteration 1 since Tasks 3-6 haven't added the verify call). Confirm it returns `{ stopReason: 'iteration-cap', iterations: 10, auditLog: [] }` without a syntax error. This is a smoke test of the skeleton, not of the loop's real behavior.

- [ ] **Step 3: Commit**

```bash
git add .claude/workflows/ai-fix-loop.js
git commit -m "feat(ai-fix-loop): workflow script skeleton with loop scaffolding"
```

---

### Task 3: Implement the Verify phase

**Files:**
- Modify: `.claude/workflows/ai-fix-loop.js`

**Interfaces:**
- Consumes: the `parseVerifyText` helper from Task 2 (skeleton phase).
- Produces: `verify` object per iteration, with `cleanExit`, `issueCount`, `issuesSummary` — consumed by Task 6's stop-condition checks and Task 5's fix-dispatch prompt.

- [ ] **Step 1: Replace the `// Task 3 fills in the Verify phase here.` comment with the real call**

Use the actual output shape recorded in Task 1's Step 1 report in place of the illustrative example below — describe it concretely to the agent rather than assuming the exact wording:

```js
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
    `If the command crashes or produces no usable output (distinct from "hooks failed" — a crash means the tool itself errored), set cleanExit=false, issueCount=-1, and put the crash description in issuesSummary.`,
    { label: `verify-iter-${iteration}`, phase: 'Verify' }
  )
  // Parse the agent's text response loosely.

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
```

The helper `parseVerifyText(text)` lives at module scope and returns `{ cleanExit, issueCount, issuesSummary }` by regex-extracting the three labeled lines. Falls back to `verify-error` semantics if any line is missing or malformed.

- [ ] **Step 2: Test against this repo's real current state**

Run the workflow with `maxIterations: 1` against this repo as-is. Confirm the `verify` step correctly reports whether the repo is currently clean or not, and that `issueCount`/`issuesSummary` plausibly match what `python -m crackerjack run -v` actually shows when run directly (spot-check by eye, not exact string matching — the agent is summarizing, not transcribing).

- [ ] **Step 3: Commit**

```bash
git add .claude/workflows/ai-fix-loop.js
git commit -m "feat(ai-fix-loop): implement Verify phase (run crackerjack -v, agent-interpreted)"
```

---

### Task 4: Implement the Snapshot phase

**Files:**
- Modify: `.claude/workflows/ai-fix-loop.js`

**Interfaces:**
- Produces: `snapshot` object per iteration with `stashRef: string` — consumed by Task 6's rollback logic.

- [ ] **Step 1: Replace the `// Task 4 fills in the Snapshot phase here.` comment**

```js
  phase('Snapshot')
  // Snapshot captures BOTH the positional ref AND a durable SHA handle.
  // The positional ref (`stash@{0}`) can shift if the user adds their
  // own stash between iterations; the SHA (`<rev>^3`) survives any
  // positional reshuffling and is used at rollback time.
  const snapshotText = await agent(
    `In the crackerjack repo, perform a snapshot before this iteration's fix attempt:\n` +
    `1. Run \`git status --short\` and verify the dirty set matches what this loop expects to snapshot. ` +
    `If there are unexpected changes (e.g., user edits, an unrelated file change), DO NOT stash — instead respond with \`dirty=true, stashed=false, reason="<describe the unexpected changes>"\`.\n` +
    `2. If the tree is already clean (no fix applied yet, or last iteration rolled back), respond with \`dirty=false, stashed=false\` and stop.\n` +
    `3. Otherwise run \`git stash push -u -m "ai-fix-loop-iter-${iteration}"\` and then run \`git rev-parse "stash@{0}^3"\` to get the commit SHA the stash represents. ` +
    `Respond with EXACTLY these three lines (nothing else):\n` +
    `dirty: <true-or-false>\n` +
    `stashed: <true-or-false>\n` +
    `stashSha: <the-rev-parse-output-or-empty>\n` +
    `If stashed=true, also include \`stashMessage: ai-fix-loop-iter-${iteration}\` on a fourth line.`,
    { label: `snapshot-iter-${iteration}`, phase: 'Snapshot' }
  )
  const snapshot = parseSnapshotText(snapshotText)
  if (!snapshot) {
    log(`Snapshot agent returned malformed result on iteration ${iteration} — aborting.`)
    return { stopReason: 'snapshot-error', iterations: iteration - 1, auditLog }
  }
  if (snapshot.dirty && !snapshot.stashed) {
    log(`Unexpected dirty state detected on iteration ${iteration}: ${snapshot.reason} — aborting to avoid clobbering user changes.`)
    return { stopReason: 'concurrent-change-detected', iterations: iteration - 1, auditLog }
  }
```

The helper `parseSnapshotText(text)` lives at module scope and parses the labeled lines. Stores both `stashRef: "stash@{0}"` (positional) and `stashSha: "<sha>"` (durable) plus `stashMessage` in the parsed object — Task 6's rollback uses the SHA + message to locate and verify the entry even if the positional index has shifted.

- [ ] **Step 2: Test the stash-or-skip branch**

Run the workflow against a repo with (a) a clean working tree and (b) a deliberately dirtied working tree (touch a file, don't commit). Confirm `stashed=false` in case (a) and `stashed=true` with a real `stashRef` in case (b).

- [ ] **Step 3: Commit**

```bash
git add .claude/workflows/ai-fix-loop.js
git commit -m "feat(ai-fix-loop): implement Snapshot phase (conditional git stash before each fix attempt)"
```

---

### Task 5: Implement the Fix phase

**Files:**
- Modify: `.claude/workflows/ai-fix-loop.js`

**Interfaces:**
- Consumes: `verify.issuesSummary` from Task 3.
- Produces: `fix` object per iteration with `changes: Array<{file: string, description: string}>` — appended to `auditLog` in Task 6.

- [ ] **Step 1: Replace the `// Task 5 fills in the Fix phase here.` comment**

```js
  phase('Fix')
  // Loose-text parsing — `agent({schema})` has the infinite-loop bug noted in Task 3.
  const fixText = await agent(
    `You are fixing quality issues in the crackerjack repo reported by \`crackerjack run -v\`. Here is a summary of the current issues: ${verify.issuesSummary}\n\n` +
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
```

The helper `parseFixText(text)` extracts the `CHANGES:` block entries. Returns `{ changes: [{file, description}, ...] }`.

- [ ] **Step 2: Test against a real, small, known issue**

Deliberately introduce one trivial, real crackerjack-detectable issue (e.g., an unused import) in a scratch branch, run the workflow with `maxIterations: 1`, and confirm the `fix` step's returned `changes` list correctly names the file and describes the fix that was actually made (verify with `git diff`, not just the agent's self-report).

- [ ] **Step 3: Commit**

```bash
git add .claude/workflows/ai-fix-loop.js
git commit -m "feat(ai-fix-loop): implement Fix phase (dispatch residual issues to an agent)"
```

---

### Task 6: Implement stop-condition checks, rollback, audit log, and diff-sanity

**Files:**
- Modify: `.claude/workflows/ai-fix-loop.js`

**Interfaces:**
- Consumes: `verify`, `snapshot`, `fix` from Tasks 3-5.
- Produces: the loop's final return value — `{ stopReason: <expanded-taxonomy>, iterations: number, auditLog: Array }`.

**Stop reason taxonomy (final form):**

| Reason | Meaning | Operator action |
|---|---|---|
| `'clean'` | Zero issues, all fixed | None — success |
| `'initial-issue-count-too-high'` | First Verify found more than `INITIAL_ISSUE_GUARD` (default 200) issues — fix-loop not appropriate, triage needed | Triage largest-bucket failures first, then re-run |
| `'progress-stalled'` | 2+ consecutive iterations with no count reduction | Inspect audit log, accept partial progress |
| `'regressed'` | Issue count increased | Auto-rollback already attempted; inspect git state |
| `'iteration-cap'` | Hit `MAX_ITERATIONS` | Inspect audit log for partial progress, may want to re-run |
| `'verify-error'` | Verify agent returned malformed result OR reported a crackerjack crash | Investigate the verify phase, possibly rerun |
| `'snapshot-error'` | Snapshot agent returned malformed result | Investigate snapshot phase |
| `'fix-agent-error'` | Fix agent returned malformed result | Investigate fix phase |
| `'rollback-error'` | Stash pop after no-improvement failed | Manual `git stash list` + `git checkout` |
| `'concurrent-change-detected'` | Working tree was dirty with unexpected changes when snapshot ran | Resolve user edits, re-run |
| `'diff-too-large'` | Fix agent exceeded the 5-files/100-lines blocklist from Task 5 Step 1 | Reduce fix scope manually, re-run |
| `'akosha-best-effort'` | Akosha logging partially failed but loop succeeded | None — logging is best-effort |

- [ ] **Step 1: Add the no-improvement / rollback check, placed after Verify (Task 3) and before Snapshot (Task 4) each iteration**

```js
  // Count-delta and consecutive-flat tracking.
  const countDelta = verify.issueCount - previousIssueCount
  if (!Number.isFinite(countDelta)) {
    log(`Non-finite count delta on iteration ${iteration} — aborting to avoid silent infinite loop.`)
    return { stopReason: 'verify-error', iterations: iteration - 1, auditLog }
  }
  if (countDelta > 0) {
    log(`Issue count increased (was ${previousIssueCount}, now ${verify.issueCount}) — rolling back.`)
    await attemptRollback(auditLog, iteration)
    return { stopReason: 'regressed', iterations: iteration - 1, auditLog }
  }
  if (countDelta === 0) {
    consecutiveFlat += 1
    if (consecutiveFlat >= FLAT_THRESHOLD) {
      log(`No progress for ${consecutiveFlat} consecutive iterations — rolling back and stopping.`)
      await attemptRollback(auditLog, iteration)
      return { stopReason: 'progress-stalled', iterations: iteration - 1, auditLog }
    }
    log(`Flat iteration ${consecutiveFlat}/${FLAT_THRESHOLD} — continuing.`)
  } else {
    consecutiveFlat = 0
  }
  previousIssueCount = verify.issueCount
```

- [ ] **Step 2: Implement SHA-anchored rollback (helper at module scope)**

`attemptRollback(auditLog, iteration)` reads `auditLog[auditLog.length - 1]` for the last snapshot's `stashMessage` and `stashSha`, then runs an `agent()` call that:

1. `git stash list --grep '^<stashMessage>$'` to find the entry by message (positional index may have shifted).
2. Verify the entry's commit SHA matches the captured `stashSha` (via `git rev-parse "<entry>^3"`).
3. If SHA matches: `git stash pop "<entry>"`, then `git stash drop "<entry>"` to prevent accumulation.
4. If SHA mismatch: abort with `rollback-error` rather than guess.

The positional `stashRef` (`stash@{N}`) is never used for rollback. Document this in the helper's leading comment.

- [ ] **Step 3: Add post-fix diff sanity check (after Fix phase, before audit-log append)**

```js
  // Post-fix diff sanity — fix-agent prompts are advisory; cap scope.
  const diffStatText = await agent(
    `Run \`git diff --stat\` and \`git diff --name-only\` from the snapshot SHA in the crackerjack repo. ` +
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
  if (diffSanity.filesChanged > 5 || diffSanity.linesChanged > 100 || diffSanity.forbiddenTouched) {
    log(`Fix exceeded limits on iteration ${iteration}: files=${diffSanity.filesChanged}, lines=${diffSanity.linesChanged}, forbidden=${diffSanity.forbiddenTouched} — rolling back.`)
    await attemptRollback(auditLog, iteration)
    return { stopReason: 'diff-too-large', iterations: iteration - 1, auditLog }
  }
```

- [ ] **Step 4: Append to the audit log (in-memory and on-disk)**

```js
  const entry = {
    iteration,
    issuesBefore: verify.issueCount,
    issuesAfter: null,  // filled in by next iter's Verify
    stashSha: snapshot.stashed ? snapshot.stashSha : null,
    stashMessage: snapshot.stashed ? snapshot.stashMessage : null,
    changes: fix.changes,
    diffStat: diffSanity,
  }
  auditLog.push(entry)
  // Persist immediately to disk so a harness crash mid-iteration
  // doesn't lose the audit trail. This requires an `agent()` call
  // since the script itself can't write files.
  await agent(
    `Append this JSON line to the file \`${AUDIT_LOG_PATH}\` (create the parent dir if missing). ` +
    `Use a JSON.stringify call from a Bash heredoc or python -c. Line content:\n` +
    `${JSON.stringify(entry)}`,
    { label: `audit-persist-iter-${iteration}`, phase: 'Snapshot' }
  )
```

- [ ] **Step 5: Assemble the full loop body in order**

Final iteration body order is:

1. Verify (Task 3) — with `parseVerifyText` and `Number.isFinite` guard
2. Clean-exit check (Task 3)
3. Initial-issue-count + MAX_ITERATIONS adjustment (Task 3, on first iter only)
4. **No-improvement / regressed / progress-stalled check (Task 6 Step 1)**
5. Snapshot (Task 4) — with clean-tree invariant
6. Fix (Task 5) — with hard constraints in prompt
7. **Diff-sanity check (Task 6 Step 3)**
8. **Audit-log append + persist (Task 6 Step 4)**

Re-read the full file after assembly to confirm no phase was duplicated or dropped during the incremental edits across Tasks 3-6.

- [ ] **Step 6: Test the no-improvement path (progress-stalled)**

Deliberately construct a scenario where the Fix agent's changes don't reduce the issue count (e.g., point it at an issue type it can't actually fix) — and run for 2 iterations. Confirm the loop correctly detects flat progress, triggers rollback, and returns `stopReason: 'progress-stalled'` rather than looping further.

- [ ] **Step 7: Test the regressed path**

Deliberately construct a scenario where the Fix agent's changes increase the issue count. Confirm the loop correctly detects the regression, triggers rollback, and returns `stopReason: 'regressed'`.

- [ ] **Step 8: Test the iteration-cap path**

Run with `maxIterations: 2` against a repo state with more than 2 genuinely fixable issues spread across iterations. Confirm it stops at the cap with `stopReason: 'iteration-cap'` and a populated `auditLog` covering both iterations.

- [ ] **Step 9: Verify on-disk audit log persistence**

After each test above, read `.crackerjack/audit/ai-fix-loop.jsonl` and confirm it contains one JSON line per completed iteration, matching the in-memory `auditLog` array. Stop reason is NOT in the persisted entries — that's only known at loop end.

- [ ] **Step 10: Note the timeout limitation explicitly**

This implementation has no independent wall-clock timeout — `Date.now()` is unavailable in Workflow scripts. Each `agent()` call is bounded only by the harness's own per-agent turn/time limits, not by this script. Wall-clock timeout is enforced by the **caller** via `dispatch_to_pool(timeout=N)` from Mahavishnu, or a cron wrapper with the `timeout` command. Document this as a known constraint in the script's header comment.

- [ ] **Step 11: Commit**

```bash
git add .claude/workflows/ai-fix-loop.js
git commit -m "feat(ai-fix-loop): stop conditions, SHA-anchored rollback, diff sanity, audit log"
```

---

### Task 7: Wire the Akosha passive-logging hook

**Files:**
- Modify: `.claude/workflows/ai-fix-loop.js`

**Interfaces:**
- Consumes: each `auditLog` entry's `changes` list from Task 6.
- Produces: no new return value — this is a side-effecting write to Akosha after the loop concludes.

- [ ] **Step 1: Discover the real Akosha tool names**

Run: `ToolSearch` with query `"akosha store memory generate embedding"` (via the ToolSearch tool, not guessed) to get the exact current tool names and parameter schemas — do not assume `mcp__akosha__store_memory`/`mcp__akosha__generate_embedding` are correct without confirming.

- [ ] **Step 2: Add the logging call after the loop's final return is computed, before actually returning**

Restructure the loop slightly so the final result is captured in a variable before returning, then log each successful iteration's fix from `auditLog`:

```js
  // After the for-loop, before the final `return`.
  //
  // Akosha contract compliance — `store_memory` requires both a
  // non-empty `memory_id` AND a 384-dim `embedding` vector. The
  // sequence is mandatory:
  //   1. Generate embedding via `generate_embedding(text)`
  //   2. Call `store_memory(memory_id, text, embedding, metadata)`
  //
  // Custom metadata keys (repo, file, outcome, iteration) are NOT
  // preserved by Akosha's metadata normalizer — only `correlation_id`
  // round-trips. Pack fix context into the `text` payload instead.
  //
  // Use `batch_store_memories` to ship one iteration's fixes in a
  // single call instead of one-call-per-change.
  await agent(
    `For each change in this iteration's audit log entry, log a memory to Akosha using ` +
    `\`batch_store_memories\`. For each change, build:\n` +
    `  - text: "Crackerjack ai-fix-loop iter=${entry.iteration} | file=${change.file} | ${change.description}"\n` +
    `  - memory_id: "ai-fix-loop:iter-${entry.iteration}:${change.file}" (deterministic, non-empty)\n` +
    `  - metadata: { correlation_id: "ai-fix-loop:iter-${entry.iteration}", type: "session_memory" }\n` +
    `Then for EACH memory's text, FIRST call \`generate_embedding(text)\` to get a 384-dim vector, ` +
    `THEN call \`store_memory\` (or build the full batch with embeddings and call \`batch_store_memories\` once). ` +
    `Skip any change where the embedding call fails — log a warning but continue.\n\n` +
    `This is best-effort write-only logging. Do not query Akosha for prior fixes. ` +
    `If a call fails, log the error and continue — DO NOT abort the workflow result.`,
    { label: `akosha-log-iter-${entry.iteration}`, phase: 'Fix' }
  )
```

(Replace `batch_store_memories` / `store_memory` / `generate_embedding` with the exact tool names confirmed in Step 1 — they are confirmed to exist in `/Users/les/Projects/akosha/akosha/mcp/tools/session_buddy_tools.py` and `akosha_tools.py`.)

- [ ] **Step 3: Test that a failed Akosha call doesn't break the loop's result**

Confirm (by temporarily pointing at an invalid tool name, then reverting) that if the Akosha logging `agent()` call fails, the workflow still returns its `stopReason`/`iterations`/`auditLog` correctly — this is best-effort logging, not a loop-critical step, and should not turn a successful fix run into a reported failure.

- [ ] **Step 4: Commit**

```bash
git add .claude/workflows/ai-fix-loop.js
git commit -m "feat(ai-fix-loop): passive Akosha fix-outcome logging (write-only, per fix)"
```

---

### Task 8: Update CLAUDE.md's usage documentation

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:** N/A — documentation update.

- [ ] **Step 1: Replace the removed `--ai-fix` example**

In the "Most Common Commands" section, replace:
```
# Daily development (quality + tests + AI fixes) - RECOMMENDED
python -m crackerjack run --ai-fix --run-tests
```
with:
```
# Daily development (quality + tests) - RECOMMENDED
python -m crackerjack run --run-tests

# AI-assisted auto-fix (external loop, runs outside crackerjack itself)
# Invoke the ai-fix-loop workflow: Workflow({ scriptPath: '.claude/workflows/ai-fix-loop.js' })
```

- [ ] **Step 2: Remove or update the "AI Agent System" and "Skills Tracking Integration" sections**

These describe the 12-agent internal system and session-buddy skill tracking that no longer exist after the sibling plan's removal work. Replace with a short section pointing at the two design specs (`docs/superpowers/specs/2026-08-06-ai-fix-removal-external-loop-design.md`) for anyone looking for the old behavior's replacement.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for external ai-fix-loop workflow (replaces --ai-fix section)"
```

---

### Task 9: End-to-end acceptance test against this repo's real failures

**Files:**
- Create: `tests/integration/test_ai_fix_loop_acceptance.md` (a runbook, not a pytest file — this exercises live agent dispatch and git mutation, which isn't meaningfully unit-testable)

**Interfaces:** N/A — acceptance verification, the final gate for this plan.

- [ ] **Step 1: Write the runbook**

```markdown
# ai-fix-loop acceptance runbook

Run manually after any change to `.claude/workflows/ai-fix-loop.js`:

1. `git status --short` — confirm clean tree before starting.
2. `uv run python -m crackerjack run -v 2>&1 | tail -40` — record the current real hook results by eye.
3. `cat .crackerjack/audit/ai-fix-loop.jsonl 2>/dev/null | wc -l` — record the audit log line count (should be 0 on a clean state, or non-zero if resuming a prior interrupted run; if non-zero, decide whether to resume or archive-and-start-fresh before invoking).
4. Invoke the workflow: `Workflow({ scriptPath: '.claude/workflows/ai-fix-loop.js', args: { maxIterations: 5 } })`.
5. Confirm the returned `stopReason` matches expectations:
   - If step 2 showed a clean pass, expect `stopReason: 'clean'`, `iterations: 0`.
   - If step 2 showed issues, expect either `stopReason: 'clean'` with `iterations > 0` and a populated `auditLog`, or one of `'progress-stalled'`/`'iteration-cap'`/`'regressed'`/`'diff-too-large'` with a legible partial-progress `auditLog`.
   - Any of `'verify-error'`, `'snapshot-error'`, `'fix-agent-error'`, `'rollback-error'`, `'concurrent-change-detected'` indicates a bug, not a known limitation.
6. Run `uv run python -m crackerjack run -v 2>&1 | tail -40` again — confirm the real hook results improved or reached clean, matching what the workflow reported (don't trust the workflow's self-report alone).
7. `git log --oneline -10` — confirm no unexpected commits were created (the loop should only stash/pop, not commit, unless a future revision changes that).
8. `git status --short` — confirm no leftover dirty files.
9. `git stash list` — confirm no leftover `ai-fix-loop-iter-*` entries. If any remain, they indicate the loop crashed before the rollback/drop step (manual cleanup required).
10. `cat .crackerjack/audit/ai-fix-loop.jsonl` — confirm one JSON line per iteration ran (or zero if the loop never started). Verify the entries' `iteration`, `issuesBefore`, `changes`, `diffStat` fields are populated. This file is the durable record — keep it for postmortem review; delete it between runs only if you want a fresh start.
```

- [ ] **Step 2: Run it for real**

Execute the runbook against this repo's actual current state (post sibling-plan removal, so there should be real residual issues from the extraction/deletion work to fix, or a clean tree to confirm the zero-issue path).

- [ ] **Step 3: Record the result and fix any deviation before considering this plan complete**

If any step's actual outcome doesn't match its expected outcome, that's a bug in `.claude/workflows/ai-fix-loop.js`, not an acceptable known-limitation — fix it and re-run the full runbook from Step 1.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_ai_fix_loop_acceptance.md
git commit -m "test(ai-fix-loop): add end-to-end acceptance runbook, verified against real repo state"
```

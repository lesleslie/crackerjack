# AI-Fix External Loop + Akosha Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the external, agent-driven replacement for crackerjack's deleted `--ai-fix` capability: a `Workflow` script that runs `crackerjack run --json`, dispatches residual issues to an agent for fixing, re-verifies, and repeats until clean or capped — with git snapshot/rollback safety, a durable audit log, and a passive fix-outcome log to Akosha.

**Architecture:** A named `Workflow` script (`.claude/workflows/ai-fix-loop.js`, checked into the crackerjack repo for durability/review) drives the loop entirely through `agent()` calls with structured schemas — Workflow scripts have no direct Bash/filesystem access, so every external action (running crackerjack, git snapshot/rollback, editing files, querying Akosha) happens inside an `agent()` invocation, while the script's own JS control flow owns the loop invariants (iteration count, no-improvement detection, stop reasons) deterministically rather than relying on agent judgment for safety-critical decisions.

**Tech Stack:** Claude Code `Workflow` tool (JS, no TypeScript, no `Date.now()`/`Math.random()`), the `CrackerjackRunResult` JSON contract from the sibling plan (`docs/superpowers/plans/2026-08-06-ai-fix-removal-extraction.md`), Akosha MCP tools (exact tool names TBD via `ToolSearch` — see Task 7).

**Reference spec:** [docs/superpowers/specs/2026-08-06-ai-fix-removal-external-loop-design.md](../specs/2026-08-06-ai-fix-removal-external-loop-design.md), sections 5-6.

## Global Constraints

- No `Date.now()`/`Math.random()`/argless `new Date()` inside the Workflow script body — these throw. Wall-clock timeout is therefore enforced per-`agent()`-call via prompt instruction and the harness's own turn limits, not measured by the script itself (see Task 6).
- The script must not fabricate or predict `agent()` results — every loop decision reads a real returned value.
- No placeholders, TODOs, or dummy data (CLAUDE.md rule #3).
- Every git-mutating action (snapshot, rollback, fix) happens through an `agent()` call, since the Workflow script itself cannot run Bash directly.

## Precondition

This plan depends on `crackerjack/models/issues.py`'s `CrackerjackRunResult` (Task 3 of the sibling extraction plan) being merged, and `crackerjack run --json` emitting it. **Task 1 below verifies this precondition before any other work starts** — do not proceed past Task 1 if it fails.

## File Structure

**New files:**
- `.claude/workflows/ai-fix-loop.js` — the Workflow script itself.
- `tests/integration/test_ai_fix_loop_acceptance.md` — a manual acceptance-test runbook (this is agent-orchestration code, not a pytest-testable unit — see Task 9 for why).

**Modified files:**
- `CLAUDE.md` — replace the removed `--ai-fix` usage in "Most Common Commands" with the new workflow invocation.

---

### Task 1: Verify the `--json` contract precondition

**Files:** None modified — verification task.

**Interfaces:**
- Consumes: `crackerjack.models.issues.CrackerjackRunResult` (must exist and be wired into `crackerjack run --json`'s actual output).

- [ ] **Step 1: Confirm the module exists**

Run: `python -c "from crackerjack.models.issues import CrackerjackRunResult; print(CrackerjackRunResult.model_fields.keys())"`
Expected: prints a `dict_keys` view including `schema_version`, `success`, `issues`, `summary`. If this fails, the sibling extraction plan's Task 3 hasn't landed yet — stop and do not proceed with this plan.

- [ ] **Step 2: Confirm real CLI output matches**

Run: `python -m crackerjack run --json 2>&1 | tail -1 | python -m json.tool`
Expected: valid JSON with a `"schema_version"` field. Record the exact top-level key set — this is what Task 3's `agent()` prompt will tell the verify-agent to expect.

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

const MAX_ITERATIONS = (args && args.maxIterations) || 10

const RUN_RESULT_SCHEMA = {
  type: 'object',
  properties: {
    cleanExit: { type: 'boolean' },
    issueCount: { type: 'number' },
    issuesJson: { type: 'string' },
    schemaVersion: { type: 'string' },
  },
  required: ['cleanExit', 'issueCount', 'issuesJson', 'schemaVersion'],
}

let previousIssueCount = Number.POSITIVE_INFINITY
const auditLog = []

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
- Consumes: `RUN_RESULT_SCHEMA` from Task 2.
- Produces: `verify` object per iteration, with `cleanExit`, `issueCount`, `issuesJson`, `schemaVersion` — consumed by Task 6's stop-condition checks and Task 5's fix-dispatch prompt.

- [ ] **Step 1: Replace the `// Task 3 fills in the Verify phase here.` comment with the real call**

```js
  phase('Verify')
  const verify = await agent(
    `Run this exact command in the crackerjack repo: \`python -m crackerjack run --json\`. ` +
    `The last line of stdout is a JSON object matching this shape: {schema_version, success, issues: [...], summary: {...}}. ` +
    `Parse it. Return cleanExit=true only if the "issues" array is empty, issueCount=the length of the "issues" array, ` +
    `issuesJson=the raw JSON string of the full parsed object (not re-serialized, the actual text), and schemaVersion=the "schema_version" field value. ` +
    `If the command fails to run or produces no parseable JSON, return cleanExit=false, issueCount=-1, issuesJson="", schemaVersion="".`,
    { schema: RUN_RESULT_SCHEMA, label: `verify-iter-${iteration}`, phase: 'Verify' }
  )
  if (!verify || verify.issueCount === -1) {
    log(`Verify agent failed or crackerjack did not produce parseable JSON on iteration ${iteration} — aborting.`)
    return { stopReason: 'fixer-error', iterations: iteration - 1, auditLog }
  }
  if (verify.cleanExit) {
    log(`Clean after ${iteration - 1} fix iteration(s).`)
    return { stopReason: 'clean', iterations: iteration - 1, auditLog }
  }
```

- [ ] **Step 2: Test against this repo's real current state**

Run the workflow with `maxIterations: 1` against this repo as-is. Confirm the `verify` step correctly reports whether the repo is currently clean or not, matching what `python -m crackerjack run --json` actually shows when run directly.

- [ ] **Step 3: Commit**

```bash
git add .claude/workflows/ai-fix-loop.js
git commit -m "feat(ai-fix-loop): implement Verify phase (run crackerjack --json, parse result)"
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
  const snapshot = await agent(
    `Run \`git stash push -u -m "ai-fix-loop-iter-${iteration}"\` in the repo, but only if there are uncommitted changes to stash ` +
    `(check with \`git status --short\` first — if the tree is already clean, do NOT run stash, since it would stash nothing and confuse rollback). ` +
    `Then run \`git stash list\` and return the top entry's reference (e.g. "stash@{0}") as stashRef. ` +
    `If nothing was stashed because the tree was already clean, return stashRef="" and stashed=false. Otherwise return stashed=true.`,
    {
      schema: { type: 'object', properties: { stashRef: { type: 'string' }, stashed: { type: 'boolean' } }, required: ['stashRef', 'stashed'] },
      label: `snapshot-iter-${iteration}`,
      phase: 'Snapshot',
    }
  )
  if (!snapshot) {
    log(`Snapshot agent failed on iteration ${iteration} — aborting rather than risk an unsnapshotted fix attempt.`)
    return { stopReason: 'fixer-error', iterations: iteration - 1, auditLog }
  }
```

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
- Consumes: `verify.issuesJson` from Task 3.
- Produces: `fix` object per iteration with `changes: Array<{file: string, description: string}>` — appended to `auditLog` in Task 6.

- [ ] **Step 1: Replace the `// Task 5 fills in the Fix phase here.` comment**

```js
  phase('Fix')
  const fix = await agent(
    `You are fixing quality issues in the crackerjack repo reported by \`crackerjack run --json\`. Here is the current issue list as JSON: ${verify.issuesJson}\n\n` +
    `Fix as many of these issues as you directly can by editing the affected files. Prefer minimal, targeted edits — do not refactor unrelated code. ` +
    `Do not run \`crackerjack run\` yourself; the loop driving you will re-verify after you finish. ` +
    `When done (or if you get stuck and cannot fix something), return a list of changes you made: each with the file path and a one-sentence description of the fix. ` +
    `If you made no changes at all, return an empty list.`,
    {
      schema: {
        type: 'object',
        properties: {
          changes: {
            type: 'array',
            items: { type: 'object', properties: { file: { type: 'string' }, description: { type: 'string' } }, required: ['file', 'description'] },
          },
        },
        required: ['changes'],
      },
      label: `fix-iter-${iteration}`,
      phase: 'Fix',
    }
  )
  if (!fix) {
    log(`Fix agent failed on iteration ${iteration} — aborting.`)
    return { stopReason: 'fixer-error', iterations: iteration - 1, auditLog }
  }
```

- [ ] **Step 2: Test against a real, small, known issue**

Deliberately introduce one trivial, real crackerjack-detectable issue (e.g., an unused import) in a scratch branch, run the workflow with `maxIterations: 1`, and confirm the `fix` step's returned `changes` list correctly names the file and describes the fix that was actually made (verify with `git diff`, not just the agent's self-report).

- [ ] **Step 3: Commit**

```bash
git add .claude/workflows/ai-fix-loop.js
git commit -m "feat(ai-fix-loop): implement Fix phase (dispatch residual issues to an agent)"
```

---

### Task 6: Implement stop-condition checks, rollback, and the audit log

**Files:**
- Modify: `.claude/workflows/ai-fix-loop.js`

**Interfaces:**
- Consumes: `verify`, `snapshot`, `fix` from Tasks 3-5.
- Produces: the loop's final return value — `{ stopReason: 'clean' | 'no-improvement' | 'iteration-cap' | 'fixer-error', iterations: number, auditLog: Array }`.

- [ ] **Step 1: Add the no-improvement / rollback check, placed after Verify (Task 3) and before Snapshot (Task 4) each iteration**

```js
  if (verify.issueCount >= previousIssueCount) {
    log(`No improvement (was ${previousIssueCount}, now ${verify.issueCount}).`)
    if (auditLog.length > 0 && auditLog[auditLog.length - 1].stashRef) {
      const lastStash = auditLog[auditLog.length - 1].stashRef
      await agent(
        `Run \`git stash pop ${lastStash}\` in the repo to undo the last fix attempt, since it made no improvement. ` +
        `If that stash ref no longer exists or pop fails, run \`git status --short\` and report the current state instead of guessing further.`,
        { label: `rollback-iter-${iteration}`, phase: 'Snapshot' }
      )
    }
    return { stopReason: 'no-improvement', iterations: iteration - 1, auditLog }
  }
  previousIssueCount = verify.issueCount
```

- [ ] **Step 2: Append to the audit log after the Fix phase completes**

```js
  auditLog.push({
    iteration,
    issuesBefore: verify.issueCount,
    stashRef: snapshot.stashed ? snapshot.stashRef : null,
    changes: fix.changes,
  })
```

- [ ] **Step 3: Assemble the full loop body in order**

Confirm the final iteration body order is: Verify (Task 3) → clean-exit check (Task 3) → no-improvement/rollback check (this task, Step 1) → Snapshot (Task 4) → Fix (Task 5) → audit-log append (this task, Step 2). Re-read the full file after assembly to confirm no phase was duplicated or dropped during the incremental edits across Tasks 3-6.

- [ ] **Step 4: Test the no-improvement path**

Deliberately construct a scenario where the Fix agent's changes don't reduce the issue count (e.g., point it at an issue type it can't actually fix) and confirm the loop correctly detects no improvement, triggers rollback, and returns `stopReason: 'no-improvement'` rather than looping further.

- [ ] **Step 5: Test the iteration-cap path**

Run with `maxIterations: 2` against a repo state with more than 2 genuinely fixable issues spread across iterations, and confirm it stops at the cap with `stopReason: 'iteration-cap'` and a populated `auditLog` covering both iterations.

- [ ] **Step 6: Note the timeout limitation explicitly**

This implementation has no independent wall-clock timeout — `Date.now()` is unavailable in Workflow scripts. Each `agent()` call is bounded only by the harness's own per-agent turn/time limits, not by this script. If a hard wall-clock budget is needed later, it must be enforced by whatever invokes this workflow (e.g., a cron wrapper with the `timeout` command), not by the script itself. Document this as a known constraint in the script's header comment.

- [ ] **Step 7: Commit**

```bash
git add .claude/workflows/ai-fix-loop.js
git commit -m "feat(ai-fix-loop): stop conditions, rollback-on-no-improvement, audit log"
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
  // After the for-loop, before the final `return`:
  for (const entry of auditLog) {
    for (const change of entry.changes) {
      await agent(
        `Log this fix outcome to Akosha for future pattern learning. First call the embedding-generation tool found via ToolSearch on the text: ` +
        `"Fixed in ${change.file}: ${change.description}". Then call the memory-storage tool with that embedding, the same text, and metadata ` +
        `{repo: "crackerjack", file: "${change.file}", outcome: "fixed", iteration: ${entry.iteration}}. ` +
        `This is write-only — do not query Akosha for prior fixes, just log this one.`,
        { label: `akosha-log-${entry.iteration}-${change.file}`, phase: 'Fix' }
      )
    }
  }
```

(Use the exact tool names confirmed in Step 1 in the prompt text, replacing the generic "embedding-generation tool"/"memory-storage tool" phrasing with the real tool names.)

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
2. `python -m crackerjack run --json | tail -1 | python -m json.tool` — record the current real issue count.
3. Invoke the workflow: `Workflow({ scriptPath: '.claude/workflows/ai-fix-loop.js', args: { maxIterations: 5 } })`.
4. Confirm the returned `stopReason` matches expectations:
   - If step 2 showed 0 issues, expect `stopReason: 'clean'`, `iterations: 0`.
   - If step 2 showed issues, expect either `stopReason: 'clean'` with `iterations > 0` and a populated `auditLog`, or `stopReason: 'iteration-cap'`/`'no-improvement'` with a legible partial-progress `auditLog`.
5. Run `python -m crackerjack run --json | tail -1 | python -m json.tool` again — confirm the real issue count decreased or reached zero, matching what the workflow reported (don't trust the workflow's self-report alone).
6. `git log --oneline -10` — confirm no unexpected commits were created (the loop should only stash/pop, not commit, unless a future revision changes that).
7. `git status --short` — confirm no leftover stash entries (`git stash list` should be empty or only contain pre-existing entries from before this run).
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

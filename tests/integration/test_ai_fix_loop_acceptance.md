# ai-fix-loop Acceptance Runbook

> **Status:** Active manual runbook. Not a pytest test.
> **Owner:** Workflow script changes (`.claude/workflows/ai-fix-loop.js`) — run after every change.
> **Plan:** `docs/superpowers/plans/2026-08-06-ai-fix-external-loop.md` (Task 9).

## What This Is

This is a **manual** acceptance test. The `ai-fix-loop` workflow exercises
live agent dispatch (multiple `agent()` calls per iteration), git
mutation (`stash push`/`pop`/`drop`), and best-effort Akosha logging —
none of which are meaningfully unit-testable in pytest. The script
itself has parser-level smoke tests (`node --check`, structural
regex assertions) for the inner loops; this runbook covers the
end-to-end behavior those tests can't reach.

Run it after:

- Any edit to `.claude/workflows/ai-fix-loop.js`
- Any change to the Akosha MCP tool contract (`store_memory`,
  `generate_embedding`)
- Any change to crackerjack's `-v` output format that the Verify phase
  relies on

## Prerequisites

| Prereq | Why |
|---|---|
| Clean working tree (`git status --short` is empty) | The loop requires a clean tree at start; concurrent edits trigger `concurrent-change-detected` |
| `uv` installed and project deps synced (`uv sync`) | Needed for `uv run crackerjack run -v` |
| Mahavishnu pool available (or equivalent Workflow-tool host) | The loop is invoked via `Workflow({ scriptPath: ... })` |
| Akosha MCP server reachable | Step 9's Akosha logging check requires the MCP server up (otherwise it's a `akosha-best-effort` failure, which the loop tolerates but this runbook flags) |

## Steps

1. **`git status --short`** — confirm clean tree before starting.
2. **`uv run python -m crackerjack run -v 2>&1 | tail -40`** — record
   the current real hook results by eye. This is the ground truth
   the loop will be measured against.
3. **`cat .crackerjack/audit/ai-fix-loop.jsonl 2>/dev/null | wc -l`** —
   record the audit log line count. Should be `0` on a fresh state;
   non-zero means a prior interrupted run left state. Decide whether
   to resume (re-invoke the workflow and trust the in-memory
   `auditLog` push) or archive-and-start-fresh (move the file aside)
   before proceeding.
4. **Invoke the workflow**:
   ```
   Workflow({ scriptPath: '.claude/workflows/ai-fix-loop.js', args: { maxIterations: 5 } })
   ```
   Capture the returned object — `{ stopReason, iterations, auditLog, ... }`.
5. **Confirm `stopReason` matches expectations**:
   - If step 2 showed a clean pass, expect `stopReason: 'clean'`,
     `iterations: 0`.
   - If step 2 showed issues but the count was ≤ `INITIAL_ISSUE_GUARD`
     (default 200), expect either:
     - `stopReason: 'clean'` with `iterations > 0` and a populated
       `auditLog`, OR
     - `stopReason` ∈ {`'progress-stalled'`, `'iteration-cap'`,
       `'regressed'`, `'diff-too-large'`} with a legible
       partial-progress `auditLog`.
   - If step 2 showed issues with count > `INITIAL_ISSUE_GUARD`
     (e.g., this repo's ~1014 ruff-check baseline), expect
     `stopReason: 'initial-issue-count-too-high'`, `iterations: 0`,
     and the documented message about triaging first.
   - Any of `'verify-error'`, `'snapshot-error'`,
     `'fix-agent-error'`, `'rollback-error'`,
     `'concurrent-change-detected'` indicates a bug, not a known
     limitation.
6. **`uv run python -m crackerjack run -v 2>&1 | tail -40` again** —
   confirm the real hook results improved or reached clean, matching
   what the workflow reported. Don't trust the workflow's
   self-report alone.
7. **`git log --oneline -10`** — confirm no unexpected commits were
   created. The loop only stash/pop, never commit. A new commit here
   is a regression.
8. **`git status --short`** — confirm no leftover dirty files. Any
   unstaged modifications mean the loop's stash/pop didn't fully
   restore state, which is a rollback bug.
9. **`git stash list`** — confirm no leftover `ai-fix-loop-iter-*`
   entries. If any remain, the loop crashed mid-iteration before
   `git stash drop` ran. Manual cleanup:
   ```
   git stash drop "stash@{<N>}"
   ```
   where `<N>` is the leftover entry's positional index.
10. **`cat .crackerjack/audit/ai-fix-loop.jsonl`** — confirm one JSON
    line per completed iteration (or zero if the loop never started,
    e.g., `initial-issue-count-too-high` aborted before any iter
    ran). Each line's `iteration`, `issuesBefore`, `changes`,
    `diffStat` fields should be populated. This file is the durable
    record — keep it for postmortem review; delete it between runs
    only if you want a fresh start.

## Expected Outcome for This Repo (2026-08-10 baseline)

This repo currently has ~1014 baseline issues across multiple hooks
(ruff-check=999, check-local-links=8, codespell=7, pip-audit=2,
mdformat=1, skill-coverage=2 — exact counts in
`docs/superpowers/plans/2026-08-10-ai-fix-loop-task-1-kickoff.md`).
That's well above `INITIAL_ISSUE_GUARD=200`, so:

| Step | Expected result |
|---|---|
| 2 | Crackerjack prints `Fast Hook Results` with multiple FAILED entries; total ~1014 |
| 3 | Audit log line count is `0` (fresh state) |
| 4 | Workflow invoked, returns quickly (single Verify iter + abort) |
| 5 | `stopReason: 'initial-issue-count-too-high'`, `iterations: 0`, `initialIssueCount` populated, `guard: 200`, `message` populated. **`auditLog` is empty** (no iteration completed before the guard fired) |
| 6 | Identical to step 2 — the loop didn't touch the working tree, so re-running `crackerjack run -v` shows the same baseline |
| 7 | No new commits |
| 8 | Same 12 pre-existing dirty files as before invocation (no new dirt) |
| 9 | Empty stash list — no `git stash push` runs on `initial-issue-count-too-high` (it aborts before Snapshot) |
| 10 | Empty file — no JSONL lines written (audit log only persists per completed iter, and zero iters completed) |

If you want to exercise the actual fix loop end-to-end, you must
either (a) temporarily lower `INITIAL_ISSUE_GUARD` via
`args.initialIssueGuard` to a number above your baseline, or
(b) triage the largest-bucket hook (currently `ruff-check=999`) down
below 200 first.

## Failure-Mode Triage

| Symptom | Likely cause | First action |
|---|---|---|
| `stopReason: 'verify-error'` repeatedly | Verify agent's response is missing/malformed; or upstream `crackerjack run -v` output format changed | Read the latest `verify-iter-N` agent output by hand; confirm `cleanExit:`, `issueCount:`, `issuesSummary:` lines present |
| `stopReason: 'snapshot-error'` after first iter | Snapshot agent's stash step failed; usually permissions or `.git` corruption | `git stash list` and `git status`; verify the repo is a real git repo, not a worktree-shallow clone |
| `stopReason: 'fix-agent-error'` | Fix agent returned no `CHANGES:` block | Inspect the `fix-iter-N` output; the agent may have crashed mid-edit or refused to make changes |
| `stopReason: 'rollback-error'` with `rollbackReason: 'sha-mismatch'` | Stash list message-collision (very rare) or git corruption | `git stash list`; manually resolve the rollback with `git stash pop "stash@{N}"` after verifying the SHA matches the `auditLog[N].stashSha` |
| `stopReason: 'rollback-error'` with `rollbackReason: 'pop-failed'` | Stash pop hit a merge conflict | Manual `git status` + `git stash pop`; resolve conflicts, `git stash drop` |
| `stopReason: 'diff-too-large'` | Fix agent exceeded 5-file/100-line cap, or touched `tests/`/`docs/`/`*.toml`/`*.yml`/`*.txt`/`pyproject.toml`/`setup.py`/`requirements*.txt`/`Dockerfile` | Read the `diffSanity` block in the last `auditLog` entry; the fix was rolled back automatically |
| `stopReason: 'audit-log-error'` | `.crackerjack/audit/` is not writable, or disk is full | `ls -la .crackerjack/`; `df -h .`; resolve the disk/permissions issue, restore the partial audit log from in-memory `auditLog` in the workflow return value |
| `stopReason: 'concurrent-change-detected'` | Working tree was dirty with non-fix files at Snapshot time | Resolve the user's pending edits/pulls, re-invoke |
| Loop never starts (errors before step 4) | Workflow tool refused to load the script | `node --check .claude/workflows/ai-fix-loop.js`; check for syntax errors or forbidden constructs (`Date.now`, `Math.random`, argless `new Date()`) |

## Acceptance Sign-Off

If all 10 steps' actual outcomes match the expected outcomes in the
table above (or the alternative outcomes listed in step 5's
branching), the loop is verified against this repo's real state. Mark
the run as accepted in your work log. If any step's actual outcome
diverges, file a bug against `.claude/workflows/ai-fix-loop.js` and
re-run from step 1 after the fix.
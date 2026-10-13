---
status: active
role: implementation
kind: decision
date: 2026-10-12
last_reviewed: 2026-10-12
topic: crackerjack-infrastructure
related:
  - ../../../templates/GITIGNORE_BODAI.md
  - 2026-10-12-canonical-claude-gitignore-policy.md
---

# Auto-sync gitignore on pre-publish gate failure

## Context

The pre-publish gate `_validate_gitignore_conformance` in
`crackerjack/managers/publish_manager.py:689` is detection-only:
drift aborts the publish with a message telling the operator to
manually run `crackerjack gitignore sync` and re-run. When the
canonical template is updated fleet-wide (e.g. the 9a47c9dc commit
that promoted `.claude/` policy), every repo in the fleet hits this
gate until each operator manually syncs.

## Decision

The gate now does **detect → attempt auto-repair → re-verify →
fail if still broken** instead of pure detection:

- snippet present, no missing patterns → PASS (no subprocess)
- drift detected → auto-sync attempt via subprocess
  - sync succeeds, re-check passes → PASS, continue
  - sync subprocess fails (non-zero exit, timeout, or stderr error) → FAIL, abort
  - sync succeeds but patterns still missing → FAIL, abort (likely a stale backup or template bug)
- non-Bodai fleet member → PASS silently (unchanged)

Pre-flight guard: refuses auto-sync if `.gitignore` has uncommitted
working-tree edits (sync would clobber; operator WIP would be lost
though sync also writes a `.gitignore.bak.<timestamp>` backup).

## Implementation

- `crackerjack/managers/publish_manager.py:644-820` — `_validate_prerequisites`,
  `_validate_gitignore_conformance`, new `_attempt_gitignore_sync`
- `tests/managers/test_publish_gitignore_autosync.py` — 10 tests
  covering all contract branches (PASS without sync, PASS with sync,
  sync subprocess failure, sync timeout, drift persists after sync,
  dirty .gitignore refuses sync, clean .gitignore proceeds, correct
  subprocess args, non-fleet member pass, snippet-only drift)

## Behavior contract (recap)

| Pre-state | Sync result | Post-state | Gate verdict |
|---|---|---|---|
| Conforming | n/a | unchanged | PASS |
| Snippet missing | sync OK | Conforming | PASS, continue |
| Snippet + patterns missing | sync OK | Conforming | PASS, continue |
| Drift | sync subprocess fails | unchanged | FAIL, abort |
| Drift | sync OK but drift persists | unchanged or partial | FAIL, abort |
| Drift + dirty `.gitignore` | refused | unchanged | FAIL, abort |
| Not a Bodai fleet member | n/a | n/a | PASS silently |

## Edge cases NOT auto-fixed

1. **Tracked files now matched by new ignore rules** — gitignore
   changes don't un-track existing entries. mahavishnu's
   `.claude/settings.local.json` is the canonical example; operator
   must `git rm --cached` separately. Gate passes after sync but
   the underlying state is still wrong.
2. **Stale `.gitignore.bak.<timestamp>` blocking sync** — sync
   detects already-applied state by matching the `>>>` / `<<<`
   markers; a stale backup could confuse detection.
3. **Tracked-but-ignored files without `git rm --cached`** — same as
   #1.

## What we deliberately don't propose

- **Auto-commit the sync'd `.gitignore`** — surprising the operator
  with a `chore:` commit they didn't write breaks `git blame` hygiene.
  Let operator decide whether to commit, amend-into-bump, or stash.
- **Auto-push** — same reasoning.
- **Auto-fix tracked-but-should-be-untracked files** — `git rm
  --cached` is a destructive operation that requires human judgment.

## Verification

- `pytest tests/managers/test_publish_gitignore_autosync.py -v` → 10 passed
- `pytest crackerjack/tests/checks/test_gitignore_conformance.py` → 12 passed (existing tests still green)
- `pytest tests/unit/managers/test_publish_manager_extended.py tests/test_publish_manager_coverage.py tests/test_publish_workflow.py` → 115 passed (existing publish tests still green)
- `ruff check` and `ty check` clean on modified files

## Related

- Gate: `crackerjack/managers/publish_manager.py:644-820`
- Conformance check: `crackerjack/checks/gitignore_conformance.py`
- Tests: `tests/managers/test_publish_gitignore_autosync.py`
- Decision: `2026-10-12-canonical-claude-gitignore-policy.md` (promoted
  the canonical snippet that this gate now auto-syncs)
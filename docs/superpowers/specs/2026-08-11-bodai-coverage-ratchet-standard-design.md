# Coverage-Ratchet Standardization — Design

**Status:** design
**Date:** 2026-08-11
**Owner:** les
**Policy repo:** crackerjack (the enforcer)
**Applies to:** all 7 Bodai components (mcp-common, oneiric, fastblocks, mahavishnu, crackerjack, session-buddy, akosha, dhara)

## Goal

Make coverage regression visible across the Bodai ecosystem by setting a single floor (the ratchet) per repo and enforcing it on every `crackerjack` run. The ratchet ticks up only when coverage rises; never down (an explicit `lower` command with `--reason` is the only way to drop it).

## Non-Goals

- Forcing a fixed floor (e.g. 80% everywhere). Each repo's initial floor is its current coverage.
- Changing the existing `CoverageRatchetService` math (MILESTONES, TOLERANCE_MARGIN, history schema).
- Replacing `pyproject.toml` `--cov-fail-under` with a per-repo tool config. The two coexist by intention.
- Auto-migrating CI on every Bodai repo in one PR. Migration is per-repo, lowest coverage first, direct commits to main.

## Background

The Bodai ecosystem has 7 components. Today:

| Repo | `.coverage-ratchet.json` | Current baseline | `pyproject.toml` `--cov-fail-under` |
|---|---|---|---|
| mcp-common | tracked | 99.49% | 80 |
| oneiric | tracked | 79.41% | 80 |
| fastblocks | tracked | 49.13% | 80 |
| mahavishnu | absent | — | 80 |
| crackerjack | absent | — | 80 |
| session-buddy | absent | — | 80 |
| akosha | absent | — | 80 |
| dhara | absent | — | 80 |

The Crackerjack service `crackerjack/crackerjack/services/coverage_ratchet.py` already implements the ratchet logic. The test stage partly wires it. The CLI surface is incomplete. Adoption is inconsistent.

## Architecture

```
crackerjack/docs/                              ← policy lives here
├── plans/2026-08-11-bodai-coverage-ratchet-standard.md
└── specs/2026-08-11-bodai-coverage-ratchet-standard-design.md (this file)

crackerjack/crackerjack/                       ← policy is enforced here
├── services/coverage_ratchet.py                (existing — extend)
├── managers/test_manager.py                    (existing — already invokes)
├── core/phase_coordinator.py                   (existing — wires test stage)
└── cli/coverage_ratchet_cli.py                 (new — `init`, `status`, `lower`)

Per-repo state (all 7 Bodai repos):
├── .coverage-ratchet.json                       (SOURCE OF TRUTH)
├── pyproject.toml                               (--cov-fail-under is a mirror)
└── Crackerjack test-stage invocation           (ratchet always-on)
```

**Invariants:**

1. `.coverage-ratchet.json` is the only source of truth for the floor.
2. `pyproject.toml` `--cov-fail-under` is a mirror, kept in sync by the Crackerjack test stage.
3. No 80% default. Initial floor = current coverage at `init` time.
4. The ratchet ticks up only when coverage rises. It never moves down automatically.
5. Direct commits to main per `bodai-pre-1.0-merge-policy.md`. No PRs.

## Data flow

### Phase 1: Initialize (one-time per repo)

```
$ crackerjack coverage-ratchet init
  → reads current coverage from .coverage / coverage.json
  → creates .coverage-ratchet.json with baseline = current coverage
  → mirrors value to pyproject.toml: --cov-fail-under = <current>
  → commits both files
```

The init command is idempotent. It refuses to overwrite an existing ratchet unless `--reinit` is passed.

### Phase 2: Run (every `crackerjack` invocation, in the test stage)

```
crackerjack test stage:
  1. Run pytest with coverage
  2. Read coverage.json
  3. Compare against .coverage-ratchet.json current_minimum
       ├─ within TOLERANCE_MARGIN (2.0%)    → pass, possibly bump up
       ├─ above current_minimum             → bump ratchet up, mirror to pyproject
       └─ below current_minimum - TOLERANCE → FAIL with actionable error
  4. Write updated .coverage-ratchet.json (if bumped)
  5. Mirror the bumped value to pyproject.toml (if bumped)
```

### Phase 3: Recover (when CI fails)

If the test stage exits non-zero due to a coverage drop, the error message is:

```
📉 Coverage regression detected
   Current: 46.50%
   Ratchet: 49.13% (TOLERANCE_MARGIN: 2.0%)
   Drop: 2.63% (exceeds tolerance)

To recover:
  • Add tests to bring coverage back above 49.13%
  • OR acknowledge the regression explicitly:
      crackerjack coverage-ratchet lower --to 46.50 --reason "<text>"
```

The author chooses:
- **a. Add tests** → push → CI runs again → passes (ratchet stays at 49.13).
- **b. Run `lower`** → records reason in history, commits the ratchet update.

The `lower` command is logged in history with reason and timestamp. The history is visible via `crackerjack coverage-ratchet status`.

## Components

### Component 1: `CoverageRatchetService` (existing + extend)

**Path:** `crackerjack/crackerjack/services/coverage_ratchet.py`

**Existing methods (production-ready):**
- `initialize_baseline(initial_coverage)` — creates the ratchet file
- `get_ratchet_data()` — round-trip JSON
- `record_coverage(coverage)` — bumps up only
- `check_drop(coverage)` — tolerance math, drop detection

**Methods to add:**
- `lower_baseline(new_coverage, reason)` — explicit operator ack, requires `--reason`
- `mirror_to_pyproject(coverage)` — writes `--cov-fail-under` to pyproject.toml
- `report_status()` — human-readable summary for `status` CLI command

**Boundary:** pure logic + json + one pyproject.toml edit. No subprocess, no network.

### Component 2: Test-stage integration (existing + extend)

**Path:** `crackerjack/crackerjack/managers/test_manager.py`

**Existing behavior:** partly wires the ratchet.

**Behavior to add:**
- After pytest exits, call `CoverageRatchetService.check_drop()`.
- On drop (outside tolerance): exit 1 with the message in Phase 3 above.
- On bump: write updated ratchet + mirror to pyproject.
- On missing ratchet file: exit 1 with init hint.

### Component 3: CLI commands (new)

**Path:** `crackerjack/crackerjack/cli/coverage_ratchet_cli.py`

**Commands:**
- `init` — first-time setup. Reads current coverage, creates ratchet, mirrors pyproject.
- `status` — show ratchet state + history + next milestone.
- `lower --to <N> --reason "<text>"` — explicit operator ack of regression.
- `migrate` (temporary, removed in Phase C) — auto-invoke `init` across all 7 Bodai repos via Mahavishnu.

**Boundary:** thin wrappers around the service. No business logic.

## Error handling

| Failure mode | Exit code | Output | Recovery |
|---|---|---|---|
| Coverage drop > TOLERANCE_MARGIN | 1 | "Coverage regression detected" with current/ratchet/drop | Add tests OR `lower --to <N> --reason "<text>"` |
| `.coverage-ratchet.json` missing | 1 | "Run `crackerjack coverage-ratchet init` to initialize" | Run `init` |
| `pyproject.toml` mirror drift | 0 (auto-fix) | "Pyproject.toml mirror out of sync, auto-fixing" | None — ratchet is canonical |
| `init` on existing ratchet (no `--reinit`) | 1 | "Ratchet already exists at <baseline>%" | Use `--reinit` to overwrite (rare) |
| `lower` without `--reason` | 1 | "Reason required" | Re-run with `--reason` |

**Specific design choices:**
- **Hard fail on drop**: matches the user's choice. No soft warnings.
- **Tolerance is built-in**: `TOLERANCE_MARGIN = 2.0` already in the service. No new code.
- **Auto-fix for mirror drift**: the ratchet is the source of truth. pyproject.toml sync is automatic. No operator-friendly "fix manually" path.
- **`lower` is explicit and recorded**: requires `--reason`, logged in history, visible in `status`.

## Testing strategy

### Layer 1: Unit tests (no I/O)

**Path:** `crackerjack/tests/services/test_coverage_ratchet.py`

Targets:
- `initialize_baseline`: creates file with correct schema
- `record_coverage`: bumps up only, never down (without explicit `lower`)
- `check_drop`: tolerance math, drop detection, status string
- `lower_baseline`: requires `--reason`, recorded in history
- `mirror_to_pyproject`: writes `--cov-fail-under` to pyproject.toml (test with tmp pyproject)
- `get_ratchet_data`: round-trip JSON

### Layer 2: Integration tests (service ↔ test stage ↔ pyproject)

**Path:** `crackerjack/tests/managers/test_test_manager_ratchet.py`

Targets:
- Test stage calls `CoverageRatchetService` after pytest
- Exit code 1 on drop, exit code 0 on pass
- pyproject.toml mirror is updated on bump
- Missing ratchet file → exit code 1 with init hint

Uses fixtures: `tmp_path`, fake pytest subprocess, fake coverage.json.

### Layer 3: End-to-end (one per Bodai repo)

**Path:** `crackerjack/tests/e2e/test_bodai_ratchet_adoption.py`

Targets (one test per Bodai repo):
- Clone-repo-style fixture (use a tmp copy of mcp-common, etc.)
- Run `crackerjack coverage-ratchet init`
- Verify `.coverage-ratchet.json` created with current coverage
- Verify pyproject.toml mirror updated
- Run a fake pytest that produces coverage
- Verify ratchet ticks up on bump, fails on drop

**Test philosophy:**
- Pure logic in unit tests.
- Boundaries in integration tests.
- Real-world scenarios in e2e tests.

## Migration plan

Per-repo migration, lowest coverage first. Direct commits to main, no PRs.

### Phase A: Crackerjack infrastructure (1 repo, 1 commit)

**Repo:** crackerjack
**Scope:** Add the missing CLI commands (`init`, `status`, `lower`, `migrate`) + test-stage integration + 3 test layers.
**Commit:** `feat(ratchet): add CLI + test-stage integration`
**Files:** ~6 production + 3 test
**Result:** `CoverageRatchetService` is fully wired into the test stage. CLI surface is complete.

### Phase B: Adoption wave (5 repos, 5 commits)

**Order:** lowest coverage first → highest coverage first.

| Order | Repo | Current state | Action |
|---|---|---|---|
| 1 | fastblocks | ratchet at 49.13% | Mirror pyproject to 49.13 (no init needed) |
| 2 | mahavishnu | no ratchet | Run `init` at current coverage, mirror pyproject |
| 3 | crackerjack | no ratchet | Run `init` at current coverage, mirror pyproject |
| 4 | session-buddy | no ratchet | Run `init` at current coverage, mirror pyproject |
| 5 | akosha | no ratchet | Run `init` at current coverage, mirror pyproject |
| 6 | dhara | no ratchet | Run `init` at current coverage, mirror pyproject |
| 7 | mcp-common | ratchet at 99.49% | No change (already aligned) |
| 8 | oneiric | ratchet at 79.41% | No change (already aligned) |

**Migration invariants:**
- Each repo's migration is one commit on its own `main`.
- Each commit lands only if the ratchet math is satisfied post-init.
- Direct commits to main, no PRs.
- Crackerjack test stage must pass on each repo before the commit lands.

### Phase C: Cleanup (1 commit, crackerjack)

**Repo:** crackerjack
**Scope:** Remove the temporary `migrate` CLI command from Phase A. Keep `init`, `status`, `lower`.
**Commit:** `chore(ratchet): remove temporary migrate CLI`

## Open questions

None. All design decisions are confirmed.

## Related docs

- `docs/superpowers/plans/2026-08-11-bodai-coverage-ratchet-standard.md` (the implementation plan, written by writing-plans)
- `crackerjack/crackerjack/services/coverage_ratchet.py` (the service)
- `crackerjack/docs/superpowers/specs/2026-06-29-ty-ratchet-cleanup-design.md` (related ty-ratchet spec, separate concern)
- `.claude/decisions/bodai-pre-1.0-merge-policy.md` (memory: direct-to-main policy)

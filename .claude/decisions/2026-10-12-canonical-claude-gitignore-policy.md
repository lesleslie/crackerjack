---
status: active
role: implementation
kind: decision
date: 2026-10-12
last_reviewed: 2026-10-12
topic: crackerjack-infrastructure
related:
  - ../../../templates/GITIGNORE_BODAI.md
---

# Canonical `.claude/` policy in `templates/GITIGNORE_BODAI.md`

## Context

Fleet audit (2026-10-12, see companion reports) found three divergent
`.claude/` gitignore styles across the 6+ Bodai repos:

- **oneiric, mcp-common**: blanket `.claude/` + subdir allowlists
- **akosha, session-buddy, crackerjack**: `.claude/*` (single-star) + subdir allowlists
- **mahavishnu**: no blanket; targeted ignores for known runtime artifacts only

Symptoms of the divergence:
- New tracked subdirs under `.claude/` required a gitignore edit in
  oneiric/mcp-common/mahavishnu; akosha/session-buddy/crackerjack worked
  but only because the allowlist happened to be comprehensive
- `git add -f` was needed for first-time adds under allowlisted subdirs
  (local exclude-cache behavior; documented as a UX issue)
- mahavishnu tracks `.claude/settings.local.json` (per-machine config)
  because its gitignore never excluded it
- mcp-common + oneiric have `.claude/decisions/README.md` on disk but
  not tracked

## Decision

Promote the canonical `.claude/` policy into
`templates/GITIGNORE_BODAI.md` so `crackerjack gitignore sync`
distributes it fleet-wide. The new block (between the `>>>` and `<<<`
markers, after the existing `.superpowers/` rule) follows the
**reference design** (`.claude/*` + explicit allowlists for the eight
canonical durable subdirs, plus first-class rules for known runtime
artifacts):

```gitignore
.claude/*
!.claude/CLAUDE.md
!.claude/settings.json
!.claude/decisions/        !.claude/decisions/**
!.claude/agents/           !.claude/agents/**
!.claude/commands/         !.claude/commands/**
!.claude/hooks/            !.claude/hooks/**
!.claude/skills/           !.claude/skills/**
!.claude/workflows/        !.claude/workflows/**

.claude/settings.local.json
.claude/agents/.a2a_enrollment/
.claude/agents/.archive/
.claude/skills/*/.archive/
.claude/workflows/.archive/
.claude/backups/
.claude/handoff/
.claude/worktrees/
.claude/worktree-snapshots/
.claude/__pycache__/
.claude/**/__pycache__/
.claude/**/*~.tmp
.claude/**/test_hook_*.txt
.claude/**/hook_test_marker.txt
```

### Why this shape

- **`.claude/*` (single star)** is idiomatic — only blocks immediate
  children, leaves room for explicit subdir re-includes without cache
  quirks
- **Allowlist canonical subdirs even if empty today** — future content
  lands cleanly without a gitignore edit (one of the main pain
  points in the divergent patterns)
- **First-class rules for runtime artifacts** — surfaces all known
  noise sources at a glance, so a new contributor sees the policy
- **`.claude/settings.local.json` is its own rule** — universal
  fleet-wide; not subject to allowlist gymnastics

## Per-repo migration steps (after `crackerjack gitignore sync` runs)

The sync itself only edits `.gitignore`. It does **not** un-track files
already in the git tree. Per-repo cleanup is still required for files
that should be untracked:

### mahavishnu (highest priority — wrong state today)

```bash
cd /Users/les/Projects/mahavishnu
git rm --cached .claude/settings.local.json
git rm --cached .claude/agents/.a2a_enrollment/a2a_agent_index.json
git rm --cached .claude/agents/.a2a_enrollment/a2a_enrollment_summary.md
git rm --cached .claude/agents/.a2a_enrollment/a2a_validation_report.json
# Disk-cleanup (not git):
rm -rf .claude/backups/20260501T064626  # runaway-cp archive
rm -f  .claude/hook_test_marker.txt .claude/test_hook_*.txt
# Fix typo in .gitignore:
sed -i 's|^claude-skills/|.claude/skills/|' .gitignore
```

### oneiric + mcp-common (medium priority — index files missing)

```bash
cd /Users/les/Projects/oneiric
git add .claude/decisions/README.md
cd /Users/les/Projects/mcp-common
git add .claude/decisions/README.md
```

### session-buddy (cleanup, not strictly required)

The 397 files in `.claude/handoff/` are correctly ignored but
dominate every `ls .claude/`. Consider moving out-of-tree:

```bash
mkdir -p ~/.claude/handoff/session-buddy
mv .claude/handoff/session_handoff_*.md ~/.claude/handoff/session-buddy/
```

(Or rotate by month — older handoffs become archival noise.)

### akosha, crackerjack (no changes needed)

Already on the reference design. After sync runs, they'll gain the
expanded canonical block but no breakage.

## Verification

```bash
# From crackerjack/, after editing the template:
pytest crackerjack/tests/checks/test_gitignore_conformance.py -v
# 12 tests passed

# Per-repo check after the canonical block is updated:
python -c "
from crackerjack.checks.gitignore_conformance import _bodai_fleet_paths, check_repo_gitignore
for p in _bodai_fleet_paths():
    r = check_repo_gitignore(p)
    status = 'PASS' if not r.missing_patterns else 'NEEDS-SYNC'
    print(f'{status}  {p.name}  missing={len(r.missing_patterns)}')"
# Expect: every repo lists the new .claude/* patterns as missing until sync runs
```

## Rollback signal

- `crackerjack check gitignore-conformance` fails on any repo with
  missing canonical patterns after sync
- New `.claude/` files at the repo root (not under an allowlisted
  subdir) get accidentally committed — the canonical block isn't
  preventing this

Action: re-read this note, check `git diff templates/GITIGNORE_BODAI.md`,
re-run `crackerjack gitignore sync` against the affected repo.

## Related

- Template: `templates/GITIGNORE_BODAI.md`
- Audit findings (private, not in fleet repo): "Bodai fleet `.claude/`
  audit 2026-10-12" (Explore agent report)
- Per-repo migration notes will live in each consumer repo's
  `.claude/decisions/` after the sync is run

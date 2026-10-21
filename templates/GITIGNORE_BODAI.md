# >>> bodai-shared-gitignore >>>
# Source of truth: crackerjack/templates/GITIGNORE_BODAI.md
# Enforced by: crackerjack check `gitignore-conformance`
# Fleet list: /Users/les/Projects/mahavishnu/BODAI_REPO_REGISTRY.md
# Do NOT remove the marker line above — `crackerjack gitignore sync` uses it
# to detect already-applied state.

# Local configuration overlay (per-machine / per-developer; never commit)
# Patterns mirror mahavishnu/.gitignore §Local Configuration so all Bodai
# repos ignore the same overlay set. The four files are: developer-local
# overrides (`local.yaml`), the legacy repo catalog (`repos.yaml`),
# the orchestrator-managed catalog (`ecosystem.yaml`), and the per-machine
# fleet registry overlay (`registry_metadata.local.yaml`, sibling of the
# tracked `registry_metadata.yaml`).
settings/local.yaml
settings/repos.yaml
settings/ecosystem.yaml
settings/registry_metadata.local.yaml

# Editor / pre-edit backups (foo.py.backup, foo.py.backup.json)
*.backup
*.backup.*
*.bak
# `.bak.` infix (e.g. `.gitignore.bak.20261004T104858Z`,
# `foo.py.bak.20261004T104858Z`) — `*.bak` only matches a SUFFIX and silently
# misses timestamped backups where `.bak` is followed by `.` + suffix.
# Added 2026-10-05 after a session-buddy tool modifier wrote
# `.gitignore.bak.20261004T104858Z` to the working tree and the existing
# `*.bak` pattern failed to catch it on the next `git add`.
*.bak.*
.gitignore.bak.*
*.tmpl
# XDG mistake dirs (env var expansion failed; literal names)
# Note: both `{` and `}` are escaped (`{` -> `[{]`, `}` -> `[}]`)
# because gitignore parsers interpret `${...}` as a brace-expansion
# alternate group; escaping only the open brace leaves a stray `}`.
~
[{]HOME[}]
[{]XDG_DATA_HOME:-$HOME[}]
# pytest-benchmark autosave cache (sibling of the tracked `benchmarks/` test suite)
.benchmarks/

# Coverage / complexity tool outputs (run artifacts — never track).
# `.coverage*` matches the default coverage.py SQLite file plus any
# variants a parallel runner or plugin writes (`.coverage.<host>.<pid>`,
# `.coverage.<hash>`, etc.); `coverage.json` covers pytest-cov's JSON
# report and Cracker's coverage snapshot; `complexipy*.json` covers
# both legacy underscore (`complexipy_results_*.json`) and hyphen
# (`complexipy-results.json`) variants — see crackerjack/.gitignore
# lines around 58-62 and 256-262 for the per-repo provenance.
.coverage*
coverage.json
complexipy*.json
htmlcov/
# Vitest config timestamp cache
vitest.config.js.timestamp-*.mjs
# Playwright output cruft
playwright-junit.xml
playwright-report/
playwright-results.json
test-results/
# Superpowers skill artifacts (local-only, per-project runtime).
# All `.superpowers/` content is scratch: SDD controller workspace
# (briefs, reports, ledger, review packages) and the brainstorm
# visual-companion's mockup HTML+server-state. Plans and specs live
# at docs/plans/ and docs/specs/ — committed under their canonical
# paths, never under .superpowers/.
.superpowers/

# === Bodai `.claude/` policy ===
# Default-deny the entire .claude/ tree, then narrow allowlist for the
# canonical durable subtrees. Settings.local.json + runtime artifacts
# stay untracked. Converges the fleet on a single shape (was divergent:
# oneiric/mcp-common used blanket+allowlist, mahavishnu used targeted
# blocks, akosha/session-buddy/crackerjack used .claude/* + allowlist).
#
# After `crackerjack gitignore sync` runs fleet-wide, per-repo cleanup
# is still required for files already tracked that this block would
# un-track (most notably mahavishnu's .claude/settings.local.json) —
# gitignore changes don't un-track existing entries. Those require
# `git rm --cached <path>` per file per repo.
.claude/*
!.claude/CLAUDE.md
!.claude/settings.json
# Canonical durable subtrees — track everywhere (empty dirs allowed
# so future content lands without a gitignore edit):
!.claude/decisions/
!.claude/decisions/**
!.claude/agents/
!.claude/agents/**
!.claude/commands/
!.claude/commands/**
!.claude/hooks/
!.claude/hooks/**
!.claude/skills/
!.claude/skills/**
!.claude/workflows/
!.claude/workflows/**
# Runtime artifacts — never track. Surface as first-class rules so
# every contributor sees the policy at a glance:
.claude/settings.local.json
.claude/agents/.a2a_enrollment/
.claude/agents/.archive/
.claude/skills/*/.archive/
.claude/workflows/.archive/
# Generic .archive catchall — any directory named .archive (docs/plans/.archive,
# session-buddy scratch dirs, etc.) should never be tracked. The bare
# pattern matches at top level; the **/.archive/ form is explicit
# deep matching as defense in depth. Both are needed because some
# gitignore implementations short-circuit on the first match.
.archive/
**/.archive/
.claude/backups/
.claude/handoff/
.claude/worktrees/
.claude/worktree-snapshots/
.claude/__pycache__/
.claude/**/__pycache__/
.claude/**/*~.tmp
.claude/**/test_hook_*.txt
.claude/**/hook_test_marker.txt
# Runtime data dirs (per-repo scratch: DuckDB/SQLite caches, local state).
# Added 2026-10-20 after akosha's data/warm/warm.db (274 KB) was found
# tracked on main: c37dde2 (2026-09-26) untracked it and added a repo-local
# rule, then f4a5376 ("chore: bump version", the next day) re-added the
# binary and dropped the rule. A .gitignore rule only binds UNTRACKED
# files, so once the artifact re-entered the index the rule stopped
# mattering and could be deleted alongside it, leaving nothing to catch a
# repeat. Carrying the rule here makes `crackerjack gitignore sync` apply
# it fleet-wide instead of each repo rediscovering the gap.
# Verified 2026-10-20: no tracked file under any data/ dir in akosha,
# oneiric, mahavishnu, crackerjack, session-buddy or mcp-common.
data/
# <<< bodai-shared-gitignore <<<

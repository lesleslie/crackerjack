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
.claude/backups/
.claude/handoff/
.claude/worktrees/
.claude/worktree-snapshots/
.claude/__pycache__/
.claude/**/__pycache__/
.claude/**/*~.tmp
.claude/**/test_hook_*.txt
.claude/**/hook_test_marker.txt
# <<< bodai-shared-gitignore <<<

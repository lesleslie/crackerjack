---
title: Bodai Shared Gitignore Snippet (crackerjack-enforced)
description: Centralize the cross-repo `.gitignore` patterns we paste-appended to 29 Bodai fleet repos on 2026-09-07, revive the archived `check_gitignore.py`, and wire enforcement into `crackerjack run`.
audience: crackerjack maintainer + Bodai fleet owners
created: 2026-09-07
status: draft
role: implementation
topic: gitignore-conformance
date: 2026-09-07
last_reviewed: 2026-09-07
superseded_by: null
blocks_on: []
---

# Bodai Shared `.gitignore` Snippet — crackerjack-enforced

## Brief (intent-driven)

### Goal

Bodai fleet repos have a canonical `.gitignore` snippet that crackerjack CI enforces.

### Constraints

1. The canonical snippet must be a single source of truth that lives in the crackerjack repo, not duplicated per Bodai repo.
2. The check must fail `crackerjack run` for fleet repos when the snippet is missing or drifted.
3. The check must not block or mutate non-Bodai projects that use crackerjack.
4. The sync operation must back up the existing `.gitignore` to a timestamped sibling before modifying.
5. The check must preserve project-specific `.gitignore` patterns that not in the canonical snippet.

### Failure Conditions (verifier-only)

1. `crackerjack run` against `/Users/les/Projects/dhara` (and each of the other 28 fleet repos) exits 0 with the canonical snippet present in the repo's `.gitignore`.
2. Removing the canonical snippet block from any one fleet repo's `.gitignore` causes `crackerjack run` to exit 1 with a clear error naming the missing block.
4. Running `crackerjack gitignore-sync` against a fleet repo preserves every pattern in the repo's existing `.gitignore` that is not in the canonical snippet.
5. Running the new check against `/Users/les/Projects/<some-non-bodai-repo>` (any project outside the Bodai registry) does not modify the repo and exits 0.
6. The template file is referenced by exactly one source file in crackerjack (no duplicate copies).

## Context

### What happened on 2026-09-07

A one-shot cleanup sweep across the Bodai fleet paste-appended a block of cruft patterns to 29 repos' `.gitignore` files:

```
*.backup, *.backup.*, *.bak, *.tmpl
~, ${HOME}, ${XDG_DATA_HOME:-$HOME
.benchmarks/
vitest.config.js.timestamp-*.mjs
playwright-junit.xml, playwright-report/, playwright-results.json, test-results/
```

The paste was effective but it's exactly the kind of pattern that drifts on the next release — every future Bodai repo will forget to copy it, and every existing repo will diverge if someone edits the canonical set. Drift here is invisible until cruft re-accumulates, at which point we discover the snippet was never uniformly applied.

### Prior art in this repo

`crackerjack/templates/` already ships canonical templates:

- `pyproject-full.toml`, `pyproject-library.toml`, `pyproject-minimal.toml`
- `README.md`, `api_reference.md.template`, `user_guide.md.template`, `changelog_entry.md.template`

So a `templates/GITIGNORE_BODAI.md` (or `.txt`) lands in an established convention.

`crackerjack/checks/` already contains `release_audit.py` and `__init__.py` — the integration slot for a new check.

`crackerjack/docs/archive/session-artifacts/check_gitignore.py` is an archived half-built attempt that:

- Defines `STANDARD_PATTERNS` covering python cache, build artifacts, test coverage, logs, OS, config
- Has `check_repository()` and `standardize_gitignore()` functions
- Has CLI: `check_gitignore.py check|standardize <repo_path>`
- Auto-backs up to `.gitignore.backup` before overwrite
- Looks up the template at `Path(".claude/projects/GITIGNORE_TEMPLATE.md")` — that path doesn't exist anymore

That work needs revival, not replacement: the bones are right, only the template path and the pattern coverage need updating.

### How crackerjack CLI subcommands are registered

Each subcommand lives at `crackerjack/cli/<name>_cli.py` with Typer:

```python
from __future__ import annotations
import typer
from rich.console import Console

app = typer.Typer(name="gitignore", help="...", no_args_is_help=True)
console = Console()

@app.command()
def check(repo_path: Path = typer.Option(Path(), "--pkg-path", ...)) -> None:
    ...
```

Reference: `crackerjack/cli/coverage_ratchet_cli.py`.

### How checks gate `crackerjack run`

`crackerjack/checks/release_audit.py` is referenced from `crackerjack/managers/publish_manager.py`. Checks are pulled into the standard gate via the managers layer, not directly from `crackerjack run`. This is the integration slot for our check.

### Bodai fleet membership

Authoritative registry: `/Users/les/Projects/mahavishnu/BODAI_REPO_REGISTRY.md`. The check must consume this list (or a vendored copy) to know which repos to enforce on. Constraint #3 (non-Bodai opt-out) falls out of this — anything not on the registry is ignored.

## Approach

### File 1: `crackerjack/templates/GITIGNORE_BODAI.md`

Move the canonical block out of inline paste and into a single source of truth. Content is the same block from the sweep, with a header comment.

```markdown
# Bodai shared `.gitignore` snippet
# Source of truth: crackerjack/templates/GITIGNORE_BODAI.md
# Enforced by: crackerjack check `gitignore-conformance`
# Fleet list: /Users/les/Projects/mahavishnu/BODAI_REPO_REGISTRY.md

*.backup
*.backup.*
*.bak
*.tmpl
~
${HOME}
${XDG_DATA_HOME:-$HOME
.benchmarks/
vitest.config.js.timestamp-*.mjs
playwright-junit.xml
playwright-report/
playwright-results.json
test-results/
```

### File 2: `crackerjack/checks/gitignore_conformance.py`

Move `docs/archive/session-artifacts/check_gitignore.py` to here, then:

- Update `GITIGNORE_TEMPLATE` constant to point at `templates/GITIGNORE_BODAI.md` (relative to the crackerjack repo root)
- Extend `STANDARD_PATTERNS` with the Bodai-specific cruft categories (`editor_backups`, `xdg_mistake_dirs`, `benchmark_caches`, `playwright_cruft`, `vitest_cruft`)
- Add `BodaiFleetMembership`: loads `/Users/les/Projects/mahavishnu/BODAI_REPO_REGISTRY.md` and resolves absolute repo paths from the table's `Path` column. Caches the result per-process.
- Add `check_repo_gitignore(repo_path: Path) -> list[str]` returning missing-pattern violations. Empty list = pass.
- Add `sync_repo_gitignore(repo_path: Path, *, backup: bool = True) -> Path` returning the backup path (or `None` if no backup was created). Behavior:
  - Refuses to operate on a non-Bodai repo (logs + returns `None` with no mutation)
  - Reads existing `.gitignore`, parses non-comment lines, unions with canonical patterns, writes back with a leading marker comment so the next sync can detect already-applied state
  - Writes backup to `.gitignore.bak.<UTC-timestamp>` before overwriting (constraint #4)

### File 3: `crackerjack/cli/gitignore_cli.py`

New Typer subcommand module matching the convention from `coverage_ratchet_cli.py`:

```python
app = typer.Typer(name="gitignore", help="...", no_args_is_help=True)

@app.command()
def check(repo_path: Path = typer.Option(Path(), "--pkg-path", ...)) -> None: ...

@app.command()
def sync(repo_path: Path = typer.Option(Path(), "--pkg-path", ...)) -> None: ...
```

`check` exits 1 with a structured error if the canonical block is absent from a fleet repo. `sync` performs the union-and-write flow. Both refuse to operate on non-Bodai repos (constraint #3).

### File 4: `crackerjack/managers/publish_manager.py` (or peer)

Wire the new check into the standard gate so `crackerjack run` invokes `check_repo_gitignore` on every fleet repo under management. Pattern follows how `release_audit.py` is referenced today.

### File 5: `crackerjack/checks/__init__.py`

Re-export the new check alongside `release_audit`.

### Tests

`crackerjack/tests/checks/test_gitignore_conformance.py`:

- Pass: fleet repo with canonical block present → empty violations list
- Fail: fleet repo with canonical block removed → violations list contains the missing patterns
- Pass: non-Bodai repo → check returns empty (skipped)
- Sync: fleet repo with project-specific patterns → after sync, project-specific patterns still present
- Sync: writes timestamped backup before overwriting
- Sync: refuses non-Bodai repos
- Single-source: import resolution points to exactly one template file (failure condition #6)

## Resolved decisions

1. **Marker for "already-applied"**: yes — the snippet includes `# >>> bodai-shared-gitignore >>>` on its own line so `sync` can detect a previously-applied block and union cleanly.
2. **CLI subcommand shape**: `gitignore` (parent) with `check`/`sync` children — matches `coverage-ratchet`.
3. **Backwards-compat for the archived script**: archive it as `docs/archive/session-artifacts/check_gitignore.v1.py` (the new module is authoritative; the v1 archive is historical reference only).

## Risks

- **Force-pushing the snippet into a repo with a hand-tuned `.gitignore`** could surprise the repo owner even if the union semantics preserve their patterns. The sync command must default to a dry-run preview that prints what would change before asking for `--apply`. Without that, first-time sync in any repo will be a trust hit.
- **Bodai fleet membership is a moving list.** If a repo is renamed or removed from `BODAI_REPO_REGISTRY.md`, the check should not silently fail-open. Strategy: if the registry file is unreachable, the check fails-closed with a clear error.
- **The 29 paste-appended blocks aren't byte-identical to the new template.** The migration run will see them as drifted and re-sync. If their content is identical to the template, the union is idempotent and safe. If someone hand-edited one of them in the past 6 hours (low probability), we'd lose those edits on first sync. The dry-run preview mitigates this.

## References

- Memory `crackerjack-compliant-code.md` — quality gate conventions in this repo
- Memory `crackerjack-cli-run-subcommand.md` — `crackerjack run` is the canonical entry point
- Memory `crackerjack-ratchet-cli-defects.md` — precedent for how ratchet-style CLI commands are structured
- Memory `bodai-repo-registry.md` — registry as authoritative source for fleet membership
- Memory `docs-audit-cross-component-port-drift.md` — same drift pattern, different artifact (ports); this plan is the gitignore analog
- Memory `crackerjack-staged-oneiric-downgrade.md` — `crackerjack run` modifies working files; we should consider whether `gitignore-sync` should also be part of `crackerjack run -p patch` automatic bumping, or stay manual
- Memory `docs-audit-removed-but-referenced.md` — the original 29-block sweep was the cleanup that triggered this plan
- Plan template: `docs/plans/TEMPLATE.md` (if present; else this format)

## Estimated scope

| Phase | Effort |
|---|---|
| File 1 (template) | 5 min |
| File 2 (check logic) | 1.5 hr |
| File 3 (CLI subcommand) | 30 min |
| File 4 (gate integration) | 1 hr |
| File 5 (re-export) | 5 min |
| Tests | 2 hr |
| Migration run (29 repos) | 30 min |
| Review + iteration | 1 hr |
| **Total** | ~7 hr |

Ship target: end of week.

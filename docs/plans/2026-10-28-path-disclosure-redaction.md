---
title: Redact User Home Paths from Crackerjack Output and Resolve the Bodai Registry Dynamically
description: Remove the hardcoded /Users/les path from BODAI_REGISTRY_PATH and the shared gitignore template, replace it with a portable resolution chain (env var -> sibling checkout -> ~/Projects), and sweep the ~167 call sites that interpolate absolute filesystem paths into console output and log records.
audience: crackerjack maintainer
created: 2026-10-28
status: active
role: implementation
topic: security
date: 2026-10-28
last_reviewed: 2026-10-28
superseded_by: null
blocks_on: []
---

# Redact User Home Paths from Crackerjack Output and Resolve the Bodai Registry Dynamically

## Brief (intent-driven)

### Goal

No crackerjack console line or log record discloses the operator's OS account
name, and no crackerjack source file hardcodes an absolute path under a
specific user's home directory.

### Constraints

1. Redaction must preserve operator usefulness. A redacted path stays
   shell-expandable (`~/Projects/oneiric`), not truncated to a basename.
2. Redaction is a **no-op** for paths outside `$HOME`. Only the account-name
   prefix is sensitive; a path like `/opt/tools` must survive unchanged.
3. `redact_path()` must never raise. It sits inside log/console formatting,
   so a non-path value (`None`, an int) must render verbatim rather than
   crash a diagnostic.
4. The registry resolution chain must work on a developer machine, in a
   worktree, in CI, and from an installed wheel — and must **fail open**
   (no fleet members) rather than hard-fail when the registry is absent.
   Changing fail-open to fail-closed is a separate decision.
5. The registry file lives in the *mahavishnu* repo, not in crackerjack. Its
   resolution is therefore a cross-repo lookup, not a package-relative one.
6. The `templates/GITIGNORE_BODAI.md` comment block is written verbatim into
   every fleet repo's `.gitignore`. It currently carries the operator's
   username into 30+ repositories.
7. Only **comments** may change in the template. Conformance comparison
   ignores comment lines (`_existing_canonical_patterns` filters `#` lines),
   so a comment edit causes **no fleet-wide drift** and needs no re-sync.
8. Pre-1.0 — direct commit to local `main`, no PR, per
   `feedback-bodai-pre-1.0-merge-policy.md`. No push without explicit
   operator approval.

### Failure Conditions (verifier-only)

1. `git grep -n "/Users/les" -- crackerjack/ templates/` returns zero matches.
2. `BODAI_REGISTRY_PATH` as a module-level constant no longer exists; the
   registry path is resolved at call time.
3. `CRACKERJACK_BODAI_REGISTRY` overrides the resolved registry path.
4. `redact_path("/Users/<anyone>/Projects/x")` returns `~/Projects/x` for the
   *current* user, and leaves a non-home path untouched.
5. `redact_path(None)` returns `"None"` and does not raise.
6. `pytest tests/` for the touched suites exits 0.
7. `ruff check` and `ty check` pass on every changed file.

## Phase 1 — Dynamic registry resolution

### Design

New module `crackerjack/checks/bodai_registry.py` owns both the *where* and
the *how*:

- `resolve_registry_path() -> Path | None` — the resolution chain.
- `parse_registry_paths(text) -> list[Path]` — path-column extraction from the
  generated markdown tables.
- `load_fleet_repo_paths() -> frozenset[Path]` — the `###`-scoped fleet set
  used by the conformance gate.

Resolution chain (first hit wins):

1. `$CRACKERJACK_BODAI_REGISTRY` — explicit operator override.
2. Sibling checkout next to the running package
   (`<repo root>/../mahavishnu/BODAI_REPO_REGISTRY.md`).
3. Sibling checkout next to the current working directory.
4. `~/Projects/mahavishnu/BODAI_REPO_REGISTRY.md` — canonical dev layout.

The candidate for (2) is derived from the *package* location so it works in a
worktree checkout; in an installed wheel it simply does not resolve, which is
correct.

Step 1 is **authoritative**: if the override names something that is not a
file, resolution stops there and reports no fleet members, rather than
silently falling through to a different registry. An operator who points the
variable at a path must not be left believing they are testing against that
registry when the resolver quietly used another one.

### Integration Contract

**Integration Contract:**
- **Triggered from:** `crackerjack gitignore check|sync`, and the publish
  gate's `_validate_gitignore_conformance`.
- **Returns to / updates:** `is_bodai_fleet_member()` now consults a
  dynamically resolved registry; unchanged return contract.
- **Demonstrable by:** `python -m crackerjack gitignore check --pkg-path
  <fleet repo>` prints a home-relative path and exits 0.
- **Rollback signal:** registry resolves to `None` where it previously
  resolved to a file — fleet membership silently drops to zero.
- **Observability added:** a `logger.warning` naming every candidate tried
  when resolution fails.

## Phase 2 — Path-disclosure sweep

### Design

Apply `redact_path()` at every call site that interpolates a filesystem path
into a console line or log record. The sweep is script-driven (AST-guided,
byte-precise) and then reviewed by hand.

The helper lives in `crackerjack/utils/path_redaction.py` and imports
**nothing** from `crackerjack`. A helper that lived with the other display
formatters would pull `crackerjack.config` in, and `crackerjack.config`
reaches back into modules that log paths — a cycle across a 69-file sweep.

Selection rule: the interpolated expression must be a `Name` or `Attribute`
chain whose final dotted segment contains one of `path`, `dir`, `folder`,
`file`, `root`, `cwd`, `location`, `home`, `repo`, `workdir`, `basedir` as a
**whole underscore-separated word** — excluding `.name`, `.stem`, `.suffix`
(not paths) and `relpath` (already relative).

The whole-word rule is load-bearing. Substring matching selects `total_files`
(a count), `direction_color` (a colour), `profile_name` (a label) and
`coverage_report` (a report) — none of which are paths.

Because `redact_path()` is a no-op outside `$HOME`, the sweep cannot change
behavior for non-home paths.

### Integration Contract

**Integration Contract:**
- **Triggered from:** every `logger.*` and `console.print` call that names a
  path.
- **Returns to / updates:** message text only; no control flow changes.
- **Demonstrable by:** a captured log record contains `~/Projects/...` and
  never `/Users/<name>/`.
- **Rollback signal:** a log consumer parses the absolute path out of a
  message and breaks on the `~` form.
- **Observability added:** none — this phase only removes disclosure.

## Out of Scope

1. The registry file in the *mahavishnu* repo still contains `/Users/les`
   in its prose and in the generated path column. That is a different repo
   with its own generation pipeline.
2. `settings/ecosystem.yaml` in mahavishnu is the true source of the
   registry; crackerjack consumes the generated markdown.
3. Fail-open vs fail-closed when the registry is missing (constraint 4).
4. The pre-existing 4 failures in `tests/checks/test_release_audit.py`
   (`_verify_removed()` signature drift) — unrelated to this work.

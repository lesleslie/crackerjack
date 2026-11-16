# The plan index has exactly one renderer

**Date:** 2026-11-16

## Context

`docs/plans/PLAN_INDEX.md` is a generated file, and the fleet had **three**
implementations writing to that one path:

| Implementation | Scope | Output | Who ran it |
|---|---|---|---|
| `crackerjack/tools/plan_index_sync.py` — legacy inline renderer | five hard-coded Bodai stores | 4.5 KB | the `plan_index_sync` publish phase; the committed index in five of six repos |
| `oneiric.plan_index.regenerate` — the "shared" package | stores discovered dynamically | 6.3 KB | nothing by default; opt-in via `documentation.use_shared_regenerator` |
| `scripts/regenerate_plan_index.py` — a copy per repo | stores discovered dynamically, plus a status legend, an authority matrix and per-kind tables | 8.2 KB | the command `docs/schemas/document-frontmatter-v1.md` tells you to run |

The phase owns the file and runs on publish, so in five of six repos the
committed index is the phase's output, byte for byte. The repo-local copies
were dead weight there — and in the one repo whose index *was* in the copy's
format, the phase's next run would have replaced it.

Worse, the "shared" branch was not a drop-in replacement:

- it **returns the entry count where a caller expects an exit code**, so the
  publish phase would have reported `plan_index_sync exited with code 277`
  and failed the release on success;
- its output is **not mdformat-stable** — it writes `Role \ Lifecycle` where
  mdformat writes `Role \\ Lifecycle`, which is the exact defect the
  in-crackerjack renderer was fixed for. mdformat gates `docs/`, so every
  run would rewrite the index and leave the tree dirty for a change nobody
  made;
- it does **not filter to git-tracked files**, so a stray untracked
  `README.md` would be indexed and its rendered link would fail
  `check-local-links` on a fresh clone.

## Decision

**`crackerjack.tools.plan_index_sync` is the single renderer** for the five
canonical Bodai stores (`docs/adr/`, `docs/plans/`, `docs/specs/`,
`.claude/decisions/`, `docs/followups/`). It keeps the guarantees the fleet
depends on — mdformat stability, git-tracked filtering, link targets that
resolve from `docs/plans/` — and its unit tests pin them.

The shared `oneiric.plan_index` branch is **removed** from the tool, and the
`documentation.use_shared_regenerator` setting is removed with it. It was
opt-in, off by default, and broken in all three ways above.

Each repo's `scripts/regenerate_plan_index.py` becomes a **thin wrapper** over
the tool, so the command the schema documents produces byte-identical output
to the publish phase. The wrapper also gained `--json-summary` on the tool,
which the copies had and the tool did not — the per-store counts now come
from the renderer that actually writes the index.

**`mahavishnu/scripts/regenerate_plan_index.py` is the documented
exception.** It is not a copy that drifted; it is a different artifact. It
renders the *ecosystem* index — thirteen stores rather than five, with a
status legend, an authority matrix and per-kind tables — and it is the
shared frontmatter library that `mahavishnu/scripts/audit_doc_frontmatter.py`
imports (`KIND_VALUES`, `LIFECYCLE_VALUES`, `ROLE_VALUES`,
`extract_frontmatter`, `_is_excluded`). Replacing it with the wrapper would
break that import and silently drop eight store sections from mahavishnu's
index.

## Consequences

- The documented command and the publish phase now produce the same bytes.
  Running the script can no longer produce a diff that the next publish
  reverts.
- The five repos whose index was already the phase's output are unchanged:
  the wrapper's output is byte-identical to what is committed.
- **`mahavishnu`'s index will change on its next publish** — from thirteen
  stores to the five canonical ones. That is the one coverage loss in this
  change, and it is a content decision rather than a mechanical one:
  mahavishnu's index is the ecosystem-wide map, and the canonical store set
  is the plan index's set. Unifying them is a separate piece of work.
- The repo-local copies were also the *tested* unit in `akosha` and
  `mcp-common`. Those tests now assert the contract against the renderer —
  the canonical store set, no duplicates, one non-empty section per store —
  so they test the implementation that actually writes the index.

## Related

- `docs/decisions/2026-11-15-archive-lifecycle-gate.md` describes the
  removed shared branch; it carries a supersession note.

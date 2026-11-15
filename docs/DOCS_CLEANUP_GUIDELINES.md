---
status: active
role: canonical
date: 2026-07-17
last_reviewed: 2026-07-17
superseded_by: null
blocks_on: []
topic: lifecycle
---

# Documentation Cleanup Guidelines

**Purpose**: Define rules for organizing documentation files to maintain a clean, discoverable project structure.

## Core Principles

1. **Active implementation plans stay in project root or `docs/`**
1. **Closed documents go to `<area>/.archive/` (gitignored)** — a document
   is closed at `status: shipped`, not at `status: complete`
1. **User-facing documentation stays in easily accessible locations**
1. **Reference documentation goes to `docs/reference/`**
1. **Feature documentation goes to `docs/features/`**

## File Organization Rules

### 📍 Project Root (`/`)

**Keep** only core project documentation:

- `README.md` - Project overview
- `CHANGELOG.md` - Version history
- `CLAUDE.md` - Claude Code instructions
- `AGENTS.md` - Agent documentation
- `RULES.md` - Project rules
- `SECURITY.md` - Security policy
- `QWEN.md` - Qwen model docs
- `TY_MIGRATION_PLAN.md` - Implementation plan (example). The
  categorizer classifies it as an implementation plan, so it is archived to
  `<area>/.archive/implementation-plans/` — it stays here until it is
  `status: shipped` (see the Decision Tree below).
- `*_PLAN.md` - **Implementation plans, until they are `status: shipped`**

### 📚 Documentation Root (`docs/`)

**Keep** user-facing and active documentation:

- Migration guides (`MCP_GLOBAL_MIGRATION_GUIDE.md`, `MIGRATION_GUIDE_*.md`)
- System documentation (`SKILL_SYSTEM.md`, `STRUCTURED_LOGGING.md`)
- Feature docs (`docs/features/*.md`)
- Reference guides moved to `docs/reference/`
- **Implementation plans** (until they are `status: shipped`)
- Completion milestones (`PHASE_*_COMPLETION.md`)

The cleanup never *moves* a file it classifies as `keep_in_root` or
`keep_in_docs` — it only declines to archive it. `MCP_GLOBAL_MIGRATION_GUIDE.md`
and `PHASE_*_COMPLETION.md` are classified as keep-in-root, so the cleanup
leaves them wherever they are; putting them in `docs/` is a manual choice.

### 📦 Archive (`<area>/.archive/<category>/`)

**Gitignored directory** for historical documentation. The archive lives
beside the area the file came from, so a file in `docs/plans/` lands in
`docs/plans/.archive/`, one in `docs/specs/` in `docs/specs/.archive/`, and
a root-level file in `docs/.archive/`. (This per-area scheme replaced the
old flat `docs/archive/`; see the mahavishnu decision
`~/Projects/mahavishnu/docs/decisions/2026-10-15-archive-dir-canonical.md`.)

The category is the second path segment. The destinations the categorizer
produces:

The name patterns below are illustrative — `DocumentationCategorizer.CATEGORIES`
is the authority, and the examples further down are checked against it by
`tests/test_docs_cleanup_guidelines.py`.

#### `.archive/summaries/`

- `*_COMPLETE.md`
- `*_FINAL_REPORT.md`
- `*_SUMMARY.md` (completion summaries)

#### `.archive/sprints-and-fixes/`

- Sprint progress reports (`*_PROGRESS.md`)
- Fix documentation (`*_FIX.md` — `_FIX` immediately before the extension;
  `*_FIXE*.md` / `*_FIXES*.md` — `_FIXE` optionally followed by `S`;
  plus `BUGFIX_*.md`, `FIX_*.md`, `CRITICAL_*.md`. A name like
  `*_FIX_ABC.md` matches none of them)
- Agent-related docs (`*_AGENT_*.md` — the pattern needs an underscore on
  both sides, so a bare `AGENT_NOTES.md` is not one)

#### `.archive/audits/`

- `*_AUDIT.md`
- Audit documentation

#### `.archive/investigations/`

- `*_investigation.md`
- Investigation reports

#### `.archive/analysis/`

- `*_ANALYSIS.md`
- Analysis documents

#### `.archive/implementation-plans/`

- Shipped implementation plans

#### `.archive/implementation-reports/`

- Progress reports
- `progress-*.md`
- `*-implementation.md`

#### `.archive/session-artifacts/`, `.archive/test-artifacts/`, `.archive/temp-files/`

- Session scratch files, test artifacts, and temporary files

### 📖 Reference (`docs/reference/`)

**Keep** long-lived reference documentation:

- `COVERAGE_POLICY.md` - Coverage guidelines
- `BREAKING_CHANGES.md` - Breaking changes log
- `ADAPTER_UUID_REGISTRY.md` - Adapter ID registry
- Other reference documentation

### 🌟 Features (`docs/features/`)

**Keep** feature-specific documentation:

- `PARALLEL_EXECUTION.md` - Parallel execution feature
- Other feature documentation

## Decision Tree

```
Does it carry YAML frontmatter (a governed document)?
├─ Yes → Is it closed (status: shipped)?
│   ├─ Yes → Move to <area>/.archive/<category>/
│   └─ No  → Leave it where it is — the gate covers every governed
│            document, not only plans
└─ No → Is it an implementation plan?
    ├─ Yes → Keep in root or docs/ while it is active — and give it
    │        frontmatter: with NO frontmatter at all the cleanup treats
    │        it as a scratch artifact and sweeps it by name
    └─ No → Is it a completion report?
        ├─ Yes → Move to <area>/.archive/summaries/
        └─ No → Is it user-facing docs?
            ├─ Yes → Keep in accessible location
            └─ No → Is it reference documentation?
                ├─ Yes → Move to docs/reference/
                └─ No → Is it audit/investigation?
                    ├─ Yes → Move to <area>/.archive/audits/ or /investigations/
                    └─ No → Review manually
```

A document at `status: complete` is **not** closed — "delivered" is not
"verified". Flip it to `shipped` before archiving it. The gate applies to
any document with frontmatter: a completion report at `status: complete`
stays put just as a plan does.

## Examples

Every destination below is the categorizer's own verdict for that exact
filename — `categorize_file()` decides the category, and the archive path is
composed from it. A document listed under an archive heading still has to
pass the lifecycle gate before it moves.

### ✅ Keep in Root

- `README.md` - Core project documentation
- `CLAUDE.md` - User-facing instructions
- `MCP_GLOBAL_MIGRATION_GUIDE.md` - Migration reference
- `PHASE_4_COMPLETION.md` - Milestone documentation

### ✅ Keep in docs/

- `AI_FIX_EXPECTED_BEHAVIOR.md` - User-facing (referenced by CLAUDE.md)

### 📦 Move to Archive

#### .archive/summaries/

- `<area>/.archive/summaries/ADAPTER_FIX_COMPLETION_REPORT.md`
- `<area>/.archive/summaries/COMPLEXITY_REFACTORING_FINAL_REPORT.md`
- `<area>/.archive/summaries/SKILL_SYSTEM_IMPLEMENTATION_SUMMARY.md`

#### .archive/sprints-and-fixes/

- `<area>/.archive/sprints-and-fixes/ZUBAN_FIX_PROGRESS.md`
- `<area>/.archive/sprints-and-fixes/COMPLEXITY_REFACTORING_PROGRESS.md`
- `<area>/.archive/sprints-and-fixes/ERROR_DETAILS_DISPLAY_FIX.md`

#### .archive/audits/

- `<area>/.archive/audits/CLI_OPTIONS_AUDIT.md`
- `<area>/.archive/audits/comprehensive_hooks_audit.md`

#### .archive/investigations/

- `<area>/.archive/investigations/bandit-performance-investigation.md`
- `<area>/.archive/investigations/MCP_SERVER_INVESTIGATION.md`

#### .archive/analysis/

- `<area>/.archive/analysis/HOOK_REPORTING_ANALYSIS.md`

#### .archive/implementation-plans/

- `<area>/.archive/implementation-plans/TY_MIGRATION_PLAN.md`

#### .archive/implementation-reports/

- `<area>/.archive/implementation-reports/progress-indicator-analysis.md`

## Implementation Plan Integration

Implementation plans should follow this lifecycle:

1. **Create** in project root (e.g., `FEATURE_MIGRATION_PLAN.md`)
1. **Active Development** → Keep in root
1. **Complete** → Flip to `status: shipped`, then move to
   `<area>/.archive/implementation-plans/`
1. **Completion Report** → Create separate report in `<area>/.archive/summaries/`

### The lifecycle gate

**A plan may only be archived once its frontmatter says `status: shipped`.**

`complete` is not enough. In the shared frontmatter vocabulary
(`oneiric.schemas.document-frontmatter-v1`):

| `status:` | Meaning | Archivable? |
|---|---|---|
| `draft` | In preparation, not yet approved | No |
| `active` | Approved and in current use | No |
| `partial` | Partially implemented, work still open | No |
| `complete` | Delivered; **verification or follow-up may still be open** | **No** |
| `shipped` | Delivered **and verified**; closed | **Yes** |

The distinction is the whole point: `complete` means the work landed,
not that it was verified. A plan at `complete` still has open questions,
and archiving it buries them — `docs/<area>/.archive/` is gitignored, so
an archived plan leaves the repository rather than moving within it.

The flip is a deliberate act. Read the plan's body, confirm the
verification closed, then set `status: shipped`.

The cleanup tool enforces this. A **markdown** document that carries YAML
frontmatter is archived only when its `status:` is archivable — `shipped` by
default, configurable through `documentation.archivable_statuses` in
`settings/crackerjack.yaml`. A markdown document with **no** frontmatter is
not lifecycle-governed and is swept as before; one whose frontmatter does not
parse, or declares no `status:`, is left in place.

The gate applies to markdown — it is the only thing that carries a
frontmatter lifecycle. The loose non-markdown artifacts the cleanup also
sweeps (`*.json`, `*.py`, `*.backup`) have none.

The test is on the **name**, not the suffix: `TEST_foo.md.backup` holds a
document's content, so it is gated like the document it is a copy of.
(The `analysis` category's `TEST_.*\.md` pattern classifies it, because
`re.match` anchors at the *start* of a name and so matches a prefix.)

See `docs/plans/2026-11-15-archive-lifecycle-gate.md` and
`docs/decisions/2026-11-15-archive-lifecycle-gate.md`.

## Automated Cleanup

`crackerjack run`'s own `documentation_cleanup` phase is the tool that
actually moves files. It applies the lifecycle gate above, and its
`DocumentationCategorizer` is the authority on which category a filename
belongs to and where that category lands.

`scripts/docs_cleanup.py` is an older standalone report and is **not** a
reliable guide today: it carries its own copy of the category table,
which still emits the old flat `docs/archive/<category>/` routes rather
than the per-area paths above, and it fails to start — it registers
`--dry-run` twice, so argparse rejects it before it reads a single file.
Use the tool, not the script, until the script is re-pointed at
`DocumentationCategorizer` instead of forking it.

## Special Cases

### `AI_FIX_EXPECTED_BEHAVIOR.md`

- **Status**: User-facing documentation
- **Referenced by**: `CLAUDE.md`
- **Location**: Keep in `docs/` (accessible to users)

### `TY_MIGRATION_PLAN.md`

- **Status**: Active implementation plan
- **Location**: Keep in project root
- **Reason**: Plan is not yet completed, needs visibility

## Maintenance

**Review documentation structure quarterly:**

- Archive **shipped** implementation plans (a plan at `status: complete` is
  delivered but not verified — flip it to `shipped` first)
- Remove obsolete documents
- Update references in CLAUDE.md and README.md

**When to run cleanup:**

- After a major feature **ships** — a feature at `status: complete` is
  delivered, not closed
- After sprint milestones
- When docs/ becomes cluttered (>20 files in root)

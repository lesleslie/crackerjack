# Documentation Cleanup Guidelines

**Purpose**: Define rules for organizing documentation files to maintain a clean, discoverable project structure.

## Core Principles

1. **Active implementation plans stay in project root or `docs/`**
1. **Completion reports and historical docs go to `docs/archive/` (gitignored)**
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
- `TY_MIGRATION_PLAN.md` - Active implementation plan (example)
- `*_PLAN.md` - **Active implementation plans only**

### 📚 Documentation Root (`docs/`)

**Keep** user-facing and active documentation:

- Migration guides (`MCP_GLOBAL_MIGRATION_GUIDE.md`, `MIGRATION_GUIDE_*.md`)
- System documentation (`SKILL_SYSTEM.md`, `STRUCTURED_LOGGING.md`)
- Feature docs (`docs/features/*.md`)
- Reference guides moved to `docs/reference/`
- **Active implementation plans** (not yet completed)
- Completion milestones (`PHASE_*_COMPLETION.md`)

### 📦 Archive (`docs/archive/`)

**Gitignored directory** for historical documentation:

#### `docs/archive/completion-reports/`

- `*_COMPLETE.md`
- `*_FINAL_REPORT.md`
- `*_SUMMARY.md` (completion summaries)
- `FIX_*.md` (fix completion reports)

#### `docs/archive/sprints-and-fixes/`

- Sprint progress reports (`*_PROGRESS.md`)
- Fix documentation (`*_FIX*.md`, `*_FIXES.md`)
- Implementation plans (completed)
- Agent-related docs (`ZUBAN_*.md`, `AGENT_*.md`)

#### `docs/archive/audits/`

- `*_AUDIT.md`
- Audit documentation

#### `docs/archive/investigations/`

- `*_investigation.md`
- Investigation reports

#### `docs/archive/analysis/`

- `*_ANALYSIS.md`
- Analysis documents

#### `docs/archive/implementation-reports/`

- Progress reports
- `progress-*.md`
- `*-implementation.md`

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
Is it an implementation plan?
├─ Yes → Is it active (not completed)?
│   ├─ Yes → Keep in root or docs/
│   └─ No → Move to docs/archive/sprints-and-fixes/
└─ No → Is it a completion report?
    ├─ Yes → Move to docs/archive/completion-reports/
    └─ No → Is it user-facing docs?
        ├─ Yes → Keep in accessible location
        └─ No → Is it reference documentation?
            ├─ Yes → Move to docs/reference/
            └─ No → Is it audit/investigation?
                ├─ Yes → Move to docs/archive/audits/ or /investigations/
                └─ No → Review manually
```

## Examples

### ✅ Keep in Root

- `TY_MIGRATION_PLAN.md` - Active implementation plan
- `README.md` - Core project documentation
- `CLAUDE.md` - User-facing instructions

### ✅ Keep in docs/

- `AI_FIX_EXPECTED_BEHAVIOR.md` - User-facing (referenced by CLAUDE.md)
- `MCP_GLOBAL_MIGRATION_GUIDE.md` - Migration reference
- `PHASE_4_COMPLETION.md` - Milestone documentation

### 📦 Move to Archive

#### docs/archive/completion-reports/

- `ADAPTER_FIX_COMPLETION_REPORT.md`
- `COMPLEXITY_REFACTORING_FINAL_REPORT.md`
- `SKILL_SYSTEM_IMPLEMENTATION_SUMMARY.md`

#### docs/archive/sprints-and-fixes/

- `ZUBAN_FIX_PROGRESS.md`
- `COMPLEXITY_REFACTORING_PROGRESS.md`
- `ERROR_DETAILS_DISPLAY_FIX.md`

#### docs/archive/audits/

- `CLI_OPTIONS_AUDIT.md`
- `comprehensive_hooks_audit.md`

#### docs/archive/investigations/

- `bandit-performance-investigation.md`
- `MCP_SERVER_INVESTIGATION.md`

#### docs/archive/analysis/

- `HOOK_REPORTING_ANALYSIS.md`
- `progress-indicator-analysis.md`

## Implementation Plan Integration

Implementation plans should follow this lifecycle:

1. **Create** in project root (e.g., `FEATURE_MIGRATION_PLAN.md`)
1. **Active Development** → Keep in root
1. **Complete** → Move to `docs/archive/sprints-and-fixes/`
1. **Completion Report** → Create separate report in `docs/archive/completion-reports/`

## Automated Cleanup

Use `scripts/docs_cleanup.py` to analyze documentation:

```bash
# Preview changes
python scripts/docs_cleanup.py --dry-run

# Execute cleanup (manual review recommended)
python scripts/docs_cleanup.py --execute
```

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

- Archive completed implementation plans
- Remove obsolete documents
- Update references in CLAUDE.md and README.md

**When to run cleanup:**

- After major feature completion
- After sprint milestones
- When docs/ becomes cluttered (>20 files in root)

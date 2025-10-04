# Documentation Reorganization Plan

## Current State Analysis

**Problem**: 50+ markdown files scattered across project root, docs/, tests/, and nested directories with significant duplication and poor organization.

**Key Issues Identified**:

- Duplicated files: `API_REFERENCE.md`, `ARCHITECTURE.md` exist in both root and docs/
- Mixed purposes: User docs, implementation plans, and internal analysis all in root
- Scattered security docs: Root has `SECURITY.md`, `SECURITY-AUDIT.md` + 5 files in docs/security/
- Implementation plans cluttering root directory (12+ \*\_PLAN.md files)
- No clear navigation structure for developers

## Proposed Reorganization

### Project Root - Essential User Files Only

**Keep in root** (5 files):

```
README.md           # Main project overview
CHANGELOG.md        # Version history
CLAUDE.md          # Claude Code instructions
SECURITY.md        # Security policy (consolidated)
RULES.md           # Development rules
```

### docs/ Directory - Organized Documentation

```
docs/
├── architecture/
│   ├── ARCHITECTURE.md     # (moved from root, deduplicated)
│   ├── API_REFERENCE.md    # (moved from root, deduplicated)
│   └── AGENTS.md          # (moved from root)
├── development/
│   ├── IDE-SETUP.md
│   └── RUST_TOOLING_FRAMEWORK.md
├── systems/
│   ├── CACHING_SYSTEM.md
│   ├── BACKUP_SYSTEM.md
│   ├── MCP_INTEGRATION.md
│   ├── MONITORING_INTEGRATION.md
│   ├── UNIFIED_MONITORING_ARCHITECTURE.md
│   └── DASHBOARD_ARCHITECTURE.md
├── ai/
│   ├── AI-REFERENCE.md     # (moved from root)
│   └── AGENT_SELECTION.md
├── planning/
│   ├── CONFIG_MANAGEMENT_REPLACEMENT_PLAN.md
│   ├── CONFIG_MERGE_REMOVAL_PLAN.md
│   ├── COVERAGE_BADGE_IMPLEMENTATION_PLAN.md
│   ├── FEATURE_IMPLEMENTATION_PLAN.md
│   ├── RESILIENT_HOOK_ARCHITECTURE_PLAN.md
│   ├── RESILIENT_HOOK_ARCHITECTURE_IMPLEMENTATION_SUMMARY.md
│   ├── STAGE_HEADERS_IMPLEMENTATION_PLAN.md
│   ├── CURRENT_IMPLEMENTATION_STATUS.md
│   ├── EXPERIMENTAL-EVALUATION.md
│   └── ZUBAN_TOML_PARSING_BUG_ANALYSIS.md
└── security/
    ├── SECURITY_AUDIT_REPORT.md
    ├── SECURITY_AUDIT_STATUS_DISCLOSURE.md
    ├── SECURITY_HARDENING_REPORT.md
    ├── SECURITY_SUBPROCESS_HARDENING_REPORT.md
    └── INPUT_VALIDATOR_SECURITY_AUDIT.md
```

### tests/docs/ - Test Documentation

```
tests/docs/
├── TEST_COVERAGE_PLAN.md
├── TEST_IMPLEMENTATION_PLAN.md
└── HEALTH_METRICS_TESTING_SUMMARY.md
```

### Keep As-Is

- `crackerjack/docs/generated/` - Generated API documentation
- `crackerjack/slash_commands/` - MCP command documentation
- `examples/README.md` - Example documentation
- `test_docs_site/` - Test documentation site

## File Actions Required

### Moves (25 files)

- Root → docs/architecture/: `ARCHITECTURE.md`, `API_REFERENCE.md`, `AGENTS.md`
- Root → docs/ai/: `AI-REFERENCE.md`
- Root → docs/planning/: 12+ implementation and status files
- tests/ → tests/docs/: 3 test planning files

### Consolidations (2 merges)

- Merge duplicate `ARCHITECTURE.md` files (keep most current)
- Merge duplicate `API_REFERENCE.md` files (keep most current)
- Consolidate `SECURITY-AUDIT.md` into docs/security/

### Removals (3+ files)

- Remove duplicate versions after content verification
- Archive completed implementation plans (if any)
- Remove obsolete analysis files (candidate: `QWEN.md`, `UVXUSAGE.md`)

## Reference Updates Needed

1. **CLAUDE.md**: Update any documentation references
1. **README.md**: Update documentation links to new structure
1. **Internal docs**: Update cross-references between moved files

## Implementation Order

1. Create new directory structure
1. Check duplicates for content differences
1. Move files to new locations
1. Update cross-references
1. Remove duplicates and obsolete files
1. Verify all links work

## Expected Outcome

- **Root directory**: Clean, only essential user files (5 files vs current 25+)
- **docs/ directory**: Logical organization by purpose and audience
- **No duplicates**: Single source of truth for each piece of documentation
- **Better navigation**: Clear hierarchy for finding relevant documentation
- **Easier maintenance**: Related docs grouped together

**File count reduction**: ~50 scattered files → ~35 organized files

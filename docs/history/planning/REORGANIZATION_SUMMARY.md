# Documentation Reorganization - Quick Reference

## Visual Transformation

### BEFORE (Current State - 61 files)

```
docs/
├── 📁 ROOT (21 files - CHAOTIC) ← PROBLEM!
│   ├── Phase summaries (10 files)
│   ├── Implementation plans (3 files)
│   ├── User guides (2 files)
│   ├── Audits (2 files)
│   └── Misc (4 files)
├── 📁 planning/ (13 files - MIX OF ACTIVE/HISTORICAL)
├── 📁 security/ (6 files - DUPLICATE CONTENT) ← PROBLEM!
├── 📁 systems/ (6 files - good)
├── 📁 precommit-handling/ (5 files - OBSOLETE) ← PROBLEM!
├── 📁 archive/ (3 files)
├── 📁 architecture/ (2 files - good)
├── 📁 development/ (2 files - good)
└── 📁 investigation/ (2 files - COMPLETED WORK)

❌ Missing: AI documentation (referenced in CLAUDE.md) ← CRITICAL!
```

### AFTER (Proposed State - ~30 active + 31 archived)

```
docs/
├── 📁 ai/ (3 files - NEW!) ← CREATES CRITICAL MISSING DOCS
│   ├── AI-REFERENCE.md (command reference, decision trees)
│   ├── AGENT-CAPABILITIES.json (structured agent data)
│   └── ERROR-PATTERNS.yaml (automated fixes)
│
├── 📁 guides/ (3 files - USER-FACING)
│   ├── ADVANCED-FEATURES.md
│   ├── AUTO_FIX_GUIDE.md
│   └── GETTING-STARTED.md (new)
│
├── 📁 architecture/ (4 files - CORE ARCHITECTURE)
│   ├── ARCHITECTURE.md
│   ├── API_REFERENCE.md
│   ├── WORKFLOW-ARCHITECTURE.md
│   └── DOCUMENTATION_SYSTEM.md
│
├── 📁 systems/ (6 files - SYSTEM DOCUMENTATION)
│   ├── BACKUP_SYSTEM.md
│   ├── CACHING_SYSTEM.md
│   ├── DASHBOARD_ARCHITECTURE.md
│   ├── MCP_INTEGRATION.md
│   ├── MONITORING.md (consolidated from 2)
│   └── HOOK_MANAGEMENT.md (new - pre-commit info)
│
├── 📁 development/ (3 files - DEVELOPER DOCS)
│   ├── IDE-SETUP.md
│   ├── RUST_TOOLING_FRAMEWORK.md
│   └── CONTRIBUTING.md (new)
│
├── 📁 security/ (1 file - CONSOLIDATED) ← FIXED!
│   └── SECURITY_AUDIT.md (consolidated from 6 files)
│
├── 📁 planning/ (3 files - ACTIVE PLANNING ONLY)
│   ├── EXPERIMENTAL-EVALUATION.md
│   ├── STATUS.md
│   └── ROADMAP.md (new)
│
├── 📁 history/ (31 files - ORGANIZED HISTORICAL) ← CLEAN ROOT!
│   ├── phases/ (6 phase summaries)
│   ├── implementations/ (15 completed plans)
│   ├── investigations/ (4 bug fixes)
│   └── audits/ (6 audits + security/)
│
└── 📁 archive/ (3 files - TRULY OBSOLETE)
    └── [deprecated content]

✅ Zero root-level files
✅ All active docs categorized
✅ Historical work preserved but organized
✅ AI documentation complete
```

## Key Metrics

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Total Files** | 61 | 61 | 0 (reorganized) |
| **Active Files** | ~30 (mixed) | 23 (clear) | -23% |
| **Root Files** | 21 | 0 | **-100%** ✅ |
| **Active Lines** | ~23,273 | ~11,000 | **-50%** ✅ |
| **Security Files** | 6 (66.3K) | 1 (25K) | **-62%** ✅ |
| **Monitoring Files** | 2 (628 lines) | 1 (400 lines) | **-36%** ✅ |
| **Missing AI Docs** | 3 | 0 | **Fixed** ✅ |

## Critical Changes

### 🔴 BLOCKING ISSUES RESOLVED

1. **AI Documentation Missing** (CRITICAL)

   - `docs/ai/AI-REFERENCE.md` - Created
   - `docs/ai/AGENT-CAPABILITIES.json` - Created
   - `docs/ai/ERROR-PATTERNS.yaml` - Created
   - **Impact**: CLAUDE.md references now valid

1. **Root-level Chaos** (HIGH)

   - 21 files → 0 files
   - All properly categorized
   - **Impact**: Developers can find what they need

1. **Security Duplication** (MEDIUM)

   - 6 overlapping files → 1 consolidated
   - 66.3K → 25K (62% reduction)
   - **Impact**: Single source of truth

### ✅ QUALITY IMPROVEMENTS

4. **Phase History Organization**

   - 10 scattered summaries → `history/phases/`
   - Chronological order preserved
   - **Impact**: Institutional knowledge accessible

1. **Implementation Plans**

   - Active vs completed clearly separated
   - `planning/` only has future work
   - **Impact**: Focus on what matters

1. **Pre-commit Documentation**

   - 5 redundant files → consolidated in `systems/`
   - Implementation details in `history/`
   - **Impact**: Feature stable, docs streamlined

## Migration Checklist

### Phase 1: Prepare (30 min)

- [ ] Backup `docs/` directory
- [ ] Review plan: `/Users/les/Projects/crackerjack/docs/DOCUMENTATION_REORGANIZATION_PLAN_2025.md`
- [ ] Create new directory structure
- [ ] Create placeholder files

### Phase 2: CRITICAL - AI Documentation (2 hrs)

- [ ] Create `ai/AI-REFERENCE.md` with decision trees
- [ ] Create `ai/AGENT-CAPABILITIES.json` with agent data
- [ ] Create `ai/ERROR-PATTERNS.yaml` with fix patterns
- [ ] Verify CLAUDE.md references work

### Phase 3: Move Active Docs (30 min)

- [ ] Move user guides to `guides/`
- [ ] Move architecture docs to `architecture/`
- [ ] Move planning docs to `planning/`
- [ ] Update planning/STATUS.md

### Phase 4: Archive Historical (30 min)

- [ ] Move phase summaries to `history/phases/`
- [ ] Move implementations to `history/implementations/`
- [ ] Move investigations to `history/investigations/`
- [ ] Move audits to `history/audits/`

### Phase 5: Consolidate (1 hr)

- [ ] Consolidate security docs (6 → 1)
- [ ] Consolidate monitoring docs (2 → 1)
- [ ] Create `systems/HOOK_MANAGEMENT.md`
- [ ] Move originals to history

### Phase 6: Delete Obsolete (10 min)

- [ ] Delete superseded phase docs
- [ ] Delete trivial/outdated files
- [ ] Remove empty directories

### Phase 7: Create New Content (1 hr)

- [ ] Create `guides/GETTING-STARTED.md`
- [ ] Create `development/CONTRIBUTING.md`
- [ ] Create `planning/ROADMAP.md`
- [ ] Create `docs/README.md` index

### Phase 8: Validate (30 min)

- [ ] Run link checker on all docs
- [ ] Update CLAUDE.md doc references
- [ ] Update README.md doc references
- [ ] Test `python -m crackerjack` (no broken refs)
- [ ] Git commit with migration message

## Quick Start (Minimal Viable Migration)

If you need to do the absolute minimum:

### 1. Create AI Docs (CRITICAL - 2 hrs)

```bash
mkdir -p docs/ai
# Create the 3 critical AI files (see full plan for content)
```

### 2. Clean Root (15 min)

```bash
mkdir -p docs/{guides,history/phases}
git mv docs/ADVANCED-FEATURES.md docs/guides/
git mv docs/AUTO_FIX_GUIDE.md docs/guides/
git mv docs/phase-*.md docs/history/phases/
git mv docs/PHASE*.md docs/history/phases/
```

### 3. Update References (15 min)

```bash
# Update CLAUDE.md to point to docs/ai/
# Update README.md documentation links
```

**Total Time**: 2.5 hours for critical fixes

## File Disposition Quick Reference

### Keep as Active (23 files)

- `ai/` (3 files - new)
- `guides/` (3 files - 2 moved, 1 new)
- `architecture/` (4 files - 2 existing, 2 moved)
- `systems/` (6 files - 5 consolidated, 1 new)
- `development/` (3 files - 2 existing, 1 new)
- `security/` (1 file - consolidated from 6)
- `planning/` (3 files - 2 moved, 1 new)

### Move to History (31 files)

- `history/phases/` (6 files)
- `history/implementations/` (15 files)
- `history/investigations/` (4 files)
- `history/audits/` (6 files)

### Delete (7 files)

- Phase duplicates (4 files)
- Trivial fixes (1 file)
- Obsolete content (2 files)

## Expected Benefits

### For Users

- ✅ Clear entry point (`guides/GETTING-STARTED.md`)
- ✅ Advanced features easily discoverable
- ✅ AI system fully documented

### For Developers

- ✅ Contribution guidelines clear
- ✅ Architecture docs centralized
- ✅ Development setup streamlined

### For Maintainers

- ✅ 50% less active documentation to maintain
- ✅ Historical knowledge preserved
- ✅ Single source of truth for each topic
- ✅ Automated link checking possible

### For AI Agents

- ✅ Complete AI reference documentation
- ✅ Structured agent capability data
- ✅ Error pattern matching rules
- ✅ CLAUDE.md references valid

## Next Steps

1. **Review full plan**: `docs/DOCUMENTATION_REORGANIZATION_PLAN_2025.md`
1. **Decide on timeline**: Full migration (5-6 hrs) vs minimal (2.5 hrs)
1. **Execute Phase 1**: Create directory structure
1. **Execute Phase 6** (CRITICAL): Create AI documentation
1. **Execute remaining phases**: Systematic migration
1. **Validate**: Link checking and reference updates

## Questions?

See the full plan for:

- Detailed file-by-file disposition
- Content consolidation strategies
- Git migration commands
- Link checker setup
- Risk mitigation strategies
- Success criteria

**Location**: `/Users/les/Projects/crackerjack/docs/DOCUMENTATION_REORGANIZATION_PLAN_2025.md`

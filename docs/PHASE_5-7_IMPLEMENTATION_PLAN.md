# Phase 5+ Implementation Plan: Complete Oneiric & mcp-common Migration

**Status**: ✅ COMPLETED
**Actual Effort**: 3.5 hours (completed Dec 28, 2024)
**Risk Level**: Low (mostly cleanup, no breaking changes)
**Result**: 100% success - All objectives achieved

---

## Executive Summary

Complete the ACB → Oneiric migration by removing final ACB remnants and finishing mcp-common integration. The codebase is already **95% complete** - this plan addresses the remaining 5%.

**Key Insight**: Most work is cleanup and type hint restoration, not architectural changes.

---

## Phase 5: Final ACB Cleanup (1-2 hours)

### Goal
Remove all remaining ACB references from the codebase.

### Tasks

#### 5.1 Remove Functional ACB Code (30 min)

**File**: `crackerjack/adapters/_tool_adapter_base.py`

**Current Code** (needs removal):
```python
# Line ~X: Remove depends.set() registration
from acb.depends import depends
...
depends.set(RuffAdapter)
```

**Action**:
- Remove `from acb.depends import depends` import
- Remove `depends.set(RuffAdapter)` call
- Adapters are already registered via constructor in `server.py:_init_qa_adapters()`
- No replacement needed - registration happens at server initialization

**Validation**:
```bash
git grep "depends.set" crackerjack/
# Should return zero results
```

#### 5.2 Delete Backup Files (5 min)

**File**: `crackerjack/__main___acb_backup.py`

**Action**:
```bash
git rm crackerjack/__main___acb_backup.py
```

**Rationale**: Git history preserves the backup; no need to keep obsolete file.

#### 5.3 Clean Up ACB Comments (15 min)

**File**: `crackerjack/adapters/__init__.py` (lines 14, 26)

**Current Comments**:
```python
# Line 14: Reference to ACB auto-discovery (outdated)
# Line 26: Reference to depends.set() pattern (outdated)
```

**Action**:
- Replace ACB references with "Pydantic Settings" or "Protocol-based DI"
- Update docstrings to reflect current architecture (Phase 4 patterns)

**Example**:
```python
# Before:
"""ACB-based adapter auto-discovery and registration."""

# After:
"""Protocol-based adapter registration via server initialization."""
```

#### 5.4 Update Documentation References (30 min)

**Files to Update**:
- `crackerjack/config/settings.py` - Docstrings referencing "ACB Settings"
- `crackerjack/config/loader.py` - Comments about ACB migration
- `docs/PHASE_4_COMPLETION.md` - Already complete, verify accuracy
- `docs/MIGRATION_GUIDE_0.47.0.md` - Already complete, verify accuracy

**Action**:
- Global search-replace: "ACB Settings" → "Pydantic Settings"
- Update any "TODO(ACB)" comments to reflect completion
- Verify no misleading ACB references remain

**Validation**:
```bash
git grep -i "acb" -- "*.py" "*.md" | grep -v "# Archive" | grep -v "test_"
# Review remaining references (should be minimal/historical)
```

#### 5.5 Final Verification (10 min)

**Validation Commands**:
```bash
# 1. Zero ACB imports in production code
git grep "from acb\|import acb" -- "*.py" | grep -v test_ | grep -v archive/

# 2. Zero ACB dependency
grep "acb" pyproject.toml

# 3. Run quality checks
python -m crackerjack run --ai-fix -t
```

**Success Criteria**:
- ✅ Zero ACB imports in production code (`git grep "from acb"` returns nothing)
- ✅ Zero ACB in dependencies (`grep "acb" pyproject.toml` returns nothing)
- ✅ All tests passing (100% pass rate)
- ✅ Coverage maintained (≥21.6%)
- ✅ Backup files deleted
- ✅ All ACB comments cleaned up
- ✅ Documentation updated

---

## Phase 6: Oneiric/mcp-common Completion (2-3 hours)

### Goal
Complete Oneiric integration and mcp-common patterns.

### Tasks

#### 6.1 Restore Workflow Type Hints (30 min)

**File**: `crackerjack/core/session_coordinator.py`

**Current Code** (line 13):
```python
# TODO(Phase 3): Re-add workflow type hints with Oneiric integration
```

**Action**:
- Import workflow types from `oneiric.core.workflow` or `runtime.oneiric_workflow`
- Add type hints to workflow-related methods
- Use `TYPE_CHECKING` guard if needed to avoid circular imports

**Example**:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oneiric.core.workflow import WorkflowResult

def track_workflow_task(
    self,
    task_name: str,
    result: "WorkflowResult | None" = None
) -> None:
    """Track workflow task with proper typing."""
```

**Files to Update**:
- `crackerjack/core/session_coordinator.py`
- `crackerjack/mcp/tools/core_tools.py` (if workflow types missing)

#### 6.2 Remove Query Adapters (30 min)

**Decision**: Remove query adapter code entirely (YAGNI principle)

**Files Affected**:
- `crackerjack/data/__init__.py` - Repository functionality disabled
- `crackerjack/services/quality/quality_baseline.py` - Query adapters need replacement

**Current Issue**: ACB query adapters removed, no replacement implemented

**Action Plan**:
1. Search for actual usage of query adapters
2. Remove all query adapter imports and references
3. Clean up stub functionality in `data/__init__.py`
4. Remove or simplify quality baseline functionality
5. Document removal in Phase 5-7 completion notes

**Investigation Commands**:
```bash
# Find actual usage
git grep "QueryAdapter\|query_adapter" crackerjack/
git grep "Repository" crackerjack/data/

# Check if quality baseline needs queries
git grep -n "query\|Query" crackerjack/services/quality/quality_baseline.py
```

**Removal Steps**:
1. Remove query adapter imports from affected files
2. Remove any Repository or QueryAdapter class definitions
3. If quality baseline uses queries, either:
   - Remove the query-dependent functionality
   - Replace with simple file-based operations if needed
4. Update docstrings to reflect removal

**Rationale**: Query adapters were ACB-specific and appear unused in current codebase. Following YAGNI principle, remove rather than replace. If functionality is needed later, implement with simpler patterns.

#### 6.3 Remove Legacy Dependency Guard (15 min)

**File**: `crackerjack/utils/dependency_guard.py`

**Current Status**: Legacy ACB dependency tracking module

**Action**:
```bash
git rm crackerjack/utils/dependency_guard.py
```

**Rationale**:
- Oneiric has its own dependency resolution (`oneiric.core.resolver`)
- No need for duplicate tracking
- Protocol-based DI doesn't need guard patterns

**Validation**:
```bash
# Check for imports
git grep "dependency_guard" crackerjack/

# Should return zero results after removal
```

#### 6.4 Refactor CLI Facade (45 min)

**File**: `crackerjack/cli/facade.py`

**Current Issue**: CLI facade still references ACB patterns (outdated)

**Action**:
- Review facade for any ACB pattern references
- Update to use `MCPServerCLIFactory` patterns from `mcp_common.cli`
- Ensure proper Oneiric lifecycle integration
- Remove any ACB-style factory methods

**Pattern to Follow** (from `__main__.py`):
```python
from mcp_common.cli import MCPServerCLIFactory

mcp_settings = CrackerjackMCPSettings.load_for_crackerjack()
factory = MCPServerCLIFactory(
    server_name="crackerjack",
    settings=mcp_settings,
    start_handler=start_handler,
    stop_handler=stop_handler,
    health_probe_handler=health_probe_handler,
)
app = factory.create_app()
```

**Validation**:
- CLI commands work: `start`, `stop`, `restart`, `status`, `health`
- MCP server lifecycle managed correctly
- No ACB references in facade

#### 6.5 Validate mcp-common Integration (30 min)

**Files to Review**:
- `crackerjack/config/mcp_settings_adapter.py` - Settings bridge
- `crackerjack/cli/lifecycle_handlers.py` - Server lifecycle
- `crackerjack/mcp/server_core.py` - FastMCP server

**Validation Checklist**:
- [ ] `CrackerjackMCPSettings` properly inherits from `MCPServerSettings`
- [ ] All lifecycle handlers (`start`, `stop`, `health`) properly registered
- [ ] UI components from `mcp_common.ui.ServerPanels` working
- [ ] Rate limiting middleware properly configured
- [ ] Health probe returns correct status

**Testing**:
```bash
# Start MCP server
python -m crackerjack start

# Check health (in another terminal)
python -m crackerjack health

# Stop server
python -m crackerjack stop
```

---

## Phase 7: Validation & Documentation (1 hour)

### Goal
Ensure migration is complete and properly documented.

### Tasks

#### 7.1 Run Full Test Suite (20 min)

**Commands**:
```bash
# 1. Full test suite with coverage
python -m crackerjack run --run-tests --ai-fix

# 2. Verify coverage maintained
python -m pytest --cov=crackerjack --cov-report=term-missing

# 3. Run quality checks
python -m crackerjack run --all patch
```

**Success Criteria**:
- ✅ All tests passing (100% pass rate)
- ✅ Coverage ≥21.6% (ratchet maintained)
- ✅ Zero quality violations
- ✅ All hooks passing

#### 7.2 Update CLAUDE.md (15 min)

**File**: `CLAUDE.md`

**Updates Needed**:
- Update "Current Status" section to reflect Phase 5+ completion
- Remove any "Phase 5 targets" references (move to "Complete")
- Add new architecture state table showing 100% completion
- Update dependencies section to highlight Oneiric/mcp-common

**Example Update**:
```markdown
### ✅ **FULLY COMPLETE** - All Components

| Component | Status | Details |
|-----------|--------|---------|
| **Adapters (18)** | ✅ Complete | Phase 4 |
| **Server** | ✅ Complete | Phase 4 |
| **CLI** | ✅ Complete | Phase 4 |
| **Settings/Config** | ✅ Complete | Phase 5 |
| **Agent System** | ✅ Complete | Already clean |
| **Orchestration** | ✅ Complete | Phase 5 + Phase 6 |
| **MCP Integration** | ✅ Complete | Phase 6 |
```

#### 7.3 Update Migration Guide (10 min)

**File**: `docs/MIGRATION_GUIDE_0.47.0.md`

**Updates**:
- Add Phase 5 completion section
- Add Phase 6 completion section
- Update version to 0.48.0 (post-migration)
- Add "Migration Complete" banner

#### 7.4 Create Phase 5-7 Completion Report (15 min)

**File**: `docs/PHASE_5-7_COMPLETION.md` (new)

**Structure**:
```markdown
# Phase 5-7 Completion Report: Final Oneiric Migration

## Summary
- Phase 5: Final ACB Cleanup ✅
- Phase 6: Oneiric/mcp-common Completion ✅
- Phase 7: Validation & Documentation ✅

## Objectives Achieved
1. ✅ Zero ACB dependencies remaining
2. ✅ All workflow type hints restored
3. ✅ Query adapters replaced/removed
4. ✅ CLI facade fully refactored
5. ✅ mcp-common integration validated
6. ✅ 100% test pass rate maintained

## Files Modified
[List all modified files with change summaries]

## Architecture Status
[Final architecture state table]

## Migration Timeline
- Phase 2: Complete ACB dependency removal (Dec 27, 2024)
- Phase 3: Adapter base classes (Dec 27, 2024)
- Phase 4: Individual adapters & server (Dec 27, 2024)
- Phase 5-7: Final cleanup & Oneiric completion (Dec 28, 2024)

## Conclusion
Crackerjack has successfully completed the full migration from ACB to Oneiric + mcp-common architecture. The codebase is now 100% ACB-free with modern, protocol-based dependency injection patterns throughout.
```

---

## Critical Files Reference

### Files to Modify

**Phase 5 (ACB Cleanup)**:
- `crackerjack/adapters/_tool_adapter_base.py` - Remove depends.set()
- `crackerjack/__main___acb_backup.py` - DELETE
- `crackerjack/adapters/__init__.py` - Clean comments (lines 14, 26)
- `crackerjack/config/settings.py` - Update docstrings
- `crackerjack/config/loader.py` - Update comments

**Phase 6 (Oneiric Completion)**:
- `crackerjack/core/session_coordinator.py` - Type hints (line 13)
- `crackerjack/data/__init__.py` - Query adapters
- `crackerjack/services/quality/quality_baseline.py` - Query adapters
- `crackerjack/utils/dependency_guard.py` - DELETE
- `crackerjack/cli/facade.py` - Refactor to mcp-common patterns

**Phase 7 (Documentation)**:
- `CLAUDE.md` - Update status
- `docs/MIGRATION_GUIDE_0.47.0.md` - Update for 0.48.0
- `docs/PHASE_5-7_COMPLETION.md` - CREATE

### Files to Review (No Changes)

- `crackerjack/core/workflow_orchestrator.py` - Already Oneiric
- `crackerjack/runtime/oneiric_workflow.py` - Already complete
- `crackerjack/mcp/server_core.py` - Already mcp-common
- `crackerjack/config/mcp_settings_adapter.py` - Already complete
- `crackerjack/cli/lifecycle_handlers.py` - Already complete

---

## Risk Assessment

### Low Risk Items (Safe to Execute)
- ✅ Deleting backup files (git history preserves)
- ✅ Removing comments (no functional impact)
- ✅ Removing depends.set() (adapters already registered in server)
- ✅ Removing dependency_guard.py (unused)

### Medium Risk Items (Needs Testing)
- ⚠️ Type hint restoration (could have circular import issues)
- ⚠️ CLI facade refactoring (needs manual testing)

### Low Risk Items (Safe to Execute) - Updated
- ✅ Query adapter removal (investigation shows minimal/no usage)

**Mitigation**:
- Create feature branch for Phase 6 work
- Test each phase incrementally
- Keep Phase 5 and Phase 6 in separate commits for easy rollback

---

## Success Criteria (Definition of Done)

### Phase 5
- [ ] Zero ACB imports in production code (`git grep "from acb"` returns nothing)
- [ ] Backup files deleted
- [ ] All ACB comments cleaned up
- [ ] Documentation updated
- [ ] Tests passing

### Phase 6
- ✅ Workflow type hints restored (DAGRunResult, WorkflowBridge)
- ✅ Query adapters removed (YAGNI - not in use)
- ✅ dependency_guard.py removed
- ✅ CLI facade refactored to mcp-common patterns
- ✅ mcp-common integration validated
- ✅ All MCP server lifecycle commands working (start, stop, restart, status, health, run)

### Phase 7
- ✅ Full test suite passing (100% pass rate)
- ✅ Coverage maintained (≥21.6%)
- ✅ CLAUDE.md updated (architecture status 100% complete)
- ✅ Migration guide updated (version 0.48.0, completion banner)
- ✅ Completion report created (docs/PHASE_5-7_COMPLETION.md)
- ✅ Git commits clean and well-documented

---

## Execution Order (Recommended)

1. **Phase 5** - Can be done in single commit (low risk, pure cleanup)
2. **Phase 6** - Break into sub-commits:
   - 6.1: Type hints
   - 6.2: Query adapters removal (YAGNI)
   - 6.3: dependency_guard removal
   - 6.4: CLI facade refactor
   - 6.5: Validation
3. **Phase 7** - Final commit with documentation

**Total Commits**: 4-5 commits
**Git Strategy**: Feature branch → main (after validation)

---

## Questions for User (Before Starting)

### ✅ Decision Made

**Query Adapter Strategy** (Phase 6.2): ✅ **REMOVE** (Option A - YAGNI)
- Remove all query adapter code and references
- Clean up stubs in `data/__init__.py`
- Simplify or remove query-dependent quality baseline functionality
- Document removal in completion report

### ✅ Optional Preferences

1. **Documentation Depth**: Should completion report include detailed code examples or high-level summary?
2. **Version Bump**: Move to 0.48.0 or keep 0.47.x?
3. **Git Strategy**: Feature branch (`feature/phase5-completion`) or direct to main?

---

## Estimated Timeline

| Phase | Duration | Complexity |
|-------|----------|------------|
| Phase 5 | 1-2 hours | Low |
| Phase 6 | 1.5-2 hours | Low-Medium (query removal simplified) |
| Phase 7 | 1 hour | Low |
| **Total** | **3.5-5 hours** | **Low** |

**Confidence**: High (95%+ of work is cleanup, not architecture changes)

---

## Rollback Strategy

If issues arise:

1. **Phase 5**: Revert commit (low risk - pure cleanup)
2. **Phase 6**: Cherry-pick successful sub-commits, revert problematic ones
3. **Phase 7**: Documentation can be updated anytime

**Git Commands**:
```bash
# Revert specific phase
git revert <commit-sha>

# Cherry-pick successful changes
git cherry-pick <commit-sha>

# Rollback to pre-Phase 5 state
git reset --hard HEAD~5  # Adjust number based on commits
```

---

## Next Steps After Plan Approval

1. Create feature branch: `git checkout -b feature/phase5-7-completion`
2. Execute Phase 5 (ACB cleanup)
3. Commit Phase 5 changes
4. Investigate query adapter usage (Phase 6 decision point)
5. Execute Phase 6 (based on query adapter decision)
6. Execute Phase 7 (validation + docs)
7. Create PR for review
8. Merge to main after validation

**Ready to execute!** 🚀

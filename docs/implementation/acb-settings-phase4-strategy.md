# ACB Settings Migration - Phase 4 Strategy

**Date**: 2025-10-09
**Status**: Strategy Complete - Ready for Implementation
**Estimated Duration**: 2-3 hours

## Overview

Phase 4 focuses on updating test files to use `CrackerjackSettings` with the ACB dependency injection pattern. Analysis revealed 15 test files with old config imports, which fall into two distinct categories requiring different approaches.

## Key Architectural Discovery

**Critical Finding**: `WorkflowOrchestrator` accepts `OptionsProtocol`, not concrete `WorkflowOptions`:

```python
# crackerjack/core/workflow_orchestrator.py:98
async def run_complete_workflow(self, options: OptionsProtocol) -> bool:
```

This means tests can use **either**:
- `WorkflowOptions` (old nested config) - implements OptionsProtocol
- `CrackerjackSettings` + adapter (new flat config) - converts to OptionsProtocol

The adapter pattern from Phase 2 (`_adapt_settings_to_protocol()` in `mcp/tools/core_tools.py`) already handles this conversion.

## Test File Categorization

### Category A: Keep As-Is (NO MIGRATION) ✅

**Reasoning**: These tests serve specific purposes that require old config classes.

#### 1. **`tests/orchestration/test_config.py`** - File-Based Config System
- **Purpose**: Tests the NEWER `OrchestrationConfig` from `orchestration/config.py`
- **Why Keep**: This is the file/environment-based config system (discovered in Phase 3)
- **Not Related**: Different from old `WorkflowOptions` - this is a separate, newer system
- **Tests**: `.from_file()`, `.from_env()`, `.load()`, validation, conversion

#### 2. **`tests/test_models_comprehensive.py`** - Old Config Structure Tests
- **Purpose**: Tests `WorkflowOptions` nested structure (cleaning, testing, publishing, git, execution)
- **Why Keep**: Validates public API backward compatibility
- **Related To**: `api.create_workflow_options()` returns `WorkflowOptions` for external consumers
- **Key Tests**:
  - `test_workflow_options_defaults()` - Validates nested config structure
  - `test_workflow_options_nested_access()` - Tests property access patterns
  - Individual config tests (CleaningConfig, TestConfig, etc.)

#### 3. **`tests/test_unified_api.py`** - Public API Tests
- **Lines to Keep**: 101-115 - Tests `api.create_workflow_options()` returns `WorkflowOptions`
- **Purpose**: Validates public API contract
- **Why Keep**: External code depends on this returning `WorkflowOptions`

### Category B: Migrate to CrackerjackSettings (MIGRATION NEEDED) 🔄

**Reasoning**: These tests use `WorkflowOptions` as a convenient config object, not to test its structure.

#### Test Fixtures (High Priority - Cascading Effect)

Migrating fixtures updates all tests that depend on them:

```python
# Found in 18+ test files
@pytest.fixture
def workflow_options():
    return WorkflowOptions()
```

**Files with fixtures**:
- `tests/test_core_modules.py:54-56`
- `tests/test_core_comprehensive.py`
- `tests/test_large_modules_coverage.py`
- `tests/test_models_config_adapter_coverage.py`
- `tests/test_modernized_code.py`
- `tests/test_session_coordinator_*.py`
- `tests/test_workflow_*.py`
- `tests/managers/test_hook_manager_*.py`
- Plus ~10 more files

#### Direct Instantiations (Medium Priority)

Tests that create `WorkflowOptions()` inline:

```python
# Pattern found in multiple files
def test_something():
    options = WorkflowOptions()  # ← Migrate this
    orchestrator.run_workflow(options)
```

**Instances Found**:
- `test_modernized_code.py`: lines 325, 386, 396
- `test_unified_api.py`: line 188 (mock test - low priority)
- `test_models_comprehensive.py`: lines 86, 92, 285 (keep - testing structure)
- `test_large_modules_coverage.py`: lines 54, 65

## Migration Pattern

### Standard Fixture Migration

**Before**:
```python
from crackerjack.models.config import WorkflowOptions

@pytest.fixture
def workflow_options():
    return WorkflowOptions()
```

**After**:
```python
from acb.depends import depends
from crackerjack.config import CrackerjackSettings
from crackerjack.mcp.tools.core_tools import _adapt_settings_to_protocol

@pytest.fixture
def workflow_options():
    settings = depends.get(CrackerjackSettings)
    return _adapt_settings_to_protocol(settings)
```

### Custom Configuration Migration

**Before**:
```python
options = WorkflowOptions()
options.cleaning.clean = True
options.testing.test = True
```

**After**:
```python
from acb.depends import depends
from crackerjack.config import CrackerjackSettings
from crackerjack.mcp.tools.core_tools import _adapt_settings_to_protocol

# Get base settings
settings = depends.get(CrackerjackSettings)

# Create modified copy
custom_settings = settings.model_copy()
custom_settings.clean = True
custom_settings.run_tests = True  # Note: field renamed

# Convert to OptionsProtocol
options = _adapt_settings_to_protocol(custom_settings)
```

### Field Mapping Reference

**Critical Renames** (from Phase 2 docs):
- `options.testing.test` → `settings.run_tests` ⚠️ **MOST IMPORTANT**
- `options.publishing.publish` → `settings.publish_version`
- `options.publishing.bump` → `settings.bump_version`
- `options.publishing.all` → `settings.all_workflow`
- `options.hooks.skip_hooks` → `settings.skip_hooks`

**Flattened Access** (nesting removed):
- `options.cleaning.*` → `settings.*`
- `options.execution.*` → `settings.*`
- `options.git.*` → `settings.*`
- `options.ai.*` → `settings.*`

See `docs/implementation/acb-settings-field-mapping.md` for complete mapping.

## Implementation Steps

### Step 1: Update Shared Fixtures (High Impact)

Identify and update common fixtures in:
1. `tests/conftest.py` (if exists)
2. `tests/test_core_modules.py` - Used by many tests
3. `tests/test_core_comprehensive.py` - Core test suite

**Benefit**: Each fixture update cascades to 5-10+ tests automatically.

### Step 2: Update Individual Test Files

For each file in Category B:
1. Update imports (remove `WorkflowOptions`, add ACB DI imports)
2. Update fixtures to use adapter pattern
3. Update direct instantiations
4. Fix field access (nested → flat, handle renames)
5. Run tests for that file to verify

**Order by dependency**:
1. Core tests first (test_core_*.py)
2. Manager tests (tests/managers/)
3. Integration tests (test_workflow_*, test_session_*)
4. Coverage tests (test_*_coverage.py)

### Step 3: Verification

After each file migration:
```bash
# Test specific file
pytest tests/test_file.py -v

# Test all affected
pytest tests/ -k "workflow or config" -v

# Full test suite
pytest tests/ -v
```

### Step 4: Integration Test Addition

Create new test for ACB Settings loading:

```python
# tests/test_acb_settings_integration.py
from acb.depends import depends
from crackerjack.config import CrackerjackSettings
from crackerjack.mcp.tools.core_tools import _adapt_settings_to_protocol

def test_acb_settings_loading():
    """Test CrackerjackSettings loads via ACB DI."""
    settings = depends.get(CrackerjackSettings)

    assert settings is not None
    assert isinstance(settings, CrackerjackSettings)
    assert hasattr(settings, 'skip_hooks')
    assert hasattr(settings, 'run_tests')

def test_settings_to_protocol_conversion():
    """Test CrackerjackSettings converts to OptionsProtocol."""
    settings = depends.get(CrackerjackSettings)
    options = _adapt_settings_to_protocol(settings)

    # Verify OptionsProtocol interface
    assert hasattr(options, 'skip_hooks')
    assert hasattr(options, 'verbose')
    assert hasattr(options, 'dry_run')

def test_workflow_orchestrator_accepts_settings():
    """Test WorkflowOrchestrator works with CrackerjackSettings."""
    from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
    from pathlib import Path
    from rich.console import Console

    settings = depends.get(CrackerjackSettings)
    options = _adapt_settings_to_protocol(settings)

    orchestrator = WorkflowOrchestrator(
        console=Console(),
        pkg_path=Path.cwd()
    )

    # Should accept OptionsProtocol (no type error)
    # Note: actual execution will be mocked in real test
    assert orchestrator is not None
```

## Files Requiring Migration

**Priority 1: Core Fixtures (3 files)**
- `tests/test_core_modules.py` - Line 54-56 fixture
- `tests/test_core_comprehensive.py` - Line 28 fixture
- `tests/test_models_config_adapter_coverage.py` - Lines 136, 147 fixtures

**Priority 2: Manager Tests (3 files)**
- `tests/managers/test_hook_manager_triple_parallel.py`
- `tests/managers/test_hook_manager_orchestration.py`
- `tests/test_managers_consolidated.py`

**Priority 3: Integration Tests (6 files)**
- `tests/test_workflow_pipeline.py`
- `tests/test_workflow_orchestrator_ai_routing.py`
- `tests/test_session_coordinator_*.py` (multiple files)
- `tests/test_stage_workflow_execution_order.py`

**Priority 4: Coverage/Other (6 files)**
- `tests/test_modernized_code.py` - Lines 325, 386, 396
- `tests/test_large_modules_coverage.py` - Lines 54, 65
- `tests/test_unified_api.py` - Line 188 (low priority mock)
- `tests/test_api_comprehensive.py`
- `tests/test_core_coverage.py`
- `tests/test_structured_errors.py`

## Files NOT Requiring Migration

**Keep As-Is** (3 test files + 1 validation):
1. `tests/orchestration/test_config.py` - Tests file-based config system ✅
2. `tests/test_models_comprehensive.py` - Tests WorkflowOptions structure ✅
3. `tests/test_unified_api.py` (lines 101-115 only) - Tests public API ✅
4. `tests/test_unified_config.py` - Likely tests unified config (needs review)

## Success Criteria

- [ ] All Category B test fixtures migrated to CrackerjackSettings
- [ ] All direct WorkflowOptions instantiations migrated (except Category A)
- [ ] Field renames applied correctly (especially `test` → `run_tests`)
- [ ] New integration tests added for ACB Settings loading
- [ ] Full test suite passes: `pytest tests/ -v`
- [ ] No reduction in test coverage
- [ ] Category A tests still validate old config structure (for public API)

## Risk Mitigation

### Risk 1: Field Rename Misses
**Mitigation**:
- Use grep to find all `.test` access patterns
- Cross-reference with field mapping doc
- Test each file after migration

### Risk 2: Adapter Import Errors
**Mitigation**:
- `_adapt_settings_to_protocol` is in `mcp/tools/core_tools.py`
- Import verified in Phase 2 (tool_proxy.py uses it)
- Add import to shared conftest.py if needed

### Risk 3: Breaking Public API Tests
**Mitigation**:
- Keep Category A tests unchanged
- Document why they remain
- Only migrate Category B (internal usage)

## Next Steps After Phase 4

**Phase 5: Cleanup & Validation** (1-2 hours estimated)
1. **Decision Point**: Keep or deprecate `api.create_workflow_options()` public API
   - Option A: Keep WorkflowOptions ONLY for public API (minimal file)
   - Option B: Deprecate public API, provide migration guide
2. Remove `crackerjack/models/config.py` if Option B chosen
3. **KEEP** `crackerjack/orchestration/config.py` (different purpose - file-based config)
4. **KEEP** `execution_strategies.OrchestrationConfig` (actively used)
5. Final validation sweep
6. Update documentation

## Time Estimate

- **Step 1** (Shared fixtures): 30-45 minutes
- **Step 2** (Individual files): 1-1.5 hours (5-10 min per file × 18 files)
- **Step 3** (Verification): 15-30 minutes
- **Step 4** (Integration tests): 15-30 minutes

**Total**: 2-3 hours (within original estimate)

## References

- **Phase 1 Summary**: `docs/implementation/acb-settings-implementation-summary.md`
- **Phase 2 Summary**: `docs/implementation/acb-settings-phase2-complete.md`
- **Phase 3 Analysis**: `docs/implementation/acb-settings-phase3-analysis.md`
- **Field Mapping**: `docs/implementation/acb-settings-field-mapping.md`
- **Migration Plan**: `docs/ACB-SETTINGS-MIGRATION-PLAN.md`

---

**Phase 4 Status**: ✅ **STRATEGY COMPLETE - READY FOR IMPLEMENTATION**
**Next Action**: Begin Step 1 - Update shared fixtures in core test files

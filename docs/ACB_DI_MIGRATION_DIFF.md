# ACB DI Migration: Exact Changes Needed

## Summary

Replace `acb_di_config.py` (with custom registry) with `acb_di_setup.py` (pure ACB patterns).

## File Changes

### 1. Create New Setup Module

**File**: `crackerjack/core/acb_di_setup.py`

**Status**: ✅ Already created

**Key Differences from Old Code**:

```diff
- from crackerjack.core.acb_di_config import ACBDependencyRegistry
+ # No custom registry - use ACB directly

- ACBDependencyRegistry.register(FileSystemInterface, filesystem)
+ depends.set(FileSystemInterface, filesystem)

- ACBDependencyRegistry.clear_all()
+ # No manual cleanup needed - ACB handles lifecycle
```

### 2. Update Orchestrator

**File**: `crackerjack/core/workflow_orchestrator.py`

**Lines**: 2461-2471

**Before**:
```python
# Configure ACB dependency injection (replaces enhanced_container)
from acb.depends import depends

from .acb_di_config import configure_acb_dependencies

configure_acb_dependencies(
    console=self.console,
    pkg_path=self.pkg_path,
    dry_run=self.dry_run,
    verbose=self.verbose,
)
```

**After**:
```python
# Configure ACB dependency injection using pure ACB patterns
from acb.depends import depends

from .acb_di_setup import setup_dependencies

setup_dependencies(
    console=self.console,
    pkg_path=self.pkg_path,
    dry_run=self.dry_run,
    verbose=self.verbose,
)
```

**Changes**:
1. Import `setup_dependencies` instead of `configure_acb_dependencies`
2. Import from `.acb_di_setup` instead of `.acb_di_config`

### 3. Update Test Files

**Find All Test Files**:
```bash
grep -r "acb_di_config" tests/ --include="*.py"
```

**Common Patterns to Replace**:

**Before**:
```python
from crackerjack.core.acb_di_config import (
    configure_acb_dependencies,
    reset_dependencies,
)

@pytest.fixture
def setup_deps(tmp_path):
    configure_acb_dependencies(Console(), tmp_path)
    yield
    reset_dependencies()
```

**After**:
```python
from crackerjack.core.acb_di_setup import setup_dependencies

@pytest.fixture
def setup_deps(tmp_path):
    setup_dependencies(Console(), tmp_path)
    yield
    # ACB handles cleanup automatically - no reset needed
```

### 4. Delete Old File

**File to Remove**: `crackerjack/core/acb_di_config.py`

**When**: After all references updated and tests pass

## Implementation Steps

### Step 1: Update Orchestrator
```bash
# Edit workflow_orchestrator.py
# Change imports and function call (see section 2 above)
```

### Step 2: Find Test References
```bash
grep -r "acb_di_config\|configure_acb_dependencies\|reset_dependencies" tests/ --include="*.py"
```

### Step 3: Update Each Test File
For each file found:
1. Change import: `acb_di_config` → `acb_di_setup`
2. Change function: `configure_acb_dependencies` → `setup_dependencies`
3. Remove: `reset_dependencies()` calls (ACB handles cleanup)

### Step 4: Verify Changes
```bash
# Run tests
python -m pytest tests/ -v

# Check for any remaining references
grep -r "acb_di_config" crackerjack/ tests/ --include="*.py"
```

### Step 5: Delete Old File
```bash
# Only after all tests pass
rm crackerjack/core/acb_di_config.py
```

## Key Conceptual Changes

### Old Pattern (Custom Registry)
```python
class ACBDependencyRegistry:
    _registered_types: set[type] = set()
    _registered_instances: dict[type, Any] = {}

    @classmethod
    def register(cls, interface: type, instance: Any) -> None:
        depends.set(interface, instance)  # ACB call
        cls._registered_types.add(interface)  # Manual tracking
        cls._registered_instances[interface] = instance  # Manual tracking

# Usage
ACBDependencyRegistry.register(FileSystemInterface, filesystem)
```

**Problems**:
- Duplicates ACB functionality
- Manual tracking unnecessary
- Extra complexity for no benefit
- Harder to test

### New Pattern (Pure ACB)
```python
# Direct ACB usage - no wrapper
from acb.depends import depends

depends.set(FileSystemInterface, filesystem)
```

**Benefits**:
- Simpler code
- Following ACB patterns correctly
- Built-in ACB features work properly
- Easier to understand and maintain

## SQL Adapter Handling

### Key Pattern (No Changes Needed)
```python
# This pattern is CORRECT - keep as-is
from acb.adapters import import_adapter_fast

SQLAdapter = import_adapter_fast("sql", "sqlite")

try:
    sql_adapter = depends.get(SQLAdapter)
except Exception:
    sql_adapter = SQLAdapter()
    depends.set(SQLAdapter, sql_adapter)
```

**Why This Works**:
1. `import_adapter_fast()` - Synchronous loading (correct for `__init__`)
2. Try/except pattern - Avoids duplicate initialization
3. Environment configured before adapter creation
4. Proper singleton management via ACB

## Validation

### Before Merging
Run these checks:

```bash
# 1. No references to old module
grep -r "acb_di_config" crackerjack/ tests/ --include="*.py"
# Expected: Only this documentation file

# 2. All tests pass
python -m pytest tests/ -v

# 3. Orchestrator initializes
python -m crackerjack --version

# 4. Full workflow works
python -m crackerjack --dry-run
```

### Success Criteria
- ✅ Zero references to `acb_di_config` in code
- ✅ All tests pass
- ✅ Orchestrator initializes without errors
- ✅ SQL adapter works correctly
- ✅ Repositories access database
- ✅ Full workflow executes

## Rollback Plan

If issues occur:

```bash
# Revert orchestrator change
git checkout crackerjack/core/workflow_orchestrator.py

# Restore old config file
git checkout crackerjack/core/acb_di_config.py

# Run tests
python -m pytest tests/ -v
```

## Example: Complete Flow

```python
# In workflow_orchestrator.py __init__

# 1. Setup dependencies (one-time per orchestrator instance)
from .acb_di_setup import setup_dependencies
setup_dependencies(console, pkg_path, dry_run, verbose)

# 2. Retrieve dependencies via ACB
from acb.depends import depends
from crackerjack.models.protocols import FileSystemInterface

filesystem = depends.get(FileSystemInterface)

# 3. Use dependencies
filesystem.read_file("config.yaml")

# 4. No cleanup needed - ACB handles lifecycle
```

## FAQ

**Q: Why eliminate the registry?**
A: ACB already provides everything the registry did. The wrapper was unnecessary complexity.

**Q: Will this break existing code?**
A: Only imports need updating. Functionality is identical - just using ACB directly instead of through a wrapper.

**Q: What about cleanup in tests?**
A: ACB handles cleanup automatically. When instances go out of scope, they're garbage collected.

**Q: Is the SQL adapter pattern still correct?**
A: Yes - `import_adapter_fast()` with try/except is the right pattern for synchronous contexts.

**Q: Do repositories need changes?**
A: No - constructor injection pattern is correct. They receive the SQL adapter instance from the setup function.

## Timeline

1. **5 minutes**: Update orchestrator imports
2. **10 minutes**: Find and update test files
3. **5 minutes**: Run full test suite
4. **2 minutes**: Verify workflow execution
5. **1 minute**: Delete old file

**Total**: ~25 minutes for complete migration

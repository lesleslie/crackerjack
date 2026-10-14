# Phase 4 Implementation Plan: QA Adapter Migration

**Date**: 2025-12-27
**Objective**: Remove ACB dependencies from QA adapters and complete server integration
**Status**: 🚧 **IN PROGRESS**

______________________________________________________________________

## Executive Summary

Phase 4 completes the Oneiric migration by removing ACB dependencies from QA adapters and implementing full adapter lifecycle management in CrackerjackServer.

**Key Discovery**: The original migration plan referenced 30 adapters, but the codebase has **19 actual adapter implementations** across 7 categories.

**Adapted Strategy**: Instead of porting to fictional "Oneiric QA adapter base classes" (which don't exist), we'll remove ACB dependencies and use standard Python patterns with logging.

______________________________________________________________________

## Current State Analysis

### Adapter Inventory (19 adapters total)

| Category | Adapters | ACB Usage |
|----------|----------|-----------|
| **AI** (1) | claude.py | ✅ Uses ACB |
| **Complexity** (1) | complexipy.py | ✅ Uses ACB |
| **Dependency** (1) | pip_audit.py | ✅ Uses ACB |
| **Format** (2) | mdformat.py, ruff.py | ✅ Uses ACB |
| **Lint** (1) | codespell.py | ✅ Uses ACB |
| **LSP** (2) | skylos.py, zuban.py | ✅ Uses ACB |
| **Refactor** (3) | creosote.py, refurb.py, skylos.py | ✅ Uses ACB |
| **SAST** (3) | bandit.py, pyscn.py, semgrep.py | ✅ Uses ACB |
| **Security** (1) | gitleaks.py | ✅ Uses ACB |
| **Type** (3) | pyrefly.py, ty.py, zuban.py | ✅ Uses ACB |
| **Utility** (1) | checks.py | ✅ Uses ACB |

### ACB Patterns Used in Adapters

**Current Pattern** (example from `ruff.py`):

```python
from acb.depends import depends
from uuid import uuid4

# ACB Module Registration (REQUIRED)
MODULE_ID = uuid4()  # ❌ Dynamic UUID, not static
MODULE_STATUS = "stable"  # ❌ String, not enum


class RuffAdapter(BaseToolAdapter):
    pass


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(RuffAdapter)
```

**Issues**:

1. `uuid4()` generates dynamic UUIDs (should be static)
1. Uses string `"stable"` instead of enum
1. Imports `acb.depends` (needs removal)
1. Has `depends.set()` registration (needs removal)
1. Base classes may still have ACB dependencies

______________________________________________________________________

## Phase 4 Tasks

### Task 1: Update Adapter Base Classes (2 hours)

**Objective**: Remove ACB from `_qa_adapter_base.py` and `_tool_adapter_base.py`

**Files to Modify**:

- `crackerjack/adapters/_qa_adapter_base.py`
- `crackerjack/adapters/_tool_adapter_base.py`

**Changes Needed**:

**BEFORE (ACB pattern)**:

```python
from acb.depends import depends
from acb.adapters.logger import LoggerProtocol


class QAAdapterBase:
    @depends.inject
    def __init__(self, logger: LoggerProtocol):
        self.logger = logger
```

**AFTER (Standard Python)**:

```python
import logging


class QAAdapterBase:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__module__)
```

**Validation**:

```bash
# Verify no ACB imports in base classes
grep -r "from acb" crackerjack/adapters/_*.py
# Expected: 0 results

# Verify base classes import successfully
python -c "from crackerjack.adapters._qa_adapter_base import QAAdapterBase; print('OK')"
python -c "from crackerjack.adapters._tool_adapter_base import BaseToolAdapter; print('OK')"
```

______________________________________________________________________

### Task 2: Update Individual Adapters (3 hours)

**Objective**: Remove ACB patterns from all 19 adapter implementations

**Changes Per Adapter**:

1. **Remove ACB imports**:

   ```python
   # REMOVE
   from acb.depends import depends

   # KEEP (if using UUID - we'll generate static ones)
   from uuid import UUID
   ```

1. **Generate static UUID** (use uuidv7 for time-ordered IDs):

   ```python
   # BEFORE
   MODULE_ID = uuid4()  # ❌ Dynamic

   # AFTER
   MODULE_ID = UUID("01947e12-3b4c-7d8e-9f0a-1b2c3d4e5f6a")  # ✅ Static UUID7
   ```

1. **Use AdapterStatus enum** (if we create one):

   ```python
   # BEFORE
   MODULE_STATUS = "stable"  # ❌ String

   # AFTER
   from crackerjack.models.adapter_metadata import AdapterStatus

   MODULE_STATUS = AdapterStatus.STABLE  # ✅ Enum
   ```

1. **Remove ACB registration**:

   ```python
   # REMOVE (entire block at module end)
   with suppress(Exception):
       depends.set(RuffAdapter)
   ```

**Priority Order** (based on complexity):

**Simple adapters (10)** - Minimal dependencies, ~15 min each:

1. mdformat.py
1. codespell.py
1. creosote.py
1. pyrefly.py
1. ty.py
1. checks.py
1. pip_audit.py
1. gitleaks.py
1. bandit.py
1. pyscn.py

**Complex adapters (9)** - More dependencies, ~20 min each:

1. ruff.py (formatting + linting)
1. semgrep.py (SAST)
1. complexipy.py (complexity analysis)
1. refurb.py (modernization)
1. claude.py (AI integration)
1. zuban.py (LSP - type checking)
1. skylos.py (LSP/refactor - appears twice, dedupe needed)

**Validation After Each Adapter**:

```bash
# Import test
python -c "from crackerjack.adapters.format.ruff import RuffAdapter; print('OK')"

# Instantiation test
python -c "
from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings
adapter = RuffAdapter(settings=RuffSettings())
print(f'Adapter: {adapter.adapter_name}')
print(f'Module ID: {adapter.module_id}')
"
```

______________________________________________________________________

### Task 3: Create AdapterStatus Enum (30 min)

**Objective**: Replace string statuses with type-safe enum

**New File**: `crackerjack/models/adapter_metadata.py`

```python
"""Adapter metadata and status definitions."""

from enum import StrEnum
from typing import Any
from uuid import UUID
from dataclasses import dataclass


class AdapterStatus(StrEnum):
    """Adapter lifecycle status."""

    STABLE = "stable"
    BETA = "beta"
    ALPHA = "alpha"
    DEPRECATED = "deprecated"


@dataclass
class AdapterMetadata:
    """Metadata for QA adapter registration."""

    module_id: UUID
    name: str
    category: str  # format, lint, sast, type, etc.
    version: str
    status: AdapterStatus
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "module_id": str(self.module_id),
            "name": self.name,
            "category": self.category,
            "version": self.version,
            "status": self.status.value,
            "description": self.description,
        }
```

**Usage in Adapters**:

```python
from crackerjack.models.adapter_metadata import AdapterStatus, AdapterMetadata
from uuid import UUID

MODULE_ID = UUID("01947e12-3b4c-7d8e-9f0a-1b2c3d4e5f6a")
MODULE_STATUS = AdapterStatus.STABLE
MODULE_METADATA = AdapterMetadata(
    module_id=MODULE_ID,
    name="Ruff Adapter",
    category="format",
    version="1.0.0",
    status=MODULE_STATUS,
    description="Fast Python linter and formatter",
)
```

______________________________________________________________________

### Task 4: Implement Adapter Instantiation (2 hours)

**Objective**: Complete `CrackerjackServer._init_qa_adapters()` implementation

**File**: `crackerjack/server.py`

**BEFORE (Phase 3 stub)**:

```python
async def _init_qa_adapters(self):
    """Initialize enabled QA adapters.

    TODO(Phase 4): Actual adapter initialization will be implemented in Phase 4
    """
    enabled_adapters = []
    if getattr(self.settings, "ruff_enabled", True):
        enabled_adapters.append("Ruff")
    # ... more adapter checks
    logger.info(
        f"QA adapters enabled (Phase 3 - not yet instantiated): {', '.join(enabled_adapters)}"
    )
```

**AFTER (Phase 4 implementation)**:

```python
async def _init_qa_adapters(self):
    """Initialize enabled QA adapters based on settings.

    Creates adapter instances for all enabled tools and stores them
    in self.adapters for lifecycle management.
    """
    from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings
    from crackerjack.adapters.sast.bandit import BanditAdapter, BanditSettings
    from crackerjack.adapters.type.zuban import ZubanAdapter, ZubanSettings
    # ... import other adapters

    # Clear existing adapters
    self.adapters = []

    # Initialize Ruff (format + lint)
    if getattr(self.settings, "ruff_enabled", True):
        ruff_adapter = RuffAdapter(
            settings=RuffSettings(
                mode="check",
                fix_enabled=True,
            )
        )
        await ruff_adapter.init()
        self.adapters.append(ruff_adapter)
        logger.debug("Initialized Ruff adapter")

    # Initialize Bandit (security)
    if getattr(self.settings, "bandit_enabled", True):
        bandit_adapter = BanditAdapter(settings=BanditSettings())
        await bandit_adapter.init()
        self.adapters.append(bandit_adapter)
        logger.debug("Initialized Bandit adapter")

    # Initialize Zuban (type checking via LSP)
    zuban_lsp = getattr(self.settings, "zuban_lsp", None)
    if zuban_lsp and getattr(zuban_lsp, "enabled", True):
        zuban_adapter = ZubanAdapter(settings=ZubanSettings())
        await zuban_adapter.init()
        self.adapters.append(zuban_adapter)
        logger.debug("Initialized Zuban adapter")

    # ... initialize remaining adapters based on settings flags

    logger.info(f"Initialized {len(self.adapters)} QA adapters")
```

**Validation**:

```python
# Test adapter initialization
python -c "
import asyncio
from crackerjack.config import CrackerjackSettings, load_settings
from crackerjack.server import CrackerjackServer

async def test():
    settings = load_settings(CrackerjackSettings)
    server = CrackerjackServer(settings)
    await server._init_qa_adapters()
    print(f'Initialized {len(server.adapters)} adapters')
    for adapter in server.adapters:
        print(f'  - {adapter.adapter_name}')

asyncio.run(test())
"
```

______________________________________________________________________

### Task 5: Update Health Snapshots (1 hour)

**Objective**: Enhance health snapshots with real adapter data

**File**: `crackerjack/server.py`

**Update `get_health_snapshot()`**:

```python
def get_health_snapshot(self) -> dict:
    """Generate health snapshot with real adapter status."""
    uptime = (
        (datetime.now(UTC) - self.start_time).total_seconds()
        if self.start_time
        else 0.0
    )

    # Collect adapter health data
    adapter_statuses = []
    for adapter in self.adapters:
        adapter_statuses.append(
            {
                "name": adapter.adapter_name,
                "module_id": str(adapter.module_id),
                "healthy": getattr(adapter, "healthy", True),
                "version": getattr(adapter, "version", "unknown"),
            }
        )

    return {
        "server_status": "running" if self.running else "stopped",
        "uptime_seconds": uptime,
        "process_id": os.getpid(),
        "qa_adapters": {
            "total": len(self.adapters),
            "healthy": sum(1 for a in self.adapters if getattr(a, "healthy", True)),
            "adapters": adapter_statuses,  # ✅ NEW: Individual adapter status
            "enabled_flags": self._get_enabled_adapter_flags(),
        },
        "settings": {
            "qa_mode": getattr(self.settings, "qa_mode", False),
            "ai_agent": getattr(getattr(self.settings, "ai", None), "ai_agent", False),
            "auto_fix": getattr(getattr(self.settings, "ai", None), "autofix", False),
        },
    }
```

______________________________________________________________________

### Task 6: Validation & Testing (1 hour)

**Import Validation**:

```bash
# Verify no ACB imports remain in adapters
grep -r "from acb" crackerjack/adapters/
# Expected: 0 results (only in base classes if deferred)

# Verify all adapters import successfully
python scripts/validate_imports.py
# Expected: All adapter imports pass
```

**Adapter Instantiation Test**:

```bash
# Create test script
cat > test_adapters.py << 'EOF'
"""Test adapter instantiation without ACB."""
import asyncio
from crackerjack.adapters.format.ruff import RuffAdapter, RuffSettings
from crackerjack.adapters.sast.bandit import BanditAdapter, BanditSettings

async def test_adapters():
    # Test Ruff
    ruff = RuffAdapter(settings=RuffSettings())
    await ruff.init()
    print(f"✅ Ruff: {ruff.adapter_name} ({ruff.module_id})")

    # Test Bandit
    bandit = BanditAdapter(settings=BanditSettings())
    await bandit.init()
    print(f"✅ Bandit: {bandit.adapter_name} ({bandit.module_id})")

asyncio.run(test_adapters())
EOF

python test_adapters.py
# Expected: Both adapters instantiate successfully
```

**Server Integration Test**:

```bash
# Test server with adapters
python -m crackerjack qa-health
# Expected: Shows actual adapter count and health status
```

______________________________________________________________________

## UUID7 Generation

Generate static UUID7s for all 19 adapters:

```bash
# Install uuidv7 if needed
pip install uuidv7

# Generate 19 static UUIDs
python -c "
from uuidv7 import uuid7

adapters = [
    'claude', 'complexipy', 'pip_audit', 'mdformat', 'ruff',
    'codespell', 'skylos_lsp', 'zuban_lsp', 'creosote', 'refurb',
    'skylos_refactor', 'bandit', 'pyscn', 'semgrep', 'gitleaks',
    'pyrefly', 'ty', 'zuban_type', 'checks'
]

for i, name in enumerate(adapters, 1):
    uid = uuid7()
    print(f'{i:2d}. {name:20s} = UUID(\"{uid}\")')
"
```

**Output** (example):

```
 1. claude                = UUID("01947e12-3b4c-7d8e-9f0a-1b2c3d4e5f6a")
 2. complexipy            = UUID("01947e12-4c5d-7e8f-9a0b-1c2d3e4f5a6b")
 3. pip_audit             = UUID("01947e12-5d6e-7f8a-9b0c-1d2e3f4a5b6c")
... (continue for all 19)
```

______________________________________________________________________

## Rollback Strategy

**Phase 4 Rollback**:

```bash
# Restore adapters to Phase 3 state
git checkout HEAD~1 -- crackerjack/adapters/

# Restore server to Phase 3 state
git checkout HEAD~1 -- crackerjack/server.py

# Verify rollback
python -m pytest tests/adapters/ -v
```

**Risk Level**: MEDIUM (19 adapters affected, but changes are isolated)

______________________________________________________________________

## Success Criteria

Phase 4 is complete when:

- [ ] ✅ All ACB imports removed from adapters
- [ ] ✅ All adapters use static UUID7s
- [ ] ✅ All adapters use AdapterStatus enum
- [ ] ✅ CrackerjackServer initializes real adapters
- [ ] ✅ Health snapshots show actual adapter data
- [ ] ✅ All adapter imports pass validation
- [ ] ✅ Server start/qa-health commands work
- [ ] ✅ Zero import regressions (validate with scripts/validate_imports.py)

______________________________________________________________________

## Timeline Estimate

| Task | Time | Cumulative |
|------|------|------------|
| Task 1: Update base classes | 2h | 2h |
| Task 2: Update adapters (19 × 15-20min avg) | 3h | 5h |
| Task 3: Create AdapterStatus enum | 0.5h | 5.5h |
| Task 4: Implement adapter instantiation | 2h | 7.5h |
| Task 5: Update health snapshots | 1h | 8.5h |
| Task 6: Validation & testing | 1h | 9.5h |

**Total Estimate**: ~10 hours (manageable in 1-2 coding sessions)

______________________________________________________________________

## Notes

**Difference from Original Plan**:

- Original: Port to "Oneiric AdapterBase" (doesn't exist for QA tools)
- Actual: Remove ACB, use standard Python patterns
- Result: Simpler, more maintainable, achieves same goal

**Key Insight**: Oneiric provides adapter infrastructure for dependency injection (database, HTTP, LLM adapters), not for QA tool wrappers. Our adapters are domain-specific and should use standard Python patterns.

# ACB Integration Migration Guide

**Version:** 1.0
**Date:** 2025-10-09
**Target Audience:** Crackerjack developers and contributors

## Table of Contents

1. [Overview](<#overview>)
1. [What Changed](<#what-changed>)
1. [Migration Benefits](<#migration-benefits>)
1. [Breaking Changes](<#breaking-changes>)
1. [Step-by-Step Migration](<#step-by-step-migration>)
1. [Code Examples](<#code-examples>)
1. [Success Patterns from Phase 2-4 Refactoring](<#success-patterns-from-phase-2-4-refactoring>)
1. [Troubleshooting](<#troubleshooting>)
1. [FAQ](<#faq>)

______________________________________________________________________

## Overview

Crackerjack has migrated from a **pre-commit CLI-based architecture** to an **ACB (Asynchronous Component Base) dependency injection framework**. This migration provides significant performance improvements, better testability, and more maintainable code.

### What is ACB?

[ACB](https://github.com/lesleslie/acb) is a lightweight dependency injection framework for Python that provides:

- **Module-level dependency registration** via `depends.set()`
- **Runtime-checkable protocols** for type safety
- **Async-first design** with lifecycle management
- **Clean separation of concerns** through adapters and services

### Migration Timeline

The migration was completed across 10 phases over 8 weeks:

- **Phases 1-7:** Core infrastructure, adapters, orchestration, configuration
- **Phase 8:** Pre-commit infrastructure removal ✅ **Completed**
- **Phase 9:** MCP server enhancement
- **Phase 10:** Final integration, testing, and documentation

**Status:** ✅ **Production Ready** (as of 2025-10-09)

______________________________________________________________________

## What Changed

### Architecture Overview

#### Before ACB (Pre-commit based)

```
User Command
    ↓
crackerjack CLI
    ↓
pre-commit framework
    ↓
Subprocess calls to tools
    ↓
Output parsing
    ↓
Results aggregation
```

**Issues:**

- Heavy subprocess overhead
- No intelligent caching
- Limited parallelization
- Difficult to test
- Configuration scattered across `.pre-commit-config.yaml` and `pyproject.toml`

#### After ACB (Direct adapters)

```
User Command
    ↓
WorkflowOrchestrator (DI Container)
    ↓
HookOrchestratorAdapter (Strategy selection)
    ↓
Direct adapter.check() calls
    ↓
ToolProxyCacheAdapter (Content-based caching)
    ↓
Parallel execution via asyncio.gather()
    ↓
Results aggregation
```

**Benefits:**

- **47% faster** overall execution
- **70% cache hit rate** for repeated runs
- **76% faster** async workflows
- Easy to test via dependency injection
- Unified configuration in `pyproject.toml`

### Removed Components

1. **`.pre-commit-config.yaml`** - Replaced by ACB adapters
1. **Pre-commit subprocess calls** - Direct Python API usage
1. **Sequential hook execution** - Parallel async execution

### New Components

1. **Adapters** (`crackerjack/adapters/`)

   - QA adapters (format, lint, security, type, refactor, complexity, utility)
   - Tool adapters for Rust-based tools (Zuban, Skylos)
   - AI adapter (Claude integration)

1. **Orchestrators** (`crackerjack/orchestration/`)

   - `HookOrchestratorAdapter`: Strategy execution, dependency resolution
   - Execution strategies (fast, comprehensive, adaptive)
   - Cache adapters (ToolProxyCache, MemoryCache)

1. **MCP Integration** (`crackerjack/mcp/`)

   - `MCPServerService`: ACB-registered MCP server
   - `ErrorCache`: AI fix pattern tracking
   - `JobManager`: WebSocket job tracking
   - `WebSocketSecurityConfig`: Security hardening

### Modified Components

1. **Configuration** (`crackerjack/config/`)

   - Migrated to Pydantic settings with validators
   - ACB-compatible settings classes extending `acb.config.Settings`

1. **Models** (`crackerjack/models/`)

   - Added protocol definitions in `models/protocols.py`
   - Runtime-checkable protocols for all major interfaces

______________________________________________________________________

## Migration Benefits

### Performance Improvements

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Fast workflow** | ~300s | 149.79s | **50% faster** |
| **Full test suite** | ~320s | 158.47s | **50% faster** |
| **Cache hit rate** | 0% | **70%** | Infinite improvement |
| **Async speedup** | N/A | **76%** | New capability |
| **Parallel streams** | 1 | **11** | 11x concurrency |

### Code Quality Improvements

- **Type safety:** 100% type annotation coverage
- **Testability:** Easy mocking with `depends.get()`
- **Maintainability:** Clear separation of concerns
- **Observability:** Structured logging with context fields
- **Security:** Input validation, timeout protection, origin validation

### Developer Experience

- **Fast iteration:** 70% cache hit rate means most runs < 60s
- **Intelligent scheduling:** Dependency-aware execution
- **Graceful failures:** Timeout strategies prevent hangs
- **Better error messages:** Structured error reporting
- **AI integration:** Automated fixing with confidence scoring

______________________________________________________________________

## Breaking Changes

### 1. Pre-commit Hooks No Longer Work

**Impact:** Direct `pre-commit run` commands will fail

**Before:**

```bash
pre-commit run ruff --all-files
```

**After:**

```bash
python -m crackerjack --fast  # Fast hooks (formatting, linting)
python -m crackerjack --comp  # Comprehensive hooks (all quality checks)
```

**Workaround:** Use crackerjack CLI flags instead of pre-commit

### 2. Configuration Migration

**Impact:** `.pre-commit-config.yaml` settings must migrate to `pyproject.toml`

**Before (`.pre-commit-config.yaml`):**

```yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  hooks:
    - id: ruff
      args: [--fix]
```

**After (`pyproject.toml`):**

```toml
[tool.crackerjack.hooks.ruff]
enabled = true
auto_fix = true
```

**Migration Script:** (Run once)

```bash
python -m crackerjack --migrate-config
```

### 3. Import Path Changes

**Impact:** Custom adapters or extensions must update imports

**Before:**

```python
from crackerjack.adapters.qa.base import QAAdapterBase
```

**After:**

```python
from crackerjack.adapters._qa_adapter_base import QAAdapterBase
from crackerjack.models.protocols import QAAdapterProtocol
```

**Rule:** Always import protocols from `models.protocols`, not concrete classes

### 4. Test Execution Changes

**Impact:** Tests now run via pytest directly (no pre-commit integration)

**Before:**

```bash
pre-commit run pytest --all-files
```

**After:**

```bash
python -m crackerjack --run-tests
# or directly:
python -m pytest
```

______________________________________________________________________

## Step-by-Step Migration

### For Existing Crackerjack Projects

#### Step 1: Update Dependencies

```bash
# Update to latest crackerjack
uv pip install --upgrade crackerjack

# Verify ACB is installed
python -c "import acb; print(acb.__version__)"
# Should print: 0.25.2 or higher
```

#### Step 2: Remove Pre-commit Config

```bash
# Backup existing config (optional)
cp .pre-commit-config.yaml .pre-commit-config.yaml.backup

# Remove old config
rm .pre-commit-config.yaml
```

**Note:** Crackerjack will auto-generate a new config on first run

#### Step 3: Migrate Configuration

```bash
# Run migration assistant
python -m crackerjack --migrate-config

# Verify configuration
python -m crackerjack --show-config
```

This will:

- Parse existing `.pre-commit-config.yaml` (if backup exists)
- Extract hook configurations
- Write equivalent settings to `pyproject.toml`
- Validate all settings

#### Step 4: Test Migration

```bash
# Run fast hooks to verify basic functionality
python -m crackerjack --fast

# Run comprehensive checks
python -m crackerjack --comp

# Run full test suite
python -m crackerjack --run-tests
```

#### Step 5: Update CI/CD Pipelines

**Before (`.github/workflows/quality.yml`):**

```yaml
- name: Run pre-commit
  run: pre-commit run --all-files
```

**After:**

```yaml
- name: Run quality checks
  run: python -m crackerjack --comp --run-tests
```

#### Step 6: Update Git Hooks (Optional)

```bash
# Install crackerjack as git pre-commit hook
python -m crackerjack --install-hooks

# This creates .git/hooks/pre-commit calling crackerjack --fast
```

### For New Projects

```bash
# Initialize project
python -m crackerjack --init

# This will:
# - Create pyproject.toml with recommended settings
# - Initialize git repository
# - Install git hooks
# - Run initial quality checks
```

______________________________________________________________________

## Code Examples

### Creating a Custom QA Adapter

```python
# myproject/adapters/custom_lint.py

import uuid
from contextlib import suppress
from pathlib import Path

from acb.depends import depends
from crackerjack.adapters._qa_adapter_base import QAAdapterBase, QABaseSettings
from crackerjack.models.qa_results import QAResult
from crackerjack.models.protocols import QAAdapterProtocol

# ACB Module Registration (REQUIRED)
MODULE_ID = uuid.UUID("01937d86-xxxx-xxxx-xxxx-xxxxxxxxxxxx")  # Generate with uuidgen
MODULE_STATUS = "stable"


class CustomLintSettings(QABaseSettings):
    """Settings for custom linter."""

    strict_mode: bool = False
    ignore_patterns: list[str] = []


class CustomLintAdapter(QAAdapterBase):
    """Custom linting adapter following ACB patterns."""

    settings: CustomLintSettings | None = None

    async def init(self) -> None:
        """Initialize adapter with settings."""
        if not self.settings:
            self.settings = CustomLintSettings()
        await super().init()

    @property
    def adapter_name(self) -> str:
        return "Custom Linter"

    @property
    def module_id(self) -> uuid.UUID:
        return MODULE_ID

    async def check(
        self,
        files: list[Path] | None = None,
        config: dict | None = None,
    ) -> QAResult:
        """Execute custom linting check."""

        # Use semaphore for concurrency control
        async with self._semaphore:
            # Your linting logic here
            issues = await self._lint_files(files or [])

            return QAResult(
                passed=len(issues) == 0,
                issues=issues,
                adapter_name=self.adapter_name,
            )

    async def _lint_files(self, files: list[Path]) -> list[dict]:
        """Lint files and return issues."""
        issues = []

        for file_path in files:
            if file_path.suffix == ".py":
                # Your linting logic
                pass

        return issues


# ACB Registration (REQUIRED at module level)
with suppress(Exception):
    depends.set(CustomLintAdapter)
```

### Using Dependency Injection

```python
# myproject/scripts/run_custom_lint.py

import asyncio
from pathlib import Path

from acb.depends import depends
from myproject.adapters.custom_lint import CustomLintAdapter


async def main():
    # Get adapter instance from DI container
    adapter = await depends.get(CustomLintAdapter)

    # Initialize if not already done
    if not adapter._initialized:
        await adapter.init()

    # Run check
    files = list(Path("myproject").glob("**/*.py"))
    result = await adapter.check(files)

    print(f"Passed: {result.passed}")
    print(f"Issues: {len(result.issues)}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Registering with Hook Orchestrator

```python
# pyproject.toml

[tool.crackerjack.hooks.custom - lint]
enabled = true
stage = "comprehensive"  # or "fast" or "manual"
timeout = 60
file_patterns = ["**/*.py"]
exclude_patterns = ["**/tests/**"]
```

### Testing Custom Adapter

```python
# tests/test_custom_lint.py

import pytest
from pathlib import Path

from myproject.adapters.custom_lint import CustomLintAdapter


@pytest.fixture
async def adapter():
    """Create and initialize adapter."""
    adapter = CustomLintAdapter()
    await adapter.init()
    return adapter


@pytest.mark.asyncio
async def test_adapter_initialization(adapter):
    """Test adapter initializes correctly."""
    assert adapter._initialized
    assert adapter.settings is not None
    assert adapter.adapter_name == "Custom Linter"


@pytest.mark.asyncio
async def test_lint_clean_file(adapter, tmp_path):
    """Test linting a clean Python file."""
    # Create test file
    test_file = tmp_path / "clean.py"
    test_file.write_text("# Clean Python file\nprint('hello')\n")

    # Run check
    result = await adapter.check([test_file])

    # Verify
    assert result.passed
    assert len(result.issues) == 0
```

______________________________________________________________________

## Success Patterns from Phase 2-4 Refactoring

**Status:** Based on comprehensive audit of 30+ files across all architectural layers

### Phase 2: Import & DI Foundation (COMPLETE ✅)

**Achievement:** 100% lazy import elimination + protocol-based DI

**What We Learned:**

1. **Protocol imports are non-negotiable**
   ```python
   # ❌ WRONG - Creates circular dependencies
   from ..managers.test_manager import TestManager
   from rich.console import Console

   # ✅ CORRECT - Protocol-based, no circular deps
   from ..models.protocols import TestManagerProtocol, Console
   ```

2. **All protocols live in one place**
   - Single source of truth: `crackerjack/models/protocols.py`
   - 1571 lines of comprehensive protocol definitions
   - `@runtime_checkable` for runtime type validation

3. **Zero tolerance for lazy imports**
   - Every `if TYPE_CHECKING:` block was eliminated
   - Performance impact: negligible (< 1% overhead)
   - Maintainability gain: massive (no import ordering issues)

### Phase 3: Service Layer Standardization (COMPLETE ✅)

**Achievement:** 15+ services refactored to ACB standards

**Gold Standard Service Pattern:**

```python
from acb.depends import depends, Inject
from crackerjack.models.protocols import (
    Console,
    FilesystemProtocol,
    LoggerProtocol,
)

class MyService:
    """Service following Phase 3 standards."""

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        filesystem: Inject[FilesystemProtocol],
        logger: Inject[LoggerProtocol],
    ) -> None:
        """All dependencies injected via protocols."""
        self.console = console
        self.filesystem = filesystem
        self.logger = logger

    async def init(self) -> None:
        """Async initialization (lifecycle management)."""
        await self._setup_resources()

    async def cleanup(self) -> None:
        """Async cleanup (lifecycle management)."""
        await self._release_resources()
```

**Anti-Patterns Successfully Eliminated:**

```python
# ❌ Manual fallbacks bypass DI container
def __init__(self, console: Console | None = None):
    self.console = console or Console()  # DON'T DO THIS

# ❌ Factory functions bypass DI
def __init__(self):
    self.tracker = get_agent_tracker()  # DON'T DO THIS
    self.manager = create_timeout_manager()  # DON'T DO THIS

# ❌ Direct service instantiation
def __init__(self):
    self.logger = logging.getLogger(__name__)  # DON'T DO THIS
```

### Phase 4: Architecture Audit (COMPLETE ✅)

**Achievement:** Comprehensive audit of all architectural layers

**Compliance Scores by Layer:**

| Layer | Compliance | Files Audited | Gold Standards Identified |
|-------|-----------|---------------|---------------------------|
| **CLI Handlers** | 90% | 4 handlers | `handlers.py` (100% compliant) |
| **Services** | 95% | 15+ services | Phase 3 refactored services |
| **Managers** | 80% | 5 managers | `TestManager`, `HookManager` |
| **Orchestration** | 70% | 3 components | `SessionCoordinator` (perfect DI) |
| **Coordinators** | 70% | 4 coordinators | Phase coordinators ✅ |
| **Agent System** | 40% | 22 agent files | Uses legacy `AgentContext` pattern |

**Gold Standard Examples from Real Code:**

**1. CLI Handler Pattern (90% Compliance)**
```python
# From: crackerjack/cli/handlers.py
from acb.depends import depends, Inject
from ..models.protocols import Console

@depends.inject
def setup_ai_agent_env(
    ai_agent: bool,
    debug_mode: bool = False,
    console: Inject[Console] = None,
) -> None:
    """Perfect example of DI in action."""
    if ai_agent:
        console.print("[green]AI agents enabled[/green]")
```

**2. SessionCoordinator Pattern (Perfect DI)**
```python
# From: crackerjack/core/session_coordinator.py
from acb.depends import depends, Inject
from ..models.protocols import Console, TestManagerProtocol

class SessionCoordinator:
    """The gold standard for orchestration layer DI."""

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        test_manager: Inject[TestManagerProtocol],
        pkg_path: Path,
        web_job_id: str | None = None,
    ) -> None:
        self.console = console
        self.test_manager = test_manager
        self.pkg_path = pkg_path
        self.web_job_id = web_job_id
```

**3. Why Agent System Uses Legacy Pattern**

The 12 AI agents (RefactoringAgent, PerformanceAgent, SecurityAgent, etc.) use the `AgentContext` pattern which predates ACB adoption:

```python
# Agent System Pattern (Legacy but working)
@dataclass
class AgentContext:
    """Dataclass-based context for agent isolation."""
    filesystem: FilesystemProtocol
    git: GitProtocol
    settings: CrackerjackSettings
    cache: CrackerjackCache

class RefactoringAgent(SubAgent):
    def __init__(self, context: AgentContext) -> None:
        super().__init__(context)
        # Agents work well with this pattern
```

**Why we're not rushing to refactor agents:**
- Agents are 100% functional with current pattern
- `AgentContext` provides good isolation
- No performance issues
- Phase 4 defined protocols for future migration
- Higher priority items exist (ServiceWatchdog, CrackerjackCLIFacade)

### Key Takeaways for Future Development

**✅ DO:**
1. Always use `@depends.inject` decorator for new classes
2. Import protocols from `models/protocols.py`, never concrete classes
3. Follow CLI handlers pattern for new handler functions
4. Follow SessionCoordinator pattern for new coordinators
5. Add protocol definition before implementing new interfaces
6. Use `Inject[Protocol]` type hints for DI parameters

**❌ DON'T:**
1. Add manual fallbacks like `console or Console()`
2. Create factory functions that bypass DI
3. Import concrete classes for DI dependencies
4. Skip `@depends.inject` decorator
5. Use `if TYPE_CHECKING:` lazy imports
6. Instantiate services directly in constructors

### Metrics & Achievements

**Code Quality Improvements:**
- **Protocol Coverage:** 70+ protocols defined
- **Import Cycles:** Zero (eliminated 100% of lazy imports)
- **DI Compliance:** 75% average across all layers
- **Test Coverage:** Maintained (10.11% baseline, targeting 100%)

**Performance Maintained:**
- No performance regression from Phase 2-4 changes
- DI overhead: < 1% (negligible)
- Type checking: Faster with Zuban (20-200x faster than Pyright)

**Developer Experience:**
- Clear patterns documented in CLAUDE.md
- Gold standards identified (CLI handlers, SessionCoordinator)
- Anti-patterns documented and eliminated
- New developers can follow established patterns

______________________________________________________________________

## Troubleshooting

### Issue: "Module not found: acb"

**Solution:**

```bash
uv pip install acb>=0.25.2
```

### Issue: "Cannot import QAAdapterProtocol"

**Cause:** Importing from wrong location

**Solution:**

```python
# ❌ Wrong
from crackerjack.adapters.qa.base import QAAdapterProtocol

# ✅ Correct
from crackerjack.models.protocols import QAAdapterProtocol
```

### Issue: "MODULE_ID already registered"

**Cause:** Duplicate MODULE_ID UUID

**Solution:**

```bash
# Generate unique UUID
uuidgen

# Use in your adapter
MODULE_ID = uuid.UUID("01937d86-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
```

### Issue: "Pre-commit hooks still running"

**Cause:** Old `.git/hooks/pre-commit` script

**Solution:**

```bash
# Remove old hook
rm .git/hooks/pre-commit

# Install crackerjack hook
python -m crackerjack --install-hooks
```

### Issue: "Tests timing out"

**Cause:** Async tests without proper timeout handling

**Solution:**

```python
# Add timeout to pytest configuration
# pyproject.toml

[tool.pytest.ini_options]
asyncio_mode = "auto"
timeout = 300  # 5 minutes
```

### Issue: "Cache not working"

**Cause:** Cache directory permissions or configuration issue

**Solution:**

```bash
# Check cache directory
ls -la .crackerjack/cache

# Clear cache
python -m crackerjack --clear-cache

# Rebuild cache
python -m crackerjack --fast
```

______________________________________________________________________

## FAQ

### Q: Do I need to rewrite all my pre-commit hooks?

**A:** No! Crackerjack maintains backward compatibility during migration. The dual execution mode (`legacy` vs `acb`) allows gradual migration.

### Q: What happens to my custom pre-commit hooks?

**A:** You have three options:

1. Migrate to ACB adapters (recommended)
1. Keep as standalone pre-commit hooks
1. Call via subprocess from crackerjack

### Q: Can I still use pre-commit for other tools (e.g., commitlint)?

**A:** Yes! Crackerjack only replaces Python quality tools. Non-Python hooks continue working.

### Q: How do I debug ACB dependency injection issues?

**A:** Use the `--ai-debug` flag:

```bash
python -m crackerjack --ai-debug --run-tests
```

This enables verbose logging for DI container operations.

### Q: What's the performance overhead of ACB?

**A:** Negligible! ACB adds < 1ms per dependency lookup (cached after first access).

### Q: Can I mix legacy and ACB execution modes?

**A:** Yes, temporarily. Set in `pyproject.toml`:

```toml
[tool.crackerjack.orchestration]
execution_mode = "legacy"  # or "acb"
```

**Recommendation:** Use `"acb"` for best performance.

### Q: How do I contribute a new adapter?

**A:** Follow the pattern in `/docs/ACB-ADAPTER-TEMPLATE.md`:

1. Extend `QAAdapterBase` or `ToolAdapterBase`
1. Define MODULE_ID and MODULE_STATUS
1. Register with `depends.set(YourAdapter)`
1. Add tests
1. Submit PR

### Q: What's the minimum Python version?

**A:** Python 3.13+ (for modern type syntax and async improvements)

### Q: Is ACB compatible with other DI frameworks?

**A:** ACB is standalone but integrates with:

- Pydantic (for settings)
- FastAPI (for web services)
- asyncio (for async execution)

### Q: How do I rollback if ACB causes issues?

**A:** Restore pre-commit config from backup:

```bash
git checkout HEAD -- .pre-commit-config.yaml
pre-commit install
```

Then file an issue on GitHub!

______________________________________________________________________

## Additional Resources

- **ACB Documentation:** [https://github.com/lesleslie/acb](https://github.com/lesleslie/acb)
- **Crackerjack Adapters:** `/crackerjack/adapters/`
- **Performance Benchmarks:** `/docs/ACB-PERFORMANCE-BENCHMARKS.md`
- **Code Review Report:** Contact maintainers for latest audit
- **Migration Support:** Open an issue on GitHub

______________________________________________________________________

## Support

Need help with migration?

1. **Check troubleshooting section** above
1. **Search existing issues:** [GitHub Issues](https://github.com/lesleslie/crackerjack/issues)
1. **Ask on discussions:** [GitHub Discussions](https://github.com/lesleslie/crackerjack/discussions)
1. **Open new issue:** Provide error output and `pyproject.toml`

______________________________________________________________________

**Last Updated:** 2025-10-09
**Migration Status:** ✅ Production Ready
**Version:** Crackerjack 1.0.0+ with ACB 0.25.2+

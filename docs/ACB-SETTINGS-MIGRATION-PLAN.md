# ACB Settings Migration Plan

**Status:** Phase 1, Week 1 (Day 1-2)
**Priority:** HIGH
**Effort:** 1-2 days
**Risk:** LOW (ACB Settings is production-tested)

## Executive Summary

Consolidate 11 configuration files (~1,808 LOC) into a single ACB Settings class (~300 LOC), reducing complexity by 60% while adding automatic environment variable loading, validation, and secrets management.

## Current State Analysis

### Configuration Files to Consolidate

| File | Lines | Type | Purpose |
|------|-------|------|---------|
| `models/config.py` | 113 | dataclass | Workflow options (11 configs) |
| `models/qa_config.py` | 145 | Pydantic | QA framework config |
| `orchestration/config.py` | 442 | dataclass | Orchestration settings |
| `services/config.py` | 358 | service | Config management |
| `dynamic_config.py` | 680 | mixed | Dynamic configuration |
| `config/global_lock_config.py` | 70 | dataclass | Global locking |
| `services/config_integrity.py` | - | service | Config validation |
| `services/config_merge.py` | - | service | Config merging |
| `services/config_template.py` | - | service | Templates |
| `services/unified_config.py` | - | service | Unified interface |
| `models/config_adapter.py` | - | adapter | ACB adapter |

**Total:** ~1,808 lines across 11 files

### Configuration Patterns Found

#### Pattern 1: Dataclass Workflow Options (models/config.py)
```python
@dataclass
class CleaningConfig:
    clean: bool = True
    update_docs: bool = False

@dataclass
class HookConfig:
    skip_hooks: bool = False
    experimental_hooks: bool = False

@dataclass
class WorkflowOptions:
    cleaning: CleaningConfig = field(default_factory=CleaningConfig)
    hooks: HookConfig = field(default_factory=HookConfig)
    # ... 9 more configs
```

#### Pattern 2: Pydantic QA Config (models/qa_config.py)
```python
class QACheckConfig(BaseModel):
    check_id: UUID
    check_name: str
    check_type: QACheckType
    enabled: bool = True
    # ... validation, properties

class QAOrchestratorConfig(BaseModel):
    project_root: Path
    max_parallel_checks: int = 4
    enable_caching: bool = True
    checks: list[QACheckConfig] = []
```

#### Pattern 3: Custom Orchestration Config (orchestration/config.py)
```python
@dataclass
class OrchestrationConfig:
    enable_orchestration: bool = False
    orchestration_mode: str = "acb"
    cache_backend: str = "memory"
    # ... 20+ settings

    @classmethod
    def from_file(cls, config_path: Path) -> OrchestrationConfig:
        # Manual YAML loading (100+ lines)

    @classmethod
    def from_env(cls) -> OrchestrationConfig:
        # Manual env var parsing (50+ lines)
```

## Target State: ACB Settings

### Unified Settings Class

```python
# crackerjack/config/settings.py
from acb.config import Settings
from pathlib import Path
from pydantic import Field

class CrackerjackSettings(Settings):
    """Single source of truth for all Crackerjack settings.

    ACB Settings provides:
    - Automatic env var loading (CRACKERJACK_*)
    - Type validation via Pydantic
    - Secrets management (masked in logs)
    - YAML/JSON/env file loading
    - Default value handling
    """

    # === Workflow Settings ===
    # Cleaning
    clean: bool = True
    update_docs: bool = False
    force_update_docs: bool = False
    compress_docs: bool = False
    auto_compress_docs: bool = False

    # Hooks
    skip_hooks: bool = False
    update_precommit: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    enable_lsp_optimization: bool = False

    # Testing
    run_tests: bool = False
    benchmark: bool = False
    test_workers: int = 0
    test_timeout: int = 0

    # Publishing
    publish_version: str | None = None
    bump_version: str | None = None
    all_workflow: str | None = None
    no_git_tags: bool = False
    skip_version_check: bool = False

    # Git
    commit: bool = False
    create_pr: bool = False

    # AI
    ai_agent: bool = False
    start_mcp_server: bool = False
    max_iterations: int = 5
    autofix: bool = True
    ai_agent_autofix: bool = False

    # Execution
    interactive: bool = False
    verbose: bool = False
    async_mode: bool = False
    no_config_updates: bool = False

    # Progress
    progress_enabled: bool = False

    # Cleanup
    auto_cleanup: bool = True
    keep_debug_logs: int = 5
    keep_coverage_files: int = 10

    # Enterprise
    enterprise_enabled: bool = False
    license_key: str | None = Field(None, secret=True)  # ACB auto-masks
    organization: str | None = None

    # MCP Server
    mcp_http_port: int = 8676
    mcp_http_host: str = "127.0.0.1"
    mcp_websocket_port: int = 8675
    mcp_http_enabled: bool = False

    # Zuban LSP
    zuban_enabled: bool = True
    zuban_auto_start: bool = True
    zuban_port: int = 8677
    zuban_mode: str = "stdio"
    zuban_timeout: int = 30

    # === Orchestration Settings ===
    enable_orchestration: bool = False
    orchestration_mode: str = "acb"

    # Cache
    enable_caching: bool = True
    cache_backend: str = "memory"
    cache_ttl: int = 3600
    cache_max_entries: int = 100

    # Execution
    max_parallel_hooks: int = 4
    default_timeout: int = 600
    stop_on_critical_failure: bool = True

    # Advanced
    enable_dependency_resolution: bool = True
    log_cache_stats: bool = False
    log_execution_timing: bool = False

    # Parallelism
    enable_strategy_parallelism: bool = True
    enable_adaptive_execution: bool = True
    max_concurrent_strategies: int = 2

    # Tool invocation
    use_precommit_legacy: bool = True

    # === QA Settings ===
    project_root: Path = Field(default_factory=Path.cwd)
    qa_max_parallel_checks: int = 4
    qa_fail_fast: bool = False
    qa_run_formatters_first: bool = True
    qa_enable_incremental: bool = True

    # === Global Settings ===
    global_lock_timeout: int = 30
    lock_directory: Path = Field(default_factory=lambda: Path.home() / ".crackerjack" / "locks")

    class Config:
        env_prefix = "CRACKERJACK_"  # Auto-loads CRACKERJACK_VERBOSE, etc.
        env_file = ".env"  # Optional .env file support
        case_sensitive = False  # CRACKERJACK_verbose or crackerjack_VERBOSE both work
```

### Usage Pattern

```python
# Before (scattered imports)
from crackerjack.models.config import WorkflowOptions, HookConfig
from crackerjack.orchestration.config import OrchestrationConfig
from crackerjack.models.qa_config import QAOrchestratorConfig
from crackerjack.services.config import ConfigurationService

# After (single import via DI)
from acb.depends import depends
from crackerjack.config.settings import CrackerjackSettings

# Get settings anywhere in the app
settings = depends.get(CrackerjackSettings)

# ACB auto-loads from:
# 1. Environment variables (CRACKERJACK_VERBOSE=true)
# 2. .env file
# 3. YAML/JSON config files (if configured)
# 4. Defaults from class definition
```

## Migration Steps

### Phase 1: Create ACB Settings Class (2-3 hours)

1. **Create settings module**
   ```bash
   # Create new settings file
   touch crackerjack/config/settings.py
   ```

2. **Consolidate all settings**
   - Copy all dataclass fields from `models/config.py`
   - Copy all Pydantic fields from `models/qa_config.py`
   - Copy all settings from `orchestration/config.py`
   - Add env_prefix and defaults

3. **Register with ACB**
   ```python
   # In crackerjack/config/__init__.py
   from acb.depends import depends
   from .settings import CrackerjackSettings

   # Register as singleton
   depends.set(CrackerjackSettings, CrackerjackSettings())
   ```

### Phase 2: Update Import Patterns (3-4 hours)

1. **Find all config imports**
   ```bash
   grep -r "from crackerjack.models.config import" crackerjack/
   grep -r "from crackerjack.orchestration.config import" crackerjack/
   grep -r "from crackerjack.models.qa_config import" crackerjack/
   ```

2. **Replace with ACB dependency injection**
   ```python
   # Before
   config = WorkflowOptions()
   if config.hooks.skip_hooks:
       ...

   # After
   settings = depends.get(CrackerjackSettings)
   if settings.skip_hooks:
       ...
   ```

3. **Update DI containers**
   - Modify `enhanced_container.py` to use CrackerjackSettings
   - Modify `container.py` to use CrackerjackSettings
   - Update all factory lambdas

### Phase 3: Migrate Service Classes (2-3 hours)

1. **ConfigurationService → ACB Settings**
   - Remove manual env var parsing
   - Remove YAML loading logic
   - Keep only business logic (if any)

2. **ConfigMergeService → ACB Config Layers**
   ```python
   # ACB handles merging automatically via layers
   from acb.config import Config

   config = Config(
       settings=CrackerjackSettings,
       layers=["env", "file", "defaults"]  # Priority order
   )
   ```

3. **UnifiedConfigurationService → Deprecate**
   - ACB Settings already provides unified interface
   - Move any custom logic to settings class methods

### Phase 4: Update Tests (2-3 hours)

1. **Test settings access**
   ```python
   def test_settings_from_env(monkeypatch):
       monkeypatch.setenv("CRACKERJACK_VERBOSE", "true")
       settings = CrackerjackSettings()
       assert settings.verbose is True
   ```

2. **Test DI integration**
   ```python
   def test_settings_via_depends():
       from acb.depends import depends
       settings = depends.get(CrackerjackSettings)
       assert isinstance(settings, CrackerjackSettings)
   ```

3. **Update existing config tests**
   - Migrate tests from old config files
   - Simplify tests (ACB handles validation)

### Phase 5: Remove Old Files (1 hour)

1. **Safe removal order**
   ```bash
   # 1. Remove service classes (replaced by ACB)
   rm crackerjack/services/config.py
   rm crackerjack/services/config_merge.py
   rm crackerjack/services/config_integrity.py
   rm crackerjack/services/config_template.py
   rm crackerjack/services/unified_config.py

   # 2. Remove old config models
   rm crackerjack/models/config.py
   rm crackerjack/models/config_adapter.py
   rm crackerjack/orchestration/config.py
   rm crackerjack/dynamic_config.py
   rm crackerjack/config/global_lock_config.py

   # 3. Keep QA config temporarily (gradual migration)
   # Will migrate in Phase 2
   ```

2. **Update protocols**
   - Remove `ConfigurationServiceProtocol` (replaced by CrackerjackSettings)
   - Keep only business logic protocols

## Success Metrics

### Before
- **Files:** 11 configuration files
- **Lines of Code:** ~1,808
- **Import Complexity:** High (multiple patterns)
- **Env Var Support:** Manual parsing
- **Validation:** Inconsistent
- **Secrets Handling:** Risky (plain strings)

### After
- **Files:** 1 settings file
- **Lines of Code:** ~300 (83% reduction)
- **Import Complexity:** Low (single source)
- **Env Var Support:** Automatic (CRACKERJACK_* prefix)
- **Validation:** Built-in (Pydantic)
- **Secrets Handling:** Safe (auto-masked)

### Impact
- **Maintainability:** ⬆️⬆️⬆️ Much easier to understand/modify
- **Type Safety:** ⬆️⬆️ Full Pydantic validation
- **Developer Experience:** ⬆️⬆️⬆️ Single import, auto-completion
- **Configuration:** ⬆️⬆️ Env vars, files, defaults all work
- **Security:** ⬆️⬆️ Secrets auto-masked in logs

## Risk Mitigation

### Low Risk Items
- ✅ ACB Settings is Pydantic-based (already using Pydantic in QA configs)
- ✅ Gradual migration possible (keep old files during transition)
- ✅ Backward compatibility via adapter pattern if needed

### Medium Risk Items
- ⚠️ DI container updates (need careful testing)
- ⚠️ Service class removal (verify no custom logic lost)

### Mitigation Strategies
1. **Create backup branch** before starting
2. **Run full test suite** after each phase
3. **Keep old imports working** via temporary adapters
4. **Comprehensive logging** during migration

## Timeline

| Phase | Task | Duration | Day |
|-------|------|----------|-----|
| 1 | Create ACB Settings class | 2-3 hours | Day 1 AM |
| 2 | Update import patterns | 3-4 hours | Day 1 PM |
| 3 | Migrate service classes | 2-3 hours | Day 2 AM |
| 4 | Update tests | 2-3 hours | Day 2 PM |
| 5 | Remove old files & verify | 1 hour | Day 2 PM |

**Total:** 10-14 hours (1.5-2 days)

## Next Steps

1. ✅ Review this plan with team/stakeholders
2. Create feature branch: `feature/acb-settings-migration`
3. Start Phase 1: Create CrackerjackSettings class
4. Incremental commits per phase
5. Full regression testing before merge

---

**Author:** Claude Code (AI Agent)
**Date:** 2025-10-09
**Based on:** ACB-INTEGRATION-REVIEW.md, COMPREHENSIVE-IMPROVEMENT-PLAN.md

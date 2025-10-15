# ACB Settings Field Mapping Guide

## Phase 2 Migration Reference

This document maps old configuration patterns to the new unified `CrackerjackSettings` class.

## Import Pattern Changes

### Before (OLD)

```python
from crackerjack.models.config import WorkflowOptions
from crackerjack.orchestration.config import OrchestrationConfig
from crackerjack.models.qa_config import QACheckConfig
```

### After (NEW)

```python
from acb.depends import depends
from crackerjack.config import CrackerjackSettings

# Get settings from DI
settings = depends.get(CrackerjackSettings)
```

## Field Mapping

### WorkflowOptions → CrackerjackSettings

#### Nested Access Pattern Changes

**Cleaning Config**

```python
# OLD
options.cleaning.clean              → settings.clean
options.cleaning.update_docs        → settings.update_docs
options.cleaning.force_update_docs  → settings.force_update_docs
options.cleaning.compress_docs      → settings.compress_docs
options.cleaning.auto_compress_docs → settings.auto_compress_docs
```

**Hook Config**

```python
# OLD
options.hooks.skip_hooks             → settings.skip_hooks
options.hooks.update_precommit       → settings.update_precommit
options.hooks.experimental_hooks     → settings.experimental_hooks
options.hooks.enable_pyrefly         → settings.enable_pyrefly
options.hooks.enable_ty              → settings.enable_ty
options.hooks.enable_lsp_optimization → settings.enable_lsp_optimization
```

**Test Config**

```python
# OLD
options.testing.test         → settings.run_tests  # ⚠️ RENAMED!
options.testing.benchmark    → settings.benchmark
options.testing.test_workers → settings.test_workers
options.testing.test_timeout → settings.test_timeout
```

**Publishing Config**

```python
# OLD
options.publishing.publish          → settings.publish_version
options.publishing.bump             → settings.bump_version
options.publishing.all              → settings.all_workflow
options.publishing.no_git_tags      → settings.no_git_tags
options.publishing.skip_version_check → settings.skip_version_check
```

**Git Config**

```python
# OLD
options.git.commit    → settings.commit
options.git.create_pr → settings.create_pr
```

**AI Config**

```python
# OLD
options.ai.ai_agent         → settings.ai_agent
options.ai.start_mcp_server → settings.start_mcp_server
options.ai.max_iterations   → settings.max_iterations
options.ai.autofix          → settings.autofix
options.ai.ai_agent_autofix → settings.ai_agent_autofix
```

**Execution Config**

```python
# OLD
options.execution.interactive       → settings.interactive
options.execution.verbose           → settings.verbose
options.execution.async_mode        → settings.async_mode
options.execution.no_config_updates → settings.no_config_updates
```

**Progress Config**

```python
# OLD
options.progress.enabled → settings.progress_enabled
```

**Cleanup Config**

```python
# OLD
options.cleanup.auto_cleanup        → settings.auto_cleanup
options.cleanup.keep_debug_logs     → settings.keep_debug_logs
options.cleanup.keep_coverage_files → settings.keep_coverage_files
```

**Advanced Config**

```python
# OLD
options.advanced.enabled      → settings.advanced_enabled
options.advanced.license_key  → settings.license_key
options.advanced.organization → settings.organization
```

**MCP Server Config**

```python
# OLD
options.mcp_server.http_port      → settings.mcp_http_port
options.mcp_server.http_host      → settings.mcp_http_host
options.mcp_server.websocket_port → settings.mcp_websocket_port
options.mcp_server.http_enabled   → settings.mcp_http_enabled
```

**Zuban LSP Config**

```python
# OLD
options.zuban_lsp.enabled    → settings.zuban_enabled
options.zuban_lsp.auto_start → settings.zuban_auto_start
options.zuban_lsp.port       → settings.zuban_port
options.zuban_lsp.mode       → settings.zuban_mode
options.zuban_lsp.timeout    → settings.zuban_timeout
```

### OrchestrationConfig → CrackerjackSettings

**Direct Field Mapping (No Nesting)**

```python
# OLD
config.enable_orchestration        → settings.enable_orchestration
config.orchestration_mode          → settings.orchestration_mode
config.enable_caching              → settings.enable_caching
config.cache_backend               → settings.cache_backend
config.cache_ttl                   → settings.cache_ttl
config.cache_max_entries           → settings.cache_max_entries
config.max_parallel_hooks          → settings.max_parallel_hooks
config.default_timeout             → settings.default_timeout
config.stop_on_critical_failure    → settings.stop_on_critical_failure
config.enable_dependency_resolution → settings.enable_dependency_resolution
config.log_cache_stats             → settings.log_cache_stats
config.log_execution_timing        → settings.log_execution_timing
config.enable_strategy_parallelism → settings.enable_strategy_parallelism
config.enable_adaptive_execution   → settings.enable_adaptive_execution
config.max_concurrent_strategies   → settings.max_concurrent_strategies
config.use_precommit_legacy        → settings.use_precommit_legacy
```

### QACheckConfig → CrackerjackSettings

**QA Framework Settings**

```python
# OLD
qa_config.max_parallel_checks   → settings.qa_max_parallel_checks
qa_config.fail_fast             → settings.qa_fail_fast
qa_config.run_formatters_first  → settings.qa_run_formatters_first
qa_config.enable_incremental    → settings.qa_enable_incremental
```

## Migration Examples

### Example 1: MCP Tools

**Before:**

```python
from crackerjack.models.config import WorkflowOptions


def my_tool():
    options = WorkflowOptions()
    if options.hooks.skip_hooks:
        return "Skipping hooks"
    if options.execution.verbose:
        print("Verbose mode enabled")
```

**After:**

```python
from acb.depends import depends
from crackerjack.config import CrackerjackSettings


def my_tool():
    settings = depends.get(CrackerjackSettings)
    if settings.skip_hooks:
        return "Skipping hooks"
    if settings.verbose:
        print("Verbose mode enabled")
```

### Example 2: Hook Manager

**Before:**

```python
from crackerjack.orchestration.config import OrchestrationConfig


class HookManager:
    def __init__(self):
        self._config = OrchestrationConfig.load()
        self.max_workers = self._config.max_parallel_hooks
        self.use_cache = self._config.enable_caching
```

**After:**

```python
from acb.depends import depends
from crackerjack.config import CrackerjackSettings


class HookManager:
    def __init__(self):
        settings = depends.get(CrackerjackSettings)
        self.max_workers = settings.max_parallel_hooks
        self.use_cache = settings.enable_caching
```

### Example 3: QA Adapters

**Before:**

```python
from crackerjack.models.qa_config import QACheckConfig


class MyAdapter:
    def __init__(self):
        config = QACheckConfig()
        self.parallel = config.max_parallel_checks
        self.fail_fast = config.fail_fast
```

**After:**

```python
from acb.depends import depends
from crackerjack.config import CrackerjackSettings


class MyAdapter:
    def __init__(self):
        settings = depends.get(CrackerjackSettings)
        self.parallel = settings.qa_max_parallel_checks
        self.fail_fast = settings.qa_fail_fast
```

## Common Pitfalls

### 1. Renamed Fields

⚠️ `options.testing.test` → `settings.run_tests` (field renamed!)

### 2. Removed Nesting

All nested configs are now flat:

- ❌ `settings.hooks.skip_hooks`
- ✅ `settings.skip_hooks`

### 3. DI Pattern

Always use `depends.get()` instead of direct instantiation:

- ❌ `settings = CrackerjackSettings()`
- ✅ `settings = depends.get(CrackerjackSettings)`

### 4. Type Changes

Some fields had type changes:

- `publish/bump/all` changed from `t.Any | None` to `str | None`

## Migration Checklist

- [ ] Replace all `WorkflowOptions` imports
- [ ] Replace all `OrchestrationConfig` imports
- [ ] Replace all `QACheckConfig` imports
- [ ] Update nested field access (remove `.hooks`, `.testing`, etc.)
- [ ] Rename `options.testing.test` → `settings.run_tests`
- [ ] Use `depends.get(CrackerjackSettings)` pattern
- [ ] Remove old config file imports
- [ ] Update DI containers to use CrackerjackSettings
- [ ] Run tests to verify migration
- [ ] Update any protocol/interface types

## Files to Migrate

### High Priority (Core Functionality)

1. `crackerjack/managers/hook_manager.py` - OrchestrationConfig
1. `crackerjack/mcp/tools/core_tools.py` - WorkflowOptions (2 imports)
1. `crackerjack/mcp/tools/utility_tools.py` - WorkflowOptions
1. `crackerjack/executors/tool_proxy.py` - Options

### Medium Priority (Adapters)

5. All QA adapter files in `crackerjack/adapters/` (13 files)

### Low Priority (Backup Files)

6. `crackerjack/mcp/tools/execution_tools_backup.py` - Consider removal

## Testing Strategy

After each file migration:

1. Run: `python -c "from crackerjack.config import CrackerjackSettings; from acb.depends import depends; print(depends.get(CrackerjackSettings))"`
1. Run: `python -m crackerjack --help` (verify CLI works)
1. Run: `python -m pytest tests/ -v` (run relevant tests)

## Rollback Plan

If migration fails:

1. Revert changes to affected files
1. Check git diff to see what was changed
1. Fix issues one file at a time
1. Re-run verification tests

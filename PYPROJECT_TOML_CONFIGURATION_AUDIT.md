# Crackerjack pyproject.toml Configuration Audit

## Executive Summary

Investigation of two issues:

1. **Skylos timeout not being respected** when configured in pyproject.toml
1. **Oneiric's comprehensive_hooks configuration** referencing non-existent hooks

## Root Cause Analysis

### Issue 1: Skylos Timeout Not Respected

**Problem**: Setting `skylos_timeout = 720` in pyproject.toml `[tool.crackerjack]` doesn't override the hardcoded 600s timeout.

**Root Cause**: **Two separate timeout systems that don't communicate**

1. **Hook System** (pre-commit hooks):

   - Uses hardcoded `HookDefinition` objects in `crackerjack/config/hooks.py`
   - Skylos hook definition: `timeout=600` (line 278)
   - Executed via `hook_executor.py:383` → uses `hook.timeout` (hardcoded value)

1. **Adapter System** (QA tool wrappers):

   - Reads `adapter_timeouts` from settings (`_tool_adapter_base.py:240-245`)
   - Checks `settings.adapter_timeouts.{name}_timeout`
   - Returns 300s default if not configured

**The Disconnect**:

```python
# In hooks.py - HookDefinition (hardcoded)
HookDefinition(
    name="skylos",
    timeout=600,  # ← HARDCODED - never reads from pyproject.toml!
    ...
)

# In _tool_adapter_base.py - Adapter timeout lookup
def get_timeout(self) -> int:
    # This code DOES read from adapter_timeouts
    adapter_timeouts = settings.adapter_timeouts
    if adapter_timeouts and hasattr(adapter_timeouts, "skylos_timeout"):
        timeout = getattr(adapter_timeouts, "skylos_timeout")
        return timeout  # ← This works for DIRECT adapter execution
```

**Why the timeout setting exists but doesn't work**:

- `adapter_timeouts` configuration IS loaded correctly from pyproject.toml
- But hook execution path never checks it!
- Hooks use `HookDefinition.timeout` field (hardcoded in hooks.py)
- Adapters use `adapter_timeouts.{name}_timeout` (from pyproject.toml)

**Configuration Flow**:

```
pyproject.toml: skylos_timeout = 720
         ↓ (loader.py extracts _timeout keys)
settings.adapter_timeouts.skylos_timeout = 720  ✓ Loaded
         ↓
HookDefinition.timeout = 600  ✗ NOT UPDATED (hardcoded)
         ↓
Hook execution uses 600s  ✗ WRONG - should be 720s
```

### Issue 2: Oneiric's comprehensive_hooks Configuration

**Problem**: Oneiric's pyproject.toml configures hooks that don't exist in crackerjack's hook registry.

**Oneiric's configuration** (`../oneiric/pyproject.toml:290-300`):

```toml
[tool.crackerjack]
comprehensive_hooks = [
    "bandit",        # ✗ Commented out in crackerjack (replaced by semgrep)
    "skylos",        # ✓ Exists
    "xenon",        # ✗ Does not exist
    "flake8",       # ✗ Does not exist (uses ruff instead)
    "pyright",      # ✗ Does not exist (uses zuban instead)
    "basedpyright", # ✗ Does not exist
    "refurb",       # ✓ Exists
    "shellcheck",   # ✗ Does not exist
    "gitleaks",     # ✓ Exists
]
```

**Actual comprehensive hooks in crackerjack** (`crackerjack/config/hooks.py:220-329`):

```python
COMPREHENSIVE_HOOKS = [
    "zuban",           # Type checking
    "semgrep",         # SAST (replaced bandit)
    "pyscn",           # Code quality
    "gitleaks",        # Secret detection
    "pip-audit",       # Dependency security
    "skylos",          # Dead code detection
    "refurb",          # Modern Python suggestions
    "creosote",        # Unused dependencies
    "complexipy",      # Complexity analysis
    "check-jsonschema",# Schema validation
    "linkcheckmd",     # Link checking
]
```

**Why `comprehensive_hooks` configuration doesn't work**:

- `HookConfigLoader.load_strategy()` only supports "fast" or "comprehensive"
- Always returns hardcoded `FAST_STRATEGY` or `COMPREHENSIVE_STRATEGY`
- No mechanism to override hook lists from pyproject.toml!
- `HookSettings` class has no `comprehensive_hooks` field

## What IS Configurable Through pyproject.toml?

Based on `crackerjack/config/settings.py`, the following fields are supported:

### Core Settings (lines 128-160)

```toml
[tool.crackerjack]
# Console settings
console_width = 70
console_verbose = false

# Hook behavior (NOT which hooks to run)
skip_hooks = false
experimental_hooks = false
enable_pyrefly = false
enable_ty = false
enable_lsp_optimization = false

# Test configuration
test = false
test_workers = 0  # 0 = auto-detect
test_timeout = 0
max_workers = 8
memory_per_worker_gb = 2.0

# MCP server
mcp_http_port = 8676
mcp_http_host = "127.0.0.1"
mcp_websocket_port = 8675
mcp_http_enabled = true

# Zuban LSP
zuban_lsp_enabled = true
zuban_lsp_timeout = 120.0

# Adapter timeouts (for DIRECT adapter execution, not hooks)
skylos_timeout = 120
refurb_timeout = 120
zuban_timeout = 120
bandit_timeout = 300
semgrep_timeout = 300
pip_audit_timeout = 120
creosote_timeout = 120
complexipy_timeout = 60
pyscn_timeout = 60
gitleaks_timeout = 60
zuban_lsp_timeout = 120.0

# Orchestration
enable_orchestration = true
orchestration_mode = "oneiric"
enable_caching = true
cache_backend = "memory"
cache_ttl = 3600
cache_max_entries = 100

# Execution
max_parallel_hooks = 4
default_timeout = 1800
stop_on_critical_failure = true
enable_dependency_resolution = true
enable_strategy_parallelism = true
enable_adaptive_execution = true
max_concurrent_strategies = 2
enable_tool_proxy = true

# Logging
log_cache_stats = false
log_execution_timing = false
verbose = false
```

### What is NOT configurable:

1. **Hook lists** - Cannot customize which hooks run in fast/comprehensive strategies
1. **Hook timeouts** - `adapter_timeouts` only apply to direct adapter execution, not hooks
1. **Hook stages** - Cannot move hooks between fast/comprehensive stages
1. **Retry policies** - Hardcoded in hook strategies

## Recommended Fixes

### Fix 1: Make Hook Timeouts Respected

**Option A**: Update hook definitions from settings (recommended)

```python
# In hooks.py - after loading from pyproject.toml
def _update_hook_timeouts(settings: CrackerjackSettings):
    """Update hook timeouts from adapter_timeouts configuration."""
    for hook in COMPREHENSIVE_HOOKS + FAST_HOOKS:
        timeout_attr = f"{hook.name}_timeout"
        if hasattr(settings.adapter_timeouts, timeout_attr):
            hook.timeout = getattr(settings.adapter_timeouts, timeout_attr)
```

**Option B**: Make hooks check adapter_timeouts at runtime

```python
# In HookDefinition.get_timeout()
def get_timeout(self) -> int:
    try:
        settings = load_settings(CrackerjackSettings)
        timeout_attr = f"{self.name}_timeout"
        if hasattr(settings.adapter_timeouts, timeout_attr):
            return getattr(settings.adapter_timeouts, timeout_attr)
    except Exception:
        pass
    return self.timeout  # Fall back to hardcoded default
```

### Fix 2: Document Actual Hook Configuration

**Remove non-existent hooks from oneiric's config**:

```toml
[tool.crackerjack]
# This field is NOT currently supported - hooks are hardcoded
# comprehensive_hooks = [...]  # ← Remove this

# Instead, configure timeouts (for direct adapter execution only)
skylos_timeout = 720
refurb_timeout = 120
```

### Fix 3: Add Hook Customization Support (Future Enhancement)

If hook customization is needed, implement:

```python
# In settings.py
class HookSettings(Settings):
    comprehensive_hook_override: list[str] = []
    fast_hook_override: list[str] = []

# In HookConfigLoader
def load_strategy(name: str, custom_hooks: list[str] | None = None):
    if custom_hooks:
        # Build custom strategy from hook names
        hooks = [get_hook_by_name(h) for h in custom_hooks]
        return HookStrategy(name="custom", hooks=hooks)
    # Return default strategy
```

## Summary

**Current State**:

- ✅ `adapter_timeouts` configuration IS loaded from pyproject.toml
- ❌ Hook system DOESN'T use these timeouts (uses hardcoded values)
- ❌ `comprehensive_hooks` configuration is NOT supported
- ✅ Only adapter timeouts work for DIRECT adapter execution

**What Works**:

- Configuring timeouts for direct adapter execution (not via hooks)
- All fields in `CrackerjackSettings` (console, testing, MCP server, etc.)

**What Doesn't Work**:

- Overriding hook timeouts via pyproject.toml
- Customizing which hooks run in fast/comprehensive strategies
- Adding new hooks via configuration

**Recommendation**:
Implement Fix 1A to make hook timeouts respect `adapter_timeouts` configuration, and document that `comprehensive_hooks` is not a supported field.

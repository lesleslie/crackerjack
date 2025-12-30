> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | Hooks

# Hooks

Hook integrations and lifecycle extensions that plug into the runtime for intelligent, LSP-aware quality enforcement.

## Overview

The hooks system provides intelligent integration with quality tools through both traditional pre-commit hooks and modern LSP-based type checking. Hooks are executed in two stages (fast and comprehensive) with automatic retry logic and parallel execution support.

## Hook System Architecture

### Two-Stage Execution Model

Crackerjack uses a two-stage hook execution model for optimal performance:

1. **Fast Hooks** (~5s) - Quick formatters and basic checks with automatic retry

   - Formatting tools (Ruff, trailing whitespace, end-of-file fixer)
   - Import sorting
   - Basic static analysis
   - **Retry Policy**: Automatically retry once if failed

1. **Comprehensive Hooks** (~30s) - Thorough analysis without retry

   - Type checking (Zuban/mypy via LSP)
   - Security scanning (Bandit)
   - Complexity analysis
   - Dead code detection (Skylos)
   - **Retry Policy**: Run once, collect all issues

### Hook Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                    Crackerjack Workflow                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
        ┌──────────────────────────────────┐
        │  Phase 1: Fast Hooks (~5s)       │
        │  • Formatters (Ruff, etc.)       │
        │  • Import sorting                │
        │  • Retry once on failure         │
        └──────────────────────────────────┘
                            │
                            ▼
                   ┌────────────────┐
                   │ Formatting Fix? │
                   └────────────────┘
                     │            │
                   Yes           No
                     │            │
                     ▼            ▼
              ┌──────────┐   ┌──────────┐
              │ Retry    │   │ Continue │
              │ Fast     │   │          │
              │ Hooks    │   │          │
              └──────────┘   └──────────┘
                     │            │
                     └─────┬──────┘
                           ▼
        ┌──────────────────────────────────┐
        │  Phase 2: Test Suite             │
        │  • Collect ALL failures          │
        │  • Don't stop on first error     │
        │  • Parallel execution (xdist)    │
        └──────────────────────────────────┘
                           │
                           ▼
        ┌──────────────────────────────────┐
        │  Phase 3: Comprehensive Hooks    │
        │  • Type checking (LSP)           │
        │  • Security scanning             │
        │  • Complexity analysis           │
        │  • Collect ALL issues            │
        └──────────────────────────────────┘
                           │
                           ▼
                 ┌──────────────────┐
                 │ All Issues Found? │
                 └──────────────────┘
                     │            │
                   Yes           No
                     │            │
                     ▼            ▼
              ┌──────────┐   ┌──────────┐
              │ AI Batch │   │ Success! │
              │ Fixing   │   │          │
              │ (if      │   │          │
              │ enabled) │   │          │
              └──────────┘   └──────────┘
```

## Hook Implementations

### LSP Hook (`lsp_hook.py`)

LSP-aware type checking hook that communicates with running Zuban LSP server:

**Features:**

- **Fast Type Checking** - Uses running LSP server (no process spawn overhead)
- **Incremental Analysis** - Checks only modified files when possible
- **Fallback Support** - Falls back to direct Zuban execution if LSP unavailable
- **Smart Caching** - Leverages LSP server's incremental compilation cache

**Benefits:**

- 10-20x faster than spawning separate type checker process
- Real-time feedback during development
- Shared analysis state with IDE
- Reduced memory usage (single server process)

**Usage:**

```python
from crackerjack.hooks.lsp_hook import main as lsp_hook_main

# Run LSP-aware type checking
exit_code = lsp_hook_main(console=console)
```

## Hook Definitions

Hooks are defined in `/home/user/crackerjack/crackerjack/config/hooks.py`:

### HookDefinition Attributes

```python
@dataclass
class HookDefinition:
    name: str  # Hook identifier
    command: list[str]  # Command to execute
    timeout: int = 60  # Execution timeout (seconds)
    stage: HookStage = FAST  # FAST or COMPREHENSIVE
    description: str | None  # Human-readable description
    retry_on_failure: bool  # Auto-retry if failed
    is_formatting: bool  # Is this a formatter?
    manual_stage: bool  # Manual pre-commit stage
    config_path: Path | None  # Custom config file path
    security_level: SecurityLevel  # CRITICAL, HIGH, MEDIUM, LOW
    use_precommit_legacy: bool  # Use pre-commit wrapper
    accepts_file_paths: bool  # Accepts individual file paths
```

### HookStrategy

Groups hooks with execution strategy:

```python
@dataclass
class HookStrategy:
    name: str  # Strategy name
    hooks: list[HookDefinition]  # Hooks to execute
    timeout: int = 300  # Total timeout
    retry_policy: RetryPolicy = NONE  # Retry behavior
    parallel: bool = False  # Parallel execution
    max_workers: int = 3  # Max parallel workers
```

### Hook Stages

```python
class HookStage(Enum):
    FAST = "fast"  # Fast hooks (~5s)
    COMPREHENSIVE = "comprehensive"  # Comprehensive hooks (~30s)
```

### Retry Policies

```python
class RetryPolicy(Enum):
    NONE = "none"  # No retry
    FORMATTING_ONLY = "formatting_only"  # Retry formatters only
    ALL_HOOKS = "all_hooks"  # Retry all hooks
```

### Security Levels

```python
class SecurityLevel(Enum):
    CRITICAL = "critical"  # Security-critical hooks
    HIGH = "high"  # High-priority checks
    MEDIUM = "medium"  # Standard checks
    LOW = "low"  # Low-priority checks
```

## Creating Custom Hooks

### Method 1: Add to Hook Definitions

```python
# In crackerjack/config/hooks.py
from crackerjack.config.hooks import HookDefinition, HookStage, SecurityLevel

CUSTOM_HOOK = HookDefinition(
    name="my-custom-check",
    command=["python", "-m", "my_tool", "check"],
    timeout=120,
    stage=HookStage.COMPREHENSIVE,
    description="Custom quality check",
    retry_on_failure=False,
    security_level=SecurityLevel.MEDIUM,
    use_precommit_legacy=False,  # Direct invocation
    accepts_file_paths=True,  # Can process individual files
)
```

### Method 2: LSP-Aware Hook

For tools with LSP support:

```python
#!/usr/bin/env python3
"""LSP-aware hook for custom tool."""

import sys
from pathlib import Path
from acb.console import Console
from crackerjack.services.lsp_client import LSPClient


def main(console: Console | None = None) -> int:
    console = console or Console()
    files_to_check = sys.argv[1:] if len(sys.argv) > 1 else []

    lsp_client = LSPClient()

    if not lsp_client.is_server_running():
        # Fallback to direct tool execution
        return run_tool_directly(files_to_check)

    # Use LSP server for checking
    diagnostics = lsp_client.get_diagnostics(files_to_check)

    if diagnostics:
        for diag in diagnostics:
            console.print(f"[red]✗[/red] {diag.file}:{diag.line}: {diag.message}")
        return 1

    console.print("[green]✓[/green] All checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Method 3: Pre-commit Integration

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: my-custom-check
        name: My Custom Check
        entry: python -m my_tool check
        language: system
        types: [python]
        pass_filenames: true
        stages: [manual]  # For comprehensive stage
```

## Hook Execution Patterns

### Sequential Execution

```python
from crackerjack.executors import HookExecutor
from acb.depends import depends

executor = depends.get(HookExecutor)

# Execute hooks sequentially
result = await executor.execute_strategy(strategy_name="fast_hooks", parallel=False)
```

### Parallel Execution

```python
# Execute compatible hooks in parallel
result = await executor.execute_strategy(
    strategy_name="comprehensive_hooks", parallel=True, max_workers=4
)
```

### Selective Execution

```python
# Execute specific hooks
result = await executor.execute_hooks(
    hooks=["ruff-format", "ruff-check"], stage=HookStage.FAST
)
```

### Incremental Execution (File-Targeted)

```python
from pathlib import Path

# Only check modified files
modified_files = [Path("src/main.py"), Path("tests/test_main.py")]

result = await executor.execute_hooks_on_files(
    hooks=["ruff-check", "mypy"], files=modified_files
)
```

## Configuration

Hooks are configured through ACB Settings:

```yaml
# settings/crackerjack.yaml

# Hook execution
skip_hooks: false                # Skip all hooks
hooks_parallel: true             # Parallel hook execution
max_parallel_hooks: 4            # Max parallel workers
hook_timeout: 300                # Global hook timeout (seconds)

# Fast hooks configuration
fast_hooks_enabled: true
fast_hooks_timeout: 60
fast_hooks_retry: true           # Auto-retry on failure

# Comprehensive hooks configuration
comprehensive_hooks_enabled: true
comprehensive_hooks_timeout: 180
comprehensive_hooks_retry: false # Don't retry (collect all issues)

# LSP integration
lsp_enabled: true
lsp_fallback: true               # Fallback to direct execution
lsp_server_startup_timeout: 30

# Hook-specific overrides
hook_overrides:
  ruff-format:
    timeout: 120
  zuban-lsp:
    use_lsp: true
    fallback_command: ["zuban", "check", "src"]
```

## Usage Examples

### Basic Hook Execution

```python
from crackerjack.executors import HookExecutor
from pathlib import Path

# Initialize executor
executor = HookExecutor(console=console, pkg_path=Path.cwd(), verbose=True)

# Run fast hooks
fast_result = await executor.execute_strategy("fast_hooks")

if fast_result.success:
    print("✅ Fast hooks passed")
else:
    print(f"❌ {fast_result.failed_count} fast hooks failed")

# Run comprehensive hooks
comp_result = await executor.execute_strategy("comprehensive_hooks")
```

### LSP-Aware Type Checking

```bash
# Command-line usage
python -m crackerjack.hooks.lsp_hook src/main.py tests/test_main.py

# Or check all project files
python -m crackerjack.hooks.lsp_hook
```

### Custom Hook Strategy

```python
from crackerjack.config.hooks import HookStrategy, HookDefinition, RetryPolicy

custom_strategy = HookStrategy(
    name="security-audit",
    hooks=[
        HookDefinition(
            name="bandit",
            command=["bandit", "-r", "src"],
            timeout=180,
            security_level=SecurityLevel.CRITICAL,
        ),
        HookDefinition(
            name="safety",
            command=["safety", "check"],
            timeout=60,
            security_level=SecurityLevel.HIGH,
        ),
    ],
    timeout=300,
    retry_policy=RetryPolicy.NONE,
    parallel=True,
    max_workers=2,
)

# Execute custom strategy
result = await executor.execute_custom_strategy(custom_strategy)
```

## Integration with Executors

Hooks are executed by specialized executors (see [Executors](../executors/README.md)):

- **HookExecutor** - Base executor with sequential execution
- **AsyncHookExecutor** - Asynchronous hook execution
- **CachedHookExecutor** - Caching for repeated executions
- **ProgressHookExecutor** - Progress tracking and reporting
- **LSPAwareHookExecutor** - LSP-aware execution optimization

## Best Practices

1. **Use Two-Stage Model** - Separate fast and comprehensive hooks for optimal workflow
1. **Enable LSP** - Use LSP integration for 10-20x faster type checking
1. **Retry Formatters** - Enable auto-retry for formatting hooks only
1. **Collect All Issues** - Don't fail fast in comprehensive stage
1. **Parallel Execution** - Enable parallel execution for independent hooks
1. **Set Appropriate Timeouts** - Configure per-hook timeouts based on codebase size
1. **Use Incremental Execution** - Target only modified files when possible
1. **Security Levels** - Assign appropriate security levels for prioritization
1. **Cache Results** - Use CachedHookExecutor for repeated runs
1. **Monitor Performance** - Track hook execution times and optimize slow hooks

## Performance Optimization

### LSP vs Direct Execution

```
Traditional (direct tool invocation):
  Type checking: ~30-60s per run
  Memory: ~500MB per process
  Startup overhead: ~2-5s

LSP-aware (persistent server):
  Type checking: ~2-5s per run (10-20x faster)
  Memory: ~500MB shared across all checks
  Startup overhead: ~0s (server already running)
```

### Caching Strategy

```python
from crackerjack.executors import CachedHookExecutor

cached_executor = CachedHookExecutor(
    console=console,
    pkg_path=pkg_path,
    cache_ttl=3600,  # 1 hour cache
)

# First run: Full execution
result1 = await cached_executor.execute_strategy("fast_hooks")

# Subsequent runs: Cached results for unchanged files
result2 = await cached_executor.execute_strategy("fast_hooks")
print(f"Cache hit rate: {result2.cache_hit_rate:.1%}")
```

## Related

- [Executors](../executors/README.md) - Hook execution engines

- [Config](../config/README.md) - Hook configuration and definitions

- [CLAUDE.md](../../docs/guides/CLAUDE.md) - Two-stage quality process documentation

## Future Enhancements

- [ ] DAG-based hook dependency resolution
- [ ] Real-time hook execution monitoring dashboard
- [ ] Machine learning for hook execution optimization
- [ ] Distributed hook execution across multiple machines
- [ ] Hook execution profiling and bottleneck detection
- [ ] Custom hook plugin system with discovery

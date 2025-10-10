# Phase 10.4: Hook Configuration Fixes - Implementation Plan

## Overview

Phase 10.4 addresses hook configuration issues and integrates the Phase 10.3 optimization infrastructure (ToolProfiler, IncrementalExecutor, ToolFilter) into the hook execution system.

## Current State Analysis

### ✅ Strengths

- All hooks migrated to direct invocation (`use_precommit_legacy=False`)
- Clean separation between FAST_HOOKS and COMPREHENSIVE_HOOKS
- Tool command registry (`tool_commands.py`) provides centralized command definitions
- Security levels assigned to all hooks
- Retry policies configured for formatting hooks

### ⚠️ Issues Identified

1. **Timeout Inconsistencies**

   - `zuban`: 30s (COMPREHENSIVE) vs `bandit`: 300s (COMPREHENSIVE)
   - `refurb`, `creosote`: 300s (seems excessive for modern Rust tools)
   - No profiling data to justify timeout values

1. **Command Mismatches**

   - `.pre-commit-config.yaml` line 12: `entry: skylos`
   - `tool_commands.py` line 24: `["uv", "run", "skylos", "check", "crackerjack"]`
   - Inconsistent argument patterns

1. **Missing Phase 10.3 Integration**

   - Hooks don't use `ToolProfiler` for baseline metrics
   - No `IncrementalExecutor` for file-level caching
   - No `ToolFilter` for `--tool` and `--changed-only` support
   - Hook execution doesn't benefit from optimization infrastructure

1. **File Path Handling**

   - Direct invocation commands don't accept file path arguments
   - No way to pass changed files to tools for targeted execution
   - All tools run on entire codebase every time

1. **Execution Order**

   - FAST_HOOKS run sequentially without optimization
   - No priority-based ordering (run fastest tools first for fast feedback)

## Implementation Strategy

### Sub-Phase 10.4.1: Timeout Calibration ✅

**Goal**: Use ToolProfiler to establish realistic timeout values based on actual execution data.

**Tasks**:

1. Run ToolProfiler on all hooks to collect baseline metrics
1. Calculate 95th percentile execution times
1. Set timeouts to 3x P95 (safety margin for slower systems)
1. Update `hooks.py` with calibrated values
1. Add comments documenting the profiling data source

**Expected Outcomes**:

- Data-driven timeout values
- Faster failure detection for hung tools
- Reduced total execution time (no waiting for unnecessarily long timeouts)

### Sub-Phase 10.4.2: Command Harmonization ✅

**Goal**: Ensure `.pre-commit-config.yaml` and `tool_commands.py` are consistent.

**Tasks**:

1. Audit all hook commands for discrepancies
1. Fix skylos command mismatch
1. Standardize argument patterns (all tools use same style)
1. Ensure exclude patterns are consistent
1. Update tests to validate command consistency

**Expected Outcomes**:

- Single source of truth for tool commands
- No surprises when switching between pre-commit and direct invocation
- Easier maintenance (update in one place)

### Sub-Phase 10.4.3: Phase 10.3 Infrastructure Integration ✅

**Goal**: Wire ToolProfiler, IncrementalExecutor, and ToolFilter into hook execution.

**Architecture**:

```python
# New hook execution flow

class EnhancedHookExecutor:
    def __init__(self):
        self.profiler = ToolProfiler()
        self.executor = IncrementalExecutor()
        self.filter = ToolFilter(config=FilterConfig(...), executor=self.executor)

    def execute_hooks(
        self,
        hooks: list[HookDefinition],
        *,
        tool_filter: str | None = None,  # --tool flag
        changed_only: bool = False,       # --changed-only flag
        file_patterns: list[str] | None = None,
    ) -> list[HookResult]:
        # 1. Filter tools
        if tool_filter or changed_only or file_patterns:
            filter_config = FilterConfig(
                tool_name=tool_filter,
                changed_only=changed_only,
                file_patterns=file_patterns or [],
            )
            tool_filter_obj = ToolFilter(config=filter_config, executor=self.executor)
            tool_result = tool_filter_obj.filter_tools([h.name for h in hooks])
            hooks = [h for h in hooks if h.name in tool_result.filtered_tools]

        # 2. Profile execution
        results = []
        for hook in hooks:
            def run_hook():
                # Execute hook with incremental executor
                # ...

            self.profiler.profile_tool(hook.name, run_hook)
            results.append(...)

        # 3. Generate report
        summary = self.profiler.generate_report()
        filter_summary = tool_filter_obj.generate_filter_summary(tool_result=tool_result)
        # Combine and display

        return results
```

**Tasks**:

1. Create `EnhancedHookExecutor` class integrating all Phase 10.3 services
1. Update `WorkflowOrchestrator` to use `EnhancedHookExecutor`
1. Wire `--tool` CLI flag to `ToolFilter.tool_name`
1. Wire `--changed-only` CLI flag to `ToolFilter.changed_only`
1. Implement file path passing to tools that support it
1. Add performance reporting at end of hook execution
1. Write integration tests

**Expected Outcomes**:

- 50-90% reduction in execution time with `--changed-only`
- Instant feedback with `--tool ruff-check`
- Performance baselines tracked automatically
- Filter effectiveness metrics displayed

### Sub-Phase 10.4.4: File Path Handling ✅

**Goal**: Enable tools to receive filtered file paths for targeted execution.

**Tool Categories**:

1. **File-level tools** (can process individual files): ruff, bandit, codespell
1. **Project-level tools** (must run on entire project): zuban, skylos, creosote
1. **Formatting tools** (modify files in place): ruff-format, trailing-whitespace

**Implementation**:

```python
# Add to HookDefinition
@dataclass
class HookDefinition:
    # ... existing fields ...
    accepts_file_paths: bool = False  # NEW: Can tool process individual files?

    def build_command(self, files: list[Path] | None = None) -> list[str]:
        """Build command with optional file paths."""
        base_cmd = self.command.copy()

        if files and self.accepts_file_paths:
            base_cmd.extend([str(f) for f in files])

        return base_cmd
```

**Tasks**:

1. Add `accepts_file_paths` field to `HookDefinition`
1. Mark file-level tools: ruff-check, ruff-format, bandit, codespell, mdformat
1. Implement `build_command()` method
1. Update `EnhancedHookExecutor` to pass filtered files
1. Add tests for file path handling

**Expected Outcomes**:

- Targeted execution on changed files only
- Faster iteration during development
- Reduced resource usage

### Sub-Phase 10.4.5: Execution Optimization ✅

**Goal**: Optimize hook execution order and parallelization based on profiling data.

**Strategy**:

1. **Fast-First Ordering**: Run fastest tools first for quick feedback

   - Sort FAST_HOOKS by profiled execution time
   - Surface failures early (fail fast principle)

1. **Parallel Execution**: Run independent tools in parallel

   - Formatting tools can run in parallel (ruff-check + ruff-format + mdformat)
   - Analysis tools can run in parallel (zuban + bandit + skylos)

**Implementation**:

```python
def optimize_hook_order(
    hooks: list[HookDefinition], profiler: ToolProfiler
) -> list[HookDefinition]:
    """Sort hooks by execution time (fastest first)."""

    def get_exec_time(hook: HookDefinition) -> float:
        if hook.name in profiler.results:
            return profiler.results[hook.name].mean_time
        return 999.0  # Unknown tools run last

    return sorted(hooks, key=get_exec_time)
```

**Tasks**:

1. Implement `optimize_hook_order()` function
1. Update FAST_STRATEGY to use optimized ordering
1. Implement parallel execution for independent tools
1. Add `--parallel` / `--serial` CLI flags for user control
1. Write tests for optimization logic

**Expected Outcomes**:

- 30-50% reduction in wall-clock time with parallel execution
- Faster feedback (failures detected in first 5 seconds instead of 30 seconds)
- Better CPU utilization

## Testing Strategy

### Unit Tests

- `test_timeout_calibration.py`: Verify timeout calculations
- `test_command_harmonization.py`: Validate command consistency
- `test_enhanced_hook_executor.py`: Test integrated execution
- `test_file_path_handling.py`: Test file path passing
- `test_execution_optimization.py`: Test ordering and parallelization

### Integration Tests

- `test_tool_filter_integration.py`: End-to-end filtering
- `test_incremental_execution.py`: Cache-based file skipping
- `test_profiler_integration.py`: Metrics collection

### Performance Tests

- Baseline execution time (no optimization)
- With caching (changed files only)
- With filtering (single tool)
- With parallel execution
- Target: 70%+ improvement over baseline

## Success Criteria

1. **Correctness**: All hooks execute correctly with new infrastructure
1. **Performance**: 70%+ improvement in execution time with optimizations enabled
1. **Usability**: `--tool` and `--changed-only` work seamlessly
1. **Maintainability**: Single source of truth for hook commands
1. **Visibility**: Performance metrics displayed after execution

## Migration Path

### Phase 1: Infrastructure (Week 1)

- Sub-phase 10.4.1: Timeout calibration
- Sub-phase 10.4.2: Command harmonization

### Phase 2: Integration (Week 2)

- Sub-phase 10.4.3: Phase 10.3 integration
- Sub-phase 10.4.4: File path handling

### Phase 3: Optimization (Week 3)

- Sub-phase 10.4.5: Execution optimization
- Performance testing and tuning

## Risk Mitigation

1. **Breaking Changes**: Feature flag `--legacy-hooks` to revert to old behavior
1. **Performance Regressions**: Comprehensive benchmarking before/after
1. **Cache Correctness**: Extensive testing of cache invalidation logic
1. **Parallel Execution Bugs**: Start with serial by default, opt-in to parallel

## Dependencies

- ✅ Phase 10.3.1: ToolProfiler (baseline metrics)
- ✅ Phase 10.3.2: IncrementalExecutor (file caching)
- ✅ Phase 10.3.3: ToolFilter (selective execution)

## Next Steps

After Phase 10.4 completion:

- Phase 10.5: Developer Experience Improvements
- Phase 10.6: Documentation & Polish

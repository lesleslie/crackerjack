# Progress Bar Implementation - Complete

## Summary

Successfully implemented a **compact Rich progress bar** that respects the configured 70-character console width for hook execution.

## What Changed

### 1. Console Width Configuration (`workflows/container_builder.py`)

```python
# Console width is now set during DI container initialization
self._console.width = get_console_width()  # Returns 70 from settings
```

**Key Points:**

- Console width configured from `CrackerjackSettings.console.width` (default: 70)
- Can be overridden in `settings/local.yaml`, `settings/crackerjack.yaml`, or `pyproject.toml`
- Rich Progress automatically respects console width
- **No environment variables needed** - all in Crackerjack config

### 2. Progress Callback System

**Flow:**

```
PhaseCoordinator._execute_hooks_once()
  ↓ sets _progress_callback on hook_manager
HookManager.run_fast_hooks()
  ↓ passes callback to orchestrator
HookOrchestrator.execute_strategy()
  ↓ passes callback to adaptive strategy
AdaptiveExecutionStrategy.execute()
  ↓ calls callback(completed, total) after each wave
PhaseCoordinator updates Rich Progress bar
```

**Modified Files:**

1. `workflows/container_builder.py` - Set console width
1. `orchestration/strategies/adaptive_strategy.py` - Added progress_callback parameter
1. `orchestration/hook_orchestrator.py` - Thread callback through
1. `managers/hook_manager.py` - Pass callback from \_progress_callback attribute
1. `core/phase_coordinator.py` - Create progress bar and set callback

### 3. Compact Progress Bar Format

```
⠋ Running fast hooks... ━━━━━╸━━━ 7/11 0:00:32
```

**Components:**

- `⠋` - Animated spinner (dots style)
- `Running fast hooks...` - Dynamic description
- `━━━━━╸━━━` - Progress bar (fixed 20-char width)
- `7/11` - Completed/total hooks
- `0:00:32` - Elapsed time

**Properties:**

- `transient=False` - Bar remains visible after completion for context
- `bar_width=20` - Fixed narrow width to prevent console overflow
- Updates after each wave of parallel hooks completes

**Width Constraint Fix** (crackerjack/executors/progress_hook_executor.py:121):

- Previously used `bar_width=None` which could overflow console width
- Now uses `bar_width=20` to ensure progress bar + all columns fit within 70 chars
- Description + bar + counters + time = ~60 chars max (safe for 70-char console)

## Console Width Configuration

Users can configure width in three places (priority order):

### 1. `settings/local.yaml` (highest priority, gitignored)

```yaml
console:
  width: 80
```

### 2. `settings/crackerjack.yaml` (project default)

```yaml
console:
  width: 70
```

### 3. `pyproject.toml` (fallback)

```toml
[tool.crackerjack]
terminal_width = 70
```

## Implementation Details

### Progress Updates

Progress is reported **after each wave** of hooks completes:

```python
# Wave 1 (parallel): gitleaks, zuban, ruff-format
# → callback(3, 11)

# Wave 2 (parallel): bandit, refurb
# → callback(5, 11)

# Wave 3 (sequential): mypy
# → callback(6, 11)
```

**Why wave-based?**

- Hooks run in parallel within waves (dependency-aware batching)
- Can't report individual hook completion in real-time without race conditions
- Wave completion is a clean synchronization point
- Still provides meaningful progress feedback (vs. 46 seconds of silence)

### Compatibility

- **ACB mode**: Full progress bar support ✅
- **Legacy mode**: No progress bar (uses existing pre-commit output)
- **Orchestration disabled**: No progress bar (uses ProgressHookExecutor if configured)

## Testing

To test the progress bar:

```bash
# Fast hooks only
python -m crackerjack run

# Full workflow with progress
python -m crackerjack run -c -t -p minor
```

**Expected behavior:**

1. Shows header: `🔍 Fast Hooks - Formatters, import sorting, and quick static analysis`
1. Shows progress bar: `⠋ Running fast hooks... ━━━━━╸━━━ 7/11 [32s]`
1. Progress bar updates as waves complete
1. Progress bar disappears, final summary shown

## Known Limitations

1. **Progress granularity**: Updates per wave, not per hook

   - Wave can have multiple hooks running in parallel
   - Progress jumps (e.g., 0→3→5→11 for 3 waves)
   - This is intentional for ACB's parallel execution model

1. **No progress for legacy mode**:

   - Legacy mode bypasses orchestrator
   - Uses pre-commit CLI directly
   - Could add ProgressHookExecutor support later if needed

1. **Width only set at startup**:

   - Console width configured during container build
   - Changing `settings.yaml` mid-execution won't update width
   - Restart Crackerjack to pick up new width setting

## Future Enhancements

### Potential Improvements (Not Implemented)

1. **Per-hook progress** (complex):

   - Would need thread-safe progress updates from parallel hooks
   - Might cause flickering/overlapping output
   - Current wave-based approach is cleaner

1. **Multiple progress bars** (one per wave):

   - Show which hooks are running in current wave
   - More complex but more detailed
   - Might exceed 70-char width easily

1. **ETA calculation**:

   - Add `TimeRemainingColumn` to progress bar
   - Requires historical timing data
   - Not critical for short-running hooks

1. **ACB core integration**:

   - Move console width to ACB's Console constructor
   - Would benefit all ACB users
   - Requires upstream changes

## Is This an ACB Feature?

**Current implementation**: Purely Crackerjack-side ✅

**Should it be in ACB?**

- Console width configuration: Yes, could be in ACB

  - `Console(width=70)` would be cleaner
  - ACB Console already supports width property
  - Would need ACB update to accept width in constructor

- Progress callbacks: Maybe

  - Generic enough for other ACB workflows
  - But progress model varies by application
  - Crackerjack's wave-based model is specific to hooks

**Recommendation**:

- Keep progress bar in Crackerjack (application-specific)
- Propose console width constructor parameter to ACB (general utility)
- File issue: `acb.console.Console(width=70)` for configurable console width

## Conclusion

✅ **Implemented**: Compact progress bar respecting 70-char console width
✅ **No env vars needed**: All configuration via Crackerjack settings
✅ **Clean integration**: No ACB changes required
✅ **User configurable**: Three levels of configuration (local, project, pyproject)

The progress bar provides meaningful feedback during the 46-second execution gap while maintaining clean, readable output within the configured terminal width.

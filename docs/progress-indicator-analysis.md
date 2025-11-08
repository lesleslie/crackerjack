# Progress Indicator Analysis and Recommendations

## Current State

### What You're Seeing
When running `python -m crackerjack -c -t -p minor`, you see:
```
⏳ Started: Fast quality checks

----------------------------------------------------------------------
🔍 Fast Hooks - Formatters, import sorting, and quick static analysis
----------------------------------------------------------------------


✅ Fast hooks attempt 1: 11/11 passed in 46.16s.
```

**Problem**: There's a **46-second gap** with no visible progress between the header and the final summary. This is where hooks are running but providing no feedback.

### Why This Happens

The execution flow is:
1. `WorkflowOrchestrator._run_fast_hooks_phase()` → calls phases
2. `PhaseCoordinator.run_fast_hooks_only()` → shows header, calls hook_manager
3. `HookManager.run_fast_hooks()` → detects orchestration enabled, calls orchestrator
4. `HookOrchestrator.execute_strategy()` → executes in ACB mode (no progress output)
5. `PhaseCoordinator._report_hook_results()` → shows final summary

**The gap**: Steps 4 (ACB orchestrator) doesn't display any progress during execution.

### Architecture Context

**ACB Mode (Current):**
- `crackerjack/orchestration/hook_orchestrator.py:351` - `_execute_acb_mode()`
- Uses `AdaptiveExecutionStrategy` for dependency-aware parallel execution
- Calls hooks directly via adapters (not pre-commit CLI)
- **No console output during execution** (only logging)

**Legacy Mode (Old, has progress):**
- `crackerjack/executors/progress_hook_executor.py` - `ProgressHookExecutor`
- Uses Rich progress bars during execution
- Shows real-time hook status updates
- **Currently BYPASSED** when orchestration is enabled

## Options Analysis

### Option 1: Restore Old-Style Hook-by-Hook Output
**What users want**: See each hook as it runs:
```
⏳ Started: Fast quality checks
----------------------------------------------------------------------
🔍 Fast Hooks - Formatters, import sorting, and quick static analysis
----------------------------------------------------------------------

Running validate-regex-patterns... ✅ 3.72s
Running trailing-whitespace... ✅ 3.82s
Running end-of-file-fixer... ✅ 3.53s
Running ruff-check... ✅ 0.18s
...
```

**Difficulty**: HARD - Requires significant refactoring
- ACB orchestrator uses async batch execution with adaptive strategies
- Hooks can run in parallel (dependency-aware batching)
- Real-time line-by-line output conflicts with parallel execution model
- Would need to add callback system to orchestrator to report progress

**Implementation Path**:
1. Add progress callback to `AdaptiveExecutionStrategy.execute()`
2. Thread-safe console writing from parallel tasks
3. Handle overlapping output from concurrent hooks
4. Estimated effort: 4-6 hours

### Option 2: Rich Progress Bar (Recommended)
**What it looks like**:
```
⏳ Started: Fast quality checks
----------------------------------------------------------------------
🔍 Fast Hooks - Formatters, import sorting, and quick static analysis
----------------------------------------------------------------------

⠋ Running 11 hooks... ━━━━━━━━━━━━━━━━╸━━━━━━━━━━━━━━━━ 7/11 [00:32<00:14]
```

**Difficulty**: MEDIUM - Cleaner implementation
- Progress bar respects console width automatically (Rich built-in)
- Already has implementation in `ProgressHookExecutor`
- Needs integration with ACB orchestrator's async execution

**Implementation Path**:
1. Add progress callback to `HookOrchestrator._execute_acb_mode()`
2. Use Rich `Progress` with console width from settings
3. Update progress in callbacks from adaptive strategy
4. Estimated effort: 2-3 hours

**Console Width Handling**: Already solved! ✅
- `crackerjack/config/settings.py:82` - `ConsoleSettings.width = 70`
- Rich Progress respects console width automatically via `Console` object
- `PhaseCoordinator` already creates console with proper width

### Option 3: Simple Spinner (Easiest)
**What it looks like**:
```
⏳ Started: Fast quality checks
----------------------------------------------------------------------
🔍 Fast Hooks - Formatters, import sorting, and quick static analysis
----------------------------------------------------------------------

⠋ Running hooks... (46.2s elapsed)
```

**Difficulty**: EASY
- Just show a spinner while hooks run
- No detailed progress, just "something is happening"
- Estimated effort: 30 minutes

## Console Width Configuration

### Current Implementation ✅
The console width is **already properly configured** and will be respected by any progress indicator:

**Settings**:
```python
# crackerjack/config/settings.py:79-82
class ConsoleSettings(Settings):
    """Console/UI related settings."""
    width: int = 70
```

**Usage**:
```python
# crackerjack/utils/console_utils.py
def separator(char: str = "-", width: int | None = None) -> str:
    w = width if isinstance(width, int) and width > 0 else get_console_width()
    return char * w
```

**Rich Integration**:
- Rich `Progress` automatically respects the `Console` width setting
- `PhaseCoordinator` already has the console with proper width
- No changes needed in ACB - it's purely a Crackerjack configuration

### Configuration Files
Users can override console width in:

1. **`settings/local.yaml`** (gitignored):
   ```yaml
   console:
     width: 80  # Custom width
   ```

2. **`settings/crackerjack.yaml`** (committed):
   ```yaml
   console:
     width: 70  # Default
   ```

3. **`pyproject.toml`**:
   ```toml
   [tool.crackerjack.console]
   width = 70
   ```

## Recommendation

**Go with Option 2: Rich Progress Bar**

### Why?
1. **Clean integration**: Works naturally with ACB's async execution
2. **Console width**: Already respects configured width (70 chars)
3. **User experience**: Better than nothing, good enough for most users
4. **Implementation**: Moderate effort, clean code
5. **No ACB changes**: Purely Crackerjack-side implementation

### What it Won't Do
- Won't show individual hook names as they run (parallel execution makes this messy)
- Won't show hook-specific timing until completion

### What it Will Do
- Show real-time progress (7/11 hooks complete)
- Show elapsed time and ETA
- Respect 70-character console width
- Work with parallel execution
- Provide visual feedback during the 46-second gap

## Implementation Plan (Option 2)

### Phase 1: Add Progress Callback System
**File**: `crackerjack/orchestration/hook_orchestrator.py`

Add optional progress callback parameter:
```python
async def _execute_acb_mode(
    self,
    strategy: HookStrategy,
    progress_callback: Callable[[int, int], None] | None = None
) -> list[HookResult]:
    # ... existing code ...

    if self.settings.enable_adaptive_execution:
        results = await execution_strategy.execute(
            hooks=strategy.hooks,
            executor_callable=self._execute_single_hook,
            progress_callback=progress_callback,  # NEW
        )
```

### Phase 2: Update Adaptive Strategy
**File**: `crackerjack/orchestration/strategies/adaptive_strategy.py`

Add progress reporting:
```python
async def execute(
    self,
    hooks: list[HookDefinition],
    executor_callable: Callable,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[HookResult]:
    # ... existing code ...

    # After each hook completes
    if progress_callback:
        progress_callback(completed_count, total_count)
```

### Phase 3: Integrate with PhaseCoordinator
**File**: `crackerjack/core/phase_coordinator.py`

Add progress bar wrapper:
```python
from rich.progress import Progress, SpinnerColumn, BarColumn, ...

def _execute_hooks_once(
    self,
    suite_name: str,
    hook_runner: Callable[[], list[HookResult]],
    options: OptionsProtocol,
    attempt: int,
) -> bool:
    # Create progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=self.console,  # Respects width setting
    ) as progress:
        task = progress.add_task(
            f"Running {suite_name} hooks...",
            total=None,  # Unknown until we start
        )

        # Callback to update progress
        def update_progress(completed: int, total: int):
            progress.update(task, completed=completed, total=total)

        # Pass callback to hook_manager
        hook_results = hook_runner(progress_callback=update_progress)
```

### Phase 4: Thread Through Hook Manager
**File**: `crackerjack/managers/hook_manager.py`

```python
def run_fast_hooks(
    self,
    progress_callback: Callable[[int, int], None] | None = None
) -> list[HookResult]:
    if self.orchestration_enabled:
        return asyncio.run(
            self._run_fast_hooks_orchestrated(progress_callback)
        )
    # ... legacy path ...

async def _run_fast_hooks_orchestrated(
    self,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[HookResult]:
    # ... existing code ...
    return await self._orchestrator.execute_strategy(
        strategy,
        progress_callback=progress_callback,
    )
```

## Estimated Timeline

- **Option 1** (Old-style output): 4-6 hours (complex async handling)
- **Option 2** (Progress bar): 2-3 hours (recommended)
- **Option 3** (Simple spinner): 30 minutes (minimal value)

## Questions to Clarify

1. **Is the progress bar acceptable** instead of hook-by-hook output?
2. **Should we show hook names** during execution (requires more complex implementation)?
3. **Fallback to spinner** if progress bar is too complex?

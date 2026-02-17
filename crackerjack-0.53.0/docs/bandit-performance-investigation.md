# Bandit Performance Investigation

## Summary

Investigation into three issues reported during comprehensive hook execution:

1. **Bandit taking 765s** to execute (abnormally slow)
1. **"JSON parse failed, falling back to text parsing"** message appearing
1. **Total elapsed time calculation** summing individual hook durations instead of wall-clock time

## Issue 1: Bandit 765s Execution Time

### Current Configuration

**Tool Command** (`crackerjack/config/tool_commands.py:139-147`):

```python
"bandit": [
    "uv",
    "run",
    "python",
    "-m",
    "bandit",
    "-r",  # Recursive scan
    f"./{package_name}",  # Target only the package directory
],
```

**Hook Definition** (`crackerjack/config/hooks.py:261-269`):

```python
(
    HookDefinition(
        name="bandit",
        command=[],
        timeout=1200,  # 20 minutes
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.CRITICAL,
        use_precommit_legacy=False,  # Direct invocation
        accepts_file_paths=True,
    ),
)
```

### Root Cause Analysis

The bandit adapter has **contradictory configuration**:

**Adapter Settings** (`crackerjack/adapters/security/bandit.py:163-176`):

```python
def build_command(self, files, config=None):
    cmd = [self.tool_name]

    if self.settings.recursive:
        cmd.append("-r")

    # Use HIGH severity and confidence
    cmd.extend(["-lll"])  # Highest severity level
    cmd.extend(["-iii"])  # Highest confidence level

    # Skip specific test IDs (7 rules skipped)
    skip_rules = ["B101", "B110", "B112", "B311", "B404", "B603", "B607"]
    cmd.extend(["-s", ",".join(skip_rules)])

    # JSON output
    if self.settings.use_json_output:
        cmd.extend(["-f", "json"])

    # Add targets
    cmd.extend([str(f) for f in files])
```

**BUT** the tool command registry doesn't use the adapter's `build_command()` method - it directly invokes bandit with minimal flags:

```bash
uv run python -m bandit -r ./crackerjack
```

This means bandit is scanning with **default settings**:

- ✅ Recursive scan (`-r`)
- ❌ No severity filtering (scans ALL severity levels instead of just HIGH)
- ❌ No confidence filtering (reports ALL confidence levels instead of just HIGH)
- ❌ No rule skipping (runs ALL ~100+ security checks)
- ❌ No JSON output format (uses text output)

### Performance Impact

**Expected behavior** (with adapter flags):

- High severity only: ~10-20 potential issues
- High confidence only: ~5-10 potential issues
- 7 rules skipped: Eliminates common false positives
- Execution time: ~10-30s

**Actual behavior** (without adapter flags):

- All severity levels: ~100+ potential issues
- All confidence levels: ~200+ potential issues
- All ~100+ security checks running
- Execution time: **765s (12.75 minutes)**

### Why is This Happening?

The tool was migrated from pre-commit hooks to direct invocation (Phase 8.4), but the **adapter's filtering logic was not integrated** into the tool command registry.

The adapter has all the performance optimizations:

- High severity/confidence filters
- Rule exclusions
- JSON output parsing

But `tool_commands.py` bypasses the adapter entirely.

## Issue 2: "JSON parse failed, falling back to text parsing"

### Location

The message appears at `crackerjack/adapters/security/bandit.py:222`:

```python
try:
    data = json.loads(result.raw_output)
    logger.debug("Parsed Bandit JSON output", ...)
except json.JSONDecodeError as e:
    logger.warning(
        "JSON parse failed, falling back to text parsing",
        extra={"error": str(e), "output_preview": result.raw_output[:200]},
    )
    return self._parse_text_output(result.raw_output)
```

### Root Cause

This is **directly caused by Issue #1**. The tool command doesn't include `-f json`, so bandit outputs text format instead of JSON:

```bash
# Current command (no JSON flag)
uv run python -m bandit -r ./crackerjack

# Expected command (with JSON flag)
uv run python -m bandit -r -lll -iii -s B101,B110,... -f json ./crackerjack
```

When the adapter tries to parse JSON output that doesn't exist, it falls back to text parsing.

### Impact

- **Performance**: Text parsing is less efficient than JSON parsing
- **Accuracy**: Text parsing is more brittle and may miss issues
- **Structured Data**: Loses detailed metadata (confidence levels, line ranges, URLs)

## Issue 3: Total Elapsed Time Calculation

### Current Implementation

**Hook Manager** (`crackerjack/managers/hook_manager.py:469`):

```python
def _calculate_summary(self, results: list[HookResult]) -> dict[str, t.Any]:
    passed = sum(1 for r in results if r.status == "passed")
    failed = sum(1 for r in results if r.status == "failed")
    errors = sum(1 for r in results if r.status in ("timeout", "error"))
    total_duration = sum(r.duration for r in results)  # ⚠️ WRONG FOR PARALLEL

    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "total_duration": total_duration,  # Reports sum of durations
        "success_rate": (passed / len(results)) * 100 if results else 0,
    }
```

**Async Hook Manager** (`crackerjack/managers/async_hook_manager.py:107`):

```python
total_duration = sum(r.duration for r in results)  # ⚠️ SAME ISSUE
```

### Why This is Wrong

For **parallel execution**, summing individual hook durations gives **cumulative CPU time**, not **wall-clock elapsed time**.

Example from your output:

```
❌ Comprehensive hooks attempt 1: 7/8 passed in 928.75s (1 failed, 0 errors).

Hook durations (parallel execution):
- check-jsonschema:  5.22s
- zuban:             1.77s
- gitleaks:          0.20s
- skylos:            8.59s
- refurb:          114.88s
- creosote:         31.52s
- bandit:          765.78s
- complexipy:        0.79s
─────────────────────────────
Sum:               928.75s  ← WRONG (this is what's reported)
```

But these ran in **parallel**, so the actual elapsed time was closer to **765.78s** (the longest-running hook), not 928.75s.

### Correct Implementation

The parallel executor already calculates this correctly:

**Parallel Executor** (`crackerjack/services/parallel_executor.py:204, 229`):

```python
async def _execute_with_groups(...):
    start_time = time.time()

    # ... execute hooks in parallel ...

    total_duration = time.time() - start_time  # ✅ CORRECT: wall-clock time

    return ParallelExecutionResult(
        total_duration_seconds=total_duration,
        ...
    )
```

### Impact

- **User Confusion**: Reported time doesn't match actual experience
- **Performance Metrics**: Skewed analytics (makes parallel execution look slower than it is)
- **Progress Tracking**: Misleading progress estimates

## Recommendations

### 1. Fix Bandit Configuration (HIGH PRIORITY)

**Option A: Use Adapter's build_command()** (Recommended)

Modify `tool_commands.py` to use the adapter:

```python
# In crackerjack/config/tool_commands.py
def get_tool_command(hook_name: str, pkg_path: Path) -> list[str]:
    """Get command for hook, using adapter if available."""

    # Special handling for adapter-based tools
    if hook_name == "bandit":
        from crackerjack.adapters.security.bandit import BanditAdapter, BanditSettings

        adapter = BanditAdapter(settings=BanditSettings())
        # Build command with proper flags
        return adapter.build_command(files=[pkg_path / "crackerjack"])

    # ... existing logic for other tools
```

**Option B: Hard-code Optimized Command** (Quick fix)

```python
"bandit": [
    "uv", "run", "python", "-m", "bandit",
    "-r",                    # Recursive
    "-lll",                  # High severity only
    "-iii",                  # High confidence only
    "-s", "B101,B110,B112,B311,B404,B603,B607",  # Skip common false positives
    "-f", "json",            # JSON output
    f"./{package_name}",
],
```

**Expected Performance Improvement**: **765s → 10-30s** (~25-75x faster)

### 2. Fix Total Duration Calculation (MEDIUM PRIORITY)

The hook managers need to receive and use the wall-clock time from the executor:

```python
# In HookManager/AsyncHookManager
def run_comprehensive_hooks(self) -> tuple[list[HookResult], float]:
    """Return results AND elapsed time."""
    start_time = time.time()

    if self.orchestration_enabled:
        results = asyncio.run(self._run_comprehensive_hooks_orchestrated())
    else:
        execution_result = self.executor.execute_strategy(strategy)
        results = execution_result.results

    elapsed_time = time.time() - start_time
    return results, elapsed_time


def _calculate_summary(self, results, elapsed_time: float | None = None):
    # ... existing logic ...

    # Use provided elapsed time if available (parallel), otherwise sum (sequential)
    total_duration = (
        elapsed_time if elapsed_time is not None else sum(r.duration for r in results)
    )

    return {
        # ... existing fields ...
        "total_duration": total_duration,
    }
```

### 3. Remove Redundant JSON Parse Warning (LOW PRIORITY)

Once bandit uses JSON output consistently, the fallback warning will stop appearing.

Alternatively, make it DEBUG level instead of WARNING:

```python
except json.JSONDecodeError as e:
    logger.debug(  # Changed from warning to debug
        "JSON parse failed, falling back to text parsing",
        ...
    )
```

## Testing Plan

1. **Test bandit with optimized flags**:

   ```bash
   time uv run python -m bandit -r -lll -iii -s B101,B110,B112,B311,B404,B603,B607 -f json ./crackerjack
   ```

1. **Verify parallel timing**:

   ```bash
   python -m crackerjack run  # Should show wall-clock time, not sum
   ```

1. **Check JSON parsing**:

   ```bash
   # Should see no "JSON parse failed" messages in logs
   python -m crackerjack run --verbose
   ```

## Files to Modify

1. `crackerjack/config/tool_commands.py` - Fix bandit command
1. `crackerjack/managers/hook_manager.py` - Fix duration calculation
1. `crackerjack/managers/async_hook_manager.py` - Fix duration calculation
1. `crackerjack/adapters/security/bandit.py` - (Optional) Reduce log level

## References

- Bandit adapter: `crackerjack/adapters/security/bandit.py`
- Tool commands: `crackerjack/config/tool_commands.py:139-147`
- Hook definitions: `crackerjack/config/hooks.py:261-269`
- Parallel executor: `crackerjack/services/parallel_executor.py:204, 229`
- Hook managers: `crackerjack/managers/hook_manager.py:469`, `async_hook_manager.py:107`

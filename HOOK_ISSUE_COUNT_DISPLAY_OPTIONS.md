# Hook Issue Count Display Options

## Current Problem

After the fix, hooks show truthful issue counts:

```
ruff-format    FAILED   0.05s      0    ← Confusing: why FAILED with 0 issues?
codespell      FAILED   0.03s      0    ← Confusing: why FAILED with 0 issues?
ruff-check     FAILED   0.15s      95   ← Clear: 95 code violations
```

**User Question**: Can we show config errors differently (colored number, 'x', etc.)?

## Design Options

### Option 1: Use Symbol for Config Errors (Recommended)

Show a distinct symbol in the Issues column for config/tool errors:

```
┌──────────────┬────────┬──────────┬────────┐
│ Hook         │ Status │ Duration │ Issues │
├──────────────┼────────┼──────────┼────────┤
│ ruff-format  │ FAILED │ 0.05s    │ ⚠️      │  ← Config error symbol
│ codespell    │ FAILED │ 0.03s    │ ⚠️      │  ← Config error symbol
│ complexipy   │ PASSED │ 2.50s    │ 0      │  ← Normal: no issues
│ ruff-check   │ FAILED │ 0.15s    │ 95     │  ← Normal: 95 violations
└──────────────┴────────┴──────────┴────────┘
```

**Symbol Choices**:

- `⚠️` (warning triangle) - Clear, recognizable
- `✗` (cross) - Simple, indicates failure
- `⚙️` (gear) - Suggests config/tool issue
- `!` (exclamation) - Alert indicator
- `ERR` (text) - Explicit but takes more space

**Pros**:

- ✅ Immediately obvious it's not a code issue count
- ✅ Doesn't require counting or mental math
- ✅ Works well with Rich's emoji support
- ✅ Consistent with UX patterns (symbols for special states)

**Cons**:

- ⚠️ Requires symbol font support (but Rich handles this)
- ⚠️ Screen readers might need special handling

**Implementation**:

```python
# In phase_coordinator.py _create_summary_table()
if result.status == "passed":
    issues_display = 0
else:
    if hasattr(qa_result, "status") and qa_result.status == QAResultStatus.ERROR:
        issues_display = "⚠️"  # Config/tool error
    else:
        issues_display = result.issues_count  # Code violations
```

______________________________________________________________________

### Option 2: Colored Numbers with Suffix

Use color + text suffix to distinguish error types:

```
┌──────────────┬────────┬──────────┬────────────┐
│ Hook         │ Status │ Duration │ Issues     │
├──────────────┼────────┼──────────┼────────────┤
│ ruff-format  │ FAILED │ 0.05s    │ 0 (err)    │  ← Yellow/orange
│ codespell    │ FAILED │ 0.03s    │ 0 (err)    │  ← Yellow/orange
│ complexipy   │ PASSED │ 2.50s    │ 0          │  ← White
│ ruff-check   │ FAILED │ 0.15s    │ 95         │  ← Bright white/red
└──────────────┴────────┴──────────┴────────────┘
```

**Color Scheme**:

- **Yellow/Orange** for config errors: `[yellow]0 (err)[/yellow]`
- **Red** for code violations: `[red]95[/red]`
- **White** for passed: `0`

**Pros**:

- ✅ Still shows numeric "0" for clarity
- ✅ Color-blind friendly with suffix
- ✅ Explains what the "0" means

**Cons**:

- ⚠️ More verbose
- ⚠️ Suffix might be too subtle

**Implementation**:

```python
if result.status == "passed":
    issues_display = "0"
else:
    if hasattr(qa_result, "status") and qa_result.status == QAResultStatus.ERROR:
        issues_display = "[yellow]0 (err)[/yellow]"
    else:
        issues_display = f"[red]{result.issues_count}[/red]"
```

______________________________________________________________________

### Option 3: Two-Column Issues Display

Split the Issues column into "Code" and "Config" sub-columns:

```
┌──────────────┬────────┬──────────┬─────────────┐
│ Hook         │ Status │ Duration │ Issues      │
│              │        │          │ Code │ Cfg  │
├──────────────┼────────┼──────────┼──────┼──────┤
│ ruff-format  │ FAILED │ 0.05s    │  0   │  1   │
│ codespell    │ FAILED │ 0.03s    │  0   │  1   │
│ complexipy   │ PASSED │ 2.50s    │  0   │  0   │
│ ruff-check   │ FAILED │ 0.15s    │ 95   │  0   │
└──────────────┴────────┴──────────┴──────┴──────┘
```

**Pros**:

- ✅ Very explicit separation
- ✅ Easy to scan both types
- ✅ Numeric for both (easier comparison)

**Cons**:

- ⚠️ Takes more horizontal space
- ⚠️ Adds complexity to the table
- ⚠️ Might be overkill for rare config errors

______________________________________________________________________

### Option 4: Colored Background Highlight

Use background colors to distinguish error types:

```
┌──────────────┬────────┬──────────┬────────┐
│ Hook         │ Status │ Duration │ Issues │
├──────────────┼────────┼──────────┼────────┤
│ ruff-format  │ FAILED │ 0.05s    │   0    │  ← Yellow bg
│ codespell    │ FAILED │ 0.03s    │   0    │  ← Yellow bg
│ complexipy   │ PASSED │ 2.50s    │   0    │  ← Normal
│ ruff-check   │ FAILED │ 0.15s    │  95    │  ← Red bg
└──────────────┴────────┴──────────┴────────┘
```

**Pros**:

- ✅ Color-coded for quick scanning
- ✅ Doesn't change the number format
- ✅ Works with existing Rich styling

**Cons**:

- ⚠️ Background colors can be hard to read
- ⚠️ Might clash with terminal themes
- ⚠️ Less accessible

**Implementation**:

```python
if result.status == "passed":
    issues_display = "0"
else:
    if hasattr(qa_result, "status") and qa_result.status == QAResultStatus.ERROR:
        issues_display = "[on yellow]0[/on yellow]"  # Yellow background
    else:
        issues_display = f"[on red]{result.issues_count}[/on red]"  # Red background
```

______________________________________________________________________

### Option 5: Negative Number for Config Errors (Novel)

Use negative numbers to indicate config errors (e.g., -1 = config error):

```
┌──────────────┬────────┬──────────┬────────┐
│ Hook         │ Status │ Duration │ Issues │
├──────────────┼────────┼──────────┼────────┤
│ ruff-format  │ FAILED │ 0.05s    │  -1    │  ← Config error
│ codespell    │ FAILED │ 0.03s    │  -1    │  ← Config error
│ complexipy   │ PASSED │ 2.50s    │   0    │  ← No issues
│ ruff-check   │ FAILED │ 0.15s    │  95    │  ← 95 violations
└──────────────┴────────┴──────────┴────────┘
```

**Pros**:

- ✅ Still numeric (sortable, comparable)
- ✅ Visually distinct from 0
- ✅ Convention: negative = error state

**Cons**:

- ⚠️ Non-intuitive (what does -1 mean?)
- ⚠️ Requires documentation/tooltip
- ⚠️ Might confuse users

______________________________________________________________________

## Recommendation: Option 1 (Symbol) + Tooltip

**Best UX**: Use a symbol with a tooltip/legend:

```
┌──────────────┬────────┬──────────┬────────┐
│ Hook         │ Status │ Duration │ Issues │
├──────────────┼────────┼──────────┼────────┤
│ ruff-format  │ FAILED │ 0.05s    │ ⚠️      │
│ codespell    │ FAILED │ 0.03s    │ ⚠️      │
│ complexipy   │ PASSED │ 2.50s    │ 0      │
│ ruff-check   │ FAILED │ 0.15s    │ 95     │
└──────────────┴────────┴──────────┴────────┘

Legend: ⚠️ = Configuration/tool error
```

**Alternative Symbols**:

- `⚠️` (Warning) - Most universal
- `⚙️` (Gear) - Suggests config issue
- `❌` (Red X) - Error indicator
- `🔧` (Wrench) - Tool problem
- `⚡` (Bolt) - System issue

**Implementation Locations**:

1. **`crackerjack/core/phase_coordinator.py:643-660`** (display logic)
1. **`crackerjack/orchestration/hook_orchestrator.py:939-975`** (data preparation)

**Code Changes**:

```python
# In phase_coordinator.py
for result in results:
    status_style = self._status_style(result.status)

    if result.status == "passed":
        issues_display = "0"
    else:
        # Check if this is a config/tool error
        if self._is_config_error(result):
            issues_display = "⚠️"  # Config error symbol
        else:
            # Code violations
            issues_display = str(result.issues_count)

    table.add_row(
        self._strip_ansi(result.name),
        f"[{status_style}]{result.status.upper()}[/{status_style}]",
        f"{result.duration:.2f}s",
        issues_display,
    )

# Add footer note if any config errors found
if any(self._is_config_error(r) for r in results):
    console.print("\n[dim]⚠️ = Configuration or tool error (not code issues)[/dim]")
```

______________________________________________________________________

## Hybrid Approach: Contextual Display

Show different formats based on context:

**In Summary Table** (space-constrained):

```
Issues: ⚠️   (symbol only)
```

**In Detailed Output** (verbose):

```
Issues: 0 (config error: invalid configuration file)
```

**In JSON/API** (programmatic):

```json
{
  "issues_count": 0,
  "issue_type": "config_error",
  "error_category": "invalid_configuration"
}
```

______________________________________________________________________

## User Preference Configuration

Add a config option to let users choose their preferred display:

```yaml
# settings/crackerjack.yaml
display:
  config_error_indicator: "symbol"  # Options: symbol, text, count, colored
  config_error_symbol: "⚠️"         # Customizable symbol
  show_config_error_legend: true    # Show legend below table
```

______________________________________________________________________

## Accessibility Considerations

For users with visual impairments or terminal limitations:

1. **Text Alternative**: `ERR` or `CFG` instead of symbols
1. **Screen Reader Hint**: Use aria-label equivalent in Rich
1. **Color-Blind Safe**: Don't rely on color alone (use symbol + color)
1. **High Contrast Mode**: Ensure symbols are visible in all terminal themes

______________________________________________________________________

## Final Recommendation

**Implement Option 1 with these enhancements**:

1. **Primary**: Use `⚠️` symbol for config errors
1. **Fallback**: Add `(err)` suffix if terminal doesn't support emoji
1. **Legend**: Show legend footer if any config errors present
1. **Config**: Allow users to customize via settings
1. **Accessibility**: Provide text alternative in `--verbose` mode

**Example Output**:

```
Fast Hooks Results:
┌──────────────┬────────┬──────────┬────────┐
│ Hook         │ Status │ Duration │ Issues │
├──────────────┼────────┼──────────┼────────┤
│ ruff-format  │ FAILED │ 0.05s    │ ⚠️      │
│ codespell    │ FAILED │ 0.03s    │ ⚠️      │
│ ruff-check   │ FAILED │ 0.15s    │ 95     │
│ complexipy   │ PASSED │ 2.50s    │ 0      │
└──────────────┴────────┴──────────┴────────┘

⚠️ = Configuration or tool error (not code issues)

Details:
- ruff-format: Invalid configuration file (check pyproject.toml)
- codespell: Binary not found in PATH
```

This provides:

- ✅ Clear visual distinction
- ✅ No confusion about "0 issues" meaning
- ✅ Accessible (symbol + text legend)
- ✅ Customizable
- ✅ Detailed error info still available

Would you like me to implement this option?

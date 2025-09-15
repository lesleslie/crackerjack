# Zuban TOML Parsing Bug Analysis

## Problem Summary

Zuban v0.0.22 has a critical TOML parsing bug that causes it to panic when trying to parse the `[tool.mypy]` section in `pyproject.toml`, even though the configuration is perfectly valid TOML.

**Error Message:**

```
thread 'main' panicked at crates/zmypy/src/lib.rs:291:27:
Problem parsing Mypy config: Expected tool.mypy to be simple table in pyproject.toml
```

## Analysis

### 1. TOML Structure is Correct

Our mypy configuration is a standard "simple table" in TOML spec:

```toml
[tool.mypy]
python_version = "3.13"
strict = true
ignore_missing_imports = true
show_error_codes = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

This is **NOT** a complex table and should be parsed without issues.

### 2. Root Cause

The bug is in Zuban's Rust TOML parser at `crates/zmypy/src/lib.rs:291:27`. The parser incorrectly:

1. **Always attempts to parse MyPy config** even for native `zuban check` commands
1. **Misidentifies simple tables** as complex tables
1. **Panics instead of graceful error handling** (anti-pattern in Rust)

### 3. Impact Assessment

- **Blocking**: Cannot use Zuban for type checking in crackerjack
- **Widespread**: Affects both `zuban mypy` and `zuban check` commands
- **Critical**: Panic crash instead of recoverable error

### 4. Evidence

Testing confirms the issue persists across multiple scenarios:

- ✗ Default pyproject.toml parsing
- ✗ Explicit `--config-file` specification
- ✗ Separate mypy.ini file creation
- ✗ Minimal TOML structure
- ✗ Native `zuban check` mode (should not parse mypy config)

## Resolution Strategy

### Immediate (Local Workaround)

1. **Disable Zuban temporarily** in crackerjack configuration
1. **Fall back to pyright** for type checking
1. **Update adapter to handle failure gracefully**

### Short-term (Upstream Fix)

1. **Report bug to Zuban maintainers** with minimal reproduction case
1. **Propose patch** for graceful error handling
1. **Version pin until fix** is available

### Long-term (Architecture)

1. **Implement tool health checking** in adapters
1. **Add graceful degradation** patterns
1. **Consider alternative Rust type checkers** as backup

## Code Changes Required

### 1. Disable Zuban in Config

```toml
[tool.crackerjack]
zuban_lsp_enabled = false  # Temporarily disable
```

### 2. Update Adapter Error Handling

```python
def check_tool_health(self) -> bool:
    """Check if tool is functional before use."""
    try:
        result = subprocess.run(
            ["uv", "run", "zuban", "--version"], capture_output=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False
```

### 3. Graceful Fallback

```python
async def check_with_lsp_or_fallback(self, target_files: list[Path]) -> ToolResult:
    if not self.check_tool_health():
        return self._create_error_result(
            "Zuban is not functional, falling back to pyright"
        )
    # ... existing logic
```

## Testing

### Minimal Reproduction Case

```bash
# Create minimal project
mkdir test-zuban-bug
cd test-zuban-bug
echo '[tool.mypy]\npython_version = "3.13"' > pyproject.toml
echo 'def test() -> None: pass' > test.py

# This should work but crashes
uv run zuban mypy .
```

## Next Steps

1. ✅ **Fixed adapter command**: `zmypy` → `mypy`
1. 🔄 **Implement graceful fallback** to pyright
1. 📝 **Report upstream bug** with reproduction case
1. 🛠️ **Update crackerjack config** to disable temporarily

## Expected Timeline

- **Immediate**: Fallback implementation (1 hour)
- **Short-term**: Upstream bug report (1 day)
- **Long-term**: Upstream fix available (1-4 weeks)

This is clearly a **Zuban parsing bug**, not an issue with our TOML structure.

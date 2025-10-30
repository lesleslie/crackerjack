# Migration Guide: Dependency Groups Modernization (v0.41.0)

## Breaking Change

Crackerjack v0.41.0 removes self-reference from `[dependency-groups]` following modern UV and PEP 735 standards.

## What Changed

### Self-Reference Removed

**Before (v0.40.3)**:

```toml
[dependency-groups]
dev = [
    "crackerjack",  # ❌ Self-reference
    "excalidraw-mcp>=0.34.0",
    "session-mgmt-mcp>=0.4.0",
]
```

**After (v0.41.0)**:

```toml
[dependency-groups]
dev = [
    "excalidraw-mcp>=0.34.0",
    "session-mgmt-mcp>=0.4.0",
]
```

## Why This Change?

1. **Eliminates Circular Dependencies**: Self-references create unnecessary complexity
1. **UV Best Practices**: Modern UV doesn't require self-installation in dev groups
1. **Consistency**: Aligns with ACB v0.24.0+ dependency group standards
1. **Cleaner Installation**: Separates tool installation from development dependencies

## Migration Steps

### 1. Update Installation

No changes required for normal installation:

```bash
# Install crackerjack
uv add crackerjack

# Install dev dependencies
uv add --group dev
```

### 2. Reinstall Dev Dependencies (Optional)

If you had issues with the old structure:

```bash
# Clean cache
uv cache clean

# Remove old installation
uv remove crackerjack

# Reinstall
uv add crackerjack
uv add --group dev
```

## Impact

**Low Impact** - This change only affects development dependency installation and does not change any functionality or APIs.

- ✅ No code changes required
- ✅ No configuration changes required
- ✅ Existing installations continue to work
- ✅ Only affects fresh installs with `--group dev`

## Questions?

- See the main [README.md](<./README.md>) for installation examples
- Check [CHANGELOG.md](<./CHANGELOG.md>) for detailed release notes

______________________________________________________________________

**Version**: 0.41.0
**Migration Difficulty**: Very Low (structural only)
**Estimated Time**: 1 minute

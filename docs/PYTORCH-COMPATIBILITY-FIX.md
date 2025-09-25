# PyTorch Dependency Compatibility Fix

## Problem Analysis

The semantic search implementation in crackerjack requires `sentence-transformers`, which depends on PyTorch. However, PyTorch 2.8.0 doesn't have wheels available for `macosx_26_0_x86_64` (Intel Mac with macOS 15+).

**Current Error:**

```
error: Distribution `torch==2.8.0 @ registry+https://pypi.org/simple` can't be installed because it doesn't have a source distribution or wheel for the current platform

hint: You're on macOS (`macosx_26_0_x86_64`), but `torch` (v2.8.0) only has wheels for the following platforms: `manylinux_2_28_aarch64`, `manylinux_2_28_x86_64`, `macosx_11_0_arm64`, `win_amd64`
```

## Available PyTorch Versions

PyTorch 2.7.0 and earlier have broader platform support including Intel Macs. PyTorch 2.8.0 appears to have dropped Intel Mac support.

## Solution Strategy

1. **Constrain PyTorch version** to 2.7.x which has compatible wheels
1. **Update pyproject.toml** with explicit PyTorch constraint
1. **Configure UV** for compatibility if needed
1. **Test semantic search** implementation with compatible PyTorch

## Implementation Steps

1. Add explicit PyTorch version constraint to `pyproject.toml`
1. Update sentence-transformers dependency
1. Add UV platform configuration if needed
1. Test installation and semantic search functionality
1. Run comprehensive tests to validate compatibility

## Expected Outcome

- PyTorch 2.7.x installation successful on Intel Mac
- sentence-transformers working with compatible PyTorch version
- Semantic search implementation functional
- All tests passing

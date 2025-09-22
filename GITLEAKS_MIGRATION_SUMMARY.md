# Detect-Secrets to Gitleaks Migration Summary

## Overview
As part of our ongoing security improvements, we've migrated from `detect-secrets` to `gitleaks` for secret detection in the Crackerjack project. This change aligns with our commitment to using modern, actively maintained security tools.

## Changes Made

### 1. Code Updates
- **`crackerjack/executors/cached_hook_executor.py`**: Updated the `should_use_cache_for_hook` method to reference `gitleaks` instead of `detect-secrets` in the external hooks set.
- **`crackerjack/orchestration/execution_strategies.py`**: Updated priority hook selection logic to use `gitleaks` instead of `detect-secrets` when processing setup.py and pyproject.toml files.

### 2. Documentation Updates
- **`docs/systems/CACHING_SYSTEM.md`**: Removed the outdated `detect-secrets` entry from the caching TTL table and ensured only `gitleaks` is listed for secret detection.

### 3. Configuration Updates
- **`.pre-commit-config.yaml`**: Already properly configured with `gitleaks` as the secret detection tool.

## Verification
- All source code references to `detect-secrets` have been removed
- All references to `gitleaks` are consistent throughout the codebase
- Configuration files properly reference `gitleaks`
- Documentation has been updated to reflect the change

## Benefits of Migration
1. **Active Maintenance**: Gitleaks is actively maintained with regular updates
2. **Better Performance**: Gitleaks offers superior performance compared to detect-secrets
3. **Enhanced Detection**: Gitleaks has a more comprehensive ruleset for secret detection
4. **Community Support**: Larger community and better documentation
5. **Integration**: Better integration with modern development workflows

This migration ensures that our secret detection capabilities remain strong while using the best available tooling in the ecosystem.
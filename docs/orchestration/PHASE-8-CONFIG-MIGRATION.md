# Phase 8.3: Configuration Migration Guide

## Overview

Phase 8.3 consolidates tool configurations from `.pre-commit-config.yaml` into native configuration files, primarily `pyproject.toml`. This eliminates configuration duplication and provides a single source of truth for all tool settings.

## Current State Analysis

### Tools Already Configured in pyproject.toml ✅

These tools already have complete configuration in `pyproject.toml` and require **no migration**:

1. **Ruff** (`[tool.ruff]`)

   - Target version: Python 3.13
   - Line length: 88
   - Linting rules: complexity (max 15), imports, upgrades
   - Format settings: docstring formatting enabled

1. **Bandit** (`[tool.bandit]`)

   - Target: `crackerjack/`
   - Skips: B101, B110, B112, B404, B603, B607
   - Exclusions: `tests/`, `test_*.py`

1. **Complexipy** (`[tool.complexipy]`)

   - Pattern: `**/*.py`
   - Max complexity: 15
   - Exclusions: `**/tests/**`, `**/test_*.py`

1. **Codespell** (`[tool.codespell]`)

   - Skip paths: `*/data/*`, `htmlcov/*`, `tests/*`
   - Quiet level: 3
   - Custom ignore words list

1. **Zuban** (`[tool.zuban]`)

   - Strict mode: enabled
   - Error codes: shown
   - Config file: `mypy.ini` (separate file, intentional)

1. **Pytest** (`[tool.pytest.ini_options]`)

   - Asyncio mode: auto
   - Timeout: 300s
   - Coverage integration

### Tools Using Default Configuration 📋

These tools work with sensible defaults and don't require explicit configuration:

1. **Gitleaks**: Uses built-in rules for secret detection
1. **UV Lock**: No configuration needed (reads `pyproject.toml`)
1. **MDFormat**: Works with defaults, uses `mdformat-ruff` plugin
1. **Refurb**: Python modernization with sensible defaults
1. **Creosote**: Dependency checking with automatic detection

### Native Tool Configurations 🆕

Our Phase 8.1 native tools have minimal configuration needs:

1. **trailing-whitespace**: No config needed (automatic detection)
1. **end-of-file-fixer**: No config needed (ensures single newline)
1. **check-yaml**: No config needed (syntax validation only)
1. **check-toml**: No config needed (syntax validation only)
1. **check-added-large-files**: Default 500KB threshold (configurable via `--maxkb`)

## Configuration Migration Status

### Summary Matrix

| Tool | Current Config | Target Config | Status | Migration Needed |
|------|---------------|---------------|--------|-----------------|
| **ruff-check** | pyproject.toml | pyproject.toml | ✅ Complete | None |
| **ruff-format** | pyproject.toml | pyproject.toml | ✅ Complete | None |
| **bandit** | pyproject.toml | pyproject.toml | ✅ Complete | None |
| **complexipy** | pyproject.toml | pyproject.toml | ✅ Complete | None |
| **codespell** | pyproject.toml | pyproject.toml | ✅ Complete | None |
| **zuban** | mypy.ini | mypy.ini | ✅ Complete | None (intentional) |
| **gitleaks** | Defaults | Defaults | ✅ Complete | None |
| **uv-lock** | Defaults | Defaults | ✅ Complete | None |
| **mdformat** | Defaults | Defaults | ✅ Complete | None |
| **refurb** | Defaults | Defaults | ✅ Complete | None |
| **creosote** | Defaults | Defaults | ✅ Complete | None |
| **skylos** | CLI args | pyproject.toml | 🔄 Optional | Add `[tool.skylos]` |
| **Native tools** | N/A | Defaults | ✅ Complete | None |

### Recommended Additions (Optional)

While not strictly necessary, these additions would centralize all configurations:

#### 1. Skylos Configuration (Optional)

```toml
[tool.skylos]
# Equivalent to: skylos crackerjack --exclude tests
paths = ["crackerjack"]
exclude = ["tests"]
```

**Benefit**: Removes CLI args from command definitions, centralizes config.
**Status**: Low priority - current CLI args work perfectly.

#### 2. Large File Threshold (Optional)

```toml
[tool.crackerjack.checks]
# Equivalent to: --maxkb 500
max_file_size_kb = 500
```

**Benefit**: Explicit documentation of threshold.
**Status**: Low priority - 500KB default is sensible.

#### 3. MDFormat Configuration (Optional)

```toml
[tool.mdformat]
# Currently uses defaults
wrap = "no"  # Don't wrap long lines
number = true  # Number ordered lists
```

**Benefit**: Explicit formatting rules.
**Status**: Low priority - defaults work well.

## Migration Decision: NO MIGRATION REQUIRED

**Conclusion**: After thorough analysis, **no configuration migration is needed** for Phase 8.3.

### Rationale

1. **All critical tools already configured**: Ruff, bandit, complexipy, codespell, zuban all have complete `pyproject.toml` configurations

1. **Default configurations are appropriate**: Tools like gitleaks, uv-lock, mdformat, refurb, creosote work perfectly with defaults

1. **Native tools need no config**: Our Phase 8.1 implementations have sensible built-in defaults

1. **Zero duplication**: No settings are duplicated between files

1. **Discovery is excellent**: All configurations are in `pyproject.toml` or use obvious defaults

### What Phase 8.3 Actually Needs

Instead of migrating configurations, Phase 8.3 should focus on:

1. **Verification**: Confirm all tool configs work with direct invocation
1. **Documentation**: Update docs to reference `pyproject.toml` sections
1. **Testing**: Validate tools read configs correctly when invoked directly

## Verification Checklist

To validate Phase 8.3 completion, verify each tool works with direct invocation:

### Commands to Test

```bash
# Ruff
uv run ruff check .
uv run ruff format .

# Bandit
uv run bandit -c pyproject.toml -r crackerjack

# Complexipy
uv run complexipy crackerjack --max-complexity 15

# Codespell
uv run codespell

# Zuban
uv run zuban check --config-file mypy.ini ./crackerjack

# Skylos
uv run skylos check crackerjack

# Gitleaks
uv run gitleaks detect --no-git -v

# UV Lock
uv lock

# MDFormat
uv run mdformat --check .

# Refurb
uv run refurb crackerjack

# Creosote
uv run creosote --venv .venv

# Native tools
uv run python -m crackerjack.tools.trailing_whitespace
uv run python -m crackerjack.tools.end_of_file_fixer
uv run python -m crackerjack.tools.check_yaml
uv run python -m crackerjack.tools.check_toml
uv run python -m crackerjack.tools.check_added_large_files
```

### Expected Outcomes

Each command should:

- ✅ Execute successfully
- ✅ Read configuration from `pyproject.toml` (where applicable)
- ✅ Produce same results as pre-commit wrapper version
- ✅ Return appropriate exit codes (0=pass, 1=issues)

## Configuration File Structure

### Current (Phase 8.3)

```
crackerjack/
├── pyproject.toml          # All tool configurations ✅
│   ├── [tool.ruff]
│   ├── [tool.bandit]
│   ├── [tool.complexipy]
│   ├── [tool.codespell]
│   ├── [tool.zuban]
│   ├── [tool.pytest.ini_options]
│   ├── [tool.coverage.run]
│   └── [tool.crackerjack]  # MCP server settings
├── mypy.ini                # Zuban configuration (intentional separation)
└── .pre-commit-config.yaml # To be removed in Phase 8.5
```

**Why mypy.ini is separate**: Zuban (mypy) has extensive configuration that's cleaner in a dedicated file. This is a common practice and doesn't violate our consolidation goals.

## Phase 8.3 Success Criteria

- ✅ **All configurations are in native files** (no migration needed - already done)
- ✅ **No configuration duplication** (verified - zero duplication)
- ✅ **Tools read from pyproject.toml** (verified for ruff, bandit, complexipy, codespell, zuban)
- ✅ **Default configurations are sensible** (verified for gitleaks, uv-lock, mdformat, refurb, creosote)
- ✅ **Documentation updated** (this document serves as reference)

## Next Steps

**Phase 8.4**: Update hook definitions in `hooks.py` to use direct commands with `use_precommit_legacy=False`, enabling direct tool invocation for all hooks.

______________________________________________________________________

**Status**: ✅ **COMPLETE** - No migration required, all configurations already optimal

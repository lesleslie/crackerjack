# Configuration Consolidation Audit

**Date:** 2025-11-16
**Scope:** Tool configuration files, pyproject.toml simplification, unused settings
**Status:** 🎯 Significant consolidation opportunities identified

______________________________________________________________________

## Executive Summary

Audit identified **12 consolidation opportunities** and **15+ redundant/unused settings** across configuration files. Primary recommendations:

1. **Eliminate mypy.ini** → Consolidate into pyproject.toml (saves 1 config file)
1. **Simplify gitleaksignore** → Can use crackerjack settings (optional)
1. **Remove duplicate pyright/mypy configs** in pyproject.toml
1. **Consolidate test worker settings** → Remove redundant config keys
1. **Simplify tool.refurb** → Remove duplicate test path ignores

**Impact:**

- ✅ Reduce from 5 config files to 3-4
- ✅ Remove ~30 lines of redundant configuration
- ✅ Single source of truth for all tool configs
- ✅ Easier maintenance and onboarding

______________________________________________________________________

## Current Configuration Inventory 📋

### Active Configuration Files

| File | Lines | Tools Configured | Can Consolidate? | Priority |
|------|-------|------------------|------------------|----------|
| `pyproject.toml` | 438 | 14 tools | ✅ Yes (simplify) | High |
| `mypy.ini` | 18 | mypy, zuban | ✅ Yes (eliminate) | **CRITICAL** |
| `.gitleaksignore` | 23 | gitleaks | ⚠️ Maybe | Low |
| `.codespell-ignore` | 3 | codespell | ✅ Yes (enhance) | Medium |
| `settings/crackerjack.yaml` | Variable | crackerjack | ✅ Yes (review) | Medium |

### Tools Configured in pyproject.toml

```toml
[tool.ruff]                  # ✅ Correct location
[tool.ruff.format]           # ✅ Correct location
[tool.ruff.lint]             # ✅ Correct location
[tool.codespell]             # ✅ Correct location
[tool.pytest.ini_options]    # ✅ Correct location
[tool.coverage.run]          # ✅ Correct location
[tool.coverage.report]       # ✅ Correct location
[tool.pyright]               # ✅ Correct location
[tool.creosote]              # ✅ Correct location
[tool.refurb]                # ✅ Correct location
[tool.bandit]                # ✅ Correct location
[tool.complexipy]            # ✅ Correct location
[tool.mypy]                  # ⚠️ DUPLICATE (also in mypy.ini)
[tool.zuban]                 # ✅ Correct location
[tool.crackerjack]           # ✅ Correct location
```

______________________________________________________________________

## Issue #1: CRITICAL - Duplicate mypy Configuration 🚨

### Problem

**mypy.ini exists but is SUPERSEDED by tool.mypy in pyproject.toml**

**Current State:**

```ini
# mypy.ini (18 lines)
[mypy]
python_version = 3.13
warn_unused_configs = False
warn_redundant_casts = False
warn_unused_ignores = False
ignore_missing_imports = True
show_error_codes = True
check_untyped_defs = False
disallow_untyped_defs = False
disallow_incomplete_defs = False
disallow_untyped_decorators = False
warn_return_any = False
warn_unreachable = False
follow_imports = "skip"
ignore_errors = False

[mypy-tests.*]
ignore_errors = True
```

**AND ALSO in pyproject.toml:**

```toml
[tool.mypy]
python_version = "3.13"
```

**Problem:**

- mypy/zuban read from `mypy.ini` (via `--config-file mypy.ini` flag)
- pyproject.toml has `[tool.mypy]` section that's **IGNORED**
- Configuration is **split between two files**
- Developers must edit two places

### Solution: Eliminate mypy.ini ✅

**Step 1:** Move all mypy.ini settings to pyproject.toml

```toml
[tool.mypy]
python_version = "3.13"
warn_unused_configs = false
warn_redundant_casts = false
warn_unused_ignores = false
ignore_missing_imports = true
show_error_codes = true
check_untyped_defs = false
disallow_untyped_defs = false
disallow_incomplete_defs = false
disallow_untyped_decorators = false
warn_return_any = false
warn_unreachable = false
follow_imports = "skip"
ignore_errors = false

[[tool.mypy.overrides]]
module = "tests.*"
ignore_errors = true
```

**Step 2:** Update zuban command in tool_commands.py

```python
# OLD:
"zuban": [
    "uv", "run", "zuban", "check",
    "--config-file", "mypy.ini",  # ❌ Remove this
    "--no-error-summary",
    f"./{package_name}",
],

# NEW:
"zuban": [
    "uv", "run", "zuban", "check",
    # No --config-file flag - reads from pyproject.toml automatically
    "--no-error-summary",
    f"./{package_name}",
],
```

**Step 3:** Delete mypy.ini

```bash
git rm mypy.ini
```

**Verification:**

Both mypy and zuban support reading from `[tool.mypy]` in pyproject.toml:

- **mypy**: Native support since v0.900
- **zuban**: As a mypy wrapper, inherits mypy's config discovery

**Benefits:**

- ✅ One less config file
- ✅ Single source of truth
- ✅ Better discoverability
- ✅ Follows PEP 518 standards

______________________________________________________________________

## Issue #2: Redundant Test Worker Settings ⚙️

### Problem

**Duplicate/redundant test parallelization settings:**

```toml
[tool.crackerjack]
# Test parallelization settings
test_workers = 0            # ✅ Keep - Primary config
auto_detect_workers = true  # ⚠️ REDUNDANT (implied by test_workers=0)
max_workers = 8             # ✅ Keep - Safety limit
min_workers = 2             # ⚠️ REDUNDANT (pytest-xdist doesn't use this)
memory_per_worker_gb = 2.0  # ✅ Keep - Safety feature
```

### Analysis

**auto_detect_workers is redundant:**

- When `test_workers = 0`, auto-detection is **implicit**
- Having both creates confusion: "What if test_workers=0 but auto_detect_workers=false?"

**min_workers is unused:**

- pytest-xdist doesn't support minimum worker config
- Crackerjack doesn't enforce this limit
- Value is never read in code

**Search confirmation:**

```bash
$ grep -r "min_workers\|auto_detect_workers" crackerjack/
# Returns: Only in config loading, never used in logic
```

### Solution: Simplify ✅

```toml
[tool.crackerjack]
# Test parallelization settings
test_workers = 0            # 0 = auto-detect, 1 = sequential, >1 = explicit, <0 = fractional
max_workers = 8             # Maximum parallel workers (safety limit)
memory_per_worker_gb = 2.0  # Minimum memory per worker (prevents OOM)
```

**Lines removed:** 2
**Clarity improved:** Yes - fewer knobs to understand

______________________________________________________________________

## Issue #3: Redundant Refurb Test Ignores 📝

### Problem

**Triple-redundant test path configuration:**

```toml
[tool.refurb]
enable_all = true
quiet = true
python_version = "3.13"
ignore = [
    "FURB184",
    "FURB120",
]

# ⚠️ REDUNDANT: Same ignore rules repeated 3 times
[[tool.refurb.amend]]
path = "tests"
ignore = ["FURB184", "FURB120"]

[[tool.refurb.amend]]
path = "test_*.py"
ignore = ["FURB184", "FURB120"]

[[tool.refurb.amend]]
path = "*_test.py"
ignore = ["FURB184", "FURB120"]
```

### Analysis

**Why it's redundant:**

1. Global `ignore` already applies to ALL files
1. Test files get the same ignore rules as non-test files
1. Three `amend` blocks add no additional value

**Refurb behavior:**

- Global `ignore` applies to **all paths**
- `amend` only needed if **different** rules for different paths

### Solution: Remove Redundant Amend Blocks ✅

```toml
[tool.refurb]
enable_all = true
quiet = true
python_version = "3.13"
ignore = [
    "FURB184",  # Applies to all files, including tests
    "FURB120",  # Applies to all files, including tests
]

# ✅ Removed 3 redundant [[tool.refurb.amend]] blocks
```

**Lines removed:** 18
**Behavior:** Identical (global ignore already covered test files)

______________________________________________________________________

## Issue #4: Pyright/Mypy Overlap 🔍

### Problem

**Both pyright and mypy configured, but zuban (mypy wrapper) is the active type checker:**

**pyproject.toml has extensive pyright config:**

```toml
[tool.pyright]
verboseOutput = true
include = ["crackerjack"]
exclude = [
    "scratch", ".venv", "*/.venv", "**/.venv",
    "build", "dist", "tests/*", "examples/*",
    "crackerjack/mcp/*", "crackerjack/plugins/*",
]
typeCheckingMode = "strict"
reportMissingTypeStubs = false
reportOptionalMemberAccess = false
# ... 15+ more report settings
pythonVersion = "3.13"
```

**But crackerjack uses zuban (mypy), not pyright:**

```python
# tool_commands.py
"zuban": ["uv", "run", "zuban", "check", "--config-file", "mypy.ini", ...]
```

**hooks.py uses zuban, not pyright:**

```python
(
    HookDefinition(
        name="zuban",  # ✅ Active type checker
        command=[],
        timeout=80,
        stage=HookStage.COMPREHENSIVE,
        security_level=SecurityLevel.HIGH,
        use_precommit_legacy=False,
    ),
)
```

### Analysis

**Questions:**

1. Is pyright config **used anywhere**?
1. Is it for IDE support (VS Code)?
1. Should it be kept for editor integration?

**Findings:**

```bash
$ grep -r "pyright" crackerjack/
# Returns: pyproject.toml config only, no execution code
```

**Conclusion:** Pyright config is **likely for VS Code IDE** support, NOT for CI/CD hooks.

### Solution: Document and Optionally Simplify ⚠️

**Option A: Keep for IDE Support (Recommended)**

Add comment to clarify:

```toml
# Type checking in CI/CD: zuban (mypy wrapper)
# Type checking in IDEs: pyright (VS Code, etc.)
[tool.pyright]
verboseOutput = true
include = ["crackerjack"]
exclude = [
    "scratch", ".venv", "tests/*", "examples/*",
    "crackerjack/mcp/*", "crackerjack/plugins/*",
]
typeCheckingMode = "strict"
pythonVersion = "3.13"
# Simplified: removed redundant report settings (use defaults)
```

**Option B: Remove If Not Used**

If team doesn't use VS Code or pyright:

```bash
# Remove entire [tool.pyright] section
# Lines removed: 35
```

**Recommendation:** Keep simplified version (Option A) for IDE support

______________________________________________________________________

## Issue #5: Creosote Exclude List 📦

### Problem

**Massive exclude-deps list (50+ packages):**

```toml
[tool.creosote]
paths = ["crackerjack"]
deps-file = "pyproject.toml"
exclude-deps = [
    # ... 50+ packages listed
    "hatchling", "pre-commit", "pytest", "pytest-asyncio",
    "pytest-cov", "pytest-mock", "pytest-xdist", "pytest-benchmark",
    "pyfiglet", "pyyaml", "uv", "tomli-w", "google-crc32c",
    # ... and many more
]
```

### Analysis

**Why so many excludes?**

- Development tools not imported in production code
- Test dependencies
- Build system tools
- Type stubs

**Problem:**

- Manual maintenance required
- Easy to forget to add new dev dependencies
- Clutters pyproject.toml

### Solution: Use Creosote Categories ✅

Creosote v4.1.0+ supports excluding by category:

```toml
[tool.creosote]
paths = ["crackerjack"]
deps-file = "pyproject.toml"

# Exclude entire categories instead of individual packages
exclude-categories = [
    "build-system",      # hatchling
    "dev-dependencies",  # dev group in pyproject.toml
    "test",              # pytest and plugins
    "types",             # type stubs (types-*)
]

# Only list exceptional packages that don't fit categories
exclude-deps = [
    "uv",          # CLI tool, not imported
    "pyfiglet",    # Optional import
    "tomli-w",     # Only in scripts
]
```

**Lines reduced:** 50+ → ~10

**Benefits:**

- ✅ Automatically excludes new test dependencies
- ✅ Automatically excludes new type stubs
- ✅ Less manual maintenance

______________________________________________________________________

## Issue #6: .codespell-ignore Empty 📝

### Problem

**Empty ignore file:**

```
# .codespell-ignore
# Project-specific codespell ignore words
# Add words here that should be ignored by codespell

```

**pyproject.toml config:**

```toml
[tool.codespell]
quiet-level = 3
ignore-words-list = "crate,uptodate,nd,nin"
ignore-words = ".codespell-ignore"  # ⚠️ Points to empty file
```

### Solution: Simplify ✅

**Option A: Keep File for Future Use**

Keep the file but update comment:

```
# .codespell-ignore
# Project-specific codespell ignore words
# Add words here that should be ignored by codespell
# Example: CompanyName, ProductName, etc.
```

**Option B: Remove File**

Remove file and update config:

```toml
[tool.codespell]
quiet-level = 3
ignore-words-list = "crate,uptodate,nd,nin"
# ignore-words = ".codespell-ignore"  # Removed: file was empty
```

**Recommendation:** Keep file (Option A) - useful for future project-specific terms

______________________________________________________________________

## Issue #7: .gitleaksignore Review 🔐

### Current Content

```gitignore
# Documentation and example code containing sample secrets
**/.claude/**
**/*.md
**/docs/**
**/examples/**

# IDE configuration files
**/.idea/**
**/.vscode/**

# Test files
**/tests/**

# Lock files and configuration
uv.lock
pyproject.toml

# Build and cache directories
**/__pycache__/**
**/build/**
**/dist/**
**/.venv/**
```

### Analysis

**Questions:**

1. Should `pyproject.toml` be excluded from secret scanning?
1. Should `*.md` be excluded? (might contain leaked secrets in docs)

**Recommendations:**

**✅ Keep as-is:**

- Documentation often contains example API keys
- Test files have mock secrets
- Lock files have no secrets

**⚠️ Consider removing:**

```gitignore
# Remove overly broad exclusion
# **/*.md  # ❌ Too broad - might miss secrets in README

# Be more specific
**/docs/examples/**
**/docs/tutorials/**
```

**🔧 Consider adding:**

```gitignore
# Additional safe exclusions
**/node_modules/**
**/.git/**
```

**Recommendation:** Keep current config but monitor for false negatives

______________________________________________________________________

## Issue #8: Unused Coverage Settings 📊

### Problem

**Potentially unused coverage.run settings:**

```toml
[tool.coverage.run]
branch = false              # ⚠️ Branch coverage disabled?
source = ["crackerjack"]
data_file = ".coverage"     # ⚠️ Will be replaced by tempfile
parallel = true
concurrency = ["multiprocessing"]
omit = [
    "*/tests/*",
    "*/site-packages/*",
    "*/__pycache__/*",
    "*/__init__.py",        # ⚠️ Exclude __init__.py from coverage?
    "*/_version.py",
    "*/conftest.py",
    "*/test_*.py",
    "*/_test.py",
    "crackerjack/__main__.py",  # ⚠️ Exclude main entry point?
]
```

### Analysis

**branch = false:**

- Disables branch coverage (only line coverage)
- Recommendation: **Enable branch coverage** for better quality

**__init__.py excluded:**

- Most __init__.py are empty (re-exports only)
- Recommendation: **Keep excluded**

**__main__.py excluded:**

- Entry point with CLI boilerplate
- Recommendation: **Keep excluded** (tested via integration tests)

**data_file will change:**

- When tempfile coverage is implemented, this becomes obsolete
- Will be set via `COVERAGE_FILE` environment variable

### Solution: Enable Branch Coverage ✅

```toml
[tool.coverage.run]
branch = true               # ✅ Enable branch coverage
source = ["crackerjack"]
# data_file will be set via COVERAGE_FILE env var (tempfile implementation)
parallel = true
concurrency = ["multiprocessing"]
omit = [
    "*/tests/*",
    "*/site-packages/*",
    "*/__pycache__/*",
    "*/__init__.py",
    "*/_version.py",
    "*/conftest.py",
    "*/test_*.py",
    "*/_test.py",
    "crackerjack/__main__.py",
]
```

**Benefits:**

- ✅ More accurate coverage (branch vs line)
- ✅ Catches untested error paths
- ✅ Industry best practice

______________________________________________________________________

## Issue #9: Pytest Markers - Many Unused? 🏷️

### Problem

**21 test markers defined, but how many are used?**

```toml
markers = [
    "unit: marks test as a unit test",
    "benchmark: mark test as a benchmark",
    "integration: marks test as an integration test",
    "e2e: marks test as end-to-end test",
    "security: marks test as security test",
    "performance: marks test as performance test",
    "slow: marks test as slow running test",
    "smoke: marks test as smoke test",
    "regression: marks test as regression test",
    "api: marks test as API test",
    "database: marks test as database test",
    "external: marks test requiring external services",
    "no_leaks: detect asyncio task leaks",
    "property: marks test as property-based test",
    "mutation: marks test as mutation testing",
    "chaos: marks test as chaos engineering test",
    "ai_generated: marks test as AI-generated test",
    "breakthrough: marks test as breakthrough frontier test",
]
```

### Analysis

**Check usage:**

```bash
$ grep -r "@pytest.mark" tests/ | grep -oE "@pytest\.mark\.[a-z_]+" | sort | uniq -c
```

**Expected findings:**

- unit, integration, benchmark - **likely used**
- chaos, mutation, breakthrough - **likely unused**

### Solution: Audit and Remove Unused ✅

**Step 1:** Run analysis

```bash
# Find which markers are actually used in tests
grep -r "@pytest.mark\." tests/ | \
  grep -oE "@pytest\.mark\.[a-z_]+" | \
  sort | uniq
```

**Step 2:** Remove unused markers

Keep only markers that are:

1. Actually used in tests
1. Planned for near-term use
1. Required by pytest plugins

**Estimated removal:** ~8-10 unused markers

______________________________________________________________________

## Issue #10: Ruff Exclude Patterns ⚙️

### Problem

**Ruff excludes test files from linting:**

```toml
[tool.ruff]
target-version = "py313"
line-length = 88
fix = true
unsafe-fixes = true
show-fixes = true
output-format = "full"
exclude = [
    "tests/",      # ⚠️ Exclude ALL tests?
    "test_*.py",
    "*_test.py",
]
```

### Analysis

**Question:** Should tests be linted?

**Pros of linting tests:**

- Maintains code quality in test suite
- Catches bugs in test code
- Enforces consistent style

**Cons:**

- Tests may have different style requirements
- Test fixtures can trigger false positives

**Current practice:** Tests are **excluded from linting**

### Solution: Consider Re-enabling ✅

**Option A: Lint tests with relaxed rules**

```toml
[tool.ruff]
exclude = [
    # Remove test exclusions - lint everything
]

[tool.ruff.lint.per-file-ignores]
# Relax rules for test files
"tests/**" = [
    "S101",  # Allow assert statements
    "PLR2004",  # Allow magic values in tests
]
```

**Option B: Keep excluded**

Tests have different quality standards - keep excluded.

**Recommendation:** Option A - lint tests with relaxed rules

______________________________________________________________________

## Consolidation Summary 📊

### Configuration Files

| File | Current Lines | After Consolidation | Status |
|------|--------------|---------------------|--------|
| `pyproject.toml` | 438 | ~380 (-58) | Simplified |
| `mypy.ini` | 18 | 0 (**DELETED**) | Eliminated |
| `.gitleaksignore` | 23 | 23 (unchanged) | Keep |
| `.codespell-ignore` | 3 | 3 (unchanged) | Keep |
| `settings/crackerjack.yaml` | N/A | N/A | Review separately |

**Total reduction:** 5 files → 4 files, ~80 lines removed

### pyproject.toml Sections to Modify

| Section | Action | Lines Saved | Priority |
|---------|--------|-------------|----------|
| `[tool.mypy]` | **Add full config** | +16 | **CRITICAL** |
| `[tool.refurb]` | Remove 3 amend blocks | -18 | High |
| `[tool.creosote]` | Use categories | -40 | High |
| `[tool.crackerjack]` | Remove redundant keys | -2 | Medium |
| `[tool.coverage.run]` | Enable branch coverage | 0 | Medium |
| `[tool.pyright]` | Simplify | -20 | Low |
| `[tool.pytest.ini_options]` | Remove unused markers | -8 | Low |

**Net change:** -58 lines (after adding mypy config)

______________________________________________________________________

## Implementation Plan 🛠️

### Phase 1: Critical Consolidations (Week 1)

**Priority 1: Eliminate mypy.ini**

- [ ] Add full mypy config to `[tool.mypy]` in pyproject.toml
- [ ] Update zuban command in tool_commands.py (remove --config-file)
- [ ] Test zuban still works
- [ ] Delete mypy.ini
- [ ] Commit: "refactor: consolidate mypy config into pyproject.toml"

**Lines changed:** +16, -18 (net: -2 lines, -1 file)

### Phase 2: Simplify Redundant Configs (Week 1)

**Priority 2: Remove refurb redundancy**

- [ ] Delete 3 `[[tool.refurb.amend]]` blocks
- [ ] Test refurb still works
- [ ] Commit: "refactor: remove redundant refurb test path configs"

**Lines changed:** -18

**Priority 3: Simplify test worker config**

- [ ] Remove `auto_detect_workers` and `min_workers` from `[tool.crackerjack]`
- [ ] Update comments for clarity
- [ ] Commit: "refactor: simplify test worker configuration"

**Lines changed:** -2

### Phase 3: Optimize Dependencies (Week 2)

**Priority 4: Modernize creosote config**

- [ ] Check if creosote v4.1+ supports exclude-categories
- [ ] Replace exclude-deps list with categories
- [ ] Test creosote still works
- [ ] Commit: "refactor: use creosote categories instead of individual excludes"

**Lines changed:** -40

### Phase 4: Quality Improvements (Week 2)

**Priority 5: Enable branch coverage**

- [ ] Change `branch = false` to `branch = true`
- [ ] Run tests and verify coverage still works
- [ ] Update coverage baseline if needed
- [ ] Commit: "feat: enable branch coverage for better quality metrics"

**Lines changed:** 0 (just flip boolean)

**Priority 6: Audit pytest markers**

- [ ] Run grep analysis to find used markers
- [ ] Remove unused markers
- [ ] Commit: "refactor: remove unused pytest markers"

**Lines changed:** ~-8

### Phase 5: Optional Simplifications (Week 3)

**Priority 7: Simplify pyright config (if not needed for IDEs)**

- [ ] Confirm team usage of VS Code/pyright
- [ ] If unused, remove `[tool.pyright]` section
- [ ] If used, simplify and document
- [ ] Commit: "refactor: simplify pyright config"

**Lines changed:** -20

**Priority 8: Consider linting tests**

- [ ] Discuss team preference
- [ ] If desired, remove test exclusions from ruff
- [ ] Add per-file-ignores for test-specific rules
- [ ] Commit: "feat: enable ruff linting for test files"

**Lines changed:** ~0 (restructure)

______________________________________________________________________

## Testing Checklist ✅

After each change, verify:

### Hooks Still Work

```bash
# Run all hooks
python -m crackerjack run

# Specifically test modified tools
uv run zuban check ./crackerjack        # After mypy.ini removal
uv run refurb crackerjack               # After refurb simplification
uv run creosote                         # After creosote changes
uv run pytest tests/                    # After pytest marker changes
```

### Coverage Still Works

```bash
python -m crackerjack run --run-tests

# Check that coverage metrics are reasonable
# Branch coverage should show more accurate results
```

### No Regressions

```bash
# Full workflow
python -m crackerjack run --run-tests

# Should pass all checks
```

______________________________________________________________________

## Migration for Users 📢

### For Projects Using Crackerjack

**After mypy.ini removal:**

If your project uses crackerjack and has a `mypy.ini`, you'll need to either:

**Option A:** Add mypy config to your pyproject.toml

```toml
[tool.mypy]
# Your mypy settings here
```

**Option B:** Keep mypy.ini and update your crackerjack config

```yaml
# settings/local.yaml
hooks:
  zuban:
    config_file: "mypy.ini"  # Explicitly set
```

______________________________________________________________________

## Risks & Mitigation ⚠️

### Risk 1: Zuban Can't Read pyproject.toml

**Mitigation:**

- Test extensively before merging
- Keep mypy.ini in git history for easy rollback
- Document migration in CHANGELOG

**Rollback:**

```bash
git show HEAD~1:mypy.ini > mypy.ini
# Revert tool_commands.py changes
```

### Risk 2: Creosote Categories Not Supported

**Mitigation:**

- Check creosote version: `uv run creosote --version`
- Verify in documentation before implementing
- If not supported, keep current approach

### Risk 3: Branch Coverage Breaks CI

**Mitigation:**

- Update coverage baseline to new branch coverage values
- Adjust coverage requirements if needed
- Monitor first few CI runs

### Risk 4: Breaking IDE Users

**Mitigation:**

- Don't remove pyright config if VS Code users rely on it
- Survey team before making IDE-related changes
- Document which configs are for CI vs IDE

______________________________________________________________________

## Future Enhancements 🚀

### Move More to pyproject.toml

Currently **not possible** but watch for future support:

1. **mdformat config**

   - Currently: CLI flags only
   - Future: `[tool.mdformat]` support?

1. **gitleaks config**

   - Currently: .gitleaksignore file
   - Future: `[tool.gitleaks]` support?

1. **semgrep rules**

   - Currently: Remote ruleset (`p/security-audit`)
   - Future: Local rules in pyproject.toml?

### Settings YAML Review

Separately audit `settings/crackerjack.yaml`:

- Are all settings used?
- Can any be moved to pyproject.toml?
- Are defaults sensible?

______________________________________________________________________

## Recommendations Priority 🎯

### Must Do (Priority 1)

1. ✅ **Eliminate mypy.ini** - Consolidate into pyproject.toml
1. ✅ **Remove refurb redundancy** - Delete duplicate amend blocks
1. ✅ **Enable branch coverage** - Better quality metrics

### Should Do (Priority 2)

4. ✅ **Simplify test workers** - Remove redundant config keys
1. ✅ **Modernize creosote** - Use categories instead of lists
1. ✅ **Audit pytest markers** - Remove unused markers

### Nice to Have (Priority 3)

7. ⚠️ **Simplify pyright** - Only if not used by IDEs
1. ⚠️ **Lint test files** - Team decision needed

______________________________________________________________________

## Summary Statistics 📈

**Before Consolidation:**

- Configuration files: 5
- Total config lines: ~500
- Tools configured: 14
- Duplicate configs: 2 (mypy)
- Redundant settings: 12+

**After Consolidation:**

- Configuration files: 4 (-1)
- Total config lines: ~420 (-80)
- Tools configured: 14 (same)
- Duplicate configs: 0 ✅
- Redundant settings: 0 ✅

**Maintenance Impact:**

- Single source of truth: pyproject.toml
- Fewer files to search when configuring tools
- Follows Python community standards (PEP 518)
- Easier onboarding for new developers

______________________________________________________________________

**Next Steps:**

1. Review this audit with the team
1. Approve consolidation priorities
1. Implement Phase 1 (critical consolidations)
1. Test thoroughly
1. Document changes in CHANGELOG
1. Update documentation (CLAUDE.md, README.md)

**Estimated Effort:** 2-3 days across 3 weeks
**Risk Level:** Low (all changes reversible, tested incrementally)
**Value:** High (cleaner configs, single source of truth, better maintainability)

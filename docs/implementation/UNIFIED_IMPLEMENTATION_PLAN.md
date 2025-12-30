# Unified Implementation Plan - Crackerjack Quality & Configuration Improvements

**Created:** 2025-11-16
**Status:** 🚀 In Progress
**Source Documents:**

- AUDIT_HOOKS_TOOLS.md (7 issues)
- CONFIG_CONSOLIDATION_AUDIT.md (10 issues)
- CROSS_PROJECT_CONFIG_AUDIT.md (6 projects)

______________________________________________________________________

## Executive Summary

This plan consolidates findings from 3 comprehensive audits into a prioritized, executable roadmap. We've identified **17 high-impact improvements** that will:

1. ✅ Fix critical bugs causing false negatives in external projects
1. ✅ Eliminate 1 config file (mypy.ini) and ~80 lines of redundant config
1. ✅ Improve code quality metrics (branch coverage)
1. ✅ Standardize configuration across the portfolio

**Total Impact:**

- Fix 1 CRITICAL bug (affecting 100% of external projects)
- Eliminate 8+ config files across portfolio
- Remove ~250 lines of redundant configuration
- Improve maintainability across 6 projects

______________________________________________________________________

## Implementation Status Overview

### ✅ Completed (0/17)

*None yet - ready to start!*

### 🚧 In Progress (0/17)

*Will update as we go*

### ⏳ Pending (17/17)

*All tasks queued*

______________________________________________________________________

## Priority Matrix

| Priority | Issue | Impact | Effort | Risk | Can Parallelize? |
|----------|-------|--------|--------|------|------------------|
| **P0 (CRITICAL)** | Hardcoded package name | 🔴 Critical | Low | Low | No (blocks testing) |
| **P1 (High)** | Eliminate mypy.ini | 🟠 High | Low | Low | ✅ Yes (parallel with P2-P4) |
| **P1 (High)** | Add gitleaks JSON parsing | 🟠 High | Medium | Low | ✅ Yes |
| **P1 (High)** | Remove refurb redundancy | 🟠 High | Low | Low | ✅ Yes |
| **P2 (Medium)** | Enable branch coverage | 🟡 Medium | Low | Low | ✅ Yes |
| **P2 (Medium)** | Simplify test workers | 🟡 Medium | Low | Low | ✅ Yes |
| **P2 (Medium)** | Modernize creosote config | 🟡 Medium | Low | Low | ✅ Yes |
| **P3 (Low)** | Zuban --no-error-summary | 🟢 Low | Low | Medium | ✅ Yes |
| **P3 (Low)** | Path separator fix | 🟢 Low | Low | Low | ✅ Yes |
| **P3 (Low)** | Semgrep error categorization | 🟢 Low | Medium | Low | ⏸️ Later |

______________________________________________________________________

## Phase 1: Critical Fixes (Day 1) 🚨

### Task 1.1: Fix Hardcoded Package Name in Complexipy Parser

**Status:** ⏳ Pending
**Priority:** P0 - CRITICAL
**Effort:** 1-2 hours
**Blocks:** Testing of other changes

**Files to Modify:**

- `crackerjack/executors/hook_executor.py`
- `crackerjack/config/tool_commands.py`

**Implementation Steps:**

- [ ] **Step 1:** Add package name detection method

  ```python
  # In hook_executor.py
  def _detect_package_from_output(self, output: str) -> str:
      """Auto-detect package name from tool output."""
      import re
      from pathlib import Path

      # Try to extract from file paths in output
      path_pattern = r"\./([a-z_][a-z0-9_]*)/[a-z_]"
      matches = re.findall(path_pattern, output)
      if matches:
          from collections import Counter

          return Counter(matches).most_common(1)[0][0]

      # Fallback to detecting from pyproject.toml
      from crackerjack.config.tool_commands import _detect_package_name_cached

      return _detect_package_name_cached(str(self.pkg_path))
  ```

- [ ] **Step 2:** Update `_should_include_line` to accept package_name

  ```python
  def _should_include_line(self, line: str, package_name: str) -> bool:
      """Check if the line should be included in the output."""
      return "│" in line and package_name in line
  ```

- [ ] **Step 3:** Update `_parse_complexipy_issues` to detect/use package name

  ```python
  def _parse_complexipy_issues(self, output: str) -> list[str]:
      """Parse complexipy table output to count actual violations."""
      # Auto-detect package name from output
      package_name = self._detect_package_from_output(output)

      issues = []
      for line in output.split("\n"):
          if self._should_include_line(line, package_name):
              if not self._is_header_or_separator_line(line):
                  parts = [p.strip() for p in line.split("│") if p.strip()]
                  complexity = self._extract_complexity_from_parts(parts)
                  if complexity is not None and complexity > 15:
                      issues.append(line.strip())
      return issues
  ```

- [ ] **Step 4:** Add tests for package name detection

  ```python
  # tests/test_hook_executor.py
  def test_complexipy_parsing_different_package_names():
      """Test complexipy parser works for any package name."""
      executor = HookExecutor(...)

      # Test with "my_project" instead of "crackerjack"
      output = """
      │ path │ file │ function │ complexity │
      │ ./my_project/core.py │ core.py │ process │ 16 │
      """

      issues = executor._parse_complexipy_issues(output)
      assert len(issues) == 1
      assert "my_project" in issues[0]
  ```

- [ ] **Step 5:** Test with real external project

**Validation:**

```bash
# Test that complexipy parsing works for non-crackerjack projects
cd /tmp
mkdir test-project && cd test-project
# Create simple Python project
# Run crackerjack hooks
# Verify complexipy violations are detected
```

**Success Criteria:**

- ✅ Complexipy violations detected in projects with ANY package name
- ✅ No hardcoded "crackerjack" references in parser
- ✅ Tests pass for multiple package names

______________________________________________________________________

## Phase 2: High-Priority Config Consolidation (Day 1-2) 📋

### Task 2.1: Eliminate mypy.ini

**Status:** ⏳ Pending
**Priority:** P1 - High
**Effort:** 30 minutes
**Can run in parallel:** ✅ Yes (with 2.2, 2.3, 2.4)

**Files to Modify:**

- `pyproject.toml`
- `mypy.ini` (delete)
- `crackerjack/config/tool_commands.py`

**Implementation Steps:**

- [ ] **Step 1:** Add full mypy config to pyproject.toml

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

- [ ] **Step 2:** Update zuban command to remove --config-file

  ```python
  # In tool_commands.py
  "zuban": [
      "uv", "run", "zuban", "check",
      # Removed: "--config-file", "mypy.ini",
      "--no-error-summary",
      f"./{package_name}",
  ],
  ```

- [ ] **Step 3:** Test zuban still works

  ```bash
  uv run zuban check ./crackerjack
  ```

- [ ] **Step 4:** Delete mypy.ini

  ```bash
  git rm mypy.ini
  ```

**Success Criteria:**

- ✅ Zuban reads config from pyproject.toml
- ✅ Type checking still works
- ✅ mypy.ini deleted

______________________________________________________________________

### Task 2.2: Add Gitleaks JSON Output

**Status:** ⏳ Pending
**Priority:** P1 - High
**Effort:** 1 hour
**Can run in parallel:** ✅ Yes

**Files to Modify:**

- `crackerjack/config/tool_commands.py`
- `crackerjack/executors/hook_executor.py`

**Implementation Steps:**

- [ ] **Step 1:** Add JSON output flag to gitleaks command

  ```python
  "gitleaks": [
      "uv", "run", "gitleaks", "protect",
      "-v",
      "--report-format", "json",  # ✅ Add structured output
      "--report-path", "/dev/stdout",  # Output to stdout for capture
  ],
  ```

- [ ] **Step 2:** Rewrite `_parse_gitleaks_issues` for JSON

  ```python
  def _parse_gitleaks_issues(self, output: str) -> list[str]:
      """Parse gitleaks JSON output to extract leaks."""
      import json

      issues = []

      try:
          # Gitleaks outputs NDJSON (one JSON object per line)
          for line in output.split("\n"):
              line = line.strip()
              if not line:
                  continue

              try:
                  leak = json.loads(line)

                  # Format: "file.py:line - rule: description"
                  file_path = leak.get("File", "unknown")
                  line_num = leak.get("StartLine", "?")
                  rule_id = leak.get("RuleID", "unknown-rule")
                  description = leak.get("Description", "Secret detected")

                  issues.append(f"{file_path}:{line_num} - {rule_id}: {description}")
              except json.JSONDecodeError:
                  continue

      except Exception:
          # Fallback to text parsing if JSON fails
          if "no leaks found" in output.lower():
              return []
          return [line.strip() for line in output.split("\n") if "leak" in line.lower()][
              :10
          ]

      return issues
  ```

- [ ] **Step 3:** Test with real gitleaks output

**Success Criteria:**

- ✅ Gitleaks outputs JSON
- ✅ Parser correctly extracts leak information
- ✅ No false positives from warnings

______________________________________________________________________

### Task 2.3: Remove Refurb Redundancy

**Status:** ⏳ Pending
**Priority:** P1 - High
**Effort:** 5 minutes
**Can run in parallel:** ✅ Yes

**Files to Modify:**

- `pyproject.toml`

**Implementation Steps:**

- [ ] **Step 1:** Delete redundant `[[tool.refurb.amend]]` blocks

  ```toml
  # DELETE these 3 blocks:
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

- [ ] **Step 2:** Keep only global ignore

  ```toml
  [tool.refurb]
  enable_all = true
  quiet = true
  python_version = "3.13"
  ignore = [
      "FURB184",  # Already applies to ALL files
      "FURB120",  # Already applies to ALL files
  ]
  ```

- [ ] **Step 3:** Test refurb still works

  ```bash
  uv run refurb crackerjack
  ```

**Success Criteria:**

- ✅ 18 lines removed from pyproject.toml
- ✅ Refurb behavior unchanged
- ✅ Tests still ignored

______________________________________________________________________

### Task 2.4: Simplify Test Worker Config

**Status:** ⏳ Pending
**Priority:** P1 - High
**Effort:** 5 minutes
**Can run in parallel:** ✅ Yes

**Files to Modify:**

- `pyproject.toml`

**Implementation Steps:**

- [ ] **Step 1:** Remove redundant keys

  ```toml
  [tool.crackerjack]
  # Test parallelization settings
  test_workers = 0            # 0 = auto-detect, 1 = sequential, >1 = explicit, <0 = fractional
  # auto_detect_workers = true  # ❌ REMOVE - redundant with test_workers=0
  max_workers = 8             # Maximum parallel workers (safety limit)
  # min_workers = 2             # ❌ REMOVE - not used by pytest-xdist
  memory_per_worker_gb = 2.0  # Minimum memory per worker (prevents OOM)
  ```

- [ ] **Step 2:** Verify no code references removed keys

  ```bash
  grep -r "auto_detect_workers\|min_workers" crackerjack/
  # Should only find config loading, no usage
  ```

**Success Criteria:**

- ✅ 2 lines removed
- ✅ Test parallelization still works
- ✅ No broken references

______________________________________________________________________

## Phase 3: Quality Improvements (Day 2) 📈

### Task 3.1: Enable Branch Coverage

**Status:** ⏳ Pending
**Priority:** P2 - Medium
**Effort:** 15 minutes
**Can run in parallel:** ✅ Yes

**Files to Modify:**

- `pyproject.toml`

**Implementation Steps:**

- [ ] **Step 1:** Enable branch coverage

  ```toml
  [tool.coverage.run]
  branch = true  # ✅ Changed from false
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

- [ ] **Step 2:** Run tests and check new coverage

  ```bash
  python -m crackerjack run --run-tests
  ```

- [ ] **Step 3:** Update coverage baseline if needed

**Success Criteria:**

- ✅ Branch coverage enabled
- ✅ Tests pass
- ✅ More accurate coverage metrics

______________________________________________________________________

### Task 3.2: Modernize Creosote Config

**Status:** ⏳ Pending
**Priority:** P2 - Medium
**Effort:** 30 minutes
**Can run in parallel:** ✅ Yes

**Files to Modify:**

- `pyproject.toml`

**Implementation Steps:**

- [ ] **Step 1:** Check creosote version supports categories

  ```bash
  uv run creosote --version
  # Need v4.1.0+ for exclude-categories
  ```

- [ ] **Step 2:** Replace exclude-deps list with categories (if supported)

  ```toml
  [tool.creosote]
  paths = ["crackerjack"]
  deps-file = "pyproject.toml"

  # If categories supported:
  exclude-categories = [
      "build-system",
      "dev-dependencies",
      "test",
      "types",
  ]

  # Only list exceptional packages
  exclude-deps = [
      "uv",          # CLI tool
      "pyfiglet",    # Optional import
      "tomli-w",     # Only in scripts
  ]
  ```

- [ ] **Step 3:** If categories NOT supported, keep current list

- [ ] **Step 4:** Test creosote

  ```bash
  uv run creosote
  ```

**Success Criteria:**

- ✅ Creosote works correctly
- ✅ Fewer lines in pyproject.toml (if categories supported)
- ✅ No false positives

______________________________________________________________________

## Phase 4: Minor Fixes & Polish (Day 2-3) ✨

### Task 4.1: Fix Path Separator for Windows

**Status:** ⏳ Pending
**Priority:** P3 - Low
**Effort:** 5 minutes
**Can run in parallel:** ✅ Yes

**Files to Modify:**

- `crackerjack/executors/hook_executor.py`

**Implementation Steps:**

- [ ] **Step 1:** Fix path separator
  ```python
  def _update_path(self, clean_env: dict[str, str]) -> None:
      """Update the PATH environment variable."""
      import os

      system_path = os.environ.get("PATH", "")
      if system_path:
          venv_bin = str(Path(self.pkg_path) / ".venv" / "bin")
          path_parts = [
              p for p in system_path.split(os.pathsep) if p != venv_bin
          ]  # ✅ Use os.pathsep
          clean_env["PATH"] = os.pathsep.join(path_parts)  # ✅ Use os.pathsep
  ```

**Success Criteria:**

- ✅ Works on Windows (uses `;`)
- ✅ Works on Linux/Mac (uses `:`)

______________________________________________________________________

### Task 4.2: Investigate Zuban --no-error-summary

**Status:** ⏳ Pending
**Priority:** P3 - Low
**Effort:** 30 minutes
**Can run in parallel:** ✅ Yes

**Files to Modify:**

- `crackerjack/config/tool_commands.py` (possibly)

**Implementation Steps:**

- [ ] **Step 1:** Test zuban with error summary enabled

  ```bash
  uv run zuban check --config-file mypy.ini ./crackerjack
  # Note: Do this BEFORE deleting mypy.ini, or add config to pyproject.toml first
  ```

- [ ] **Step 2:** Check if output parsing breaks

- [ ] **Step 3:** If no issues found, remove --no-error-summary flag

  ```python
  "zuban": [
      "uv", "run", "zuban", "check",
      # Removed: "--no-error-summary",
      f"./{package_name}",
  ],
  ```

- [ ] **Step 4:** If issues found, document in comment and keep flag

**Success Criteria:**

- ✅ Decision made: keep or remove flag
- ✅ Rationale documented in code

______________________________________________________________________

### Task 4.3: Categorize Semgrep Errors

**Status:** ⏳ Pending
**Priority:** P3 - Low
**Effort:** 1 hour
**Can run in parallel:** ⏸️ Do later (lower priority)

**Files to Modify:**

- `crackerjack/executors/hook_executor.py`

**Implementation Steps:**

- [ ] **Step 1:** Define error type categories

  ```python
  # Code errors that should fail the hook
  CODE_ERROR_TYPES = {"ParseError", "SyntaxError", "LexicalError"}

  # Infrastructure errors that should warn but not fail
  INFRA_ERROR_TYPES = {"NetworkError", "RuleDownloadError", "ConfigError"}
  ```

- [ ] **Step 2:** Update `_parse_semgrep_issues` to categorize

  ```python
  if "errors" in json_data:
      for error in json_data.get("errors", []):
          error_type = error.get("type", "SemgrepError")
          error_msg = error.get("message", str(error))

          if error_type in CODE_ERROR_TYPES:
              issues.append(f"{error_type}: {error_msg}")
          elif error_type in INFRA_ERROR_TYPES:
              # Log as warning but don't fail
              self.console.print(f"[yellow]⚠️ Semgrep {error_type}: {error_msg}[/yellow]")
  ```

- [ ] **Step 3:** Test with various semgrep error scenarios

**Success Criteria:**

- ✅ Code errors fail the hook
- ✅ Infrastructure errors warn but don't fail
- ✅ No false failures from network issues

______________________________________________________________________

## Phase 5: Testing & Validation (Day 3) ✅

### Task 5.1: Comprehensive Testing

**Status:** ⏳ Pending
**Priority:** P0 - CRITICAL
**Blocks:** Everything

**Test Checklist:**

- [ ] **All hooks pass**

  ```bash
  python -m crackerjack run
  # Should pass all hooks
  ```

- [ ] **Tests pass with branch coverage**

  ```bash
  python -m crackerjack run --run-tests
  # Should pass all tests
  # Check coverage report for branch metrics
  ```

- [ ] **Zuban works without mypy.ini**

  ```bash
  uv run zuban check ./crackerjack
  # Should type-check successfully
  ```

- [ ] **Gitleaks JSON parsing works**

  ```bash
  uv run gitleaks protect -v --report-format json
  # Check output is parsed correctly
  ```

- [ ] **Complexipy works for different package names**

  ```bash
  # Test in external project
  cd /tmp/test-project
  python -m crackerjack run
  # Should detect complexipy violations
  ```

- [ ] **Refurb works without amend blocks**

  ```bash
  uv run refurb crackerjack
  # Should run without errors
  ```

- [ ] **Test parallelization works**

  ```bash
  python -m crackerjack run --run-tests --test-workers 0
  python -m crackerjack run --run-tests --test-workers 4
  # Both should work
  ```

**Success Criteria:**

- ✅ All tests pass
- ✅ All hooks pass
- ✅ No regressions introduced

______________________________________________________________________

## Phase 6: Documentation & Cleanup (Day 3) 📚

### Task 6.1: Update Documentation

**Status:** ⏳ Pending

**Files to Update:**

- `CLAUDE.md`
- `README.md`
- `CHANGELOG.md`

**Implementation Steps:**

- [ ] **Step 1:** Update CLAUDE.md

  - Remove mypy.ini references
  - Update config consolidation examples
  - Add note about branch coverage

- [ ] **Step 2:** Update README.md

  - Update configuration section
  - Note pyproject.toml as single source of truth

- [ ] **Step 3:** Update CHANGELOG.md

  ```markdown
  ## [0.44.21] - 2025-11-16

  ### Fixed
  - **CRITICAL:** Fixed hardcoded package name in complexipy parser that caused all violations to be ignored in external projects
  - Fixed Windows path separator compatibility

  ### Changed
  - Consolidated mypy configuration into pyproject.toml (removed mypy.ini)
  - Added gitleaks JSON output parsing for better error detection
  - Enabled branch coverage for more accurate metrics
  - Simplified test worker configuration (removed unused settings)
  - Removed redundant refurb amend blocks
  - Modernized creosote configuration to use categories

  ### Removed
  - mypy.ini (consolidated into pyproject.toml)
  ```

- [ ] **Step 4:** Update version in pyproject.toml

  ```bash
  # Bump patch version
  uv bump patch
  ```

**Success Criteria:**

- ✅ All documentation updated
- ✅ CHANGELOG reflects changes
- ✅ Version bumped

______________________________________________________________________

### Task 6.2: Clean Up Audit Documents

**Status:** ⏳ Pending

**Implementation Steps:**

- [ ] **Step 1:** Update audit documents with completion status

  - Mark completed tasks with ✅
  - Add "IMPLEMENTED" notes

- [ ] **Step 2:** Create summary document

  ```markdown
  # Implementation Summary

  All tasks from unified implementation plan completed.

  ## Results:
  - ✅ Fixed 1 CRITICAL bug
  - ✅ Eliminated 1 config file
  - ✅ Removed ~60 lines of redundant config
  - ✅ Improved code quality metrics

  ## Next Steps:
  - Roll out to other projects in portfolio
  - Monitor for regressions
  ```

**Success Criteria:**

- ✅ Audit documents marked complete
- ✅ Summary created

______________________________________________________________________

## Commit Strategy 📝

### Commit 1: Critical Fix

```bash
git add crackerjack/executors/hook_executor.py
git add crackerjack/config/tool_commands.py
git commit -m "fix(hooks): remove hardcoded package name from complexipy parser

BREAKING: Complexipy parser now auto-detects package name instead of
hardcoding 'crackerjack'. This fixes a critical bug where ALL complexipy
violations were silently ignored in external projects.

- Add _detect_package_from_output() method
- Update _should_include_line() to accept package_name parameter
- Update _parse_complexipy_issues() to detect package from output
- Add tests for multiple package names

Fixes: #issue-number (if applicable)
Affects: 100% of projects using crackerjack
"
```

### Commit 2: Config Consolidation

```bash
git add pyproject.toml
git rm mypy.ini
git commit -m "refactor(config): consolidate mypy.ini into pyproject.toml

Eliminates mypy.ini and moves all configuration to pyproject.toml
following PEP 518 standards. Zuban now reads from [tool.mypy] section.

- Add full mypy config to pyproject.toml
- Remove --config-file flag from zuban command
- Delete mypy.ini

Benefits:
- Single source of truth for all configuration
- Follows Python community standards
- Easier maintenance and discovery
"
```

### Commit 3: Quality Improvements

```bash
git add pyproject.toml
git add crackerjack/config/tool_commands.py
git add crackerjack/executors/hook_executor.py
git commit -m "feat(quality): improve hooks and coverage

Multiple quality and configuration improvements:

- Add gitleaks JSON output parsing (better error detection)
- Enable branch coverage (more accurate metrics)
- Remove redundant refurb amend blocks (-18 lines)
- Simplify test worker config (-2 redundant settings)
- Fix Windows path separator compatibility
- Modernize creosote config (use categories)

All changes tested and verified. No regressions.
"
```

### Commit 4: Documentation

```bash
git add CLAUDE.md README.md CHANGELOG.md
git add pyproject.toml  # version bump
git commit -m "docs: update documentation and version to 0.44.21

- Update CLAUDE.md with config consolidation info
- Update README.md configuration section
- Add comprehensive CHANGELOG entry
- Bump version to 0.44.21
"
```

______________________________________________________________________

## Risk Mitigation 🛡️

### Rollback Plan

If any phase fails:

```bash
# Rollback to before changes
git reset --hard origin/claude/audit-hooks-tools-01GSaVfxx6Kuin6GiUssm4oV

# Or rollback specific commits
git revert HEAD~3..HEAD  # Revert last 3 commits
```

### Backup Strategy

- ✅ Work on feature branch (already done)
- ✅ Commit incrementally
- ✅ Test after each phase
- ✅ Keep audit documents for reference

### Testing Strategy

- Test after each major change
- Run full test suite before each commit
- Verify hooks pass after each commit
- Test with external project for complexipy fix

______________________________________________________________________

## Success Metrics 📊

### Code Quality

- ✅ All tests pass (100% pass rate)
- ✅ All hooks pass (0 failures)
- ✅ Branch coverage enabled (better metrics)
- ✅ No regressions introduced

### Configuration

- ✅ 1 file eliminated (mypy.ini)
- ✅ ~60 lines removed from pyproject.toml
- ✅ Single source of truth (pyproject.toml)
- ✅ Follows PEP 518 standards

### Bug Fixes

- ✅ CRITICAL: Complexipy works in external projects
- ✅ Gitleaks has better error parsing
- ✅ Windows path separator compatibility
- ✅ More accurate coverage metrics

______________________________________________________________________

## Timeline Estimate ⏱️

| Phase | Duration | Can Parallelize |
|-------|----------|-----------------|
| Phase 1: Critical Fix | 1-2 hours | No (blocking) |
| Phase 2: Config Consolidation | 2-3 hours | ✅ Yes (4 tasks in parallel) |
| Phase 3: Quality Improvements | 1-2 hours | ✅ Yes (2 tasks in parallel) |
| Phase 4: Minor Fixes | 1-2 hours | ✅ Yes (3 tasks in parallel) |
| Phase 5: Testing | 1 hour | No (blocking) |
| Phase 6: Documentation | 30 minutes | No (final step) |

**Total Estimated Time:** 6-10 hours (1 full day, or 2-3 shorter sessions)

**Parallelization Opportunity:** Tasks in Phase 2-4 can be done simultaneously, reducing wall-clock time to ~4-6 hours.

______________________________________________________________________

## Progress Tracking

### Current Status

- 🚀 Phase 1: Not started
- ⏳ Phase 2: Not started
- ⏳ Phase 3: Not started
- ⏳ Phase 4: Not started
- ⏳ Phase 5: Not started
- ⏳ Phase 6: Not started

### Completed Tasks: 0/17

### Remaining Tasks: 17/17

______________________________________________________________________

**Let's begin implementation! 🚀**

Start with Phase 1: Critical Fix (hardcoded package name)

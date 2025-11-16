# Hooks and Tools Audit Report

**Date:** 2025-11-16
**Scope:** Commands, flags, regex patterns, and error parsing logic
**Status:** ⚠️ Critical issues found requiring immediate attention

## Executive Summary

This audit identified **7 critical issues** that cause false positives, missed errors, or incorrectly reported issues when crackerjack is used in other projects. The root cause is **hardcoded assumptions** about package names and overly aggressive or insufficient output parsing.

______________________________________________________________________

## 🚨 Critical Issues

### 1. **Hardcoded Package Name in Complexipy Parser**

**Severity:** CRITICAL
**Location:** `crackerjack/executors/hook_executor.py:615`
**Impact:** Complexipy errors are **silently ignored** in all non-crackerjack projects

```python
def _should_include_line(self, line: str) -> bool:
    """Check if the line should be included in the output."""
    return "│" in line and "crackerjack" in line  # ❌ HARDCODED!
```

**Problem:**

- This method filters complexipy table output to only show lines containing "crackerjack"
- In other projects (e.g., `my-project`), ALL complexipy violations are dropped
- Users see "✅ passed" when there are actually complexity violations

**Solution:**

```python
def _should_include_line(self, line: str, package_name: str) -> bool:
    """Check if the line should be included in the output."""
    # Match table rows with the actual package being scanned
    return "│" in line and package_name in line
```

**Required Changes:**

1. Pass `package_name` from command detection in `tool_commands.py`
1. Update `_parse_complexipy_issues` to accept package name parameter
1. Update `_extract_issues_for_reporting_tools` call chain

______________________________________________________________________

### 2. **Zuban `--no-error-summary` Flag**

**Severity:** HIGH
**Location:** `crackerjack/config/tool_commands.py:89`
**Impact:** May suppress critical type checking summary information

```python
"zuban": [
    "uv", "run", "zuban", "check",
    "--config-file", "mypy.ini",
    "--no-error-summary",  # ⚠️ Why disable error summary?
    f"./{package_name}",
],
```

**Problem:**

- Comment says "Don't show error summary which may be causing issues"
- No evidence provided for what issues this causes
- Disabling error summary makes debugging type errors harder for users
- May hide useful aggregate information

**Investigation Needed:**

1. What specific issue was this trying to fix?
1. Does zuban output error summary in a format that breaks parsing?
1. Can we parse zuban output correctly WITH the error summary?

**Recommendation:** Remove `--no-error-summary` unless there's documented evidence it causes false positives

______________________________________________________________________

### 3. **Creosote Dependency Parsing Fragility**

**Severity:** MEDIUM
**Location:** `crackerjack/executors/hook_executor.py:658-675`
**Impact:** May miss unused dependencies or report false positives

```python
def _parse_creosote_issues(self, output: str) -> list[str]:
    """Parse creosote output - only count unused dependencies."""
    if "No unused dependencies found" in output:
        return []
    issues = []
    parsing_unused = False
    for line in output.split("\n"):
        if "unused" in line.lower() and "dependenc" in line.lower():
            parsing_unused = True
            continue
        if parsing_unused and line.strip() and not line.strip().startswith("["):
            # Dependency names (not ANSI color codes)
            dep_name = line.strip().lstrip("- ")
            if dep_name:
                issues.append(f"Unused dependency: {dep_name}")
        if not line.strip():
            parsing_unused = False
    return issues
```

**Problems:**

1. **Assumption:** Unused dependencies are listed after a header containing "unused" and "dependenc"
1. **Fragile:** Breaks if creosote changes output format
1. **ANSI codes:** Only filters lines starting with `[`, but ANSI codes can appear anywhere
1. **No validation:** Doesn't verify dependency names are valid package names

**Test Cases Missing:**

- Creosote output with color codes in middle of line
- Creosote output with multiple sections (unused, missing, etc.)
- Creosote output with empty lines between dependencies

**Solution:** Use structured output if creosote supports it (JSON), or add comprehensive test fixtures

______________________________________________________________________

### 4. **Gitleaks Warning Filtering Too Aggressive**

**Severity:** MEDIUM
**Location:** `crackerjack/executors/hook_executor.py:641-656`
**Impact:** May hide legitimate secrets or report false positives

```python
def _parse_gitleaks_issues(self, output: str) -> list[str]:
    """Parse gitleaks output - ignore warnings, only count leaks."""
    # Gitleaks outputs "no leaks found" when clean
    if "no leaks found" in output.lower():
        return []
    return [
        line.strip()
        for line in output.split("\n")
        if not (
            "WRN" in line and "Invalid .gitleaksignore" in line
        )  # Skip warnings about .gitleaksignore format
        and any(
            x in line.lower() for x in ("leak", "secret", "credential", "api")
        )  # Look for actual leak findings
        and "found" not in line.lower()  # Skip summary lines
    ]
```

**Problems:**

1. **Keyword matching:** `any(x in line.lower() for x in ("leak", "secret", ...))` is too broad
   - Matches "no leaks found" (filtered by earlier check, but fragile)
   - Matches "checking for leaks..." (progress messages)
   - Matches "api.example.com" (URLs, not API keys)
1. **Summary exclusion:** `"found" not in line.lower()` excludes any line with "found"
   - Could exclude "API key found in file.py:10"
1. **No structure:** Relies on unstructured text parsing instead of JSON

**Better Approach:**

```python
# Use gitleaks JSON output: --report-format json
# Then parse structured data instead of text matching
```

**Required Changes:**

1. Update `tool_commands.py` to add `--report-format=json` flag
1. Rewrite parser to handle JSON output
1. Add test fixtures with real gitleaks JSON output

______________________________________________________________________

### 5. **Semgrep Error Array Interpretation**

**Severity:** MEDIUM
**Location:** `crackerjack/executors/hook_executor.py:706-711`
**Impact:** Infrastructure errors reported as code issues

```python
# Extract errors from errors array (config errors, download failures, etc.)
if "errors" in json_data:
    for error in json_data.get("errors", []):
        error_type = error.get("type", "SemgrepError")
        error_msg = error.get("message", str(error))
        issues.append(f"{error_type}: {error_msg}")  # ⚠️ ALL errors treated as failures
```

**Problem:**

- Semgrep "errors" array contains both:
  - **Code issues:** Syntax errors, parsing failures in target code
  - **Infrastructure issues:** Rule download failures, network timeouts, config errors
- Current logic treats ALL errors as code failures
- Network issues or rule download problems cause hook to fail even when code is clean

**Example False Positive:**

```json
{
  "results": [],
  "errors": [
    {
      "type": "NetworkError",
      "message": "Failed to download security rules: timeout"
    }
  ]
}
```

Result: Hook fails ❌ even though code has no security issues

**Solution:**

```python
# Categorize errors - only fail on code-related errors
CODE_ERROR_TYPES = {"ParseError", "SyntaxError", "LexicalError"}
INFRA_ERROR_TYPES = {"NetworkError", "RuleDownloadError", "ConfigError"}

for error in json_data.get("errors", []):
    error_type = error.get("type", "SemgrepError")
    if error_type in CODE_ERROR_TYPES:
        issues.append(f"{error_type}: {error_msg}")
    elif error_type in INFRA_ERROR_TYPES:
        # Log as warning but don't fail the hook
        self.console.print(f"[yellow]⚠️ Semgrep {error_type}: {error_msg}[/yellow]")
```

______________________________________________________________________

### 6. **Regex Pattern Assumptions in Ruff Parser**

**Severity:** LOW
**Location:** `crackerjack/services/patterns/tool_output/ruff.py:12`
**Impact:** May fail to parse ruff errors if format changes

```python
"ruff_check_error": ValidatedPattern(
    name="ruff_check_error",
    pattern=r"^(.+?): (\d+): (\d+): ([A-Z]\d+) (.+)$",  # ⚠️ Assumes specific format
    ...
),
```

**Problem:**

- Assumes ruff output format: `file: line: col: CODE message`
- Ruff may change output format between versions
- No fallback if pattern doesn't match

**Current Mitigation:**

- Pattern is only used for TRANSFORMATION, not for error detection
- Actual error detection uses broader heuristics in `_extract_issues_for_regular_tools`

**Recommendation:** Document that this pattern is for beautification only, not parsing

______________________________________________________________________

### 7. **Path Separator Hardcoding**

**Severity:** LOW
**Location:** `crackerjack/executors/hook_executor.py:1139`
**Impact:** May break on Windows systems

```python
def _update_path(self, clean_env: dict[str, str]) -> None:
    """Update the PATH environment variable."""
    system_path = os.environ.get("PATH", "")
    if system_path:
        venv_bin = str(Path(self.pkg_path) / ".venv" / "bin")
        path_parts = [
            p for p in system_path.split(": ") if p != venv_bin
        ]  # ❌ Colon separator
        clean_env["PATH"] = ": ".join(path_parts)  # ❌ Should use os.pathsep
```

**Problem:**

- Uses `: ` (colon) as path separator on all platforms
- Windows uses `;` (semicolon) as separator
- Code will malfunction on Windows

**Solution:**

```python
import os

path_parts = [p for p in system_path.split(os.pathsep) if p != venv_bin]
clean_env["PATH"] = os.pathsep.join(path_parts)
```

______________________________________________________________________

## ✅ Correctly Implemented Areas

### 1. **Refurb Parsing**

```python
def _parse_refurb_issues(self, output: str) -> list[str]:
    return [
        line.strip() for line in output.split("\n") if "[FURB" in line and ":" in line
    ]
```

- Simple, robust pattern matching
- Refurb uses consistent `[FURB###]` format
- No hardcoded package names

### 2. **Reporting Tool Detection**

```python
reporting_tools = {"complexipy", "refurb", "gitleaks", "creosote"}
if hook.name in reporting_tools and issues_found:
    status = "failed"
```

- Correctly identifies tools that exit 0 even when finding issues
- Properly overrides status based on parsed issues

### 3. **Timeout Handling**

- Clean timeout detection with proper exit codes
- Detailed error messages for debugging
- Distinguishes timeouts from other errors

### 4. **Incremental Execution**

- Smart file extension mapping
- Proper fallback to full scans
- Only runs on changed files when supported

______________________________________________________________________

## 🔧 Recommended Fixes (Priority Order)

### Priority 1: Fix Hardcoded Package Name (CRITICAL)

**File:** `crackerjack/executors/hook_executor.py`

```python
# Add package_name parameter to parsing methods
def _parse_complexipy_issues(self, output: str, package_name: str | None = None) -> list[str]:
    """Parse complexipy table output to count actual violations (complexity > 15)."""
    # Auto-detect package name from output if not provided
    if package_name is None:
        package_name = self._detect_package_from_output(output)

    issues = []
    for line in output.split("\n"):
        # Match table rows: │ path │ file │ function │ complexity │
        if "│" in line and package_name in line:
            # ... rest of logic
```

**File:** `crackerjack/executors/hook_executor.py` (add new method)

```python
def _detect_package_from_output(self, output: str) -> str:
    """Auto-detect package name from tool output.

    Looks for common patterns like:
    - Table rows with paths: │ ./package_name/...
    - File paths: package_name/file.py
    """
    import re
    from pathlib import Path

    # Try to extract from file paths in output
    path_pattern = r"\./([a-z_][a-z0-9_]*)/[a-z_]"
    matches = re.findall(path_pattern, output)
    if matches:
        # Return most common package name
        from collections import Counter

        return Counter(matches).most_common(1)[0][0]

    # Fallback to detecting from pyproject.toml (existing logic)
    from crackerjack.config.tool_commands import _detect_package_name_cached

    return _detect_package_name_cached(str(self.pkg_path))
```

### Priority 2: Use Structured Output Formats

**File:** `crackerjack/config/tool_commands.py`

Add JSON output flags where supported:

```python
"gitleaks": [
    "uv", "run", "gitleaks", "protect",
    "-v",
    "--report-format=json",  # ✅ Add structured output
],
"bandit": [
    # ... existing flags
    "--format", "json",  # ✅ Already present
],
"semgrep": [
    # ... existing flags
    "--json",  # ✅ Already present
],
```

### Priority 3: Remove or Document `--no-error-summary`

**File:** `crackerjack/config/tool_commands.py:89`

**Option A:** Remove flag (recommended)

```python
"zuban": [
    "uv", "run", "zuban", "check",
    "--config-file", "mypy.ini",
    # Removed --no-error-summary to preserve diagnostic info
    f"./{package_name}",
],
```

**Option B:** Document rationale

```python
"zuban": [
    "uv", "run", "zuban", "check",
    "--config-file", "mypy.ini",
    "--no-error-summary",  # RATIONALE: Zuban error summary contains ANSI codes that break parsing in terminals without color support. See issue #XXX
    f"./{package_name}",
],
```

### Priority 4: Fix Path Separator

**File:** `crackerjack/executors/hook_executor.py:1139`

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

______________________________________________________________________

## 📋 Testing Recommendations

### 1. Cross-Project Testing

Create test fixtures with different project names:

```python
@pytest.mark.parametrize(
    "package_name",
    [
        "crackerjack",
        "my_project",
        "foo-bar",  # Hyphens converted to underscores
        "complex_pkg_name_2024",
    ],
)
def test_complexipy_parsing_with_different_packages(package_name):
    # Test that complexipy parser works for any package name
    ...
```

### 2. Tool Output Fixtures

Create fixtures for each tool's actual output:

```
tests/fixtures/tool_outputs/
├── complexipy/
│   ├── violations_found.txt
│   ├── no_violations.txt
│   └── different_package_name.txt
├── gitleaks/
│   ├── leaks_found.json
│   ├── no_leaks.json
│   └── network_error.json
├── semgrep/
│   ├── findings.json
│   ├── parse_errors.json
│   └── network_errors.json
└── creosote/
    ├── unused_deps.txt
    └── no_unused_deps.txt
```

### 3. Integration Tests

Test crackerjack against real projects:

```bash
# Test suite
./tests/integration/test_external_projects.sh

# Should test against:
# - Small project (1-2 files)
# - Medium project (10-50 files)
# - Large project (100+ files)
# - Project with violations
# - Clean project
```

______________________________________________________________________

## 📊 Impact Analysis

| Issue | Severity | Projects Affected | False Positives | False Negatives |
|-------|----------|-------------------|-----------------|-----------------|
| Hardcoded package name | CRITICAL | 100% (all non-crackerjack) | No | Yes (missed violations) |
| Zuban error summary | HIGH | Unknown | Possibly | No |
| Creosote parsing | MEDIUM | Projects using creosote | Yes | Possibly |
| Gitleaks filtering | MEDIUM | Projects with secrets | No | Possibly |
| Semgrep errors | MEDIUM | Projects with network issues | Yes (infra errors) | No |
| Ruff pattern | LOW | None (not used for detection) | No | No |
| Path separator | LOW | Windows users | N/A | N/A (runtime error) |

______________________________________________________________________

## 🎯 Action Items

1. **Immediate (This Week)**

   - [ ] Fix hardcoded "crackerjack" in complexipy parser
   - [ ] Add package name auto-detection
   - [ ] Test against 3 external projects

1. **Short Term (Next Sprint)**

   - [ ] Investigate zuban `--no-error-summary` rationale
   - [ ] Add gitleaks JSON parsing
   - [ ] Fix path separator for Windows
   - [ ] Add tool output test fixtures

1. **Medium Term (Next Month)**

   - [ ] Refactor all parsers to use structured output (JSON)
   - [ ] Create integration test suite
   - [ ] Document all tool output formats
   - [ ] Add parser robustness tests

1. **Long Term (Roadmap)**

   - [ ] Consider using tool adapters/plugins pattern
   - [ ] Add parser versioning for tool compatibility
   - [ ] Create parser validation framework
   - [ ] Add telemetry for parser failures

______________________________________________________________________

## 📚 References

- Hook configurations: `crackerjack/config/hooks.py`
- Tool commands: `crackerjack/config/tool_commands.py`
- Hook executor: `crackerjack/executors/hook_executor.py`
- Regex patterns: `crackerjack/services/patterns/tool_output/`
- Metrics collector: `crackerjack/services/metrics.py`

______________________________________________________________________

**Audit Completed By:** Claude Code
**Review Status:** Pending implementation
**Next Review:** After Priority 1 & 2 fixes are deployed

# Comprehensive Hooks Failure - Root Cause Analysis

**Date:** 2025-02-05
**Severity:** CRITICAL - Blocking all quality checks
**Status:** Investigation Complete

## Executive Summary

The comprehensive hooks stage is failing with multiple independent issues:

1. **skylos**: TIMEOUT after 600 seconds (10 minutes) - should take seconds
2. **pyscn**: Parser missing - "No parser available for tool 'pyscn'"
3. **refurb**: Parser returns 0 issues despite expected_count=None (false negative)
4. **AI Agent**: Started but fails immediately with parsing errors

## Root Cause Analysis

### 1. Skylos Infinite Hang (CRITICAL)

**Location:** `/Users/les/Projects/crackerjack/crackerjack/adapters/refactor/skylos.py:94-112`

**Issue:**
```python
# Command EXECUTED (from logs):
uv run skylos --confidence 86 --json ./crackerjack

# Command EXPECTED (from tool_commands.py:40-47):
uv run skylos --exclude-folder tests ./crackerjack

# MISSING: --exclude-folder tests flag
```

**Root Cause:**
The `build_command()` method **NEVER adds the `--exclude-folder tests` flag**, causing:
1. Skylos to scan the entire `tests/` directory (200+ test files)
2. Circular import patterns between tests and production code
3. Dead code analysis gets stuck in infinite loops
4. Never completes, triggers 600s timeout

**Evidence:**
```python
# File: crackerjack/adapters/refactor/skylos.py:94-112 (BROKEN)
def build_command(self, files: list[Path] | None = None, config: QACheckConfig | None = None) -> list[str]:
    cmd = ["uv", "run", "skylos"]
    cmd.extend(["--confidence", str(self.settings.confidence_threshold)])
    if self.settings.use_json_output:
        cmd.append("--json")
    # ❌ MISSING: cmd.extend(["--exclude-folder", "tests"])
    if files:
        cmd.extend([str(f) for f in files])
    # ...
```

**Secondary Issue - Timeout Too Long:**
- Location: `/Users/les/Projects/crackerjack/crackerjack/config/settings.py:174`
- Current: `skylos_timeout: int = 600` (10 minutes)
- Problem: Skylos is "20x faster than vulture" - should take seconds, not minutes
- Even with correct flags, 600s timeout is way too long

**Why This Matters:**
```python
# config/hooks.py:320-330
def _update_hook_timeouts_from_settings(hooks: list[HookDefinition]) -> None:
    from crackerjack.config import CrackerjackSettings, load_settings
    settings = load_settings(CrackerjackSettings)

    for hook in hooks:
        timeout_attr = f"{hook.name}_timeout"
        if hasattr(settings.adapter_timeouts, timeout_attr):
            configured_timeout = getattr(settings.adapter_timeouts, timeout_attr)
            hook.timeout = configured_timeout  # ← OVERRIDES HOOK DEFINITION
```

**Evidence:**
- Hook definition: `timeout=180` (3 min) → Overridden to `600` (10 min)
- Skylos should complete in seconds, not minutes
- 10-minute timeout suggests tool is hanging or not running at all

**Impact:** Blocks entire comprehensive stage for 10 minutes, then fails

---

### 2. Pyscn Parser Missing

**Location:** `/Users/les/Projects/crackerjack/crackerjack/parsers/regex_parsers.py:422-445`

**Issue:**
```python
def register_regex_parsers(factory: "ParserFactory") -> None:
    CodespellRegexParser()
    RefurbRegexParser()
    RuffFormatRegexParser()
    ComplexityRegexParser()
    CreosoteRegexParser()
    StructuredDataParser()

    factory.register_regex_parser("codespell", CodespellRegexParser)
    factory.register_regex_parser("refurb", RefurbRegexParser)
    factory.register_regex_parser("ruff-format", RuffFormatRegexParser)
    factory.register_regex_parser("complexipy", ComplexityRegexParser)
    factory.register_regex_parser("creosote", CreosoteRegexParser)
    factory.register_regex_parser("mypy", MypyRegexParser)
    factory.register_regex_parser("zuban", MypyRegexParser)

    factory.register_regex_parser("check-yaml", StructuredDataParser)
    factory.register_regex_parser("check-toml", StructuredDataParser)
    factory.register_regex_parser("check-json", StructuredDataParser)

    # ❌ NO PARSER FOR 'pyscn' - NOT REGISTERED!
```

**Root Cause:**
- `pyscn` hook is defined in `config/hooks.py:228-235`
- No parser class exists for `pyscn` output
- `ParserFactory.create_parser()` raises `ValueError("No parser available for tool 'pyscn'")` (factory.py:95)

**Evidence:**
```python
# parsers/factory.py:83-95
def create_parser(self, tool_name: str) -> JSONParser | RegexParser:
    if tool_name in self._parser_cache:
        return self._parser_cache[tool_name]

    parser: JSONParser | RegexParser
    if supports_json(tool_name) and tool_name in self._json_parsers:
        logger.debug(f"Using JSON parser for '{tool_name}'")
        parser = self._json_parsers[tool_name]()
    elif tool_name in self._regex_parsers:
        logger.debug(f"Using regex parser for '{tool_name}'")
        parser = self._regex_parsers[tool_name]()
    else:
        raise ValueError(f"No parser available for tool '{tool_name}'")  # ← THIS FIRES FOR pyscn
```

**Impact:** AI fix workflow crashes when trying to parse pyscn output

---

### 3. Refurb Parser Returns 0 Issues (False Negative)

**Location:** `/Users/les/Projects/crackerjack/crackerjack/parsers/regex_parsers.py:75-120`

**Issue:**
```python
class RefurbRegexParser(RegexParser):
    def parse_text(self, output: str) -> list[Issue]:
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not self._should_parse_refurb_line(line):
                continue

            issue = self._parse_refurb_line(line)
            if issue:
                issues.append(issue)

        logger.debug(f"Parsed {len(issues)} issues from refurb")
        return issues

    def _should_parse_refurb_line(self, line: str) -> bool:
        return bool(
            line
            and "FURB" in line  # ← REQUIRES "FURB" IN OUTPUT
            and ":" in line
            and not line.startswith(("Found", "Checked"))
        )
```

**Root Cause:**
- Parser requires `"FURB"` substring in every line
- Actual refurb output may not contain "FURB" in the expected format
- `_should_parse_refurb_line()` filters out ALL lines that don't match exactly
- Result: Parser returns empty list even when refurb found issues

**Why expected_count=None:**
```python
# core/autofix_coordinator.py:1004-1012
def _extract_issue_count(self, output: str, tool_name: str) -> int | None:
    if tool_name in ("complexipy", "refurb", "creosote"):
        return None  # ← SKIP VALIDATION FOR THESE TOOLS

    json_count = _extract_issue_count_from_json(output, tool_name)
    if json_count is not None:
        return json_count

    return _extract_issue_count_from_text_lines(output)
```

**Evidence:**
```python
# core/autofix_coordinator.py:994-997
if issues:
    self._log_parsed_issues(hook_name, issues)
    self._validate_parsed_issues(issues)
else:
    self.logger.warning(
        f"❌ No issues parsed from '{hook_name}' despite expected_count={expected_count}"
    )  # ← THIS LOGS BUT DOESN'T FAIL
```

**Impact:**
- False negatives: Refurb issues are silently ignored
- AI agent never receives refurb issues to fix
- Quality checks pass when they should fail

---

### 4. AI Agent Parsing Error

**Location:** `/Users/les/Projects/crackerjack/crackerjack/core/autofix_coordinator.py:980-1002`

**Issue:**
```python
def _parse_hook_to_issues(self, hook_name: str, raw_output: str) -> list[Issue]:
    expected_count = self._extract_issue_count(raw_output, hook_name)
    self.logger.info(f"Parsing '{hook_name}': expected_count={expected_count}")

    try:
        issues = self._parser_factory.parse_with_validation(
            tool_name=hook_name,
            output=raw_output,
            expected_count=expected_count,
        )

        self.logger.info(f"Successfully parsed {len(issues)} issues from '{hook_name}'")

        if issues:
            self._log_parsed_issues(hook_name, issues)
            self._validate_parsed_issues(issues)
        else:
            self.logger.warning(
                f"❌ No issues parsed from '{hook_name}' despite expected_count={expected_count}"
            )  # ← LOGS BUT CONTINUES

        return issues

    except ParsingError as e:
        self.logger.error(f"Parsing failed for '{hook_name}': {e}")
        raise  # ← THIS CRASHES THE AI AGENT
```

**Root Cause:**
- AI agent tries to parse ALL failed hook results
- When it hits `pyscn`, `ParserFactory.create_parser()` raises `ValueError`
- This becomes `ParsingError` and crashes the entire AI fix workflow
- AI agent never gets to fix ANY issues

**Impact:**
- AI fix workflow crashes immediately
- No automatic fixing occurs
- Manual intervention required

---

## Orchestration Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Hook Execution (async_hook_executor.py)                          │
│    - Executes hooks with timeout from settings                      │
│    - skylos gets 600s timeout (overridden from 180s)                │
│    - Returns HookResult objects                                     │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. AI Fix Coordinator (autofix_coordinator.py)                      │
│    - _apply_ai_agent_fixes() called with hook_results               │
│    - _parse_hook_results_to_issues() filters failed hooks           │
│    - _parse_hook_to_issues() called for each failed hook            │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. Parser Factory (parsers/factory.py)                              │
│    - create_parser('pyscn') → ValueError (no parser registered)     │
│    - create_parser('refurb') → Returns parser (0 issues filtered)   │
│    - create_parser('skylos') → Times out before parsing             │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. AI Agent (agents/coordinator.py)                                 │
│    - Receives empty issue list (refurb) or crashes (pyscn)          │
│    - Cannot fix what it cannot see                                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Recommended Fixes

### Fix 1: Reduce Skylos Timeout (CRITICAL)

**File:** `/Users/les/Projects/crackerjack/crackerjack/config/settings.py:174`

**Change:**
```python
# BEFORE
class AdapterTimeouts(Settings):
    skylos_timeout: int = 600  # 10 minutes - TOO LONG

# AFTER
class AdapterTimeouts(Settings):
    skylos_timeout: int = 60  # 1 minute - ultra-fast tool
```

**Rationale:**
- Skylos is "20x faster than vulture" - should complete in seconds
- 60 seconds is more than enough for dead code detection
- Prevents 10-minute blocking wait

---

### Fix 2: Implement Pyscn Parser (CRITICAL)

**File:** `/Users/les/Projects/crackerjack/crackerjack/parsers/regex_parsers.py`

**Add:**
```python
class PyscnRegexParser(RegexParser):
    def parse_text(self, output: str) -> list[Issue]:
        issues: list[Issue] = []

        for line in output.split("\n"):
            line = line.strip()
            if not self._should_parse_pyscn_line(line):
                continue

            issue = self._parse_pyscn_line(line)
            if issue:
                issues.append(issue)

        logger.debug(f"Parsed {len(issues)} issues from pyscn")
        return issues

    def _should_parse_pyscn_line(self, line: str) -> bool:
        # pyscn output format: file:line:severity:message
        return bool(line and ":" in line and not line.startswith(("Found", "Checked", "==")))

    def _parse_pyscn_line(self, line: str) -> Issue | None:
        parts = line.split(":", 3)
        if len(parts) < 4:
            return None

        try:
            file_path = parts[0].strip()
            line_number = int(parts[1].strip())
            severity = parts[2].strip()
            message = parts[3].strip() if len(parts) > 3 else line

            return Issue(
                type=IssueType.SECURITY,
                severity=Priority.HIGH if severity == "error" else Priority.MEDIUM,
                message=message,
                file_path=file_path,
                line_number=line_number,
                stage="pyscn",
            )
        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse pyscn line: {line} ({e})")
            return None


def register_regex_parsers(factory: "ParserFactory") -> None:
    # ... existing parsers ...
    factory.register_regex_parser("pyscn", PyscnRegexParser)  # ← ADD THIS

    logger.info(
        "Registered regex parsers: codespell, refurb, ruff-format, complexipy, "
        "creosote, mypy, zuban, check-yaml, check-toml, check-json, pyscn"  # ← ADD pyscn
    )
```

**Rationale:**
- pyscn is a security scanner (SAST tool)
- Needs regex parser for text output
- Follows same pattern as existing parsers

---

### Fix 3: Fix Refurb Parser False Negatives (HIGH)

**File:** `/Users/les/Projects/crackerjack/crackerjack/parsers/regex_parsers.py:91-97`

**Change:**
```python
# BEFORE
def _should_parse_refurb_line(self, line: str) -> bool:
    return bool(
        line
        and "FURB" in line  # ← TOO STRICT
        and ":" in line
        and not line.startswith(("Found", "Checked"))
    )

# AFTER
def _should_parse_refurb_line(self, line: str) -> bool:
    if not line:
        return False
    if line.startswith(("Found", "Checked", "Success", "=")):
        return False
    # More flexible: just needs colon separator, not "FURB" literal
    return ":" in line and len(line.split(":")) >= 3
```

**Rationale:**
- Refurb output format: `file:line:column: message`
- "FURB" may not appear in every line
- Current filter is too strict, causing false negatives
- New logic: look for structure (3+ colons) not content

---

### Fix 4: Add Parser Validation at Startup (MEDIUM)

**File:** `/Users/les/Projects/crackerjack/crackerjack/parsers/factory.py:50-69`

**Add:**
```python
def _register_parsers(self) -> None:
    try:
        from crackerjack.parsers.json_parsers import register_json_parsers
        register_json_parsers(self)
    except ImportError as e:
        logger.warning(f"Failed to import JSON parsers: {e}")

    try:
        from crackerjack.parsers.regex_parsers import register_regex_parsers
        register_regex_parsers(self)
    except ImportError as e:
        logger.warning(f"Failed to import regex parsers: {e}")

    # ← ADD VALIDATION
    self._validate_parser_coverage()

def _validate_parser_coverage(self) -> None:
    """Ensure all hooks have registered parsers."""
    from crackerjack.config.hooks import COMPREHENSIVE_HOOKS

    hook_names = {hook.name for hook in COMPREHENSIVE_HOOKS}
    registered_parsers = set(self._json_parsers) | set(self._regex_parsers)

    missing = hook_names - registered_parsers
    if missing:
        logger.error(
            f"⚠️ Missing parsers for hooks: {', '.join(sorted(missing))}. "
            f"These hooks will fail during parsing."
        )
```

**Rationale:**
- Detect missing parsers at startup, not runtime
- Clear error messages before execution
- Prevents cascading failures

---

### Fix 5: Add Fallback for Missing Parsers (LOW)

**File:** `/Users/les/Projects/crackerjack/crackerjack/parsers/factory.py:83-98`

**Change:**
```python
def create_parser(self, tool_name: str) -> JSONParser | RegexParser:
    if tool_name in self._parser_cache:
        return self._parser_cache[tool_name]

    parser: JSONParser | RegexParser
    if supports_json(tool_name) and tool_name in self._json_parsers:
        logger.debug(f"Using JSON parser for '{tool_name}'")
        parser = self._json_parsers[tool_name]()
    elif tool_name in self._regex_parsers:
        logger.debug(f"Using regex parser for '{tool_name}'")
        parser = self._regex_parsers[tool_name]()
    else:
        # ← ADD FALLBACK
        logger.warning(f"No specific parser for '{tool_name}', using generic parser")
        parser = GenericRegexParser(tool_name)

    self._parser_cache[tool_name] = parser
    return parser
```

**Rationale:**
- Graceful degradation instead of crash
- Generic parser extracts basic info
- Allows workflow to continue

---

## Test Plan

### 1. Verify Skylos Timeout Fix
```bash
# Run skylos hook with verbose logging
python -m crackerjack run -c --verbose 2>&1 | grep -A5 "skylos"

# Expected: Completes in <60 seconds
```

### 2. Verify Pyscn Parser Registration
```python
# Test parser factory
from crackerjack.parsers.factory import ParserFactory

factory = ParserFactory()
parser = factory.create_parser("pyscn")

# Expected: No ValueError, returns PyscnRegexParser instance
```

### 3. Verify Refurb Parser Accuracy
```bash
# Create test file with refurb issues
echo "x = 1  # FURB123" > test_refurb.py

# Run refurb
uv run refurb test_refurb.py

# Parse output
python -c "
from crackerjack.parsers.factory import ParserFactory
factory = ParserFactory()
output = '''test_refurb.py:1:1 FURB123: ...'''
issues = factory.parse_with_validation('refurb', output, None)
print(f'Parsed {len(issues)} issues')
"

# Expected: len(issues) > 0
```

### 4. Verify AI Agent Workflow
```bash
# Run comprehensive hooks with AI fix enabled
AI_AGENT=1 python -m crackerjack run -c --run-tests

# Expected: No crashes, pyscn issues parsed and fixed
```

---

## Files Requiring Changes

| File | Line(s) | Change | Priority |
|------|---------|--------|----------|
| `config/settings.py` | 174 | Reduce `skylos_timeout` from 600 to 60 | CRITICAL |
| `parsers/regex_parsers.py` | 422-445 | Add `PyscnRegexParser` class and registration | CRITICAL |
| `parsers/regex_parsers.py` | 91-97 | Fix `_should_parse_refurb_line()` logic | HIGH |
| `parsers/factory.py` | 50-69 | Add `_validate_parser_coverage()` method | MEDIUM |
| `parsers/factory.py` | 83-98 | Add fallback to `GenericRegexParser` | LOW |

---

## Additional Observations

### Timeout Override Anti-Pattern

The current timeout system has a confusing override pattern:

1. Hook definition specifies timeout: `HookDefinition(name="skylos", timeout=180)`
2. Settings override it: `AdapterTimeouts.skylos_timeout = 600`
3. Final value used: 600 (not 180)

**This is intentional but confusing.** Consider:
- Rename `AdapterTimeouts` to `AdapterTimeoutOverrides`
- Add logging when override happens
- Document why hooks have default timeouts that get overridden

### Parser Validation Gap

No validation occurs between:
1. Hook definition (`config/hooks.py`)
2. Parser registration (`parsers/regex_parsers.py`, `parsers/json_parsers.py`)

This allows gaps like `pyscn` to exist until runtime.

### Expected Count Logic

The `_extract_issue_count()` logic has special cases:
```python
if tool_name in ("complexipy", "refurb", "creosote"):
    return None  # Skip validation
```

**Why?** These tools have unreliable issue counting. This masks the refurb parser bug.

---

## Summary

| Issue | Root Cause | Fix Complexity | Priority |
|-------|------------|----------------|----------|
| skylos timeout | Timeout override 600s instead of 60s | 1 line change | CRITICAL |
| pyscn missing | Parser never implemented | Add parser class | CRITICAL |
| refurb false negative | Parser filter too strict | Relax regex | HIGH |
| AI agent crash | Missing parser causes ValueError | Add fallback/validate | MEDIUM |

**Estimated Fix Time:** 2-3 hours
**Risk Level:** Low (isolated changes)
**Testing Required:** Integration tests for all 4 hooks

# WarningSuppressionAgent Design

## Overview

**Agent Name**: `WarningSuppressionAgent`

**Purpose**: Automatically detect, categorize, and fix pytest warnings and codebase warnings while intelligently skipping non-critical warnings.

**Issue Type**: `IssueType.WARNING`

**Confidence**: 0.85

## Architecture

### Warning Classification System

```python
class WarningCategory(StrEnum):
    """Categories of warnings with handling strategies."""

    SKIP = "skip"                    # Non-critical, ignore
    FIX_AUTOMATIC = "fix_automatic"  # Safe to fix automatically
    FIX_MANUAL = "fix_manual"        # Requires human review
    BLOCKER = "blocker"              # Must fix before continuing
```

### Warning Patterns Database

```python
WARNING_PATTERNS = {
    # SKIP: Non-critical warnings
    "pytest-benchmark": {
        "pattern": r"PytestBenchmarkWarning",
        "category": WarningCategory.SKIP,
        "reason": "Benchmark internals, not user code issues"
    },
    "pytest-unraisable": {
        "pattern": r"PytestUnraisableExceptionWarning.*asyncio",
        "category": WarningCategory.SKIP,
        "reason": "Async cleanup warnings are acceptable in test context"
    },

    # FIX_AUTOMATIC: Safe to fix
    "deprecated-pytest-import": {
        "pattern": r"DeprecationWarning:.*pytest\.helpers\.",
        "category": WarningCategory.FIX_AUTOMATIC,
        "fix": "Replace with direct pytest import"
    },
    "deprecated-assert": {
        "pattern": r"DeprecationWarning:.*assert (called|rewritten)",
        "category": WarningCategory.FIX_AUTOMATIC,
        "fix": "Update to modern pytest assertion style"
    },
    "import-warning": {
        "pattern": r"ImportWarning:.*deprecated",
        "category": WarningCategory.FIX_AUTOMATIC,
        "fix": "Update to current import location"
    },

    # FIX_MANUAL: Requires review
    "pending-deprecation": {
        "pattern": r"PendingDeprecationWarning",
        "category": WarningCategory.FIX_MANUAL,
        "reason": "Review migration path first"
    },

    # BLOCKER: Must fix
    "config-error": {
        "pattern": r"PytestConfigWarning",
        "category": WarningCategory.BLOCKER,
        "reason": "Configuration errors prevent proper test execution"
    },
}
```

## Agent Implementation

### Core Methods

```python
class WarningSuppressionAgent(SubAgent):
    """Agent for detecting and fixing codebase warnings."""

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.WARNING}

    async def can_handle(self, issue: Issue) -> float:
        """Check if issue is a warning we can handle."""
        if issue.type != IssueType.WARNING:
            return 0.0

        message_lower = issue.message.lower()

        # High confidence for pytest warnings
        if "pytest" in message_lower and "warning" in message_lower:
            return 0.9

        # Medium confidence for general warnings
        if "warning" in message_lower or "deprecation" in message_lower:
            return 0.7

        return 0.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        """Categorize and fix warning based on pattern database."""
        # Step 1: Categorize warning
        category = self._categorize_warning(issue)

        # Step 2: Handle based on category
        if category == WarningCategory.SKIP:
            return self._skip_warning(issue)
        elif category == WarningCategory.FIX_AUTOMATIC:
            return await self._fix_warning(issue)
        elif category == WarningCategory.FIX_MANUAL:
            return self._suggest_manual_fix(issue)
        else:  # BLOCKER
            return await self._fix_blocker(issue)

    def _categorize_warning(self, issue: Issue) -> WarningCategory:
        """Match warning against pattern database."""
        for name, config in WARNING_PATTERNS.items():
            if re.search(config["pattern"], issue.message):
                return config["category"]

        # Default: manual review if not in database
        return WarningCategory.FIX_MANUAL
```

## Integration with BatchProcessor

### Issue Creation from Pytest Output

```python
def parse_pytest_warnings(test_output: str) -> list[Issue]:
    """Parse pytest output and create Warning issues."""

    issues = []
    warning_pattern = r"(?P<file>.*):(?P<line>\d+): (?P<type>\w+Warning): (?P<message>.*)"

    for match in re.finditer(warning_pattern, test_output):
        issue = Issue(
            type=IssueType.WARNING,
            severity=Priority.MEDIUM,
            message=f"{match.group('type')}: {match.group('message').strip()}",
            file_path=match.group('file'),
            line_number=int(match.group('line')),
        )
        issues.append(issue)

    return issues
```

### Routing Configuration

```python
# In crackerjack/agents/coordinator.py
ISSUE_TYPE_TO_AGENTS = {
    # ... existing mappings ...
    IssueType.WARNING: ["WarningSuppressionAgent"],
}
```

## Common Warning Fixes

### 1. Deprecated Pytest Imports

**Before**:
```python
from pytest import deprecated_call
from pytest.helpers import sysprog
```

**After**:
```python
import pytest
from _pytest.pytester import Sysproc
```

### 2. Deprecated Assertion Style

**Before**:
```python
assert spam in ("eggs", "ham")
assert frobnicate() == 42
```

**After**:
```python
assert spam in ("eggs", "ham")  # Keep modern assertions
assert frobnicate() == 42
```

### 3. Fixture Scope Mismatch

**Before**:
```python
@pytest.fixture
def db_session():
    """Should be session-scoped but isn't marked."""
    return create_session()
```

**After**:
```python
@pytest.fixture(scope="session")
def db_session():
    """Properly scoped."""
    return create_session()
```

### 4. Import Warnings

**Before**:
```python
from collections.abc import Mapping  # Old location
```

**After**:
```python
from typing import Mapping  # Current location
```

## Skip List Configuration

### Settings File

```yaml
# settings/crackerjack.yaml
warning_suppression:
  skip_patterns:
    - "pytest-benchmark"
    - "PytestUnraisableExceptionWarning.*asyncio"
    - "DeprecationWarning:.*third_party_lib"

  auto_fix:
    - "deprecated-import"
    - "pytest-assert-rewrite"
    - "fixture-scope"

  require_manual_review:
    - "PendingDeprecationWarning"
    - "experimental-api"
```

## Implementation Steps

### Phase 1: Core Agent (Week 9)
1. Create WarningSuppressionAgent class
2. Implement warning pattern database
3. Add categorization logic
4. Create skip list configuration

### Phase 2: Parser Integration (Week 9)
1. Extend TestResultParser to capture warnings
2. Create Warning issues from pytest output
3. Add to ISSUE_TYPE_TO_AGENTS routing

### Phase 3: Fix Strategies (Week 10)
1. Implement automatic fix strategies:
   - Deprecated imports
   - Fixture scopes
   - Assertion styles
2. Add manual fix suggestions
3. Create fix verification

### Phase 4: Validation (Week 10)
1. Test on crackerjack test suite
2. Measure warning reduction
3. Validate no false positives

## Success Metrics

### Baseline (Current)
- Pytest warnings: Unknown (need to measure)
- Warning types: Unknown
- Fix rate: 0%

### Target (Post-Implementation)
- Pytest warnings: Categorized and documented
- Fix rate for auto-fixable: 80%+
- False positive rate: <5%
- Test suite speed: Same or faster (no regressions)

## Risks & Mitigations

### Risk 1: Over-Aggressive Fixing
**Risk**: Auto-fixing warnings that should be reviewed
**Mitigation**: Start with conservative auto-fix list, require manual review for deprecations

### Risk 2: False Positives in Skip List
**Risk**: Skipping important warnings due to overly broad patterns
**Mitigation**: Use specific regex patterns, audit skip list quarterly

### Risk 3: Breaking Tests
**Risk**: Fixing warnings introduces test failures
**Mitigation**: Run test suite after each fix, rollback on failure

## Example Usage

### Command Line

```bash
# Run pytest and auto-fix warnings
python -m crackerjack run --run-tests --ai-fix

# Or standalone
python -m crackerjack run-tests --fix-warnings
```

### Output

```
⚠ WarningSuppressionAgent: 15 warnings detected

📊 Categorization:
  ✅ SKIP: 8 (pytest-benchmark, asyncio cleanup)
  🔧 AUTO-FIX: 5 (deprecated imports, fixture scopes)
  👁 MANUAL: 2 (pending deprecations)

🔧 Applied Fixes:
  ✅ Updated 3 deprecated imports
  ✅ Fixed 2 fixture scope mismatches

📋 Manual Review Required:
  ⚠️ test_api.py:45 - PendingDeprecationWarning: foo() will be deprecated
  ⚠️ test_legacy.py:123 - Experimental API usage
```

## Testing Strategy

### Unit Tests
1. Test warning categorization
2. Test pattern matching
3. Test fix strategies

### Integration Tests
1. Run on crackerjack test suite
2. Measure warning reduction
3. Validate no test breakage

### Regression Tests
1. Test that skipped warnings don't reappear
2. Test that fixed warnings don't recur
3. Test that manual warnings are tracked

## Documentation

### User Guide Section

```
## Warning Suppression

Crackerjack automatically detects and fixes pytest warnings:

**Auto-Fixed** (applied automatically):
- Deprecated imports
- Fixture scope mismatches
- Assertion style updates

**Skipped** (intentionally ignored):
- Pytest benchmark warnings
- Asyncio cleanup warnings
- Third-party library warnings

**Manual Review** (requires human judgment):
- Pending deprecations
- Experimental API usage
- Breaking changes

See `docs/BATCHPROCESSOR_USER_GUIDE.md` for configuration.
```

## Future Enhancements

### Phase 5+: Advanced Features
1. **Machine Learning**: Learn which warnings should be skipped vs fixed
2. **Warning Analytics**: Track warning trends over time
3. **Custom Patterns**: User-defined warning patterns
4. **IDE Integration**: Real-time warning detection in IDEs
5. **CI Integration**: Warning gates in CI/CD pipelines

## Related Issues

- **Covers**: IssueType.WARNING (new)
- **Complements**: TestSpecialistAgent (test fixes), TestCreationAgent (test creation)
- **Similar To**: SecurityAgent (pattern-based detection), DRYAgent (code quality)
- **Different From**: TestSpecialistAgent (focuses on failures, not warnings)

## Conclusion

The WarningSuppressionAgent fills an important gap in the AI-fix ecosystem by intelligently handling warnings that are currently ignored or manually reviewed. By categorizing warnings and applying appropriate strategies, it improves code quality while avoiding false positives and over-aggressive fixes.

**Estimated Development Time**: 2 weeks (Phases 1-4)
**Expected Impact**: 80%+ reduction in pytest warnings with minimal false positives
**Risk Level**: Low (conservative defaults, manual review for critical changes)
```

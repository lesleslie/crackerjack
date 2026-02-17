# WarningSuppressionAgent Integration Guide

## Quick Start

### 1. Update Coordinator Routing

Add to `crackerjack/agents/coordinator.py`:

```python
from crackerjack.agents.warning_suppression_agent import WarningSuppressionAgent

# In ISSUE_TYPE_TO_AGENTS mapping:
ISSUE_TYPE_TO_AGENTS = {
    # ... existing mappings ...
    IssueType.WARNING: ["WarningSuppressionAgent"],
}
```

### 2. Add to BatchProcessor

Add to `crackerjack/services/batch_processor.py`:

```python
# In _get_agent() method:
elif agent_name == "WarningSuppressionAgent":
    from crackerjack.agents.warning_suppression_agent import (
        WarningSuppressionAgent,
    )
    self._agents[agent_name] = WarningSuppressionAgent(self.context)
```

### 3. Parse Pytest Warnings

Extend TestResultParser to extract warnings:

```python
# In crackerjack/services/test_result_parser.py
def parse_warnings(self, output: str) -> list[Issue]:
    """Parse pytest warnings from output."""
    from docs.pytest_warning_parser_example import parse_pytest_warnings

    return parse_pytest_warnings(output)
```

### 4. Usage Examples

#### Command Line

```bash
# Run with warning detection
python -m crackerjack run --run-tests --ai-fix

# Warning-specific mode
python -m crackerjack run-tests --fix-warnings
```

#### Python API

```python
from crackerjack.agents.warning_suppression_agent import WarningSuppressionAgent
from crackerjack.agents.base import Issue, IssueType, Priority

# Create agent
agent = WarningSuppressionAgent(context)

# Create warning issue
issue = Issue(
    type=IssueType.WARNING,
    severity=Priority.MEDIUM,
    message="DeprecationWarning: pytest.helpers.sysprog is deprecated",
    file_path="tests/test_foo.py",
    line_number=15,
)

# Fix warning
result = await agent.analyze_and_fix(issue)
print(f"Success: {result.success}")
print(f"Fixes: {result.fixes_applied}")
```

## Expected Behavior

### Input (pytest output with warnings)

```
tests/test_benchmarks.py:10: PytestBenchmarkWarning: internal warning
tests/test_foo.py:15: DeprecationWarning: pytest.helpers.sysprog is deprecated
tests/test_api.py:50: PendingDeprecationWarning: foo() will be deprecated
```

### Output (categorization + fixes)

```
⚠ WarningSuppressionAgent: 3 warnings detected

📊 Categorization:
  ✅ SKIP: 1 (pytest-benchmark)
  🔧 AUTO-FIX: 1 (deprecated-pytest-import)
  👁 MANUAL: 1 (pending-deprecation)

🔧 Applied Fixes:
  ✅ tests/test_foo.py:15 - Replaced deprecated pytest.helpers import

📋 Manual Review Required:
  ⚠️ tests/test_api.py:50 - PendingDeprecationWarning: foo() will be deprecated
```

## Configuration

### Skip List

Edit `WARNING_PATTERNS` in `warning_suppression_agent.py`:

```python
WARNING_PATTERNS = {
    "my-custom-skip": {
        "pattern": r"MyCustomWarning",
        "category": WarningCategory.SKIP,
        "reason": "Not relevant for our codebase",
    },
}
```

### Auto-Fix Patterns

Add new auto-fix patterns:

```python
"my-custom-fix": {
    "pattern": r"DeprecatedThing: (.*)",
    "category": WarningCategory.FIX_AUTOMATIC,
    "fix": "Replace with NewThing",
}
```

## Testing

### Unit Tests

```python
# tests/agents/test_warning_suppression_agent.py
import pytest
from crackerjack.agents.warning_suppression_agent import WarningSuppressionAgent
from crackerjack.agents.base import Issue, IssueType, Priority

@pytest.mark.asyncio
async def test_skip_benchmark_warning():
    agent = WarningSuppressionAgent(context)

    issue = Issue(
        type=IssueType.WARNING,
        severity=Priority.LOW,
        message="PytestBenchmarkWarning: internal",
    )

    result = await agent.analyze_and_fix(issue)
    assert result.success
    assert "Skipped" in result.fixes_applied[0]

@pytest.mark.asyncio
async def test_fix_deprecated_import():
    agent = WarningSuppressionAgent(context)

    issue = Issue(
        type=IssueType.WARNING,
        severity=Priority.MEDIUM,
        message="DeprecationWarning: pytest.helpers.sysprog is deprecated",
        file_path="tests/test_foo.py",
        line_number=15,
    )

    result = await agent.analyze_and_fix(issue)
    # Assert fix was applied
```

### Integration Tests

Run on real pytest output:

```bash
# Run pytest and capture warnings
python -m pytest tests/ -v 2>&1 | tee pytest_output.txt

# Parse and categorize
python docs/pytest_warning_parser_example.py < pytest_output.txt

# Run agent on warnings
python -m crackerjack run --run-tests --ai-fix
```

## Success Metrics

### Before Agent

- Warnings: Unknown (not tracked)
- Fix rate: 0%
- Manual review required: All warnings

### After Agent

- Warnings: Categorized and tracked
- Fix rate: 60-80% (auto-fixable warnings)
- Manual review: Only complex cases
- Time saved: Significant (no manual triage)

## Troubleshooting

### Agent Not Triggered

**Symptom**: Warnings not being processed

**Solution**: Check routing configuration:

```python
# Verify in coordinator.py
assert IssueType.WARNING in ISSUE_TYPE_TO_AGENTS
assert "WarningSuppressionAgent" in ISSUE_TYPE_TO_AGENTS[IssueType.WARNING]
```

### False Positives

**Symptom**: Important warnings being skipped

**Solution**: Update pattern database:

```python
# Remove from skip list or change category
"my-warning": {
    "pattern": r"MyWarning",
    "category": WarningCategory.FIX_MANUAL,  # Was SKIP
    "reason": "Actually important",
}
```

### Fixes Breaking Tests

**Symptom**: Auto-fix causes test failures

**Solution**: Disable specific fix pattern:

```python
# Comment out or remove pattern
# "deprecated-pytest-import": { ... },
```

## Future Enhancements

1. **Machine Learning**: Learn which warnings to skip/fix from history
1. **Custom Patterns**: User-defined warning patterns via config
1. **Warning Analytics**: Track warning trends over time
1. **CI Integration**: Warning gates in CI/CD pipelines
1. **IDE Plugin**: Real-time warning detection in editor

## Related Documentation

- `docs/WARNING_SUPPRESSION_AGENT_DESIGN.md` - Full design spec
- `docs/pytest_warning_parser_example.py` - Parser implementation
- `docs/BATCHPROCESSOR_USER_GUIDE.md` - User guide for BatchProcessor

# JSON Parsing Implementation - Single PR

## Goal

Replace fragile regex-based parsing with robust JSON parsing in one complete PR.

## Scope

- ✅ Implement JSON parsers for ruff, mypy, bandit
- ✅ Add validation layer with count checking
- ✅ Update hook execution to use JSON flags
- ✅ Remove old regex parsers
- ✅ Update all tests
- ❌ NO feature flags
- ❌ NO gradual rollout
- ❌ NO backward compatibility

## Implementation Steps

### 1. Create Parser Infrastructure (30 min)

**Files to create:**

- `crackerjack/parsers/__init__.py`
- `crackerjack/parsers/base.py` - Protocol interfaces
- `crackerjack/parsers/factory.py` - Parser factory with validation
- `crackerjack/models/tool_config.py` - Tool configurations

**Code structure:**

```python
# parsers/base.py
from typing import Protocol
from crackerjack.agents.base import Issue

class ToolParser(Protocol):
    def parse(self, output: str, tool_name: str) -> list[Issue]: ...

class JSONParser(Protocol):
    def parse_json(self, data: dict | list) -> list[Issue]: ...
    def get_issue_count(self, data: dict | list) -> int: ...
```

### 2. Implement JSON Parsers (2 hours)

**Priority order:**

1. `RuffJSONParser` - Highest impact (fixes current bug)
1. `MypyJSONParser` - High usage
1. `BanditJSONParser` - Security critical

**File:** `crackerjack/parsers/json_parsers.py`

```python
import json
import logging
from crackerjack.parsers.base import JSONParser
from crackerjack.agents.base import Issue, IssueType, Priority

logger = logging.getLogger(__name__)

class RuffJSONParser(JSONParser):
    def parse_json(self, data: dict | list) -> list[Issue]:
        if not isinstance(data, list):
            return []

        issues = []
        for item in data:
            try:
                issues.append(Issue(
                    type=self._get_type(item["code"]),
                    severity=self._get_severity(item["code"]),
                    message=f"{item['code']} {item['message']}",
                    file_path=item["filename"],
                    line_number=item["location"]["row"],
                    stage="ruff-check",
                    details=[
                        f"code: {item['code']}",
                        f"fixable: {'fix' in item}"
                    ]
                ))
            except KeyError as e:
                logger.error(f"Missing required field in ruff output: {e}")

        return issues

    def get_issue_count(self, data: dict | list) -> int:
        return len(data) if isinstance(data, list) else 0

    # ... helper methods
```

### 3. Update Hook Execution (30 min)

**File:** `crackerjack/managers/hook_manager.py`

**Change:** Add JSON flags to hook commands

```python
def _get_hook_command(self, hook: HookDefinition) -> list[str]:
    """Get hook command with JSON output format if supported."""
    base_cmd = hook.get_command()

    # Add JSON flags for tools that support it
    json_flags = {
        "ruff": ["--output-format=json"],
        "ruff-check": ["--output-format=json"],
        "mypy": ["--output=json"],
        "bandit": ["-f", "json"],
    }

    hook_name = hook.name
    if hook_name in json_flags:
        return base_cmd + json_flags[hook_name]

    return base_cmd
```

### 4. Replace AutofixCoordinator Parsing (1 hour)

**File:** `crackerjack/core/autofix_coordinator.py`

**Changes:**

1. Import `ParserFactory`
1. Replace `_parse_hook_to_issues()` with factory call
1. Remove old regex parsing methods
1. Add validation

```python
from crackerjack.parsers.factory import ParserFactory, ParsingError

class AutofixCoordinator:
    def __init__(self, ...):
        # ... existing init ...
        self._parser_factory = ParserFactory()

    def _parse_hook_to_issues(
        self,
        hook_name: str,
        raw_output: str
    ) -> list[Issue]:
        """Parse hook output using JSON parser with validation."""
        try:
            # Detect issue count from output summary
            expected_count = self._extract_issue_count(raw_output, hook_name)

            # Parse with validation
            issues = self._parser_factory.parse_with_validation(
                tool_name=hook_name,
                output=raw_output,
                expected_count=expected_count
            )

            logger.info(f"Parsed {len(issues)} issues from '{hook_name}'")
            return issues

        except ParsingError as e:
            logger.error(f"Parsing failed for '{hook_name}': {e}")
            # Re-raise to fail fast - don't silently continue
            raise

    def _extract_issue_count(self, output: str, tool_name: str) -> int:
        """Extract expected issue count from tool output."""
        # Try parsing JSON to get count
        try:
            data = json.loads(output)
            if tool_name == "ruff":
                return len(data) if isinstance(data, list) else 0
            elif tool_name == "bandit":
                return len(data.get("results", [])) if isinstance(data, dict) else 0
            # ... other tools
        except json.JSONDecodeError:
            pass

        # Fallback: count lines that look like issues
        return len([line for line in output.split("\n") if ":" in line and line.strip()])
```

**Remove these methods (no longer needed):**

- `_parse_ruff_output()`
- `_parse_mypy_output()`
- `_parse_bandit_output()`
- `_parse_type_checker_output()`
- `_parse_ruff_format_output()`
- All other regex-based parsers

### 5. Keep Regex Fallback for Tools Without JSON (30 min)

**File:** `crackerjack/parsers/regex_parsers.py`

Keep existing regex parsers for:

- codespell (no JSON support)
- refurb (no JSON support)
- Other tools without JSON

Move these from `autofix_coordinator.py` to dedicated file.

### 6. Update Tests (2 hours)

**Unit tests to create:**

```
tests/parsers/
├── test_json_parsers.py       # Test all JSON parsers
├── test_parser_factory.py     # Test factory + validation
└── fixtures/
    ├── ruff_output.json       # Sample ruff JSON
    ├── mypy_output.json       # Sample mypy JSON
    └── bandit_output.json     # Sample bandit JSON
```

**Tests to update:**

- `tests/test_core_autofix_coordinator.py` - Use factory instead of direct parsing
- Remove tests for old regex methods
- Add tests for validation error cases

**Integration tests:**

- Run real tools and parse their JSON output
- Verify count validation catches mismatches
- Test error handling for malformed JSON

### 7. Documentation (30 min)

**Files to update:**

- `CLAUDE.md` - Document JSON parsing approach
- `docs/AI_FIX_ARCHITECTURE.md` - Update with JSON parsing section
- Add inline docstrings to all new code

### 8. Cleanup (15 min)

**Remove:**

- Old regex parsing code from `autofix_coordinator.py`
- Any dead code imports
- Outdated comments about regex parsing

## Testing Strategy

### Before Committing

```bash
# 1. Unit tests
python -m pytest tests/parsers/ -v

# 2. Integration test - run real tools
uv run ruff check --output-format json . > /tmp/ruff.json
uv run mypy --output json . > /tmp/mypy.json

# 3. Test full workflow with AI-fix
python -m crackerjack run --ai-fix --run-tests

# 4. Verify current bug is fixed
# Should now parse all 16 ruff issues instead of just 1
```

### Success Criteria

- [ ] All 16 ruff issues parsed (current bug fixed)
- [ ] Zero test failures
- [ ] JSON parsers work for ruff, mypy, bandit
- [ ] Regex fallback works for codespell, refurb
- [ ] Validation catches count mismatches
- [ ] Code coverage maintained (no regressions)
- [ ] No regex parsing code remains in `autofix_coordinator.py`

## File Changes Summary

**New files (7):**

1. `crackerjack/parsers/__init__.py`
1. `crackerjack/parsers/base.py`
1. `crackerjack/parsers/factory.py`
1. `crackerjack/parsers/json_parsers.py`
1. `crackerjack/parsers/regex_parsers.py` (moved from autofix_coordinator)
1. `crackerjack/models/tool_config.py`
1. `tests/parsers/test_json_parsers.py`

**Modified files (3):**

1. `crackerjack/core/autofix_coordinator.py` (remove regex parsing, use factory)
1. `crackerjack/managers/hook_manager.py` (add JSON flags)
1. `tests/test_core_autofix_coordinator.py` (update to use factory)

**Estimated total time:** 6-7 hours

## Risk Mitigation

**What if JSON format changes?**

- Tool's JSON schema is part of their API (more stable than text)
- Can add version pinning if needed
- Validation will catch format changes immediately

**What if parsing is slower?**

- Benchmark first (expect \<5% difference)
- Tool execution dominates (seconds vs milliseconds)
- Net impact should be negligible

**What if a tool doesn't output valid JSON?**

- ParsingError raised immediately
- Clear error message with output preview
- Fail fast instead of silent data loss

## Next Steps

1. **Review this plan** - approve or adjust
1. **Start implementation** - work through steps 1-8
1. **Test thoroughly** - verify all success criteria
1. **Single PR** - complete migration in one shot
1. **Merge** - celebrate the bug fix!

______________________________________________________________________

**Ready to start?** Say the word and I'll begin implementation!

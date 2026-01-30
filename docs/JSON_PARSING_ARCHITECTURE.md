# JSON-Based Parsing Architecture for AI-Fix

## Executive Summary

**Problem:** Current regex-based parsing is fragile and breaks when tools change output format.

**Solution:** Switch to JSON output formats where available, with unified parsing architecture.

**Impact:** Eliminates silent failures, improves maintainability, makes system resilient to tool updates.

______________________________________________________________________

## Current State Analysis

### Fragile Regex Parsing

**Location:** `crackerjack/core/autofix_coordinator.py`

**Example Bug (Current Issue):**

```python
# Line 1085 - Fails to parse ruff output with [*] marker
pattern = re.compile(r"^(.+?):(\d+):(\d+):?\s*([A-Z]\d+)\s+(.+)$")

# Ruff outputs: "file.py:10:5: UP017 [*] Use datetime.UTC alias"
# Regex expects: "file.py:10:5: UP017 Use datetime.UTC alias"
# Result: Silent failure - 15 of 16 issues dropped
```

**Problems:**

1. Silent failures when regex doesn't match
1. No validation that parsed count matches tool's reported count
1. Brittle contract with tool output format
1. Different regex patterns for each tool
1. Hard to maintain and debug

### Tools and JSON Support

| Tool | JSON Support | Command | Current Status |
|------|--------------|---------|----------------|
| **ruff** | ✅ Native | `--output-format json` | 🔴 Regex (buggy) |
| **mypy** | ✅ Native | `--output json` | 🔴 Regex |
| **bandit** | ✅ Native | `-f json` | 🔴 Regex |
| **pylint** | ✅ Native | `--output-format json` | ❌ Not integrated |
| **codespell** | ❌ None | N/A | 🔴 Regex only |
| **refurb** | ❌ None | N/A | 🔴 Regex only |
| **complexity** | ✅ Native | `--json` | 🔴 Regex |
| **vulture/skylos** | ⚠️ Custom | Custom parser | 🔴 Regex |

**JSON Coverage:** 6/8 tools (75%)

______________________________________________________________________

## Proposed Architecture

### Design Principles

1. **Parse, Don't Validate:** JSON provides structured data, not text to validate
1. **Fail Loudly:** Missing required fields → explicit error, not silent drop
1. **Validate Counts:** Compare parsed issue count with tool's reported count
1. **Graceful Fallback:** Regex for tools without JSON support
1. **Unified Interface:** All parsers return `list[Issue]`

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Hook Execution                           │
│  (runs tool with JSON flag if supported)                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Tool Output Detection                           │
│  (detect JSON vs text output)                                │
└─────┬──────────────────────────────┬────────────────────────┘
      │                              │
      ▼                              ▼
┌──────────────┐            ┌──────────────┐
│ JSON Parser  │            │ Regex Parser │
│  (Primary)   │            │  (Fallback)  │
└──────┬───────┘            └──────┬───────┘
       │                           │
       └───────────┬───────────────┘
                   ▼
        ┌─────────────────────┐
        │  Validation Layer   │
        │  - Count check      │
        │  - Required fields  │
        │  - Error reporting  │
        └──────────┬──────────┘
                   ▼
        ┌─────────────────────┐
        │   list[Issue]       │
        │  (unified format)   │
        └─────────────────────┘
```

### Implementation Components

#### 1. Tool Configuration Registry

```python
# crackerjack/models/tool_config.py

from dataclasses import dataclass
from enum import Enum

class OutputFormat(str, Enum):
    JSON = "json"
    TEXT = "text"
    CUSTOM = "custom"

@dataclass(frozen=True)
class ToolConfig:
    """Configuration for tool output parsing."""

    name: str
    supports_json: bool
    json_flag: str | None = None  # e.g., "--output-format json"
    output_format: OutputFormat = OutputFormat.JSON
    fallback_to_regex: bool = True
    required_json_fields: set[str] = frozenset()

# Tool configurations
TOOL_CONFIGS: dict[str, ToolConfig] = {
    "ruff": ToolConfig(
        name="ruff",
        supports_json=True,
        json_flag="--output-format=json",
        output_format=OutputFormat.JSON,
        required_json_fields={"filename", "location", "code", "message"}
    ),
    "ruff-check": ToolConfig(
        name="ruff-check",
        supports_json=True,
        json_flag="--output-format=json",
        output_format=OutputFormat.JSON,
        required_json_fields={"filename", "location", "code", "message"}
    ),
    "mypy": ToolConfig(
        name="mypy",
        supports_json=True,
        json_flag="--output=json",
        output_format=OutputFormat.JSON,
        required_json_fields={"file", "line", "column", "message"}
    ),
    "bandit": ToolConfig(
        name="bandit",
        supports_json=True,
        json_flag="-f json",
        output_format=OutputFormat.JSON,
        required_json_fields={"filename", "issue_text", "line_number", "issue_severity"}
    ),
    "codespell": ToolConfig(
        name="codespell",
        supports_json=False,
        output_format=OutputFormat.TEXT,
        fallback_to_regex=True
    ),
    "refurb": ToolConfig(
        name="refurb",
        supports_json=False,
        output_format=OutputFormat.TEXT,
        fallback_to_regex=True
    ),
    "complexity": ToolConfig(
        name="complexity",
        supports_json=True,
        json_flag="--json",
        output_format=OutputFormat.JSON,
        required_json_fields={"file", "function", "complexity"}
    ),
}
```

#### 2. Unified Parser Interface

```python
# crackerjack/parsers/base_parser.py

from abc import ABC, abstractmethod
from typing import Protocol

class ToolParser(Protocol):
    """Protocol for tool output parsers."""

    def parse(self, output: str, tool_name: str) -> list[Issue]:
        """Parse tool output into Issue objects."""
        ...

    def validate_output(
        self,
        output: str,
        expected_count: int | None = None
    ) -> bool:
        """Validate that output was parsed correctly."""
        ...

class JSONParser(ABC):
    """Base class for JSON-based parsers."""

    @abstractmethod
    def parse_json(self, data: dict | list) -> list[Issue]:
        """Parse JSON data into Issue objects."""
        ...

    @abstractmethod
    def get_issue_count(self, data: dict | list) -> int:
        """Extract issue count from JSON data."""
        ...

class RegexParser(ABC):
    """Base class for regex-based parsers (fallback)."""

    @abstractmethod
    def parse_text(self, output: str) -> list[Issue]:
        """Parse text output into Issue objects."""
        ...
```

#### 3. JSON Parser Implementations

```python
# crackerjack/parsers/json_parsers.py

import json
import logging
from typing import Any

from crackerjack.parsers.base_parser import JSONParser
from crackerjack.agents.base import Issue, IssueType, Priority

logger = logging.getLogger(__name__)

class RuffJSONParser(JSONParser):
    """Parse ruff JSON output."""

    def parse_json(self, data: dict | list) -> list[Issue]:
        """Parse ruff JSON output.

        Ruff JSON format:
        [
            {
                "filename": "path/to/file.py",
                "location": {"row": 10, "column": 5},
                "code": "UP017",
                "message": "Use `datetime.UTC` alias",
                "fix": {...},  # Optional: available if fixable
                "url": "https://docs.astral.sh/ruff/rules/UP017"
            }
        ]
        """
        if not isinstance(data, list):
            logger.warning(f"Expected list from ruff, got {type(data)}")
            return []

        issues: list[Issue] = []

        for item in data:
            try:
                # Validate required fields
                if not all(k in item for k in ["filename", "location", "code", "message"]):
                    logger.warning(f"Skipping ruff item missing required fields: {item}")
                    continue

                file_path = item["filename"]
                line_number = item["location"].get("row")
                code = item["code"]
                message = item["message"]

                issue_type = self._get_issue_type(code)
                severity = self._get_severity(code)

                issues.append(Issue(
                    type=issue_type,
                    severity=severity,
                    message=f"{code} {message}",
                    file_path=file_path,
                    line_number=line_number,
                    stage="ruff-check",
                    details=[
                        f"code: {code}",
                        f"fixable: {'fix' in item}"
                    ]
                ))
            except Exception as e:
                logger.error(f"Error parsing ruff JSON item: {e}", exc_info=True)

        logger.info(f"Parsed {len(issues)} issues from ruff JSON output")
        return issues

    def _get_issue_type(self, code: str) -> IssueType:
        """Map ruff code to IssueType."""
        if code.startswith("C9"):
            return IssueType.COMPLEXITY
        if code.startswith("S"):
            return IssueType.SECURITY
        if code.startswith("F4"):
            return IssueType.IMPORT_ERROR
        return IssueType.FORMATTING

    def _get_severity(self, code: str) -> Priority:
        """Map ruff code to Priority."""
        if code.startswith(("C9", "S")):
            return Priority.HIGH
        if code.startswith("F4"):
            return Priority.MEDIUM
        return Priority.LOW

    def get_issue_count(self, data: dict | list) -> int:
        """Get issue count from ruff JSON."""
        return len(data) if isinstance(data, list) else 0


class MypyJSONParser(JSONParser):
    """Parse mypy JSON output."""

    def parse_json(self, data: dict | list) -> list[Issue]:
        """Parse mypy JSON output.

        Mypy JSON format:
        [
            {
                "file": "path/to/file.py",
                "line": 10,
                "column": 5,
                "message": "Incompatible return value type",
                "severity": "error",
                "code": "error"
            }
        ]
        """
        if not isinstance(data, list):
            logger.warning(f"Expected list from mypy, got {type(data)}")
            return []

        issues: list[Issue] = []

        for item in data:
            try:
                # Validate required fields
                if not all(k in item for k in ["file", "line", "message"]):
                    logger.warning(f"Skipping mypy item missing required fields: {item}")
                    continue

                file_path = item["file"]
                line_number = item.get("line")
                message = item["message"]
                severity_str = item.get("severity", "error")

                issues.append(Issue(
                    type=IssueType.TYPE_ERROR,
                    severity=Priority.HIGH if severity_str == "error" else Priority.MEDIUM,
                    message=message,
                    file_path=file_path,
                    line_number=line_number,
                    stage="mypy",
                    details=[f"severity: {severity_str}"]
                ))
            except Exception as e:
                logger.error(f"Error parsing mypy JSON item: {e}", exc_info=True)

        logger.info(f"Parsed {len(issues)} issues from mypy JSON output")
        return issues

    def get_issue_count(self, data: dict | list) -> int:
        """Get issue count from mypy JSON."""
        return len(data) if isinstance(data, list) else 0


class BanditJSONParser(JSONParser):
    """Parse bandit JSON output."""

    def parse_json(self, data: dict | list) -> list[Issue]:
        """Parse bandit JSON output.

        Bandit JSON format:
        {
            "results": [
                {
                    "filename": "path/to/file.py",
                    "line_number": 42,
                    "issue_text": "Description of security issue",
                    "issue_severity": "HIGH",
                    "test_id": "B201",
                    "test_name": "flask_debug_true"
                }
            ]
        }
        """
        if not isinstance(data, dict) or "results" not in data:
            logger.warning(f"Expected dict with 'results' from bandit, got {type(data)}")
            return []

        issues: list[Issue] = []

        for item in data["results"]:
            try:
                # Validate required fields
                if not all(k in item for k in ["filename", "issue_text", "line_number"]):
                    logger.warning(f"Skipping bandit item missing required fields: {item}")
                    continue

                file_path = item["filename"]
                line_number = item.get("line_number")
                message = item["issue_text"]
                severity_str = item.get("issue_severity", "MEDIUM")
                test_id = item.get("test_id", "UNKNOWN")

                severity = self._map_severity(severity_str)

                issues.append(Issue(
                    type=IssueType.SECURITY,
                    severity=severity,
                    message=f"{test_id}: {message}",
                    file_path=file_path,
                    line_number=line_number,
                    stage="bandit",
                    details=[
                        f"test_id: {test_id}",
                        f"severity: {severity_str}"
                    ]
                ))
            except Exception as e:
                logger.error(f"Error parsing bandit JSON item: {e}", exc_info=True)

        logger.info(f"Parsed {len(issues)} issues from bandit JSON output")
        return issues

    def _map_severity(self, severity_str: str) -> Priority:
        """Map bandit severity to Priority."""
        mapping = {
            "HIGH": Priority.CRITICAL,
            "MEDIUM": Priority.HIGH,
            "LOW": Priority.MEDIUM
        }
        return mapping.get(severity_str, Priority.MEDIUM)

    def get_issue_count(self, data: dict | list) -> int:
        """Get issue count from bandit JSON."""
        if isinstance(data, dict) and "results" in data:
            return len(data["results"])
        return 0
```

#### 4. Parser Factory with Validation

```python
# crackerjack/parsers/parser_factory.py

import json
import logging
from typing import Any

from crackerjack.models.tool_config import TOOL_CONFIGS, ToolConfig
from crackerjack.parsers.base_parser import ToolParser, JSONParser, RegexParser
from crackerjack.parsers.json_parsers import RuffJSONParser, MypyJSONParser, BanditJSONParser
from crackerjack.parsers.regex_parsers import (  # Existing regex parsers
    RuffRegexParser, MypyRegexParser, CodespellRegexParser, etc.
)
from crackerjack.agents.base import Issue

logger = logging.getLogger(__name__)

class ParserFactory:
    """Factory for creating tool output parsers with validation."""

    # JSON parser registry
    JSON_PARSERS: dict[str, type[JSONParser]] = {
        "ruff": RuffJSONParser,
        "ruff-check": RuffJSONParser,
        "mypy": MypyJSONParser,
        "bandit": BanditJSONParser,
        # "zuban": ZubanJSONParser,  # Custom type checker
        # "complexity": ComplexityJSONParser,
    }

    # Regex parser registry (fallback)
    REGEX_PARSERS: dict[str, type[RegexParser]] = {
        "ruff": RuffRegexParser,
        "mypy": MypyRegexParser,
        "codespell": CodespellRegexParser,
        "refurb": RefurbRegexParser,
        # ... existing regex parsers
    }

    def create_parser(self, tool_name: str) -> ToolParser:
        """Create appropriate parser for tool.

        Strategy:
        1. Check if tool supports JSON
        2. If yes, create JSON parser
        3. If no, create regex parser (if available)
        """
        config = TOOL_CONFIGS.get(tool_name)

        if config and config.supports_json and tool_name in self.JSON_PARSERS:
            logger.debug(f"Using JSON parser for '{tool_name}'")
            return self.JSON_PARSERS[tool_name]()

        if tool_name in self.REGEX_PARSERS:
            logger.debug(f"Using regex parser for '{tool_name}' (JSON not supported)")
            return self.REGEX_PARSERS[tool_name]()

        logger.warning(f"No parser found for '{tool_name}', using generic parser")
        return GenericRegexParser(tool_name)

    def parse_with_validation(
        self,
        tool_name: str,
        output: str,
        expected_count: int | None = None
    ) -> list[Issue]:
        """Parse tool output with validation.

        Args:
            tool_name: Name of the tool
            output: Raw tool output (JSON or text)
            expected_count: Expected number of issues (for validation)

        Returns:
            List of parsed issues

        Raises:
            ParsingError: If validation fails
        """
        parser = self.create_parser(tool_name)

        # Detect if output is JSON
        is_json = self._is_json_output(output)

        if is_json:
            issues = self._parse_json_output(parser, output, tool_name)
        else:
            issues = self._parse_text_output(parser, output, tool_name)

        # Validation
        if expected_count is not None:
            self._validate_issue_count(issues, expected_count, tool_name, output)

        return issues

    def _is_json_output(self, output: str) -> bool:
        """Detect if output is JSON."""
        stripped = output.strip()
        return stripped.startswith(("{", "["))

    def _parse_json_output(
        self,
        parser: ToolParser,
        output: str,
        tool_name: str
    ) -> list[Issue]:
        """Parse JSON output."""
        try:
            data = json.loads(output)

            if isinstance(parser, JSONParser):
                return parser.parse_json(data)
            else:
                logger.warning(
                    f"JSON output detected but parser for '{tool_name}' "
                    f"doesn't support JSON, falling back to text parsing"
                )
                return parser.parse(output)  # Will treat as text

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from '{tool_name}': {e}")
            logger.debug(f"Output preview: {output[:500]}")
            raise ParsingError(
                f"Invalid JSON output from {tool_name}: {e}",
                tool_name=tool_name,
                output=output
            ) from e

    def _parse_text_output(
        self,
        parser: ToolParser,
        output: str,
        tool_name: str
    ) -> list[Issue]:
        """Parse text output."""
        return parser.parse(output, tool_name)

    def _validate_issue_count(
        self,
        issues: list[Issue],
        expected_count: int,
        tool_name: str,
        output: str
    ) -> None:
        """Validate that parsed issue count matches expected."""
        actual_count = len(issues)

        if actual_count != expected_count:
            error_msg = (
                f"Issue count mismatch for '{tool_name}': "
                f"expected {expected_count}, parsed {actual_count}"
            )

            # Log details for debugging
            logger.error(error_msg)
            logger.debug(f"Output preview: {output[:500]}")
            logger.debug(f"Parsed issues: {[str(i)[:100] for i in issues[:5]]}")

            raise ParsingError(
                error_msg,
                tool_name=tool_name,
                expected_count=expected_count,
                actual_count=actual_count,
                output=output
            )

        logger.debug(
            f"Validation passed for '{tool_name}': "
            f"{actual_count} issues parsed (expected {expected_count})"
        )


class ParsingError(Exception):
    """Error raised when parsing fails validation."""

    def __init__(
        self,
        message: str,
        tool_name: str,
        expected_count: int | None = None,
        actual_count: int | None = None,
        output: str | None = None
    ):
        super().__init__(message)
        self.tool_name = tool_name
        self.expected_count = expected_count
        self.actual_count = actual_count
        self.output = output
```

#### 5. Integration with Autofix Coordinator

```python
# crackerjack/core/autofix_coordinator.py (MODIFIED)

from crackerjack.parsers.parser_factory import ParserFactory, ParsingError

class AutofixCoordinator:
    def __init__(self, ...):
        # ... existing init ...
        self._parser_factory = ParserFactory()

    def _parse_hook_to_issues(
        self,
        hook_name: str,
        raw_output: str,
        expected_count: int | None = None
    ) -> list[Issue]:
        """Parse hook output using appropriate parser.

        Args:
            hook_name: Name of the hook
            raw_output: Raw tool output
            expected_count: Expected issue count (from tool's summary)

        Returns:
            List of parsed issues

        Raises:
            ParsingError: If validation fails
        """
        try:
            issues = self._parser_factory.parse_with_validation(
                tool_name=hook_name,
                output=raw_output,
                expected_count=expected_count
            )

            logger.info(
                f"Successfully parsed {len(issues)} issues from '{hook_name}'"
            )

            return issues

        except ParsingError as e:
            # Re-raise with context
            self.logger.error(
                f"Failed to parse '{hook_name}' output: {e}",
                exc_info=True
            )
            raise  # Let caller handle the error
```

______________________________________________________________________

## Migration Strategy

### Phase 1: Foundation (Week 1)

- [ ] Create `crackerjack/models/tool_config.py` with tool configurations
- [ ] Create `crackerjack/parsers/` package structure
- [ ] Create base parser interfaces (`base_parser.py`)
- [ ] Add comprehensive unit tests for parser factory
- [ ] Document JSON output formats for all tools

### Phase 2: JSON Parsers (Week 2)

- [ ] Implement `RuffJSONParser`
- [ ] Implement `MypyJSONParser`
- [ ] Implement `BanditJSONParser`
- [ ] Add unit tests with real tool output samples
- [ ] Test with various ruff versions for format stability

### Phase 3: Integration (Week 3)

- [ ] Modify hook execution to add JSON flags to commands
- [ ] Update `AutofixCoordinator` to use `ParserFactory`
- [ ] Add validation layer with count checks
- [ ] Integration tests with full workflow
- [ ] Performance benchmarks (JSON vs regex)

### Phase 4: Rollout (Week 4)

- [ ] Feature flag: `CRACKERJACK_USE_JSON_PARSERS=true`
- [ ] Run in parallel with regex parsers (compare results)
- [ ] Monitor for discrepancies in production
- [ ] Gradual rollout to all hooks
- [ ] Remove old regex parsers

### Phase 5: Remaining Tools (Week 5)

- [ ] Implement JSON parsers for pylint, complexity
- [ ] Improve regex parsers for codespell, refurb
- [ ] Explore alternative tools with JSON support
- [ ] Document tools without JSON support

______________________________________________________________________

## Validation Strategy

### 1. Count Validation

```python
# Extract tool's reported issue count
ruff_output = """
{
  "results": [...],
  "summary": {
    "error_count": 15,
    "warning_count": 1
  }
}
"""

# Parse JSON
issues = parser.parse_json(data)

# Validate count
parser.validate_output(
    output=ruff_output,
    expected_count=16  # 15 errors + 1 warning
)

# If len(issues) != 16 → raise ParsingError
```

### 2. Field Validation

```python
# Validate required fields present
for item in json_data:
    missing = config.required_fields - item.keys()
    if missing:
        logger.warning(f"Missing fields {missing} in item: {item}")
        continue  # Skip this item, don't silently fail
```

### 3. Comparison Testing

```bash
# Run both parsers in parallel during migration
CRACKERJACK_USE_JSON_PARSERS=true python -m crackerjack run --ai-fix
CRACKERJACK_USE_JSON_PARSERS=false python -m crackerjack run --ai-fix

# Compare results
python scripts/compare_parsing_results.py json_output.json regex_output.json
```

______________________________________________________________________

## Performance Considerations

### JSON vs Regex Performance

| Aspect | Regex | JSON |
|--------|-------|------|
| **Parsing Speed** | Fast (compiled regex) | Medium (json.loads) |
| **Maintainability** | Poor (brittle patterns) | Excellent (stable schemas) |
| **Error Detection** | Silent failures | Explicit validation |
| **Tool Updates** | Breaks often | Rarely breaks |
| **Debugging** | Hard (regex complexity) | Easy (structured data) |

**Expected Performance Impact:**

- JSON parsing: ~2-5x slower than regex
- BUT: Tool execution dominates (seconds vs milliseconds)
- Net impact: \<1% difference in total workflow time
- Trade-off: Worth it for reliability

### Optimization Strategies

1. **Reuse JSON parsers** (don't recreate per issue)
1. **Cache parsed schemas** if using JSON schema validation
1. **Batch parsing** for tools with multiple files
1. **Lazy validation** in development, strict in CI

______________________________________________________________________

## Error Handling

### Current (Silent Failures)

```python
# Regex doesn't match → issue silently dropped
for line in raw_output.split("\n"):
    match = pattern.match(line)
    if not match:
        continue  # ❌ Silent failure
```

### Proposed (Explicit Errors)

```python
# Validation error → explicit exception
try:
    issues = parser_factory.parse_with_validation(
        tool_name="ruff",
        output=raw_output,
        expected_count=16
    )
except ParsingError as e:
    # ✅ Explicit error with context
    logger.error(
        f"Parsing failed for ruff: {e}\n"
        f"Expected: {e.expected_count} issues\n"
        f"Parsed: {e.actual_count} issues\n"
        f"Output preview: {e.output[:500]}"
    )
    # Decide: abort or continue with partial results?
```

______________________________________________________________________

## Testing Strategy

### Unit Tests

```python
# tests/parsers/test_ruff_json_parser.py

import json
import pytest
from crackerjack.parsers.json_parsers import RuffJSONParser

@pytest.fixture
def ruff_json_output():
    """Real ruff JSON output sample."""
    return json.dumps([
        {
            "filename": "test.py",
            "location": {"row": 10, "column": 5},
            "code": "UP017",
            "message": "Use `datetime.UTC` alias",
            "fix": {"applicability": "automatic"}
        },
        {
            "filename": "test.py",
            "location": {"row": 20, "column": 8},
            "code": "I001",
            "message": "Import block is un-sorted",
        }
    ])

def test_parse_ruff_json(ruff_json_output):
    """Test parsing ruff JSON output."""
    parser = RuffJSONParser()
    data = json.loads(ruff_json_output)

    issues = parser.parse_json(data)

    assert len(issues) == 2
    assert issues[0].file_path == "test.py"
    assert issues[0].line_number == 10
    assert "UP017" in issues[0].message
    assert issues[0].details[0] == "fixable: True"  # Has 'fix' field

    assert issues[1].line_number == 20
    assert "I001" in issues[1].message
    assert issues[1].details[0] == "fixable: False"  # No 'fix' field

def test_get_issue_count(ruff_json_output):
    """Test extracting issue count."""
    parser = RuffJSONParser()
    data = json.loads(ruff_json_output)

    count = parser.get_issue_count(data)
    assert count == 2
```

### Integration Tests

```python
# tests/integration/test_json_parsing_workflow.py

import subprocess
import json

def test_ruff_json_parsing_in_workflow():
    """Test that ruff JSON parsing works in full workflow."""
    # Run ruff with JSON output
    result = subprocess.run(
        ["uv", "run", "ruff", "check", "--output-format=json", "."],
        capture_output=True,
        text=True
    )

    # Parse JSON
    data = json.loads(result.stdout)

    # Use parser
    from crackerjack.parsers.parser_factory import ParserFactory
    factory = ParserFactory()

    issues = factory.parse_with_validation(
        tool_name="ruff",
        output=result.stdout,
        expected_count=len(data)  # All items should be parsed
    )

    # Validate
    assert len(issues) == len(data)
    assert all(i.file_path for i in issues)
```

### Regression Tests

```python
# tests/regression/test_parser_comparison.py

def test_json_regex_parity():
    """Ensure JSON parser produces same results as regex for valid output."""
    # Sample output that both parsers should handle
    sample = "..."

    factory = ParserFactory()

    # Parse with JSON (simulate)
    json_issues = factory.parse_with_validation(
        tool_name="ruff",
        output=sample,
        expected_count=None
    )

    # Parse with regex (old way)
    regex_issues = old_regex_parser.parse(sample)

    # Should be identical
    assert len(json_issues) == len(regex_issues)
    for j, r in zip(json_issues, regex_issues):
        assert j.file_path == r.file_path
        assert j.line_number == r.line_number
        assert j.message == r.message
```

______________________________________________________________________

## Rollout Plan

### 1. Development Environment

```bash
# Enable JSON parsing in dev
export CRACKERJACK_USE_JSON_PARSERS=true

# Run workflow
python -m crackerjack run --ai-fix

# Compare with old regex parsing
export CRACKERJACK_USE_JSON_PARSERS=false
python -m crackerjack run --ai-fix
```

### 2. Staging Environment

```bash
# Feature flag in config
# settings/crackerjack.yaml
use_json_parsing: true

# Run full test suite
python -m crackerjack run --run-tests -c

# Monitor logs for parsing errors
grep "ParsingError" logs/crackerjack.log
```

### 3. Production Rollout

- Week 1: Monitor with feature flag (10% of runs)
- Week 2: Increase to 50% of runs
- Week 3: 100% of runs
- Week 4: Remove old regex code

______________________________________________________________________

## Benefits

### Immediate Benefits

1. **Fixes Current Bug:** Ruff [\*] marker issue eliminated
1. **No Silent Failures:** Validation catches parsing errors immediately
1. **Easier Debugging:** JSON is human-readable and structured
1. **Better Error Messages:** Know exactly which field is missing

### Long-term Benefits

1. **Maintainability:** Tool updates don't break parsing
1. **Reliability:** Stable schemas backed by tool APIs
1. **Extensibility:** Easy to add new tools
1. **Testability:** JSON samples are easy to mock

### Developer Experience

```python
# Before: Regex complexity
pattern = re.compile(r"^(.+?):(\d+):(\d+):?\s*([A-Z]\d+)\s+(.+)$")
match = pattern.match(line)
if not match:
    continue  # ❌ What went wrong?

# After: Clear structure
item = json_data[0]
if "filename" in item and "location" in item:
    issue = Issue(
        file_path=item["filename"],
        line_number=item["location"]["row"],
        ...
    )
else:
    logger.warning(f"Missing fields: {item}")  # ✅ Clear problem
```

______________________________________________________________________

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Tool changes JSON schema** | Medium | Version pinning + schema validation |
| **Performance degradation** | Low | Benchmarking + caching |
| **Missing field in old tool version** | Medium | Required field config + graceful degradation |
| **JSON output less verbose** | Low | Keep regex as fallback |

______________________________________________________________________

## Open Questions

1. **Tools without JSON support** (codespell, refurb):

   - Status: Keep regex parsers
   - Alternative: Find replacement tools with JSON support?

1. **Custom tool wrappers** (zuban, skylos):

   - Can we modify them to output JSON?
   - Or add JSON serialization layer?

1. **Error recovery**:

   - When parsing fails, should we abort or continue with partial results?
   - Proposal: Configurable `strict_mode` (default: abort in CI, continue in dev)

1. **Backward compatibility**:

   - How long to maintain regex parsers?
   - Proposal: Keep for 2 major versions, deprecate with warnings

______________________________________________________________________

## Success Metrics

### Technical Metrics

- [ ] All 16 ruff issues parsed successfully (current bug fixed)
- [ ] Zero silent parsing failures in logs
- [ ] 100% count validation accuracy
- [ ] \<5% performance overhead vs regex

### Quality Metrics

- [ ] 90%+ test coverage for new parser code
- [ ] Zero parsing errors in sample output files
- [ ] Successful migration of 6/8 tools to JSON

### Developer Experience

- [ ] Reduced debugging time for parsing issues
- [ ] Easier onboarding for new contributors
- [ ] Clear error messages for all failure modes

______________________________________________________________________

## Next Steps

1. **Review this proposal** with team
1. **Create implementation plan** with task breakdown
1. **Set up feature flags** for gradual rollout
1. **Start Phase 1** (Foundation)
1. **Weekly syncs** to track progress

______________________________________________________________________

## Appendix: Tool JSON Format Samples

### Ruff JSON Output

```json
[
  {
    "filename": "crackerjack/core/auth.py",
    "location": {"row": 51, "column": 34},
    "end_location": {"row": 51, "column": 42},
    "code": "UP017",
    "message": "Use `datetime.UTC` alias",
    "fix": {
      "applicability": "automatic",
      "edits": [
        {
          "content": "datetime.UTC",
          "location": {"row": 51, "column": 34},
          "end_location": {"row": 51, "column": 42}
        }
      ]
    },
    "url": "https://docs.astral.sh/ruff/rules/upcase-datetime-alias",
    "parent": null
  }
]
```

### Mypy JSON Output

```json
[
  {
    "file": "crackerjack/core/auth.py",
    "line": 51,
    "column": 34,
    "message": "Argument 1 has incompatible type \"None\"; expected \"str\"",
    "severity": "error",
    "code": "arg-type"
  }
]
```

### Bandit JSON Output

```json
{
  "metrics": {
    "total_issues": {"severity": {"HIGH": 0, "MEDIUM": 2, "LOW": 1}}
  },
  "results": [
    {
      "code": "debug = True\n",
      "filename": "app.py",
      "issue_confidence": "HIGH",
      "issue_severity": "MEDIUM",
      "issue_text": "A Flask app appears to be run with debug=True, which exposes the Werkzeug debugger...",
      "line_number": 42,
      "line_range": [42, 42],
      "more_info": "https://bandit.readthedocs.io/en/latest/plugins/b201_flask_debug_true.html",
      "test_id": "B201",
      "test_name": "flask_debug_true"
    }
  ],
  "generated_at": "2025-01-29T12:34:56Z"
}
```

______________________________________________________________________

**Document Version:** 1.0
**Last Updated:** 2025-01-29
**Author:** Claude (AI Assistant)
**Status:** Proposal - Awaiting Review

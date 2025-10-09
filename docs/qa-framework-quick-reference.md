# QA Framework Quick Reference

**For:** Developers implementing new QA adapters
**Last Updated:** 2025-10-09

## TL;DR

```python
# Create a new QA adapter in 3 steps:
# 1. Define settings
# 2. Create adapter class with check() method
# 3. Register with orchestrator
```

## Minimal Example

```python
# adapters/qa/my_check.py
from uuid import UUID
from crackerjack.adapters.qa.base import QAAdapterBase, QABaseSettings
from crackerjack.models.qa_results import QAResult, QAResultStatus, QACheckType

class MyCheckSettings(QABaseSettings):
    # Add custom settings here
    pass

class MyCheckAdapter(QAAdapterBase):
    MODULE_ID = UUID("01937d86-xxxx-xxxx-xxxx-xxxxxxxxxxxx")  # Generate unique UUID7
    MODULE_STATUS = "stable"

    def __init__(self):
        super().__init__()
        self.settings = MyCheckSettings()

    async def check(self, files=None, config=None):
        # Run your check here
        return QAResult(
            check_id=self.MODULE_ID,
            check_name="my-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            message="Check passed",
        )

    async def validate_config(self, config):
        return True

    def get_default_config(self):
        from crackerjack.models.qa_config import QACheckConfig
        return QACheckConfig(
            enabled=True,
            timeout_seconds=60,
            file_patterns=["**/*.py"],
        )
```

## Directory Structure

```
crackerjack/
├── adapters/qa/          # All QA adapters go here
│   ├── base.py           # Don't modify (base classes)
│   ├── ruff_format.py    # Example adapter
│   └── your_adapter.py   # Add new adapters here
├── models/
│   ├── qa_results.py     # Result models (don't modify)
│   └── qa_config.py      # Config models (don't modify)
└── services/
    └── qa_orchestrator.py  # Don't modify (uses adapters)
```

## Import Cheat Sheet

```python
# Base classes and protocols
from crackerjack.adapters.qa.base import (
    QAAdapterBase,           # Inherit from this
    QABaseSettings,          # Inherit for settings
    QAAdapterProtocol,       # Type hints only
)

# Result models
from crackerjack.models.qa_results import (
    QAResult,                # Return from check()
    QAResultStatus,          # SUCCESS, FAILURE, WARNING, ERROR, SKIPPED
    QACheckType,             # LINT, FORMAT, TYPE_CHECK, SECURITY, TEST, etc.
)

# Configuration
from crackerjack.models.qa_config import (
    QACheckConfig,           # Per-check config
    QAOrchestratorConfig,    # Orchestrator config
)

# ACB imports (optional enhancements)
from acb.adapters import AdapterMetadata, AdapterStatus, AdapterCapability
from acb.cleanup import CleanupMixin
```

## Common Patterns

### 1. File Discovery and Filtering

```python
async def check(self, files=None, config=None):
    check_config = config or self.get_default_config()

    # Determine files to check
    files_to_check = files or self._discover_python_files()

    # Filter by patterns
    files_to_check = [
        f for f in files_to_check
        if self._should_check_file(f, check_config)
    ]

    if not files_to_check:
        return QAResult(
            check_id=self.MODULE_ID,
            check_name="my-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SKIPPED,
            message="No files to check",
        )
```

### 2. Running External Commands

```python
import asyncio
import subprocess

async def check(self, files=None, config=None):
    cmd = ["tool-name", "--flag", *files]

    try:
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await result.communicate()

        if result.returncode == 0:
            return QAResult(
                check_id=self.MODULE_ID,
                check_name="my-check",
                check_type=QACheckType.LINT,
                status=QAResultStatus.SUCCESS,
                message="Check passed",
            )
        else:
            return QAResult(
                check_id=self.MODULE_ID,
                check_name="my-check",
                check_type=QACheckType.LINT,
                status=QAResultStatus.FAILURE,
                message="Issues found",
                details=stdout.decode() + stderr.decode(),
            )
    except Exception as e:
        return QAResult(
            check_id=self.MODULE_ID,
            check_name="my-check",
            check_type=QACheckType.LINT,
            status=QAResultStatus.ERROR,
            message=f"Check failed: {str(e)}",
        )
```

### 3. Execution Timing

```python
import time

async def check(self, files=None, config=None):
    start_time = time.time()

    # ... perform check ...

    execution_time_ms = (time.time() - start_time) * 1000

    return QAResult(
        # ... other fields ...
        execution_time_ms=execution_time_ms,
    )
```

### 4. Enhanced Metadata (Recommended)

```python
from acb.adapters import AdapterMetadata, AdapterStatus, AdapterCapability
from uuid import UUID

MODULE_METADATA = AdapterMetadata(
    module_id=UUID("01937d86-xxxx-xxxx-xxxx-xxxxxxxxxxxx"),
    name="My Check Adapter",
    category="qa",
    provider="provider-name",
    version="1.0.0",
    acb_min_version="0.19.0",
    status=AdapterStatus.STABLE,
    capabilities=[AdapterCapability.ASYNC_OPERATIONS],
    required_packages=["tool>=1.0.0"],
    description="Brief description of what this adapter does",
)

class MyCheckAdapter(QAAdapterBase):
    MODULE_ID = MODULE_METADATA.module_id
    MODULE_STATUS = "stable"
    MODULE_METADATA = MODULE_METADATA  # Optional but recommended
```

## QAResult Fields

```python
QAResult(
    check_id=UUID,              # REQUIRED: Your adapter's MODULE_ID
    check_name=str,             # REQUIRED: Human-readable name (e.g., "ruff-format")
    check_type=QACheckType,     # REQUIRED: LINT, FORMAT, TYPE_CHECK, etc.
    status=QAResultStatus,      # REQUIRED: SUCCESS, FAILURE, WARNING, ERROR, SKIPPED

    message=str,                # Optional: Summary message
    details=str,                # Optional: Detailed output (stdout/stderr)
    files_checked=list[Path],   # Optional: Files that were checked
    files_modified=list[Path],  # Optional: Files modified (formatters)
    issues_found=int,           # Optional: Number of issues found
    issues_fixed=int,           # Optional: Number of issues auto-fixed
    execution_time_ms=float,    # Optional: How long it took
    timestamp=datetime,         # Optional: When it ran (auto-set)
    metadata=dict,              # Optional: Any custom data
)
```

## QACheckType Enum

```python
class QACheckType(str, Enum):
    LINT = "lint"               # Style/quality checks (ruff, pylint)
    FORMAT = "format"           # Code formatting (black, ruff format)
    TYPE_CHECK = "type_check"   # Type checking (mypy, pyright, zuban)
    SECURITY = "security"       # Security scanning (bandit, safety)
    TEST = "test"               # Test execution (pytest)
    REFACTOR = "refactor"       # Refactoring suggestions
    UTILITY = "utility"         # Other checks
```

## QAResultStatus Enum

```python
class QAResultStatus(str, Enum):
    SUCCESS = "success"         # Check passed
    FAILURE = "failure"         # Check failed (issues found)
    WARNING = "warning"         # Issues found but not critical
    SKIPPED = "skipped"         # Check was skipped
    ERROR = "error"             # Check failed to run (exception)
```

## Registration Example

```python
# In your workflow/coordinator
from crackerjack.services.qa_orchestrator import QAOrchestrator
from crackerjack.adapters.qa.my_check import MyCheckAdapter

# Create orchestrator
orchestrator = QAOrchestrator(config)

# Register your adapter
orchestrator.register_adapter(MyCheckAdapter())

# Run checks
results = await orchestrator.run_checks()
```

## Testing Template

```python
# tests/unit/adapters/qa/test_my_check.py
import pytest
from crackerjack.adapters.qa.my_check import MyCheckAdapter
from crackerjack.models.qa_results import QAResultStatus

class TestMyCheckAdapter:
    @pytest.fixture
    def adapter(self):
        return MyCheckAdapter()

    @pytest.mark.asyncio
    async def test_check_success(self, adapter):
        result = await adapter.check()
        assert result.status == QAResultStatus.SUCCESS

    @pytest.mark.asyncio
    async def test_validate_config(self, adapter):
        config = adapter.get_default_config()
        assert await adapter.validate_config(config) is True

    def test_default_config(self, adapter):
        config = adapter.get_default_config()
        assert config.enabled is True
```

## Common Mistakes to Avoid

❌ **Don't hardcode file paths:**
```python
# Bad
files = [Path("/absolute/path/to/file.py")]

# Good
files = list(Path.cwd().rglob("*.py"))
```

❌ **Don't forget error handling:**
```python
# Bad
result = await subprocess.check_output(cmd)

# Good
try:
    result = await asyncio.create_subprocess_exec(...)
except Exception as e:
    return QAResult(..., status=QAResultStatus.ERROR)
```

❌ **Don't block the event loop:**
```python
# Bad
time.sleep(5)

# Good
await asyncio.sleep(5)
```

❌ **Don't return raw exceptions:**
```python
# Bad
async def check(self, ...):
    raise Exception("Something went wrong")

# Good
async def check(self, ...):
    try:
        # ... code ...
    except Exception as e:
        return QAResult(
            ...,
            status=QAResultStatus.ERROR,
            message=str(e),
        )
```

## UUID Generation

```python
# Use UUID7 for time-ordered UUIDs
from uuid import UUID

# Generate: https://www.uuidtools.com/v7
# Or use Python: pip install uuid7
from uuid7 import uuid7
MODULE_ID = uuid7()
```

## File Pattern Matching

```python
# Include patterns
file_patterns = [
    "**/*.py",          # All Python files
    "src/**/*.ts",      # TypeScript in src/
    "tests/unit/**/*",  # All files in tests/unit/
]

# Exclude patterns
exclude_patterns = [
    "**/migrations/**",     # Django migrations
    "**/.venv/**",          # Virtual environments
    "**/node_modules/**",   # Node packages
    "**/__pycache__/**",    # Python cache
    "**/test_*.py",         # Test files
]
```

## Full Example: Bandit Security Scanner

```python
# adapters/qa/bandit_security.py
"""Bandit security scanner adapter."""

from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path
from uuid import UUID

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from loguru import logger

from crackerjack.adapters.qa.base import QAAdapterBase, QABaseSettings
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus

MODULE_METADATA = AdapterMetadata(
    module_id=UUID("01937d86-5f2a-7b3c-9d1e-a2b3c4d5e6f1"),
    name="Bandit Security Scanner",
    category="qa",
    provider="pycqa",
    version="1.0.0",
    status=AdapterStatus.STABLE,
    capabilities=[AdapterCapability.ASYNC_OPERATIONS],
    required_packages=["bandit>=1.7.0"],
    description="Security issue detection for Python code",
)


class BanditSettings(QABaseSettings):
    """Bandit-specific settings."""

    severity_level: str = "LOW"  # LOW, MEDIUM, HIGH
    confidence_level: str = "LOW"  # LOW, MEDIUM, HIGH
    skip_tests: list[str] = []  # Test IDs to skip


class BanditSecurityAdapter(QAAdapterBase):
    """Bandit security scanning adapter."""

    MODULE_ID = MODULE_METADATA.module_id
    MODULE_STATUS = "stable"
    MODULE_METADATA = MODULE_METADATA

    def __init__(self) -> None:
        super().__init__()
        self.settings = BanditSettings()

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        """Run Bandit security scan."""
        start_time = time.time()

        check_config = config or self.get_default_config()
        files_to_check = files or self._discover_python_files()
        files_to_check = [
            f for f in files_to_check
            if self._should_check_file(f, check_config)
        ]

        if not files_to_check:
            return self._skipped_result(start_time)

        cmd = [
            "bandit",
            "-f", "json",
            "-ll",  # Report severity/confidence
            "-r",   # Recursive
            *[str(f) for f in files_to_check],
        ]

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()
            execution_time = (time.time() - start_time) * 1000

            if result.returncode == 0:
                return QAResult(
                    check_id=self.MODULE_ID,
                    check_name="bandit-security",
                    check_type=QACheckType.SECURITY,
                    status=QAResultStatus.SUCCESS,
                    message="No security issues found",
                    files_checked=files_to_check,
                    execution_time_ms=execution_time,
                )
            else:
                # Parse JSON output for issue count
                import json
                try:
                    output = json.loads(stdout.decode())
                    issue_count = len(output.get("results", []))
                except:
                    issue_count = 1

                return QAResult(
                    check_id=self.MODULE_ID,
                    check_name="bandit-security",
                    check_type=QACheckType.SECURITY,
                    status=QAResultStatus.FAILURE,
                    message=f"Found {issue_count} security issue(s)",
                    details=stdout.decode(),
                    files_checked=files_to_check,
                    issues_found=issue_count,
                    execution_time_ms=execution_time,
                )

        except Exception as e:
            logger.error(f"Bandit scan failed: {e}")
            return QAResult(
                check_id=self.MODULE_ID,
                check_name="bandit-security",
                check_type=QACheckType.SECURITY,
                status=QAResultStatus.ERROR,
                message=f"Scan failed: {str(e)}",
                details=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def validate_config(self, config: QACheckConfig) -> bool:
        """Validate that Bandit is available."""
        try:
            result = await asyncio.create_subprocess_exec(
                "bandit", "--version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await result.communicate()
            return result.returncode == 0
        except Exception:
            return False

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration."""
        return QACheckConfig(
            enabled=True,
            timeout_seconds=120,
            file_patterns=["**/*.py"],
            exclude_patterns=[
                "**/test_*.py",
                "**/tests/**",
                "**/.venv/**",
            ],
            fail_on_error=True,
        )

    def _discover_python_files(self) -> list[Path]:
        """Discover all Python files."""
        return list(Path.cwd().rglob("*.py"))

    def _skipped_result(self, start_time: float) -> QAResult:
        """Generate a skipped result."""
        return QAResult(
            check_id=self.MODULE_ID,
            check_name="bandit-security",
            check_type=QACheckType.SECURITY,
            status=QAResultStatus.SKIPPED,
            message="No files to check",
            execution_time_ms=(time.time() - start_time) * 1000,
        )
```

## Questions?

- **Architecture Review:** See `/docs/qa-framework-architecture-review.md`
- **Implementation Plan:** See `/docs/qa-framework-implementation-plan.md`
- **Example Reference:** See `adapters/ai/claude.py` for ACB patterns
- **Ask:** Architecture Council via Claude Code

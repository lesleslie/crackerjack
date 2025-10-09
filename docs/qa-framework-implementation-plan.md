# QA Framework Implementation Plan

**Date:** 2025-10-09
**Status:** Ready for Implementation
**Approval:** Architecture Council ✅

## Overview

Implementation plan for ACB-based Quality Assurance framework to replace pre-commit hooks in crackerjack.

**Key Principle:** Adapters perform checks, services orchestrate them.

## Phase 1: Foundation (Priority 1 - Required)

### Step 1.1: Refactor Models Directory

**Action:** Consolidate QA models into main `models/` directory

```bash
# Move model files
mv crackerjack/models_qa/results.py crackerjack/models/qa_results.py
mv crackerjack/models_qa/config.py crackerjack/models/qa_config.py

# Remove old directory
rm -rf crackerjack/models_qa/
```

**Update `models/__init__.py`:**

```python
from .config import (
    AIConfig,
    CleaningConfig,
    # ... existing exports ...
)
from .protocols import OptionsProtocol
from .task import HookResult, SessionTracker, TaskStatus
from .qa_results import QAResult, QAResultStatus, QACheckType
from .qa_config import QACheckConfig, QAOrchestratorConfig

__all__ = [
    # ... existing exports ...
    "QAResult",
    "QAResultStatus",
    "QACheckType",
    "QACheckConfig",
    "QAOrchestratorConfig",
]
```

**Update imports in `adapters/qa/base.py`:**

```python
# Change from:
from crackerjack.models_qa.config import QACheckConfig
from crackerjack.models_qa.results import QAResult

# To:
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QAResult
```

### Step 1.2: Create QA Orchestrator Service

**Create `services/qa_orchestrator.py`:**

```python
"""Quality Assurance orchestration service.

This service coordinates execution of multiple QA adapters,
manages parallel/sequential execution, and aggregates results.

This is NOT an adapter - it's a service that USES adapters.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from loguru import logger

from crackerjack.models.qa_config import QAOrchestratorConfig
from crackerjack.models.qa_results import QAResult, QAResultStatus

if TYPE_CHECKING:
    from crackerjack.adapters.qa.base import QAAdapterProtocol


class QAOrchestrator:
    """Orchestrates execution of multiple QA adapters.

    Features:
    - Parallel or sequential execution
    - Result aggregation and reporting
    - Error handling and recovery
    - Performance tracking
    """

    def __init__(self, config: QAOrchestratorConfig) -> None:
        """Initialize the orchestrator.

        Args:
            config: Orchestration configuration
        """
        self.config = config
        self._adapters: dict[UUID, QAAdapterProtocol] = {}
        self._results: list[QAResult] = []

    def register_adapter(self, adapter: QAAdapterProtocol) -> None:
        """Register a QA adapter with the orchestrator.

        Args:
            adapter: QA adapter implementing QAAdapterProtocol
        """
        logger.info(f"Registering QA adapter: {adapter.MODULE_ID}")
        self._adapters[adapter.MODULE_ID] = adapter

    def unregister_adapter(self, adapter_id: UUID) -> None:
        """Unregister a QA adapter.

        Args:
            adapter_id: UUID of the adapter to remove
        """
        if adapter_id in self._adapters:
            logger.info(f"Unregistering QA adapter: {adapter_id}")
            del self._adapters[adapter_id]

    async def run_checks(
        self,
        files: list[Path] | None = None,
        parallel: bool = True,
        fail_fast: bool = False,
    ) -> list[QAResult]:
        """Run all registered QA checks.

        Args:
            files: Optional list of files to check (None = all)
            parallel: Run checks in parallel if True
            fail_fast: Stop on first failure if True

        Returns:
            List of QAResult objects from all checks
        """
        if not self._adapters:
            logger.warning("No QA adapters registered")
            return []

        logger.info(f"Running {len(self._adapters)} QA checks")
        results: list[QAResult] = []

        if parallel:
            # Run all checks concurrently
            tasks = [adapter.check(files=files) for adapter in self._adapters.values()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and convert to error results
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    adapter = list(self._adapters.values())[i]
                    processed_results.append(self._create_error_result(adapter, result))
                else:
                    processed_results.append(result)
            results = processed_results
        else:
            # Run checks sequentially
            for adapter in self._adapters.values():
                try:
                    result = await adapter.check(files=files)
                    results.append(result)

                    if fail_fast and result.status == QAResultStatus.FAILURE:
                        logger.warning(
                            f"Stopping due to failure in {adapter.MODULE_ID}"
                        )
                        break
                except Exception as e:
                    results.append(self._create_error_result(adapter, e))
                    if fail_fast:
                        break

        self._results = results
        self._log_summary(results)
        return results

    def _create_error_result(
        self, adapter: QAAdapterProtocol, error: Exception
    ) -> QAResult:
        """Create an error result for a failed adapter.

        Args:
            adapter: The adapter that failed
            error: The exception that was raised

        Returns:
            QAResult with error status
        """
        from crackerjack.models.qa_results import QACheckType

        return QAResult(
            check_id=adapter.MODULE_ID,
            check_name=str(adapter.MODULE_ID),
            check_type=QACheckType.UTILITY,
            status=QAResultStatus.ERROR,
            message=f"Adapter error: {str(error)}",
            details=str(error),
        )

    def _log_summary(self, results: list[QAResult]) -> None:
        """Log a summary of check results.

        Args:
            results: List of check results
        """
        successes = sum(1 for r in results if r.status == QAResultStatus.SUCCESS)
        failures = sum(1 for r in results if r.status == QAResultStatus.FAILURE)
        errors = sum(1 for r in results if r.status == QAResultStatus.ERROR)
        warnings = sum(1 for r in results if r.status == QAResultStatus.WARNING)

        logger.info(
            f"QA Check Summary: {successes} passed, {failures} failed, "
            f"{warnings} warnings, {errors} errors"
        )

    @property
    def last_results(self) -> list[QAResult]:
        """Get results from the last run."""
        return self._results

    @property
    def has_failures(self) -> bool:
        """Check if any checks failed in last run."""
        return any(
            r.status in (QAResultStatus.FAILURE, QAResultStatus.ERROR)
            for r in self._results
        )
```

**Add to `services/__init__.py`:**

```python
from .qa_orchestrator import QAOrchestrator

__all__ = [
    # ... existing exports ...
    "QAOrchestrator",
]
```

## Phase 2: Enhanced Adapter Pattern (Priority 2 - Recommended)

### Step 2.1: Add Adapter Metadata Support

**Update `adapters/qa/base.py`:**

```python
from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from acb.cleanup import CleanupMixin


class QAAdapterBase(AdapterBase, CleanupMixin):
    """Base class for quality assurance adapters with enhanced ACB features.

    Changes from original:
    - Added CleanupMixin for resource management
    - Added lifecycle methods (init, cleanup)
    - Added metadata property
    """

    MODULE_ID: UUID
    MODULE_STATUS: str = "stable"
    MODULE_METADATA: AdapterMetadata | None = None

    def __init__(self) -> None:
        """Initialize the adapter and register with dependency injection."""
        super().__init__()
        with suppress(Exception):
            depends.set(self)

    async def init(self) -> None:
        """Async initialization hook.

        Override this method to initialize async resources like
        HTTP clients, database connections, etc.
        """
        pass

    async def cleanup(self) -> None:
        """Cleanup async resources.

        Override this method to close connections, release resources, etc.
        Called automatically by CleanupMixin when adapter is destroyed.
        """
        pass

    @property
    def metadata(self) -> AdapterMetadata | None:
        """Get adapter metadata if defined."""
        return self.MODULE_METADATA

    # ... rest of existing methods ...
```

### Step 2.2: Create Example Concrete Adapter

**Create `adapters/qa/ruff_format.py`:**

```python
"""Ruff format checker adapter."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from uuid import UUID

from acb.adapters import AdapterCapability, AdapterMetadata, AdapterStatus
from loguru import logger

from crackerjack.adapters.qa.base import QAAdapterBase, QABaseSettings
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QACheckType, QAResult, QAResultStatus

# Static metadata for adapter discovery
MODULE_METADATA = AdapterMetadata(
    module_id=UUID("01937d86-5f2a-7b3c-9d1e-a2b3c4d5e6f0"),
    name="Ruff Format Checker",
    category="qa",
    provider="astral-sh",
    version="1.0.0",
    acb_min_version="0.19.0",
    status=AdapterStatus.STABLE,
    capabilities=[AdapterCapability.ASYNC_OPERATIONS],
    required_packages=["ruff>=0.8.0"],
    description="Code formatting checks and auto-fixing using Ruff",
)


class RuffFormatSettings(QABaseSettings):
    """Ruff-specific settings."""

    line_length: int = 88
    target_version: str = "py313"
    check_mode: bool = False  # If False, auto-fix formatting issues


class RuffFormatAdapter(QAAdapterBase):
    """Ruff code formatting adapter.

    Performs code formatting checks and optionally auto-fixes issues.
    """

    MODULE_ID = MODULE_METADATA.module_id
    MODULE_STATUS = "stable"
    MODULE_METADATA = MODULE_METADATA

    def __init__(self) -> None:
        super().__init__()
        self.settings = RuffFormatSettings()

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        """Run Ruff format check.

        Args:
            files: List of files to check (None = all Python files)
            config: Optional configuration override

        Returns:
            QAResult with formatting check results
        """
        import time

        start_time = time.time()

        # Use provided config or get defaults
        check_config = config or self.get_default_config()

        # Determine files to check
        files_to_check = files or self._discover_python_files()
        files_to_check = [
            f for f in files_to_check if self._should_check_file(f, check_config)
        ]

        if not files_to_check:
            return QAResult(
                check_id=self.MODULE_ID,
                check_name="ruff-format",
                check_type=QACheckType.FORMAT,
                status=QAResultStatus.SKIPPED,
                message="No files to check",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Build ruff command
        cmd = ["ruff", "format"]
        if self.settings.check_mode:
            cmd.append("--check")
        cmd.extend(str(f) for f in files_to_check)

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            execution_time = (time.time() - start_time) * 1000
            output = stdout.decode() + stderr.decode()

            if result.returncode == 0:
                status = QAResultStatus.SUCCESS
                message = "All files formatted correctly"
                issues_found = 0
            else:
                status = QAResultStatus.FAILURE
                message = "Formatting issues found"
                issues_found = len(files_to_check)

            return QAResult(
                check_id=self.MODULE_ID,
                check_name="ruff-format",
                check_type=QACheckType.FORMAT,
                status=status,
                message=message,
                details=output,
                files_checked=files_to_check,
                issues_found=issues_found,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            logger.error(f"Ruff format check failed: {e}")
            return QAResult(
                check_id=self.MODULE_ID,
                check_name="ruff-format",
                check_type=QACheckType.FORMAT,
                status=QAResultStatus.ERROR,
                message=f"Check failed: {str(e)}",
                details=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    async def validate_config(self, config: QACheckConfig) -> bool:
        """Validate configuration."""
        # Basic validation - check that ruff is available
        try:
            result = await asyncio.create_subprocess_exec(
                "ruff",
                "--version",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            await result.communicate()
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Ruff not available: {e}")
            return False

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration."""
        return QACheckConfig(
            enabled=True,
            timeout_seconds=60,
            file_patterns=["**/*.py"],
            exclude_patterns=["**/migrations/**", "**/.venv/**"],
            fail_on_error=True,
        )

    def _discover_python_files(self) -> list[Path]:
        """Discover all Python files in current directory."""
        return list(Path.cwd().rglob("*.py"))
```

**Update `adapters/qa/__init__.py`:**

```python
"""Quality Assurance adapters."""

from .base import QAAdapterBase, QAAdapterProtocol, QABaseSettings
from .ruff_format import RuffFormatAdapter, RuffFormatSettings

__all__ = [
    "QAAdapterBase",
    "QAAdapterProtocol",
    "QABaseSettings",
    "RuffFormatAdapter",
    "RuffFormatSettings",
]
```

## Phase 3: Integration (Priority 2 - Recommended)

### Step 3.1: Wire Up in Main Workflow

**Example integration in `__main__.py` or coordinator:**

```python
from crackerjack.adapters.qa.ruff_format import RuffFormatAdapter
from crackerjack.services.qa_orchestrator import QAOrchestrator
from crackerjack.models.qa_config import QAOrchestratorConfig


async def run_qa_checks(files: list[Path] | None = None):
    """Run all QA checks."""
    # Create orchestrator
    config = QAOrchestratorConfig(
        parallel=True,
        fail_fast=False,
        timeout_seconds=300,
    )
    orchestrator = QAOrchestrator(config)

    # Register adapters
    orchestrator.register_adapter(RuffFormatAdapter())
    # Add more adapters as implemented

    # Run checks
    results = await orchestrator.run_checks(files=files)

    # Process results
    for result in results:
        print(result.to_summary())

    return orchestrator.has_failures
```

## Phase 4: Testing (Priority 1 - Required)

### Step 4.1: Unit Tests for Base Adapter

**Create `tests/unit/adapters/qa/test_base.py`:**

```python
"""Tests for QA adapter base classes."""

import pytest
from pathlib import Path
from uuid import UUID

from crackerjack.adapters.qa.base import (
    QAAdapterBase,
    QABaseSettings,
    QAAdapterProtocol,
)
from crackerjack.models.qa_config import QACheckConfig
from crackerjack.models.qa_results import QAResult, QAResultStatus, QACheckType


class TestQAAdapterSettings:
    """Test suite for QABaseSettings."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = QABaseSettings()

        assert settings.enabled is True
        assert settings.timeout_seconds == 60
        assert settings.file_patterns == ["**/*.py"]
        assert settings.exclude_patterns == []
        assert settings.fail_on_error is True
        assert settings.verbose is False

    def test_custom_settings(self):
        """Test custom settings override defaults."""
        settings = QABaseSettings(
            enabled=False,
            timeout_seconds=120,
            file_patterns=["**/*.ts"],
        )

        assert settings.enabled is False
        assert settings.timeout_seconds == 120
        assert settings.file_patterns == ["**/*.ts"]


class ConcreteQAAdapter(QAAdapterBase):
    """Concrete adapter for testing."""

    MODULE_ID = UUID("01937d86-0000-0000-0000-000000000000")
    MODULE_STATUS = "stable"

    async def check(self, files=None, config=None):
        return QAResult(
            check_id=self.MODULE_ID,
            check_name="test-adapter",
            check_type=QACheckType.LINT,
            status=QAResultStatus.SUCCESS,
            message="Test passed",
        )

    async def validate_config(self, config):
        return True

    def get_default_config(self):
        return QACheckConfig(
            enabled=True,
            timeout_seconds=60,
            file_patterns=["**/*.py"],
        )


class TestQAAdapterBase:
    """Test suite for QAAdapterBase."""

    def test_adapter_initialization(self):
        """Test adapter initializes correctly."""
        adapter = ConcreteQAAdapter()

        assert adapter.MODULE_ID == UUID("01937d86-0000-0000-0000-000000000000")
        assert adapter.MODULE_STATUS == "stable"

    @pytest.mark.asyncio
    async def test_check_method(self):
        """Test check method returns valid result."""
        adapter = ConcreteQAAdapter()
        result = await adapter.check()

        assert isinstance(result, QAResult)
        assert result.status == QAResultStatus.SUCCESS
        assert result.check_id == adapter.MODULE_ID

    def test_should_check_file(self):
        """Test file pattern matching."""
        adapter = ConcreteQAAdapter()
        config = QACheckConfig(
            file_patterns=["**/*.py"],
            exclude_patterns=["**/test_*.py"],
        )

        # Should check regular Python files
        assert adapter._should_check_file(Path("src/main.py"), config)

        # Should not check test files
        assert not adapter._should_check_file(Path("tests/test_main.py"), config)

        # Should not check non-Python files
        assert not adapter._should_check_file(Path("README.md"), config)

    def test_implements_protocol(self):
        """Test adapter implements QAAdapterProtocol."""
        adapter = ConcreteQAAdapter()
        assert isinstance(adapter, QAAdapterProtocol)
```

### Step 4.2: Integration Tests for Orchestrator

**Create `tests/integration/services/test_qa_orchestrator.py`:**

```python
"""Integration tests for QA orchestrator."""

import pytest
from pathlib import Path

from crackerjack.services.qa_orchestrator import QAOrchestrator
from crackerjack.adapters.qa.ruff_format import RuffFormatAdapter
from crackerjack.models.qa_config import QAOrchestratorConfig
from crackerjack.models.qa_results import QAResultStatus


class TestQAOrchestrator:
    """Test suite for QAOrchestrator service."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance."""
        config = QAOrchestratorConfig(
            parallel=True,
            fail_fast=False,
            timeout_seconds=300,
        )
        return QAOrchestrator(config)

    def test_register_adapter(self, orchestrator):
        """Test adapter registration."""
        adapter = RuffFormatAdapter()
        orchestrator.register_adapter(adapter)

        assert adapter.MODULE_ID in orchestrator._adapters
        assert len(orchestrator._adapters) == 1

    def test_unregister_adapter(self, orchestrator):
        """Test adapter unregistration."""
        adapter = RuffFormatAdapter()
        orchestrator.register_adapter(adapter)
        orchestrator.unregister_adapter(adapter.MODULE_ID)

        assert adapter.MODULE_ID not in orchestrator._adapters
        assert len(orchestrator._adapters) == 0

    @pytest.mark.asyncio
    async def test_run_checks_parallel(self, orchestrator):
        """Test running checks in parallel."""
        orchestrator.register_adapter(RuffFormatAdapter())

        results = await orchestrator.run_checks(parallel=True)

        assert len(results) == 1
        assert all(hasattr(r, "status") for r in results)

    @pytest.mark.asyncio
    async def test_run_checks_sequential(self, orchestrator):
        """Test running checks sequentially."""
        orchestrator.register_adapter(RuffFormatAdapter())

        results = await orchestrator.run_checks(parallel=False)

        assert len(results) == 1
        assert all(hasattr(r, "status") for r in results)

    @pytest.mark.asyncio
    async def test_no_adapters_warning(self, orchestrator, caplog):
        """Test warning when no adapters registered."""
        results = await orchestrator.run_checks()

        assert len(results) == 0
        assert "No QA adapters registered" in caplog.text
```

## Summary Checklist

### Phase 1: Foundation ✅

- [ ] Move `models_qa/` → `models/qa_*.py`
- [ ] Update imports in `adapters/qa/base.py`
- [ ] Update `models/__init__.py` exports
- [ ] Create `services/qa_orchestrator.py`
- [ ] Update `services/__init__.py`

### Phase 2: Enhancement 📝

- [ ] Add `CleanupMixin` to `QAAdapterBase`
- [ ] Add lifecycle methods (`init()`, `cleanup()`)
- [ ] Create example `RuffFormatAdapter`
- [ ] Update `adapters/qa/__init__.py`

### Phase 3: Integration 📝

- [ ] Wire up in main workflow
- [ ] Add CLI flags for QA checks
- [ ] Integrate with existing coordinators

### Phase 4: Testing ✅

- [ ] Unit tests for `QAAdapterBase`
- [ ] Unit tests for `QABaseSettings`
- [ ] Integration tests for `QAOrchestrator`
- [ ] Example adapter tests

## Next Steps

1. **Execute Phase 1** (required architectural changes)
1. **Run tests** to ensure no regressions
1. **Execute Phase 2** (enhanced patterns)
1. **Implement additional adapters** (Pyright, Skylos, etc.)
1. **Integrate with existing workflow**

## References

- Architecture Review: `/docs/qa-framework-architecture-review.md`
- ACB Documentation: [acb.anthropic.com](https://acb.anthropic.com)
- FastBlocks Reference: `adapters/ai/claude.py`

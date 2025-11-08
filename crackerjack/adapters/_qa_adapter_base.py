"""Base adapter for ACB Quality Assurance framework.

This module provides the foundational classes and protocols for implementing
QA checks as ACB adapters following ACB 0.19.0+ patterns.

Key ACB Patterns:
- MODULE_ID and MODULE_STATUS are module-level constants in concrete adapters
- Dependency injection via module-level depends.set() after class definition
- Runtime-checkable protocols for type safety
- Concrete base class for shared implementation
- Settings extend acb.config.Settings with validators
- Async init() method for lazy initialization

CRITICAL: Imports protocols from models.protocols, not local definitions.
"""

from __future__ import annotations

import asyncio
import typing as t
from contextlib import asynccontextmanager
from pathlib import Path

from acb.config import Settings
from pydantic import Field, field_validator

# Import protocol from models.protocols per crackerjack pattern
from crackerjack.models.protocols import QAAdapterProtocol

if t.TYPE_CHECKING:
    from uuid import UUID

    from crackerjack.models.qa_config import QACheckConfig
    from crackerjack.models.qa_results import QAResult


class QABaseSettings(Settings):
    """Base settings for quality assurance adapters.

    All QA adapter settings should inherit from this class to ensure
    consistent configuration patterns across all checks.
    """

    enabled: bool = True
    timeout_seconds: int = Field(60, ge=1, le=3600)
    file_patterns: list[str] = Field(default_factory=lambda: ["**/*.py"])
    exclude_patterns: list[str] = Field(default_factory=list)
    fail_on_error: bool = True
    verbose: bool = False
    cache_enabled: bool = True
    cache_ttl: int = 3600
    max_workers: int = Field(4, ge=1, le=16)

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout is within reasonable bounds."""
        if v < 1 or v > 3600:
            raise ValueError("Timeout must be between 1 and 3600 seconds")
        return v

    @field_validator("max_workers")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        """Validate worker count is reasonable."""
        if v < 1 or v > 16:
            raise ValueError("Max workers must be between 1 and 16")
        return v


# QAAdapterProtocol is imported from models.protocols per crackerjack pattern
# See crackerjack/models/protocols.py for protocol definition


from acb.adapters import AdapterMetadata


class QAAdapterBase:
    """Concrete base class for quality assurance adapters.

    Provides shared implementation for all QA adapters following ACB patterns.
    Unlike traditional abstract base classes, this is concrete and provides
    default implementations where sensible.

    IMPORTANT ACB Patterns:
    - MODULE_ID must be defined at module level in concrete adapters (not here)
    - depends.set() registration happens at module level after class definition
    - Use async init() for lazy initialization, not __init__
    - Subclasses override specific methods as needed

    Example:
        ```python
        # In concrete adapter file (e.g., ruff_lint.py)
        import uuid
        from contextlib import suppress
        from acb.depends import depends
        from crackerjack.adapters.qa.base import QAAdapterBase, QABaseSettings

        # MODULE_ID at module level (REQUIRED by ACB)
        MODULE_ID = uuid.UUID("01937d86-5f2a-7b3c-9d1e-a2b3c4d5e6f7")
        MODULE_STATUS = "stable"


        class RuffLintSettings(QABaseSettings):
            select_rules: list[str] = []
            ignore_rules: list[str] = []
            fix_enabled: bool = False


        class RuffLintAdapter(QAAdapterBase):
            settings: RuffLintSettings | None = None

            async def init(self) -> None:
                if not self.settings:
                    self.settings = RuffLintSettings()
                await super().init()

            @property
            def adapter_name(self) -> str:
                return "Ruff Linter"

            @property
            def module_id(self) -> uuid.UUID:
                return MODULE_ID

            async def check(self, files=None, config=None):
                # Implementation here
                return QAResult(...)


        # Register at module level (REQUIRED by ACB)
        with suppress(Exception):
            depends.set(RuffLintAdapter)
        ```
    """

    settings: QABaseSettings | None = None
    metadata: AdapterMetadata | None = None

    def __init__(self) -> None:
        """Initialize adapter instance.

        Note: ACB pattern is to do minimal work here. Use async init()
        for expensive setup operations.
        """
        self._initialized = False
        self._semaphore: asyncio.Semaphore | None = None

    async def init(self) -> None:
        """ACB standard initialization method.

        Called lazily before first check. Override in subclasses to:
        - Load settings
        - Setup async resources
        - Initialize clients/connections
        - Validate configuration
        """
        if not self.settings:
            self.settings = QABaseSettings()

        # Create semaphore for concurrency control
        max_workers = self.settings.max_workers
        self._semaphore = asyncio.Semaphore(max_workers)

        self._initialized = True

    @property
    def adapter_name(self) -> str:
        """Human-readable adapter name.

        Override in subclasses for better identification.
        """
        return self.__class__.__name__

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID.

        Must be overridden in concrete adapters to return the
        module-level MODULE_ID constant.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement module_id property "
            "that returns the module-level MODULE_ID constant"
        )

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        """Execute the quality assurance check.

        Must be overridden in concrete adapters.

        Args:
            files: List of files to check (None = check all files matching patterns)
            config: Optional configuration override for this check

        Returns:
            QAResult containing the check execution results
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement check() method"
        )

    async def validate_config(self, config: QACheckConfig) -> bool:
        """Validate configuration.

        Default implementation provides basic validation.
        Override for adapter-specific validation.

        Args:
            config: Configuration to validate

        Returns:
            True if configuration is valid, False otherwise
        """
        return config is not None

    def get_default_config(self) -> QACheckConfig:
        """Get default configuration.

        Must be overridden in concrete adapters.

        Returns:
            QACheckConfig with sensible defaults for this check
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_default_config() method"
        )

    async def health_check(self) -> dict[str, t.Any]:
        """ACB standard health check method.

        Provides basic health status. Override for more detailed checks.

        Returns:
            Dictionary with health status and metadata
        """
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "adapter": self.adapter_name,
            "module_id": str(self.module_id) if self._initialized else "unknown",
            "settings_loaded": self.settings is not None,
            "metadata": self.metadata.dict() if self.metadata else None,
        }

    def _should_check_file(self, file_path: Path, config: QACheckConfig) -> bool:
        """Determine if a file should be checked based on patterns.

        Args:
            file_path: Path to the file
            config: Configuration containing file patterns

        Returns:
            True if file should be checked, False otherwise
        """
        # Check if file matches any include patterns
        matches_include = any(
            file_path.match(pattern) for pattern in config.file_patterns
        )

        if not matches_include:
            return False

        # Check if file matches any exclude patterns
        matches_exclude = any(
            file_path.match(pattern) for pattern in config.exclude_patterns
        )

        return not matches_exclude

    @asynccontextmanager
    async def _lifecycle(self) -> t.AsyncIterator[QAAdapterBase]:
        """ACB pattern for resource lifecycle management.

        Use this context manager for proper setup/teardown:

        ```python
        async with adapter._lifecycle():
            result = await adapter.check(files)
        ```
        """
        try:
            if not self._initialized:
                await self.init()
            yield self
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        """Cleanup async resources.

        Override in subclasses to clean up:
        - Close connections
        - Release resources
        - Flush caches
        """
        # Base implementation - subclasses can extend
        self._semaphore = None


# Export the main classes and protocol
__all__ = [
    "QAAdapterBase",
    "QAAdapterProtocol",
    "QABaseSettings",
]

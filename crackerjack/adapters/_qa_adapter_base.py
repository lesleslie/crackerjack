from __future__ import annotations

import asyncio
import typing as t
from contextlib import asynccontextmanager
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

from crackerjack.models.adapter_metadata import AdapterMetadata
from crackerjack.models.protocols import QAAdapterProtocol

if t.TYPE_CHECKING:
    from uuid import UUID

    from crackerjack.models.qa_config import QACheckConfig
    from crackerjack.models.qa_results import QAResult


class QABaseSettings(BaseModel):
    enabled: bool = True
    timeout_seconds: int = Field(300, ge=1, le=7200)
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
        if v < 1 or v > 3600:
            raise ValueError("Timeout must be between 1 and 3600 seconds")
        return v

    @field_validator("max_workers")
    @classmethod
    def validate_workers(cls, v: int) -> int:
        if v < 1 or v > 16:
            raise ValueError("Max workers must be between 1 and 16")
        return v


class QAAdapterBase:
    settings: QABaseSettings | None = None
    metadata: AdapterMetadata | None = None

    def __init__(self) -> None:
        self._initialized = False
        self._semaphore: asyncio.Semaphore | None = None

    async def init(self) -> None:
        if not self.settings:
            self.settings = QABaseSettings(
                timeout_seconds=300,
                max_workers=4,
            )

        max_workers = self.settings.max_workers
        self._semaphore = asyncio.Semaphore(max_workers)

        self._initialized = True

    @property
    def adapter_name(self) -> str:
        return self.__class__.__name__

    @property
    def module_id(self) -> UUID:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement module_id property "
            "that returns the module-level MODULE_ID constant"
        )

    async def check(
        self,
        files: list[Path] | None = None,
        config: QACheckConfig | None = None,
    ) -> QAResult:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement check() method"
        )

    async def validate_config(self, config: QACheckConfig) -> bool:
        return config is not None

    def get_default_config(self) -> QACheckConfig:
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement get_default_config() method"
        )

    async def health_check(self) -> dict[str, t.Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "adapter": self.adapter_name,
            "module_id": str(self.module_id) if self._initialized else "unknown",
            "settings_loaded": self.settings is not None,
            "metadata": self.metadata.dict() if self.metadata else None,
        }

    def _should_check_file(self, file_path: Path, config: QACheckConfig) -> bool:
        matches_include = any(
            file_path.match(pattern) for pattern in config.file_patterns
        )

        if not matches_include:
            return False

        matches_exclude = any(
            file_path.match(pattern) for pattern in config.exclude_patterns
        )

        return not matches_exclude

    @asynccontextmanager
    async def _lifecycle(self) -> t.AsyncIterator[QAAdapterBase]:
        try:
            if not self._initialized:
                await self.init()
            yield self
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        self._semaphore = None


__all__ = [
    "QAAdapterBase",
    "QAAdapterProtocol",
    "QABaseSettings",
]

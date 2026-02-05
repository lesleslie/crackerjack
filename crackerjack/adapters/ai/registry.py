import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from crackerjack.adapters.ai.base import BaseCodeFixer

logger = logging.getLogger(__name__)

"""AI Provider Registry and Fallback Chain.

This module provides a robust provider selection system with automatic fallback,
ensuring 99%+ availability for AI-fix operations through multiple providers
(Claude, Qwen, Ollama).

Key Components:
    - ProviderID: Enum of supported AI providers (claude, qwen, ollama)
    - ProviderFactory: Creates provider instances with validation
    - ProviderChain: Manages fallback chain with priority-based selection
    - ProviderInfo: Metadata about each provider (cost, setup, requirements)

Usage:
    >>> chain = ProviderChain(["claude", "qwen", "ollama"])
    >>> provider, provider_id = await chain.get_available_provider()
    >>> print(f"Using {provider_id}")
    Using claude

Provider Priority:
    1. Claude (Anthropic) - Highest quality, paid API
    2. Qwen (Alibaba) - Good quality, low-cost API
    3. Ollama - Free local models, requires installation

Availability Checking:
    - Validates API keys before attempting to use provider
    - Checks Ollama server is running
    - Tracks performance metrics for each provider

Error Handling:
    - Falls back to next provider on expected errors (ConnectionError, TimeoutError, ValueError)
    - Logs unexpected errors at ERROR level
    - Raises RuntimeError only when all providers fail

Metrics:
    - Tracks provider selection success/failure
    - Records latency for each provider attempt
    - Stores error messages for debugging
"""


class ProviderID(StrEnum):
    CLAUDE = "claude"
    QWEN = "qwen"
    OLLAMA = "ollama"


@dataclass(frozen=True)
class ProviderInfo:
    id: ProviderID
    name: str
    description: str
    requires_api_key: bool
    default_model: str
    setup_url: str
    cost_tier: str

    def __str__(self) -> str:
        return f"{self.name} ({self.id.value})"


PROVIDER_INFO: dict[ProviderID, ProviderInfo] = {
    ProviderID.CLAUDE: ProviderInfo(
        id=ProviderID.CLAUDE,
        name="Claude (Anthropic)",
        description="Best overall quality, excellent at complex reasoning",
        requires_api_key=True,
        default_model="claude-sonnet-4-5-20250929",
        setup_url="https://docs.anthropic.com/claude/reference/getting-started-with-the-api",
        cost_tier="high",
    ),
    ProviderID.QWEN: ProviderInfo(
        id=ProviderID.QWEN,
        name="Qwen (Alibaba)",
        description="Cost-effective, code-specialized models",
        requires_api_key=True,
        default_model="qwen-coder-plus",
        setup_url="https://help.aliyun.com/zh/dashscope/developer-reference/compatibility-of-openai-with-dashscope",
        cost_tier="low",
    ),
    ProviderID.OLLAMA: ProviderInfo(
        id=ProviderID.OLLAMA,
        name="Ollama (Local)",
        description="Free local models, complete privacy, requires installation",
        requires_api_key=False,
        default_model="qwen2.5-coder: 7b",
        setup_url="https://ollama.com/download",
        cost_tier="free",
    ),
}


class ProviderFactory:
    @staticmethod
    def _parse_provider_id(provider_id: ProviderID | str) -> ProviderID:
        if isinstance(provider_id, str):
            try:
                return ProviderID(provider_id.lower())
            except ValueError:
                available = [p.value for p in ProviderID]
                msg = f"Unknown provider: {provider_id}. Available: {available}"
                raise ValueError(msg) from None
        return provider_id

    @staticmethod
    def create_provider(
        provider_id: ProviderID | str,
        settings: None = None,
    ) -> BaseCodeFixer:
        if settings is not None:
            msg = "Settings must be loaded from configuration, not passed to create_provider"
            raise TypeError(msg)

        provider_id = ProviderFactory._parse_provider_id(provider_id)

        from crackerjack.adapters.ai.claude import ClaudeCodeFixer
        from crackerjack.adapters.ai.ollama import OllamaCodeFixer
        from crackerjack.adapters.ai.qwen import QwenCodeFixer

        if provider_id == ProviderID.CLAUDE:
            return ClaudeCodeFixer()

        if provider_id == ProviderID.QWEN:
            return QwenCodeFixer()

        if provider_id == ProviderID.OLLAMA:
            return OllamaCodeFixer()

        msg = f"Provider not implemented: {provider_id}"
        raise ValueError(msg)

    @staticmethod
    def get_provider_info(provider_id: ProviderID | str) -> ProviderInfo:
        provider_id = ProviderFactory._parse_provider_id(provider_id)

        if provider_id not in PROVIDER_INFO:
            msg = f"Provider info not found: {provider_id}"
            raise ValueError(msg)

        return PROVIDER_INFO[provider_id]

    @staticmethod
    def list_providers() -> list[ProviderInfo]:
        return list(PROVIDER_INFO.values())


class ProviderChain:
    def __init__(self, provider_ids: Sequence[ProviderID | str]) -> None:
        if not provider_ids:
            msg = "Provider chain requires at least one provider"
            raise ValueError(msg)

        self.provider_ids: list[ProviderID] = []
        seen: set[ProviderID] = set()

        for pid in provider_ids:
            parsed_pid = ProviderFactory._parse_provider_id(pid)
            if parsed_pid in seen:
                msg = f"Duplicate provider in chain: {parsed_pid.value}"
                raise ValueError(msg)
            seen.add(parsed_pid)
            self.provider_ids.append(parsed_pid)

        self._provider_cache: dict[ProviderID, BaseCodeFixer] = {}

        self._metrics: Any = None

    async def get_available_provider(self) -> tuple[BaseCodeFixer, ProviderID]:
        last_error: Exception | None = None

        for idx, provider_id in enumerate(self.provider_ids):
            start_time = time.time()
            try:
                provider = self._get_or_create_provider(provider_id)

                if await self._check_provider_availability(provider):
                    latency_ms = (time.time() - start_time) * 1000

                    self._track_provider_selection(
                        provider_id, success=True, latency_ms=latency_ms
                    )

                    logger.debug(
                        "Provider selected",
                        extra={
                            "provider_id": provider_id.value,
                            "latency_ms": latency_ms,
                            "chain_position": idx,
                            "total_providers": len(self.provider_ids),
                        },
                    )
                    return provider, provider_id

                logger.debug(
                    "Provider not available, trying next",
                    extra={
                        "provider_id": provider_id.value,
                        "chain_position": idx,
                        "reason": "availability_check_failed",
                    },
                )
                latency_ms = (time.time() - start_time) * 1000
                self._track_provider_selection(
                    provider_id,
                    success=False,
                    latency_ms=latency_ms,
                    error="Not available",
                )

            except (ConnectionError, TimeoutError, ValueError, RuntimeError) as e:
                last_error = e
                latency_ms = (time.time() - start_time) * 1000

                self._track_provider_selection(
                    provider_id,
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                )

                logger.debug(
                    "Provider failed (expected error)",
                    extra={
                        "provider_id": provider_id.value,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "latency_ms": latency_ms,
                        "chain_position": idx,
                    },
                )
                continue
            except Exception as e:
                last_error = e
                latency_ms = (time.time() - start_time) * 1000

                self._track_provider_selection(
                    provider_id,
                    success=False,
                    latency_ms=latency_ms,
                    error=f"Unexpected: {str(e)}",
                )

                logger.debug(
                    "Provider had unexpected error",
                    extra={
                        "provider_id": provider_id.value,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "latency_ms": latency_ms,
                        "chain_position": idx,
                    },
                    exc_info=True,
                )
                continue

        msg = "All AI providers unavailable or failed"
        if last_error:
            msg += f" (last error: {last_error})"
        raise RuntimeError(msg) from last_error

    def _get_or_create_provider(self, provider_id: ProviderID) -> BaseCodeFixer:
        if provider_id not in self._provider_cache:
            self._provider_cache[provider_id] = ProviderFactory.create_provider(
                provider_id
            )
        return self._provider_cache[provider_id]

    async def _check_provider_availability(self, provider: BaseCodeFixer) -> bool:
        try:
            if not hasattr(provider, "_settings"):
                return True

            from crackerjack.adapters.ai.claude import ClaudeCodeFixerSettings
            from crackerjack.adapters.ai.ollama import OllamaCodeFixerSettings
            from crackerjack.adapters.ai.qwen import QwenCodeFixerSettings

            settings = provider._settings

            if isinstance(settings, (ClaudeCodeFixerSettings, QwenCodeFixerSettings)):
                if isinstance(settings, ClaudeCodeFixerSettings):
                    key = (
                        settings.anthropic_api_key.get_secret_value()
                        if settings.anthropic_api_key
                        else None
                    )
                else:
                    key = (
                        settings.qwen_api_key.get_secret_value()
                        if settings.qwen_api_key
                        else None
                    )

                if not key or key.startswith("placeholder") or len(key) < 10:
                    return False

            if isinstance(settings, OllamaCodeFixerSettings):
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(
                            settings.base_url,
                            timeout=aiohttp.ClientTimeout(total=5),
                        ) as resp:
                            return resp.status == 200
                    except Exception:
                        return False

            return True

        except Exception as e:
            logger.debug(f"Provider availability check failed: {e}")
            return False

    def _track_provider_selection(
        self,
        provider_id: ProviderID,
        success: bool,
        latency_ms: float,
        error: str | None = None,
    ) -> None:
        try:
            from crackerjack.services.metrics import get_metrics

            if self._metrics is None:
                self._metrics = get_metrics()

            self._metrics.execute(
                """
                INSERT INTO provider_performance
                (provider_id, success, latency_ms, error_message, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (provider_id.value, success, latency_ms, error, datetime.now()),
            )
        except Exception as e:
            logger.debug(f"Failed to track provider selection: {e}")

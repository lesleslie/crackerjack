import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from crackerjack.adapters.ai.base import BaseCodeFixer

logger = logging.getLogger(__name__)


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
        default_model="qwen2.5-coder:7b",
        setup_url="https://ollama.com/download",
        cost_tier="free",
    ),
}


class ProviderFactory:
    @staticmethod
    def _parse_provider_id(provider_id: ProviderID | str) -> ProviderID:
        """Parse provider ID from string or enum.

        Args:
            provider_id: Provider ID as string or enum

        Returns:
            ProviderID enum value

        Raises:
            ValueError: If provider_id is unknown
        """
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
    """Manages fallback chain of AI providers with availability checking.

    This class implements a priority-based provider selection system with automatic
    fallback, ensuring 99%+ availability for AI-fix operations.

    Example:
        chain = ProviderChain([ProviderID.CLAUDE, ProviderID.QWEN, ProviderID.OLLAMA])
        provider, provider_id = await chain.get_available_provider()
        # Uses Claude if available, falls back to Qwen, then Ollama
    """

    def __init__(self, provider_ids: list[ProviderID | str]) -> None:
        """Initialize provider chain with prioritized list.

        Args:
            provider_ids: Ordered list of provider IDs (highest priority first)

        Raises:
            ValueError: If provider_ids is empty, contains duplicates, or unknown providers
        """
        if not provider_ids:
            msg = "Provider chain requires at least one provider"
            raise ValueError(msg)

        # Convert strings to ProviderID enums and check for duplicates
        self.provider_ids: list[ProviderID] = []
        seen: set[ProviderID] = set()

        for pid in provider_ids:
            parsed_pid = ProviderFactory._parse_provider_id(pid)
            if parsed_pid in seen:
                msg = f"Duplicate provider in chain: {parsed_pid.value}"
                raise ValueError(msg)
            seen.add(parsed_pid)
            self.provider_ids.append(parsed_pid)

        # Cache provider instances to avoid repeated creation
        self._provider_cache: dict[ProviderID, BaseCodeFixer] = {}

        # Metrics database (will be initialized on first use)
        self._metrics: Any = None

    async def get_available_provider(self) -> tuple[BaseCodeFixer, ProviderID]:
        """Return first available provider in priority order.

        Tries each provider in order, checking availability before returning.
        Tracks performance metrics for each attempt.

        Returns:
            (provider, provider_id): The first available provider and its ID

        Raises:
            RuntimeError: If all providers are unavailable or failed
        """
        last_error: Exception | None = None

        for provider_id in self.provider_ids:
            start_time = time.time()
            try:
                provider = self._get_or_create_provider(provider_id)

                # Verify provider is actually available
                if await self._check_provider_availability(provider):
                    latency_ms = (time.time() - start_time) * 1000

                    # Track successful provider selection
                    self._track_provider_selection(
                        provider_id, success=True, latency_ms=latency_ms
                    )

                    logger.info(f"Using AI provider: {provider_id.value}")
                    return provider, provider_id

                logger.warning(f"Provider {provider_id.value} not available, trying next")
                latency_ms = (time.time() - start_time) * 1000
                self._track_provider_selection(
                    provider_id, success=False, latency_ms=latency_ms, error="Not available"
                )

            except Exception as e:
                last_error = e
                latency_ms = (time.time() - start_time) * 1000

                # Track failed provider
                self._track_provider_selection(
                    provider_id,
                    success=False,
                    latency_ms=latency_ms,
                    error=str(e),
                )

                logger.warning(f"Provider {provider_id.value} failed: {e}")
                continue

        # All providers failed
        msg = "All AI providers unavailable or failed"
        if last_error:
            msg += f" (last error: {last_error})"
        raise RuntimeError(msg) from last_error

    def _get_or_create_provider(self, provider_id: ProviderID) -> BaseCodeFixer:
        """Get cached provider or create new instance.

        Args:
            provider_id: The provider identifier

        Returns:
            Cached or newly created provider instance
        """
        if provider_id not in self._provider_cache:
            self._provider_cache[provider_id] = ProviderFactory.create_provider(provider_id)
        return self._provider_cache[provider_id]

    async def _check_provider_availability(self, provider: BaseCodeFixer) -> bool:
        """Check if provider is actually available (API key, server running, etc.).

        Args:
            provider: The provider instance to check

        Returns:
            True if provider is available, False otherwise
        """
        try:
            # Check if provider has settings attribute
            if not hasattr(provider, "_settings"):
                # No settings to check, assume available
                return True

            from crackerjack.adapters.ai.claude import ClaudeCodeFixerSettings
            from crackerjack.adapters.ai.ollama import OllamaCodeFixerSettings
            from crackerjack.adapters.ai.qwen import QwenCodeFixerSettings

            settings = provider._settings

            # Check API key for cloud providers
            if isinstance(settings, (ClaudeCodeFixerSettings, QwenCodeFixerSettings)):
                # Get API key based on settings type
                if isinstance(settings, ClaudeCodeFixerSettings):
                    key = (
                        settings.anthropic_api_key.get_secret_value()
                        if settings.anthropic_api_key
                        else None
                    )
                else:  # QwenCodeFixerSettings
                    key = (
                        settings.dashscope_api_key.get_secret_value()
                        if settings.dashscope_api_key
                        else None
                    )

                # Check if key is present and not a placeholder
                if not key or key.startswith("placeholder") or len(key) < 10:
                    return False

            # Check Ollama server is running
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
        """Track provider selection for metrics analysis.

        Args:
            provider_id: The provider being tracked
            success: Whether the provider was available
            latency_ms: Time taken to check availability
            error: Error message if failed
        """
        try:
            # Lazy import to avoid circular dependency
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
            # Don't fail the provider chain if metrics tracking fails
            logger.debug(f"Failed to track provider selection: {e}")

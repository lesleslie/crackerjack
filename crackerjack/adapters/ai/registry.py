"""Provider registry for AI code fixers.

Central registry of all available providers with metadata and factory functions.
"""

import logging
import typing as t
from dataclasses import dataclass
from enum import Enum

from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings

logger = logging.getLogger(__name__)


class ProviderID(str, Enum):
    """Identifier for each AI provider."""
    CLAUDE = "claude"
    QWEN = "qwen"
    OLLAMA = "ollama"


@dataclass(frozen=True)
class ProviderInfo:
    """Metadata about an AI provider."""
    id: ProviderID
    name: str
    description: str
    requires_api_key: bool
    default_model: str
    setup_url: str
    cost_tier: str  # "free", "low", "medium", "high"
    
    def __str__(self) -> str:
        return f"{self.name} ({self.id.value})"


# Provider metadata registry
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
    """Factory for creating AI provider instances."""
    
    @staticmethod
    def create_provider(
        provider_id: ProviderID | str,
        settings: BaseCodeFixerSettings | None = None,
    ) -> BaseCodeFixer:
        """Create a provider instance.
        
        Args:
            provider_id: Provider identifier (enum or string)
            settings: Provider-specific settings (optional)
            
        Returns:
            Instantiated provider
            
        Raises:
            ValueError: If provider_id is unknown
        """
        # Convert string to enum if needed
        if isinstance(provider_id, str):
            try:
                provider_id = ProviderID(provider_id.lower())
            except ValueError:
                available = [p.value for p in ProviderID]
                msg = f"Unknown provider: {provider_id}. Available: {available}"
                raise ValueError(msg) from None
        
        # Import adapter classes (lazy import to avoid circular dependencies)
        from crackerjack.adapters.ai.claude import ClaudeCodeFixer, ClaudeCodeFixerSettings
        from crackerjack.adapters.ai.qwen import QwenCodeFixer, QwenCodeFixerSettings
        from crackerjack.adapters.ai.ollama import OllamaCodeFixer, OllamaCodeFixerSettings
        
        # Create provider instance
        if provider_id == ProviderID.CLAUDE:
            if settings is None:
                settings = ClaudeCodeFixerSettings()
            return ClaudeCodeFixer(settings)
        
        if provider_id == ProviderID.QWEN:
            if settings is None:
                settings = QwenCodeFixerSettings()
            return QwenCodeFixer(settings)
        
        if provider_id == ProviderID.OLLAMA:
            if settings is None:
                settings = OllamaCodeFixerSettings()
            return OllamaCodeFixer(settings)
        
        msg = f"Provider not implemented: {provider_id}"
        raise ValueError(msg)
    
    @staticmethod
    def get_provider_info(provider_id: ProviderID | str) -> ProviderInfo:
        """Get metadata about a provider.
        
        Args:
            provider_id: Provider identifier
            
        Returns:
            ProviderInfo object
            
        Raises:
            ValueError: If provider_id is unknown
        """
        if isinstance(provider_id, str):
            try:
                provider_id = ProviderID(provider_id.lower())
            except ValueError:
                available = [p.value for p in ProviderID]
                msg = f"Unknown provider: {provider_id}. Available: {available}"
                raise ValueError(msg) from None
        
        if provider_id not in PROVIDER_INFO:
            msg = f"Provider info not found: {provider_id}"
            raise ValueError(msg)
        
        return PROVIDER_INFO[provider_id]
    
    @staticmethod
    def list_providers() -> list[ProviderInfo]:
        """List all available providers.
        
        Returns:
            List of ProviderInfo objects
        """
        return list(PROVIDER_INFO.values())

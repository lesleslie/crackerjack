import logging
from dataclasses import dataclass
from enum import Enum

from crackerjack.adapters.ai.base import BaseCodeFixer

logger = logging.getLogger(__name__)


class ProviderID(str, Enum):
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
    def create_provider(
        provider_id: ProviderID | str,
        settings: None = None,
    ) -> BaseCodeFixer:
        if settings is not None:
            msg = "Settings must be loaded from configuration, not passed to create_provider"
            raise TypeError(msg)

        if isinstance(provider_id, str):
            try:
                provider_id = ProviderID(provider_id.lower())
            except ValueError:
                available = [p.value for p in ProviderID]
                msg = f"Unknown provider: {provider_id}. Available: {available}"
                raise ValueError(msg) from None

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
        return list(PROVIDER_INFO.values())

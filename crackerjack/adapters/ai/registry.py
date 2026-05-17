from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from crackerjack.adapters.ai.base import BaseCodeFixer


class ProviderID(StrEnum):
    MINIMAX = "minimax"
    LLAMA_SERVER = "llama_server"
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
    ProviderID.MINIMAX: ProviderInfo(
        id=ProviderID.MINIMAX,
        name="MiniMax",
        description="OpenAI-compatible cloud provider with strong text models",
        requires_api_key=True,
        default_model="MiniMax-M2.7",
        setup_url="https://platform.minimax.io/docs/guides/models-intro",
        cost_tier="medium",
    ),
    ProviderID.LLAMA_SERVER: ProviderInfo(
        id=ProviderID.LLAMA_SERVER,
        name="llama-server (llama.cpp)",
        description="Local llama.cpp server with qwen3.5 — secondary local provider",
        requires_api_key=False,
        default_model="qwen3.5",
        setup_url="https://github.com/ggerganov/llama.cpp",
        cost_tier="free",
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


def list_providers() -> list[ProviderInfo]:
    return list(PROVIDER_INFO.values())


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


def get_code_fixer() -> BaseCodeFixer:
    from crackerjack.adapters.ai.unified import FallbackChainCodeFixer

    return FallbackChainCodeFixer()

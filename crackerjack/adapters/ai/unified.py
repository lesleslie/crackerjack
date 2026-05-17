from __future__ import annotations

import logging
import os
import typing as t
from uuid import UUID

from mcp_common.llm import FallbackChain
from mcp_common.llm.config import LLMSettings, ProviderConfig

from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings
from crackerjack.models.adapter_metadata import AdapterStatus

MODULE_ID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)

_DEFAULT_PROVIDERS: dict[str, dict[str, t.Any]] = {
    "minimax": {
        "name": "minimax",
        "base_url": "https://api.minimax.io/v1",
        "api_key_env": "MINIMAX_API_KEY",
        "api_key": "${MINIMAX_API_KEY}",
        "require_auth": True,
        "task_routing": {
            "code_generation": "MiniMax-M2.7",
            "code_review": "MiniMax-M2.7",
            "debugging": "MiniMax-M2.7",
        },
        "timeout_seconds": 60,
    },
    "llama_server": {
        "name": "llama_server",
        "base_url": "${LLAMA_SERVER_URL}",
        "require_auth": False,
        "task_routing": {
            "code_generation": "qwen3.5",
            "code_review": "qwen3.5",
            "debugging": "qwen3.5",
        },
        "timeout_seconds": 120,
    },
    "ollama": {
        "name": "ollama",
        "base_url": "http://localhost: 11434/v1",
        "require_auth": False,
        "task_routing": {
            "code_generation": "qwen2.5-coder: 7b",
            "code_review": "qwen2.5-coder: 7b",
            "debugging": "qwen2.5-coder: 7b",
        },
        "timeout_seconds": 120,
    },
}


class FallbackChainSettings(BaseCodeFixerSettings):
    model: str = "MiniMax-M2.7"
    task_type: str = "code_generation"
    llama_server_url: str = "http://localhost: 8081"


def _build_llm_settings() -> LLMSettings:
    providers = dict(_DEFAULT_PROVIDERS)
    llama_url = os.environ.get("LLAMA_SERVER_URL", "http://localhost: 8081")
    providers["llama_server"] = dict(providers["llama_server"])
    providers["llama_server"]["base_url"] = llama_url
    return LLMSettings(
        providers=providers,
        fallback_chain=["minimax", "llama_server", "ollama"],
    )


class FallbackChainCodeFixer(BaseCodeFixer):
    def __init__(self, settings: FallbackChainSettings | None = None) -> None:
        super().__init__(settings or FallbackChainSettings())

    async def _initialize_client(self) -> FallbackChain:
        llm_settings = _build_llm_settings()
        chain = FallbackChain.from_settings(llm_settings)
        logger.info("FallbackChainCodeFixer initialized with mcp_common FallbackChain")
        return chain

    async def _call_provider_api(
        self,
        client: t.Any,
        prompt: str,
    ) -> dict[str, t.Any]:
        assert isinstance(self._settings, FallbackChainSettings)
        chain: FallbackChain = client
        return await chain.execute(
            {
                "model": self._settings.model,
                "task_type": self._settings.task_type,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": self._settings.max_tokens,
                "temperature": self._settings.temperature,
            }
        )

    def _extract_content_from_response(self, response: t.Any) -> str:
        if isinstance(response, dict):
            return response.get("content", "")
        return str(response)

    def _validate_provider_specific_settings(self) -> None:
        pass


def build_provider_config(provider_name: str) -> ProviderConfig | None:
    raw = _DEFAULT_PROVIDERS.get(provider_name)
    if raw is None:
        return None
    return ProviderConfig(**raw)

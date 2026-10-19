from __future__ import annotations

import logging
import os
import typing as t
from uuid import UUID

from mcp_common.llm import FallbackChain
from mcp_common.llm.config import LLMSettings, ProviderConfig
from oneiric.adapters.llm.bifrost import get_router
from oneiric.adapters.llm.llm_interface import LLMProvider

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
}


class FallbackChainSettings(BaseCodeFixerSettings):
    model: str = "MiniMax-M2.7"
    task_type: str = "code_generation"
    llama_server_url: str = "http://localhost:8081"


def _build_llm_settings() -> LLMSettings:
    # Phase 5 (REQ-BIFROST-010, bifrost plan §5): the OPENAI-compatible
    # ``minimax`` provider's ``base_url`` comes from the oneiric
    # ``BifrostLLMRouter`` singleton. When the router is enabled and
    # routes OPENAI, the provider transparently hits the local
    # Bifrost gateway (which forwards to the upstream cloud);
    # when the router returns ``None`` (gateway disabled or OPENAI
    # route unconfigured), falls through to the ``MINIMAX_BASE_URL``
    # env-var (operator override) and then to the public
    # ``api.minimax.io`` default. The router → env-var → hardcoded
    # precedence mirrors ``mahavishnu/workers/cloud_worker.py:86-96``.
    # The ``llama_server`` provider keeps its env-var-only resolution
    # (the router's ``_PROVIDER_ROUTE`` only maps ANTHROPIC + OPENAI).
    bifrost_openai_url = get_router().resolve(LLMProvider.OPENAI)
    providers = _DEFAULT_PROVIDERS.copy()
    providers["minimax"] = providers["minimax"].copy()
    if bifrost_openai_url:
        providers["minimax"]["base_url"] = str(bifrost_openai_url)
    else:
        # Router disabled — honor a ``MINIMAX_BASE_URL`` operator
        # override (added in Phase 5 follow-up so the env var matches
        # the comment that has been there since Phase 0). The default
        # stays at the public ``api.minimax.io`` direct-cloud URL.
        env_minimax_url = os.environ.get("MINIMAX_BASE_URL")
        if env_minimax_url:
            providers["minimax"]["base_url"] = env_minimax_url
    llama_url = os.environ.get("LLAMA_SERVER_URL", "http://localhost:8081")
    providers["llama_server"] = providers["llama_server"].copy()
    providers["llama_server"]["base_url"] = llama_url
    return LLMSettings(
        providers=providers,
        fallback_chain=["minimax", "llama_server"],
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

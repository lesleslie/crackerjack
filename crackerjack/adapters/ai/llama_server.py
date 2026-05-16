import logging
import os
import typing as t
from uuid import UUID

from pydantic import Field

from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings
from crackerjack.models.adapter_metadata import AdapterStatus

MODULE_ID = UUID("f7e8d9c0-b1a2-4334-8556-7788990011aa")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class LlamaServerCodeFixerSettings(BaseCodeFixerSettings):
    base_url: str = Field(
        default_factory=lambda: os.environ.get(
            "LLAMA_SERVER_URL", "http://localhost:8081"
        ),
        description="llama.cpp server base URL from LLAMA_SERVER_URL",
    )
    model: str = Field(
        default_factory=lambda: os.environ.get("LLAMA_SERVER_MODEL", "qwen3.5"),
        description="Model name served by llama.cpp from LLAMA_SERVER_MODEL",
    )
    timeout: int = Field(
        default=120,
        ge=30,
        le=600,
        description="Request timeout in seconds",
    )


class LlamaServerCodeFixer(BaseCodeFixer):
    def __init__(self) -> None:
        settings = LlamaServerCodeFixerSettings()
        super().__init__(settings)

    async def _initialize_client(self) -> t.Any:
        import openai

        assert isinstance(self._settings, LlamaServerCodeFixerSettings)

        client = openai.AsyncOpenAI(
            base_url=self._settings.base_url + "/v1",
            api_key="no-auth",
            default_headers={"Authorization": ""},
            max_retries=0,
            timeout=self._settings.timeout,
        )

        logger.debug("llama-server client initialized at %s", self._settings.base_url)
        return client

    async def _call_provider_api(self, client: t.Any, prompt: str) -> t.Any:
        assert isinstance(self._settings, LlamaServerCodeFixerSettings)
        return await client.chat.completions.create(
            model=self._settings.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._settings.temperature,
            max_tokens=self._settings.max_tokens,
        )

    def _extract_content_from_response(self, response: t.Any) -> str:
        return response.choices[0].message.content

    def _validate_provider_specific_settings(self) -> None:
        if not self._settings:
            msg = "LlamaServerCodeFixerSettings not provided"
            raise RuntimeError(msg)

        assert isinstance(self._settings, LlamaServerCodeFixerSettings)
        logger.info(
            "llama-server configured: %s with model %s",
            self._settings.base_url,
            self._settings.model,
        )

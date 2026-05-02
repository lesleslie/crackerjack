import logging
import os
import typing as t
from uuid import UUID

from pydantic import Field, field_validator

from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings
from crackerjack.models.adapter_metadata import AdapterStatus

MODULE_ID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class OllamaCodeFixerSettings(BaseCodeFixerSettings):
    base_url: str = Field(
        default_factory=lambda: os.environ.get(
            "OLLAMA_BASE_URL", "http://localhost: 11434"
        ),
        description="Ollama API endpoint from environment variable OLLAMA_BASE_URL",
    )
    model: str = Field(
        default_factory=lambda: os.environ.get("OLLAMA_MODEL", "qwen2.5-coder: 7b"),
        description="Ollama model from environment variable OLLAMA_MODEL",
    )
    timeout: int = Field(
        default=300,
        ge=30,
        le=600,
        description="Request timeout in seconds (local models can be slow)",
    )
    num_ctx: int = Field(
        default=4096,
        ge=1024,
        le=32768,
        description="Context window size",
    )

    @field_validator("model")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        if ":" not in v:
            return f"{v}:latest"
        return v


class OllamaCodeFixer(BaseCodeFixer):
    def __init__(self) -> None:
        settings = OllamaCodeFixerSettings()
        super().__init__(settings)

    async def _initialize_client(self) -> t.Any:
        import openai

        assert isinstance(self._settings, OllamaCodeFixerSettings)

        client = openai.AsyncOpenAI(
            base_url=self._settings.base_url + "/v1",
            api_key="ollama",
            timeout=self._settings.timeout,
        )

        logger.debug(f"Ollama API client initialized at {self._settings.base_url}")
        return client

    async def _call_provider_api(
        self,
        client: t.Any,
        prompt: str,
    ) -> t.Any:
        assert isinstance(self._settings, OllamaCodeFixerSettings)
        return await client.chat.completions.create(
            model=self._settings.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._settings.temperature,
            num_ctx=self._settings.num_ctx,
        )

    def _extract_content_from_response(self, response: t.Any) -> str:
        return response.choices[0].message.content

    def _validate_provider_specific_settings(self) -> None:
        if not self._settings:
            msg = "OllamaCodeFixerSettings not provided"
            raise RuntimeError(msg)

        assert isinstance(self._settings, OllamaCodeFixerSettings)

        logger.info(
            f"Ollama configured: {self._settings.base_url} with model {self._settings.model}",
        )

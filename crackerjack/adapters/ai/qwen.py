import logging
import os
import typing as t
from uuid import UUID

from pydantic import Field, SecretStr

from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings
from crackerjack.models.adapter_metadata import AdapterStatus

MODULE_ID = UUID("7f3a8b2d-9c4e-4f1a-8b7d-3e9c6a5d2f1b")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class QwenCodeFixerSettings(BaseCodeFixerSettings):
    qwen_api_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.environ.get("QWEN_API_KEY", "")),
        description="Qwen API key from environment variable QWEN_API_KEY",
    )
    base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="Qwen API base URL (OpenAI-compatible endpoint)",
    )
    model: str = Field(
        default="qwen-coder-plus",
        description="Qwen model to use for code fixing",
    )


class QwenCodeFixer(BaseCodeFixer):
    def __init__(self) -> None:
        settings = QwenCodeFixerSettings()
        super().__init__(settings)

    async def _initialize_client(self) -> t.Any:
        import openai

        assert isinstance(self._settings, QwenCodeFixerSettings)
        api_key = self._settings.qwen_api_key.get_secret_value()

        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=self._settings.base_url,
            max_retries=0,
        )

        logger.debug("Qwen API client initialized")
        return client

    async def _call_provider_api(
        self,
        client: t.Any,
        prompt: str,
    ) -> t.Any:
        assert isinstance(self._settings, QwenCodeFixerSettings)
        return await client.chat.completions.create(
            model=self._settings.model,
            max_tokens=self._settings.max_tokens,
            temperature=self._settings.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

    def _extract_content_from_response(self, response: t.Any) -> str:
        return response.choices[0].message.content

    def _validate_provider_specific_settings(self) -> None:
        if not self._settings:
            msg = "QwenCodeFixerSettings not provided"
            raise RuntimeError(msg)

        assert isinstance(self._settings, QwenCodeFixerSettings)

        key = self._settings.qwen_api_key.get_secret_value()
        if len(key) < 20:
            msg = f"Qwen API key too short: {len(key)} < 20"
            raise ValueError(msg)

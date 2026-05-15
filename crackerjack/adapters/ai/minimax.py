import logging
import os
import typing as t
from uuid import UUID

from pydantic import Field, SecretStr

from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings
from crackerjack.models.adapter_metadata import AdapterStatus

MODULE_ID = UUID("b3d4f4d2-4b8f-4c0f-9e6d-6bf5c2f2f312")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class MiniMaxCodeFixerSettings(BaseCodeFixerSettings):
    minimax_api_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.environ.get("MINIMAX_API_KEY", "")),
        description="MiniMax API key from environment variable MINIMAX_API_KEY",
    )
    base_url: str = Field(
        default="https://api.minimax.io/v1",
        description="MiniMax API base URL (OpenAI-compatible endpoint)",
    )
    model: str = Field(
        default="MiniMax-M2.7",
        description="MiniMax model to use for code fixing",
    )


class MiniMaxCodeFixer(BaseCodeFixer):
    def __init__(self) -> None:
        settings = MiniMaxCodeFixerSettings()
        super().__init__(settings)

    async def _initialize_client(self) -> t.Any:
        import openai

        assert isinstance(self._settings, MiniMaxCodeFixerSettings)
        api_key = self._settings.minimax_api_key.get_secret_value()

        client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=self._settings.base_url,
            max_retries=0,
        )

        logger.debug("MiniMax API client initialized")
        return client

    async def _call_provider_api(
        self,
        client: t.Any,
        prompt: str,
    ) -> t.Any:
        assert isinstance(self._settings, MiniMaxCodeFixerSettings)
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
            msg = "MiniMaxCodeFixerSettings not provided"
            raise RuntimeError(msg)

        assert isinstance(self._settings, MiniMaxCodeFixerSettings)

        key = self._settings.minimax_api_key.get_secret_value()
        if len(key) < 20:
            msg = f"MiniMax API key too short: {len(key)} < 20"
            raise ValueError(msg)

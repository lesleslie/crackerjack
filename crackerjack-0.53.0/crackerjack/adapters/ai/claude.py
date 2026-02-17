import logging
import os
import typing as t
from uuid import UUID

from pydantic import Field, SecretStr, field_validator

from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings
from crackerjack.models.adapter_metadata import AdapterStatus

MODULE_ID = UUID("514c99ad-4f9a-4493-acca-542b0c43f95a")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class ClaudeCodeFixerSettings(BaseCodeFixerSettings):
    anthropic_api_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.environ.get("ANTHROPIC_API_KEY", "")),
        description="Anthropic API key from environment variable ANTHROPIC_API_KEY",
    )
    model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Claude model to use for code fixing",
    )

    @field_validator("anthropic_api_key")
    @classmethod
    def validate_api_key_format(cls, v: SecretStr) -> SecretStr:
        key = v.get_secret_value()

        if not key.startswith("sk-ant-"):
            msg = "Invalid Anthropic API key format (must start with 'sk-ant-')"
            raise ValueError(msg)

        if len(key) < 20:
            msg = "API key too short to be valid"
            raise ValueError(msg)

        return v


class ClaudeCodeFixer(BaseCodeFixer):
    def __init__(self) -> None:
        settings = ClaudeCodeFixerSettings()
        super().__init__(settings)

    async def _initialize_client(self) -> t.Any:
        import anthropic

        assert isinstance(self._settings, ClaudeCodeFixerSettings)
        api_key = self._settings.anthropic_api_key.get_secret_value()

        client = anthropic.AsyncAnthropic(
            api_key=api_key,
            max_retries=0,
        )

        logger.debug("Claude API client initialized")
        return client

    async def _call_provider_api(
        self,
        client: t.Any,
        prompt: str,
    ) -> t.Any:
        assert isinstance(self._settings, ClaudeCodeFixerSettings)
        return await client.messages.create(
            model=self._settings.model,
            max_tokens=self._settings.max_tokens,
            temperature=self._settings.temperature,
            messages=[{"role": "user", "content": prompt}],
        )

    def _extract_content_from_response(self, response: t.Any) -> str:
        return response.content[0].text

    def _validate_provider_specific_settings(self) -> None:
        if not self._settings:
            msg = "ClaudeCodeFixerSettings not provided"
            raise RuntimeError(msg)

        assert isinstance(self._settings, ClaudeCodeFixerSettings)

        key = self._settings.anthropic_api_key.get_secret_value()
        if not key.startswith("sk-ant-"):
            msg = f"Invalid Anthropic API key format: {key[:10]}..."
            raise ValueError(msg)

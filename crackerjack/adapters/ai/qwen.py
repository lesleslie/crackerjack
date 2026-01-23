"""Qwen AI provider for code fixing."""

import logging
import typing as t
from uuid import UUID

from pydantic import Field, SecretStr

from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings
from crackerjack.models.adapter_metadata import AdapterStatus

MODULE_ID = UUID("7f3a8b2d-9c4e-4f1a-8b7d-3e9c6a5d2f1b")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class QwenCodeFixerSettings(BaseCodeFixerSettings):
    """Qwen-specific settings."""
    qwen_api_key: SecretStr = Field(
        ...,
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
    """Qwen AI code fixer implementation.
    
    Uses Qwen's OpenAI-compatible API:
    https://help.aliyun.com/zh/dashscope/developer-reference/compatibility-of-openai-with-dashscope
    
    Refactored to inherit from BaseCodeFixer, reducing code from ~508 lines to ~140 lines.
    """
    
    def __init__(
        self,
        settings: QwenCodeFixerSettings | None = None,
    ) -> None:
        """Initialize Qwen code fixer.
        
        Args:
            settings: Qwen-specific settings (API key, base_url, model, etc.)
        """
        super().__init__(settings)
    
    async def _initialize_client(self) -> t.Any:
        """Initialize OpenAI-compatible client for Qwen."""
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
        """Call Qwen Chat Completions API.
        
        Args:
            client: openai.AsyncOpenAI instance
            prompt: Sanitized prompt for Qwen
            
        Returns:
            Chat completion response object
        """
        assert isinstance(self._settings, QwenCodeFixerSettings)
        return await client.chat.completions.create(
            model=self._settings.model,
            max_tokens=self._settings.max_tokens,
            temperature=self._settings.temperature,
            messages=[{"role": "user", "content": prompt}],
        )
    
    def _extract_content_from_response(self, response: t.Any) -> str:
        """Extract text from Qwen response.
        
        OpenAI-compatible format: response.choices[0].message.content
        """
        return response.choices[0].message.content
    
    def _validate_provider_specific_settings(self) -> None:
        """Validate Qwen API key format."""
        if not self._settings:
            msg = "QwenCodeFixerSettings not provided"
            raise RuntimeError(msg)
        
        assert isinstance(self._settings, QwenCodeFixerSettings)
        
        key = self._settings.qwen_api_key.get_secret_value()
        if len(key) < 20:
            msg = f"Qwen API key too short: {len(key)} < 20"
            raise ValueError(msg)

"""Ollama AI provider for local code fixing.

Supports running Qwen models locally via Ollama:
- No API key required
- Complete data privacy
- Zero cost
- Models: qwen2.5-coder, qwen2.5, deepseek-coder, etc.

Setup: https://ollama.com/download
Models: https://ollama.com/search
"""

import logging
import typing as t
from uuid import UUID

from pydantic import Field, field_validator

from crackerjack.adapters.ai.base import BaseCodeFixer, BaseCodeFixerSettings
from crackerjack.models.adapter_metadata import AdapterStatus

MODULE_ID = UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
MODULE_STATUS = AdapterStatus.STABLE

logger = logging.getLogger(__name__)


class OllamaCodeFixerSettings(BaseCodeFixerSettings):
    """Ollama-specific settings."""
    base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API endpoint (default: local Ollama instance)",
    )
    model: str = Field(
        default="qwen2.5-coder:7b",
        description="Ollama model to use (e.g., qwen2.5-coder:7b, qwen2.5:14b)",
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
        """Validate Ollama model name format."""
        # Ollama models: name:tag format (e.g., qwen2.5-coder:7b)
        if ":" not in v:
            # Default to :latest if no tag specified
            return f"{v}:latest"
        return v


class OllamaCodeFixer(BaseCodeFixer):
    """Ollama AI code fixer implementation.
    
    Uses Ollama's OpenAI-compatible API:
    https://github.com/ollama/ollama/blob/main/docs/api.md
    
    Advantages:
    - No API keys required
    - Complete data privacy
    - Zero cost
    - Support for multiple open-source models
    
    Disadvantages:
    - Requires local installation
    - Slower than cloud APIs
    - Quality depends on model choice
    """
    
    def __init__(
        self,
        settings: OllamaCodeFixerSettings | None = None,
    ) -> None:
        """Initialize Ollama code fixer.
        
        Args:
            settings: Ollama-specific settings (base_url, model, etc.)
        """
        super().__init__(settings)
    
    async def _initialize_client(self) -> t.Any:
        """Initialize OpenAI-compatible client for Ollama."""
        import openai
        
        assert isinstance(self._settings, OllamaCodeFixerSettings)
        
        # Ollama uses OpenAI-compatible API
        # No API key required for local Ollama
        client = openai.AsyncOpenAI(
            base_url=self._settings.base_url + "/v1",
            api_key="ollama",  # Required by OpenAI client but ignored by Ollama
            timeout=self._settings.timeout,
        )
        
        logger.debug(f"Ollama API client initialized at {self._settings.base_url}")
        return client
    
    async def _call_provider_api(
        self,
        client: t.Any,
        prompt: str,
    ) -> t.Any:
        """Call Ollama Chat API.
        
        Args:
            client: openai.AsyncOpenAI instance
            prompt: Sanitized prompt for Ollama
            
        Returns:
            Chat completion response object
        """
        assert isinstance(self._settings, OllamaCodeFixerSettings)
        return await client.chat.completions.create(
            model=self._settings.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._settings.temperature,
            num_ctx=self._settings.num_ctx,
        )
    
    def _extract_content_from_response(self, response: t.Any) -> str:
        """Extract text from Ollama response.
        
        OpenAI-compatible format: response.choices[0].message.content
        """
        return response.choices[0].message.content
    
    def _validate_provider_specific_settings(self) -> None:
        """Validate Ollama settings and connectivity.
        
        For Ollama, we verify:
        - base_url is accessible
        - model is available locally
        """
        if not self._settings:
            msg = "OllamaCodeFixerSettings not provided"
            raise RuntimeError(msg)
        
        assert isinstance(self._settings, OllamaCodeFixerSettings)
        
        # Note: Could add async connection test here
        # For now, we trust the configuration
        logger.info(
            f"Ollama configured: {self._settings.base_url} with model {self._settings.model}",
        )

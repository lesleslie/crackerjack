#!/usr/bin/env python3
"""Cross-LLM Compatibility for Session Management MCP Server.

Provides unified interface for multiple LLM providers including OpenAI, Google Gemini, and Ollama.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class LLMMessage:
    """Standardized message format across LLM providers."""

    role: str  # 'system', 'user', 'assistant'
    content: str
    timestamp: str | None = None
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.metadata is None:
            self.metadata = {}


@dataclass
class LLMResponse:
    """Standardized response format from LLM providers."""

    content: str
    model: str
    provider: str
    usage: dict[str, Any]
    finish_reason: str
    timestamp: str
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.name = self.__class__.__name__.replace("Provider", "").lower()
        self.logger = logging.getLogger(f"llm_providers.{self.name}")

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a response from the LLM."""

    @abstractmethod
    async def stream_generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[str]:
        """Generate a streaming response from the LLM."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the provider is available and properly configured."""

    @abstractmethod
    def get_models(self) -> list[str]:
        """Get list of available models for this provider."""


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.api_key = config.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.default_model = config.get("default_model", "gpt-4")
        self._client = None

    async def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                import openai

                self._client = openai.AsyncOpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                msg = "OpenAI package not installed. Install with: pip install openai"
                raise ImportError(
                    msg,
                )
        return self._client

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, str]]:
        """Convert LLMMessage objects to OpenAI format."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using OpenAI API."""
        if not await self.is_available():
            msg = "OpenAI provider not available"
            raise RuntimeError(msg)

        client = await self._get_client()
        model_name = model or self.default_model

        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=self._convert_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            return LLMResponse(
                content=response.choices[0].message.content,
                model=model_name,
                provider="openai",
                usage={
                    "prompt_tokens": response.usage.prompt_tokens
                    if response.usage
                    else 0,
                    "completion_tokens": response.usage.completion_tokens
                    if response.usage
                    else 0,
                    "total_tokens": response.usage.total_tokens
                    if response.usage
                    else 0,
                },
                finish_reason=response.choices[0].finish_reason,
                timestamp=datetime.now().isoformat(),
                metadata={"response_id": response.id},
            )

        except Exception as e:
            self.logger.exception(f"OpenAI generation failed: {e}")
            raise

    async def stream_generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[str]:
        """Stream response using OpenAI API."""
        if not await self.is_available():
            msg = "OpenAI provider not available"
            raise RuntimeError(msg)

        client = await self._get_client()
        model_name = model or self.default_model

        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=self._convert_messages(messages),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs,
            )

            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            self.logger.exception(f"OpenAI streaming failed: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if OpenAI API is available."""
        if not self.api_key:
            return False

        try:
            client = await self._get_client()
            # Test with a simple request
            await client.models.list()
            return True
        except Exception:
            return False

    def get_models(self) -> list[str]:
        """Get available OpenAI models."""
        return [
            "gpt-4",
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
        ]


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.api_key = (
            config.get("api_key")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        self.default_model = config.get("default_model", "gemini-pro")
        self._client = None

    async def _get_client(self):
        """Get or create Gemini client."""
        if self._client is None:
            try:
                import google.generativeai as genai

                genai.configure(api_key=self.api_key)
                self._client = genai
            except ImportError:
                msg = "Google Generative AI package not installed. Install with: pip install google-generativeai"
                raise ImportError(
                    msg,
                )
        return self._client

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, str]]:
        """Convert LLMMessage objects to Gemini format."""
        converted = []
        for msg in messages:
            if msg.role == "system":
                # Gemini doesn't have system role, prepend to first user message
                if converted and converted[-1]["role"] == "user":
                    converted[-1]["parts"] = [
                        f"System: {msg.content}\n\nUser: {converted[-1]['parts'][0]}",
                    ]
                else:
                    converted.append(
                        {"role": "user", "parts": [f"System: {msg.content}"]},
                    )
            elif msg.role == "user":
                converted.append({"role": "user", "parts": [msg.content]})
            elif msg.role == "assistant":
                converted.append({"role": "model", "parts": [msg.content]})
        return converted

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using Gemini API."""
        if not await self.is_available():
            msg = "Gemini provider not available"
            raise RuntimeError(msg)

        genai = await self._get_client()
        model_name = model or self.default_model

        try:
            model_instance = genai.GenerativeModel(model_name)

            # Convert messages to Gemini chat format
            chat_messages = self._convert_messages(messages)

            # Create chat or generate single response
            if len(chat_messages) > 1:
                chat = model_instance.start_chat(history=chat_messages[:-1])
                response = await chat.send_message_async(
                    chat_messages[-1]["parts"][0],
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    },
                )
            else:
                response = await model_instance.generate_content_async(
                    chat_messages[0]["parts"][0],
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    },
                )

            return LLMResponse(
                content=response.text,
                model=model_name,
                provider="gemini",
                usage={
                    "prompt_tokens": response.usage_metadata.prompt_token_count
                    if hasattr(response, "usage_metadata")
                    else 0,
                    "completion_tokens": response.usage_metadata.candidates_token_count
                    if hasattr(response, "usage_metadata")
                    else 0,
                    "total_tokens": response.usage_metadata.total_token_count
                    if hasattr(response, "usage_metadata")
                    else 0,
                },
                finish_reason="stop",  # Gemini doesn't provide detailed finish reasons
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            self.logger.exception(f"Gemini generation failed: {e}")
            raise

    async def stream_generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[str]:
        """Stream response using Gemini API."""
        if not await self.is_available():
            msg = "Gemini provider not available"
            raise RuntimeError(msg)

        genai = await self._get_client()
        model_name = model or self.default_model

        try:
            model_instance = genai.GenerativeModel(model_name)
            chat_messages = self._convert_messages(messages)

            if len(chat_messages) > 1:
                chat = model_instance.start_chat(history=chat_messages[:-1])
                response = chat.send_message(
                    chat_messages[-1]["parts"][0],
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    },
                    stream=True,
                )
            else:
                response = model_instance.generate_content(
                    chat_messages[0]["parts"][0],
                    generation_config={
                        "temperature": temperature,
                        "max_output_tokens": max_tokens,
                    },
                    stream=True,
                )

            for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            self.logger.exception(f"Gemini streaming failed: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if Gemini API is available."""
        if not self.api_key:
            return False

        try:
            genai = await self._get_client()
            # Test with a simple model list request
            list(genai.list_models())
            return True
        except Exception:
            return False

    def get_models(self) -> list[str]:
        """Get available Gemini models."""
        return [
            "gemini-pro",
            "gemini-pro-vision",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.0-pro",
        ]


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.default_model = config.get("default_model", "llama2")
        self._available_models = []

    async def _make_request(
        self,
        endpoint: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Make HTTP request to Ollama API."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/{endpoint}",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    return await response.json()
        except ImportError:
            msg = "aiohttp package not installed. Install with: pip install aiohttp"
            raise ImportError(
                msg,
            )

    def _convert_messages(self, messages: list[LLMMessage]) -> list[dict[str, str]]:
        """Convert LLMMessage objects to Ollama format."""
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    async def generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate response using Ollama API."""
        if not await self.is_available():
            msg = "Ollama provider not available"
            raise RuntimeError(msg)

        model_name = model or self.default_model

        try:
            data = {
                "model": model_name,
                "messages": self._convert_messages(messages),
                "options": {"temperature": temperature},
            }

            if max_tokens:
                data["options"]["num_predict"] = max_tokens

            response = await self._make_request("api/chat", data)

            return LLMResponse(
                content=response.get("message", {}).get("content", ""),
                model=model_name,
                provider="ollama",
                usage={
                    "prompt_tokens": response.get("prompt_eval_count", 0),
                    "completion_tokens": response.get("eval_count", 0),
                    "total_tokens": response.get("prompt_eval_count", 0)
                    + response.get("eval_count", 0),
                },
                finish_reason=response.get("done_reason", "stop"),
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            self.logger.exception(f"Ollama generation failed: {e}")
            raise

    async def stream_generate(
        self,
        messages: list[LLMMessage],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncGenerator[str]:
        """Stream response using Ollama API."""
        if not await self.is_available():
            msg = "Ollama provider not available"
            raise RuntimeError(msg)

        model_name = model or self.default_model

        try:
            import aiohttp

            data = {
                "model": model_name,
                "messages": self._convert_messages(messages),
                "stream": True,
                "options": {"temperature": temperature},
            }

            if max_tokens:
                data["options"]["num_predict"] = max_tokens

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    async for line in response.content:
                        if line:
                            try:
                                chunk_data = json.loads(line.decode("utf-8"))
                                if (
                                    "message" in chunk_data
                                    and "content" in chunk_data["message"]
                                ):
                                    yield chunk_data["message"]["content"]
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            self.logger.exception(f"Ollama streaming failed: {e}")
            raise

    async def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._available_models = [
                            model["name"] for model in data.get("models", [])
                        ]
                        return True
            return False
        except Exception:
            return False

    def get_models(self) -> list[str]:
        """Get available Ollama models."""
        return (
            self._available_models
            if self._available_models
            else [
                "llama2",
                "llama2:13b",
                "llama2:70b",
                "codellama",
                "mistral",
                "mixtral",
            ]
        )


class LLMManager:
    """Manager for multiple LLM providers with fallback support."""

    def __init__(self, config_path: str | None = None) -> None:
        self.providers: dict[str, LLMProvider] = {}
        self.config = self._load_config(config_path)
        self.logger = logging.getLogger("llm_providers.manager")
        self._initialize_providers()

    def _load_config(self, config_path: str | None) -> dict[str, Any]:
        """Load configuration from file or environment."""
        config = {
            "providers": {},
            "default_provider": "openai",
            "fallback_providers": ["gemini", "ollama"],
        }

        if config_path and Path(config_path).exists():
            try:
                with open(config_path) as f:
                    file_config = json.load(f)
                    config.update(file_config)
            except (OSError, json.JSONDecodeError):
                pass

        # Add environment-based provider configs
        if not config["providers"].get("openai"):
            config["providers"]["openai"] = {
                "api_key": os.getenv("OPENAI_API_KEY"),
                "default_model": "gpt-4",
            }

        if not config["providers"].get("gemini"):
            config["providers"]["gemini"] = {
                "api_key": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
                "default_model": "gemini-pro",
            }

        if not config["providers"].get("ollama"):
            config["providers"]["ollama"] = {
                "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
                "default_model": "llama2",
            }

        return config

    def _initialize_providers(self) -> None:
        """Initialize all configured providers."""
        provider_classes = {
            "openai": OpenAIProvider,
            "gemini": GeminiProvider,
            "ollama": OllamaProvider,
        }

        for provider_name, provider_config in self.config["providers"].items():
            if provider_name in provider_classes:
                try:
                    self.providers[provider_name] = provider_classes[provider_name](
                        provider_config,
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to initialize {provider_name} provider: {e}",
                    )

    async def get_available_providers(self) -> list[str]:
        """Get list of available providers."""
        available = []
        for name, provider in self.providers.items():
            if await provider.is_available():
                available.append(name)
        return available

    async def generate(
        self,
        messages: list[LLMMessage],
        provider: str | None = None,
        model: str | None = None,
        use_fallback: bool = True,
        **kwargs,
    ) -> LLMResponse:
        """Generate response with optional fallback."""
        target_provider = provider or self.config["default_provider"]

        # Try primary provider
        if target_provider in self.providers:
            try:
                provider_instance = self.providers[target_provider]
                if await provider_instance.is_available():
                    return await provider_instance.generate(messages, model, **kwargs)
            except Exception as e:
                self.logger.warning(f"Provider {target_provider} failed: {e}")

        # Try fallback providers if enabled
        if use_fallback:
            for fallback_name in self.config.get("fallback_providers", []):
                if fallback_name in self.providers and fallback_name != target_provider:
                    try:
                        provider_instance = self.providers[fallback_name]
                        if await provider_instance.is_available():
                            self.logger.info(f"Falling back to {fallback_name}")
                            return await provider_instance.generate(
                                messages,
                                model,
                                **kwargs,
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Fallback provider {fallback_name} failed: {e}",
                        )

        msg = "No available LLM providers"
        raise RuntimeError(msg)

    async def stream_generate(
        self,
        messages: list[LLMMessage],
        provider: str | None = None,
        model: str | None = None,
        use_fallback: bool = True,
        **kwargs,
    ) -> AsyncGenerator[str]:
        """Stream generate response with optional fallback."""
        target_provider = provider or self.config["default_provider"]

        # Try primary provider
        if target_provider in self.providers:
            try:
                provider_instance = self.providers[target_provider]
                if await provider_instance.is_available():
                    async for chunk in provider_instance.stream_generate(
                        messages,
                        model,
                        **kwargs,
                    ):
                        yield chunk
                    return
            except Exception as e:
                self.logger.warning(f"Provider {target_provider} failed: {e}")

        # Try fallback providers if enabled
        if use_fallback:
            for fallback_name in self.config.get("fallback_providers", []):
                if fallback_name in self.providers and fallback_name != target_provider:
                    try:
                        provider_instance = self.providers[fallback_name]
                        if await provider_instance.is_available():
                            self.logger.info(f"Falling back to {fallback_name}")
                            async for chunk in provider_instance.stream_generate(
                                messages,
                                model,
                                **kwargs,
                            ):
                                yield chunk
                            return
                    except Exception as e:
                        self.logger.warning(
                            f"Fallback provider {fallback_name} failed: {e}",
                        )

        msg = "No available LLM providers"
        raise RuntimeError(msg)

    def get_provider_info(self) -> dict[str, Any]:
        """Get information about all providers."""
        info = {
            "providers": {},
            "config": {
                "default_provider": self.config["default_provider"],
                "fallback_providers": self.config.get("fallback_providers", []),
            },
        }

        for name, provider in self.providers.items():
            info["providers"][name] = {
                "models": provider.get_models(),
                "config": {
                    k: v for k, v in provider.config.items() if "key" not in k.lower()
                },
            }

        return info

    async def test_providers(self) -> dict[str, Any]:
        """Test all providers and return status."""
        test_message = [
            LLMMessage(role="user", content='Hello, respond with just "OK"'),
        ]
        results = {}

        for name, provider in self.providers.items():
            try:
                available = await provider.is_available()
                if available:
                    # Quick test generation
                    response = await provider.generate(test_message, max_tokens=10)
                    results[name] = {
                        "available": True,
                        "test_successful": True,
                        "response_length": len(response.content),
                        "model": response.model,
                    }
                else:
                    results[name] = {
                        "available": False,
                        "test_successful": False,
                        "error": "Provider not available",
                    }
            except Exception as e:
                results[name] = {
                    "available": False,
                    "test_successful": False,
                    "error": str(e),
                }

        return results

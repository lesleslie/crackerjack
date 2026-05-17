"""Tests for FallbackChainCodeFixer.

Validates that the unified code fixer correctly delegates LLM calls
to mcp_common FallbackChain with proper task_type routing.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.adapters.ai.base import BaseCodeFixer
from crackerjack.adapters.ai.registry import (
    PROVIDER_INFO,
    ProviderID,
    get_code_fixer,
    get_provider_info,
    list_providers,
)
from crackerjack.adapters.ai.unified import (
    FallbackChainCodeFixer,
    FallbackChainSettings,
    _build_llm_settings,
    build_provider_config,
)


class TestFallbackChainCodeFixer:
    """Tests for FallbackChainCodeFixer initialization and behavior."""

    def test_is_base_code_fixer_subclass(self):
        fixer = FallbackChainCodeFixer()
        assert isinstance(fixer, BaseCodeFixer)

    def test_default_settings(self):
        fixer = FallbackChainCodeFixer()
        assert isinstance(fixer._settings, FallbackChainSettings)
        assert fixer._settings.task_type == "code_generation"
        assert fixer._settings.model == "MiniMax-M2.7"

    def test_validate_provider_specific_settings_is_noop(self):
        fixer = FallbackChainCodeFixer()
        fixer._settings = FallbackChainSettings()
        fixer._validate_provider_specific_settings()  # should not raise

    def test_extract_content_from_dict_response(self):
        fixer = FallbackChainCodeFixer()
        result = fixer._extract_content_from_response({"content": "fixed code", "model": "m"})
        assert result == "fixed code"

    def test_extract_content_from_empty_dict(self):
        fixer = FallbackChainCodeFixer()
        result = fixer._extract_content_from_response({})
        assert result == ""

    def test_extract_content_from_string_response(self):
        fixer = FallbackChainCodeFixer()
        result = fixer._extract_content_from_response("raw string")
        assert result == "raw string"

    @pytest.mark.asyncio
    async def test_initialize_client_returns_fallback_chain(self):
        fixer = FallbackChainCodeFixer()
        from mcp_common.llm import FallbackChain

        with patch("mcp_common.llm.fallback.FallbackChain.from_settings") as mock_fs:
            mock_chain = MagicMock(spec=FallbackChain)
            mock_fs.return_value = mock_chain
            client = await fixer._initialize_client()
            assert client is mock_chain

    @pytest.mark.asyncio
    async def test_call_provider_api_delegates_to_chain(self):
        fixer = FallbackChainCodeFixer()
        fixer._settings = FallbackChainSettings(
            model="MiniMax-M2.7",
            task_type="code_generation",
            max_tokens=2048,
            temperature=0.1,
        )

        mock_chain = AsyncMock()
        mock_chain.execute.return_value = {"content": "fixed", "provider": "minimax"}

        result = await fixer._call_provider_api(mock_chain, "fix this code")

        mock_chain.execute.assert_awaited_once()
        call_kwargs = mock_chain.execute.call_args[0][0]
        assert call_kwargs["task_type"] == "code_generation"
        assert call_kwargs["max_tokens"] == 2048
        assert call_kwargs["temperature"] == 0.1
        assert call_kwargs["messages"][0]["content"] == "fix this code"
        assert result["content"] == "fixed"


class TestBuildLlmSettings:
    """Tests for _build_llm_settings."""

    def test_default_fallback_chain(self):
        settings = _build_llm_settings()
        assert settings.fallback_chain == ["minimax", "llama_server", "ollama"]

    def test_llama_server_url_from_env(self):
        with patch.dict(os.environ, {"LLAMA_SERVER_URL": "http://myserver:9000"}):
            settings = _build_llm_settings()
        assert settings.providers["llama_server"]["base_url"] == "http://myserver:9000"

    def test_llama_server_url_default(self):
        env = {k: v for k, v in os.environ.items() if k != "LLAMA_SERVER_URL"}
        with patch.dict(os.environ, env, clear=True):
            settings = _build_llm_settings()
        assert settings.providers["llama_server"]["base_url"] == "http://localhost: 8081"

    def test_all_three_providers_present(self):
        settings = _build_llm_settings()
        assert "minimax" in settings.providers
        assert "llama_server" in settings.providers
        assert "ollama" in settings.providers

    def test_minimax_requires_auth(self):
        settings = _build_llm_settings()
        assert settings.providers["minimax"]["require_auth"] is True

    def test_local_providers_no_auth(self):
        settings = _build_llm_settings()
        assert settings.providers["llama_server"]["require_auth"] is False
        assert settings.providers["ollama"]["require_auth"] is False


class TestBuildProviderConfig:
    """Tests for build_provider_config helper."""

    def test_known_provider_returns_config(self):
        config = build_provider_config("minimax")
        assert config is not None
        assert config.require_auth is True

    def test_unknown_provider_returns_none(self):
        config = build_provider_config("nonexistent")
        assert config is None

    def test_ollama_config_no_auth(self):
        config = build_provider_config("ollama")
        assert config is not None
        assert config.require_auth is False


class TestProviderRegistry:
    """Tests for the simplified registry module."""

    def test_provider_ids_defined(self):
        assert ProviderID.MINIMAX == "minimax"
        assert ProviderID.LLAMA_SERVER == "llama_server"
        assert ProviderID.OLLAMA == "ollama"

    def test_provider_info_populated(self):
        assert ProviderID.MINIMAX in PROVIDER_INFO
        assert ProviderID.LLAMA_SERVER in PROVIDER_INFO
        assert ProviderID.OLLAMA in PROVIDER_INFO

    def test_list_providers_returns_all(self):
        infos = list_providers()
        ids = {info.id for info in infos}
        assert ProviderID.MINIMAX in ids
        assert ProviderID.LLAMA_SERVER in ids
        assert ProviderID.OLLAMA in ids

    def test_get_provider_info_by_id(self):
        info = get_provider_info(ProviderID.MINIMAX)
        assert info.requires_api_key is True
        assert info.default_model == "MiniMax-M2.7"

    def test_get_provider_info_by_string(self):
        info = get_provider_info("ollama")
        assert info.requires_api_key is False
        assert info.cost_tier == "free"

    def test_get_provider_info_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider_info("claude")

    def test_get_code_fixer_returns_fixer(self):
        fixer = get_code_fixer()
        assert isinstance(fixer, FallbackChainCodeFixer)

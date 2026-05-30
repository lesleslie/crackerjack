"""Tests for AI adapter registry and provider info.

Covers: crackerjack/adapters/ai/registry.py
"""

from __future__ import annotations

import pytest

from crackerjack.adapters.ai.registry import (
    PROVIDER_INFO,
    ProviderID,
    ProviderInfo,
    get_code_fixer,
    get_provider_info,
    list_providers,
)


class TestProviderID:
    """Tests for ProviderID enum."""

    def test_provider_id_values(self):
        assert ProviderID.MINIMAX == "minimax"
        assert ProviderID.LLAMA_SERVER == "llama_server"
        assert ProviderID.OLLAMA == "ollama"


class TestProviderInfo:
    """Tests for ProviderInfo dataclass."""

    def test_provider_info_str(self):
        info = PROVIDER_INFO[ProviderID.MINIMAX]
        assert "MiniMax" in str(info)
        assert "minimax" in str(info)

    def test_provider_info_fields(self):
        info = PROVIDER_INFO[ProviderID.MINIMAX]
        assert info.id == ProviderID.MINIMAX
        assert info.name == "MiniMax"
        assert info.requires_api_key is True
        assert info.default_model == "MiniMax-M2.7"
        assert info.cost_tier == "medium"

    def test_llama_server_info(self):
        info = PROVIDER_INFO[ProviderID.LLAMA_SERVER]
        assert info.requires_api_key is False
        assert info.default_model == "qwen3.5"
        assert info.cost_tier == "free"

    def test_ollama_info(self):
        info = PROVIDER_INFO[ProviderID.OLLAMA]
        assert info.requires_api_key is False
        assert info.cost_tier == "free"


class TestListProviders:
    """Tests for list_providers function."""

    def test_returns_all_providers(self):
        providers = list_providers()
        assert len(providers) == 3

    def test_returns_provider_info_objects(self):
        providers = list_providers()
        assert all(isinstance(p, ProviderInfo) for p in providers)

    def test_contains_minimax(self):
        providers = list_providers()
        ids = [p.id for p in providers]
        assert ProviderID.MINIMAX in ids


class TestGetProviderInfo:
    """Tests for get_provider_info function."""

    def test_get_by_provider_id(self):
        info = get_provider_info(ProviderID.MINIMAX)
        assert info.id == ProviderID.MINIMAX

    def test_get_by_string_lowercase(self):
        info = get_provider_info("ollama")
        assert info.id == ProviderID.OLLAMA

    def test_get_by_string_uppercase(self):
        info = get_provider_info("OLLAMA")
        assert info.id == ProviderID.OLLAMA

    def test_get_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider_info("unknown_provider")

    def test_unknown_provider_error_message(self):
        with pytest.raises(ValueError) as exc_info:
            get_provider_info("claude")
        assert "claude" in str(exc_info.value)
        assert "Available" in str(exc_info.value)


class TestGetCodeFixer:
    """Tests for get_code_fixer function."""

    def test_returns_code_fixer_instance(self):
        fixer = get_code_fixer()
        from crackerjack.adapters.ai.unified import FallbackChainCodeFixer

        assert isinstance(fixer, FallbackChainCodeFixer)

    def test_returns_same_instance_type(self):
        fixer1 = get_code_fixer()
        fixer2 = get_code_fixer()
        # Both should be the same type
        assert type(fixer1) == type(fixer2)

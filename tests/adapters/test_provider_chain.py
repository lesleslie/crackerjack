"""Tests for FallbackChainCodeFixer.

Validates that the unified code fixer correctly delegates LLM calls
to mcp_common FallbackChain with proper task_type routing.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from oneiric.adapters.llm.bifrost import reset_router_for_tests

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


# Per-test oneiric router reset. The router is a process-cached
# singleton; without this fixture, an earlier test that enabled
# the router would leak its state into later tests. The fixture
# also clears the oneiric env-var surface so tests are not
# coupled to operator-shell state.
@pytest.fixture(autouse=True)
def _reset_bifrost_router(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_key in (
        "ONEIRIC_BIFROST_ENABLED",
        "ONEIRIC_BIFROST_BASE_URL",
        "ONEIRIC_BIFROST_ROUTES",
    ):
        monkeypatch.delenv(env_key, raising=False)
    reset_router_for_tests()
    yield
    reset_router_for_tests()


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
        assert settings.fallback_chain == ["minimax", "llama_server"]

    def test_llama_server_url_from_env(self):
        with patch.dict(os.environ, {"LLAMA_SERVER_URL": "http://myserver:9000"}):
            settings = _build_llm_settings()
        assert settings.providers["llama_server"]["base_url"] == "http://myserver:9000"

    def test_llama_server_url_default(self):
        env = {k: v for k, v in os.environ.items() if k != "LLAMA_SERVER_URL"}
        with patch.dict(os.environ, env, clear=True):
            settings = _build_llm_settings()
        assert settings.providers["llama_server"]["base_url"] == "http://localhost:8081"

    def test_all_three_providers_present(self):
        settings = _build_llm_settings()
        assert "minimax" in settings.providers
        assert "llama_server" in settings.providers

    def test_minimax_requires_auth(self):
        settings = _build_llm_settings()
        assert settings.providers["minimax"]["require_auth"] is True

    def test_local_providers_no_auth(self):
        settings = _build_llm_settings()
        assert settings.providers["llama_server"]["require_auth"] is False

    def test_chain_uses_router(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """REQ-BIFROST-010 (bifrost plan §5 Phase 5): the OPENAI-
        compatible provider in ``_build_llm_settings`` sources its
        ``base_url`` from the oneiric ``BifrostLLMRouter`` singleton
        when the router is enabled and the OPENAI route is
        configured. Captures the ``LLMSettings`` instance and
        asserts the ``minimax`` provider's ``base_url`` matches
        the router's resolved URL.
        """
        monkeypatch.setenv("ONEIRIC_BIFROST_ENABLED", "true")
        monkeypatch.setenv("ONEIRIC_BIFROST_ROUTES", "qwen_route")
        monkeypatch.setenv("ONEIRIC_BIFROST_BASE_URL", "http://127.0.0.1:8471/v1")
        reset_router_for_tests()

        settings = _build_llm_settings()
        assert (
            settings.providers["minimax"]["base_url"] == "http://127.0.0.1:8471/v1"
        ), "REQ-BIFROST-010: minimax's base_url must come from the oneiric router."

    def test_chain_falls_back_to_direct_cloud_when_router_disabled(
        self,
    ) -> None:
        """When the router is disabled, ``_build_llm_settings`` falls
        through to the direct cloud URL. The pre-Phase-5
        ``https://api.minimax.io/v1`` default must survive the
        router integration (the gateway is opt-in).

        Note: the autouse ``_reset_bifrost_router`` fixture handles
        env-var cleanup; this test takes no ``monkeypatch`` parameter.
        """
        # Autouse fixture already cleared oneiric env vars; this
        # explicit assert documents the contract.
        assert "ONEIRIC_BIFROST_ENABLED" not in os.environ
        reset_router_for_tests()

        settings = _build_llm_settings()
        assert settings.providers["minimax"]["base_url"] == "https://api.minimax.io/v1"

    def test_chain_honors_minimax_base_url_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """General-purpose LOW-1: when the router is disabled, the
        ``MINIMAX_BASE_URL`` env-var is honored (operator override).
        Mirrors ``mahavishnu/workers/cloud_worker.py:86-96`` where
        the precedence is router → env-var → hardcoded default.
        """
        monkeypatch.setenv("MINIMAX_BASE_URL", "http://custom-direct:9999/v1")
        reset_router_for_tests()

        settings = _build_llm_settings()
        assert (
            settings.providers["minimax"]["base_url"]
            == "http://custom-direct:9999/v1"
        )

    def test_chain_keeps_llama_server_env_var_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``llama_server`` is not in the router's ``_PROVIDER_ROUTE``
        mapping; it keeps its env-var-only resolution. Pinning
        this prevents a future refactor from accidentally
        routing ``llama_server`` through the router (which would
        raise ``KeyError`` at runtime per the oneiric router
        contract).
        """
        monkeypatch.setenv("ONEIRIC_BIFROST_ENABLED", "true")
        monkeypatch.setenv("ONEIRIC_BIFROST_ROUTES", "qwen_route")
        monkeypatch.setenv("ONEIRIC_BIFROST_BASE_URL", "http://127.0.0.1:8471/v1")
        monkeypatch.setenv("LLAMA_SERVER_URL", "http://local-llama:9999")
        reset_router_for_tests()

        settings = _build_llm_settings()
        # ``llama_server`` keeps its env-var URL — never reads from the router.
        assert settings.providers["llama_server"]["base_url"] == "http://local-llama:9999"
        # ``minimax`` got the router's URL.
        assert settings.providers["minimax"]["base_url"] == "http://127.0.0.1:8471/v1"


class TestBuildProviderConfig:
    """Tests for build_provider_config helper."""

    def test_known_provider_returns_config(self):
        config = build_provider_config("minimax")
        assert config is not None
        assert config.require_auth is True

    def test_unknown_provider_returns_none(self):
        config = build_provider_config("nonexistent")
        assert config is None


class TestProviderRegistry:
    """Tests for the simplified registry module."""

    def test_provider_ids_defined(self):
        assert ProviderID.MINIMAX == "minimax"
        assert ProviderID.LLAMA_SERVER == "llama_server"

    def test_provider_info_populated(self):
        assert ProviderID.MINIMAX in PROVIDER_INFO
        assert ProviderID.LLAMA_SERVER in PROVIDER_INFO

    def test_list_providers_returns_all(self):
        infos = list_providers()
        ids = {info.id for info in infos}
        assert ProviderID.MINIMAX in ids
        assert ProviderID.LLAMA_SERVER in ids

    def test_get_provider_info_by_id(self):
        info = get_provider_info(ProviderID.MINIMAX)
        assert info.requires_api_key is True
        assert info.default_model == "MiniMax-M2.7"

    def test_get_provider_info_by_string(self):
        info = get_provider_info("llama_server")
        assert info.requires_api_key is False
        assert info.cost_tier == "free"

    def test_get_provider_info_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider_info("claude")

    def test_get_code_fixer_returns_fixer(self):
        fixer = get_code_fixer()
        assert isinstance(fixer, FallbackChainCodeFixer)

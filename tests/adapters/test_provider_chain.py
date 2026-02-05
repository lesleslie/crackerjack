"""Tests for ProviderChain fallback functionality.

Tests provider fallback chain behavior, availability checking, and
provider performance tracking.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from crackerjack.adapters.ai.base import BaseCodeFixer
from crackerjack.adapters.ai.registry import ProviderChain, ProviderID
from crackerjack.adapters.ai.claude import ClaudeCodeFixer
from crackerjack.adapters.ai.qwen import QwenCodeFixer
from crackerjack.adapters.ai.ollama import OllamaCodeFixer


@pytest.fixture
def mock_claude_provider():
    """Mock Claude provider."""
    provider = MagicMock(spec=ClaudeCodeFixer)
    provider._settings = MagicMock()
    provider._settings.anthropic_api_key = MagicMock()
    provider._settings.anthropic_api_key.get_secret_value.return_value = "sk-ant-key123456789"
    return provider


@pytest.fixture
def mock_qwen_provider():
    """Mock Qwen provider."""
    provider = MagicMock(spec=QwenCodeFixer)
    provider._settings = MagicMock()
    provider._settings.dashscope_api_key = MagicMock()
    provider._settings.dashscope_api_key.get_secret_value.return_value = "sk-dash-key123456789"
    return provider


@pytest.fixture
def mock_ollama_provider():
    """Mock Ollama provider."""
    provider = MagicMock(spec=OllamaCodeFixer)
    provider._settings = MagicMock()
    provider._settings.base_url = "http://localhost:11434"
    return provider


class TestProviderChain:
    """Test ProviderChain fallback behavior."""

    def test_init_with_providers(self):
        """Test ProviderChain initialization with provider list."""
        chain = ProviderChain([ProviderID.CLAUDE, ProviderID.QWEN, ProviderID.OLLAMA])

        assert len(chain.provider_ids) == 3
        assert ProviderID.CLAUDE in chain.provider_ids
        assert ProviderID.QWEN in chain.provider_ids
        assert ProviderID.OLLAMA in chain.provider_ids

    def test_init_with_strings(self):
        """Test ProviderChain initialization with string provider IDs."""
        chain = ProviderChain(["claude", "qwen", "ollama"])

        assert len(chain.provider_ids) == 3
        assert all(isinstance(pid, ProviderID) for pid in chain.provider_ids)

    def test_init_empty_list_raises_error(self):
        """Test that empty provider list raises ValueError."""
        with pytest.raises(ValueError, match="requires at least one provider"):
            ProviderChain([])

    def test_init_invalid_provider_raises_error(self):
        """Test that invalid provider ID raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            ProviderChain(["invalid-provider"])

    @pytest.mark.asyncio
    async def test_get_available_provider_first_available(
        self, mock_claude_provider, mock_qwen_provider
    ):
        """Test that first available provider is returned."""
        chain = ProviderChain([ProviderID.CLAUDE, ProviderID.QWEN])

        # Mock provider creation
        chain._provider_cache = {
            ProviderID.CLAUDE: mock_claude_provider,
            ProviderID.QWEN: mock_qwen_provider,
        }

        provider, provider_id = await chain.get_available_provider()

        assert provider_id == ProviderID.CLAUDE
        assert provider == mock_claude_provider

    @pytest.mark.asyncio
    async def test_get_available_provider_fallback_to_second(
        self, mock_claude_provider, mock_qwen_provider
    ):
        """Test fallback to second provider when first is unavailable."""
        chain = ProviderChain([ProviderID.CLAUDE, ProviderID.QWEN])

        # Mock Claude as unavailable (no API key)
        mock_claude_provider._settings.anthropic_api_key.get_secret_value.return_value = ""
        chain._provider_cache = {
            ProviderID.CLAUDE: mock_claude_provider,
            ProviderID.QWEN: mock_qwen_provider,
        }

        provider, provider_id = await chain.get_available_provider()

        assert provider_id == ProviderID.QWEN
        assert provider == mock_qwen_provider

    @pytest.mark.asyncio
    async def test_get_available_provider_all_unavailable_raises(
        self, mock_claude_provider, mock_qwen_provider
    ):
        """Test that RuntimeError is raised when all providers are unavailable."""
        chain = ProviderChain([ProviderID.CLAUDE, ProviderID.QWEN])

        # Mock both as unavailable
        mock_claude_provider._settings.anthropic_api_key.get_secret_value.return_value = ""
        mock_qwen_provider._settings.dashscope_api_key.get_secret_value.return_value = ""
        chain._provider_cache = {
            ProviderID.CLAUDE: mock_claude_provider,
            ProviderID.QWEN: mock_qwen_provider,
        }

        with pytest.raises(RuntimeError, match="All AI providers unavailable"):
            await chain.get_available_provider()

    def test_get_or_create_provider_caches_instances(self, mock_claude_provider):
        """Test that provider instances are cached."""
        chain = ProviderChain([ProviderID.CLAUDE])

        # First call creates and caches
        with patch.object(
            ProviderChain, "_get_or_create_provider", return_value=mock_claude_provider
        ) as mock_create:
            provider1 = chain._get_or_create_provider(ProviderID.CLAUDE)
            provider2 = chain._get_or_create_provider(ProviderID.CLAUDE)

            # Should only call create once due to caching
            assert mock_create.call_count == 1
            assert provider1 == provider2

    @pytest.mark.asyncio
    async def test_check_provider_availability_no_settings(self):
        """Test availability check for provider without _settings attribute."""
        chain = ProviderChain([ProviderID.CLAUDE])
        provider = MagicMock(spec=BaseCodeFixer)
        # Provider without _settings attribute
        del provider._settings

        available = await chain._check_provider_availability(provider)

        # Should assume available if no settings to check
        assert available is True

    @pytest.mark.asyncio
    async def test_check_provider_availability_claude_valid_key(
        self, mock_claude_provider
    ):
        """Test Claude availability check with valid API key."""
        chain = ProviderChain([ProviderID.CLAUDE])

        available = await chain._check_provider_availability(mock_claude_provider)

        assert available is True

    @pytest.mark.asyncio
    async def test_check_provider_availability_claude_invalid_key(
        self, mock_claude_provider
    ):
        """Test Claude availability check with invalid API key."""
        chain = ProviderChain([ProviderID.CLAUDE])

        # Test with placeholder key
        mock_claude_provider._settings.anthropic_api_key.get_secret_value.return_value = (
            "placeholder-key"
        )

        available = await chain._check_provider_availability(mock_claude_provider)

        assert available is False

    @pytest.mark.asyncio
    async def test_check_provider_availability_claude_short_key(
        self, mock_claude_provider
    ):
        """Test Claude availability check with too-short API key."""
        chain = ProviderChain([ProviderID.CLAUDE])

        mock_claude_provider._settings.anthropic_api_key.get_secret_value.return_value = "short"

        available = await chain._check_provider_availability(mock_claude_provider)

        assert available is False

    @pytest.mark.asyncio
    async def test_check_provider_availability_ollama_server_running(self, mock_ollama_provider):
        """Test Ollama availability check with server running."""
        chain = ProviderChain([ProviderID.OLLAMA])

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__ = AsyncMock(
                return_value=mock_response
            )

            available = await chain._check_provider_availability(mock_ollama_provider)

            assert available is True

    @pytest.mark.asyncio
    async def test_check_provider_availability_ollama_server_not_running(
        self, mock_ollama_provider
    ):
        """Test Ollama availability check with server not running."""
        chain = ProviderChain([ProviderID.OLLAMA])

        with patch("aiohttp.ClientSession") as mock_session:
            # Simulate connection error
            mock_session.return_value.__aenter__.return_value.get.side_effect = Exception(
                "Connection refused"
            )

            available = await chain._check_provider_availability(mock_ollama_provider)

            assert available is False

    def test_track_provider_selection_success(self, mock_claude_provider):
        """Test tracking successful provider selection."""
        chain = ProviderChain([ProviderID.CLAUDE])

        # Mock metrics database
        with patch("crackerjack.adapters.ai.registry.get_metrics") as mock_get_metrics:
            mock_metrics = MagicMock()
            mock_get_metrics.return_value = mock_metrics

            chain._track_provider_selection(ProviderID.CLAUDE, success=True, latency_ms=50)

            # Verify metrics were recorded
            mock_metrics.execute.assert_called_once()
            call_args = mock_metrics.execute.call_args
            assert "provider_performance" in call_args[0][0]
            assert call_args[0][1][1] is True  # success=True
            assert call_args[0][1][2] == 50  # latency_ms

    def test_track_provider_selection_failure(self, mock_claude_provider):
        """Test tracking failed provider selection."""
        chain = ProviderChain([ProviderID.CLAUDE])

        with patch("crackerjack.adapters.ai.registry.get_metrics") as mock_get_metrics:
            mock_metrics = MagicMock()
            mock_get_metrics.return_value = mock_metrics

            chain._track_provider_selection(
                ProviderID.CLAUDE, success=False, latency_ms=100, error="API key missing"
            )

            # Verify metrics were recorded
            mock_metrics.execute.assert_called_once()
            call_args = mock_metrics.execute.call_args
            assert call_args[0][1][1] is False  # success=False
            assert call_args[0][1][3] == "API key missing"  # error message

    def test_track_provider_selection_metrics_failure_doesnt_crash(
        self, mock_claude_provider
    ):
        """Test that metrics tracking failures don't crash the provider chain."""
        chain = ProviderChain([ProviderID.CLAUDE])

        with patch("crackerjack.adapters.ai.registry.get_metrics") as mock_get_metrics:
            # Simulate metrics database failure
            mock_get_metrics.side_effect = Exception("Database connection failed")

            # Should not raise exception
            chain._track_provider_selection(ProviderID.CLAUDE, success=True, latency_ms=50)

    @pytest.mark.asyncio
    async def test_provider_caching_across_calls(self, mock_claude_provider):
        """Test that provider instances are cached across multiple calls."""
        chain = ProviderChain([ProviderID.CLAUDE])

        with patch.object(
            ProviderChain, "_get_or_create_provider", return_value=mock_claude_provider
        ) as mock_create:
            # First call
            await chain.get_available_provider()

            # Create new chain instance to test caching
            chain2 = ProviderChain([ProviderID.CLAUDE])
            chain2._provider_cache = chain._provider_cache

            await chain2.get_available_provider()

            # Should use cached instance
            assert mock_create.call_count == 1

    @pytest.mark.asyncio
    async def test_priority_order_respected(self, mock_claude_provider, mock_qwen_provider):
        """Test that provider priority order is respected."""
        # Qwen first, then Claude (reverse of typical order)
        chain = ProviderChain([ProviderID.QWEN, ProviderID.CLAUDE])

        chain._provider_cache = {
            ProviderID.QWEN: mock_qwen_provider,
            ProviderID.CLAUDE: mock_claude_provider,
        }

        provider, provider_id = await chain.get_available_provider()

        # Should return Qwen (higher priority) even though Claude is also available
        assert provider_id == ProviderID.QWEN

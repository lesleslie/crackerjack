"""Tests for ProviderChain fallback functionality.

Tests provider fallback chain behavior, availability checking, and
provider performance tracking.
"""

import pytest
from pydantic import SecretStr
from unittest.mock import AsyncMock, MagicMock, patch

from crackerjack.adapters.ai.base import BaseCodeFixer
from crackerjack.adapters.ai.registry import ProviderChain, ProviderID, ProviderFactory
from crackerjack.adapters.ai.claude import ClaudeCodeFixer, ClaudeCodeFixerSettings
from crackerjack.adapters.ai.qwen import QwenCodeFixer, QwenCodeFixerSettings
from crackerjack.adapters.ai.ollama import OllamaCodeFixer, OllamaCodeFixerSettings


@pytest.fixture
def mock_claude_provider():
    """Mock Claude provider with properly typed settings."""
    provider = MagicMock(spec=ClaudeCodeFixer)
    # Use model_construct to bypass validation for testing
    provider._settings = ClaudeCodeFixerSettings.model_construct(
        anthropic_api_key=SecretStr("sk-ant-key123456789")
    )
    return provider


@pytest.fixture
def mock_qwen_provider():
    """Mock Qwen provider with properly typed settings."""
    provider = MagicMock(spec=QwenCodeFixer)
    # Use model_construct to bypass validation for testing
    provider._settings = QwenCodeFixerSettings.model_construct(
        qwen_api_key=SecretStr("sk-dash-key123456789")
    )
    return provider


@pytest.fixture
def mock_ollama_provider():
    """Mock Ollama provider with properly typed settings."""
    provider = MagicMock(spec=OllamaCodeFixer)
    # Use model_construct to bypass validation for testing
    provider._settings = OllamaCodeFixerSettings.model_construct(
        base_url="http://localhost:11434"
    )
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
        mock_claude_provider._settings = ClaudeCodeFixerSettings.model_construct(
            anthropic_api_key=SecretStr("")
        )
        chain._provider_cache = {
            ProviderID.CLAUDE: mock_claude_provider,
            ProviderID.QWEN: mock_qwen_provider,
        }

        # Create a mock that returns False for Claude, True for Qwen
        async def mock_availability(provider):
            if provider == mock_claude_provider:
                return False
            if provider == mock_qwen_provider:
                return True
            return False

        with patch.object(chain, "_check_provider_availability", side_effect=mock_availability):
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
        mock_claude_provider._settings = ClaudeCodeFixerSettings.model_construct(
            anthropic_api_key=SecretStr("")
        )
        mock_qwen_provider._settings = QwenCodeFixerSettings.model_construct(
            qwen_api_key=SecretStr("")
        )
        chain._provider_cache = {
            ProviderID.CLAUDE: mock_claude_provider,
            ProviderID.QWEN: mock_qwen_provider,
        }

        with patch.object(chain, "_check_provider_availability", return_value=False):
            with pytest.raises(RuntimeError, match="All AI providers unavailable"):
                await chain.get_available_provider()

    def test_get_or_create_provider_caches_instances(self, mock_claude_provider):
        """Test that provider instances are cached."""
        chain = ProviderChain([ProviderID.CLAUDE])

        # Mock the factory method, not the instance method
        with patch.object(
            ProviderFactory, "create_provider", return_value=mock_claude_provider
        ) as mock_create:
            # Call _get_or_create_provider twice
            provider1 = chain._get_or_create_provider(ProviderID.CLAUDE)
            provider2 = chain._get_or_create_provider(ProviderID.CLAUDE)

            # Should only call factory once due to caching
            assert mock_create.call_count == 1
            assert provider1 == provider2
            assert provider1 is mock_claude_provider

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
        mock_claude_provider._settings = ClaudeCodeFixerSettings.model_construct(
            anthropic_api_key=SecretStr("placeholder-key")
        )

        available = await chain._check_provider_availability(mock_claude_provider)

        assert available is False

    @pytest.mark.asyncio
    async def test_check_provider_availability_claude_short_key(
        self, mock_claude_provider
    ):
        """Test Claude availability check with too-short API key."""
        chain = ProviderChain([ProviderID.CLAUDE])

        mock_claude_provider._settings = ClaudeCodeFixerSettings.model_construct(
            anthropic_api_key=SecretStr("short")
        )

        available = await chain._check_provider_availability(mock_claude_provider)

        assert available is False

    @pytest.mark.asyncio
    async def test_check_provider_availability_ollama_server_running(self, mock_ollama_provider):
        """Test Ollama availability check with server running."""
        chain = ProviderChain([ProviderID.OLLAMA])

        # Import aiohttp here so we can patch it
        import aiohttp

        # Create properly configured mocks
        mock_response = AsyncMock()
        mock_response.status = 200

        mock_get_resp = AsyncMock()
        mock_get_resp.__aenter__.return_value = mock_response

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.get = MagicMock(return_value=mock_get_resp)

        # Patch ClientSession and ClientTimeout
        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            with patch.object(aiohttp, "ClientTimeout", lambda total: None):
                available = await chain._check_provider_availability(mock_ollama_provider)

        assert available is True

    @pytest.mark.asyncio
    async def test_check_provider_availability_ollama_server_not_running(
        self, mock_ollama_provider
    ):
        """Test Ollama availability check with server not running."""
        chain = ProviderChain([ProviderID.OLLAMA])

        # Import aiohttp here so we can patch it
        import aiohttp

        # Create mock session that raises exception
        async def mock_get_with_error(*args, **kwargs):
            raise Exception("Connection refused")

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.get = mock_get_with_error

        # Patch ClientSession and ClientTimeout
        with patch.object(aiohttp, "ClientSession", return_value=mock_session):
            with patch.object(aiohttp, "ClientTimeout", lambda total: None):
                available = await chain._check_provider_availability(mock_ollama_provider)

        assert available is False

    def test_track_provider_selection_success(self, mock_claude_provider):
        """Test tracking successful provider selection."""
        chain = ProviderChain([ProviderID.CLAUDE])

        # Mock metrics database - patch from the metrics module
        with patch("crackerjack.services.metrics.get_metrics") as mock_get_metrics:
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

        with patch("crackerjack.services.metrics.get_metrics") as mock_get_metrics:
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

        with patch("crackerjack.services.metrics.get_metrics") as mock_get_metrics:
            # Simulate metrics database failure
            mock_get_metrics.side_effect = Exception("Database connection failed")

            # Should not raise exception
            chain._track_provider_selection(ProviderID.CLAUDE, success=True, latency_ms=50)

    @pytest.mark.asyncio
    async def test_provider_caching_across_calls(self, mock_claude_provider):
        """Test that provider instances are cached across multiple calls."""
        chain = ProviderChain([ProviderID.CLAUDE])

        # Mock the factory to return our provider and track calls
        with patch.object(
            ProviderFactory, "create_provider", return_value=mock_claude_provider
        ) as mock_create:
            # First call - should create provider
            provider1, _ = await chain.get_available_provider()
            assert mock_create.call_count == 1

            # Second call on same chain - should use cached provider
            provider2, _ = await chain.get_available_provider()
            assert mock_create.call_count == 1  # Still 1, not 2

            # Verify both calls returned the same provider instance
            assert provider1 is provider2

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

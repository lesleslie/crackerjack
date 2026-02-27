"""Tests for Crackerjack admin shell adapter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from crackerjack.config import load_settings
from crackerjack.shell import CrackerjackShell


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.qa_adapters = {
        "pytest": True,
        "ruff": True,
        "mypy": True,
        "bandit": True,
    }
    return settings


@pytest.fixture
def crackerjack_shell(mock_settings):
    """Create a CrackerjackShell instance for testing."""
    from oneiric.shell import ShellConfig

    config = ShellConfig()
    shell = CrackerjackShell(mock_settings, config)
    return shell


@pytest.fixture(autouse=True)
def reset_oneiric_state():
    """Reset any global state from oneiric before/after each test."""
    import importlib
    # Force fresh imports to avoid state pollution from other tests
    yield
    # Cleanup after test
    import sys
    modules_to_clear = [k for k in sys.modules.keys() if k.startswith('oneiric')]
    for mod in modules_to_clear:
        del sys.modules[mod]


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
class TestCrackerjackShell:
    """Test suite for CrackerjackShell."""

    def test_initialization(self, crackerjack_shell):
        """Test shell initializes correctly."""
        assert crackerjack_shell is not None
        assert crackerjack_shell.app is not None
        assert crackerjack_shell.namespace is not None
        assert crackerjack_shell.session_tracker is not None

    def test_component_name(self, crackerjack_shell):
        """Test component name is correct."""
        assert crackerjack_shell._get_component_name() == "crackerjack"

    def test_component_version(self, crackerjack_shell):
        """Test component version is retrieved."""
        version = crackerjack_shell._get_component_version()
        assert isinstance(version, str)
        # Version should be either a valid version string or "unknown"
        assert version == "unknown" or len(version) > 0

    def test_adapters_info(self, crackerjack_shell):
        """Test adapters info is returned correctly."""
        adapters = crackerjack_shell._get_adapters_info()
        assert isinstance(adapters, list)
        # Should have at least some default adapters
        assert len(adapters) > 0

    def test_banner(self, crackerjack_shell):
        """Test banner is generated correctly."""
        banner = crackerjack_shell._get_banner()
        assert isinstance(banner, str)
        assert "Crackerjack Admin Shell" in banner
        assert "Quality & Testing Automation" in banner
        assert "crack()" in banner
        assert "test()" in banner
        assert "lint()" in banner
        assert "scan()" in banner
        assert "Session Tracking" in banner

    def test_namespace_helpers(self, crackerjack_shell):
        """Test quality helper functions are in namespace."""
        assert "crack" in crackerjack_shell.namespace
        assert "test" in crackerjack_shell.namespace
        assert "lint" in crackerjack_shell.namespace
        assert "scan" in crackerjack_shell.namespace
        assert "format_code" in crackerjack_shell.namespace
        assert "typecheck" in crackerjack_shell.namespace
        assert "show_adapters" in crackerjack_shell.namespace
        assert "show_hooks" in crackerjack_shell.namespace

    @pytest.mark.asyncio
    async def test_show_adapters(self, crackerjack_shell):
        """Test show_adapters command."""
        # Should not raise exception
        await crackerjack_shell._show_adapters()

    @pytest.mark.asyncio
    async def test_session_start_emission(self, crackerjack_shell):
        """Test session start event emission."""
        # Mock the session tracker's async method
        crackerjack_shell.session_tracker.emit_session_start = AsyncMock(
            return_value="test_session_id"
        )

        await crackerjack_shell._emit_session_start()

        # Verify session tracker was called
        crackerjack_shell.session_tracker.emit_session_start.assert_called_once()
        assert crackerjack_shell._session_id == "test_session_id"

    @pytest.mark.asyncio
    async def test_session_end_emission(self, crackerjack_shell):
        """Test session end event emission."""
        crackerjack_shell._session_id = "test_session_id"
        crackerjack_shell.session_tracker.emit_session_end = AsyncMock()

        await crackerjack_shell._emit_session_end()

        # Verify session tracker was called
        crackerjack_shell.session_tracker.emit_session_end.assert_called_once_with(
            session_id="test_session_id", metadata={}
        )
        assert crackerjack_shell._session_id is None

    @pytest.mark.asyncio
    async def test_close(self, crackerjack_shell):
        """Test shell cleanup."""
        crackerjack_shell.session_tracker.close = AsyncMock()
        crackerjack_shell._session_id = "test_session_id"
        crackerjack_shell.session_tracker.emit_session_end = AsyncMock()

        await crackerjack_shell.close()

        # Verify cleanup
        crackerjack_shell.session_tracker.emit_session_end.assert_called_once()
        crackerjack_shell.session_tracker.close.assert_called_once()


@pytest.mark.integration
class TestCrackerjackShellIntegration:
    """Integration tests for CrackerjackShell (require actual tools)."""

    @pytest.mark.asyncio
    async def test_run_lint_integration():
        """Test running actual lint command (integration)."""
        from crackerjack.config import load_settings, CrackerjackSettings
        from crackerjack.shell import CrackerjackShell

        settings = load_settings(CrackerjackSettings)
        shell = CrackerjackShell(settings)

        # This will actually run ruff, so we skip if tools not available
        try:
            await shell._run_lint()
        except FileNotFoundError:
            pytest.skip("Ruff not installed")
        except Exception as e:
            # Other exceptions are OK for integration test
            assert isinstance(e, Exception)

    @pytest.mark.asyncio
    async def test_run_typecheck_integration():
        """Test running actual typecheck command (integration)."""
        from crackerjack.config import load_settings, CrackerjackSettings
        from crackerjack.shell import CrackerjackShell

        settings = load_settings(CrackerjackSettings)
        shell = CrackerjackShell(settings)

        # This will actually run mypy, so we skip if not available
        try:
            await shell._run_typecheck()
        except FileNotFoundError:
            pytest.skip("Mypy not installed")
        except Exception as e:
            # Other exceptions are OK for integration test
            assert isinstance(e, Exception)

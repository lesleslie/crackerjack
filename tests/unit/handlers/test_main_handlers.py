"""Tests for CLI main handlers."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.cli.handlers.main_handlers import (
    setup_ai_agent_env,
    handle_interactive_mode,
    handle_standard_mode,
    handle_config_updates,
    _handle_check_updates,
    _handle_apply_updates,
    _handle_diff_config,
    _handle_refresh_cache,
    _display_available_updates,
    _get_configs_needing_update,
    _apply_config_updates_batch,
    _report_update_results,
)


class TestSetupAIAgentEnv:
    """Tests for setup_ai_agent_env function."""

    def setup_method(self):
        """Clean up environment variables before each test."""
        for var in ("AI_AGENT", "CRACKERJACK_DEBUG", "AI_AGENT_DEBUG", "AI_AGENT_VERBOSE"):
            os.environ.pop(var, None)

    def teardown_method(self):
        """Clean up environment variables after each test."""
        for var in ("AI_AGENT", "CRACKERJACK_DEBUG", "AI_AGENT_DEBUG", "AI_AGENT_VERBOSE"):
            os.environ.pop(var, None)

    @patch("crackerjack.services.logging.setup_structured_logging")
    def test_setup_ai_agent_enabled(self, mock_setup_logging):
        """Test setup with AI agent enabled."""
        console = MagicMock()

        setup_ai_agent_env(
            ai_agent=True,
            debug_mode=False,
            console=console,
        )

        # Verify environment variables are set
        assert os.environ.get("AI_AGENT") == "1"
        # setup_structured_logging is only called when debug_mode=True
        mock_setup_logging.assert_not_called()

    @patch("crackerjack.services.logging.setup_structured_logging")
    def test_setup_debug_mode(self, mock_setup_logging):
        """Test setup with debug mode enabled."""
        console = MagicMock()

        setup_ai_agent_env(
            ai_agent=False,
            debug_mode=True,
            console=console,
        )

        # Verify debug environment variables
        assert os.environ.get("CRACKERJACK_DEBUG") == "1"
        mock_setup_logging.assert_called_once_with(level="DEBUG", json_output=True)

    @patch("crackerjack.services.logging.setup_structured_logging")
    def test_setup_ai_agent_with_debug(self, mock_setup_logging):
        """Test setup with both AI agent and debug mode."""
        console = MagicMock()

        setup_ai_agent_env(
            ai_agent=True,
            debug_mode=True,
            console=console,
        )

        assert os.environ.get("AI_AGENT") == "1"
        assert os.environ.get("AI_AGENT_DEBUG") == "1"
        assert os.environ.get("AI_AGENT_VERBOSE") == "1"
        mock_setup_logging.assert_called_once_with(level="DEBUG", json_output=True)

    @patch("crackerjack.services.logging.setup_structured_logging")
    def test_setup_default_console(self, mock_setup_logging):
        """Test setup with default console."""
        # When debug_mode=False, setup_structured_logging is not called
        setup_ai_agent_env(ai_agent=False, debug_mode=False, console=None)
        mock_setup_logging.assert_not_called()


class TestHandleInteractiveMode:
    """Tests for handle_interactive_mode function."""

    @patch("crackerjack.cli.interactive.launch_interactive_cli")
    @patch("crackerjack.cli.version.get_package_version")
    def test_handle_interactive_mode(self, mock_get_version, mock_launch):
        """Test interactive mode handler."""
        from crackerjack.cli.options import Options

        mock_get_version.return_value = "1.0.0"
        mock_options = MagicMock(spec=Options)

        handle_interactive_mode(mock_options)

        mock_get_version.assert_called_once()
        mock_launch.assert_called_once()


class TestHandleStandardMode:
    """Tests for handle_standard_mode function."""

    @patch("crackerjack.cli.facade.CrackerjackCLIFacade")
    @patch("crackerjack.config.load_settings")
    def test_handle_standard_mode_basic(self, mock_load_settings, mock_facade_class):
        """Test standard mode handler."""
        from crackerjack.cli.options import Options

        mock_settings = MagicMock()
        mock_settings.documentation.auto_cleanup_on_publish = False
        mock_load_settings.return_value = mock_settings

        mock_facade = MagicMock()
        mock_facade_class.return_value = mock_facade

        mock_options = MagicMock(spec=Options)
        mock_options.publish = None
        mock_options.cleanup_docs = False

        handle_standard_mode(mock_options)

        mock_facade.process.assert_called_once()

    @patch("crackerjack.cli.facade.CrackerjackCLIFacade")
    @patch("crackerjack.config.load_settings")
    def test_handle_standard_mode_with_publish(
        self,
        mock_load_settings,
        mock_facade_class,
    ):
        """Test standard mode with publish option."""
        from crackerjack.cli.options import Options

        mock_settings = MagicMock()
        mock_settings.documentation.auto_cleanup_on_publish = True
        mock_load_settings.return_value = mock_settings

        mock_facade = MagicMock()
        mock_facade_class.return_value = mock_facade

        mock_options = MagicMock(spec=Options)
        mock_options.publish = "patch"
        mock_options.cleanup_docs = False

        handle_standard_mode(mock_options)

        # Should enable cleanup_docs automatically
        assert mock_options.cleanup_docs is True


class TestHandleConfigUpdates:
    """Tests for config update handlers."""

    def test_handle_check_updates_no_updates(self):
        """Test check updates when no updates available."""
        mock_service = MagicMock()
        mock_service.check_updates.return_value = {}

        console = MagicMock()
        pkg_path = Path("/tmp/test")

        _handle_check_updates(mock_service, pkg_path, console)

        console.print.assert_called()
        # Should print message about no updates

    def test_handle_check_updates_with_updates(self):
        """Test check updates when updates are available."""
        from crackerjack.services.config_template import ConfigUpdateInfo

        mock_service = MagicMock()
        mock_service.check_updates.return_value = {
            "pyproject": ConfigUpdateInfo(
                config_type="pyproject",
                current_version="1.0",
                latest_version="2.0",
                needs_update=True,
            ),
        }

        console = MagicMock()
        pkg_path = Path("/tmp/test")

        _handle_check_updates(mock_service, pkg_path, console)

        # Should display available updates
        assert console.print.call_count > 0

    def test_handle_apply_updates(self):
        """Test applying configuration updates."""
        from crackerjack.services.config_template import ConfigUpdateInfo

        mock_service = MagicMock()
        mock_service.check_updates.return_value = {
            "pyproject": ConfigUpdateInfo(
                config_type="pyproject",
                current_version="1.0",
                latest_version="2.0",
                needs_update=True,
            ),
        }
        mock_service.apply_update.return_value = True

        console = MagicMock()
        pkg_path = Path("/tmp/test")

        _handle_apply_updates(
            mock_service,
            pkg_path,
            interactive=False,
            console=console,
        )

        mock_service.apply_update.assert_called_once()

    def test_handle_diff_config(self):
        """Test showing config diff."""
        mock_service = MagicMock()
        mock_service._generate_diff_preview.return_value = "Diff content here"

        console = MagicMock()
        pkg_path = Path("/tmp/test")

        _handle_diff_config(mock_service, pkg_path, "pyproject", console)

        mock_service._generate_diff_preview.assert_called_once_with(
            "pyproject",
            pkg_path,
        )
        console.print.assert_called()

    def test_handle_refresh_cache(self):
        """Test refreshing cache."""
        mock_service = MagicMock()

        console = MagicMock()
        pkg_path = Path("/tmp/test")

        _handle_refresh_cache(mock_service, pkg_path, console)

        mock_service._invalidate_cache.assert_called_once_with(pkg_path)
        console.print.assert_called()


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_display_available_updates(self):
        """Test displaying available updates."""
        from crackerjack.services.config_template import ConfigUpdateInfo

        console = MagicMock()
        updates = {
            "pyproject": ConfigUpdateInfo(
                config_type="pyproject",
                current_version="1.0",
                latest_version="2.0",
                needs_update=True,
            ),
            "ruff": ConfigUpdateInfo(
                config_type="ruff",
                current_version="1.5",
                latest_version="1.6",
                needs_update=False,
            ),
        }

        _display_available_updates(updates, console)

        # Should only display updates that need update
        assert console.print.call_count > 0

    def test_get_configs_needing_update(self):
        """Test filtering configs that need updates."""
        from crackerjack.services.config_template import ConfigUpdateInfo

        updates = {
            "config1": ConfigUpdateInfo(
                config_type="config1",
                current_version="1.0",
                latest_version="2.0",
                needs_update=True,
            ),
            "config2": ConfigUpdateInfo(
                config_type="config2",
                current_version="1.0",
                latest_version="1.0",
                needs_update=False,
            ),
            "config3": ConfigUpdateInfo(
                config_type="config3",
                current_version="1.5",
                latest_version="2.0",
                needs_update=True,
            ),
        }

        result = _get_configs_needing_update(updates)

        assert len(result) == 2
        assert "config1" in result
        assert "config3" in result
        assert "config2" not in result

    def test_apply_config_updates_batch(self):
        """Test batch applying config updates."""
        mock_service = MagicMock()
        mock_service.apply_update.side_effect = [True, False, True]

        console = MagicMock()
        pkg_path = Path("/tmp/test")
        configs = ["config1", "config2", "config3"]

        result = _apply_config_updates_batch(
            mock_service,
            configs,
            pkg_path,
            interactive=False,
            console=console,
        )

        assert result == 2  # 2 out of 3 succeeded
        assert mock_service.apply_update.call_count == 3

    def test_report_update_results_all_success(self):
        """Test reporting update results when all succeed."""
        console = MagicMock()

        _report_update_results(success_count=3, total_count=3, console=console)

        console.print.assert_called()
        # Should contain success message

    def test_report_update_results_partial_success(self):
        """Test reporting update results with partial success."""
        console = MagicMock()

        _report_update_results(success_count=2, total_count=3, console=console)

        console.print.assert_called()
        # Should contain partial success message

    def test_report_update_results_all_failed(self):
        """Test reporting update results when all fail."""
        console = MagicMock()

        _report_update_results(success_count=0, total_count=3, console=console)

        console.print.assert_called()

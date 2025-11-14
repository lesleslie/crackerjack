"""Unit tests for CLI command handlers.

Tests handler functions for MCP server, monitoring, watchdog,
WebSocket server, and AI agent setup.
"""

import asyncio
import os
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.cli.handlers import (
    handle_dashboard_mode,
    handle_enhanced_monitor_mode,
    handle_mcp_server,
    handle_monitor_mode,
    handle_restart_mcp_server,
    handle_restart_websocket_server,
    handle_start_websocket_server,
    handle_stop_mcp_server,
    handle_stop_websocket_server,
    handle_unified_dashboard_mode,
    handle_watchdog_mode,
    setup_ai_agent_env,
)


@pytest.mark.unit
class TestSetupAIAgentEnv:
    """Test AI agent environment setup."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    def test_setup_ai_agent_env_disabled(self, mock_console):
        """Test setup with AI agent disabled."""
        setup_ai_agent_env(ai_agent=False, debug_mode=False, console=mock_console)

        # Should not set AI_AGENT env var
        assert os.environ.get("AI_AGENT") != "1"

    def test_setup_ai_agent_env_enabled(self, mock_console):
        """Test setup with AI agent enabled."""
        with patch("crackerjack.cli.handlers.setup_structured_logging"):
            setup_ai_agent_env(ai_agent=True, debug_mode=False, console=mock_console)

            assert os.environ.get("AI_AGENT") == "1"

        # Cleanup
        os.environ.pop("AI_AGENT", None)

    def test_setup_ai_agent_env_debug_mode(self, mock_console):
        """Test setup with debug mode enabled."""
        with patch("crackerjack.cli.handlers.setup_structured_logging"):
            setup_ai_agent_env(ai_agent=False, debug_mode=True, console=mock_console)

            assert os.environ.get("CRACKERJACK_DEBUG") == "1"
            assert os.environ.get("AI_AGENT_DEBUG") == "1"
            assert os.environ.get("AI_AGENT_VERBOSE") == "1"
            mock_console.print.assert_called()

        # Cleanup
        os.environ.pop("CRACKERJACK_DEBUG", None)
        os.environ.pop("AI_AGENT_DEBUG", None)
        os.environ.pop("AI_AGENT_VERBOSE", None)

    def test_setup_ai_agent_env_both_enabled(self, mock_console):
        """Test setup with both AI agent and debug mode."""
        with patch("crackerjack.cli.handlers.setup_structured_logging"):
            setup_ai_agent_env(ai_agent=True, debug_mode=True, console=mock_console)

            assert os.environ.get("AI_AGENT") == "1"
            assert os.environ.get("CRACKERJACK_DEBUG") == "1"
            assert os.environ.get("AI_AGENT_DEBUG") == "1"
            assert os.environ.get("AI_AGENT_VERBOSE") == "1"
            mock_console.print.assert_called()

        # Cleanup
        for var in ["AI_AGENT", "CRACKERJACK_DEBUG", "AI_AGENT_DEBUG", "AI_AGENT_VERBOSE"]:
            os.environ.pop(var, None)

    def test_setup_structured_logging_called(self, mock_console):
        """Test structured logging is set up when needed."""
        with patch("crackerjack.cli.handlers.setup_structured_logging") as mock_logging:
            setup_ai_agent_env(ai_agent=True, debug_mode=False, console=mock_console)

            mock_logging.assert_called_once_with(level="DEBUG", json_output=True)

        # Cleanup
        os.environ.pop("AI_AGENT", None)


@pytest.mark.unit
class TestHandleMCPServer:
    """Test MCP server handler."""

    def test_handle_mcp_server_without_port(self):
        """Test starting MCP server without port."""
        with patch("crackerjack.cli.handlers.start_mcp_main") as mock_start:
            handle_mcp_server()

            mock_start.assert_called_once()
            args = mock_start.call_args
            assert len(args[0]) == 1  # Only project_path

    def test_handle_mcp_server_with_port(self):
        """Test starting MCP server with port."""
        with patch("crackerjack.cli.handlers.start_mcp_main") as mock_start:
            handle_mcp_server(websocket_port=8080)

            mock_start.assert_called_once()
            args = mock_start.call_args
            assert len(args[0]) == 2  # project_path and port


@pytest.mark.unit
class TestHandleMonitorMode:
    """Test monitor mode handler."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    def test_handle_monitor_mode_default(self, mock_console):
        """Test monitor mode with default settings."""
        with patch("crackerjack.cli.handlers.run_progress_monitor") as mock_monitor:
            mock_monitor.return_value = asyncio.Future()
            mock_monitor.return_value.set_result(None)

            with patch("crackerjack.cli.handlers.asyncio.run") as mock_run:
                handle_monitor_mode(dev_mode=False, console=mock_console)

                mock_console.print.assert_called()
                mock_run.assert_called_once()

    def test_handle_monitor_mode_keyboard_interrupt(self, mock_console):
        """Test monitor mode handling keyboard interrupt."""
        with patch("crackerjack.cli.handlers.asyncio.run") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            handle_monitor_mode(dev_mode=False, console=mock_console)

            # Should print stop message
            assert mock_console.print.called

    def test_handle_monitor_mode_dev_mode(self, mock_console):
        """Test monitor mode with dev mode enabled."""
        with patch("crackerjack.cli.handlers.run_progress_monitor") as mock_monitor:
            mock_monitor.return_value = asyncio.Future()
            mock_monitor.return_value.set_result(None)

            with patch("crackerjack.cli.handlers.asyncio.run"):
                handle_monitor_mode(dev_mode=True, console=mock_console)

                mock_console.print.assert_called()


@pytest.mark.unit
class TestHandleEnhancedMonitorMode:
    """Test enhanced monitor mode handler."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    def test_handle_enhanced_monitor_mode(self, mock_console):
        """Test enhanced monitor mode."""
        with patch(
            "crackerjack.cli.handlers.run_enhanced_progress_monitor"
        ) as mock_monitor:
            mock_monitor.return_value = asyncio.Future()
            mock_monitor.return_value.set_result(None)

            with patch("crackerjack.cli.handlers.asyncio.run"):
                handle_enhanced_monitor_mode(dev_mode=False, console=mock_console)

                mock_console.print.assert_called()

    def test_handle_enhanced_monitor_mode_keyboard_interrupt(self, mock_console):
        """Test enhanced monitor handling keyboard interrupt."""
        with patch("crackerjack.cli.handlers.asyncio.run") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            handle_enhanced_monitor_mode(dev_mode=False, console=mock_console)

            assert mock_console.print.called


@pytest.mark.unit
class TestHandleDashboardMode:
    """Test dashboard mode handler."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    def test_handle_dashboard_mode(self, mock_console):
        """Test dashboard mode."""
        with patch("crackerjack.cli.handlers.run_dashboard") as mock_dashboard:
            handle_dashboard_mode(dev_mode=False, console=mock_console)

            mock_dashboard.assert_called_once()
            mock_console.print.assert_called()

    def test_handle_dashboard_mode_keyboard_interrupt(self, mock_console):
        """Test dashboard handling keyboard interrupt."""
        with patch("crackerjack.cli.handlers.run_dashboard") as mock_dashboard:
            mock_dashboard.side_effect = KeyboardInterrupt()

            handle_dashboard_mode(dev_mode=False, console=mock_console)

            assert mock_console.print.called


@pytest.mark.unit
class TestHandleUnifiedDashboardMode:
    """Test unified dashboard mode handler."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    def test_handle_unified_dashboard_mode_default(self, mock_console):
        """Test unified dashboard with default port."""
        with patch(
            "crackerjack.cli.handlers.CrackerjackMonitoringServer"
        ) as mock_server_class:
            mock_server = Mock()
            mock_server.start_monitoring = AsyncMock()
            mock_server_class.return_value = mock_server

            with patch("crackerjack.cli.handlers.asyncio.run"):
                handle_unified_dashboard_mode(console=mock_console)

                mock_console.print.assert_called()
                assert "8675" in str(mock_console.print.call_args)

    def test_handle_unified_dashboard_mode_custom_port(self, mock_console):
        """Test unified dashboard with custom port."""
        with patch(
            "crackerjack.cli.handlers.CrackerjackMonitoringServer"
        ) as mock_server_class:
            mock_server = Mock()
            mock_server.start_monitoring = AsyncMock()
            mock_server_class.return_value = mock_server

            with patch("crackerjack.cli.handlers.asyncio.run"):
                handle_unified_dashboard_mode(port=9000, console=mock_console)

                mock_console.print.assert_called()
                assert "9000" in str(mock_console.print.call_args)

    def test_handle_unified_dashboard_mode_keyboard_interrupt(self, mock_console):
        """Test unified dashboard handling keyboard interrupt."""
        with patch("crackerjack.cli.handlers.asyncio.run") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            handle_unified_dashboard_mode(console=mock_console)

            assert mock_console.print.called

    def test_handle_unified_dashboard_mode_error(self, mock_console):
        """Test unified dashboard handling error."""
        with patch("crackerjack.cli.handlers.asyncio.run") as mock_run:
            mock_run.side_effect = Exception("Dashboard error")

            handle_unified_dashboard_mode(console=mock_console)

            # Should print error message
            assert mock_console.print.called


@pytest.mark.unit
class TestHandleWatchdogMode:
    """Test watchdog mode handler."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    def test_handle_watchdog_mode(self, mock_console):
        """Test watchdog mode."""
        with patch("crackerjack.cli.handlers.start_watchdog") as mock_watchdog:
            mock_watchdog.return_value = asyncio.Future()
            mock_watchdog.return_value.set_result(None)

            with patch("crackerjack.cli.handlers.asyncio.run"):
                handle_watchdog_mode(console=mock_console)

    def test_handle_watchdog_mode_keyboard_interrupt(self, mock_console):
        """Test watchdog handling keyboard interrupt."""
        with patch("crackerjack.cli.handlers.asyncio.run") as mock_run:
            mock_run.side_effect = KeyboardInterrupt()

            handle_watchdog_mode(console=mock_console)

            assert mock_console.print.called


@pytest.mark.unit
class TestHandleWebSocketServer:
    """Test WebSocket server handlers."""

    def test_handle_start_websocket_server_default(self):
        """Test starting WebSocket server with default port."""
        with patch(
            "crackerjack.cli.handlers.handle_websocket_server_command"
        ) as mock_command:
            handle_start_websocket_server()

            mock_command.assert_called_once_with(start=True, port=8675)

    def test_handle_start_websocket_server_custom_port(self):
        """Test starting WebSocket server with custom port."""
        with patch(
            "crackerjack.cli.handlers.handle_websocket_server_command"
        ) as mock_command:
            handle_start_websocket_server(port=9000)

            mock_command.assert_called_once_with(start=True, port=9000)

    def test_handle_stop_websocket_server(self):
        """Test stopping WebSocket server."""
        with patch(
            "crackerjack.cli.handlers.handle_websocket_server_command"
        ) as mock_command:
            handle_stop_websocket_server()

            mock_command.assert_called_once_with(stop=True)

    def test_handle_restart_websocket_server_default(self):
        """Test restarting WebSocket server with default port."""
        with patch(
            "crackerjack.cli.handlers.handle_websocket_server_command"
        ) as mock_command:
            handle_restart_websocket_server()

            mock_command.assert_called_once_with(restart=True, port=8675)

    def test_handle_restart_websocket_server_custom_port(self):
        """Test restarting WebSocket server with custom port."""
        with patch(
            "crackerjack.cli.handlers.handle_websocket_server_command"
        ) as mock_command:
            handle_restart_websocket_server(port=9000)

            mock_command.assert_called_once_with(restart=True, port=9000)


@pytest.mark.unit
class TestHandleStopMCPServer:
    """Test stop MCP server handler."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    def test_handle_stop_mcp_server_success(self, mock_console):
        """Test stopping MCP server successfully."""
        with patch("crackerjack.cli.handlers.list_server_status") as mock_list:
            with patch(
                "crackerjack.cli.handlers.stop_all_servers", return_value=True
            ) as mock_stop:
                handle_stop_mcp_server(console=mock_console)

                mock_list.assert_called_once_with(mock_console)
                mock_stop.assert_called_once_with(mock_console)
                mock_console.print.assert_called()

    def test_handle_stop_mcp_server_failure(self, mock_console):
        """Test stopping MCP server with failure."""
        with patch("crackerjack.cli.handlers.list_server_status"):
            with patch(
                "crackerjack.cli.handlers.stop_all_servers", return_value=False
            ):
                with pytest.raises(SystemExit) as exc_info:
                    handle_stop_mcp_server(console=mock_console)

                assert exc_info.value.code == 1


@pytest.mark.unit
class TestHandleRestartMCPServer:
    """Test restart MCP server handler."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    def test_handle_restart_mcp_server_success(self, mock_console):
        """Test restarting MCP server successfully."""
        with patch(
            "crackerjack.cli.handlers.restart_mcp_server", return_value=True
        ) as mock_restart:
            handle_restart_mcp_server(console=mock_console)

            mock_restart.assert_called_once()
            mock_console.print.assert_called()

    def test_handle_restart_mcp_server_with_port(self, mock_console):
        """Test restarting MCP server with custom port."""
        with patch(
            "crackerjack.cli.handlers.restart_mcp_server", return_value=True
        ) as mock_restart:
            handle_restart_mcp_server(websocket_port=9000, console=mock_console)

            mock_restart.assert_called_once_with(9000, mock_console)

    def test_handle_restart_mcp_server_failure(self, mock_console):
        """Test restarting MCP server with failure."""
        with patch(
            "crackerjack.cli.handlers.restart_mcp_server", return_value=False
        ):
            # Should complete without error (no SystemExit on False return)
            handle_restart_mcp_server(console=mock_console)


@pytest.mark.unit
class TestHandlersIntegration:
    """Test handler integration scenarios."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock()

    def test_setup_ai_then_start_server(self, mock_console):
        """Test setting up AI agent then starting server."""
        # Setup AI agent
        with patch("crackerjack.cli.handlers.setup_structured_logging"):
            setup_ai_agent_env(ai_agent=True, debug_mode=True, console=mock_console)

            assert os.environ.get("AI_AGENT") == "1"

        # Start MCP server
        with patch("crackerjack.cli.handlers.start_mcp_main"):
            handle_mcp_server()

        # Cleanup
        os.environ.pop("AI_AGENT", None)
        os.environ.pop("CRACKERJACK_DEBUG", None)
        os.environ.pop("AI_AGENT_DEBUG", None)
        os.environ.pop("AI_AGENT_VERBOSE", None)

    def test_monitor_modes_sequence(self, mock_console):
        """Test running different monitor modes."""
        with patch("crackerjack.cli.handlers.asyncio.run"):
            with patch("crackerjack.cli.handlers.run_progress_monitor"):
                handle_monitor_mode(console=mock_console)

            with patch("crackerjack.cli.handlers.run_enhanced_progress_monitor"):
                handle_enhanced_monitor_mode(console=mock_console)

            with patch("crackerjack.cli.handlers.run_dashboard"):
                handle_dashboard_mode(console=mock_console)

    def test_websocket_server_lifecycle(self):
        """Test WebSocket server start/stop/restart lifecycle."""
        with patch("crackerjack.cli.handlers.handle_websocket_server_command") as mock:
            # Start
            handle_start_websocket_server()
            assert mock.call_args[1]["start"] is True

            # Stop
            handle_stop_websocket_server()
            assert mock.call_args[1]["stop"] is True

            # Restart
            handle_restart_websocket_server()
            assert mock.call_args[1]["restart"] is True

    def test_mcp_server_lifecycle(self, mock_console):
        """Test MCP server start/stop/restart lifecycle."""
        # Start
        with patch("crackerjack.cli.handlers.start_mcp_main"):
            handle_mcp_server()

        # Stop
        with patch("crackerjack.cli.handlers.list_server_status"):
            with patch("crackerjack.cli.handlers.stop_all_servers", return_value=True):
                handle_stop_mcp_server(console=mock_console)

        # Restart
        with patch("crackerjack.cli.handlers.restart_mcp_server", return_value=True):
            handle_restart_mcp_server(console=mock_console)

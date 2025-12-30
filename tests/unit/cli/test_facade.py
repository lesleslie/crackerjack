"""Unit tests for CrackerjackCLIFacade and command validation.

Tests CLI facade, command validation, special mode handling,
and workflow orchestration integration.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.cli.facade import (
    VALID_COMMANDS,
    CrackerjackCLIFacade,
    create_crackerjack_runner,
    validate_command,
)


@pytest.mark.unit
class TestValidateCommand:
    """Test command validation function."""

    def test_validate_valid_command_no_args(self):
        """Test validating valid command without args."""
        command, args = validate_command("test", "")

        assert command == "test"
        assert args == []

    def test_validate_valid_command_with_args(self):
        """Test validating valid command with args."""
        command, args = validate_command("check", "--verbose")

        assert command == "check"
        assert args == ["--verbose"]

    def test_validate_all_valid_commands(self):
        """Test all valid commands."""
        for cmd in VALID_COMMANDS:
            command, args = validate_command(cmd, "")
            assert command == cmd
            assert args == []

    def test_validate_none_command(self):
        """Test command cannot be None."""
        with pytest.raises(ValueError, match="Command cannot be None"):
            validate_command(None, "")

    def test_validate_command_starts_with_double_dash(self):
        """Test command starting with -- is invalid."""
        with pytest.raises(ValueError, match="Invalid command: '--ai-fix'"):
            validate_command("--ai-fix", "")

    def test_validate_command_starts_with_single_dash(self):
        """Test command starting with - is invalid."""
        with pytest.raises(ValueError, match="Invalid command: '-t'"):
            validate_command("-t", "")

    def test_validate_unknown_command(self):
        """Test unknown command raises error."""
        with pytest.raises(ValueError, match="Unknown command: 'invalid'"):
            validate_command("invalid", "")

    def test_validate_args_with_ai_fix_flag(self):
        """Test args containing --ai-fix raises error."""
        with pytest.raises(
            ValueError, match="Do not pass --ai-fix in args parameter"
        ):
            validate_command("test", "--ai-fix")

    def test_validate_command_with_none_args(self):
        """Test command with None args."""
        command, args = validate_command("test", None)

        assert command == "test"
        assert args == []

    def test_validate_command_with_quoted_args(self):
        """Test command with quoted arguments."""
        command, args = validate_command("check", '--message="test message"')

        assert command == "check"
        assert len(args) > 0

    def test_validate_command_with_multiple_args(self):
        """Test command with multiple arguments."""
        command, args = validate_command("lint", "--verbose --strict --fix")

        assert command == "lint"
        assert len(args) == 3
        assert "--verbose" in args
        assert "--strict" in args
        assert "--fix" in args

    def test_valid_commands_set(self):
        """Test VALID_COMMANDS contains expected commands."""
        assert "test" in VALID_COMMANDS
        assert "lint" in VALID_COMMANDS
        assert "check" in VALID_COMMANDS
        assert "format" in VALID_COMMANDS
        assert "security" in VALID_COMMANDS
        assert "complexity" in VALID_COMMANDS
        assert "all" in VALID_COMMANDS


@pytest.mark.unit
class TestCrackerjackCLIFacadeInitialization:
    """Test CrackerjackCLIFacade initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        mock_console = Mock()
        facade = CrackerjackCLIFacade(console=mock_console)

        assert facade.console == mock_console
        assert facade.pkg_path == Path.cwd()

    def test_initialization_with_console(self):
        """Test initialization with provided console."""
        mock_console = Mock()
        facade = CrackerjackCLIFacade(console=mock_console)

        assert facade.console == mock_console

    def test_initialization_with_pkg_path(self, tmp_path):
        """Test initialization with provided pkg_path."""
        facade = CrackerjackCLIFacade(pkg_path=tmp_path)

        assert facade.pkg_path == tmp_path

    def test_initialization_with_both_args(self, tmp_path):
        """Test initialization with both console and pkg_path."""
        mock_console = Mock()
        facade = CrackerjackCLIFacade(console=mock_console, pkg_path=tmp_path)

        assert facade.console == mock_console
        assert facade.pkg_path == tmp_path


@pytest.mark.unit
class TestCrackerjackCLIFacadeProcess:
    """Test process method."""

    @pytest.fixture
    def facade(self):
        """Create facade instance."""
        mock_console = Mock()
        return CrackerjackCLIFacade(console=mock_console)

    @pytest.fixture
    def mock_options(self):
        """Create mock options."""
        options = Mock()
        options.verbose = False
        options.start_mcp_server = False
        options.advanced_batch = False
        options.monitor_dashboard = False
        return options

    def test_process_successful_workflow(self, facade, mock_options):
        """Test successful workflow processing."""
        pipeline = Mock()
        pipeline.run_complete_workflow_sync.return_value = True
        with patch("crackerjack.cli.facade.WorkflowPipeline", return_value=pipeline):
            facade.process(mock_options)
        pipeline.run_complete_workflow_sync.assert_called_once_with(mock_options)

    def test_process_failed_workflow(self, facade, mock_options):
        """Test failed workflow processing."""
        pipeline = Mock()
        pipeline.run_complete_workflow_sync.return_value = False
        with patch("crackerjack.cli.facade.WorkflowPipeline", return_value=pipeline):
            with pytest.raises(SystemExit) as exc_info:
                facade.process(mock_options)
        assert exc_info.value.code == 1

    def test_process_keyboard_interrupt(self, facade, mock_options):
        """Test handling keyboard interrupt."""
        pipeline = Mock()
        pipeline.run_complete_workflow_sync.side_effect = KeyboardInterrupt()
        with patch("crackerjack.cli.facade.WorkflowPipeline", return_value=pipeline):
            with pytest.raises(SystemExit) as exc_info:
                facade.process(mock_options)
        assert exc_info.value.code == 130

    def test_process_unexpected_error(self, facade, mock_options):
        """Test handling unexpected error."""
        pipeline = Mock()
        pipeline.run_complete_workflow_sync.side_effect = Exception("Test error")
        with patch("crackerjack.cli.facade.WorkflowPipeline", return_value=pipeline):
            with pytest.raises(SystemExit) as exc_info:
                facade.process(mock_options)
        assert exc_info.value.code == 1

    def test_process_unexpected_error_verbose(self, facade, mock_options):
        """Test handling unexpected error with verbose mode."""
        mock_options.verbose = True
        pipeline = Mock()
        pipeline.run_complete_workflow_sync.side_effect = Exception("Test error")
        with patch("crackerjack.cli.facade.WorkflowPipeline", return_value=pipeline):
            with pytest.raises(SystemExit):
                facade.process(mock_options)
        assert facade.console.print.call_count >= 1


@pytest.mark.unit
@pytest.mark.asyncio
class TestCrackerjackCLIFacadeProcessAsync:
    """Test async process method."""

    @pytest.fixture
    def facade(self):
        """Create facade instance."""
        mock_console = Mock()
        return CrackerjackCLIFacade(console=mock_console)

    @pytest.fixture
    def mock_options(self):
        """Create mock options."""
        options = Mock()
        options.verbose = False
        options.start_mcp_server = False
        options.advanced_batch = False
        options.monitor_dashboard = False
        return options

    async def test_process_async(self, facade, mock_options):
        """Test async processing."""
        with patch.object(facade, "process") as mock_process:
            await facade.process_async(mock_options)

            mock_process.assert_called_once_with(mock_options)


@pytest.mark.unit
class TestCrackerjackCLIFacadeSpecialModes:
    """Test special mode detection and handling."""

    @pytest.fixture
    def facade(self):
        """Create facade instance."""
        mock_console = Mock()
        return CrackerjackCLIFacade(console=mock_console)

    def test_should_handle_special_mode_mcp_server(self, facade):
        """Test MCP server mode detection."""
        options = Mock()
        options.start_mcp_server = True
        options.advanced_batch = False
        options.monitor_dashboard = False

        assert facade._should_handle_special_mode(options) is True

    def test_should_handle_special_mode_advanced_batch(self, facade):
        """Test advanced batch mode detection."""
        options = Mock()
        options.start_mcp_server = False
        options.advanced_batch = True
        options.monitor_dashboard = False

        assert facade._should_handle_special_mode(options) is True

    def test_should_handle_special_mode_monitor_dashboard(self, facade):
        """Test monitor dashboard mode detection."""
        options = Mock()
        options.start_mcp_server = False
        options.advanced_batch = False
        options.monitor_dashboard = True

        assert facade._should_handle_special_mode(options) is True

    def test_should_handle_special_mode_none(self, facade):
        """Test no special mode."""
        options = Mock()
        options.start_mcp_server = False
        options.advanced_batch = False
        options.monitor_dashboard = False

        assert facade._should_handle_special_mode(options) is False

    def test_handle_special_modes_mcp_server(self, facade):
        """Test handling MCP server mode."""
        options = Mock()
        options.start_mcp_server = True
        options.advanced_batch = False
        options.monitor_dashboard = False

        with patch.object(facade, "_start_mcp_server") as mock_start:
            facade._handle_special_modes(options)

            mock_start.assert_called_once()

    def test_handle_special_modes_advanced_batch(self, facade):
        """Test handling advanced batch mode."""
        options = Mock()
        options.start_mcp_server = False
        options.advanced_batch = True
        options.monitor_dashboard = False

        with patch.object(facade, "_handle_advanced_batch") as mock_batch:
            facade._handle_special_modes(options)

            mock_batch.assert_called_once_with(options)

    def test_handle_special_modes_monitor_dashboard(self, facade):
        """Test handling monitor dashboard mode."""
        options = Mock()
        options.start_mcp_server = False
        options.advanced_batch = False
        options.monitor_dashboard = True
        facade._handle_special_modes(options)


@pytest.mark.unit
class TestCrackerjackCLIFacadeMCPServer:
    """Test MCP server handling."""

    @pytest.fixture
    def facade(self):
        """Create facade instance."""
        mock_console = Mock()
        return CrackerjackCLIFacade(console=mock_console)

    def test_start_mcp_server_success(self, facade):
        """Test successful MCP server start."""
        with patch("crackerjack.mcp.server.main") as mock_start:
            facade._start_mcp_server()

            mock_start.assert_called_once()
            facade.console.print.assert_called()

    def test_start_mcp_server_import_error(self, facade):
        """Test MCP server import error."""
        with patch(
            "crackerjack.mcp.server.main", side_effect=ImportError()
        ):
            with pytest.raises(SystemExit) as exc_info:
                facade._start_mcp_server()

            assert exc_info.value.code == 1
            facade.console.print.assert_called()

    def test_start_mcp_server_unexpected_error(self, facade):
        """Test MCP server unexpected error."""
        with patch(
            "crackerjack.mcp.server.main",
            side_effect=Exception("Server error"),
        ):
            with pytest.raises(SystemExit) as exc_info:
                facade._start_mcp_server()

            assert exc_info.value.code == 1


@pytest.mark.unit
class TestCrackerjackCLIFacadeNotImplemented:
    """Test not implemented special modes."""

    @pytest.fixture
    def facade(self):
        """Create facade instance."""
        mock_console = Mock()
        return CrackerjackCLIFacade(console=mock_console)

    def test_handle_advanced_batch_not_implemented(self, facade):
        """Test advanced batch not implemented."""
        options = Mock()

        with pytest.raises(SystemExit) as exc_info:
            facade._handle_advanced_batch(options)

        assert exc_info.value.code == 1
        facade.console.print.assert_called()
        assert "not yet implemented" in str(facade.console.print.call_args)

    def test_handle_monitor_dashboard_not_implemented(self, facade):
        """Test monitor dashboard not implemented."""
        options = Mock()
        options.start_mcp_server = False
        options.advanced_batch = False
        options.monitor_dashboard = True

        facade._handle_special_modes(options)


@pytest.mark.unit
class TestCreateCrackerjackRunner:
    """Test factory function."""

    def test_create_crackerjack_runner_default(self):
        """Test creating runner with defaults."""
        runner = create_crackerjack_runner()

        assert isinstance(runner, CrackerjackCLIFacade)

    def test_create_crackerjack_runner_with_args(self, tmp_path):
        """Test creating runner with arguments."""
        mock_console = Mock()
        runner = create_crackerjack_runner(console=mock_console, pkg_path=tmp_path)

        assert isinstance(runner, CrackerjackCLIFacade)
        assert runner.console == mock_console
        assert runner.pkg_path == tmp_path


@pytest.mark.unit
class TestCrackerjackCLIFacadeIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def facade(self, tmp_path):
        """Create facade instance with temp path."""
        mock_console = Mock()
        return CrackerjackCLIFacade(console=mock_console, pkg_path=tmp_path)

    def test_full_workflow_with_special_mode(self, facade):
        """Test full workflow with special mode."""
        options = Mock()
        options.start_mcp_server = True
        options.advanced_batch = False
        options.monitor_dashboard = False
        options.verbose = False

        with patch.object(facade, "_start_mcp_server") as mock_start:
            facade.process(options)

            mock_start.assert_called_once()

    def test_full_workflow_without_special_mode(self, facade):
        """Test full workflow without special mode."""
        options = Mock()
        options.start_mcp_server = False
        options.advanced_batch = False
        options.monitor_dashboard = False
        options.verbose = False

        pipeline = Mock()
        pipeline.run_complete_workflow_sync.return_value = True
        with patch("crackerjack.cli.facade.WorkflowPipeline", return_value=pipeline):
            facade.process(options)
        pipeline.run_complete_workflow_sync.assert_called_once_with(options)

    def test_command_validation_integration(self):
        """Test command validation integrates with facade."""
        # Test that facade could use validate_command if needed
        command, args = validate_command("test", "--verbose")

        assert command == "test"
        assert "--verbose" in args

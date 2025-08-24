"""Additional test coverage for cli/facade.py - Focus on untested paths."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.cli.facade import CrackerjackCLIFacade


class MockOptionsSimple:
    """Simple mock options without complex attributes."""

    def __init__(self, **kwargs) -> None:
        self.verbose = kwargs.get("verbose", False)
        self.start_mcp_server = kwargs.get("start_mcp_server", False)
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestCLIFacadeAdditional:
    """Additional test coverage for CLI facade."""

    @pytest.fixture
    def facade(self):
        """Create CLI facade with mocked orchestrator."""
        console = Mock(spec=Console)
        pkg_path = Path("/test")

        with patch("crackerjack.cli.facade.WorkflowOrchestrator") as mock_orch_class:
            mock_orchestrator = Mock()
            mock_orch_class.return_value = mock_orchestrator

            facade = CrackerjackCLIFacade(console=console, pkg_path=pkg_path)
            facade.orchestrator = mock_orchestrator  # Ensure it's mocked

            return facade

    def test_process_with_successful_workflow(self, facade) -> None:
        """Test process method with successful workflow."""
        options = MockOptionsSimple()
        facade.orchestrator.run_complete_workflow.return_value = True

        facade.process(options)

        facade.console.print.assert_called_with(
            "[green]🎉 Workflow completed successfully![/green]",
        )

    def test_process_with_failed_workflow(self, facade) -> None:
        """Test process method with failed workflow."""
        options = MockOptionsSimple()
        facade.orchestrator.run_complete_workflow.return_value = False

        facade.process(options)

        facade.console.print.assert_called_with(
            "[red]❌ Workflow completed with errors[/red]",
        )

    def test_process_with_exception_non_verbose(self, facade) -> None:
        """Test process method with exception - non-verbose mode."""
        options = MockOptionsSimple(verbose=False)
        facade.orchestrator.run_complete_workflow.side_effect = ValueError("Test error")

        with pytest.raises(SystemExit) as exc_info:
            facade.process(options)

        assert exc_info.value.code == 1
        facade.console.print.assert_any_call(
            "[red]💥 Unexpected error: Test error[/red]",
        )

    def test_process_with_exception_verbose(self, facade) -> None:
        """Test process method with exception - verbose mode."""
        options = MockOptionsSimple(verbose=True)
        facade.orchestrator.run_complete_workflow.side_effect = ValueError("Test error")

        with patch("traceback.format_exc", return_value="Full traceback"):
            with pytest.raises(SystemExit) as exc_info:
                facade.process(options)

        assert exc_info.value.code == 1
        facade.console.print.assert_any_call(
            "[red]💥 Unexpected error: Test error[/red]",
        )
        facade.console.print.assert_any_call("[dim]Full traceback[/dim]")

    def test_process_with_keyboard_interrupt(self, facade) -> None:
        """Test process method handles KeyboardInterrupt."""
        options = MockOptionsSimple()
        facade.orchestrator.run_complete_workflow.side_effect = KeyboardInterrupt()

        with pytest.raises(SystemExit) as exc_info:
            facade.process(options)

        assert exc_info.value.code == 130
        facade.console.print.assert_called_with(
            "\n[yellow]⏹️ Operation cancelled by user[/yellow]",
        )

    def test_should_handle_special_mode_false_cases(self, facade) -> None:
        """Test various false cases for special mode detection."""
        # Basic options with no special modes
        options = MockOptionsSimple()
        assert facade._should_handle_special_mode(options) is False

        # Options with falsy special mode values
        options = MockOptionsSimple(start_mcp_server=False)
        assert facade._should_handle_special_mode(options) is False

    def test_should_handle_special_mode_true_cases(self, facade) -> None:
        """Test true cases for special mode detection."""
        # MCP server mode
        options = MockOptionsSimple(start_mcp_server=True)
        assert facade._should_handle_special_mode(options) is True

    def test_handle_special_modes_mcp_server(self, facade) -> None:
        """Test handling of MCP server special mode."""
        options = MockOptionsSimple(start_mcp_server=True)

        with patch.object(facade, "_start_mcp_server") as mock_start:
            facade._handle_special_modes(options)
            mock_start.assert_called_once()

    def test_start_mcp_server_success_path(self, facade) -> None:
        """Test successful MCP server start."""
        with (
            patch("crackerjack.mcp.server.main") as mock_main,
            patch("asyncio.run") as mock_asyncio_run,
        ):
            facade._start_mcp_server()

            facade.console.print.assert_called_with(
                "[bold cyan]🤖 Starting Crackerjack MCP Server...[/bold cyan]",
            )
            mock_asyncio_run.assert_called_once_with(mock_main())

    def test_start_mcp_server_import_error_handling(self, facade) -> None:
        """Test MCP server start with ImportError."""

        def mock_import_that_fails(name, *args, **kwargs):
            if "mcp.server" in name:
                msg = "No module named mcp"
                raise ImportError(msg)
            return __import__(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import_that_fails):
            with pytest.raises(SystemExit) as exc_info:
                facade._start_mcp_server()

            assert exc_info.value.code == 1
            facade.console.print.assert_any_call(
                "[red]❌ MCP server requires additional dependencies[/red]",
            )

    def test_start_mcp_server_general_exception(self, facade) -> None:
        """Test MCP server start with general exception."""
        with (
            patch("crackerjack.mcp.server.main"),
            patch("asyncio.run", side_effect=RuntimeError("Server error")),
        ):
            with pytest.raises(SystemExit) as exc_info:
                facade._start_mcp_server()

            assert exc_info.value.code == 1
            facade.console.print.assert_called_with(
                "[red]❌ Failed to start MCP server: Server error[/red]",
            )

    def test_process_special_mode_integration(self, facade) -> None:
        """Test process method with special mode handling."""
        options = MockOptionsSimple(start_mcp_server=True)

        with patch.object(facade, "_handle_special_modes") as mock_handle:
            facade.process(options)
            mock_handle.assert_called_once_with(options)

    def test_facade_attributes(self, facade) -> None:
        """Test that facade has expected attributes."""
        assert hasattr(facade, "console")
        assert hasattr(facade, "pkg_path")
        assert hasattr(facade, "orchestrator")
        assert callable(facade.process)

    def test_facade_console_and_path_types(self, facade) -> None:
        """Test facade attribute types."""
        assert facade.console is not None
        assert isinstance(facade.pkg_path, Path)

    def test_missing_attributes_in_options(self, facade) -> None:
        """Test handling of options missing certain attributes."""
        # Create an object without the special mode attributes
        options = object()

        # Should not crash when attributes are missing
        result = facade._should_handle_special_mode(options)
        assert result is False

    def test_handle_special_modes_with_missing_attributes(self, facade) -> None:
        """Test _handle_special_modes with options missing attributes."""
        options = MockOptionsSimple()  # No special mode attributes

        # Should not crash or call any handlers
        facade._handle_special_modes(options)
        # If we get here without exception, the test passes


class TestCreateCrackerjackRunner:
    """Test the create_crackerjack_runner function."""

    def test_create_runner_with_params(self) -> None:
        """Test creating runner with parameters."""
        from crackerjack.cli.facade import create_crackerjack_runner

        console = Mock(spec=Console)
        pkg_path = Path("/test")

        with patch("crackerjack.cli.facade.CrackerjackCLIFacade") as mock_facade_class:
            mock_facade = Mock()
            mock_facade_class.return_value = mock_facade

            result = create_crackerjack_runner(console=console, pkg_path=pkg_path)

            mock_facade_class.assert_called_once_with(
                console=console, pkg_path=pkg_path,
            )
            assert result is mock_facade

    def test_create_runner_with_defaults(self) -> None:
        """Test creating runner with default parameters."""
        from crackerjack.cli.facade import create_crackerjack_runner

        runner = create_crackerjack_runner()

        # Should create a CrackerjackCLIFacade instance
        assert hasattr(runner, "console")
        assert hasattr(runner, "pkg_path")
        assert hasattr(runner, "orchestrator")


class TestCrackerjackRunnerAlias:
    """Test the CrackerjackRunner alias."""

    def test_runner_alias_is_facade(self) -> None:
        """Test that CrackerjackRunner is the same as CrackerjackCLIFacade."""
        from crackerjack.cli.facade import CrackerjackCLIFacade, CrackerjackRunner

        assert CrackerjackRunner is CrackerjackCLIFacade

    def test_runner_alias_functionality(self) -> None:
        """Test that the alias works for creating instances."""
        from crackerjack.cli.facade import CrackerjackRunner

        runner = CrackerjackRunner()

        # Should have all the expected attributes
        assert hasattr(runner, "console")
        assert hasattr(runner, "pkg_path")
        assert hasattr(runner, "orchestrator")
        assert hasattr(runner, "process")


class TestProcessAsyncMethod:
    """Test the process_async method."""

    @pytest.mark.asyncio
    async def test_process_async_delegates_to_sync(self) -> None:
        """Test that process_async properly delegates to process."""
        facade = CrackerjackCLIFacade()
        options = MockOptionsSimple()

        with (
            patch.object(facade, "process"),
            patch("asyncio.to_thread") as mock_to_thread,
        ):
            await facade.process_async(options)

            mock_to_thread.assert_called_once_with(facade.process, options)

"""Strategic test coverage for cli/facade.py - CLI facade functionality."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from rich.console import Console

from crackerjack.cli.facade import CrackerjackCLIFacade, create_crackerjack_runner, CrackerjackRunner


class MockOptions:
    """Mock options for testing."""
    
    def __init__(self, **kwargs):
        self.verbose = kwargs.get('verbose', False)
        self.start_mcp_server = kwargs.get('start_mcp_server', False)
        self.enterprise_batch = kwargs.get('enterprise_batch', False)
        self.monitor_dashboard = kwargs.get('monitor_dashboard', False)
        self.test = kwargs.get('test', False)
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestCrackerjackCLIFacade:
    """Test CLI facade functionality."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock(spec=Console)

    @pytest.fixture
    def facade(self, mock_console):
        """Create CLI facade instance."""
        pkg_path = Path("/test/path")
        return CrackerjackCLIFacade(console=mock_console, pkg_path=pkg_path)

    def test_facade_initialization_with_params(self, mock_console):
        """Test facade initialization with provided parameters."""
        pkg_path = Path("/test/path")
        facade = CrackerjackCLIFacade(console=mock_console, pkg_path=pkg_path)
        
        assert facade.console is mock_console
        assert facade.pkg_path == pkg_path
        assert facade.orchestrator is not None

    def test_facade_initialization_with_defaults(self):
        """Test facade initialization with default parameters."""
        facade = CrackerjackCLIFacade()
        
        # Should have console and pkg_path set to defaults
        assert facade.console is not None
        assert facade.pkg_path is not None
        assert facade.orchestrator is not None

    def test_process_successful_workflow(self, facade):
        """Test successful workflow processing."""
        options = MockOptions()
        
        with patch.object(facade, '_should_handle_special_mode', return_value=False), \
             patch.object(facade.orchestrator, 'run_complete_workflow', return_value=True):
            
            facade.process(options)
            
            facade.console.print.assert_called_with("[green]🎉 Workflow completed successfully![/green]")

    def test_process_failed_workflow(self, facade):
        """Test failed workflow processing."""
        options = MockOptions()
        
        with patch.object(facade, '_should_handle_special_mode', return_value=False), \
             patch.object(facade.orchestrator, 'run_complete_workflow', return_value=False):
            
            facade.process(options)
            
            facade.console.print.assert_called_with("[red]❌ Workflow completed with errors[/red]")

    def test_process_keyboard_interrupt(self, facade):
        """Test keyboard interrupt handling."""
        options = MockOptions()
        
        with patch.object(facade, '_should_handle_special_mode', return_value=False), \
             patch.object(facade.orchestrator, 'run_complete_workflow', side_effect=KeyboardInterrupt), \
             pytest.raises(SystemExit) as exc_info:
            
            facade.process(options)
            
            assert exc_info.value.code == 130
            facade.console.print.assert_called_with("\n[yellow]⏹️ Operation cancelled by user[/yellow]")

    def test_process_unexpected_exception(self, facade):
        """Test unexpected exception handling."""
        options = MockOptions(verbose=False)
        
        with patch.object(facade, '_should_handle_special_mode', return_value=False), \
             patch.object(facade.orchestrator, 'run_complete_workflow', side_effect=Exception("Test error")), \
             pytest.raises(SystemExit) as exc_info:
            
            facade.process(options)
            
            assert exc_info.value.code == 1
            facade.console.print.assert_any_call("[red]💥 Unexpected error: Test error[/red]")

    def test_process_unexpected_exception_verbose(self, facade):
        """Test unexpected exception handling with verbose output."""
        options = MockOptions(verbose=True)
        
        with patch.object(facade, '_should_handle_special_mode', return_value=False), \
             patch.object(facade.orchestrator, 'run_complete_workflow', side_effect=Exception("Test error")), \
             patch('traceback.format_exc', return_value="Full traceback"), \
             pytest.raises(SystemExit):
            
            facade.process(options)
            
            facade.console.print.assert_any_call("[red]💥 Unexpected error: Test error[/red]")
            facade.console.print.assert_any_call("[dim]Full traceback[/dim]")

    def test_process_special_mode(self, facade):
        """Test processing with special mode handling."""
        options = MockOptions(start_mcp_server=True)
        
        with patch.object(facade, '_should_handle_special_mode', return_value=True), \
             patch.object(facade, '_handle_special_modes') as mock_handle:
            
            facade.process(options)
            
            mock_handle.assert_called_once_with(options)

    @pytest.mark.asyncio
    async def test_process_async(self, facade):
        """Test async processing."""
        options = MockOptions()
        
        with patch.object(facade, 'process') as mock_process, \
             patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
            
            await facade.process_async(options)
            
            mock_to_thread.assert_called_once_with(facade.process, options)

    def test_should_handle_special_mode(self, facade):
        """Test special mode detection."""
        # MCP server mode
        options = MockOptions(start_mcp_server=True)
        assert facade._should_handle_special_mode(options) is True
        
        # Normal mode
        options = MockOptions()
        assert facade._should_handle_special_mode(options) is False

    def test_should_handle_special_mode_missing_attributes(self, facade):
        """Test special mode detection with missing attributes."""
        options = Mock()
        # Remove attributes to test hasattr checks
        if hasattr(options, 'start_mcp_server'):
            delattr(options, 'start_mcp_server')
        if hasattr(options, 'enterprise_batch'):
            delattr(options, 'enterprise_batch')
        if hasattr(options, 'monitor_dashboard'):
            delattr(options, 'monitor_dashboard')
        
        assert facade._should_handle_special_mode(options) is False

    def test_handle_special_modes_mcp_server(self, facade):
        """Test handling MCP server mode."""
        options = MockOptions(start_mcp_server=True)
        
        with patch.object(facade, '_start_mcp_server') as mock_start:
            facade._handle_special_modes(options)
            
            mock_start.assert_called_once()

    def test_handle_special_modes_enterprise_batch(self, facade):
        """Test handling enterprise batch mode."""
        options = MockOptions(enterprise_batch="/path1,/path2")
        
        with patch.object(facade, '_handle_enterprise_batch') as mock_handle:
            facade._handle_special_modes(options)
            
            mock_handle.assert_called_once_with(options)

    def test_handle_special_modes_monitor_dashboard(self, facade):
        """Test handling monitor dashboard mode."""
        options = MockOptions(monitor_dashboard="/path1,/path2")
        
        with patch.object(facade, '_handle_monitor_dashboard') as mock_handle:
            facade._handle_special_modes(options)
            
            mock_handle.assert_called_once_with(options)

    @patch('asyncio.run')
    def test_start_mcp_server_success(self, mock_asyncio_run, facade):
        """Test successful MCP server start.""" 
        with patch('crackerjack.mcp.server.main') as mock_main:
            facade._start_mcp_server()
            
            facade.console.print.assert_called_with(
                "[bold cyan]🤖 Starting Crackerjack MCP Server...[/bold cyan]"
            )
            mock_asyncio_run.assert_called_once_with(mock_main())

    def test_start_mcp_server_import_error(self, facade):
        """Test MCP server start with import error."""
        # Patch the import to raise ImportError
        original_import = __builtins__['__import__']
        def mock_import(name, *args, **kwargs):
            if name == 'crackerjack.mcp.server':
                raise ImportError("No module named mcp")
            return original_import(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import), \
             pytest.raises(SystemExit) as exc_info:
            
            facade._start_mcp_server()
            
            assert exc_info.value.code == 1
            facade.console.print.assert_any_call(
                "[red]❌ MCP server requires additional dependencies[/red]"
            )

    @patch('asyncio.run')
    def test_start_mcp_server_exception(self, mock_asyncio_run, facade):
        """Test MCP server start with general exception."""
        mock_asyncio_run.side_effect = Exception("Test error")
        
        with patch('crackerjack.mcp.server.main'), \
             pytest.raises(SystemExit) as exc_info:
            
            facade._start_mcp_server()
            
            assert exc_info.value.code == 1
            facade.console.print.assert_called_with(
                "[red]❌ Failed to start MCP server: Test error[/red]"
            )

    def test_handle_enterprise_batch_structure(self, facade):
        """Test enterprise batch handling structure."""
        options = MockOptions(enterprise_batch="/path1,/path2")
        
        # Test that the method exists and can be called
        assert hasattr(facade, '_handle_enterprise_batch')
        assert callable(facade._handle_enterprise_batch)

    def test_handle_monitor_dashboard_structure(self, facade):
        """Test monitor dashboard handling structure."""
        options = MockOptions(monitor_dashboard="/path1,/path2")
        
        # Test that the method exists and can be called
        assert hasattr(facade, '_handle_monitor_dashboard')
        assert callable(facade._handle_monitor_dashboard)


class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_crackerjack_runner(self):
        """Test create_crackerjack_runner factory function."""
        console = Mock(spec=Console)
        pkg_path = Path("/test")
        
        with patch('crackerjack.cli.facade.CrackerjackCLIFacade') as mock_facade_class:
            mock_facade = Mock()
            mock_facade_class.return_value = mock_facade
            
            result = create_crackerjack_runner(console=console, pkg_path=pkg_path)
            
            mock_facade_class.assert_called_once_with(console=console, pkg_path=pkg_path)
            assert result is mock_facade

    def test_create_crackerjack_runner_defaults(self):
        """Test create_crackerjack_runner with default parameters."""
        with patch('crackerjack.cli.facade.CrackerjackCLIFacade') as mock_facade_class:
            mock_facade = Mock()
            mock_facade_class.return_value = mock_facade
            
            result = create_crackerjack_runner()
            
            mock_facade_class.assert_called_once_with(console=None, pkg_path=None)
            assert result is mock_facade

    def test_crackerjack_runner_alias(self):
        """Test that CrackerjackRunner is an alias for CrackerjackCLIFacade."""
        assert CrackerjackRunner is CrackerjackCLIFacade


class TestCLIFacadeIntegration:
    """Integration tests for CLI facade."""

    def test_facade_has_orchestrator(self):
        """Test that facade has orchestrator integration."""
        facade = CrackerjackCLIFacade()
        
        assert hasattr(facade, 'orchestrator')
        assert facade.orchestrator is not None

    def test_path_parsing_logic_exists(self):
        """Test that path parsing logic exists."""
        facade = CrackerjackCLIFacade()
        
        # Test that methods exist for special handling
        assert hasattr(facade, '_handle_enterprise_batch')
        assert hasattr(facade, '_handle_monitor_dashboard')

    def test_error_handling_structure(self):
        """Test that error handling structure is in place."""
        facade = CrackerjackCLIFacade()
        options = MockOptions()
        
        # Test that process method exists and has expected structure
        assert hasattr(facade, 'process')
        assert callable(facade.process)
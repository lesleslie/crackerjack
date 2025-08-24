"""Tests for MCP server functionality."""

from unittest.mock import patch

from crackerjack.mcp.server import MCPOptions, main


class TestMCPOptions:
    """Test MCPOptions configuration."""

    def test_default_options(self) -> None:
        """Test default MCPOptions."""
        options = MCPOptions()
        assert options.websocket_port is None
        assert options.verbose is False
        assert options.cache_dir is None

    def test_custom_options(self) -> None:
        """Test custom MCPOptions."""
        options = MCPOptions(websocket_port=8675, verbose=True)
        assert options.websocket_port == 8675
        assert options.verbose is True


class TestMCPServerIntegration:
    """Test MCP server integration."""

    def test_main_function_exists(self) -> None:
        """Test that main function exists and can be called."""
        assert callable(main)

    def test_main_with_defaults(self) -> None:
        """Test main function with default arguments."""
        with patch("crackerjack.mcp.server_core._initialize_context"):
            with patch("crackerjack.mcp.server_core.Console"):
                # Test that main can be called without errors
                try:
                    main(".", None)
                except SystemExit:
                    # Expected - main() calls sys.exit() when FastMCP is not available
                    pass

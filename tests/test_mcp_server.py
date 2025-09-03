from unittest.mock import patch

from crackerjack.mcp.server import MCPOptions, main


class TestMCPOptions:
    def test_default_options(self) -> None:
        options = MCPOptions()
        assert options.verbose is False
        assert options.commit is False
        assert options.interactive is False

    def test_custom_options(self) -> None:
        options = MCPOptions(verbose=True, commit=True, interactive=True)
        assert options.verbose is True
        assert options.commit is True
        assert options.interactive is True


class TestMCPServerIntegration:
    def test_main_function_exists(self) -> None:
        assert callable(main)

    def test_main_with_defaults(self) -> None:
        with patch("crackerjack.mcp.server_core._initialize_context"):
            with patch("crackerjack.mcp.server_core.Console"):
                try:
                    main(".", None)
                except SystemExit:
                    pass

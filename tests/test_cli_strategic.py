import pytest


@pytest.mark.unit
class TestCLIInteractive:
    def test_cli_interactive_import(self) -> None:
        import crackerjack.cli.interactive

        assert crackerjack.cli.interactive is not None


@pytest.mark.unit
class TestCLIHandlers:
    def test_cli_handlers_import(self) -> None:
        import crackerjack.cli.handlers

        assert crackerjack.cli.handlers is not None


@pytest.mark.unit
class TestCLIFacade:
    def test_cli_facade_import(self) -> None:
        import crackerjack.cli.facade

        assert crackerjack.cli.facade is not None


@pytest.mark.unit
class TestCLIOptions:
    def test_cli_options_import(self) -> None:
        import crackerjack.cli.options

        assert crackerjack.cli.options is not None


@pytest.mark.unit
class TestCLIUtils:
    def test_cli_utils_import(self) -> None:
        import crackerjack.cli.utils

        assert crackerjack.cli.utils is not None

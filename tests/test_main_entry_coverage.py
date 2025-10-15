from crackerjack.__main__ import (
    app,
)
from crackerjack.cli.options import BumpOption, Options


class TestBumpOption:
    def test_bump_option_values(self) -> None:
        assert BumpOption.major.value == "major"
        assert BumpOption.minor.value == "minor"
        assert BumpOption.patch.value == "patch"
        assert BumpOption.interactive.value == "interactive"

    def test_bump_option_from_string(self) -> None:
        assert BumpOption("major") == BumpOption.major
        assert BumpOption("minor") == BumpOption.minor
        assert BumpOption("patch") == BumpOption.patch
        assert BumpOption("interactive") == BumpOption.interactive

    def test_bump_option_str_conversion(self) -> None:
        assert str(BumpOption.major) == "major"
        assert str(BumpOption.minor) == "minor"
        assert str(BumpOption.patch) == "patch"


class TestOptions:
    def test_options_default_values(self) -> None:
        options = Options()

        assert options.clean is False
        assert options.test is False
        assert options.interactive is False
        assert options.verbose is False
        assert options.commit is False
        assert options.publish is None
        assert options.bump is None
        assert options.benchmark is False
        assert options.ai_agent is False

    def test_options_with_values(self) -> None:
        options = Options(
            clean=True,
            test=True,
            interactive=True,
            verbose=True,
            commit=True,
            publish=BumpOption.patch,
            bump=BumpOption.minor,
            benchmark=True,
            ai_agent=True,
        )

        assert options.clean is True
        assert options.test is True
        assert options.interactive is True
        assert options.verbose is True
        assert options.commit is True
        assert options.publish == BumpOption.patch
        assert options.bump == BumpOption.minor
        assert options.benchmark is True
        assert options.ai_agent is True

    def test_options_with_all_flags(self) -> None:
        options = Options(
            commit=True,
            interactive=True,
            no_config_updates=True,
            update_precommit=True,
            verbose=True,
            update_docs=True,
            clean=True,
            test=True,
            benchmark=True,
            test_workers=4,
            test_timeout=300,
            ai_agent=True,
            start_mcp_server=True,
        )

        assert options.commit is True
        assert options.interactive is True
        assert options.no_config_updates is True
        assert options.update_precommit is True
        assert options.verbose is True
        assert options.test_workers == 4
        assert options.test_timeout == 300

    def test_options_validation(self) -> None:
        options = Options(
            publish=BumpOption.patch,
            bump=BumpOption.minor,
            all=BumpOption.major,
        )

        assert options.publish == BumpOption.patch
        assert options.bump == BumpOption.minor
        assert options.all == BumpOption.major


class TestModuleImports:
    def test_console_available(self) -> None:
        assert console is not None
        assert hasattr(console, "print")

    def test_app_available(self) -> None:
        assert app is not None
        assert hasattr(app, "command")

    def test_typer_app_help(self) -> None:
        assert "Crackerjack" in str(app.info.help)
